"""Async wrapper around the Esse-ti `wifi_connect.sh` script.

Translates the script's JSON output into typed Python objects. The `runner`
dependency is an injected async callable so unit tests run without spawning
a real subprocess.

Script contract (verified against the Esse-ti delivery's actual script):
  - `scan` outputs ubus iwinfo scan JSON: {"results":[...]}
  - `connect <ssid> <key> [enc]` returns:
      rc=0, {"status":"connected","ssid":"...","ip":"..."}
      rc=1, {"status":"associated","ssid":"...","ip":""}    (auth/DHCP fail)
      rc=1, {"status":"error","message":"..."}             (any other failure)
  - `disconnect` returns {"status":"disconnected"}, rc=0
  - `status` returns {"status":"connected","ssid":...,"signal":-55,"ip":"..."}
                  or {"status":"disconnected"}
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Awaitable, Callable

from bluetoothApi.state import ConnectionInfo, NetworkInfo
from lib.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_SCRIPT_PATH = "/opt/nexyhub/wifi_connect.sh"
SCAN_TIMEOUT_S = 45.0
CONNECT_TIMEOUT_S = 60.0
STATUS_TIMEOUT_S = 5.0

Runner = Callable[[tuple[str, ...], float], Awaitable[tuple[int, str, str]]]


@dataclass(frozen=True)
class ConnectResult:
    """Raw script outcome from `wifi_connect.sh connect`. Controller maps this
    to a Phase / ErrorCode.
    """

    status: str  # "connected" | "associated" | "error"
    ssid: str
    ip: str


async def _real_runner(args: tuple[str, ...], timeout: float) -> tuple[int, str, str]:
    """Spawn a subprocess, return (rc, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    rc = proc.returncode if proc.returncode is not None else -1
    return rc, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def _security_label(enc: dict) -> str:
    """Map ubus iwinfo encryption object to a compact label."""
    if enc.get("enabled") is False:
        return "none"
    auth = enc.get("authentication") or []
    wpa = enc.get("wpa")
    if isinstance(wpa, list) and wpa:
        label = f"WPA{max(wpa)}"
        if "sae" in auth:
            label = "WPA3" if label != "WPA3" else label
        return label
    if isinstance(wpa, int):
        return f"WPA{wpa}"
    if enc.get("enabled"):
        return "encrypted"
    return "none"


class WifiCli:
    """Facade over the host WiFi configuration script."""

    def __init__(
        self,
        runner: Runner | None = None,
        script_path: str = DEFAULT_SCRIPT_PATH,
    ) -> None:
        self._runner = runner or _real_runner
        self._script = script_path

    async def scan(self) -> list[NetworkInfo]:
        """Run a WiFi scan, return deduplicated networks sorted by signal.

        Raises asyncio.TimeoutError so the controller can map it to a TIMEOUT
        error code rather than silently returning an empty network list.
        """
        try:
            rc, stdout, stderr = await self._runner(
                (self._script, "scan"), SCAN_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.warning("wifi scan timed out")
            raise
        if rc != 0:
            logger.warning("wifi scan rc=%s stderr=%s", rc, stderr[:200])
            return []
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            logger.error("wifi scan returned non-JSON: %s", stdout[:200])
            return []

        seen: dict[str, NetworkInfo] = {}
        for net in data.get("results", []):
            ssid = net.get("ssid", "")
            if not ssid:
                continue
            info = NetworkInfo(
                ssid=ssid,
                rssi=int(net.get("signal", 0)),
                security=_security_label(net.get("encryption", {})),
            )
            existing = seen.get(ssid)
            if existing is None or info.rssi > existing.rssi:
                seen[ssid] = info
        return sorted(seen.values(), key=lambda n: n.rssi, reverse=True)

    async def connect(self, ssid: str, psk: str) -> ConnectResult:
        """Attempt a connection. Returns the raw script status.

        Raises asyncio.TimeoutError so the controller surfaces TIMEOUT instead
        of misclassifying the failure as SSID_NOT_FOUND.
        """
        try:
            _rc, stdout, _stderr = await self._runner(
                (self._script, "connect", ssid, psk), CONNECT_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.warning("wifi connect timed out")
            raise
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            logger.error("wifi connect returned non-JSON: %s", stdout[:200])
            return ConnectResult(status="error", ssid="", ip="")
        return ConnectResult(
            status=str(data.get("status", "error")),
            ssid=str(data.get("ssid", "")),
            ip=str(data.get("ip", "")),
        )

    async def disconnect(self) -> None:
        """Bring WLAN down. Best-effort; errors are logged."""
        try:
            rc, _stdout, stderr = await self._runner(
                (self._script, "disconnect"), STATUS_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.warning("wifi disconnect timed out")
            return
        if rc != 0:
            logger.warning("wifi disconnect rc=%s stderr=%s", rc, stderr[:200])

    async def get_status(self) -> ConnectionInfo | None:
        """Return ConnectionInfo when connected to a WiFi network, else None.

        Note: the script's `status` JSON uses field name `signal` (RSSI in
        dBm), not `rssi`. There is no `interface` field — we infer wlan0
        from `status == "connected"`.
        """
        try:
            rc, stdout, _stderr = await self._runner(
                (self._script, "status"), STATUS_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            return None
        if rc != 0:
            return None
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return None
        if data.get("status") != "connected":
            return None
        return ConnectionInfo(
            ssid=str(data.get("ssid", "")),
            rssi=int(data.get("signal", 0)),
            ip=str(data.get("ip", "")),
        )
