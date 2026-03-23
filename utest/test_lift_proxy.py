"""Unit tests for LiftProxy."""

import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from unittest.mock import patch, MagicMock, AsyncMock

from lib.error_signals import LpCode
from liftApi.lift_identifier import LiftType
from liftApi.lift_proxy import LiftProxy


class TestLpCode(unittest.TestCase):
    """Tests for the LpCode error enum."""

    def test_source_is_lift_proxy(self):
        self.assertEqual(LpCode.SOURCE.value, "LiftProxy")

    def test_has_expected_members(self):
        expected = [
            "SOURCE", "NO_ERR", "INIT_ERR", "IDENTIFY_ERR", "LINK_ERR",
            "PARAM_NOT_IN_DB", "PARAM_NOT_SET", "PARAM_READ_ONLY",
            "COM_ERR", "ARG_ERR", "POLL_ERR", "LOG_ERR", "FILE_ERR",
            "PARTIAL_ERR", "DATA_ERR",
        ]
        actual = [m.name for m in LpCode]
        self.assertEqual(actual, expected)


class LiftProxyTestBase(unittest.IsolatedAsyncioTestCase):
    """Shared setup for LiftProxy tests — patches handlers and libs."""

    def setUp(self):
        self.mock_modbus = MagicMock()
        self.mock_rs232 = MagicMock()

        # Patch handler constructors so no real serial ports are opened
        self.patcher_modbus = patch(
            "liftApi.lift_proxy.ModBusHandler",
            return_value=self.mock_modbus,
        )
        self.patcher_rs232 = patch(
            "liftApi.lift_proxy.Rs232Handler",
            return_value=self.mock_rs232,
        )
        self.patcher_ahl = patch("liftApi.lift_proxy.AhlLib")
        self.patcher_tl = patch("liftApi.lift_proxy.ThousandLib")

        self.MockModBus = self.patcher_modbus.start()
        self.MockRs232 = self.patcher_rs232.start()
        self.MockAhlLib = self.patcher_ahl.start()
        self.MockThousandLib = self.patcher_tl.start()

    def tearDown(self):
        self.patcher_modbus.stop()
        self.patcher_rs232.stop()
        self.patcher_ahl.stop()
        self.patcher_tl.stop()


class TestLiftProxyCreate(LiftProxyTestBase):
    """Tests for LiftProxy.create() async factory."""

    # --- AHL identification ---

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_sets_lift_type(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertEqual(proxy.lift_type, LiftType.AHL)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_sets_ahl_lib(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIs(proxy.lib, self.MockAhlLib.return_value)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_keeps_modbus_handler(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIs(proxy.handler, self.mock_modbus)

    # --- 1k identification ---

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_sets_lift_type(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertEqual(proxy.lift_type, LiftType.ONE_K)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_sets_thousand_lib(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertIs(proxy.lib, self.MockThousandLib.return_value)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_keeps_rs232_handler(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertIs(proxy.handler, self.mock_rs232)

    # --- Unknown identification (all retries exhausted) ---

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_unknown_sets_lift_type(self, mock_identify, _mock_sleep):
        mock_identify.return_value = LiftType.UNKNOWN
        proxy = await LiftProxy.create()
        self.assertEqual(proxy.lift_type, LiftType.UNKNOWN)

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_unknown_handler_is_none(self, mock_identify, _mock_sleep):
        mock_identify.return_value = LiftType.UNKNOWN
        proxy = await LiftProxy.create()
        self.assertIsNone(proxy.handler)

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_unknown_lib_is_none(self, mock_identify, _mock_sleep):
        mock_identify.return_value = LiftType.UNKNOWN
        proxy = await LiftProxy.create()
        self.assertIsNone(proxy.lib)

    # --- Handler creation ---

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_both_handlers_created_during_init(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        await LiftProxy.create()
        self.MockModBus.assert_called_once()
        self.MockRs232.assert_called_once()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_identify_called_with_both_handlers(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        await LiftProxy.create()
        mock_identify.assert_called_once_with(self.mock_modbus, self.mock_rs232)

    # --- Discards unused handler ---

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_discards_rs232_handler(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIsNot(proxy.handler, self.mock_rs232)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_discards_modbus_handler(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertIsNot(proxy.handler, self.mock_modbus)


class TestLiftProxyRetry(LiftProxyTestBase):
    """Tests for identification retry behavior."""

    def setUp(self):
        super().setUp()
        self.patcher_sleep = patch(
            "liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock
        )
        self.mock_sleep = self.patcher_sleep.start()

    def tearDown(self):
        self.patcher_sleep.stop()
        super().tearDown()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_retries_on_unknown_then_succeeds(self, mock_identify):
        mock_identify.side_effect = [LiftType.UNKNOWN, LiftType.UNKNOWN, LiftType.AHL]
        proxy = await LiftProxy.create()
        self.assertEqual(proxy.lift_type, LiftType.AHL)
        self.assertEqual(mock_identify.call_count, 3)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_sleeps_between_retries(self, mock_identify):
        mock_identify.side_effect = [LiftType.UNKNOWN, LiftType.AHL]
        await LiftProxy.create()
        self.mock_sleep.assert_called_once_with(5)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_no_sleep_on_first_success(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        await LiftProxy.create()
        self.mock_sleep.assert_not_called()

    @patch("liftApi.lift_proxy.IDENTIFY_MAX_RETRIES", 3)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_stops_after_max_retries(self, mock_identify):
        mock_identify.return_value = LiftType.UNKNOWN
        proxy = await LiftProxy.create()
        self.assertEqual(proxy.lift_type, LiftType.UNKNOWN)
        self.assertEqual(mock_identify.call_count, 3)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_no_sleep_after_last_failed_attempt(self, mock_identify):
        mock_identify.return_value = LiftType.UNKNOWN
        await LiftProxy.create()
        # Sleep is called between retries, not after the last one
        self.assertEqual(self.mock_sleep.call_count, 9)  # 10 attempts, 9 sleeps


class TestGetParamValue(unittest.TestCase):
    """Tests for LiftProxy.get_param_value()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.mock_lib = MagicMock()
        self.proxy._lib = self.mock_lib

    def test_returns_value_and_no_err(self):
        self.mock_lib.get_param.return_value = (42, "NO_ERR")
        value, code = self.proxy.get_param_value(100)
        self.assertEqual(value, 42)
        self.assertEqual(code, LpCode.NO_ERR)

    def test_param_not_in_db(self):
        self.mock_lib.get_param.return_value = (-1, "PARAM_NOT_IN_DB")
        value, code = self.proxy.get_param_value(999)
        self.assertEqual(value, -1)
        self.assertEqual(code, LpCode.PARAM_NOT_IN_DB)

    def test_param_not_set(self):
        self.mock_lib.get_param.return_value = (-1, "PARAM_NOT_SET")
        value, code = self.proxy.get_param_value(100)
        self.assertEqual(value, -1)
        self.assertEqual(code, LpCode.PARAM_NOT_SET)

    def test_unknown_error_code_returns_com_err(self):
        self.mock_lib.get_param.return_value = (-1, "SOME_UNKNOWN_CODE")
        value, code = self.proxy.get_param_value(100)
        self.assertEqual(value, -1)
        self.assertEqual(code, LpCode.COM_ERR)

    def test_lib_none_returns_init_err(self):
        self.proxy._lib = None
        value, code = self.proxy.get_param_value(100)
        self.assertIsNone(value)
        self.assertEqual(code, LpCode.INIT_ERR)

    def test_delegates_to_lib_get_param(self):
        self.mock_lib.get_param.return_value = (42, "NO_ERR")
        self.proxy.get_param_value(100)
        self.mock_lib.get_param.assert_called_once_with(100)


if __name__ == "__main__":
    unittest.main()
