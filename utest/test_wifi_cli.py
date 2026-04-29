"""Unit tests for WifiCli with an injected fake runner."""

import json
import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from bluetoothApi.state import ConnectionInfo, NetworkInfo
from bluetoothApi.wifi_cli import ConnectResult, WifiCli


class _Recorder:
    """Records calls and returns pre-programmed (rc, stdout, stderr) results."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], float]] = []
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = {}
        self.default: tuple[int, str, str] = (0, "", "")

    async def __call__(
        self, args: tuple[str, ...], timeout: float
    ) -> tuple[int, str, str]:
        self.calls.append((args, timeout))
        return self.responses.get(args, self.default)


SCRIPT = "/opt/nexyhub/wifi_connect.sh"


class TestScan(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runner = _Recorder()
        self.cli = WifiCli(runner=self.runner, script_path=SCRIPT)

    async def test_parses_iwinfo_output(self):
        self.runner.responses[(SCRIPT, "scan")] = (
            0,
            json.dumps(
                {
                    "results": [
                        {"ssid": "Home", "signal": -40, "encryption": {"wpa": [2]}},
                        {"ssid": "Cafe", "signal": -72, "encryption": {"enabled": False}},
                    ]
                }
            ),
            "",
        )
        result = await self.cli.scan()
        self.assertEqual(
            result,
            [
                NetworkInfo("Home", -40, "WPA2"),
                NetworkInfo("Cafe", -72, "none"),
            ],
        )

    async def test_skips_empty_ssid(self):
        self.runner.responses[(SCRIPT, "scan")] = (
            0,
            json.dumps({"results": [{"ssid": "", "signal": -50, "encryption": {}}]}),
            "",
        )
        self.assertEqual(await self.cli.scan(), [])

    async def test_dedupes_by_ssid_keeping_strongest(self):
        self.runner.responses[(SCRIPT, "scan")] = (
            0,
            json.dumps(
                {
                    "results": [
                        {"ssid": "Home", "signal": -70, "encryption": {"wpa": [2]}},
                        {"ssid": "Home", "signal": -40, "encryption": {"wpa": [2]}},
                    ]
                }
            ),
            "",
        )
        result = await self.cli.scan()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rssi, -40)

    async def test_sorts_by_signal_descending(self):
        self.runner.responses[(SCRIPT, "scan")] = (
            0,
            json.dumps(
                {
                    "results": [
                        {"ssid": "B", "signal": -70, "encryption": {"wpa": [2]}},
                        {"ssid": "A", "signal": -40, "encryption": {"wpa": [2]}},
                    ]
                }
            ),
            "",
        )
        result = await self.cli.scan()
        self.assertEqual([n.ssid for n in result], ["A", "B"])

    async def test_nonzero_rc_returns_empty(self):
        self.runner.default = (1, "", "boom")
        self.assertEqual(await self.cli.scan(), [])

    async def test_invalid_json_returns_empty(self):
        self.runner.default = (0, "not json", "")
        self.assertEqual(await self.cli.scan(), [])


class TestConnect(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runner = _Recorder()
        self.cli = WifiCli(runner=self.runner, script_path=SCRIPT)

    async def test_connected_status(self):
        self.runner.default = (
            0,
            json.dumps({"status": "connected", "ssid": "Home", "ip": "10.0.0.5"}),
            "",
        )
        result = await self.cli.connect("Home", "hunter222")
        self.assertEqual(result, ConnectResult("connected", "Home", "10.0.0.5"))

    async def test_associated_status(self):
        self.runner.default = (
            1,
            json.dumps({"status": "associated", "ssid": "Home", "ip": ""}),
            "",
        )
        result = await self.cli.connect("Home", "wrongpw1")
        self.assertEqual(result.status, "associated")

    async def test_error_status(self):
        self.runner.default = (
            1,
            json.dumps({"status": "error", "message": "Connection failed"}),
            "",
        )
        result = await self.cli.connect("Nope", "hunter222")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.ssid, "")
        self.assertEqual(result.ip, "")

    async def test_invalid_json_falls_back_to_error(self):
        self.runner.default = (1, "garbage", "")
        result = await self.cli.connect("Home", "hunter222")
        self.assertEqual(result, ConnectResult("error", "", ""))


class TestStatus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runner = _Recorder()
        self.cli = WifiCli(runner=self.runner, script_path=SCRIPT)

    async def test_connected_returns_connection_info(self):
        self.runner.default = (
            0,
            json.dumps(
                {
                    "status": "connected",
                    "ssid": "Home",
                    "signal": -55,
                    "ip": "10.0.0.5",
                }
            ),
            "",
        )
        result = await self.cli.get_status()
        self.assertEqual(result, ConnectionInfo("Home", -55, "10.0.0.5"))

    async def test_disconnected_returns_none(self):
        self.runner.default = (0, json.dumps({"status": "disconnected"}), "")
        self.assertIsNone(await self.cli.get_status())

    async def test_invalid_json_returns_none(self):
        self.runner.default = (0, "garbage", "")
        self.assertIsNone(await self.cli.get_status())


class TestDisconnect(unittest.IsolatedAsyncioTestCase):
    async def test_calls_script(self):
        runner = _Recorder()
        runner.default = (0, '{"status":"disconnected"}', "")
        cli = WifiCli(runner=runner, script_path=SCRIPT)
        await cli.disconnect()
        self.assertIn(((SCRIPT, "disconnect"), 5.0), runner.calls)
