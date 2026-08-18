"""Unit tests for WifiController state machine, notify dispatch, heartbeat."""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from bluetoothApi.controller import WifiController
from bluetoothApi.state import (
    ConnectionInfo,
    ErrorCode,
    NetworkInfo,
    Phase,
)
from bluetoothApi.wifi_cli import ConnectResult


class _FakeCli:
    """Minimal in-memory WifiCli double."""

    def __init__(self) -> None:
        self.scan_result: list[NetworkInfo] = []
        self.scan_raises: type[BaseException] | None = None
        self.connect_return: ConnectResult = ConnectResult("connected", "Home", "10.0.0.5")
        self.connect_raises: type[BaseException] | None = None
        self.status_return: ConnectionInfo | None = None
        self.disconnect_calls: int = 0
        self.connect_calls: list[tuple[str, str]] = []

    async def scan(self) -> list[NetworkInfo]:
        if self.scan_raises is not None:
            raise self.scan_raises("boom")
        return list(self.scan_result)

    async def connect(self, ssid: str, psk: str) -> ConnectResult:
        self.connect_calls.append((ssid, psk))
        if self.connect_raises is not None:
            raise self.connect_raises("boom")
        return self.connect_return

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def get_status(self) -> ConnectionInfo | None:
        return self.status_return


class _Counter:
    """Deterministic monotonic clock."""

    def __init__(self) -> None:
        self.t = 1_000

    def __call__(self) -> int:
        self.t += 1
        return self.t


def _decode_ticks(ticks: list[bytes]) -> list[dict]:
    return [json.loads(t) for t in ticks]


class _Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cli = _FakeCli()
        self.ticks: list[bytes] = []

        async def on_tick(payload: bytes) -> None:
            self.ticks.append(payload)

        self.clock = _Counter()
        self.controller = WifiController(
            cli=self.cli, on_tick=on_tick, clock=self.clock
        )


class TestScan(_Base):
    async def test_success_pushes_two_ticks(self):
        self.cli.scan_result = [NetworkInfo("Home", -40, "WPA2")]
        await self.controller.request_scan()
        decoded = _decode_ticks(self.ticks)
        self.assertEqual([d["phase"] for d in decoded], ["scanning", "idle"])
        # seq is monotonic
        self.assertEqual([d["seq"] for d in decoded], [1, 2])

    async def test_full_status_includes_networks_after_scan(self):
        self.cli.scan_result = [NetworkInfo("Home", -40, "WPA2")]
        await self.controller.request_scan()
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "idle")
        self.assertEqual(len(full["networks"]), 1)
        self.assertEqual(full["networks"][0]["ssid"], "Home")

    async def test_caps_networks_at_four(self):
        self.cli.scan_result = [
            NetworkInfo(f"net-{i}", -40 - i, "WPA2") for i in range(20)
        ]
        await self.controller.request_scan()
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(len(full["networks"]), 4)

    async def test_exception_transitions_to_error(self):
        self.cli.scan_raises = RuntimeError
        await self.controller.request_scan()
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "error")
        self.assertEqual(full["error"]["code"], ErrorCode.TIMEOUT.value)

    async def test_force_overrides_busy_phase(self):
        # Manually mark connecting via internal state, then force scan
        await self.controller.request_connect("Home", "longpassword", "wlan0")
        # connect succeeded → CONNECTED
        await self.controller.request_scan(force=True)
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "idle")


class TestConnect(_Base):
    async def test_wlan0_success(self):
        self.cli.connect_return = ConnectResult("connected", "Home", "10.0.0.5")
        await self.controller.request_connect("Home", "longpsk1234", "wlan0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "connected")
        self.assertEqual(full["iface"], "wlan0")
        self.assertEqual(
            full["current"], {"ssid": "Home", "rssi": 0, "ip": "10.0.0.5"}
        )

    async def test_wlan0_short_psk_short_circuits(self):
        await self.controller.request_connect("Home", "short", "wlan0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "error")
        self.assertEqual(full["error"]["code"], ErrorCode.PSK_TOO_SHORT.value)
        self.assertEqual(self.cli.connect_calls, [])

    async def test_wlan0_associated_becomes_psk_wrong(self):
        self.cli.connect_return = ConnectResult("associated", "Home", "")
        await self.controller.request_connect("Home", "longpsk1234", "wlan0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["error"]["code"], ErrorCode.PSK_WRONG.value)

    async def test_wlan0_error_becomes_ssid_not_found(self):
        self.cli.connect_return = ConnectResult("error", "", "")
        await self.controller.request_connect("Home", "longpsk1234", "wlan0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["error"]["code"], ErrorCode.SSID_NOT_FOUND.value)

    async def test_wlan0_exception_becomes_timeout(self):
        self.cli.connect_raises = RuntimeError
        await self.controller.request_connect("Home", "longpsk1234", "wlan0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["error"]["code"], ErrorCode.TIMEOUT.value)

    async def test_ppp0_no_script_call(self):
        await self.controller.request_connect("", "", "ppp0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "connected")
        self.assertEqual(full["iface"], "ppp0")
        self.assertEqual(self.cli.connect_calls, [])

    async def test_unknown_iface_invalid_request(self):
        await self.controller.request_connect("Home", "longpsk1234", "eth0")
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["error"]["code"], ErrorCode.INVALID_REQUEST.value)


class TestDisconnect(_Base):
    async def test_calls_cli_and_transitions(self):
        await self.controller.request_disconnect()
        full = json.loads(await self.controller.get_status_json())
        self.assertEqual(full["phase"], "disconnected")
        self.assertEqual(self.cli.disconnect_calls, 1)


class TestSeqAndTimestamps(_Base):
    async def test_seq_monotonic_across_operations(self):
        await self.controller.request_scan()
        await self.controller.request_connect("Home", "longpsk1234", "wlan0")
        await self.controller.request_disconnect()
        seqs = [json.loads(t)["seq"] for t in self.ticks]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), len(seqs))  # no duplicates

    async def test_last_updated_ms_advances(self):
        await self.controller.request_scan()
        await self.controller.request_disconnect()
        ts = [json.loads(t)["last_updated_ms"] for t in self.ticks]
        self.assertEqual(ts, sorted(ts))


class TestHeartbeat(unittest.IsolatedAsyncioTestCase):
    # The heartbeat loop's asyncio.sleep is patched to yield without real
    # delay — wall-clock sleeps flake on Windows CI timer resolution.

    async def test_starts_and_stops_cleanly(self):
        cli = _FakeCli()
        ticks: list[bytes] = []
        enough = asyncio.Event()

        async def on_tick(payload: bytes) -> None:
            ticks.append(payload)
            if len(ticks) >= 2:
                enough.set()

        # Capture the real sleep — the patch target is the shared asyncio
        # module, so calling asyncio.sleep inside would hit the mock.
        real_sleep = asyncio.sleep

        async def instant_sleep(_delay: float) -> None:
            await real_sleep(0)

        controller = WifiController(
            cli=cli, on_tick=on_tick, refresh_interval_s=0.01, clock=_Counter()
        )
        with patch(
            "bluetoothApi.controller.asyncio.sleep", side_effect=instant_sleep
        ):
            await controller.start_heartbeat()
            await asyncio.wait_for(enough.wait(), timeout=5)
            await controller.stop_heartbeat()
        self.assertGreaterEqual(len(ticks), 2)

    async def test_refreshes_current_when_connected(self):
        cli = _FakeCli()
        cli.connect_return = ConnectResult("connected", "Home", "10.0.0.5")
        cli.status_return = ConnectionInfo("Home", -42, "10.0.0.5")
        got_tick = asyncio.Event()

        async def on_tick(payload: bytes) -> None:
            got_tick.set()

        # Capture the real sleep — the patch target is the shared asyncio
        # module, so calling asyncio.sleep inside would hit the mock.
        real_sleep = asyncio.sleep

        async def instant_sleep(_delay: float) -> None:
            await real_sleep(0)

        controller = WifiController(
            cli=cli, on_tick=on_tick, refresh_interval_s=0.01, clock=_Counter()
        )
        await controller.request_connect("Home", "longpsk1234", "wlan0")
        # request_connect emits its own tick; only ticks after this point
        # come from the heartbeat (which refreshes before emitting).
        got_tick.clear()
        with patch(
            "bluetoothApi.controller.asyncio.sleep", side_effect=instant_sleep
        ):
            await controller.start_heartbeat()
            await asyncio.wait_for(got_tick.wait(), timeout=5)
            await controller.stop_heartbeat()
        full = json.loads(await controller.get_status_json())
        self.assertEqual(full["current"]["rssi"], -42)


class TestTickPayloadShape(_Base):
    async def test_tick_has_only_three_fields(self):
        await self.controller.request_disconnect()
        decoded = json.loads(self.ticks[0])
        self.assertEqual(set(decoded.keys()), {"seq", "phase", "last_updated_ms"})
