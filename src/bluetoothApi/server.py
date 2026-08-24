"""BluetoothServer — GATT lifecycle, 4-char WiFi service, and DIS.

Indicate-and-fetch transport: the Status characteristic supports both READ
(returns the cached full Status JSON) and NOTIFY (small tick payload pushed
on every state change). Mobile subscribes to NOTIFY and performs a READ on
each tick to get the full state.

The nexyhub_ble SDK calls characteristic callbacks synchronously from inside
its asyncio event loop. Read callbacks must return bytes immediately; write
callbacks dispatch async controller work via asyncio.create_task().

Advertising parameters are not configurable through the SDK — bless/BlueZ
manage advertising with their internal defaults. Customising the
advertising interval would require bypassing the SDK and calling
LEAdvertisingManager1 over D-Bus directly; that is left to a follow-up.

Factories for the GATT server / service / characteristic types are
injectable so unit tests run without the SDK.
"""

import asyncio
import json
import os
from typing import Any, Callable

from bluetoothApi.controller import WifiController
from bluetoothApi.wifi_cli import WifiCli
from lib.logging_config import get_logger

logger = get_logger(__name__)

# WiFi service UUIDs (modern protocol — clean break from legacy de0a7b0c)
WIFI_SERVICE_UUID = "de0a7b0d-358f-4cef-b778-000000000000"
CHR_STATUS = "de0a7b0d-358f-4cef-b778-000000000001"
CHR_SCAN_REQUEST = "de0a7b0d-358f-4cef-b778-000000000002"
CHR_CONNECT_REQUEST = "de0a7b0d-358f-4cef-b778-000000000003"
CHR_DISCONNECT = "de0a7b0d-358f-4cef-b778-000000000004"

# Standard Device Information Service (Bluetooth SIG)
DIS_SERVICE_UUID = "180A"
DIS_MODEL_UUID = "2A24"
DIS_SERIAL_UUID = "2A25"
DIS_HARDWARE_REV_UUID = "2A27"
DIS_SOFTWARE_REV_UUID = "2A28"
DIS_MANUFACTURER_UUID = "2A29"

DEFAULT_NAME = "Aritco Gateway"
DEFAULT_ADAPTER = "hci0"
DEFAULT_REFRESH_INTERVAL_MS = 2000


# nexyhub_ble is the Esse-ti BLE SDK installed inside the Docker image from
# vendor/nexyhub-ble-sdk/. It is not available in the CI lint environment, so
# pylint cannot resolve the import. Suppress at the import site.
def _default_gatt_server_factory(*, name: str, adapter: str) -> Any:
    from nexyhub_ble import GATTServer  # pylint: disable=import-error,import-outside-toplevel
    return GATTServer(name=name, adapter=adapter)


def _default_service_factory(uuid: str, primary: bool = True) -> Any:
    from nexyhub_ble import Service  # pylint: disable=import-error,import-outside-toplevel
    return Service(uuid=uuid, primary=primary)


def _default_characteristic_factory(
    uuid: str,
    permissions: list[str],
    value: bytes = b"",
    on_read: Callable[[], bytes] | None = None,
    on_write: Callable[[bytes], None] | None = None,
) -> Any:
    from nexyhub_ble import Characteristic  # pylint: disable=import-error,import-outside-toplevel
    return Characteristic(
        uuid=uuid,
        permissions=permissions,
        value=value,
        on_read=on_read,
        on_write=on_write,
    )


class BluetoothServer:
    """Owns the GATT server, controller, and registered services."""

    def __init__(
        self,
        wifi_cli: WifiCli,
        name: str = DEFAULT_NAME,
        adapter: str = DEFAULT_ADAPTER,
        ar_number: str = "",
        model: str = "46044-V1",
        hardware_rev: str = "1.3",
        # TODO: source software_rev from a version file or build-time env var
        # instead of hardcoding. Legacy used a SOFTWARE_REV C macro.
        software_rev: str = "2026.04",
        manufacturer: str = "Aritco Lift AB",
        refresh_interval_ms: int = DEFAULT_REFRESH_INTERVAL_MS,
        gatt_server_factory: Callable[..., Any] = _default_gatt_server_factory,
        service_factory: Callable[..., Any] = _default_service_factory,
        characteristic_factory: Callable[..., Any] = _default_characteristic_factory,
    ) -> None:
        self._wifi_cli = wifi_cli
        self._name = name
        self._adapter = adapter
        self._ar_number = ar_number
        self._model = model
        self._hw_rev = hardware_rev
        self._sw_rev = software_rev
        self._manufacturer = manufacturer
        self._refresh_interval_ms = refresh_interval_ms
        self._gatt_factory = gatt_server_factory
        self._service_factory = service_factory
        self._char_factory = characteristic_factory

        self._controller = WifiController(
            cli=self._wifi_cli,
            on_tick=self._on_tick,
            refresh_interval_s=self._refresh_interval_ms / 1000.0,
        )
        self._server: Any = None
        self._status_char: Any = None
        self._tasks: set[asyncio.Task] = set()
        self._stopping = False

    # --- characteristic callbacks (sync — called from SDK on the loop) ------

    def on_read_status(self) -> bytes:
        """Sync read of the cached full Status JSON."""
        return self._controller.latest_status_json()

    def on_write_scan(self, value: bytes) -> None:
        """Schedule a scan. Body: {} or {\"force\": true}."""
        force = self._parse_force(value)
        self._dispatch(self._controller.request_scan(force=force))

    def on_write_connect(self, value: bytes) -> None:
        """Schedule a connect. Body: {\"ssid\",\"psk\",\"iface\"}."""
        try:
            payload = json.loads(value) if value else {}
        except (json.JSONDecodeError, ValueError):
            self._dispatch(
                self._controller.report_invalid_request(
                    "ConnectRequest body is not JSON"
                )
            )
            return
        if not isinstance(payload, dict):
            self._dispatch(
                self._controller.report_invalid_request(
                    "ConnectRequest body must be an object"
                )
            )
            return
        ssid = payload.get("ssid", "")
        psk = payload.get("psk", "")
        iface = payload.get("iface", "")
        if (
            not isinstance(ssid, str)
            or not isinstance(psk, str)
            or not isinstance(iface, str)
        ):
            self._dispatch(
                self._controller.report_invalid_request(
                    "ssid, psk, and iface must be strings"
                )
            )
            return
        if not ssid and iface == "wlan0":
            self._dispatch(
                self._controller.report_invalid_request(
                    "ssid is required for wlan0"
                )
            )
            return
        self._dispatch(
            self._controller.request_connect(ssid=ssid, psk=psk, iface=iface)
        )

    def on_write_disconnect(self, value: bytes) -> None:
        """Schedule a disconnect. Body ignored."""
        self._dispatch(self._controller.request_disconnect())

    # --- internals ----------------------------------------------------------

    def _dispatch(self, coro: Any) -> None:
        """Schedule a controller coroutine on the running loop.

        Holds a reference to the task (create_task results are only weakly
        referenced by the loop) and logs any exception on completion.
        """
        if self._stopping:
            # A BLE write landing mid-shutdown must not spawn work after
            # stop() has cancelled and gathered the outstanding tasks.
            logger.warning("server stopping; dropping BLE callback")
            coro.close()
            return
        try:
            task = asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            logger.warning("no running loop; dropping BLE callback")
            coro.close()
            return
        self._tasks.add(task)
        task.add_done_callback(self._on_dispatch_done)

    def _on_dispatch_done(self, task: asyncio.Task) -> None:
        """Drop the finished task's reference and log its exception, if any."""
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("BLE dispatch task failed", exc_info=exc)

    @staticmethod
    def _parse_force(value: bytes) -> bool:
        if not value:
            return False
        try:
            payload = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(payload, dict):
            return False
        return bool(payload.get("force", False))

    async def _on_tick(self, tick: bytes) -> None:
        """Push tick payload to the Status characteristic, triggering NOTIFY."""
        if self._status_char is None:
            return
        try:
            self._status_char.value = tick
        except Exception:
            logger.exception("failed to push Status tick")

    def _dis_values(self) -> dict[str, bytes]:
        return {
            DIS_MODEL_UUID: self._model.encode(),
            DIS_SERIAL_UUID: self._ar_number.encode(),
            DIS_HARDWARE_REV_UUID: self._hw_rev.encode(),
            DIS_SOFTWARE_REV_UUID: self._sw_rev.encode(),
            DIS_MANUFACTURER_UUID: self._manufacturer.encode(),
        }

    async def start(self) -> None:
        """Build and start the GATT server, then start the heartbeat ticker."""
        self._server = self._gatt_factory(name=self._name, adapter=self._adapter)

        # WiFi service: Status (read+notify) + 3 write commands
        wifi_service = self._service_factory(uuid=WIFI_SERVICE_UUID)
        self._status_char = self._char_factory(
            uuid=CHR_STATUS,
            permissions=["read", "notify"],
            on_read=self.on_read_status,
        )
        wifi_service.add_characteristic(self._status_char)
        wifi_service.add_characteristic(
            self._char_factory(
                uuid=CHR_SCAN_REQUEST,
                permissions=["write"],
                on_write=self.on_write_scan,
            )
        )
        wifi_service.add_characteristic(
            self._char_factory(
                uuid=CHR_CONNECT_REQUEST,
                permissions=["write"],
                on_write=self.on_write_connect,
            )
        )
        wifi_service.add_characteristic(
            self._char_factory(
                uuid=CHR_DISCONNECT,
                permissions=["write"],
                on_write=self.on_write_disconnect,
            )
        )
        self._server.add_service(wifi_service)

        # DIS — read-only static characteristics
        dis_service = self._service_factory(uuid=DIS_SERVICE_UUID)
        for uuid, value in self._dis_values().items():
            dis_service.add_characteristic(
                self._char_factory(uuid=uuid, permissions=["read"], value=value)
            )
        self._server.add_service(dis_service)

        logger.info(
            "Starting %s BLE service on %s (heartbeat %dms)",
            self._name,
            self._adapter,
            self._refresh_interval_ms,
        )
        await self._server.start()
        await self._controller.start_heartbeat()

    async def stop(self) -> None:
        """Cancel in-flight callbacks, stop heartbeat, stop GATT server."""
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._controller.stop_heartbeat()
        if self._server is not None:
            await self._server.stop()


def build_from_env(wifi_cli: WifiCli) -> BluetoothServer:
    """Build a BluetoothServer reading config from env vars.

    Reads:
      BLE_NAME              (default \"Aritco Gateway\")
      BLE_ADAPTER           (default \"hci0\")
      AR_NUMBER             (default \"\")
      BLE_STATUS_REFRESH_MS (default 2000)
    """
    refresh_raw = os.environ.get("BLE_STATUS_REFRESH_MS")
    try:
        refresh_ms = int(refresh_raw) if refresh_raw else DEFAULT_REFRESH_INTERVAL_MS
    except ValueError:
        logger.warning(
            "Invalid BLE_STATUS_REFRESH_MS=%r, falling back to %d",
            refresh_raw,
            DEFAULT_REFRESH_INTERVAL_MS,
        )
        refresh_ms = DEFAULT_REFRESH_INTERVAL_MS

    return BluetoothServer(
        wifi_cli=wifi_cli,
        name=os.environ.get("BLE_NAME", DEFAULT_NAME),
        adapter=os.environ.get("BLE_ADAPTER", DEFAULT_ADAPTER),
        ar_number=os.environ.get("AR_NUMBER", ""),
        refresh_interval_ms=refresh_ms,
    )
