"""Unit tests for lift_identifier module."""

import os
import sys
import unittest
from unittest.mock import MagicMock

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from lib.error_signals import MbCode, Rs232Code
from liftApi.lift_identifier import LCM_SOFTWARE_VERSION_PARAM, LiftType, identify_lift


class TestIdentifyLift(unittest.IsolatedAsyncioTestCase):
    """Tests for the async identify_lift function."""

    def setUp(self):
        self.modbus = MagicMock()
        self.rs232 = MagicMock()

    # --- AHL detection ---

    async def test_ahl_detected_when_modbus_responds(self):
        self.modbus.read_parameter.return_value = ("3.2", "ModBusHandler", MbCode.NO_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.AHL)

    async def test_rs232_not_called_when_modbus_succeeds(self):
        self.modbus.read_parameter.return_value = ("3.2", "ModBusHandler", MbCode.NO_ERR.name)
        await identify_lift(self.modbus, self.rs232)
        self.rs232.get_ar_version.assert_not_called()

    # --- 1k detection ---

    async def test_1k_detected_when_modbus_fails_and_rs232_responds(self):
        self.modbus.read_parameter.return_value = (-1, "ModBusHandler", MbCode.LINK_ERR.name)
        self.rs232.get_ar_version.return_value = ("4.7", "Rs232Handler", Rs232Code.NO_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.ONE_K)

    async def test_1k_detected_when_modbus_raises_exception(self):
        self.modbus.read_parameter.side_effect = Exception("serial port gone")
        self.rs232.get_ar_version.return_value = ("4.7", "Rs232Handler", Rs232Code.NO_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.ONE_K)

    # --- UNKNOWN ---

    async def test_unknown_when_both_fail(self):
        self.modbus.read_parameter.return_value = (-1, "ModBusHandler", MbCode.LINK_ERR.name)
        self.rs232.get_ar_version.return_value = (-1, "Rs232Handler", Rs232Code.SERIAL_COM_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.UNKNOWN)

    async def test_unknown_when_both_raise_exceptions(self):
        self.modbus.read_parameter.side_effect = Exception("no modbus")
        self.rs232.get_ar_version.side_effect = Exception("no serial")
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.UNKNOWN)

    # --- None handlers ---

    async def test_1k_detected_when_modbus_handler_is_none(self):
        self.rs232.get_ar_version.return_value = ("4.7", "Rs232Handler", Rs232Code.NO_ERR.name)
        result = await identify_lift(None, self.rs232)
        self.assertEqual(result, LiftType.ONE_K)

    async def test_ahl_detected_when_rs232_handler_is_none(self):
        self.modbus.read_parameter.return_value = ("3.2", "ModBusHandler", MbCode.NO_ERR.name)
        result = await identify_lift(self.modbus, None)
        self.assertEqual(result, LiftType.AHL)

    async def test_unknown_when_both_handlers_are_none(self):
        result = await identify_lift(None, None)
        self.assertEqual(result, LiftType.UNKNOWN)

    # --- Probe order ---

    async def test_modbus_is_tried_first(self):
        self.modbus.read_parameter.return_value = ("3.2", "ModBusHandler", MbCode.NO_ERR.name)
        self.rs232.get_ar_version.return_value = ("4.7", "Rs232Handler", Rs232Code.NO_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.AHL)
        self.modbus.read_parameter.assert_called_once()
        self.rs232.get_ar_version.assert_not_called()

    # --- Correct probe parameters ---

    async def test_modbus_probed_with_lcm_software_version_param(self):
        self.modbus.read_parameter.return_value = ("3.2", "ModBusHandler", MbCode.NO_ERR.name)
        await identify_lift(self.modbus, self.rs232)
        self.modbus.read_parameter.assert_called_once_with([LCM_SOFTWARE_VERSION_PARAM])

    # --- Various Modbus error codes fall through to RS232 ---

    async def test_modbus_com_err_falls_through_to_rs232(self):
        self.modbus.read_parameter.return_value = (-1, "ModBusHandler", MbCode.COM_ERR.name)
        self.rs232.get_ar_version.return_value = ("4.7", "Rs232Handler", Rs232Code.NO_ERR.name)
        result = await identify_lift(self.modbus, self.rs232)
        self.assertEqual(result, LiftType.ONE_K)


class TestIdentifyLiftQuiet(unittest.IsolatedAsyncioTestCase):
    """quiet=True demotes the per-round probe failure lines (AIOT-183 FR-010)."""

    LOGGER = "liftApi.lift_identifier"

    def setUp(self):
        self.modbus = MagicMock()
        self.rs232 = MagicMock()
        self.modbus.read_parameter.return_value = (
            -1, "ModBusHandler", MbCode.LINK_ERR.name
        )
        self.rs232.get_ar_version.return_value = (
            -1, "Rs232Handler", Rs232Code.SERIAL_COM_ERR.name
        )

    async def test_quiet_emits_nothing_at_info(self):
        """A failed quiet round must not log at INFO or above."""
        with self.assertNoLogs(self.LOGGER, level="INFO"):
            result = await identify_lift(self.modbus, self.rs232, quiet=True)
        self.assertEqual(result, LiftType.UNKNOWN)

    async def test_quiet_still_logs_at_debug(self):
        """The three per-round failure lines survive at DEBUG."""
        with self.assertLogs(self.LOGGER, level="DEBUG") as captured:
            await identify_lift(self.modbus, self.rs232, quiet=True)
        self.assertEqual([r.levelname for r in captured.records], ["DEBUG"] * 3)

    async def test_loud_round_warns(self):
        """Without quiet the failed round keeps its WARNING and INFO lines."""
        with self.assertLogs(self.LOGGER, level="INFO") as captured:
            await identify_lift(self.modbus, self.rs232)
        levels = [r.levelname for r in captured.records]
        self.assertEqual(levels.count("WARNING"), 1)
        self.assertEqual(levels.count("INFO"), 2)

    async def test_quiet_keeps_success_line_at_info(self):
        """A successful identification is always announced at INFO."""
        self.modbus.read_parameter.return_value = (
            "3.2", "ModBusHandler", MbCode.NO_ERR.name
        )
        with self.assertLogs(self.LOGGER, level="INFO") as captured:
            result = await identify_lift(self.modbus, self.rs232, quiet=True)
        self.assertEqual(result, LiftType.AHL)
        self.assertIn("Lift identified as AHL", captured.records[0].getMessage())

    async def test_quiet_demotes_raising_probes_to_debug(self):
        """A probe that raises every round must not warn every round (FR-010)."""
        self.modbus.read_parameter.side_effect = RuntimeError("tty")
        self.rs232.get_ar_version.side_effect = RuntimeError("tty")
        with self.assertNoLogs(self.LOGGER, level="INFO"):
            result = await identify_lift(self.modbus, self.rs232, quiet=True)
        self.assertEqual(result, LiftType.UNKNOWN)

    async def test_loud_round_keeps_traceback_for_raising_probe(self):
        """Startup keeps the WARNING with traceback when a probe raises."""
        self.modbus.read_parameter.side_effect = RuntimeError("tty")
        with self.assertLogs(self.LOGGER, level="WARNING") as captured:
            await identify_lift(self.modbus, self.rs232)
        raised = [r for r in captured.records if r.exc_info]
        self.assertEqual(len(raised), 1)

    async def test_quiet_defaults_to_false(self):
        """Callers that pass nothing keep the loud startup logging."""
        with self.assertLogs(self.LOGGER, level="WARNING"):
            await identify_lift(self.modbus, self.rs232)


class TestLiftTypeEnum(unittest.TestCase):
    """Tests for the LiftType enum values."""

    def test_enum_values(self):
        self.assertEqual(LiftType.UNKNOWN.value, "unknown")
        self.assertEqual(LiftType.AHL.value, "AHL")
        self.assertEqual(LiftType.ONE_K.value, "1k")

    def test_enum_members_count(self):
        self.assertEqual(len(LiftType), 3)


if __name__ == "__main__":
    unittest.main()
