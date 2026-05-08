"""Tests for BluetoothServer — service registration, callbacks, lifecycle."""

import asyncio
import json
import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from bluetoothApi.server import (
    CHR_CONNECT_REQUEST,
    CHR_DISCONNECT,
    CHR_SCAN_REQUEST,
    CHR_STATUS,
    DIS_HARDWARE_REV_UUID,
    DIS_MANUFACTURER_UUID,
    DIS_MODEL_UUID,
    DIS_SERIAL_UUID,
    DIS_SERVICE_UUID,
    DIS_SOFTWARE_REV_UUID,
    WIFI_SERVICE_UUID,
    BluetoothServer,
)
from bluetoothApi.state import NetworkInfo
from bluetoothApi.wifi_cli import ConnectResult


# --- Fakes -------------------------------------------------------------------


class _FakeChar:
    def __init__(
        self,
        uuid: str,
        permissions: list[str],
        value: bytes = b"",
        on_read=None,
        on_write=None,
    ) -> None:
        self.uuid = uuid
        self.permissions = permissions
        self.value: bytes = value
        self.on_read = on_read
        self.on_write = on_write


class _FakeService:
    def __init__(self, uuid: str, primary: bool = True) -> None:
        self.uuid = uuid
        self.characteristics: list[_FakeChar] = []

    def add_characteristic(self, c: _FakeChar) -> None:
        self.characteristics.append(c)


class _FakeGATT:
    def __init__(self, name: str, adapter: str) -> None:
        self.name = name
        self.adapter = adapter
        self.services: list[_FakeService] = []
        self.started = False
        self.stopped = False

    def add_service(self, s: _FakeService) -> None:
        self.services.append(s)

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def _gatt_factory(*, name: str, adapter: str) -> _FakeGATT:
    return _FakeGATT(name=name, adapter=adapter)


class _FakeCli:
    def __init__(self) -> None:
        self.scan_result: list[NetworkInfo] = []
        self.connect_return = ConnectResult("connected", "Home", "10.0.0.5")
        self.status_return = None
        self.connect_calls: list[tuple[str, str]] = []
        self.disconnect_calls = 0

    async def scan(self):
        return list(self.scan_result)

    async def connect(self, ssid, psk):
        self.connect_calls.append((ssid, psk))
        return self.connect_return

    async def disconnect(self):
        self.disconnect_calls += 1

    async def get_status(self):
        return self.status_return


def _make_server(cli: _FakeCli, ar_number: str = "AR12345") -> BluetoothServer:
    return BluetoothServer(
        wifi_cli=cli,  # type: ignore[arg-type]
        name="Aritco Gateway",
        adapter="hci0",
        ar_number=ar_number,
        refresh_interval_ms=60_000,  # disable heartbeat noise in tests
        gatt_server_factory=_gatt_factory,
        service_factory=_FakeService,
        characteristic_factory=_FakeChar,
    )


async def _drain_loop() -> None:
    """Yield long enough for tasks scheduled via create_task to finish.

    Avoids the fragile fixed-iteration-count pattern: a small real sleep
    yields the loop until pending callbacks run, regardless of how many
    iterations the chain needs.
    """
    await asyncio.sleep(0.01)


# --- Tests -------------------------------------------------------------------


class TestServiceRegistration(unittest.IsolatedAsyncioTestCase):
    async def test_registers_wifi_and_dis(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            uuids = {s.uuid for s in server._server.services}  # type: ignore[attr-defined]
            self.assertEqual(uuids, {WIFI_SERVICE_UUID, DIS_SERVICE_UUID})
        finally:
            await server.stop()

    async def test_wifi_service_has_4_chars(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            wifi = next(
                s for s in server._server.services  # type: ignore[attr-defined]
                if s.uuid == WIFI_SERVICE_UUID
            )
            self.assertEqual(len(wifi.characteristics), 4)
            uuids = {c.uuid for c in wifi.characteristics}
            self.assertEqual(
                uuids,
                {CHR_STATUS, CHR_SCAN_REQUEST, CHR_CONNECT_REQUEST, CHR_DISCONNECT},
            )
        finally:
            await server.stop()

    async def test_status_char_is_read_and_notify(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            wifi = next(
                s for s in server._server.services  # type: ignore[attr-defined]
                if s.uuid == WIFI_SERVICE_UUID
            )
            status_char = next(c for c in wifi.characteristics if c.uuid == CHR_STATUS)
            self.assertIn("read", status_char.permissions)
            self.assertIn("notify", status_char.permissions)
        finally:
            await server.stop()

    async def test_dis_has_5_chars(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            dis = next(
                s for s in server._server.services  # type: ignore[attr-defined]
                if s.uuid == DIS_SERVICE_UUID
            )
            self.assertEqual(len(dis.characteristics), 5)
        finally:
            await server.stop()

    async def test_dis_serial_is_ar_number(self):
        server = _make_server(_FakeCli(), ar_number="AR99999")
        await server.start()
        try:
            dis = next(
                s for s in server._server.services  # type: ignore[attr-defined]
                if s.uuid == DIS_SERVICE_UUID
            )
            by_uuid = {c.uuid: c.value for c in dis.characteristics}
            self.assertEqual(by_uuid[DIS_SERIAL_UUID], b"AR99999")
            self.assertEqual(by_uuid[DIS_MODEL_UUID], b"46044-V1")
            self.assertEqual(by_uuid[DIS_HARDWARE_REV_UUID], b"1.3")
            self.assertEqual(by_uuid[DIS_SOFTWARE_REV_UUID], b"0.0.0-dev")
            self.assertEqual(by_uuid[DIS_MANUFACTURER_UUID], b"Aritco Lift AB")
        finally:
            await server.stop()


class TestStatusReadCallback(unittest.IsolatedAsyncioTestCase):
    async def test_returns_full_status_json_sync(self):
        cli = _FakeCli()
        server = _make_server(cli)
        await server.start()
        try:
            payload = server.on_read_status()
            decoded = json.loads(payload)
            self.assertEqual(decoded["phase"], "idle")
            self.assertEqual(decoded["networks"], [])
            self.assertIn("seq", decoded)
            self.assertIn("last_updated_ms", decoded)
        finally:
            await server.stop()


class TestScanWriteCallback(unittest.IsolatedAsyncioTestCase):
    async def test_empty_body_triggers_scan(self):
        cli = _FakeCli()
        cli.scan_result = [NetworkInfo("Home", -40, "WPA2")]
        server = _make_server(cli)
        await server.start()
        try:
            server.on_write_scan(b"")
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(len(full["networks"]), 1)
        finally:
            await server.stop()

    async def test_force_payload(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            server.on_write_scan(b'{"force":true}')
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(full["phase"], "idle")
        finally:
            await server.stop()


class TestConnectWriteCallback(unittest.IsolatedAsyncioTestCase):
    async def test_valid_connect_request(self):
        cli = _FakeCli()
        cli.connect_return = ConnectResult("connected", "Home", "10.0.0.5")
        server = _make_server(cli)
        await server.start()
        try:
            server.on_write_connect(
                b'{"ssid":"Home","psk":"longpsk1234","iface":"wlan0"}'
            )
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(full["phase"], "connected")
            self.assertEqual(full["iface"], "wlan0")
            self.assertEqual(cli.connect_calls, [("Home", "longpsk1234")])
        finally:
            await server.stop()

    async def test_malformed_json_gives_invalid_request(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            server.on_write_connect(b"not json")
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(full["phase"], "error")
            self.assertEqual(full["error"]["code"], "INVALID_REQUEST")
        finally:
            await server.stop()

    async def test_non_object_payload_gives_invalid_request(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            server.on_write_connect(b'["array","not","object"]')
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(full["error"]["code"], "INVALID_REQUEST")
        finally:
            await server.stop()

    async def test_wlan0_missing_ssid_gives_invalid_request(self):
        server = _make_server(_FakeCli())
        await server.start()
        try:
            server.on_write_connect(
                b'{"ssid":"","psk":"longpsk1234","iface":"wlan0"}'
            )
            await _drain_loop()
            full = json.loads(server.on_read_status())
            self.assertEqual(full["error"]["code"], "INVALID_REQUEST")
        finally:
            await server.stop()


class TestDisconnectWriteCallback(unittest.IsolatedAsyncioTestCase):
    async def test_dispatches(self):
        cli = _FakeCli()
        server = _make_server(cli)
        await server.start()
        try:
            server.on_write_disconnect(b"")
            await _drain_loop()
            self.assertEqual(cli.disconnect_calls, 1)
            full = json.loads(server.on_read_status())
            self.assertEqual(full["phase"], "disconnected")
        finally:
            await server.stop()


class TestStatusNotifyTick(unittest.IsolatedAsyncioTestCase):
    async def test_status_char_value_updates_on_state_change(self):
        cli = _FakeCli()
        server = _make_server(cli)
        await server.start()
        try:
            initial_value = server._status_char.value  # type: ignore[attr-defined]
            server.on_write_disconnect(b"")
            await _drain_loop()
            new_value = server._status_char.value  # type: ignore[attr-defined]
            self.assertNotEqual(initial_value, new_value)
            tick = json.loads(new_value)
            self.assertEqual(set(tick.keys()), {"seq", "phase", "last_updated_ms"})
            self.assertEqual(tick["phase"], "disconnected")
        finally:
            await server.stop()


class TestStartStopLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_stop_calls_underlying_server_stop(self):
        server = _make_server(_FakeCli())
        await server.start()
        await server.stop()
        self.assertTrue(server._server.stopped)  # type: ignore[attr-defined]
