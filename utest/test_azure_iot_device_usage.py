import asyncio
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from cloudApi.blob_upload_handler import upload_to_blob
from cloudApi.device_client import DeviceClientFactory
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.dps_client import DPSClient
from cloudApi.event_sender import EventSender
from cloudApi.method_request_handler import MethodRequestHandler


class TestDPSClient(unittest.IsolatedAsyncioTestCase):
    @patch("cloudApi.dps_client.ProvisioningDeviceClient")
    @patch("cloudApi.dps_client.Config")
    async def test_create_provisioning_device_assigned(self, mock_config, mock_provisioning):
        mock_config.PROVISIONING_HOST = "host"
        mock_config.DEVICE_NAME = "device"
        mock_config.SCOPE_ID = "scope"
        mock_config.TT_CERT = "cert.pem"
        mock_config.TT_KEY = "key.pem"

        registration_state = SimpleNamespace(assigned_hub="hub", device_id="dev")
        register_result = SimpleNamespace(status="assigned", registration_state=registration_state)

        client = MagicMock()
        client.register = AsyncMock(return_value=register_result)
        mock_provisioning.create_from_x509_certificate.return_value = client

        dps = DPSClient()
        result = await dps.create_provisioning_device()

        self.assertIs(result, register_result)
        mock_provisioning.create_from_x509_certificate.assert_called_once()
        client.register.assert_awaited_once()


class TestDeviceClientFactory(unittest.TestCase):
    @patch("cloudApi.device_client.IoTHubDeviceClient")
    def test_create_client(self, mock_device_client):
        registration_state = SimpleNamespace(assigned_hub="hub", device_id="dev")
        registration_result = SimpleNamespace(registration_state=registration_state)
        created_client = MagicMock()
        mock_device_client.create_from_x509_certificate.return_value = created_client

        factory = DeviceClientFactory(registration_result)
        result = factory.create_client()

        self.assertIs(result, created_client)
        mock_device_client.create_from_x509_certificate.assert_called_once()


class TestEventSender(unittest.IsolatedAsyncioTestCase):
    @patch("cloudApi.event_sender.Message")
    async def test_send_event_sends_message(self, mock_message):
        message = MagicMock()
        message.custom_properties = {}
        mock_message.return_value = message

        device_client = MagicMock()
        device_client.send_message = AsyncMock()

        sender = EventSender(device_client)
        payload = {"temp": 21}
        await sender.send_event(payload)

        mock_message.assert_called_once_with(json.dumps(payload))
        self.assertEqual(message.custom_properties.get("LIFT_TYPE"), "1")
        device_client.send_message.assert_awaited_once_with(message)


class TestMethodRequestHandler(unittest.IsolatedAsyncioTestCase):
    @patch("cloudApi.method_request_handler.MethodResponse")
    async def test_listen_for_method_sends_response(self, mock_method_response):
        request = SimpleNamespace(name="la.read.parameter", payload={"k": "v"})
        device_client = MagicMock()
        device_client.receive_method_request = AsyncMock(
            side_effect=[request, asyncio.CancelledError()]
        )
        device_client.send_method_response = AsyncMock()

        response = MagicMock()
        mock_method_response.create_from_method_request.return_value = response

        handler = MethodRequestHandler(device_client)
        with self.assertRaises(asyncio.CancelledError):
            await handler.listen_for_method()

        mock_method_response.create_from_method_request.assert_called_once()
        device_client.send_method_response.assert_awaited_once_with(response)


class TestDeviceTwinDesiredHandler(unittest.IsolatedAsyncioTestCase):
    async def test_create_populates_desired_properties(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(return_value={"desired": {"mode": "auto"}})

        handler = await DeviceTwinDesiredHandler.create(device_client)

        self.assertEqual(handler.desired_properties, {"mode": "auto"})

    async def test_listen_for_desired_updates_loops(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(return_value={"desired": {}})
        device_client.receive_twin_desired_properties_patch = AsyncMock(
            side_effect=[{"mode": "auto"}, asyncio.CancelledError()]
        )

        handler = await DeviceTwinDesiredHandler.create(device_client)
        with self.assertRaises(asyncio.CancelledError):
            await handler.listen_for_desired_updates()

        self.assertGreaterEqual(
            device_client.receive_twin_desired_properties_patch.await_count,
            1
        )


class TestDeviceTwinReporter(unittest.IsolatedAsyncioTestCase):
    async def test_report_property_nested_dict(self):
        device_client = MagicMock()
        device_client.patch_twin_reported_properties = AsyncMock()

        reporter = DeviceTwinReporter(device_client)
        await reporter.report_property("la.arNumber", "AR998877")

        device_client.patch_twin_reported_properties.assert_awaited_once_with(
            {"la": {"arNumber": "AR998877"}}
        )


class TestBlobUploadHandler(unittest.IsolatedAsyncioTestCase):
    @patch("cloudApi.blob_upload_handler.BlobClient")
    async def test_upload_to_blob_success(self, mock_blob_client):
        storage_info = {
            "hostName": "host",
            "containerName": "cont",
            "blobName": "name",
            "sasToken": "?token",
            "correlationId": "corr"
        }
        device_client = MagicMock()
        device_client.get_storage_info_for_blob = AsyncMock(return_value=storage_info)
        device_client.notify_blob_upload_status = AsyncMock()

        blob_instance = MagicMock()
        mock_blob_client.from_blob_url.return_value = blob_instance

        await upload_to_blob(device_client, "blob.bin", b"data")

        device_client.get_storage_info_for_blob.assert_awaited_once_with("blob.bin")
        mock_blob_client.from_blob_url.assert_called_once()
        blob_instance.upload_blob.assert_called_once_with(b"data", overwrite=True)
        device_client.notify_blob_upload_status.assert_awaited_once_with(
            "corr",
            True,
            200,
            "OK"
        )

    @patch("cloudApi.blob_upload_handler.BlobClient")
    async def test_upload_to_blob_failure_reports_error(self, mock_blob_client):
        storage_info = {
            "hostName": "host",
            "containerName": "cont",
            "blobName": "name",
            "sasToken": "?token",
            "correlationId": "corr"
        }
        device_client = MagicMock()
        device_client.get_storage_info_for_blob = AsyncMock(return_value=storage_info)
        device_client.notify_blob_upload_status = AsyncMock()

        blob_instance = MagicMock()
        blob_instance.upload_blob.side_effect = Exception("boom")
        mock_blob_client.from_blob_url.return_value = blob_instance

        await upload_to_blob(device_client, "blob.bin", b"data")

        device_client.notify_blob_upload_status.assert_awaited_once_with(
            "corr",
            False,
            500,
            "boom"
        )


if __name__ == "__main__":
    unittest.main()
