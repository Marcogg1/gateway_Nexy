#!/usr/bin/env python3
import sys
import os
import unittest

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


if __name__ == '__main__':
    unittest.main()
