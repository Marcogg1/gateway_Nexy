#!/usr/bin/env python

"""Unit tests for main startup resilience (EG-72)."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

import main
from liftApi.lift_identifier import LiftType


class TestProvisionAndConnect(unittest.IsolatedAsyncioTestCase):
    """Test suite for provision_and_connect retry behaviour."""

    def _setup_mocks(self, mock_dps_cls, mock_factory_cls):
        """Wire DPS and factory mocks to a connectable device client."""
        self.mock_dps = mock_dps_cls.return_value
        self.mock_dps.create_provisioning_device = AsyncMock(
            return_value="registration")
        self.mock_client = MagicMock()
        self.mock_client.connect = AsyncMock()
        self.mock_client.shutdown = AsyncMock()
        mock_factory_cls.return_value.create_client.return_value = self.mock_client

    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_returns_client_on_first_success(
            self, mock_dps_cls, mock_factory_cls, mock_sleep):
        """Successful provisioning and connect returns the device client."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)

        client = await main.provision_and_connect()

        self.assertIs(client, self.mock_client)
        self.mock_client.connect.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_retries_dps_failure_until_success(
            self, mock_dps_cls, mock_factory_cls, mock_sleep):
        """DPS provisioning failures are retried until success."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        self.mock_dps.create_provisioning_device.side_effect = [
            RuntimeError("dps down"),
            RuntimeError("dps down"),
            "registration",
        ]

        client = await main.provision_and_connect()

        self.assertIs(client, self.mock_client)
        self.assertEqual(
            self.mock_dps.create_provisioning_device.await_count, 3)

    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_connect_retried_before_reprovisioning(
            self, mock_dps_cls, mock_factory_cls, mock_sleep):
        """A transient connect failure retries connect on the same registration."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        self.mock_client.connect.side_effect = [RuntimeError("no link"), None]

        client = await main.provision_and_connect()

        self.assertIs(client, self.mock_client)
        self.assertEqual(
            self.mock_dps.create_provisioning_device.await_count, 1)
        self.assertEqual(self.mock_client.connect.await_count, 2)
        self.mock_client.shutdown.assert_not_awaited()

    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_exhausted_connect_attempts_reprovision_and_shutdown(
            self, mock_dps_cls, mock_factory_cls, mock_sleep):
        """Exhausted connect attempts shut the client down and re-provision."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        failures = [RuntimeError("no link")] * main.CONNECT_ATTEMPTS_PER_PROVISION
        self.mock_client.connect.side_effect = failures + [None]

        client = await main.provision_and_connect()

        self.assertIs(client, self.mock_client)
        self.assertEqual(
            self.mock_dps.create_provisioning_device.await_count, 2)
        self.assertEqual(
            self.mock_client.connect.await_count,
            main.CONNECT_ATTEMPTS_PER_PROVISION + 1)
        self.mock_client.shutdown.assert_awaited_once()

    @patch("main.random.random", return_value=0.5)
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_backoff_doubles_and_caps(
            self, mock_dps_cls, mock_factory_cls, mock_sleep, mock_random):
        """Backoff doubles per attempt and is capped at the maximum."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        failures = [RuntimeError("dps down")] * 8
        self.mock_dps.create_provisioning_device.side_effect = (
            failures + ["registration"])

        await main.provision_and_connect()

        delays = [call.args[0] for call in mock_sleep.await_args_list]
        self.assertEqual(delays, [1, 2, 4, 8, 16, 32, 60, 60])

    @patch("main.random.random", side_effect=[0.0, 1.0])
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_backoff_is_jittered(
            self, mock_dps_cls, mock_factory_cls, mock_sleep, mock_random):
        """Each delay is multiplied by a random factor in [0.5, 1.5)."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        self.mock_dps.create_provisioning_device.side_effect = [
            RuntimeError("dps down"),
            RuntimeError("dps down"),
            "registration",
        ]

        await main.provision_and_connect()

        delays = [call.args[0] for call in mock_sleep.await_args_list]
        self.assertEqual(delays, [0.5, 3.0])

    @patch("main.logger")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.DeviceClientFactory")
    @patch("main.DPSClient")
    async def test_traceback_logged_only_on_first_failure(
            self, mock_dps_cls, mock_factory_cls, mock_sleep, mock_logger):
        """First retry logs ERROR with traceback, later retries log WARNING."""
        self._setup_mocks(mock_dps_cls, mock_factory_cls)
        self.mock_dps.create_provisioning_device.side_effect = [
            RuntimeError("dps down"),
            RuntimeError("dps down"),
            "registration",
        ]

        await main.provision_and_connect()

        self.assertEqual(mock_logger.error.call_count, 1)
        self.assertEqual(mock_logger.warning.call_count, 1)


if __name__ == "__main__":
    unittest.main()
