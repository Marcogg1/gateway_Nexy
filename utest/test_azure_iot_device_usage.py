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
from cloudApi.connection_monitor import ConnectionMonitor
from cloudApi.device_client import DeviceClientFactory
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.dps_client import DPSClient
from cloudApi.event_sender import EventSender
from cloudApi.method_request_handler import MethodRequestHandler
from liftApi.lift_identifier import LiftType


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

    @staticmethod
    def _configure(mock_config):
        mock_config.PROVISIONING_HOST = "host"
        mock_config.DEVICE_NAME = "device"
        mock_config.SCOPE_ID = "scope"
        mock_config.TT_CERT = "cert.pem"
        mock_config.TT_KEY = "key.pem"

    @patch.object(DPSClient, "_shutdown_pipeline", new_callable=AsyncMock)
    @patch("cloudApi.dps_client.ProvisioningDeviceClient")
    @patch("cloudApi.dps_client.Config")
    async def test_register_exception_shuts_down_pipeline(
            self, mock_config, mock_provisioning, mock_shutdown):
        """A register() failure tears the provisioning pipeline down."""
        self._configure(mock_config)
        client = MagicMock()
        client.register = AsyncMock(side_effect=RuntimeError("dps down"))
        mock_provisioning.create_from_x509_certificate.return_value = client

        dps = DPSClient()
        with self.assertRaises(RuntimeError):
            await dps.create_provisioning_device()

        mock_shutdown.assert_awaited_once_with(client)

    def test_sdk_private_surface_still_exists(self):
        """Guard for the private SDK internals _shutdown_pipeline relies on.

        dps_client reaches into provisioning_client._pipeline and
        async_adapter (no public shutdown exists). If an azure-iot-device
        bump removes them, this test fails in CI instead of the pipeline
        leak silently returning in the field.
        """
        from azure.iot.device.aio import (
            ProvisioningDeviceClient as RealProvisioningClient)
        from azure.iot.device.common import async_adapter

        self.assertTrue(hasattr(async_adapter, "emulate_async"))
        self.assertTrue(hasattr(async_adapter, "AwaitableCallback"))
        self.assertTrue(
            hasattr(RealProvisioningClient(MagicMock()), "_pipeline"))

    @patch.object(DPSClient, "_shutdown_pipeline", new_callable=AsyncMock)
    @patch("cloudApi.dps_client.ProvisioningDeviceClient")
    @patch("cloudApi.dps_client.Config")
    async def test_not_assigned_shuts_down_pipeline_and_raises(
            self, mock_config, mock_provisioning, mock_shutdown):
        """A non-assigned registration tears the pipeline down and raises."""
        self._configure(mock_config)
        register_result = SimpleNamespace(
            status="failed", registration_state=None)
        client = MagicMock()
        client.register = AsyncMock(return_value=register_result)
        mock_provisioning.create_from_x509_certificate.return_value = client

        dps = DPSClient()
        with self.assertRaises(Exception):
            await dps.create_provisioning_device()

        mock_shutdown.assert_awaited_once_with(client)


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
        self.assertEqual(message.custom_properties.get("LIFT_TYPE"), "unknown")
        device_client.send_message.assert_awaited_once_with(message)

    @patch("cloudApi.event_sender.Message")
    async def test_send_event_with_ahl_lift_type(self, mock_message):
        message = MagicMock()
        message.custom_properties = {}
        mock_message.return_value = message

        device_client = MagicMock()
        device_client.send_message = AsyncMock()

        sender = EventSender(device_client, LiftType.AHL)
        await sender.send_event({"temp": 21})

        self.assertEqual(message.custom_properties["LIFT_TYPE"], "AHL")

    @patch("cloudApi.event_sender.Message")
    async def test_send_event_with_1k_lift_type(self, mock_message):
        message = MagicMock()
        message.custom_properties = {}
        mock_message.return_value = message

        device_client = MagicMock()
        device_client.send_message = AsyncMock()

        sender = EventSender(device_client, LiftType.ONE_K)
        await sender.send_event({"temp": 21})

        self.assertEqual(message.custom_properties["LIFT_TYPE"], "1k")


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

        proxy = MagicMock()
        reporter = MagicMock()
        desired = MagicMock()
        desired.desired_properties = {}
        handler = MethodRequestHandler(device_client, proxy, reporter, desired)
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

    async def test_create_no_desired_key_defaults_to_empty(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(return_value={})

        handler = await DeviceTwinDesiredHandler.create(device_client)

        self.assertEqual(handler.desired_properties, {})

    async def test_create_raises_when_get_twin_fails(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(side_effect=Exception("connection failed"))

        with self.assertRaises(Exception):
            await DeviceTwinDesiredHandler.create(device_client)

    async def test_listen_for_desired_updates_processes_multiple_patches(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(return_value={"desired": {}})
        device_client.receive_twin_desired_properties_patch = AsyncMock(
            side_effect=[{"mode": "auto"}, {"mode": "manual"}, asyncio.CancelledError()]
        )

        handler = await DeviceTwinDesiredHandler.create(device_client)
        with self.assertRaises(asyncio.CancelledError):
            await handler.listen_for_desired_updates()

        self.assertEqual(device_client.receive_twin_desired_properties_patch.await_count, 3)

    async def test_listen_for_desired_updates_propagates_exception(self):
        device_client = MagicMock()
        device_client.get_twin = AsyncMock(return_value={"desired": {}})
        device_client.receive_twin_desired_properties_patch = AsyncMock(
            side_effect=Exception("connection lost")
        )

        handler = await DeviceTwinDesiredHandler.create(device_client)
        with self.assertRaises(Exception):
            await handler.listen_for_desired_updates()


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


class TestConnectionMonitor(unittest.IsolatedAsyncioTestCase):
    async def test_attach_registers_handlers(self):
        device_client = MagicMock()
        monitor = ConnectionMonitor(device_client)

        monitor.attach()

        self.assertEqual(
            device_client.on_connection_state_change,
            monitor._on_connection_state_change,
        )
        self.assertEqual(
            device_client.on_background_exception,
            monitor._on_background_exception,
        )

    async def test_logs_connected(self):
        device_client = MagicMock()
        device_client.connected = True
        monitor = ConnectionMonitor(device_client)

        with self.assertLogs("cloudApi.connection_monitor", level="INFO") as cm:
            await monitor._on_connection_state_change()

        self.assertIn("Connection to IoT Hub updated: CONNECTED", cm.output[0])

    async def test_logs_disconnected(self):
        device_client = MagicMock()
        device_client.connected = False
        monitor = ConnectionMonitor(device_client)

        with self.assertLogs("cloudApi.connection_monitor", level="INFO") as cm:
            await monitor._on_connection_state_change()

        self.assertIn("Connection to IoT Hub updated: DISCONNECTED", cm.output[0])

    async def test_logs_background_exception(self):
        device_client = MagicMock()
        monitor = ConnectionMonitor(device_client)
        exc = ValueError("pipeline boom")

        with self.assertLogs("cloudApi.connection_monitor", level="ERROR") as cm:
            await monitor._on_background_exception(exc)

        self.assertIn("pipeline boom", cm.output[0])


if __name__ == "__main__":
    unittest.main()
