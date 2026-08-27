"""Unit tests for LiftProxy."""

import asyncio
import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from unittest.mock import patch, call, MagicMock, AsyncMock

from lib.error_signals import LpCode
from liftApi.lift_identifier import LiftType
from liftApi.lift_proxy import (
    DEFAULT_DAILY_INTERVAL,
    REIDENTIFY_INTERVAL,
    REIDENTIFY_LOG_EVERY,
    LiftProxy,
)


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

        # _detect_ahl_polling_table reads param 127 — default to "not readable"
        self.mock_modbus.read_parameter.return_value = (-1, "ModBusHandler", "LCM_ERR")

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

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_handler_created_with_shared_lib(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.MockRs232.assert_called_once_with(self.MockThousandLib.return_value)

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
        mock_identify.assert_called_once_with(
            self.mock_modbus, self.mock_rs232, quiet=False
        )

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_startup_probe_is_not_quiet(self, mock_identify):
        """The startup burst keeps full probe logging (only the loop is quiet)."""
        mock_identify.return_value = LiftType.AHL
        await LiftProxy.create()
        self.assertFalse(mock_identify.await_args.kwargs["quiet"])

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


class TestBind(LiftProxyTestBase):
    """Tests for the bind step that commits one handler + lib pair."""

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_bind_sets_handler_and_lib(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIs(proxy.handler, self.mock_modbus)
        self.assertIs(proxy.lib, self.MockAhlLib.return_value)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_bind_closes_rs232(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        await LiftProxy.create()
        self.mock_rs232.close.assert_called_once_with()
        self.mock_modbus.close.assert_not_called()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_bind_clears_candidate_refs(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIsNone(proxy._rs232_handler)
        self.assertIsNone(proxy._modbus_handler)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_ahl_bind_rearms_force_read_all(self, _mock_identify):
        proxy = LiftProxy()
        await proxy._create_handlers()
        proxy._force_read_all = False
        await proxy._bind(LiftType.AHL)
        self.assertTrue(proxy._force_read_all)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_bind_sets_handler_and_lib(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertIs(proxy.handler, self.mock_rs232)
        self.assertIs(proxy.lib, self.MockThousandLib.return_value)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_bind_closes_modbus(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        await LiftProxy.create()
        self.mock_modbus.close.assert_called_once_with()
        self.mock_rs232.close.assert_not_called()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_bind_clears_candidate_refs(self, mock_identify):
        mock_identify.return_value = LiftType.ONE_K
        proxy = await LiftProxy.create()
        self.assertIsNone(proxy._modbus_handler)
        self.assertIsNone(proxy._rs232_handler)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_1k_bind_rearms_force_read_all(self, _mock_identify):
        proxy = LiftProxy()
        await proxy._create_handlers()
        proxy._force_read_all = False
        await proxy._bind(LiftType.ONE_K)
        self.assertTrue(proxy._force_read_all)

    # --- UNKNOWN keeps both candidates ---

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_unknown_keeps_both_handlers(self, mock_identify, _mock_sleep):
        mock_identify.return_value = LiftType.UNKNOWN
        proxy = await LiftProxy.create()
        self.assertIs(proxy._modbus_handler, self.mock_modbus)
        self.assertIs(proxy._rs232_handler, self.mock_rs232)

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_unknown_closes_no_handler(self, mock_identify, _mock_sleep):
        mock_identify.return_value = LiftType.UNKNOWN
        await LiftProxy.create()
        self.mock_modbus.close.assert_not_called()
        self.mock_rs232.close.assert_not_called()

    # --- Ordering: _lift_type is published last ---

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_lift_type_set_after_handler_and_lib(self, mock_identify):
        """_lift_type must still be UNKNOWN while the pair is being bound."""
        mock_identify.return_value = LiftType.AHL
        observed = {}

        def record_lift_type():
            observed["lift_type"] = proxy._lift_type
            return MagicMock()

        self.MockAhlLib.side_effect = record_lift_type
        proxy = LiftProxy()
        await proxy._create_handlers()
        await proxy._try_identify()

        self.assertEqual(observed["lift_type"], LiftType.UNKNOWN)
        self.assertEqual(proxy._lift_type, LiftType.AHL)
        self.assertIs(proxy._handler, self.mock_modbus)
        self.assertIsNotNone(proxy._lib)

    # --- A failing bind leaves the proxy untouched (FR-008) ---

    def _assert_unbound(self, proxy):
        """Assert the proxy is still UNKNOWN with both candidates alive."""
        self.assertIsNone(proxy._handler)
        self.assertIsNone(proxy._lib)
        self.assertEqual(proxy._lift_type, LiftType.UNKNOWN)
        self.assertIs(proxy._modbus_handler, self.mock_modbus)
        self.assertIs(proxy._rs232_handler, self.mock_rs232)

    async def test_polling_table_failure_leaves_state_unchanged(self):
        """A raising table detection must not publish a half-bound pair."""
        proxy = LiftProxy()
        await proxy._create_handlers()

        with patch.object(
            LiftProxy,
            "_detect_ahl_polling_table",
            new=AsyncMock(side_effect=RuntimeError("bus")),
        ):
            with self.assertRaises(RuntimeError):
                await proxy._bind(LiftType.AHL)

        self._assert_unbound(proxy)
        self.mock_rs232.close.assert_not_called()
        self.mock_modbus.close.assert_not_called()

    async def test_cancelled_loser_close_leaves_state_unchanged(self):
        """Cancellation on the close() thread hop must not publish either."""
        proxy = LiftProxy()
        await proxy._create_handlers()

        with patch(
            "liftApi.lift_proxy.asyncio.to_thread",
            new=AsyncMock(side_effect=asyncio.CancelledError),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._bind(LiftType.ONE_K)

        self._assert_unbound(proxy)

    async def test_failed_bind_releases_the_handler_lock(self):
        """The lock must not be held after a bind blows up."""
        proxy = LiftProxy()
        await proxy._create_handlers()

        with patch.object(
            LiftProxy,
            "_detect_ahl_polling_table",
            new=AsyncMock(side_effect=RuntimeError("bus")),
        ):
            with self.assertRaises(RuntimeError):
                await proxy._bind(LiftType.AHL)

        self.assertFalse(proxy._handler_lock.locked())


class TestReidentifyLoop(LiftProxyTestBase):
    """Tests for the background re-identification loop (AIOT-183 US1)."""

    async def _unknown_proxy(self):
        """Build a proxy left in the UNKNOWN state with both handlers alive."""
        proxy = LiftProxy()
        await proxy._create_handlers()
        return proxy

    @staticmethod
    def _summary_calls(mock_logger):
        """Count the periodic 'still unidentified' INFO summaries."""
        return [
            c for c in mock_logger.info.call_args_list
            if "still unidentified" in c.args[0]
        ]

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_binds_after_two_unknown_rounds(self, mock_identify, mock_sleep):
        """The loop keeps probing and binds as soon as the lift answers."""
        mock_identify.side_effect = [
            LiftType.UNKNOWN, LiftType.UNKNOWN, LiftType.AHL
        ]
        proxy = await self._unknown_proxy()

        await proxy._reidentify_loop()

        self.assertEqual(proxy.lift_type, LiftType.AHL)
        self.assertEqual(mock_identify.await_count, 3)
        self.assertEqual(mock_sleep.await_count, 3)
        mock_sleep.assert_has_awaits([call(REIDENTIFY_INTERVAL)] * 3)

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_probes_quietly(self, mock_identify, _mock_sleep):
        """Background probes run quiet so failures stay below INFO (FR-010)."""
        mock_identify.side_effect = [LiftType.UNKNOWN, LiftType.AHL]
        proxy = await self._unknown_proxy()

        await proxy._reidentify_loop()

        for probe in mock_identify.await_args_list:
            self.assertTrue(probe.kwargs["quiet"])

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_survives_probe_exception(self, mock_identify, _mock_sleep):
        """A raising probe is logged and the loop keeps going."""
        mock_identify.side_effect = [RuntimeError("bus"), LiftType.ONE_K]
        proxy = await self._unknown_proxy()

        await proxy._reidentify_loop()

        self.assertEqual(proxy.lift_type, LiftType.ONE_K)
        self.assertIs(proxy.handler, self.mock_rs232)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_cancellation_propagates(self, mock_identify):
        """Cancellation must not be swallowed by the exception guard."""
        proxy = await self._unknown_proxy()

        with patch(
            "liftApi.lift_proxy.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._reidentify_loop()

        mock_identify.assert_not_awaited()

    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_returns_immediately_when_identified(self, mock_identify, mock_sleep):
        """An already identified proxy must not probe at all."""
        proxy = await self._unknown_proxy()
        proxy._lift_type = LiftType.AHL

        await proxy._reidentify_loop()

        mock_identify.assert_not_awaited()
        mock_sleep.assert_not_awaited()

    @patch("liftApi.lift_proxy.logger")
    @patch("liftApi.lift_proxy.asyncio.sleep", new_callable=AsyncMock)
    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_log_rate_limited(self, mock_identify, _mock_sleep, mock_logger):
        """One WARNING on the first miss, then a summary every N attempts."""
        unknown_rounds = 25
        mock_identify.side_effect = (
            [LiftType.UNKNOWN] * unknown_rounds + [LiftType.AHL]
        )
        proxy = await self._unknown_proxy()

        await proxy._reidentify_loop()

        self.assertEqual(mock_logger.warning.call_count, 1)
        self.assertEqual(
            len(self._summary_calls(mock_logger)),
            unknown_rounds // REIDENTIFY_LOG_EVERY,
        )

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_run_gathers_reidentify_loop(self, mock_identify):
        """run() drives the loop, and polling resumes with a full read."""
        mock_identify.side_effect = [LiftType.AHL]
        lib = self.MockAhlLib.return_value
        lib.poll_params = AsyncMock(return_value=[])
        lib.DEFAULT_ON_CHANGE_PARAMS = []
        lib.DEFAULT_DAILY_PARAMS = []
        proxy = await self._unknown_proxy()
        desired_handler = MagicMock()
        desired_handler.desired_properties = {}
        real_sleep = asyncio.sleep

        async def fast_sleep(seconds):
            """Park the daily loop, run the other two loops at full speed."""
            if seconds >= DEFAULT_DAILY_INTERVAL:
                await asyncio.Event().wait()
            await real_sleep(0)

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=fast_sleep):
            task = asyncio.create_task(
                proxy.run(AsyncMock(), desired_handler, AsyncMock())
            )
            try:
                # to_thread hops inside _bind need real time, not just yields
                for _ in range(200):
                    await real_sleep(0.005)
                    if any(
                        c.kwargs.get("force_read_all")
                        for c in lib.poll_params.await_args_list
                    ):
                        break
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        self.assertEqual(proxy.lift_type, LiftType.AHL)
        self.assertTrue(
            any(
                c.kwargs.get("force_read_all")
                for c in lib.poll_params.await_args_list
            ),
            "polling loop did not do a full read after late identification",
        )


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


class TestWriteParam(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy.write_param()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.mock_handler = MagicMock()
        self.mock_lib = MagicMock()
        self.proxy._handler = self.mock_handler
        self.proxy._lib = self.mock_lib
        self.proxy._lift_type = LiftType.AHL

    async def test_handler_none_returns_init_err(self):
        self.proxy._handler = None
        status, source, code = await self.proxy.write_param("5", "42")
        self.assertEqual(status, -1)
        self.assertEqual(source, "LiftProxy")
        self.assertEqual(code, "INIT_ERR")

    async def test_delegates_to_write_parameter(self):
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        await self.proxy.write_param("5", "42")
        self.mock_handler.write_parameter.assert_called_once_with(["5", "42"])

    async def test_success_passes_through(self):
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        status, source, code = await self.proxy.write_param("5", "42")
        self.assertEqual(status, 0)
        self.assertEqual(source, "ModBusHandler")
        self.assertEqual(code, "NO_ERR")

    async def test_success_updates_lib(self):
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        await self.proxy.write_param("5", "42")
        self.mock_lib.set_param.assert_called_once_with(5, 42)

    async def test_error_does_not_update_lib(self):
        self.mock_handler.write_parameter.return_value = (-1, "Rs232Handler", "FLOOR_LOCK_ERR")
        await self.proxy.write_param("5", "42")
        self.mock_lib.set_param.assert_not_called()

    async def test_error_passes_through(self):
        self.mock_handler.write_parameter.return_value = (-1, "Rs232Handler", "FLOOR_LOCK_ERR")
        status, source, code = await self.proxy.write_param("5", "42")
        self.assertEqual(status, -1)
        self.assertEqual(source, "Rs232Handler")
        self.assertEqual(code, "FLOOR_LOCK_ERR")

    async def test_success_hex_value_updates_lib(self):
        """Hex value strings must not crash the post-write cache update."""
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        status, _, code = await self.proxy.write_param("5", "0x10")
        self.assertEqual((status, code), (0, "NO_ERR"))
        self.mock_lib.set_param.assert_called_once_with(5, 16)

    async def test_success_leading_zero_value_updates_lib(self):
        """Leading-zero decimals are accepted by _pack_value — cache must match."""
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        await self.proxy.write_param("5", "042")
        self.mock_lib.set_param.assert_called_once_with(5, 42)

    async def test_1k_success_does_not_update_lib(self):
        """Rs232Handler already updates the 1k cache — no manual int() update."""
        self.proxy._lift_type = LiftType.ONE_K
        self.mock_handler.write_parameter.return_value = (0, "Rs232Handler", "NO_ERR")
        status, _, code = await self.proxy.write_param("5", "someText")
        self.assertEqual((status, code), (0, "NO_ERR"))
        self.mock_lib.set_param.assert_not_called()

    async def test_success_unsigned_hex_cached_as_int32(self):
        """Hex is a bit pattern: cache holds the signed decode reads report."""
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        await self.proxy.write_param("5", "0xFFFFFFFF")
        self.mock_lib.set_param.assert_called_once_with(5, -1)


class TestWriteReadParam(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy.write_read_param()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.mock_handler = MagicMock()
        self.mock_lib = MagicMock()
        self.proxy._handler = self.mock_handler
        self.proxy._lib = self.mock_lib
        self.proxy._lift_type = LiftType.AHL

    async def test_handler_none_returns_init_err(self):
        self.proxy._handler = None
        status, value, source, code = await self.proxy.write_read_param("5", "42")
        self.assertEqual((status, value, source, code),
                         (-1, None, "LiftProxy", "INIT_ERR"))

    async def test_write_failure_passes_through_no_read(self):
        self.mock_handler.write_parameter.return_value = (-1, "ModBusHandler", "LCM_ERR")
        status, value, source, code = await self.proxy.write_read_param("5", "42")
        self.assertEqual((status, value, source, code),
                         (-1, None, "ModBusHandler", "LCM_ERR"))
        self.mock_handler.read_parameter.assert_not_called()
        self.mock_lib.set_param.assert_not_called()

    async def test_success_returns_live_value_and_syncs_cache(self):
        """LCM clamps 7 to 5: only the verified live value reaches the cache."""
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        self.mock_handler.read_parameter.return_value = (5, "ModBusHandler", "NO_ERR")
        status, value, source, code = await self.proxy.write_read_param("1", "7")
        self.assertEqual((status, value, code), (0, 5, "NO_ERR"))
        self.mock_handler.read_parameter.assert_called_once_with(["1"])
        self.mock_lib.set_param.assert_called_once_with(1, 5)

    async def test_read_back_failure_leaves_cache_untouched(self):
        """A verify operation must never cache an unverified value."""
        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        self.mock_handler.read_parameter.return_value = (-1, "ModBusHandler", "COM_ERR")
        status, value, source, code = await self.proxy.write_read_param("5", "42")
        self.assertEqual((status, value, source, code),
                         (0, None, "ModBusHandler", "COM_ERR"))
        self.mock_lib.set_param.assert_not_called()

    async def test_1k_read_back_does_not_rewrite_cache(self):
        """1k read-back comes from the ThousandLib cache — no rewrite."""
        self.proxy._lift_type = LiftType.ONE_K
        self.mock_handler.write_parameter.return_value = (0, "Rs232Handler", "NO_ERR")
        self.mock_handler.read_parameter.return_value = ("text", "Rs232Handler", "NO_ERR")
        status, value, _, code = await self.proxy.write_read_param("5", "text")
        self.assertEqual((status, value, code), (0, "text", "NO_ERR"))
        self.mock_lib.set_param.assert_not_called()

    async def test_holds_lock_across_write_and_read(self):
        """Poll loop must not interleave between write and read-back."""
        held_during_read = []

        def read_side_effect(_args):
            held_during_read.append(self.proxy._handler_lock.locked())
            return (5, "ModBusHandler", "NO_ERR")

        self.mock_handler.write_parameter.return_value = (0, "ModBusHandler", "NO_ERR")
        self.mock_handler.read_parameter.side_effect = read_side_effect
        await self.proxy.write_read_param("1", "7")
        self.assertEqual(held_during_read, [True])


class TestGetParamPushList(unittest.TestCase):
    """Tests for LiftProxy._get_param_push_list()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.DEFAULT_ON_CHANGE_PARAMS = [5, 6, 7]
        self.proxy._lib.DEFAULT_DAILY_PARAMS = [18, 19]
        self.proxy._desired_handler = MagicMock()

    def test_returns_lib_defaults_when_no_twin_config(self):
        self.proxy._desired_handler.desired_properties = {}
        result = self.proxy._get_param_push_list("onChange")
        self.assertEqual(result, [5, 6, 7])

    def test_returns_daily_defaults_when_no_twin_config(self):
        self.proxy._desired_handler.desired_properties = {}
        result = self.proxy._get_param_push_list("daily")
        self.assertEqual(result, [18, 19])

    def test_returns_twin_list_when_present(self):
        self.proxy._desired_handler.desired_properties = {
            "paramPush": {"onChange": [10, 20, 30]}
        }
        result = self.proxy._get_param_push_list("onChange")
        self.assertEqual(result, [10, 20, 30])

    def test_returns_default_when_twin_list_empty(self):
        self.proxy._desired_handler.desired_properties = {
            "paramPush": {"onChange": []}
        }
        result = self.proxy._get_param_push_list("onChange")
        self.assertEqual(result, [5, 6, 7])

    def test_returns_default_when_desired_handler_none(self):
        self.proxy._desired_handler = None
        result = self.proxy._get_param_push_list("onChange")
        self.assertEqual(result, [5, 6, 7])

    def test_returns_default_on_invalid_type(self):
        self.proxy._desired_handler.desired_properties = {
            "paramPush": {"onChange": "not_a_list"}
        }
        result = self.proxy._get_param_push_list("onChange")
        self.assertEqual(result, [5, 6, 7])


class TestGetInterval(unittest.TestCase):
    """Tests for LiftProxy._get_interval()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._desired_handler = MagicMock()

    def test_returns_twin_value(self):
        self.proxy._desired_handler.desired_properties = {
            "intervals": {"liftAgentPolling": 10}
        }
        self.assertEqual(self.proxy._get_interval("liftAgentPolling", 5), 10)

    def test_returns_default_when_no_intervals(self):
        self.proxy._desired_handler.desired_properties = {}
        self.assertEqual(self.proxy._get_interval("liftAgentPolling", 5), 5)

    def test_returns_default_when_zero(self):
        self.proxy._desired_handler.desired_properties = {
            "intervals": {"liftAgentPolling": 0}
        }
        self.assertEqual(self.proxy._get_interval("liftAgentPolling", 5), 5)

    def test_returns_default_when_negative(self):
        self.proxy._desired_handler.desired_properties = {
            "intervals": {"liftAgentPolling": -1}
        }
        self.assertEqual(self.proxy._get_interval("liftAgentPolling", 5), 5)

    def test_returns_default_when_desired_handler_none(self):
        self.proxy._desired_handler = None
        self.assertEqual(self.proxy._get_interval("liftAgentPolling", 5), 5)


class TestSendParams(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy._send_params()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._event_sender = AsyncMock()

    async def test_sends_event_with_changed_params(self):
        self.proxy._lib.get_param.return_value = (42, "NO_ERR")
        await self.proxy._send_params([5, 6])
        self.proxy._event_sender.send_event.assert_called_once()
        payload = self.proxy._event_sender.send_event.call_args[0][0]
        self.assertEqual(payload["event"], "la.parameters.update")
        self.assertEqual(payload["source"], "la.parameter.polling")
        self.assertEqual(payload["error"], "")
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["data"][0]["value"], 42)
        self.assertEqual(payload["data"][0]["parameter"], 5)

    async def test_skips_params_with_errors(self):
        def get_param_side_effect(pid):
            if pid == 5:
                return (42, "NO_ERR")
            return (-1, "PARAM_NOT_SET")
        self.proxy._lib.get_param.side_effect = get_param_side_effect
        await self.proxy._send_params([5, 6])
        payload = self.proxy._event_sender.send_event.call_args[0][0]
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["parameter"], 5)

    async def test_no_send_when_all_params_error(self):
        self.proxy._lib.get_param.return_value = (-1, "PARAM_NOT_SET")
        await self.proxy._send_params([5, 6])
        self.proxy._event_sender.send_event.assert_not_called()


class TestPollingLoop(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy._polling_loop() — runs one cycle then stops."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.DEFAULT_ON_CHANGE_PARAMS = [5, 6, 7]
        self.proxy._lib.get_param.return_value = (42, "NO_ERR")
        self.proxy._handler = MagicMock()
        self.proxy._event_sender = AsyncMock()
        self.proxy._desired_handler = MagicMock()
        self.proxy._desired_handler.desired_properties = {}

    async def test_sends_changed_params_on_push_list(self):
        """One cycle: poll returns [5, 6, 99], push list is [5, 6, 7] → sends [5, 6]."""
        self.proxy._lib.poll_params = AsyncMock(return_value=[5, 6, 99])
        cycle_count = 0

        original_sleep = asyncio.sleep
        async def mock_sleep(seconds):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 1:
                raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.proxy._event_sender.send_event.assert_called_once()
        payload = self.proxy._event_sender.send_event.call_args[0][0]
        sent_params = [d["parameter"] for d in payload["data"]]
        self.assertEqual(sent_params, [5, 6])

    async def test_no_send_when_no_changes(self):
        """No changed params → no event sent."""
        self.proxy._lib.poll_params = AsyncMock(return_value=[])
        cycle_count = 0

        async def mock_sleep(seconds):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 1:
                raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.proxy._event_sender.send_event.assert_not_called()

    async def test_no_send_when_changes_not_on_push_list(self):
        """Changed params [99, 100] not on push list [5, 6, 7] → no send."""
        self.proxy._lib.poll_params = AsyncMock(return_value=[99, 100])
        cycle_count = 0

        async def mock_sleep(seconds):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 1:
                raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.proxy._event_sender.send_event.assert_not_called()


class TestDailyLoop(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy._daily_loop()."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.DEFAULT_DAILY_PARAMS = [18, 19]
        self.proxy._lib.get_param.return_value = (100, "NO_ERR")
        self.proxy._handler = MagicMock()
        self.proxy._event_sender = AsyncMock()
        self.proxy._desired_handler = MagicMock()
        self.proxy._desired_handler.desired_properties = {}

    async def test_sleeps_first_then_reads_and_sends(self):
        """Daily loop sleeps before first send (no immediate push on startup)."""
        call_order = []

        async def mock_sleep(seconds):
            call_order.append("sleep")
            raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._daily_loop()

        # Sleep called first, before any send
        self.assertEqual(call_order, ["sleep"])
        self.proxy._event_sender.send_event.assert_not_called()

    async def test_sends_all_daily_params_from_db(self):
        """After sleep, sends all daily params from db (no hardware read)."""
        cycle_count = 0

        async def mock_sleep(seconds):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._daily_loop()

        # Sends from db, not from handler
        self.proxy._handler.read_parameter.assert_not_called()
        self.proxy._event_sender.send_event.assert_called_once()
        payload = self.proxy._event_sender.send_event.call_args[0][0]
        sent_params = [d["parameter"] for d in payload["data"]]
        self.assertEqual(sent_params, [18, 19])


class TestPollParams(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy.poll_params() delegation."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._handler = MagicMock()
        # poll_params consumes the pending cold-start flag; clear it so
        # these tests see plain delegation (see TestPollParamsColdStartFlag)
        self.proxy._force_read_all = False

    async def test_delegates_to_lib(self):
        self.proxy._lib.poll_params = AsyncMock(return_value=[5, 6])
        result = await self.proxy.poll_params()
        self.assertEqual(result, [5, 6])
        self.proxy._lib.poll_params.assert_called_once_with(
            self.proxy._handler, force_read_all=False
        )

    async def test_returns_empty_when_lib_none(self):
        self.proxy._lib = None
        result = await self.proxy.poll_params()
        self.assertEqual(result, [])

    async def test_returns_empty_when_handler_none(self):
        self.proxy._handler = None
        result = await self.proxy.poll_params()
        self.assertEqual(result, [])


class TestPollParamsColdStartFlag(LiftProxyTestBase):
    """poll_params() owns the pending cold-start flag (AIOT-183)."""

    async def test_consumes_pending_flag(self):
        """The pending flag forces one full read, then is cleared."""
        proxy = LiftProxy()
        proxy._lib = MagicMock()
        proxy._lib.poll_params = AsyncMock(return_value=[])
        proxy._handler = MagicMock()

        await proxy.poll_params()
        await proxy.poll_params()

        first, second = proxy._lib.poll_params.await_args_list
        self.assertTrue(first.kwargs["force_read_all"])
        self.assertFalse(second.kwargs["force_read_all"])
        self.assertFalse(proxy._force_read_all)

    async def test_flag_stays_set_when_lib_raises(self):
        """A raising lib call must not consume the pending full read."""
        proxy = LiftProxy()
        proxy._lib = MagicMock()
        proxy._lib.poll_params = AsyncMock(side_effect=RuntimeError("bus"))
        proxy._handler = MagicMock()

        with self.assertRaises(RuntimeError):
            await proxy.poll_params()

        self.assertTrue(proxy._force_read_all)

    async def test_bind_rearm_survives_queued_poll(self):
        """A poll queued on the handler lock during _bind still reads all.

        Regression: the poll used to capture the flag before _bind
        re-armed it and then cleared the re-armed flag, losing the
        cold-start full read after late identification. _bind() now
        publishes the pair last, so the racing poll no-ops instead.
        """
        proxy = LiftProxy()
        await proxy._create_handlers()
        proxy._force_read_all = False       # cleared by an earlier cycle
        lib = self.MockAhlLib.return_value
        lib.poll_params = AsyncMock(return_value=[])
        poll_task = None

        async def to_thread_hook(func, *args):
            """Queue a poll while _bind holds the lock, mid-bind."""
            nonlocal poll_task
            if poll_task is None:
                poll_task = asyncio.create_task(proxy.poll_params())
                for _ in range(2):
                    await asyncio.sleep(0)  # let the poll reach the lock
            return func(*args)

        with patch("liftApi.lift_proxy.asyncio.to_thread", side_effect=to_thread_hook):
            await proxy._bind(LiftType.AHL)
        await poll_task

        # A poll racing the bind never consumes the re-armed flag: while
        # the pair is still unpublished it no-ops, and the first poll
        # after the bind reads every parameter.
        self.assertNotIn(
            False,
            [c.kwargs["force_read_all"] for c in lib.poll_params.await_args_list],
            "queued poll cleared the flag _bind re-armed",
        )
        await proxy.poll_params()
        self.assertTrue(lib.poll_params.await_args.kwargs["force_read_all"])


class TestLiftProxyIdleSupervisor(LiftProxyTestBase):
    """Tests for idle_supervisor wiring in LiftProxy."""

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_idle_supervisor_defaults_to_none(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create()
        self.assertIsNone(proxy._idle_supervisor)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_idle_supervisor_stored_when_passed(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        supervisor = MagicMock()
        proxy = await LiftProxy.create(idle_supervisor=supervisor)
        self.assertIs(proxy._idle_supervisor, supervisor)

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_polling_loop_invokes_supervisor_on_change(self, mock_identify):
        """One poll cycle with changes → supervisor.on_param_changes called once."""
        from liftApi.idle_supervisor import ParamChange
        mock_identify.return_value = LiftType.AHL
        supervisor = MagicMock()
        supervisor.on_param_changes = AsyncMock()
        proxy = await LiftProxy.create(idle_supervisor=supervisor)

        proxy.poll_params = AsyncMock(return_value=[22, 23])
        self.MockAhlLib.return_value.get_param.side_effect = [
            (100, "NO_ERR"),
            (200, "NO_ERR"),
        ]

        with patch(
            "liftApi.lift_proxy.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._polling_loop()

        supervisor.on_param_changes.assert_called_once_with([
            ParamChange(22, 100),
            ParamChange(23, 200),
        ])

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_polling_loop_skips_supervisor_when_no_changes(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        supervisor = MagicMock()
        supervisor.on_param_changes = AsyncMock()
        proxy = await LiftProxy.create(idle_supervisor=supervisor)

        proxy.poll_params = AsyncMock(return_value=[])

        with patch(
            "liftApi.lift_proxy.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._polling_loop()

        supervisor.on_param_changes.assert_not_called()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_polling_loop_works_without_supervisor(self, mock_identify):
        mock_identify.return_value = LiftType.AHL
        proxy = await LiftProxy.create(idle_supervisor=None)

        proxy.poll_params = AsyncMock(return_value=[22])
        self.MockAhlLib.return_value.get_param.return_value = (100, "NO_ERR")

        with patch(
            "liftApi.lift_proxy.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._polling_loop()

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_supervisor_exception_does_not_crash_polling_loop(self, mock_identify):
        """Supervisor raising must be caught; loop continues."""
        mock_identify.return_value = LiftType.AHL
        supervisor = MagicMock()
        supervisor.on_param_changes = AsyncMock(side_effect=RuntimeError("boom"))
        proxy = await LiftProxy.create(idle_supervisor=supervisor)

        proxy.poll_params = AsyncMock(return_value=[22])
        self.MockAhlLib.return_value.get_param.return_value = (100, "NO_ERR")

        with self.assertLogs("liftApi.lift_proxy", level="ERROR") as cm:
            with patch(
                "liftApi.lift_proxy.asyncio.sleep",
                new_callable=AsyncMock,
                side_effect=asyncio.CancelledError,
            ):
                with self.assertRaises(asyncio.CancelledError):
                    await proxy._polling_loop()

        self.assertTrue(
            any("IdleSupervisor failed" in line for line in cm.output),
            f"Expected 'IdleSupervisor failed' in logs, got: {cm.output}",
        )

    @patch("liftApi.lift_proxy.identify_lift", new_callable=AsyncMock)
    async def test_polling_loop_skips_ids_with_get_param_error(self, mock_identify):
        """Ids whose get_param returns non-NO_ERR are omitted from the ParamChange list."""
        from liftApi.idle_supervisor import ParamChange
        mock_identify.return_value = LiftType.AHL
        supervisor = MagicMock()
        supervisor.on_param_changes = AsyncMock()
        proxy = await LiftProxy.create(idle_supervisor=supervisor)

        proxy.poll_params = AsyncMock(return_value=[22, 23, 24])
        self.MockAhlLib.return_value.get_param.side_effect = [
            (100, "NO_ERR"),
            (None, "PARAM_NOT_SET"),
            (300, "NO_ERR"),
        ]

        with patch(
            "liftApi.lift_proxy.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await proxy._polling_loop()

        supervisor.on_param_changes.assert_called_once_with([
            ParamChange(22, 100),
            ParamChange(24, 300),
        ])


class TestProxyPollParamsForceRead(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy.poll_params force_read_all forwarding."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.poll_params = AsyncMock(return_value=[5])
        self.proxy._handler = MagicMock()

    async def test_forwards_force_read_all_true(self):
        await self.proxy.poll_params(force_read_all=True)
        self.proxy._lib.poll_params.assert_awaited_once_with(
            self.proxy._handler, force_read_all=True
        )

    async def test_returns_empty_when_handler_none(self):
        self.proxy._handler = None
        result = await self.proxy.poll_params(force_read_all=True)
        self.assertEqual(result, [])


class TestPollingLoopForceRead(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy._polling_loop force-read-all on first iteration."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.DEFAULT_ON_CHANGE_PARAMS = [5, 6]
        self.proxy._lib.get_param.return_value = (42, "NO_ERR")
        self.proxy._lib.poll_params = AsyncMock(return_value=[])
        self.proxy._handler = MagicMock()
        self.proxy._event_sender = AsyncMock()
        self.proxy._desired_handler = MagicMock()
        self.proxy._desired_handler.desired_properties = {}

    async def test_first_iter_passes_force_read_all_true(self):
        cycle_count = 0

        async def mock_sleep(_seconds):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.assertEqual(self.proxy._lib.poll_params.await_count, 2)
        self.proxy._lib.poll_params.assert_any_await(
            self.proxy._handler, force_read_all=True
        )
        self.proxy._lib.poll_params.assert_any_await(
            self.proxy._handler, force_read_all=False
        )
        first_call, second_call = self.proxy._lib.poll_params.await_args_list
        self.assertTrue(first_call.kwargs["force_read_all"])
        self.assertFalse(second_call.kwargs["force_read_all"])

    async def test_flag_cleared_after_first_iter(self):
        async def mock_sleep(_seconds):
            raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.assertFalse(self.proxy._force_read_all)

    async def test_flag_initially_true(self):
        fresh = LiftProxy()
        self.assertTrue(fresh._force_read_all)

    async def test_flag_stays_set_when_poll_raises(self):
        """If poll_params raises on the first cycle, the flag must remain True so the next iteration retries the full read."""
        self.proxy._lib.poll_params = AsyncMock(side_effect=RuntimeError("conn error"))

        async def mock_sleep(_seconds):
            raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy._polling_loop()

        self.assertTrue(self.proxy._force_read_all)


class TestRunReportsLiftType(unittest.IsolatedAsyncioTestCase):
    """Tests for LiftProxy.run() reporting gw.liftType once on startup."""

    def setUp(self):
        self.proxy = LiftProxy()
        self.proxy._lib = MagicMock()
        self.proxy._lib.DEFAULT_ON_CHANGE_PARAMS = []
        self.proxy._lib.DEFAULT_DAILY_PARAMS = []
        self.proxy._lib.poll_params = AsyncMock(return_value=[])
        self.proxy._handler = MagicMock()
        self.event_sender = AsyncMock()
        self.desired_handler = MagicMock()
        self.desired_handler.desired_properties = {}
        self.reporter = AsyncMock()

    async def _run_one_tick(self):
        """Start proxy.run, let it fire the report + one loop tick, then stop."""
        async def mock_sleep(_seconds):
            raise asyncio.CancelledError

        with patch("liftApi.lift_proxy.asyncio.sleep", side_effect=mock_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.proxy.run(self.event_sender, self.desired_handler, self.reporter)

    async def test_reports_ahl(self):
        self.proxy._lift_type = LiftType.AHL
        await self._run_one_tick()
        self.reporter.report_property.assert_awaited_once_with("gw.liftType", "AHL")

    async def test_reports_one_k(self):
        self.proxy._lift_type = LiftType.ONE_K
        await self._run_one_tick()
        self.reporter.report_property.assert_awaited_once_with("gw.liftType", "1k")

    async def test_reports_unknown_at_start(self):
        """An unidentified lift now reports 'unknown' instead of skipping (AIOT-183 US2)."""
        self.proxy._lift_type = LiftType.UNKNOWN
        await self._run_one_tick()
        self.reporter.report_property.assert_awaited_once_with("gw.liftType", "unknown")

    async def test_run_stores_reporter(self):
        """run() keeps a reference to the reporter for later use by _on_identified()."""
        self.proxy._lift_type = LiftType.AHL
        await self._run_one_tick()
        self.assertIs(self.proxy._reporter, self.reporter)

    async def test_identified_at_start_reports_once_no_reidentify(self):
        """An already-identified startup reports exactly once and never probes."""
        self.proxy._lift_type = LiftType.AHL
        with patch(
            "liftApi.lift_proxy.identify_lift", new_callable=AsyncMock
        ) as mock_identify:
            await self._run_one_tick()
        self.reporter.report_property.assert_awaited_once_with("gw.liftType", "AHL")
        mock_identify.assert_not_awaited()

    async def test_second_report_after_late_identification(self):
        """After background identification, _on_identified reports the real type."""
        self.proxy._lift_type = LiftType.UNKNOWN
        await self._run_one_tick()
        self.reporter.report_property.assert_awaited_once_with("gw.liftType", "unknown")

        self.proxy._lift_type = LiftType.AHL
        await self.proxy._on_identified()

        self.assertEqual(self.reporter.report_property.await_count, 2)
        self.reporter.report_property.assert_awaited_with("gw.liftType", "AHL")

    async def test_on_identified_reporter_failure_does_not_undo_bind(self):
        """A reporter that raises during late-report is logged, never raised, bind stands."""
        self.proxy._lift_type = LiftType.AHL
        self.proxy._reporter = self.reporter
        self.reporter.report_property = AsyncMock(side_effect=RuntimeError("twin unavailable"))

        with self.assertLogs("liftApi.lift_proxy", level="ERROR"):
            await self.proxy._on_identified()  # must not raise

        self.assertEqual(self.proxy.lift_type, LiftType.AHL)


class TestSurfacesAfterLateIdentification(unittest.IsolatedAsyncioTestCase):
    """Tests for AIOT-183 US3: event_sender.lift_type follows late identification."""

    async def test_event_sender_lift_type_updated_on_late_identification(self):
        """_on_identified assigns the LiftType enum (not .value) to event_sender."""
        proxy = LiftProxy()
        proxy._lift_type = LiftType.ONE_K
        proxy._event_sender = MagicMock()
        proxy._event_sender.lift_type = LiftType.UNKNOWN
        proxy._reporter = AsyncMock()

        await proxy._on_identified()

        self.assertEqual(proxy._event_sender.lift_type, LiftType.ONE_K)
        self.assertIsInstance(proxy._event_sender.lift_type, LiftType)

    async def test_on_identified_without_event_sender_does_not_raise(self):
        """_reidentify_loop can run without run() ever being called (no event_sender)."""
        proxy = LiftProxy()
        proxy._lift_type = LiftType.AHL
        proxy._event_sender = None
        proxy._reporter = None

        await proxy._on_identified()  # must not raise


class TestReadParamLive(LiftProxyTestBase):
    """Tests for LiftProxy.read_param_live()."""

    async def test_returns_init_err_without_handler(self):
        proxy = LiftProxy()
        value, source, code = await proxy.read_param_live(96)
        self.assertIsNone(value)
        self.assertEqual(source, "LiftProxy")
        self.assertEqual(code, "INIT_ERR")

    async def test_delegates_to_handler_read_parameter(self):
        proxy = LiftProxy()
        proxy._handler = MagicMock()
        proxy._handler.read_parameter.return_value = ("123456", "ModBusHandler", "NO_ERR")
        value, source, code = await proxy.read_param_live(96)
        proxy._handler.read_parameter.assert_called_once_with(["96"])
        self.assertEqual((value, source, code), ("123456", "ModBusHandler", "NO_ERR"))


class TestReadArNumber(LiftProxyTestBase):
    """Tests for LiftProxy.read_ar_number()."""

    async def test_ahl_reads_param_96_live(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.AHL
        proxy._handler = MagicMock()
        proxy._handler.read_parameter.return_value = ("998877", "ModBusHandler", "NO_ERR")
        value, source, code = await proxy.read_ar_number()
        proxy._handler.read_parameter.assert_called_once_with(["96"])
        self.assertEqual((value, code), ("998877", "NO_ERR"))

    async def test_1k_reads_liftref1_generic_text(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.ONE_K
        proxy._handler = MagicMock()
        proxy._handler.get_generic_text.return_value = (["AR111222"], "Rs232Handler", "NO_ERR")
        value, source, code = await proxy.read_ar_number()
        proxy._handler.get_generic_text.assert_called_once_with("liftRef1")
        self.assertEqual((value, source, code), ("AR111222", "Rs232Handler", "NO_ERR"))

    async def test_unknown_returns_init_err(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.UNKNOWN
        value, source, code = await proxy.read_ar_number()
        self.assertEqual((value, source, code), (None, "LiftProxy", "INIT_ERR"))


class TestWriteArNumber(LiftProxyTestBase):
    """Tests for LiftProxy.write_ar_number()."""

    async def test_ahl_rejects_read_only(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.AHL
        value, source, code = await proxy.write_ar_number("998877")
        self.assertEqual((value, source, code), (None, "LiftProxy", "PARAM_READ_ONLY"))

    async def test_1k_writes_liftref1(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.ONE_K
        proxy._handler = MagicMock()
        proxy._handler.write_generic_text.return_value = ("AR563412", "Rs232Handler", "NO_ERR")
        value, source, code = await proxy.write_ar_number("AR563412")
        proxy._handler.write_generic_text.assert_called_once_with(["liftRef1", "AR563412"])
        self.assertEqual((value, source, code), ("AR563412", "Rs232Handler", "NO_ERR"))

    async def test_unknown_returns_init_err(self):
        proxy = LiftProxy()
        proxy._lift_type = LiftType.UNKNOWN
        value, source, code = await proxy.write_ar_number("x")
        self.assertEqual((value, source, code), (None, "LiftProxy", "INIT_ERR"))


class TestPushParamEvent(LiftProxyTestBase):
    """Tests for DDM-write telemetry via push_param_event()."""

    async def test_sends_event_with_ddm_source(self):
        proxy = LiftProxy()
        proxy._lib = MagicMock()
        # get_param_value path: lib.get_param returns (value, code_name)
        proxy._lib.get_param.return_value = (7, "NO_ERR")
        proxy._event_sender = MagicMock()
        proxy._event_sender.send_event = AsyncMock()

        await proxy.push_param_event([1])

        proxy._event_sender.send_event.assert_awaited_once()
        payload = proxy._event_sender.send_event.await_args[0][0]
        self.assertEqual(payload["source"], "la.parameter.ddm")
        self.assertEqual(payload["event"], "la.parameters.update")
        self.assertEqual(payload["data"][0]["parameter"], 1)
        self.assertEqual(payload["data"][0]["value"], 7)

    async def test_no_send_when_event_sender_missing(self):
        proxy = LiftProxy()
        proxy._lib = MagicMock()
        proxy._event_sender = None
        # Should not raise
        await proxy.push_param_event([1])


if __name__ == "__main__":
    unittest.main()
