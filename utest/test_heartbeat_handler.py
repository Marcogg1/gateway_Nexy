#!/usr/bin/env python

"""Unit tests for heartbeat handler."""

import asyncio
import inspect
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.heartbeat_handler import HeartbeatHandler, DEFAULT_HEARTBEAT_INTERVAL


class TestHeartbeatHandler(unittest.TestCase):
    """Test suite for HeartbeatHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_event_sender = MagicMock()
        self.mock_event_sender.send_event = AsyncMock()

        self.mock_reporter = MagicMock()
        self.mock_reporter.report_property = AsyncMock()

        self.mock_desired_handler = MagicMock()
        self.mock_desired_handler.desired_properties = {}

        self.handler = HeartbeatHandler(
            event_sender=self.mock_event_sender,
            reporter=self.mock_reporter,
            desired_handler=self.mock_desired_handler,
        )

    async def test_send_heartbeat_sends_uptime_and_rssi(self):
        """Heartbeat telemetry contains gw.uptime and gw.rssiGsm."""
        await self.handler.send_heartbeat()

        self.mock_event_sender.send_event.assert_called_once()
        payload = self.mock_event_sender.send_event.call_args[0][0]
        self.assertIn("gw.uptime", payload)
        self.assertIn("gw.rssiGsm", payload)
        self.assertIsInstance(payload["gw.uptime"], int)
        self.assertIsInstance(payload["gw.rssiGsm"], str)

    async def test_first_heartbeat_reports_metadata(self):
        """First heartbeat reports gateway metadata via twin properties."""
        await self.handler.send_heartbeat()

        reported_keys = [
            call[0][0] for call in self.mock_reporter.report_property.call_args_list
        ]
        self.assertIn("gw.serialNumber", reported_keys)
        self.assertIn("gw.hardwareVersion", reported_keys)
        self.assertIn("ca.softwareVersion", reported_keys)
        self.assertIn("gw.wifi", reported_keys)

    async def test_second_heartbeat_does_not_report_metadata(self):
        """Subsequent heartbeats do NOT report metadata again."""
        await self.handler.send_heartbeat()
        self.mock_reporter.report_property.reset_mock()

        await self.handler.send_heartbeat()

        self.mock_reporter.report_property.assert_not_called()

    async def test_default_interval(self):
        """Returns default interval when no desired property set."""
        interval = self.handler.get_interval()
        self.assertEqual(interval, DEFAULT_HEARTBEAT_INTERVAL)

    async def test_interval_from_desired_properties(self):
        """Reads interval from device twin desired properties."""
        self.mock_desired_handler.desired_properties = {
            "intervals": {"cloudAgentHeartbeat": "600"}
        }
        interval = self.handler.get_interval()
        self.assertEqual(interval, 600)

    async def test_interval_invalid_value_falls_back_to_default(self):
        """Invalid interval value falls back to default."""
        self.mock_desired_handler.desired_properties = {
            "intervals": {"cloudAgentHeartbeat": "not_a_number"}
        }
        interval = self.handler.get_interval()
        self.assertEqual(interval, DEFAULT_HEARTBEAT_INTERVAL)

    async def test_interval_missing_intervals_key(self):
        """Missing 'intervals' key falls back to default."""
        self.mock_desired_handler.desired_properties = {"other": "stuff"}
        interval = self.handler.get_interval()
        self.assertEqual(interval, DEFAULT_HEARTBEAT_INTERVAL)

    async def test_heartbeat_continues_on_send_event_error(self):
        """Handler does not crash if send_event raises."""
        self.mock_event_sender.send_event = AsyncMock(
            side_effect=Exception("IoT Hub unreachable")
        )

        # Should not raise
        await self.handler.send_heartbeat()

    async def test_get_signal_strength_returns_stub(self):
        """Signal strength is stubbed as N/A."""
        result = self.handler.get_signal_strength()
        self.assertEqual(result, "N/A")

    async def test_get_uptime_returns_int(self):
        """Uptime returns an integer."""
        result = self.handler.get_uptime()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)


def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply decorator to async tests
for name in dir(TestHeartbeatHandler):
    if name.startswith('test_') and inspect.iscoroutinefunction(getattr(TestHeartbeatHandler, name)):
        setattr(TestHeartbeatHandler, name, async_test(getattr(TestHeartbeatHandler, name)))


if __name__ == '__main__':
    unittest.main()
