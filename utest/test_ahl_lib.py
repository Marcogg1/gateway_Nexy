#!/usr/bin/env python3
import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'src'))
sys.path.append(p)

from lib.ahl_lib import AhlLib, AhlParam
from lib.ahl_lib import (
    AhlParamSystem, AhlParamSettings, AhlParamInformation,
    AhlParamConfiguration, AhlParamLighting, AhlParamPower,
    AhlParamAlarms, AhlParamHardware, AhlParamSoftware,
    AhlParamNetwork, AhlParamAlarmDetails,
)
from lib.error_signals import MbCode


class TestAhlLib(unittest.TestCase):
    def setUp(self):
        self.ahl = AhlLib()

    def tearDown(self):
        pass

    # --- Database init ---

    def test_database_all_params_are_ahl_param(self):
        """All database entries are AhlParam instances."""
        for pid, param in self.ahl.database.items():
            assert isinstance(param, AhlParam), f"Param {pid} is not AhlParam"

    def test_database_param_id_matches_key(self):
        """Each param's param_id matches its database key."""
        for pid, param in self.ahl.database.items():
            assert param.param_id == pid, f"Key {pid} != param_id {param.param_id}"

    def test_database_all_values_initially_none(self):
        """All values are None before any set_param calls."""
        for pid, param in self.ahl.database.items():
            assert param.value is None, f"Param {pid} has initial value {param.value}"

    # --- get_param ---

    def test_get_param_valid(self):
        """Set a value, read it back, get NO_ERR."""
        self.ahl.database[0].value = 42
        val, err = self.ahl.get_param(0)
        assert val == 42
        assert err == MbCode.NO_ERR.name

    def test_get_param_not_in_db(self):
        """Nonexistent param_id returns PARAM_NOT_IN_DB."""
        val, err = self.ahl.get_param(99999)
        assert val == -1
        assert err == MbCode.PARAM_NOT_IN_DB.name

    def test_get_param_not_set(self):
        """Unread param returns PARAM_NOT_SET."""
        val, err = self.ahl.get_param(0)
        assert val == -1
        assert err == MbCode.PARAM_NOT_SET.name

    def test_get_param_value_zero(self):
        """Value 0 is returned correctly, not confused with not-set."""
        self.ahl.set_param(8, 0)
        val, err = self.ahl.get_param(8)
        assert val == 0
        assert err == MbCode.NO_ERR.name

    def test_get_param_value_negative(self):
        """Negative value is returned correctly, even -1."""
        self.ahl.set_param(8, -1)
        val, err = self.ahl.get_param(8)
        assert val == -1
        assert err == MbCode.NO_ERR.name

    def test_get_param_after_set_param(self):
        """Round-trip through public API: set_param then get_param."""
        self.ahl.set_param(8, 750)
        val, err = self.ahl.get_param(8)
        assert val == 750
        assert err == MbCode.NO_ERR.name

    # --- set_param ---

    def test_set_param_valid(self):
        """Set value, verify it's stored, returns changed list."""
        changed, err = self.ahl.set_param(8, 500)
        assert changed == [8]
        assert err == MbCode.NO_ERR.name
        assert self.ahl.database[8].value == 500

    def test_set_param_unchanged(self):
        """Set same value twice, second returns empty list."""
        self.ahl.set_param(8, 500)
        changed, err = self.ahl.set_param(8, 500)
        assert changed == []
        assert err == MbCode.NO_ERR.name

    def test_set_param_not_in_db(self):
        """Invalid param_id returns PARAM_NOT_IN_DB."""
        changed, err = self.ahl.set_param(99999, 100)
        assert changed == []
        assert err == MbCode.PARAM_NOT_IN_DB.name

    def test_set_param_overwrites_previous(self):
        """Setting a different value overwrites and reports changed."""
        self.ahl.set_param(8, 500)
        changed, err = self.ahl.set_param(8, 999)
        assert changed == [8]
        assert err == MbCode.NO_ERR.name
        assert self.ahl.database[8].value == 999

    def test_set_param_value_zero(self):
        """Setting value 0 stores it and counts as a change from None."""
        changed, err = self.ahl.set_param(8, 0)
        assert changed == [8]
        assert err == MbCode.NO_ERR.name
        assert self.ahl.database[8].value == 0

    # --- available_params ---

    def test_available_params(self):
        """Returns all param IDs."""
        params = self.ahl.available_params()
        assert 0 in params
        assert 381 in params

    # --- get_writable_params / get_readable_params ---

    def test_get_writable_params(self):
        """Returns only RW params and includes all of them."""
        writable = self.ahl.get_writable_params()
        for pid in writable:
            assert self.ahl.database[pid].access == 'RW', f"Param {pid} is not RW"
        # Verify we got all RW params, not just some
        expected_count = sum(1 for p in self.ahl.database.values() if p.access == 'RW')
        assert len(writable) == expected_count
        # Spot check: param 8 (DOOR_DWELL_TIME) is RW
        assert 8 in writable

    def test_get_readable_params_includes_rw(self):
        """Readable list includes both R and RW params."""
        readable = set(self.ahl.get_readable_params())
        # Param 0 is R, param 8 is RW - both should be in readable
        assert 0 in readable
        assert 8 in readable

    def test_writable_is_subset_of_readable(self):
        """All writable params are also readable."""
        writable = set(self.ahl.get_writable_params())
        readable = set(self.ahl.get_readable_params())
        assert writable.issubset(readable)

    # --- Enum consistency ---

    def test_system_enum_values(self):
        """Spot-check AhlParamSystem enum values match expected param IDs."""
        assert AhlParamSystem.PARAM_LIFT_INTERFACE_USED.value == 0
        assert AhlParamSystem.PARAM_POLLING.value == 2
        assert AhlParamSystem.PARAM_GATEWAY_STATUS.value == 3
        assert AhlParamSystem.PARAM_RESET_PARAMETERS.value == 98

    def test_settings_enum_values(self):
        """Spot-check AhlParamSettings enum values."""
        assert AhlParamSettings.PARAM_DOOR_DWELL_TIME.value == 8
        assert AhlParamSettings.PARAM_LUBRICATION_TIME.value == 32
        assert AhlParamSettings.PARAM_CUSTOMER_ID.value == 354

    def test_alarm_details_enum_range(self):
        """All AhlParamAlarmDetails values are in range 141-328."""
        for member in AhlParamAlarmDetails:
            assert 141 <= member.value <= 328, f"{member.name} = {member.value} out of range"

    def test_hardware_enum_values(self):
        """Spot-check AhlParamHardware enum values."""
        assert AhlParamHardware.PARAM_LCM_HARDWARE_VERSION.value == 67
        assert AhlParamHardware.PARAM_LMM_SERIAL_NUMBER.value == 122

    def test_network_enum_values(self):
        """Spot-check AhlParamNetwork enum values."""
        assert AhlParamNetwork.PARAM_NUM_OF_DCMS.value == 27
        assert AhlParamNetwork.PARAM_REGISTERED_UNITS.value == 112

    # --- MbCode error enum ---

    def test_mb_code_enum(self):
        """Verify error codes exist and have correct values."""
        assert MbCode.SOURCE.value == 'ModBusHandler'
        assert MbCode.NO_ERR.value == 0
        assert MbCode.PARAM_NOT_IN_DB.value == 25
        assert MbCode.PARAM_NOT_SET.value == 26

    # --- Interface consistency with ThousandLib ---

    def test_error_codes_attribute(self):
        """error_codes attribute exposes the MbCode enum."""
        assert self.ahl.error_codes is MbCode
        assert self.ahl.error_codes.NO_ERR.name == 'NO_ERR'

    def test_param_enum_instance_attributes(self):
        """Param category enums accessible as instance attributes."""
        assert self.ahl.params_system is AhlParamSystem
        assert self.ahl.params_settings is AhlParamSettings
        assert self.ahl.params_information is AhlParamInformation
        assert self.ahl.params_configuration is AhlParamConfiguration
        assert self.ahl.params_lighting is AhlParamLighting
        assert self.ahl.params_power is AhlParamPower
        assert self.ahl.params_alarms is AhlParamAlarms
        assert self.ahl.params_hardware is AhlParamHardware
        assert self.ahl.params_software is AhlParamSoftware
        assert self.ahl.params_network is AhlParamNetwork
        assert self.ahl.params_alarm_details is AhlParamAlarmDetails

    def test_all_enum_categories_map_to_database(self):
        """Every member of every category enum exists in the database."""
        categories = [
            self.ahl.params_system, self.ahl.params_settings,
            self.ahl.params_information, self.ahl.params_configuration,
            self.ahl.params_lighting, self.ahl.params_power,
            self.ahl.params_alarms, self.ahl.params_hardware,
            self.ahl.params_software, self.ahl.params_network,
            self.ahl.params_alarm_details,
        ]
        for category in categories:
            for member in category:
                assert member.value in self.ahl.database, \
                    f"{category.__name__}.{member.name} ({member.value}) not in database"

    # --- Param access checks ---

    def test_read_only_param_not_writable(self):
        """Param 0 (LIFT_INTERFACE_USED) is R, not in writable list."""
        writable = self.ahl.get_writable_params()
        assert 0 not in writable

    def test_rw_param_is_writable(self):
        """Param 5 (PLATFORM_LIGHT_ON_TIME) is RW."""
        writable = self.ahl.get_writable_params()
        assert 5 in writable


class TestDecodeChangeFlags(unittest.TestCase):
    """Tests for AhlLib.decode_change_flags() with old polling table."""

    def setUp(self):
        self.ahl = AhlLib()
        self.ahl.set_polling_table(new_table=False)

    def test_bit0_returns_params_excluding_param2(self):
        """Bit 0 maps to params 0-15, excluding param 2 (PARAM_POLLING)."""
        result = self.ahl.decode_change_flags(0b1)
        self.assertEqual(result, [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])

    def test_bit1_returns_params_16_to_31(self):
        result = self.ahl.decode_change_flags(0b10)
        self.assertEqual(result, list(range(16, 32)))

    def test_bit5_returns_params_80_to_93(self):
        """Bit 5 has only 14 params (80-93), not 16."""
        result = self.ahl.decode_change_flags(0b100000)
        self.assertEqual(result, list(range(80, 94)))

    def test_bit8_returns_126_and_353_to_367(self):
        """Bit 8 has split range: param 126 then 353-367."""
        result = self.ahl.decode_change_flags(1 << 8)
        self.assertEqual(result, [126] + list(range(353, 368)))

    def test_bit9_returns_params_368_to_383(self):
        """Bits 9+ use formula: 224 + bit*16 to 224 + bit*16 + 15."""
        result = self.ahl.decode_change_flags(1 << 9)
        self.assertEqual(result, list(range(368, 384)))

    def test_bit30_returns_params_704_to_719(self):
        result = self.ahl.decode_change_flags(1 << 30)
        self.assertEqual(result, list(range(704, 720)))

    def test_zero_bitmask_returns_empty(self):
        result = self.ahl.decode_change_flags(0)
        self.assertEqual(result, [])

    def test_multiple_bits_combines_params(self):
        """Bits 0 and 1 set returns both ranges."""
        result = self.ahl.decode_change_flags(0b11)
        expected = [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] + list(range(16, 32))
        self.assertEqual(result, expected)

    def test_all_bits_set_returns_all_params(self):
        """All 31 bits set returns all parameter ranges."""
        result = self.ahl.decode_change_flags(0x7FFFFFFF)
        self.assertIn(0, result)
        self.assertNotIn(2, result)
        self.assertIn(719, result)


class TestDecodeChangeFlagsNewTable(unittest.TestCase):
    """Tests for AhlLib.decode_change_flags() with new polling table."""

    def setUp(self):
        self.ahl = AhlLib()
        self.ahl.set_polling_table(new_table=True)

    def test_bit0_same_as_old_table(self):
        result = self.ahl.decode_change_flags(0b1)
        self.assertEqual(result, [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])

    def test_bit8_returns_126_to_129_and_353_to_364(self):
        """New table bit 8: params 126-129 + 353-364."""
        result = self.ahl.decode_change_flags(1 << 8)
        self.assertEqual(result, [126, 127, 128, 129] + list(range(353, 365)))

    def test_bit9_returns_params_130_to_145(self):
        """Bits 9-20 use formula: -14 + bit*16 to -14 + bit*16 + 15."""
        result = self.ahl.decode_change_flags(1 << 9)
        self.assertEqual(result, list(range(130, 146)))

    def test_bit20_returns_params_306_to_321(self):
        result = self.ahl.decode_change_flags(1 << 20)
        self.assertEqual(result, list(range(306, 322)))

    def test_bit21_returns_non_contiguous_params(self):
        """Bit 21: 322-333, 335-336, 338-339 (missing 334, 337)."""
        result = self.ahl.decode_change_flags(1 << 21)
        expected = list(range(322, 334)) + [335, 336, 338, 339]
        self.assertEqual(result, expected)

    def test_bit22_returns_non_contiguous_params(self):
        """Bit 22: 340, 344-345, 347-352, 365-371."""
        result = self.ahl.decode_change_flags(1 << 22)
        expected = [340, 344, 345] + list(range(347, 353)) + list(range(365, 372))
        self.assertEqual(result, expected)

    def test_bit23_returns_params_372_to_387(self):
        """Bits 23-30 use formula: 4 + bit*16 to 4 + bit*16 + 15."""
        result = self.ahl.decode_change_flags(1 << 23)
        self.assertEqual(result, list(range(372, 388)))

    def test_bit30_returns_params_484_to_499(self):
        result = self.ahl.decode_change_flags(1 << 30)
        self.assertEqual(result, list(range(484, 500)))

    def test_zero_bitmask_returns_empty(self):
        result = self.ahl.decode_change_flags(0)
        self.assertEqual(result, [])


class TestAhlDefaultParamPush(unittest.TestCase):
    """Tests for AHL default param push lists."""

    def test_default_on_change_is_list_of_ints(self):
        self.assertIsInstance(AhlLib.DEFAULT_ON_CHANGE_PARAMS, list)
        for p in AhlLib.DEFAULT_ON_CHANGE_PARAMS:
            self.assertIsInstance(p, int)

    def test_default_daily_is_list_of_ints(self):
        self.assertIsInstance(AhlLib.DEFAULT_DAILY_PARAMS, list)
        for p in AhlLib.DEFAULT_DAILY_PARAMS:
            self.assertIsInstance(p, int)

    def test_default_daily_count(self):
        self.assertEqual(len(AhlLib.DEFAULT_DAILY_PARAMS), 13)

    def test_no_overlap_between_on_change_and_daily(self):
        overlap = set(AhlLib.DEFAULT_ON_CHANGE_PARAMS) & set(AhlLib.DEFAULT_DAILY_PARAMS)
        self.assertEqual(overlap, set(), f"Overlap: {overlap}")


def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


class TestAhlPollParams(unittest.TestCase):
    """Tests for AhlLib.poll_params() — unified polling interface."""

    def setUp(self):
        self.ahl = AhlLib()
        self.handler = MagicMock()

    @async_test
    async def test_zero_bitmask_returns_empty(self):
        """No changed bits means no params to read."""
        self.handler.read_parameter.return_value = (0, "ModBusHandler", MbCode.NO_ERR.name)
        result = await self.ahl.poll_params(self.handler)
        self.assertEqual(result, [])
        self.handler.read_parameter.assert_called_once_with(["2"])

    @async_test
    async def test_bitmask_read_failure_returns_empty(self):
        """If reading param 2 fails, return empty list."""
        self.handler.read_parameter.return_value = (-1, "ModBusHandler", MbCode.COM_ERR.name)
        result = await self.ahl.poll_params(self.handler)
        self.assertEqual(result, [])

    @async_test
    async def test_changed_params_are_read_and_updated(self):
        """Bit 0 set → reads params in bit 0, returns those that changed."""
        # Bit 0 params: [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        # First call: read param 2 (bitmask), subsequent calls: read individual params
        call_count = 0

        def fake_read(args):
            nonlocal call_count
            call_count += 1
            if args == ["2"]:
                return (1, "ModBusHandler", MbCode.NO_ERR.name)  # bit 0
            # Return a value for each param read
            return (42, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        result = await self.ahl.poll_params(self.handler)
        # All params in bit 0 should be changed (from None to 42)
        self.assertEqual(result, [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])

    @async_test
    async def test_unchanged_values_not_in_result(self):
        """Params already at the same value are not reported as changed."""
        # Pre-set param 0 to 42
        self.ahl.set_param(0, 42)

        def fake_read(args):
            if args == ["2"]:
                return (1, "ModBusHandler", MbCode.NO_ERR.name)  # bit 0
            return (42, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        result = await self.ahl.poll_params(self.handler)
        # Param 0 was already 42, so not changed
        self.assertNotIn(0, result)
        # Others should still be changed (from None to 42)
        self.assertIn(1, result)

    @async_test
    async def test_read_failure_for_individual_param_skipped(self):
        """If reading an individual param fails, skip it."""
        call_count = 0

        def fake_read(args):
            nonlocal call_count
            call_count += 1
            if args == ["2"]:
                return (1, "ModBusHandler", MbCode.NO_ERR.name)  # bit 0
            if args == ["0"]:
                return (-1, "ModBusHandler", MbCode.COM_ERR.name)
            return (99, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        result = await self.ahl.poll_params(self.handler)
        self.assertNotIn(0, result)
        self.assertIn(1, result)

    @async_test
    async def test_force_read_all_acks_bitmask_first(self):
        """force_read_all=True reads param 2 FIRST (ack/clear LCM flags), discards value."""
        reads: list[str] = []

        def fake_read(args):
            reads.append(args[0])
            if args == ["2"]:
                # Power-on state: LCM reports all groups dirty. Value must be ignored.
                return (0x7FFFFFFF, "ModBusHandler", MbCode.NO_ERR.name)
            return (7, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        result = await self.ahl.poll_params(self.handler, force_read_all=True)
        self.assertEqual(reads[0], "2")
        self.assertEqual(reads.count("2"), 1)
        self.assertIn(0, result)
        self.assertIn(15, result)

    @async_test
    async def test_force_read_all_survives_ack_failure(self):
        """A failed param-2 ack read must not abort the forced full sweep."""
        def fake_read(args):
            if args == ["2"]:
                return (-1, "ModBusHandler", MbCode.COM_ERR.name)
            return (7, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        result = await self.ahl.poll_params(self.handler, force_read_all=True)
        self.assertIn(0, result)
        self.assertIn(15, result)

    @async_test
    async def test_force_read_all_reads_every_group_old_table(self):
        """Old table covers bits 0-31 → every param id in those groups gets read."""
        reads: list[str] = []

        def fake_read(args):
            reads.append(args[0])
            return (1, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        await self.ahl.poll_params(self.handler, force_read_all=True)
        self.assertEqual(reads[0], "2")
        for pid in (0, 16, 32, 48, 64, 80, 94, 110, 126):
            self.assertIn(str(pid), reads, f"Param {pid} not read")

    @async_test
    async def test_force_read_all_reads_every_group_new_table(self):
        """New polling table also reachable via force-read."""
        self.ahl.set_polling_table(True)
        reads: list[str] = []

        def fake_read(args):
            reads.append(args[0])
            return (1, "ModBusHandler", MbCode.NO_ERR.name)

        self.handler.read_parameter.side_effect = fake_read
        await self.ahl.poll_params(self.handler, force_read_all=True)
        self.assertEqual(reads[0], "2")
        for pid in (127, 128, 129, 340, 344, 345):
            self.assertIn(str(pid), reads, f"Param {pid} not read")

    @async_test
    async def test_default_call_still_reads_bitmask(self):
        """Regression: poll_params() without kwarg still reads param 2."""
        self.handler.read_parameter.return_value = (0, "ModBusHandler", MbCode.NO_ERR.name)
        await self.ahl.poll_params(self.handler)
        self.handler.read_parameter.assert_called_once_with(["2"])


if __name__ == '__main__':
    unittest.main()
