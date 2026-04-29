"""WifiController — state machine, notify dispatch, and heartbeat ticker.

Indicate-and-fetch transport pattern:
  - Every state mutation produces a small "tick" payload pushed via
    `on_tick`. Mobile uses that as a wake-up signal and reads the full
    Status separately via `get_status_json()`.
  - A heartbeat task fires `on_tick` every `refresh_interval_s` seconds
    regardless of phase, so the mobile sees a steady pulse confirming
    the gateway is alive ("socket-like" feel).

Concurrency: one asyncio.Lock serializes all state mutations and snapshot
captures. Notification callbacks run outside the lock so they cannot deadlock
even if they call back into this controller.
"""

import asyncio
import time
from typing import Awaitable, Callable

from bluetoothApi.state import (
    MAX_NETWORKS_IN_STATUS,
    ConnectionInfo,
    ErrorCode,
    Phase,
    Status,
    StatusError,
)
from bluetoothApi.wifi_cli import WifiCli
from lib.logging_config import get_logger

logger = get_logger(__name__)

MIN_PSK_LEN = 8
SUPPORTED_IFACES = ("wlan0", "ppp0")


def _now_ms() -> int:
    return int(time.time() * 1000)


class WifiController:
    """State machine + notify dispatch + heartbeat ticker."""

    def __init__(
        self,
        cli: WifiCli,
        on_tick: Callable[[bytes], Awaitable[None]] | None = None,
        refresh_interval_s: float = 2.0,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._cli = cli
        self._on_tick = on_tick
        self._refresh_interval_s = refresh_interval_s
        self._clock = clock or _now_ms
        self._status = Status(last_updated_ms=self._clock())
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        # Cached JSON snapshot for the sync READ path. Updated atomically on
        # every state mutation under the lock.
        self._latest_status_json: bytes = self._status.to_json()

    def latest_status_json(self) -> bytes:
        """Return the cached full Status JSON (sync — for BLE READ path).

        The SDK calls characteristic on_read callbacks synchronously and
        expects bytes back immediately. The snapshot is updated atomically
        on every state change under the lock; reading the bytes attribute
        is a single Python read so no race occurs.
        """
        return self._latest_status_json

    async def get_status_json(self) -> bytes:
        """Async accessor for tests; equivalent to `latest_status_json()`."""
        async with self._lock:
            return self._status.to_json()

    async def request_scan(self, *, force: bool = False) -> None:
        """Initiate a WiFi scan. Silent no-op if already busy unless force."""
        async with self._lock:
            if self._status.phase in (Phase.SCANNING, Phase.CONNECTING) and not force:
                return
            tick = self._commit(self._with_phase(Phase.SCANNING))
        await self._emit(tick)

        try:
            networks = await self._cli.scan()
        except Exception:
            logger.exception("scan raised; transitioning to ERROR")
            await self._set_error(ErrorCode.TIMEOUT, "scan failed")
            return

        async with self._lock:
            tick = self._commit(
                self._with_phase(
                    Phase.IDLE,
                    networks=networks[:MAX_NETWORKS_IN_STATUS],
                )
            )
        await self._emit(tick)

    async def request_connect(self, ssid: str, psk: str, iface: str) -> None:
        """Atomic connect request — JSON-validated by caller."""
        if iface not in SUPPORTED_IFACES:
            await self._set_error(
                ErrorCode.INVALID_REQUEST, f"unknown iface {iface!r}"
            )
            return

        if iface == "ppp0":
            async with self._lock:
                tick = self._commit(
                    Status(
                        seq=self._status.seq + 1,
                        phase=Phase.CONNECTED,
                        iface="ppp0",
                        networks=self._status.networks,
                        last_updated_ms=self._clock(),
                    )
                )
            await self._emit(tick)
            return

        # iface == "wlan0"
        if len(psk) < MIN_PSK_LEN:
            await self._set_error(
                ErrorCode.PSK_TOO_SHORT,
                f"PSK must be at least {MIN_PSK_LEN} characters",
            )
            return

        async with self._lock:
            if self._status.phase == Phase.CONNECTING:
                # Already connecting — ignore retry
                return
            tick = self._commit(self._with_phase(Phase.CONNECTING, iface="wlan0"))
        await self._emit(tick)

        try:
            result = await self._cli.connect(ssid, psk)
        except Exception:
            logger.exception("connect raised; transitioning to ERROR")
            await self._set_error(ErrorCode.TIMEOUT, "connect timed out")
            return

        if result.status == "connected":
            async with self._lock:
                tick = self._commit(
                    Status(
                        seq=self._status.seq + 1,
                        phase=Phase.CONNECTED,
                        iface="wlan0",
                        current=ConnectionInfo(
                            ssid=result.ssid, rssi=0, ip=result.ip
                        ),
                        networks=self._status.networks,
                        last_updated_ms=self._clock(),
                    )
                )
            await self._emit(tick)
        elif result.status == "associated":
            await self._set_error(
                ErrorCode.PSK_WRONG, "associated but no IP — likely auth failure"
            )
        else:
            await self._set_error(ErrorCode.SSID_NOT_FOUND, "connection failed")

    async def report_invalid_request(self, message: str) -> None:
        """Surface an INVALID_REQUEST from the BLE write layer."""
        await self._set_error(ErrorCode.INVALID_REQUEST, message)

    async def request_disconnect(self) -> None:
        """Disconnect WLAN. Idempotent."""
        try:
            await self._cli.disconnect()
        except Exception:
            logger.exception("disconnect raised; continuing")
        async with self._lock:
            tick = self._commit(
                self._with_phase(
                    Phase.DISCONNECTED,
                    networks=self._status.networks,
                )
            )
        await self._emit(tick)

    async def start_heartbeat(self) -> None:
        """Start the periodic heartbeat ticker."""
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat ticker."""
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        self._heartbeat_task = None

    # --- internals ----------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._refresh_interval_s)
                await self._heartbeat_tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("heartbeat loop crashed; not restarting")

    async def _heartbeat_tick(self) -> None:
        """One heartbeat: refresh CONNECTED state from cli, bump seq, emit."""
        async with self._lock:
            phase = self._status.phase

        # Refresh live RSSI/IP if currently connected
        new_current: ConnectionInfo | None = None
        if phase == Phase.CONNECTED and self._status.iface == "wlan0":
            try:
                new_current = await self._cli.get_status()
            except Exception:
                logger.exception("heartbeat get_status raised; keeping last known")

        async with self._lock:
            tick = self._commit(
                Status(
                    seq=self._status.seq + 1,
                    phase=self._status.phase,
                    iface=self._status.iface,
                    current=new_current if new_current is not None else self._status.current,
                    networks=self._status.networks,
                    error=self._status.error,
                    last_updated_ms=self._clock(),
                )
            )
        await self._emit(tick)

    async def _set_error(self, code: ErrorCode, message: str) -> None:
        async with self._lock:
            tick = self._commit(
                Status(
                    seq=self._status.seq + 1,
                    phase=Phase.ERROR,
                    iface=self._status.iface,
                    networks=self._status.networks,
                    error=StatusError(code=code.value, message=message),
                    last_updated_ms=self._clock(),
                )
            )
        await self._emit(tick)

    def _commit(self, status: Status) -> bytes:
        """Atomically swap in a new Status, refresh JSON cache, return tick.

        Caller must hold the lock.
        """
        self._status = status
        self._latest_status_json = status.to_json()
        return status.to_tick_json()

    def _with_phase(
        self,
        phase: Phase,
        *,
        iface: str | None = ...,  # type: ignore[assignment]
        current: ConnectionInfo | None = None,
        networks: list | None = None,
    ) -> Status:
        """Build a new Status with the new phase. Iface is preserved by default."""
        return Status(
            seq=self._status.seq + 1,
            phase=phase,
            iface=self._status.iface if iface is ... else iface,
            current=current,
            networks=networks if networks is not None else [],
            error=None,
            last_updated_ms=self._clock(),
        )

    async def _emit(self, tick: bytes) -> None:
        if self._on_tick is None:
            return
        try:
            await self._on_tick(tick)
        except Exception:
            logger.exception("on_tick callback raised")
