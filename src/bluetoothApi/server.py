"""BluetoothServer — GATT lifecycle, 4-char WiFi service, and DIS.

Indicate-and-fetch transport: the Status characteristic supports both READ
(returns full Status JSON) and NOTIFY (small tick payload). Mobile subscribes
to NOTIFY, performs a READ on each tick to get the full state.

Advertising is configured for ~100ms cadence so phones discover the gateway
within ~0.1s. Configurable via BLE_ADV_INTERVAL_MS env var.

Factories for the GATT server / service / characteristic / advertisement
types are injectable so tests run without the nexyhub_ble SDK.
"""

import os
from typing import Any, Callable

from bluetoothApi.controller import WifiController
from bluetoothApi.wifi_cli import WifiCli
from lib.logging_config import get_logger

logger = get_logger(__name__)

# WiFi service UUIDs (modern protocol — clean break from legacy de0a7b0c family)
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
# 152 ms = closest int to Apple Accessory Design Guidelines' recommended
# 152.5 ms (one of the "approved" advertising intervals on iOS). Discovery
# latency stays under ~0.5 s while keeping RF chatter polite. The gateway is
# mains-powered, so dynamic fast/slow adv (Argenox #4) is unnecessary —
# technicians may install the gateway and connect minutes later.
DEFAULT_ADV_INTERVAL_MS = 152
DEFAULT_REFRESH_INTERVAL_MS = 2000


def _default_gatt_server_factory(*, name: str, adapter: str) -> Any:
    from nexyhub_ble import GATTServer  # type: ignore[import-not-found]
    return GATTServer(name=name, adapter=adapter)


def _default_service_factory(uuid: str, primary: bool = True) -> Any:
    from nexyhub_ble import Service  # type: ignore[import-not-found]
    return Service(uuid=uuid, primary=primary)


def _default_characteristic_factory(
    uuid: str,
    permissions: list[str],
    **kwargs: object,
) -> Any:
    from nexyhub_ble import Characteristic  # type: ignore[import-not-found]
    return Characteristic(uuid=uuid, permissions=permissions, **kwargs)


def _default_advertisement_factory(
    *, name: str, service_uuids: list[str], min_interval_ms: int, max_interval_ms: int
) -> Any:
    from nexyhub_ble import Advertisement  # type: ignore[import-not-found]
    return Advertisement(
        name=name,
        service_uuids=service_uuids,
        min_interval_ms=min_interval_ms,
        max_interval_ms=max_interval_ms,
    )


class BluetoothServer:
    """Owns the GATT server, controller, and advertisement.

    Lifecycle:
      start() — register services, set up advertisement, start GATT, start
                heartbeat ticker.
      stop()  — stop heartbeat, stop GATT.
    """

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
        adv_interval_ms: int = DEFAULT_ADV_INTERVAL_MS,
        refresh_interval_ms: int = DEFAULT_REFRESH_INTERVAL_MS,
        gatt_server_factory: Callable[..., Any] = _default_gatt_server_factory,
        service_factory: Callable[..., Any] = _default_service_factory,
        characteristic_factory: Callable[..., Any] = _default_characteristic_factory,
        advertisement_factory: Callable[..., Any] = _default_advertisement_factory,
    ) -> None:
        self._wifi_cli = wifi_cli
        self._name = name
        self._adapter = adapter
        self._ar_number = ar_number
        self._model = model
        self._hw_rev = hardware_rev
        self._sw_rev = software_rev
        self._manufacturer = manufacturer
        self._adv_interval_ms = adv_interval_ms
        self._refresh_interval_ms = refresh_interval_ms
        self._gatt_factory = gatt_server_factory
        self._service_factory = service_factory
        self._char_factory = characteristic_factory
        self._adv_factory = advertisement_factory

        self._controller = WifiController(
            cli=self._wifi_cli,
            on_tick=self._on_tick,
            refresh_interval_s=self._refresh_interval_ms / 1000.0,
        )
        self._server: Any = None
        self._status_char: Any = None

    # --- characteristic callbacks -------------------------------------------

    async def on_read_status(self) -> bytes:
        """READ Status — return full JSON. The BLE stack handles fragmentation."""
        return await self._controller.get_status_json()

    async def on_write_scan(self, value: bytes) -> None:
        """ScanRequest write. Body: {} or {"force": true}."""
        force = self._parse_force(value)
        await self._controller.request_scan(force=force)

    async def on_write_connect(self, value: bytes) -> None:
        """ConnectRequest write. Body: {"ssid","psk","iface"}."""
        import json
        try:
            payload = json.loads(value) if value else {}
        except (json.JSONDecodeError, ValueError):
            await self._controller.report_invalid_request(
                "ConnectRequest body is not JSON"
            )
            return
        if not isinstance(payload, dict):
            await self._controller.report_invalid_request(
                "ConnectRequest body must be an object"
            )
            return
        ssid = payload.get("ssid", "")
        psk = payload.get("psk", "")
        iface = payload.get("iface", "")
        if not isinstance(ssid, str) or not isinstance(psk, str) or not isinstance(iface, str):
            await self._controller.report_invalid_request(
                "ssid, psk, and iface must be strings"
            )
            return
        if not ssid and iface == "wlan0":
            await self._controller.report_invalid_request(
                "ssid is required for wlan0"
            )
            return
        await self._controller.request_connect(ssid=ssid, psk=psk, iface=iface)

    async def on_write_disconnect(self, value: bytes) -> None:
        """Disconnect write. Body ignored."""
        await self._controller.request_disconnect()

    # --- internals ----------------------------------------------------------

    @staticmethod
    def _parse_force(value: bytes) -> bool:
        import json
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

        # Fast advertising: min == max for stable cadence, ~100ms by default
        advertisement = self._adv_factory(
            name=self._name,
            service_uuids=[WIFI_SERVICE_UUID],
            min_interval_ms=self._adv_interval_ms,
            max_interval_ms=self._adv_interval_ms,
        )
        if hasattr(self._server, "set_advertisement"):
            self._server.set_advertisement(advertisement)

        logger.info(
            "Starting %s BLE service on %s (adv %dms, heartbeat %dms)",
            self._name,
            self._adapter,
            self._adv_interval_ms,
            self._refresh_interval_ms,
        )
        await self._server.start()
        await self._controller.start_heartbeat()

    async def stop(self) -> None:
        """Stop heartbeat, stop GATT server."""
        await self._controller.stop_heartbeat()
        if self._server is not None:
            await self._server.stop()


def build_from_env(wifi_cli: WifiCli) -> BluetoothServer:
    """Build a BluetoothServer reading config from env vars.

    Reads:
      BLE_NAME              (default "Aritco Gateway")
      BLE_ADAPTER           (default "hci0")
      AR_NUMBER             (default "")
      BLE_ADV_INTERVAL_MS   (default 100)
      BLE_STATUS_REFRESH_MS (default 2000)
    """
    return BluetoothServer(
        wifi_cli=wifi_cli,
        name=os.environ.get("BLE_NAME", DEFAULT_NAME),
        adapter=os.environ.get("BLE_ADAPTER", DEFAULT_ADAPTER),
        ar_number=os.environ.get("AR_NUMBER", ""),
        adv_interval_ms=int(
            os.environ.get("BLE_ADV_INTERVAL_MS", DEFAULT_ADV_INTERVAL_MS)
        ),
        refresh_interval_ms=int(
            os.environ.get("BLE_STATUS_REFRESH_MS", DEFAULT_REFRESH_INTERVAL_MS)
        ),
    )
