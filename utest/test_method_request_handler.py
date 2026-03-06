#!/usr/bin/env python

"""Unit tests for MethodRequestHandler."""

import os
import sys
import pytest
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


@pytest.fixture
def mock_client():
    """Authenticated IoT Hub device client stub."""
    client = MagicMock()
    client.receive_method_request = AsyncMock()
    client.send_method_response = AsyncMock()
    return client


@pytest.fixture
def handler(mock_client):
    """MethodRequestHandler wired to the mock client."""
    return MethodRequestHandler(mock_client)


def _make_request(method_name, payload=None):
    """Create a fake MethodRequest with the given name and payload."""
    mock_request = MagicMock()
    mock_request.name = method_name
    mock_request.payload = payload
    return mock_request


async def _run_one_request(handler, mock_client, method_name, payload=None):
    """Drive listen_for_method() through exactly one request.

    Returns (status, response_payload) from the response sent to the cloud.
    """
    mock_request = _make_request(method_name, payload)
    mock_client.receive_method_request = AsyncMock(
        side_effect=[mock_request, Exception("stop loop")]
    )
    with patch("cloudApi.method_request_handler.MethodResponse") as mock_mr:
        mock_mr.create_from_method_request.return_value = MagicMock()
        try:
            await handler.listen_for_method()
        except Exception:  # pylint: disable=broad-except
            pass
        args = mock_mr.create_from_method_request.call_args[0]
        return args[1], args[2]


def test_dispatch_table_matches_known_methods(handler):
    """Dispatch table keys match KNOWN_METHODS exactly — no drift in either direction."""
    assert set(handler._dispatch.keys()) == set(KNOWN_METHODS)


@pytest.mark.parametrize("method_name", KNOWN_METHODS)
async def test_known_methods_return_200(handler, mock_client, method_name):
    """All 23 known DDM commands return status 200, result True, and correct message."""
    status, response_payload = await _run_one_request(handler, mock_client, method_name)
    assert status == 200
    assert response_payload["result"] is True
    assert response_payload["message"] == f"{method_name} method executed"


async def test_unknown_method_returns_404(handler, mock_client):
    """Unknown method name returns status 404 with result False."""
    status, response_payload = await _run_one_request(handler, mock_client, "unknown.method")
    assert status == 404
    assert response_payload["result"] is False


async def test_response_sent_for_each_request(handler, mock_client):
    """send_method_response is called exactly once per received request."""
    req1 = _make_request("gw.reboot")
    req2 = _make_request("la.read.parameter")
    mock_client.receive_method_request = AsyncMock(
        side_effect=[req1, req2, Exception("stop loop")]
    )
    with patch("cloudApi.method_request_handler.MethodResponse"):
        try:
            await handler.listen_for_method()
        except Exception:  # pylint: disable=broad-except
            pass
    assert mock_client.send_method_response.call_count == 2


async def test_payload_forwarded_without_crash(handler, mock_client):
    """Handler does not crash when a non-empty payload is received."""
    status, response_payload = await _run_one_request(
        handler, mock_client, "la.write.parameter", payload={"param": "42", "value": "100"}
    )
    assert status == 200
    assert response_payload["result"] is True


async def test_handler_exception_sends_500(handler, mock_client):
    """If a handler raises, a 500 error response is sent instead of crashing the loop."""
    handler._dispatch["gw.reboot"] = AsyncMock(side_effect=RuntimeError("boom"))
    status, response_payload = await _run_one_request(handler, mock_client, "gw.reboot")
    assert status == 500
    assert response_payload["result"] is False
    assert response_payload["message"] == "Internal error"


async def test_handler_exception_loop_continues(handler, mock_client):
    """Loop keeps running after a handler exception — next request is processed normally."""
    req1 = _make_request("gw.reboot")
    req2 = _make_request("la.read.parameter")
    mock_client.receive_method_request = AsyncMock(
        side_effect=[req1, req2, Exception("stop loop")]
    )
    handler._dispatch["gw.reboot"] = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("cloudApi.method_request_handler.MethodResponse"):
        try:
            await handler.listen_for_method()
        except Exception:  # pylint: disable=broad-except
            pass
    # req1 triggers error response, req2 triggers normal response → 2 sends total
    assert mock_client.send_method_response.call_count == 2
