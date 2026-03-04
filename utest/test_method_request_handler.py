#!/usr/bin/env python

"""Unit tests for MethodRequestHandler."""

import asyncio
import inspect
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

# pylint: disable=wrong-import-position
from cloudApi.method_request_handler import MethodRequestHandler

KNOWN_METHODS = [
    "gw.read.hostname",
    "gw.read.hw-version",
    "gw.read.bom-revision",
    "gw.read.serial-number",
    "gw.reboot",
    "la.read.ar-number",
    "la.read.parameter",
    "la.read.parameters",
    "la.read.lift-type",
    "la.write.parameter",
    "la.write.read.parameter",
    "la.write.ar-number",
    "la.send.reboot-request",
    "la.send.reset-service-memory",
    "la.script-request",
    "la.gw-log-generate",
    "la.lift-log-generate",
    "la.ll.send-request",
    "la.fwu-trigger",
    "ca.download-file",
    "ca.set.config-item",
    "ca.fwu-trigger",
    "lcm.fwu-trigger",
]


class TestMethodRequestHandler(unittest.TestCase):
    """Test suite for MethodRequestHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_client.receive_method_request = AsyncMock()
        self.mock_client.send_method_response = AsyncMock()
        self.handler = MethodRequestHandler(self.mock_client)

    def _make_request(self, method_name, payload=None):
        """Create a fake MethodRequest with the given name and payload."""
        mock_request = MagicMock()
        mock_request.name = method_name
        mock_request.payload = payload
        return mock_request

    async def _run_one_request(self, method_name, payload=None):
        """Run one loop iteration and return (status, response_payload) from the response.

        Drives listen_for_method() through exactly one request by raising an
        exception on the second receive call, then captures the arguments that
        were passed to MethodResponse.create_from_method_request.
        """
        mock_request = self._make_request(method_name, payload)
        self.mock_client.receive_method_request = AsyncMock(
            side_effect=[mock_request, Exception("stop loop")]
        )
        with patch("cloudApi.method_request_handler.MethodResponse") as mock_mr:
            mock_mr.create_from_method_request.return_value = MagicMock()
            try:
                await self.handler.listen_for_method()
            except Exception:  # pylint: disable=broad-except
                pass
            # create_from_method_request(method_request, status, payload)
            args = mock_mr.create_from_method_request.call_args[0]
            return args[1], args[2]

    async def test_known_methods_return_200(self):
        """All 23 known DDM commands return status 200, result True, and correct message."""
        for method_name in KNOWN_METHODS:
            with self.subTest(method=method_name):
                status, response_payload = await self._run_one_request(method_name)
                self.assertEqual(status, 200)
                self.assertTrue(response_payload["result"])
                self.assertEqual(response_payload["message"], f"{method_name} method executed")

    async def test_unknown_method_returns_404(self):
        """Unknown method name returns status 404 with result False."""
        status, response_payload = await self._run_one_request("unknown.method")
        self.assertEqual(status, 404)
        self.assertFalse(response_payload["result"])

    async def test_response_sent_for_each_request(self):
        """send_method_response is called exactly once per received request."""
        req1 = self._make_request("gw.reboot")
        req2 = self._make_request("la.read.parameter")
        self.mock_client.receive_method_request = AsyncMock(
            side_effect=[req1, req2, Exception("stop loop")]
        )
        with patch("cloudApi.method_request_handler.MethodResponse"):
            try:
                await self.handler.listen_for_method()
            except Exception:  # pylint: disable=broad-except
                pass
        self.assertEqual(self.mock_client.send_method_response.call_count, 2)

    async def test_payload_forwarded_without_crash(self):
        """Handler does not crash when a non-empty payload is received."""
        status, response_payload = await self._run_one_request(
            "la.write.parameter", payload={"param": "42", "value": "100"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(response_payload["result"])

    def test_dispatch_table_matched_known_methods(self):
        """Dispatch table keys match KNOWN_METHODS exactly — no drift in either direction."""
        self.assertEqual(set(self.handler._dispatch.keys()), set(KNOWN_METHODS))


def async_test(coro):
    """Decorator to run async tests synchronously."""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply decorator to all async test methods
for _name in dir(TestMethodRequestHandler):
    if _name.startswith("test_") and inspect.iscoroutinefunction(
        getattr(TestMethodRequestHandler, _name)
    ):
        setattr(
            TestMethodRequestHandler,
            _name,
            async_test(getattr(TestMethodRequestHandler, _name)),
        )


if __name__ == "__main__":
    unittest.main()
