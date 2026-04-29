"""Tests for state — wire-contract types for the BLE Status payload."""

import json
import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from bluetoothApi.state import (
    MAX_NETWORKS_IN_STATUS,
    ConnectionInfo,
    ErrorCode,
    NetworkInfo,
    Phase,
    Status,
    StatusError,
)


class TestPhase(unittest.TestCase):
    def test_string_values(self):
        self.assertEqual(Phase.IDLE.value, "idle")
        self.assertEqual(Phase.SCANNING.value, "scanning")
        self.assertEqual(Phase.CONNECTING.value, "connecting")
        self.assertEqual(Phase.CONNECTED.value, "connected")
        self.assertEqual(Phase.DISCONNECTED.value, "disconnected")
        self.assertEqual(Phase.ERROR.value, "error")


class TestErrorCode(unittest.TestCase):
    def test_string_values(self):
        self.assertEqual(ErrorCode.PSK_TOO_SHORT.value, "PSK_TOO_SHORT")
        self.assertEqual(ErrorCode.PSK_WRONG.value, "PSK_WRONG")
        self.assertEqual(ErrorCode.SSID_NOT_FOUND.value, "SSID_NOT_FOUND")
        self.assertEqual(ErrorCode.TIMEOUT.value, "TIMEOUT")
        self.assertEqual(ErrorCode.INVALID_REQUEST.value, "INVALID_REQUEST")


class TestFrozenDataclasses(unittest.TestCase):
    def test_network_info_is_frozen(self):
        n = NetworkInfo("Home", -40, "WPA2")
        with self.assertRaises(Exception):
            n.ssid = "Other"  # type: ignore[misc]

    def test_connection_info_is_frozen(self):
        c = ConnectionInfo("Home", -50, "10.0.0.5")
        with self.assertRaises(Exception):
            c.ssid = "Other"  # type: ignore[misc]

    def test_status_error_is_frozen(self):
        e = StatusError("PSK_WRONG", "wrong password")
        with self.assertRaises(Exception):
            e.code = "OK"  # type: ignore[misc]


class TestStatusDefaults(unittest.TestCase):
    def test_defaults(self):
        s = Status()
        self.assertEqual(s.seq, 0)
        self.assertEqual(s.phase, Phase.IDLE)
        self.assertIsNone(s.iface)
        self.assertIsNone(s.current)
        self.assertEqual(s.networks, [])
        self.assertIsNone(s.error)
        self.assertEqual(s.last_updated_ms, 0)

    def test_networks_default_is_fresh_list(self):
        a = Status()
        b = Status()
        a.networks.append(NetworkInfo("x", -40, "WPA2"))
        self.assertEqual(b.networks, [])


class TestNetworkCap(unittest.TestCase):
    def test_max_is_four(self):
        self.assertEqual(MAX_NETWORKS_IN_STATUS, 4)


class TestFullJson(unittest.TestCase):
    def test_default(self):
        decoded = json.loads(Status().to_json())
        self.assertEqual(
            decoded,
            {
                "seq": 0,
                "phase": "idle",
                "iface": None,
                "current": None,
                "networks": [],
                "error": None,
                "last_updated_ms": 0,
            },
        )

    def test_compact_separators(self):
        out = Status().to_json().decode()
        self.assertNotIn(", ", out)
        self.assertNotIn(": ", out)

    def test_connected_with_max_networks_under_512_bytes(self):
        # Worst case: maximum-length SSIDs (32 bytes per 802.11 spec).
        long_ssid = "X" * 32
        status = Status(
            seq=42,
            phase=Phase.CONNECTED,
            iface="wlan0",
            current=ConnectionInfo(long_ssid, -50, "192.168.111.222"),
            networks=[
                NetworkInfo(long_ssid, -40 - i, "WPA2")
                for i in range(MAX_NETWORKS_IN_STATUS)
            ],
            last_updated_ms=1719834567890,
        )
        out = status.to_json()
        self.assertLess(
            len(out),
            512,
            f"Status JSON ({len(out)} bytes) must fit under GATT 512 cap "
            "even with 32-char SSIDs",
        )
        decoded = json.loads(out)
        self.assertEqual(decoded["seq"], 42)
        self.assertEqual(decoded["phase"], "connected")
        self.assertEqual(decoded["iface"], "wlan0")
        self.assertEqual(decoded["current"]["ssid"], long_ssid)
        self.assertEqual(len(decoded["networks"]), MAX_NETWORKS_IN_STATUS)
        self.assertIsNone(decoded["error"])
        self.assertEqual(decoded["last_updated_ms"], 1719834567890)

    def test_error_payload(self):
        status = Status(
            seq=1,
            phase=Phase.ERROR,
            error=StatusError("PSK_WRONG", "wrong password"),
            last_updated_ms=123,
        )
        decoded = json.loads(status.to_json())
        self.assertEqual(decoded["phase"], "error")
        self.assertEqual(
            decoded["error"], {"code": "PSK_WRONG", "message": "wrong password"}
        )


class TestTickJson(unittest.TestCase):
    def test_default(self):
        decoded = json.loads(Status().to_tick_json())
        self.assertEqual(
            decoded,
            {"seq": 0, "phase": "idle", "last_updated_ms": 0},
        )

    def test_only_three_fields(self):
        decoded = json.loads(Status().to_tick_json())
        self.assertEqual(set(decoded.keys()), {"seq", "phase", "last_updated_ms"})

    def test_phase_serializes_as_string(self):
        decoded = json.loads(
            Status(phase=Phase.CONNECTING).to_tick_json()
        )
        self.assertEqual(decoded["phase"], "connecting")

    def test_compact(self):
        out = Status().to_tick_json().decode()
        self.assertNotIn(", ", out)
        self.assertNotIn(": ", out)
        # Tick must be small enough to fit in any reasonable MTU
        self.assertLess(len(out), 200)
