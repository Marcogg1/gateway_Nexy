"""Unit tests for MethodRequestHandler."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.method_request_handler import MethodRequestHandler
from lib.error_signals import LpCode
from liftApi.lift_identifier import LiftType

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


@patch("cloudApi.method_request_handler._now", return_value=FIXED_TS)
class TestReadDdms(unittest.IsolatedAsyncioTestCase):
    async def test_read_parameter_success(self, _ts):
        proxy = MagicMock()
        proxy.get_param_value.return_value = (125, LpCode.NO_ERR)
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(handler, "la.read.parameter", {"parameter": "121"})
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ts": FIXED_TS, "d": [{"p": "121", "v": "125"}]})

    async def test_read_parameter_error_adds_ec_and_es(self, _ts):
        proxy = MagicMock()
        proxy.get_param_value.return_value = (-1, LpCode.PARAM_NOT_IN_DB)
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(handler, "la.read.parameter", {"parameter": "550"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["es"], "LiftProxy")
        self.assertEqual(payload["d"][0]["ec"], "PARAM_NOT_IN_DB")

    async def test_read_parameter_missing_field_400(self, _ts):
        handler = make_handler()
        status, payload = await run_one(handler, "la.read.parameter", {})
        self.assertEqual(status, 400)
        self.assertEqual(payload["ec"], "ARG_ERR")

    async def test_read_parameters_mixed(self, _ts):
        proxy = MagicMock()
        proxy.get_param_value.side_effect = [(125, LpCode.NO_ERR), (-1, LpCode.PARAM_NOT_IN_DB)]
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.read.parameters", {"parameters": ["121", "550"]})
        self.assertEqual(status, 200)
        self.assertEqual(payload["d"][0], {"p": "121", "v": "125"})
        self.assertEqual(payload["d"][1]["ec"], "PARAM_NOT_IN_DB")
        self.assertEqual(payload["es"], "LiftProxy")

    async def test_read_parameters_from_to_range(self, _ts):
        proxy = MagicMock()
        proxy.get_param_value.return_value = (1, LpCode.NO_ERR)
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.read.parameters", {"from": 5, "to": 6})
        self.assertEqual([i["p"] for i in payload["d"]], ["5", "6"])

    async def test_read_parameters_bad_payload_400(self, _ts):
        handler = make_handler()
        status, payload = await run_one(handler, "la.read.parameters", {})
        self.assertEqual(status, 400)

    async def test_read_lift_type(self, _ts):
        proxy = MagicMock()
        proxy.lift_type = LiftType.ONE_K
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(handler, "la.read.lift-type", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ts": FIXED_TS, "lt": "2"})


@patch("cloudApi.method_request_handler._now", return_value=FIXED_TS)
class TestWriteDdms(unittest.IsolatedAsyncioTestCase):
    async def test_write_parameter_success_emits_telemetry(self, _ts):
        proxy = MagicMock()
        proxy.write_param = AsyncMock(return_value=(0, "ModBusHandler", "NO_ERR"))
        proxy.push_param_event = AsyncMock()
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.write.parameter", {"parameter": "1", "value": "7"})
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ts": FIXED_TS, "d": [{"p": "1", "v": "7", "s": "0"}]})
        proxy.push_param_event.assert_awaited_once_with([1])

    async def test_write_parameter_failure_no_telemetry(self, _ts):
        proxy = MagicMock()
        proxy.write_param = AsyncMock(return_value=(-1, "ModBusHandler", "LCM_ERR"))
        proxy.push_param_event = AsyncMock()
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.write.parameter", {"parameter": "1", "value": "7"})
        self.assertEqual(payload["d"][0]["s"], "-1")
        self.assertEqual(payload["d"][0]["ec"], "LCM_ERR")
        self.assertEqual(payload["es"], "ModBusHandler")
        proxy.push_param_event.assert_not_awaited()

    async def test_write_parameter_missing_field_400(self, _ts):
        handler = make_handler()
        status, payload = await run_one(handler, "la.write.parameter", {"parameter": "1"})
        self.assertEqual(status, 400)

    async def test_write_read_parameter_collapses_readback(self, _ts):
        proxy = MagicMock()
        proxy.write_param = AsyncMock(return_value=(0, "ModBusHandler", "NO_ERR"))
        proxy.push_param_event = AsyncMock()
        proxy.get_param_value.return_value = (7, LpCode.NO_ERR)
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.write.read.parameter", {"parameter": "1", "value": "7"})
        self.assertEqual(payload, {"ts": FIXED_TS, "d": [{"p": "1", "v": "7", "s": "0"}]})
        proxy.push_param_event.assert_awaited_once_with([1])

    async def test_write_read_parameter_write_fail(self, _ts):
        proxy = MagicMock()
        proxy.write_param = AsyncMock(return_value=(-1, "ModBusHandler", "LINK_ERR"))
        proxy.push_param_event = AsyncMock()
        handler = make_handler(proxy=proxy)
        status, payload = await run_one(
            handler, "la.write.read.parameter", {"parameter": "1", "value": "7"})
        self.assertEqual(payload["d"][0]["ec"], "LINK_ERR")
        self.assertEqual(payload["es"], "ModBusHandler")
        proxy.push_param_event.assert_not_awaited()
