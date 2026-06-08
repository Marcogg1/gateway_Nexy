"""Unit tests for MethodRequestHandler."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.method_request_handler import MethodRequestHandler

KNOWN_METHODS = [
    "gw.read.hostname", "gw.read.hw-version", "gw.read.bom-revision",
    "gw.read.serial-number", "gw.reboot", "la.read.ar-number",
    "la.read.parameter", "la.read.parameters", "la.read.lift-type",
    "la.write.parameter", "la.write.read.parameter", "la.write.ar-number",
    "la.send.reboot-request", "la.send.reset-service-memory", "la.script-request",
    "la.gw-log-generate", "la.lift-log-generate", "la.ll.send-request",
    "la.fwu-trigger", "ca.download-file", "ca.set.config-item",
    "ca.fwu-trigger", "lcm.fwu-trigger",
]

# Fixed timestamp for deterministic envelope assertions.
FIXED_TS = 1711843200


def make_handler(proxy=None, reporter=None, desired=None, client=None):
    """Construct a MethodRequestHandler with mock dependencies."""
    client = client or MagicMock()
    client.receive_method_request = AsyncMock()
    client.send_method_response = AsyncMock()
    proxy = proxy or MagicMock()
    reporter = reporter or MagicMock()
    desired = desired or MagicMock()
    desired.desired_properties = {}
    return MethodRequestHandler(client, proxy, reporter, desired)


def make_request(name, payload=None):
    req = MagicMock()
    req.name = name
    req.payload = payload
    return req


async def run_one(handler, name, payload=None):
    """Drive listen_for_method through one request; return (status, payload)."""
    handler.device_client.receive_method_request = AsyncMock(
        side_effect=[make_request(name, payload), Exception("stop loop")]
    )
    with patch("cloudApi.method_request_handler.MethodResponse") as mock_mr:
        mock_mr.create_from_method_request.return_value = MagicMock()
        try:
            await handler.listen_for_method()
        except Exception:  # pylint: disable=broad-except
            pass
        args = mock_mr.create_from_method_request.call_args[0]
        return args[1], args[2]


class TestDispatch(unittest.IsolatedAsyncioTestCase):
    def test_dispatch_table_matches_known_methods(self):
        handler = make_handler()
        self.assertEqual(set(handler._dispatch.keys()), set(KNOWN_METHODS))

    async def test_unknown_method_returns_404(self):
        handler = make_handler()
        status, payload = await run_one(handler, "unknown.method")
        self.assertEqual(status, 404)
        self.assertFalse(payload["result"])

    async def test_handler_exception_sends_500(self):
        handler = make_handler()
        handler._dispatch["gw.reboot"] = AsyncMock(side_effect=RuntimeError("boom"))
        status, payload = await run_one(handler, "gw.reboot")
        self.assertEqual(status, 500)

    async def test_loop_continues_after_exception(self):
        handler = make_handler()
        handler.device_client.receive_method_request = AsyncMock(
            side_effect=[make_request("gw.reboot"), make_request("la.read.lift-type"),
                         Exception("stop loop")]
        )
        handler._dispatch["gw.reboot"] = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("cloudApi.method_request_handler.MethodResponse"):
            try:
                await handler.listen_for_method()
            except Exception:  # pylint: disable=broad-except
                pass
        self.assertEqual(handler.device_client.send_method_response.call_count, 2)
