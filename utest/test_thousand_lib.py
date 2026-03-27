#!/usr/bin/env python3
import sys
import os

from mock import MagicMock, patch
import unittest
import datetime as dt
from enum import Enum

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'src'))
sys.path.append(p)

from lib.thousand_lib import ThousandLib
from lib.thousand_lib import Signal


class TestThousandLib(unittest.TestCase):
    def setup_method(self, method):
        print("\nSetup: {}".format(method.__name__))
        self.tl = ThousandLib()

    def teardown_method(self, method):
        print("\nTest done: {}\n".format(method.__name__))

    def test_131_enum(self):
        assert self.tl.params_131.DOOR_IN_RUN.value == 68
        assert self.tl.params_131.LOCK_IN_RUN.value == 69
        assert self.tl.params_131.FLOOR_1_DUBBEL.value == 70
        assert self.tl.params_131.FLOOR_X_DUBBEL.value == 71
        assert self.tl.params_131.FLOOR_TOP_DUBBEL.value == 72
        assert self.tl.params_131.STEP_FAIL.value == 73
        assert self.tl.params_131.BATTERY_BAD.value == 74
        assert self.tl.params_131.BATTERY_MISSING.value == 75
        assert self.tl.params_131.EMERG_LIGHT.value == 76
        assert self.tl.params_131.OVERLOAD_24V.value == 77
        assert self.tl.params_131.DOOR_OPEN_1_MIN.value == 78
        assert self.tl.params_131.CHECK_CONTACTOR.value == 79
        assert self.tl.params_131.SHAFT_UNIT_GONE.value == 80
        assert self.tl.params_131.BATT_TEST_FAIL.value == 81
        assert self.tl.params_131.BATT_CHARGE_FAIL.value == 82
        assert self.tl.params_131.FIRE_BLOCK.value == 83
        assert self.tl.params_131.TEST_FRICTION.value == 84
        assert self.tl.params_131.VPLUG23_14V.value == 85
        assert self.tl.params_131.LOCK_FLOOR.value == 86
        assert self.tl.params_131.RUN_TIMEOUT.value == 87
        assert self.tl.params_131.OIL_SHORT_CIRCUIT.value == 88
        assert self.tl.params_131.BATT_FUSE.value == 89
        assert self.tl.params_131.PLATFORM_SAFETY.value == 90
        # Number of unique values
        assert len(self.tl.params_131) == 23

    def test_130_enum(self):
        # assert self.tl.params_130.BATTERY_STATE_130.value == 9
        assert self.tl.params_130.OIL_LEVEL_130.value == 10
        assert self.tl.params_130.SAFETY_130.value == 11
        assert self.tl.params_130.FLOOR_130.value == 12
        assert self.tl.params_130.LOAD_CURRENT_130.value == 13
        assert self.tl.params_130.NO_NODES_130.value == 14
        assert self.tl.params_130.FLOOR_1_FIRE_130.value == 15
        assert self.tl.params_130.FLOOR_1_CABIN_130.value == 16
        assert self.tl.params_130.FLOOR_1_SHAFT_130.value == 17
        assert self.tl.params_130.FLOOR_1_LOCK_130.value == 18
        assert self.tl.params_130.FLOOR_1_INPUT_130.value == 19
        assert self.tl.params_130.FLOOR_1_FLOOR_LOCK_130.value == 146
        assert self.tl.params_130.FLOOR_2_FIRE_130.value == 20
        assert self.tl.params_130.FLOOR_2_CABIN_130.value == 21
        assert self.tl.params_130.FLOOR_2_SHAFT_130.value == 22
        assert self.tl.params_130.FLOOR_2_LOCK_130.value == 23
        assert self.tl.params_130.FLOOR_2_INPUT_130.value == 24
        assert self.tl.params_130.FLOOR_2_FLOOR_LOCK_130.value == 147
        assert self.tl.params_130.FLOOR_3_FIRE_130.value == 25
        assert self.tl.params_130.FLOOR_3_CABIN_130.value == 26
        assert self.tl.params_130.FLOOR_3_SHAFT_130.value == 27
        assert self.tl.params_130.FLOOR_3_LOCK_130.value == 28
        assert self.tl.params_130.FLOOR_3_INPUT_130.value == 29
        assert self.tl.params_130.FLOOR_3_FLOOR_LOCK_130.value == 148
        assert self.tl.params_130.FLOOR_4_FIRE_130.value == 30
        assert self.tl.params_130.FLOOR_4_CABIN_130.value == 31
        assert self.tl.params_130.FLOOR_4_SHAFT_130.value == 32
        assert self.tl.params_130.FLOOR_4_LOCK_130.value == 33
        assert self.tl.params_130.FLOOR_4_INPUT_130.value == 34
        assert self.tl.params_130.FLOOR_4_FLOOR_LOCK_130.value == 149
        assert self.tl.params_130.FLOOR_5_FIRE_130.value == 35
        assert self.tl.params_130.FLOOR_5_CABIN_130.value == 36
        assert self.tl.params_130.FLOOR_5_SHAFT_130.value == 37
        assert self.tl.params_130.FLOOR_5_LOCK_130.value == 38
        assert self.tl.params_130.FLOOR_5_INPUT_130.value == 39
        assert self.tl.params_130.FLOOR_5_FLOOR_LOCK_130.value == 150
        assert self.tl.params_130.FLOOR_6_FIRE_130.value == 40
        assert self.tl.params_130.FLOOR_6_CABIN_130.value == 41
        assert self.tl.params_130.FLOOR_6_SHAFT_130.value == 42
        assert self.tl.params_130.FLOOR_6_LOCK_130.value == 43
        assert self.tl.params_130.FLOOR_6_INPUT_130.value == 44
        assert self.tl.params_130.FLOOR_6_FLOOR_LOCK_130.value == 151
        assert self.tl.params_130.HAS_PUMP_130.value == 45
        assert self.tl.params_130.POWER_IN_130.value == 46
        assert self.tl.params_130.DOOR_NOT_OPEN_130.value == 47
        assert self.tl.params_130.ALARM_ACTIVE_130.value == 48
        assert self.tl.params_130.LIFT_LOCKED_130.value == 49
        assert self.tl.params_130.DOOR_OPEN_1MIN_130.value == 50
        assert self.tl.params_130.CONTACTOR_STUCK_130.value == 51
        assert self.tl.params_130.BATT_MISSING_130.value == 52
        assert self.tl.params_130.BATT_CHANGE_130.value == 53
        assert self.tl.params_130.BATT_BAD_130.value == 54
        assert self.tl.params_130.BATT_CHARGER_ERR_130.value == 55
        assert self.tl.params_130.CABIN_LIFT_130.value == 56
        # assert self.tl.params_130.IMPULSE_130.value == 58
        assert self.tl.params_130.EMERG_FAIL_130.value == 58
        assert self.tl.params_130.LIFT_NEEDS_SERVICE_130.value == 59
        assert self.tl.params_130.OVER_CURRENT_130.value == 60
        assert self.tl.params_130.REDUCE_LIGHT_130.value == 61
        assert self.tl.params_130.RUN_TIME_130.value == 62
        assert self.tl.params_130.FIRE_130.value == 63
        assert self.tl.params_130.PLUG_23_130.value == 64
        assert self.tl.params_130.OVER_LOAD_130.value == 65
        assert self.tl.params_130.CHILD_LOCK_130.value == 145
        assert self.tl.params_130.BATTERY_TESTING_130.value == 153
        assert self.tl.params_130.BATTERY_TEST_SUSPENDED_130.value == 154

        # Number of unique values
        assert len(self.tl.params_130) == 64

    def test_2_enum(self):
        assert self.tl.params_2.FILE_DATE_2.value == 2
        assert self.tl.params_2.PROG_DATE_2.value == 3
        assert self.tl.params_2.PROG_NAME_2.value == 4
        assert self.tl.params_2.MAIN_VERSION_2.value == 5
        assert self.tl.params_2.SUB_VERSION_2.value == 6
        assert self.tl.params_2.OS_VERSION_2.value == 7
        assert self.tl.params_2.HW_VERSION_2.value == 8
        assert len(self.tl.params_2) == 7

    def test_133_enum(self):
        # assert self.tl.params_133.BATT_STATUS.value == -1
        # assert self.tl.params_133.BATT_PROGRESS.value == -1
        # assert self.tl.params_133.CHARGE_LOAD.value == -1
        # assert self.tl.params_133.TEST_MODE.value == -1
        assert self.tl.params_133.BATTERY_VOLTAGE.value == 179
        assert self.tl.params_133.BATTERY_CAPACITY.value == 180
        # assert self.tl.params_133.BATTERY_TIME.value == -1
        # assert self.tl.params_133.BATTERY_RESISTANCE.value == -1
        assert self.tl.params_133.BATTERY_CURRENT.value == 181
        # assert self.tl.params_133.NEXT_TIME_TO_TEST_BATTERY.value == -1

        # Number of unique values
        assert len(self.tl.params_133) == 3

    def test_134_enum(self):
        assert self.tl.params_134.CURRENT.value == 91
        # assert self.tl.params_134.LOAD.value == -1
        # assert self.tl.params_134.SAFE_OUT.value == -1
        # assert self.tl.params_134.SAFE_PLATFORM.value == -1
        # assert self.tl.params_134.SAFE_DOOR.value == -1
        # assert self.tl.params_134.SAFE_LOCK.value == -1
        # assert self.tl.params_134.POWER_IN.value == -1
        # assert self.tl.params_134.V_IN.value == -1
        # assert self.tl.params_134.V_OUT.value == -1
        # assert self.tl.params_134.RIPPLE.value == -1
        # assert self.tl.params_134.BATT_OUT.value == -1
        # assert self.tl.params_134.PLUG_23.value == -1
        # assert self.tl.params_134.RELAY_SENSE.value == -1
        # assert self.tl.params_134.TEMP.value == 94
        # assert self.tl.params_134.SYSTEM_UP_TIMER.value == -1
        assert self.tl.params_134.TOTAL_STARTS.value == 66
        assert self.tl.params_134.TOTAL_RUN_TIME.value == 67
        # assert self.tl.params_134.TRIP_START.value == -1
        # assert self.tl.params_134.TRIP_RUN_TIME.value == -1

        # Number of unique values
        assert len(self.tl.params_134) == 3

    def test_virtual_enum(self):
        assert self.tl.params_virtual.BATTERY_STATE_130.value == 9
        assert self.tl.params_virtual.IMPULSE_130.value == 57
        assert self.tl.params_virtual.TEMP_134.value == 92
        assert self.tl.params_virtual.FLOOR_LOCK.value == 152
        assert len(self.tl.params_virtual) == 4

    def test_get_ar_number_enum(self):
        assert self.tl.params_lift_ar.AR_NUMBER.value == 0
        assert len(self.tl.params_lift_ar) == 1

    def test_get_lift_type_enum(self):
        assert self.tl.params_lift_type.LIFT_TYPE.value == 1
        assert len(self.tl.params_lift_type) == 1

    def test_get_lift_name_enum(self):
        assert self.tl.params_lift_name.LIFT_NAME.value == 144
        assert len(self.tl.params_lift_name) == 1

    def test_get_version_enum(self):
        assert self.tl.params_version.ARGATE_MAIN_VERSION.value == 93
        assert self.tl.params_version.ARGATE_SUB_VERSION.value == 94
        assert self.tl.params_version.ARGATE_HW_VERSION.value == 95
        assert self.tl.params_version.ARGATE_OP_VERSION.value == 96
        assert self.tl.params_version.ARGATE_MIN_VERSION.value == 161
        assert self.tl.params_version.ARGATE_BETA_VERSION.value == 162
        assert self.tl.params_version.U19_HW_VERSION.value == 163
        assert self.tl.params_version.U19_OP_VERSION.value == 164
        assert self.tl.params_version.U19_MAIN_VERSION.value == 165
        assert self.tl.params_version.U19_SUB_VERSION.value == 166
        assert self.tl.params_version.U19_MIN_VERSION.value == 167
        assert self.tl.params_version.U19_BETA_VERSION.value == 168
        assert len(self.tl.params_version) == 12

    def test_get_readFile_param(self):
        assert self.tl.params_readFile_param.DOOR_TIME.value == 97
        assert self.tl.params_readFile_param.CABIN_LIGHT.value == 98
        assert self.tl.params_readFile_param.ALARM_TIME.value == 99
        assert self.tl.params_readFile_param.CLOSE_CALL_DELAY.value == 100
        assert self.tl.params_readFile_param.DOOR_OPEN_DELAY.value == 101
        assert self.tl.params_readFile_param.FIRE_FLOOR.value == 102
        assert self.tl.params_readFile_param.RETURN_FLOOR.value == 103
        assert self.tl.params_readFile_param.RETURN_TIME.value == 104
        assert self.tl.params_readFile_param.VALVE_INTENSITY.value == 105
        assert self.tl.params_readFile_param.IMPULSE_CABIN.value == 106
        assert self.tl.params_readFile_param.BEEP_PLATFORM.value == 107
        assert self.tl.params_readFile_param.BEEP_ARRIVAL.value == 108
        assert self.tl.params_readFile_param.BATT_TEST_USE_EMERGENCY.value == 109
        assert self.tl.params_readFile_param.DOOR_LOCK_TIME.value == 110
        assert self.tl.params_readFile_param.PUMP_INTENSITY.value == 111
        assert len(self.tl.params_readFile_param) == 15

    def test_get_readFile_intern(self):
        assert self.tl.params_readFile_intern.FREQ_CONTROL.value == 112
        assert self.tl.params_readFile_intern.IMPULSE_AVAILABLE.value == 113
        assert self.tl.params_readFile_intern.LOCK_INVERT.value == 114
        assert self.tl.params_readFile_intern.OIL_MODE.value == 115
        assert self.tl.params_readFile_intern.NODE_DIRECTION.value == 116
        assert self.tl.params_readFile_intern.BOTTLE_VOLUME.value == 117
        assert self.tl.params_readFile_intern.EMERGENCY_DELAY.value == 118
        assert self.tl.params_readFile_intern.B_LIFT.value == 119
        assert self.tl.params_readFile_intern.COMMON_LIGHT.value == 120
        assert self.tl.params_readFile_intern.AUTO_LOCK_MENU.value == 121
        assert self.tl.params_readFile_intern.BATT_CAPACITY.value == 122
        assert self.tl.params_readFile_intern.PUMP_CAPACITY.value == 123
        assert self.tl.params_readFile_intern.AR_BUS_EXT.value == 124
        assert self.tl.params_readFile_intern.EMERGENCY_LIGHT_TEST.value == 125
        assert len(self.tl.params_readFile_intern) == 14

    def test_get_readFile_node(self):
        assert self.tl.params_readFile_node.FLOOR_1_NODE.value == 126
        assert self.tl.params_readFile_node.FLOOR_2_NODE.value == 127
        assert self.tl.params_readFile_node.FLOOR_3_NODE.value == 128
        assert self.tl.params_readFile_node.FLOOR_4_NODE.value == 129
        assert self.tl.params_readFile_node.FLOOR_5_NODE.value == 130
        assert self.tl.params_readFile_node.FLOOR_6_NODE.value == 131
        assert len(self.tl.params_readFile_node) == 6

    def test_get_readFile_lock(self):
        assert self.tl.params_readFile_lock.FLOOR_1_LOCK.value == 132
        assert self.tl.params_readFile_lock.FLOOR_2_LOCK.value == 133
        assert self.tl.params_readFile_lock.FLOOR_3_LOCK.value == 134
        assert self.tl.params_readFile_lock.FLOOR_4_LOCK.value == 135
        assert self.tl.params_readFile_lock.FLOOR_5_LOCK.value == 136
        assert self.tl.params_readFile_lock.FLOOR_6_LOCK.value == 137
        assert len(self.tl.params_readFile_lock) == 6

    def test_get_readFile_door(self):
        assert self.tl.params_readFile_door.FLOOR_1_DOUBLE_DOOR.value == 138
        assert self.tl.params_readFile_door.FLOOR_2_DOUBLE_DOOR.value == 139
        assert self.tl.params_readFile_door.FLOOR_3_DOUBLE_DOOR.value == 140
        assert self.tl.params_readFile_door.FLOOR_4_DOUBLE_DOOR.value == 141
        assert self.tl.params_readFile_door.FLOOR_5_DOUBLE_DOOR.value == 142
        assert self.tl.params_readFile_door.FLOOR_6_DOUBLE_DOOR.value == 143
        assert len(self.tl.params_readFile_door) == 6

    def test_get_vfd_data(self):
        assert self.tl.params_vfdResult.VFD_MOTOR_CURRENT.value == 169
        assert self.tl.params_vfdResult.VFD_MOTOR_POWER.value == 170
        assert self.tl.params_vfdResult.VFD_LINE_MAINS_VOLTAGE.value == 171
        assert self.tl.params_vfdResult.VFD_DRIVE_THERMAL_STATE.value == 172
        assert len(self.tl.params_vfdResult) == 4

    def test_init_signal_class(self):
        # Test successful init of signal
        value = ""
        name = "TotalRuntime"
        bit_start = 0
        bit_size = 32
        byte_start = 36
        byte_size = 4
        signal_type = "uint"

        signal = Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

        assert signal.value == value
        assert signal.name == name
        assert signal.bit_start == bit_start
        assert signal.bit_size == bit_size
        assert signal.byte_start == byte_start
        assert signal.byte_size == byte_size
        assert signal.signal_type == signal_type

        # Assert that false data types raise an exception
        false_value_type = 1
        false_name_type = 1
        false_bit_start_type = "0"
        false_bit_size_type = "32"
        false_byte_start_type = "36"
        false_byte_size_type = "4"
        false_signal_type_type = 1

        with self.assertRaises(TypeError):
            Signal(false_value_type, name, bit_start, bit_size, byte_start, byte_size, type)
            Signal(value, false_name_type, bit_start, bit_size, byte_start, byte_size, type)
            Signal(value, name, false_bit_start_type, bit_size, byte_start, byte_size, type)
            Signal(value, name, bit_start, false_bit_size_type, byte_start, byte_size, type)
            Signal(value, name, bit_start, bit_size, false_byte_start_type, byte_size, type)
            Signal(value, name, bit_start, bit_size, byte_start, false_byte_size_type, type)
            Signal(value, name, bit_start, bit_size, byte_start, byte_size, false_signal_type_type)

    def test_init_signal_bit_start_bit_size(self):
        """
        Test init signal class with different values of bit_start and bit_size
        """
        # Assert that incorrect bit size + bit start raises a ValueError.
        value = ""
        name = "Test"
        bit_start = 0
        bit_size = 10
        byte_start = 0
        byte_size = 1
        signal_type = "byte"
        with self.assertRaises(ValueError):
            Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

            bit_start = 3
            bit_size = 8
            Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

            bit_start = 10
            bit_size = 1
            Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

        # Assert that bit_size + bit_start > 8 is ok for signals that are not of type byte.
        value = ""
        name = "Test"
        bit_start = 0
        bit_size = 32
        byte_size = 4
        signal_type = "uint"
        signal = Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

        assert signal.value == value
        assert signal.name == name
        assert signal.bit_start == bit_start
        assert signal.bit_size == bit_size
        assert signal.byte_start == byte_start
        assert signal.byte_size == byte_size
        assert signal.signal_type == signal_type

    @patch('lib.thousand_lib.Signal')
    def test_init_database(self, signal_mock):
        signal_mock.side_effect = TypeError
        with self.assertRaises(TypeError):
            ThousandLib()

        signal_mock.side_effect = ValueError
        with self.assertRaises(ValueError):
            ThousandLib()

    def test_unpack_as_epoch_time(self):
        """
        Test unpack_as_epoch_time. This function requires unpack_uint to work.
        """
        # Required to unpack functions.
        test_signal = Signal("", "TestSignal", 0, 32, 0, 4, 'time')
        response = []

        s_1970 = dt.datetime(1970, 1, 1, 0, 0, 0)
        s_2001 = dt.datetime(2001, 1, 1, 0, 0, 0)
        assert (s_2001 - s_1970).total_seconds() == 978307200

        s_1970_to_2001 = (s_2001 - s_1970).total_seconds()

        # Test values received from the lift. Signal is sent from the lift as uint32 (max value 2^32-1).
        received_seconds_list = [0, 100, pow(2, 32) - 1]

        for received_seconds in received_seconds_list:
            self.tl._ThousandLib__unpack_uint = MagicMock(return_value=received_seconds)
            val = self.tl._ThousandLib__unpack_as_epoch_time(test_signal, response)
            assert val == s_1970_to_2001 + received_seconds

    def test_validate_bytes(self):
        """
        Test validate bytes.
        """
        byte_start = 0
        byte_size = 4
        dummy_signal = Signal("", "Dummy", 0, 32, byte_start, byte_size, "uint")

        # Test different 4 byte long responses that contain invalid data
        bad_responses = [['a', '1', '2', '3'], ['1', '255', '123', 'a'], ['1', '2', 'Bad response', '3'],
                         ['256', '1', '2', '3'], ['1', '255', '123', '999'], ['1', '2', '-3', '3']]

        for bad_response in bad_responses:
            with self.assertRaises(ValueError):
                self.tl._ThousandLib__validate_bytes(dummy_signal, bad_response)

        # Test responses that are valid but too short
        bad_responses = [['3'], ['1', '255'], ['1', '2', '3']]

        for bad_response in bad_responses:
            with self.assertRaises(IndexError):
                self.tl._ThousandLib__validate_bytes(dummy_signal, bad_response)

    @patch('time.time')
    def test_unpack_wtime(self, time_patch):
        """
        Test unpack_wtime. This function requires unpack_uint to work.
        """
        test_signal = Signal("", "TestSignal", 0, 32, 0, 4, 'wtime')
        max_time = 60 * 60 * 24 * 7
        received_seconds = 0
        self.tl._ThousandLib__unpack_uint = MagicMock(return_value=received_seconds)
        unpacked_value = self.tl._ThousandLib__unpack_weekly_timer(test_signal, [])
        assert unpacked_value == received_seconds

        received_seconds = 10
        time_patch.return_value = 1000
        self.tl._ThousandLib__unpack_uint = MagicMock(return_value=received_seconds)
        unpacked_value = self.tl._ThousandLib__unpack_weekly_timer(test_signal, [])
        assert unpacked_value == time_patch.return_value - (max_time - received_seconds)

    def test_unpack_string(self):
        """
        Test valid strings to unpack
        """
        # Strings that should be unpacked as is
        data_as_string_list = ["Test", "TeSt", "T1E2S3T4", "AritcoI", "1234"]

        junk_before_wanted_data = "DataThatIsNotTheStringWeWant"
        byte_start = len(junk_before_wanted_data)
        bit_start = 0

        for data_as_string in data_as_string_list:
            byte_size = len(data_as_string)
            bit_size = byte_size * 8

            complete_response = junk_before_wanted_data + data_as_string

            # Reformat data to ASCII
            response_as_dec = [ord(c) for c in complete_response]

            signal = Signal("", "Test_signal", bit_start, bit_size, byte_start, byte_size, "string")

            unpacked = self.tl._ThousandLib__unpack_string(signal, response_as_dec)
            assert unpacked == data_as_string

    def test_unpack_string_unsupported_chars(self):
        """
        Test unpacking characters that are not supported.
        Unsupported characters should be removed from the unpacked string.
        """
        junk_before_wanted_data = "DataThatIsNotTheStringWeWant"
        byte_start = len(junk_before_wanted_data)
        bit_start = 0

        unsupported_chars = [" ", ","]
        assert self.tl.unsupported_chars == unsupported_chars

        for unsupported_char in unsupported_chars:
            # Replace whitespace with one of the unsupported characters
            data_as_string = "Aritco I Test 123 ".replace(" ", unsupported_char)

            byte_size = len(data_as_string)
            bit_size = byte_size * 8

            complete_response = junk_before_wanted_data + data_as_string

            # Reformat data to ASCII
            response_as_dec = [ord(c) for c in complete_response]

            signal = Signal("", "Test_signal", bit_start, bit_size, byte_start, byte_size, "string")

            unpacked = self.tl._ThousandLib__unpack_string(signal, response_as_dec)
            assert unpacked == "AritcoITest123"

    def test_unpack_string_null(self):
        """
        Test unpacking NULL. NULL is unsupported however handled separately from other unsupported chars.
        """
        # Aritco I NULL
        response = [65, 114, 105, 116, 99, 111, 32, 73, 32, 0]

        byte_size = len(response)
        byte_start = 0
        bit_start = 0
        bit_size = byte_size * 8

        signal = Signal("", "Test_signal", bit_start, bit_size, byte_start, byte_size, "string")

        unpacked = self.tl._ThousandLib__unpack_string(signal, response)
        assert unpacked == "AritcoI"

    def test_unpack_signal(self):
        """
        Test unpack signal.
        """
        byte_start = 0
        byte_size = 4
        dummy_signal = Signal("", "Dummy", 0, 32, byte_start, byte_size, "uint")

        # Test different 4 byte long responses that contain invalid data
        bad_responses = [['a', '1', '2', '3'], ['1', '255', '123', 'a'], ['1', '2', 'Bad response', '3'],
                         ['256', '1', '2', '3'], ['1', '255', '123', '999'], ['1', '2', '-3', '3'],
                         ['3'], ['1', '255'], ['1', '2', '3']]

        for bad_response in bad_responses:
            val, err_code = self.tl._ThousandLib__unpack_signal(dummy_signal, bad_response)
            assert val == "-1"
            assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

    def test_unpack_byte(self):
        """
        Test unpack_byte.
        """
        # Test successful init of signal
        value = ""
        name = "Test"
        bit_start = 0
        bit_size = 8
        byte_start = 0
        byte_size = 1
        signal_type = "byte"

        signal = Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)

        # Test different value of byte_start
        response = [1, 2, 4, 8, 16, 32, 64, 128]
        signal.bit_start = 0
        signal.bit_size = 8
        val = 1
        for i in range(0, 7):
            signal.byte_start = i
            unpacked = self.tl._ThousandLib__unpack_byte(signal, response)
            assert val == unpacked
            val *= 2

        # Test different value of bit_start
        response = [255]
        signal.bit_start = 0
        signal.bit_size = 1
        signal.byte_start = 0

        for i in range(0, 7):
            signal.bit_start = i
            unpacked = self.tl._ThousandLib__unpack_byte(signal, response)
            assert unpacked == 1

        # Test different value of bit_size
        response = [255]
        signal.bit_start = 0
        signal.bit_size = 0
        signal.byte_start = 0

        for i in range(1, 8):
            signal.bit_size = i
            unpacked = self.tl._ThousandLib__unpack_byte(signal, response)
            assert unpacked == pow(2, signal.bit_size) - 1

        # Test some combinations of bit_start and bit_size
        signal.bit_start = 4
        signal.bit_size = 4

        response = [128]
        unpacked = self.tl._ThousandLib__unpack_byte(signal, response)
        assert unpacked == 8

        response = [255]
        unpacked = self.tl._ThousandLib__unpack_byte(signal, response)
        assert unpacked == 15

    def test_unpack_uint(self):
        """
        Test unpack_uint.
        """
        # Test unpack uint8
        test_signal = Signal("", "TestSignal", 0, 8, 0, 1, 'uint')
        response = [128]
        unpacked_value = self.tl._ThousandLib__unpack_uint(test_signal, response)
        assert unpacked_value == 128

        # Test unpack uint16
        test_signal = Signal("", "TestSignal", 0, 16, 0, 2, 'uint')
        response = [1, 128]
        unpacked_value = self.tl._ThousandLib__unpack_uint(test_signal, response)
        assert unpacked_value == 32769

        # Test unpack uint32
        test_signal = Signal("", "TestSignal", 0, 32, 0, 4, 'uint')
        response = [1, 0, 0, 128]
        unpacked_value = self.tl._ThousandLib__unpack_uint(test_signal, response)
        assert unpacked_value == 2147483649


    def test_update_vfd_params(self):
        """
        Test to update vfd motor params
        """
        # Invalid id in response
        resp = {"cmd":"vfdResult", "id":4, "data":"0x01,0X03,0x02,0x02,0x3A,0x10,0x44","timestamp":[204,90,12,0]}

        changed_signal, err_code = self.tl.update_vfd_params(resp)

        assert changed_signal == []
        assert err_code == self.tl.rs232Codes.VFD_ID_ERR.name



        # Correct response
        resp = {"cmd":"vfdResult", "id":0, "data":"0x01,0X03,0x02,0x02,0x3A,0x10,0x44","timestamp":[204,90,12,0]}

        changed_signal, err_code = self.tl.update_vfd_params(resp)

        assert changed_signal == [self.tl.params_vfdResult.VFD_MOTOR_CURRENT.value]
        assert err_code == self.tl.rs232Codes.NO_ERR.name


    def test_unpack_vfd_motor_data(self):
        """
        Test to unpack vfd motor result data
        """
        test_signal = Signal("", "TestSignal", 0,0,4,2,'vfd')
        response = '0x1A, 0x01, 0x54, 0x3D, 0xA7, 0x2D, 0xF2'
        unpacked_value = self.tl._ThousandLib__unpack_vfdResult_data(test_signal, response)
        assert unpacked_value == 15783

    def test_get_param(self):
        """
        Test get param.
        """
        self.tl.database, db_len = self.set_up_mocked_database_with_values()
        # Try to get param that is not db
        param = 2
        val, err_code = self.tl.get_param(param)
        assert val == str(param)
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Try to get param that is not db
        val, err_code = self.tl.get_param(db_len + 10)
        assert val == -1
        assert err_code == self.tl.rs232Codes.PARAM_NOT_IN_DB.name

        # Try getting param when value is not set for existing param
        tmp_database = dict()
        tmp_database[0] = Signal("", "NoValueTest", 0, 32, 0, 4, 'uint')
        self.tl.database = tmp_database

        val, err_code = self.tl.get_param(0)
        assert val == -1
        assert err_code == self.tl.rs232Codes.PARAM_NOT_SET.name

    def test_set_param(self):
        """Test set_param updates database value."""
        self.tl.database, _ = self.set_up_mocked_database_with_values()
        changed, err_code = self.tl.set_param(2, 99)
        assert changed == [2]
        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert self.tl.database[2].value == 99

    def test_set_param_same_value(self):
        """Test set_param with unchanged value returns empty list."""
        self.tl.database, _ = self.set_up_mocked_database_with_values()
        self.tl.set_param(2, 99)
        changed, err_code = self.tl.set_param(2, 99)
        assert changed == []
        assert err_code == self.tl.rs232Codes.NO_ERR.name

    def test_set_param_not_in_db(self):
        """Test set_param with param not in database."""
        self.tl.database, db_len = self.set_up_mocked_database_with_values()
        changed, err_code = self.tl.set_param(db_len + 10, 42)
        assert changed == []
        assert err_code == self.tl.rs232Codes.PARAM_NOT_IN_DB.name

    @staticmethod
    def set_up_mocked_database_with_values():
        database_length = 6
        database = [None] * database_length
        database[0] = Signal("0", "UintTest", 0, 32, 0, 4, 'uint')
        database[1] = Signal("1", "TimeTest", 0, 32, 4, 4, 'wtime')
        database[2] = Signal("2", "ByteTest", 0, 8, 8, 1, 'byte')
        database[3] = Signal("3", "StringTest", 0, 32, 9, 5, 'string')
        database[4] = Signal("4", "TimeTest", 0, 32, 14, 4, 'time')
        database[5] = Signal("5", "GenericTextTest", 0, 0, 18, 39, 'generic_text')
        return database, len(database)

    def test_get_updated_params_with_values(self):
        """
        Test get_updated_params and get_param to  that values are updated correctly.
        """
        # Mock package two for unpacking
        package_nr = '2'
        self.tl.params_2 = mocked_enum

        # Mock database
        self.tl.database = set_up_mocked_database()

        # Setup received response and expected values
        nr_of_signals = 6

        uint_response = [0, 128, 0, 0]
        expected_uint = '32768'

        wtime_response = [0, 0, 0, 0]
        expected_wtime = '0'

        byte_response = [23]
        expected_byte = '23'

        string_response = [65, 114, 105, 116, 99, 111, 32, 73]
        expected_string = "AritcoI"

        time_response = [100, 0, 0, 0]
        expected_time = '978307300'  # Epoch time (978307200+100)

        generic_text_response = ['Li,ft102 3']
        expected_generic_text = "Li ft102 3"

        full_response = uint_response + wtime_response + byte_response + string_response + time_response + \
                        generic_text_response

        # Assert that all signals are changed
        changed_signals, err_code = self.tl.get_updated_params(package_nr, full_response)
        assert len(changed_signals) == nr_of_signals
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Assert values
        err_code = self.tl.rs232Codes.NO_ERR.name
        assert expected_uint, err_code == self.tl.get_param(self.tl.params_2.UINT_TEST.value)
        assert expected_wtime, err_code == self.tl.get_param(self.tl.params_2.WTIME_TEST.value)
        assert expected_byte, err_code == self.tl.get_param(self.tl.params_2.BYTE_TEST.value)
        assert expected_string, err_code == self.tl.get_param(self.tl.params_2.STRING_TEST.value)
        assert expected_time, err_code == self.tl.get_param(self.tl.params_2.TIME_TEST.value)
        assert expected_generic_text, err_code == self.tl.get_param(self.tl.params_2.OBJECT_ID_TEST.value)

        # Try getting params again and assert that no signals are changed
        changed_signals, err_code = self.tl.get_updated_params(package_nr, full_response)
        assert len(changed_signals) == 0
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Change one signal
        uint_response = [1, 128, 0, 0]
        expected_uint = '32769'
        full_response = uint_response + wtime_response + byte_response + string_response + time_response + \
                        generic_text_response

        # Assert that one signal has changed
        changed_signals, err_code = self.tl.get_updated_params(package_nr, full_response)
        assert len(changed_signals) == 1
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Assert value of changed signal
        assert expected_uint, err_code == self.tl.get_param(self.tl.params_2.UINT_TEST.value)

        # Change two with one faulty signal
        uint_response = [255, 128, 0, 0]

        byte_response = [24]
        expected_byte = '24'

        full_response = uint_response + wtime_response + byte_response + string_response + time_response + \
                        generic_text_response

        # Assert that one signal is updated properly, the other ignored
        changed_signals, err_code = self.tl.get_updated_params(package_nr, full_response)
        assert len(changed_signals) == 2
        # assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        assert expected_byte, err_code == self.tl.get_param(self.tl.params_2.BYTE_TEST.value)

    def test_not_supported_package_id(self):
        """
        Test a package ID that is not supported!
        """
        exp_ar_number = "AR12x34x56"
        ar_number_resp = [exp_ar_number]

        package_generic_text_response = ar_number_resp
        assert len(package_generic_text_response) == 1

        changed_signals, err_code = self.tl.get_updated_params('random_mumbo_jumbo', package_generic_text_response)
        assert len(changed_signals) == 0
        assert err_code == self.tl.rs232Codes.PACKAGE_NOT_SUPPORTED.name

    def test_complete_database_lift_ar(self):
        """
        Test full generic_text signal type
        """
        exp_ar_number = "AR12x34x56"
        ar_number_resp = [exp_ar_number]

        package_generic_text_response = ar_number_resp
        assert len(package_generic_text_response) == 1

        changed_signals, err_code = self.tl.get_updated_params('liftRef1', package_generic_text_response)
        assert len(changed_signals) == len(self.tl.params_lift_ar)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_lift_ar.AR_NUMBER.value, exp_ar_number, err_code)

    def test_complete_database_lift_type(self):
        """
        Test full generic_text signal type
        """
        exp_lift_type = "Compact"
        lift_type_resp = [exp_lift_type]

        package_generic_text_response = lift_type_resp
        assert len(package_generic_text_response) == 1

        changed_signals, err_code = self.tl.get_updated_params('liftRef2', package_generic_text_response)
        assert len(changed_signals) == len(self.tl.params_lift_type)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_lift_type.LIFT_TYPE.value, exp_lift_type, err_code)

    def test_complete_database_lift_name(self):
        """
        Test full generic_text signal type
        """
        exp_lift_name = "Behind you"
        lift_name_resp = ["Behind_you"]

        package_generic_text_response = lift_name_resp
        assert len(package_generic_text_response) == 1

        changed_signals, err_code = self.tl.get_updated_params('liftName', package_generic_text_response)
        assert len(changed_signals) == len(self.tl.params_lift_name)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_lift_name.LIFT_NAME.value, exp_lift_name, err_code)

    def test_complete_database_ar_version(self):
        """
        Test full version signal type
        """
        expected_main_version = '1'
        main_version = [int(expected_main_version)]

        expected_sub_version = '2'
        sub_version = [int(expected_sub_version)]

        expected_hardware_version = '3'
        hardware_version = [int(expected_hardware_version)]

        expected_op_version = '4'
        op_version = [int(expected_op_version)]

        expected_min_version = '5'
        min_version = [int(expected_min_version)]

        expected_beta_version = '6'
        beta_version = [int(expected_beta_version)]

        expected_u19_hw_version = '7'
        u19_hw_version = [int(expected_u19_hw_version)]

        expected_u19_op_version = '8'
        u19_op_version = [int(expected_u19_op_version)]

        expected_u19_main_version = '9'
        u19_main_version = [int(expected_u19_main_version)]

        expected_u19_sub_version = '10'
        u19_sub_version = [int(expected_u19_sub_version)]

        expected_u19_min_version = '11'
        u19_min_version = [int(expected_u19_min_version)]

        expected_u19_beta_version = '12'
        u19_beta_version = [int(expected_u19_beta_version)]

        package_ar_version_response = main_version + sub_version + hardware_version + op_version +\
            min_version + beta_version + u19_hw_version + u19_op_version + u19_main_version +\
            u19_sub_version + u19_min_version + u19_beta_version
        assert len(package_ar_version_response) == 12

        changed_signals, err_code = self.tl.get_updated_params('version', package_ar_version_response)
        assert len(changed_signals) == len(self.tl.params_version)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_version.ARGATE_MAIN_VERSION.value, expected_main_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_SUB_VERSION.value, expected_sub_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_HW_VERSION.value, expected_hardware_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_OP_VERSION.value, expected_op_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_MIN_VERSION.value, expected_min_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_BETA_VERSION.value, expected_beta_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_HW_VERSION.value, expected_u19_hw_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_OP_VERSION.value, expected_u19_op_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_MAIN_VERSION.value, expected_u19_main_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_SUB_VERSION.value, expected_u19_sub_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_MIN_VERSION.value, expected_u19_min_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_BETA_VERSION.value, expected_u19_beta_version, err_code)

    def test_U1_46_ar_version(self):
        """
        Test when version response if from U1 4.6 and older
        """
        expected_main_version = '1'
        main_version = [int(expected_main_version)]

        expected_sub_version = '2'
        sub_version = [int(expected_sub_version)]

        expected_hardware_version = '3'
        hardware_version = [int(expected_hardware_version)]

        expected_op_version = '4'
        op_version = [int(expected_op_version)]

        expected_min_version = '5'
        min_version = [int(expected_min_version)]

        expected_beta_version = '6'
        beta_version = [int(expected_beta_version)]

        expected_u19_hw_version = '7'
        u19_hw_version = [int(expected_u19_hw_version)]

        expected_u19_op_version = '8'
        u19_op_version = [int(expected_u19_op_version)]

        expected_u19_main_version = '0'
        u19_main_version = [int(expected_u19_main_version)]

        expected_u19_sub_version = '10'
        u19_sub_version = [int(expected_u19_sub_version)]

        expected_u19_min_version = '11'
        u19_min_version = [int(expected_u19_min_version)]

        expected_u19_beta_version = '12'
        u19_beta_version = [int(expected_u19_beta_version)]

        package_U1_46_ar_version_response = (main_version +
                                             sub_version +
                                             hardware_version +
                                             op_version +
                                             min_version +
                                             beta_version +
                                             u19_hw_version +
                                             u19_op_version +
                                             u19_main_version +
                                             u19_sub_version +
                                             u19_min_version +
                                             u19_beta_version)
        assert len(package_U1_46_ar_version_response) == 12

        changed_signals, err_code = self.tl.get_updated_params('version', package_U1_46_ar_version_response)
        assert len(changed_signals) == len(self.tl.params_version)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_version.ARGATE_MAIN_VERSION.value, expected_main_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_SUB_VERSION.value, expected_sub_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_HW_VERSION.value, expected_hardware_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_OP_VERSION.value, expected_op_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_MIN_VERSION.value, expected_min_version, err_code)
        self.assert_value_and_error(self.tl.params_version.ARGATE_BETA_VERSION.value, expected_beta_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_HW_VERSION.value, expected_u19_hw_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_OP_VERSION.value, expected_u19_op_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_MAIN_VERSION.value, expected_u19_main_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_SUB_VERSION.value, expected_u19_sub_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_MIN_VERSION.value, expected_u19_min_version, err_code)
        self.assert_value_and_error(self.tl.params_version.U19_BETA_VERSION.value, expected_u19_beta_version, err_code)

    def test_complete_database_2(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on package 2 from the lift.
        This tests the complete enum defined in ThousandLib for package 2. I.e. all signals currently used from that
        package.
        """
        s_1970_to_2001 = 978307200

        file_date = [151, 5, 52, 39]
        expected_file_date = str(s_1970_to_2001 + 657720727)

        prog_date = [152, 5, 52, 39]
        expected_prog_date = str(s_1970_to_2001 + 657720728)

        prog_name = [65, 114, 105, 116, 99, 111, 32, 72, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        assert len(prog_name) == 20
        expected_progname = 'AritcoH'

        main_version = [9]
        expected_main_version = '9'

        sub_version = [7]
        expected_sub_version = '7'

        op_version = [3]
        expected_op_version = '3'

        hardware_version = [2]
        expected_hardware_version = '2'

        package_2_response = file_date + prog_date + prog_name + main_version + sub_version + op_version + \
                             hardware_version
        assert len(package_2_response) == 32

        changed_signals, err_code = self.tl.get_updated_params('2', package_2_response)
        assert len(changed_signals) == len(self.tl.params_2)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_2.FILE_DATE_2.value, expected_file_date, err_code)
        self.assert_value_and_error(self.tl.params_2.PROG_DATE_2.value, expected_prog_date, err_code)
        self.assert_value_and_error(self.tl.params_2.PROG_NAME_2.value, expected_progname, err_code)
        self.assert_value_and_error(self.tl.params_2.MAIN_VERSION_2.value, expected_main_version, err_code)
        self.assert_value_and_error(self.tl.params_2.SUB_VERSION_2.value, expected_sub_version, err_code)
        self.assert_value_and_error(self.tl.params_2.OS_VERSION_2.value, expected_op_version, err_code)
        self.assert_value_and_error(self.tl.params_2.HW_VERSION_2.value, expected_hardware_version, err_code)

    def test_complete_database_130(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on package 130 from the lift.
        This tests the complete enum defined in ThousandLib for package 130. I.e. all signals currently used from that
        package.
        """
        # Mock complete 130 package response.
        battery_state_and_safe = [1]
        # expected_battery_state = '1'
        expected_safe = '0'

        floor = [22]
        expected_floor = '22'

        oil_level = [92]
        expected_oil_level = '92'

        load_current = [13]
        expected_load_current = '13'

        no_node_and_free = [4]
        expected_no_node = '4'

        floor_info_1 = [29]  # 00011101
        expected_floor_info_1_fire = '1'
        expected_floor_info_1_cabin = '0'
        expected_floor_info_1_shaft = '1'
        expected_floor_info_1_lock = '1'
        expected_floor_info_1_input = '1'

        floor_info_2 = [2]  # 00000010
        expected_floor_info_2_fire = '0'
        expected_floor_info_2_cabin = '1'
        expected_floor_info_2_shaft = '0'
        expected_floor_info_2_lock = '0'
        expected_floor_info_2_input = '0'

        floor_info_3 = [21]  # 00010101
        expected_floor_info_3_fire = '1'
        expected_floor_info_3_cabin = '0'
        expected_floor_info_3_shaft = '1'
        expected_floor_info_3_lock = '0'
        expected_floor_info_3_input = '1'

        floor_info_4 = [29]  # 00011101
        expected_floor_info_4_fire = '1'
        expected_floor_info_4_cabin = '0'
        expected_floor_info_4_shaft = '1'
        expected_floor_info_4_lock = '1'
        expected_floor_info_4_input = '1'

        floor_info_5 = [2]  # 00000010
        expected_floor_info_5_fire = '0'
        expected_floor_info_5_cabin = '1'
        expected_floor_info_5_shaft = '0'
        expected_floor_info_5_lock = '0'
        expected_floor_info_5_input = '0'

        floor_info_6 = [21]  # 00010101
        expected_floor_info_6_fire = '1'
        expected_floor_info_6_cabin = '0'
        expected_floor_info_6_shaft = '1'
        expected_floor_info_6_lock = '0'
        expected_floor_info_6_input = '1'

        # Bytes for floors 7 and 8 are sent but never used by GW
        floor_info_7 = [0]
        floor_info_8 = [0]

        sob_0 = [170]  # 10101010
        expected_sob_0_has_pump = '0'
        expected_sob_0_power_in = '1'
        expected_sob_0_door_not_open = '0'
        # expected_sob_0_door_openener = '1'
        expected_sob_0_alarm_active = '0'
        expected_sob_0_lift_locked = '1'
        expected_sob_0_door_open_1min = '0'
        expected_sob_0_contactor_stuck = '1'

        # Some bits are not used in this byte
        sob_1 = [170]  # 10101010
        # expected_sob_1_contactor_check = '0'
        # expected_sob_1_friction_test = '1'
        expected_sob_1_batt_missing = '0'
        expected_sob_1_batt_change = '1'
        expected_sob_1_batt_bad = '0'
        expected_sob_1_batt_charge_err = '1'
        expected_sob_1_cabin_lift = '0'
        # expected_sob_1_b_lift = '0'

        sob_2 = [170]  # 10101010
        # expected_sob_2_impulse = '0'
        expected_sob_2_emerg_fail = '1'
        expected_sob_2_lift_needs_service = '0'
        expected_sob_2_over_current = '1'
        expected_sob_2_reduce_light = '0'
        # expected_sob_2_photo_cell = '1'
        expected_sob_2_run_time = '0'
        expected_sob_2_fire = '1'

        sob_3 = [170]  # 10101010
        expected_sob_3_plug23 = '0'
        expected_sob_3_over_load = '1'
        # expected_sob_3_oil_out_on = '0'
        # expected_sob_3_busy_timer = '1'
        # expected_sob_3_Busy_cabin = '0'
        expected_sob_3_child_lock = '1'
        expected_sob_3_battery_testing = '0'
        expected_sob_3_battery_test_suspended = '1'


        package_130_response = battery_state_and_safe + floor + oil_level + load_current + no_node_and_free + \
                               floor_info_1 + floor_info_2 + floor_info_3 + floor_info_4 + floor_info_5 + \
                               floor_info_6 + floor_info_7 + floor_info_8 + sob_0 + sob_1 + sob_2 + sob_3
        assert len(package_130_response) == 17

        changed_signals, err_code = self.tl.get_updated_params('130', package_130_response)
        assert len(changed_signals) == len(self.tl.params_130)

        err_code = self.tl.rs232Codes.NO_ERR.name
        # self.assert_value_and_error(self.tl.params_130.BATTERY_STATE_130.value, expected_battery_state, err_code)
        self.assert_value_and_error(self.tl.params_130.SAFETY_130.value, expected_safe, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_130.value, expected_floor, err_code)
        self.assert_value_and_error(self.tl.params_130.OIL_LEVEL_130.value, expected_oil_level, err_code)
        self.assert_value_and_error(self.tl.params_130.LOAD_CURRENT_130.value, expected_load_current, err_code)
        self.assert_value_and_error(self.tl.params_130.NO_NODES_130.value, expected_no_node, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_1_FIRE_130.value, expected_floor_info_1_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_1_CABIN_130.value, expected_floor_info_1_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_1_SHAFT_130.value, expected_floor_info_1_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_1_LOCK_130.value, expected_floor_info_1_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_1_INPUT_130.value, expected_floor_info_1_input, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_2_FIRE_130.value, expected_floor_info_2_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_2_CABIN_130.value, expected_floor_info_2_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_2_SHAFT_130.value, expected_floor_info_2_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_2_LOCK_130.value, expected_floor_info_2_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_2_INPUT_130.value, expected_floor_info_2_input, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_3_FIRE_130.value, expected_floor_info_3_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_3_CABIN_130.value, expected_floor_info_3_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_3_SHAFT_130.value, expected_floor_info_3_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_3_LOCK_130.value, expected_floor_info_3_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_3_INPUT_130.value, expected_floor_info_3_input, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_4_FIRE_130.value, expected_floor_info_4_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_4_CABIN_130.value, expected_floor_info_4_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_4_SHAFT_130.value, expected_floor_info_4_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_4_LOCK_130.value, expected_floor_info_4_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_4_INPUT_130.value, expected_floor_info_4_input, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_5_FIRE_130.value, expected_floor_info_5_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_5_CABIN_130.value, expected_floor_info_5_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_5_SHAFT_130.value, expected_floor_info_5_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_5_LOCK_130.value, expected_floor_info_5_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_5_INPUT_130.value, expected_floor_info_5_input, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_6_FIRE_130.value, expected_floor_info_6_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_6_CABIN_130.value, expected_floor_info_6_cabin, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_6_SHAFT_130.value, expected_floor_info_6_shaft, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_6_LOCK_130.value, expected_floor_info_6_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.FLOOR_6_INPUT_130.value, expected_floor_info_6_input, err_code)
        self.assert_value_and_error(self.tl.params_130.HAS_PUMP_130.value, expected_sob_0_has_pump, err_code)
        self.assert_value_and_error(self.tl.params_130.POWER_IN_130.value, expected_sob_0_power_in, err_code)
        self.assert_value_and_error(self.tl.params_130.DOOR_NOT_OPEN_130.value, expected_sob_0_door_not_open, err_code)
        self.assert_value_and_error(self.tl.params_130.ALARM_ACTIVE_130.value, expected_sob_0_alarm_active, err_code)
        self.assert_value_and_error(self.tl.params_130.LIFT_LOCKED_130.value, expected_sob_0_lift_locked, err_code)
        self.assert_value_and_error(self.tl.params_130.DOOR_OPEN_1MIN_130.value, expected_sob_0_door_open_1min,
                                    err_code)
        self.assert_value_and_error(self.tl.params_130.CONTACTOR_STUCK_130.value, expected_sob_0_contactor_stuck,
                                    err_code)
        self.assert_value_and_error(self.tl.params_130.BATT_MISSING_130.value, expected_sob_1_batt_missing, err_code)
        self.assert_value_and_error(self.tl.params_130.BATT_CHANGE_130.value, expected_sob_1_batt_change, err_code)
        self.assert_value_and_error(self.tl.params_130.BATT_BAD_130.value, expected_sob_1_batt_bad, err_code)
        self.assert_value_and_error(self.tl.params_130.BATT_CHARGER_ERR_130.value, expected_sob_1_batt_charge_err,
                                    err_code)
        self.assert_value_and_error(self.tl.params_130.CABIN_LIFT_130.value, expected_sob_1_cabin_lift, err_code)
        # self.assert_value_and_error(self.tl.params_130.IMPULSE_130.value, expected_sob_2_impulse, err_code)
        self.assert_value_and_error(self.tl.params_130.EMERG_FAIL_130.value, expected_sob_2_emerg_fail, err_code)
        self.assert_value_and_error(self.tl.params_130.LIFT_NEEDS_SERVICE_130.value, expected_sob_2_lift_needs_service,
                                    err_code)
        self.assert_value_and_error(self.tl.params_130.OVER_CURRENT_130.value, expected_sob_2_over_current, err_code)
        self.assert_value_and_error(self.tl.params_130.REDUCE_LIGHT_130.value, expected_sob_2_reduce_light, err_code)
        self.assert_value_and_error(self.tl.params_130.RUN_TIME_130.value, expected_sob_2_run_time, err_code)
        self.assert_value_and_error(self.tl.params_130.FIRE_130.value, expected_sob_2_fire, err_code)
        self.assert_value_and_error(self.tl.params_130.PLUG_23_130.value, expected_sob_3_plug23, err_code)
        self.assert_value_and_error(self.tl.params_130.OVER_LOAD_130.value, expected_sob_3_over_load, err_code)
        self.assert_value_and_error(self.tl.params_130.CHILD_LOCK_130.value, expected_sob_3_child_lock, err_code)
        self.assert_value_and_error(self.tl.params_130.BATTERY_TESTING_130.value, expected_sob_3_battery_testing,
                                    err_code)
        self.assert_value_and_error(self.tl.params_130.BATTERY_TEST_SUSPENDED_130.value,
                                    expected_sob_3_battery_test_suspended, err_code)

    @patch('time.time')
    def test_complete_database_131(self, time_patch):
        """
        Test get_updated_params without mocking the database. I.e. with full response on package 131 from the lift.
        This tests the complete enum defined in ThousandLib for package 131. I.e. all signals currently used from that package.
        """
        # Mock complete 131 package response.
        time_now_s = 17777216
        time_patch.return_value = time_now_s
        max_time = 60 * 60 * 24 * 7
        door_in_run = [1, 0, 0, 0]
        expected_door_in_run = str(time_now_s - (max_time - 1))

        lock_in_run = [0, 1, 0, 0]
        expected_lock_in_run = str(time_now_s - (max_time - 256))

        floor_1_dubbel = [0, 0, 1, 0]
        expected_floor_1_dubbel = str(time_now_s - (max_time - 65536))

        floor_x_dubbel = [0, 0, 0, 1]
        expected_floor_X_dubbel = str(time_now_s - (max_time - 16777216))

        floor_top_dubbel = [2, 0, 0, 0]
        expected_floor_Top_dubbel = str(time_now_s - (max_time - 2))

        step_fail = [3, 0, 0, 0]
        expected_step_fail = str(time_now_s - (max_time - 3))

        battery_bad = [4, 0, 0, 0]
        expected_battery_bad = str(time_now_s - (max_time - 4))

        battery_missing = [5, 0, 0, 0]
        expected_battery_missing = str(time_now_s - (max_time - 5))

        emerg_light = [6, 0, 0, 0]
        expected_emerg_light = str(time_now_s - (max_time - 6))

        overload_24v = [7, 0, 0, 0]
        expected_overload_24V = str(time_now_s - (max_time - 7))

        door_open_1min = [8, 0, 0, 0]
        expected_door_open_1min = str(time_now_s - (max_time - 8))

        contactor_check = [9, 0, 0, 0]
        expected_contactor_check = str(time_now_s - (max_time - 9))

        shaft_unit_gone = [10, 0, 0, 0]
        expected_shaft_unit_gone = str(time_now_s - (max_time - 10))

        batt_rest_fail = [11, 0, 0, 0]
        expected_batt_rest_fail = str(time_now_s - (max_time - 11))

        batt_charge_fail = [12, 0, 0, 0]
        expected_batt_charge_fail = str(time_now_s - (max_time - 12))

        fire_block = [13, 0, 0, 0]
        expected_fire_block = str(time_now_s - (max_time - 13))

        test_friction = [14, 0, 0, 0]
        expected_test_friction = str(time_now_s - (max_time - 14))

        vplug23_14v = [15, 0, 0, 0]
        expected_vplug23_14v = str(time_now_s - (max_time - 15))

        # Unused
        fotocell_stop = [16, 0, 0, 0]
        fotocell_check = [117, 0, 0, 0]

        lock_floor = [18, 0, 0, 0]
        expected_lock_floor = str(time_now_s - (max_time - 18))

        run_timeout = [119, 0, 0, 0]
        expected_run_timeout = str(time_now_s - (max_time - 119))

        oil_short_circuit = [230, 0, 0, 0]
        expected_oil_short_circuit = str(time_now_s - (max_time - 230))

        batt_fuse = [0, 0, 0, 0]
        expected_batt_fuse = str(0)

        platform_safety = [9, 0, 0, 0]
        expected_platform_safety = str(time_now_s - (max_time - 9))

        package_131_response = door_in_run + lock_in_run + floor_1_dubbel + floor_x_dubbel + floor_top_dubbel + \
                               step_fail + battery_bad + battery_missing + emerg_light + overload_24v + \
                               door_open_1min + contactor_check + shaft_unit_gone + batt_rest_fail + batt_charge_fail +\
                               fire_block + test_friction + vplug23_14v + fotocell_stop + fotocell_check + lock_floor +\
                               run_timeout + oil_short_circuit + batt_fuse + platform_safety
        assert len(package_131_response) == 4 * 25

        changed_signals, err_code = self.tl.get_updated_params('131', package_131_response)
        assert len(changed_signals) == len(self.tl.params_131)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_131.DOOR_IN_RUN.value, expected_door_in_run, err_code)
        self.assert_value_and_error(self.tl.params_131.LOCK_IN_RUN.value, expected_lock_in_run, err_code)
        self.assert_value_and_error(self.tl.params_131.FLOOR_1_DUBBEL.value, expected_floor_1_dubbel, err_code)
        self.assert_value_and_error(self.tl.params_131.FLOOR_X_DUBBEL.value, expected_floor_X_dubbel, err_code)
        self.assert_value_and_error(self.tl.params_131.FLOOR_TOP_DUBBEL.value, expected_floor_Top_dubbel, err_code)
        self.assert_value_and_error(self.tl.params_131.STEP_FAIL.value, expected_step_fail, err_code)
        self.assert_value_and_error(self.tl.params_131.BATTERY_BAD.value, expected_battery_bad, err_code)
        self.assert_value_and_error(self.tl.params_131.BATTERY_MISSING.value, expected_battery_missing, err_code)
        self.assert_value_and_error(self.tl.params_131.EMERG_LIGHT.value, expected_emerg_light, err_code)
        self.assert_value_and_error(self.tl.params_131.OVERLOAD_24V.value, expected_overload_24V, err_code)
        self.assert_value_and_error(self.tl.params_131.DOOR_OPEN_1_MIN.value, expected_door_open_1min, err_code)
        self.assert_value_and_error(self.tl.params_131.CHECK_CONTACTOR.value, expected_contactor_check, err_code)
        self.assert_value_and_error(self.tl.params_131.SHAFT_UNIT_GONE.value, expected_shaft_unit_gone, err_code)
        self.assert_value_and_error(self.tl.params_131.BATT_TEST_FAIL.value, expected_batt_rest_fail, err_code)
        self.assert_value_and_error(self.tl.params_131.BATT_CHARGE_FAIL.value, expected_batt_charge_fail, err_code)
        self.assert_value_and_error(self.tl.params_131.FIRE_BLOCK.value, expected_fire_block, err_code)
        self.assert_value_and_error(self.tl.params_131.TEST_FRICTION.value, expected_test_friction, err_code)
        self.assert_value_and_error(self.tl.params_131.VPLUG23_14V.value, expected_vplug23_14v, err_code)
        self.assert_value_and_error(self.tl.params_131.LOCK_FLOOR.value, expected_lock_floor, err_code)
        self.assert_value_and_error(self.tl.params_131.RUN_TIMEOUT.value, expected_run_timeout, err_code)
        self.assert_value_and_error(self.tl.params_131.OIL_SHORT_CIRCUIT.value, expected_oil_short_circuit, err_code)
        self.assert_value_and_error(self.tl.params_131.BATT_FUSE.value, expected_batt_fuse, err_code)
        self.assert_value_and_error(self.tl.params_131.PLATFORM_SAFETY.value, expected_platform_safety, err_code)

    def test_complete_database_134(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on package 134 from the lift.
        This tests the complete enum defined in ThousandLib for package 134. I.e. all signals currently used from that package.
        """
        # Mock package 134 response
        current = [100, 0]
        expected_current = '100'

        # Not used
        load = [0, 0]
        safe_out = [0, 0]
        safe_platform = [0, 0]
        safe_door = [0, 0]
        safe_lock = [0, 0]
        power_in = [0, 0]
        v_in = [0, 0]
        v_out = [0, 0]
        ripple = [0, 0]
        batt_out = [0, 0]
        plug_23 = [0, 0]
        relay_sense = [0, 0]

        temp = [99, 0]
        expected_temp = '99'

        # Not used
        system_up_timer = [0, 0, 0, 0]

        total_starts = [123, 1, 0, 0]
        expected_total_starts = '379'

        total_run_time = [123, 2, 1, 1]
        expected_total_run_time = '16843387'

        # Not used
        trip_starts = [0, 0, 0, 0]
        trip_run_time = [0, 0, 0, 0]

        package_134_response = current + load + safe_out + safe_platform + safe_door + safe_lock + power_in + \
                               v_in + v_out + ripple + batt_out + plug_23 + relay_sense + temp + system_up_timer + \
                               total_starts + total_run_time + trip_starts + trip_run_time
        assert len(package_134_response) == 48

        changed_signals, err_code = self.tl.get_updated_params('134', package_134_response)
        assert len(changed_signals) == len(self.tl.params_134)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_134.CURRENT.value, expected_current, err_code)
        # self.assert_value_and_error(self.tl.params_134.TEMP.value, expected_temp, err_code)
        self.assert_value_and_error(self.tl.params_134.TOTAL_STARTS.value, expected_total_starts, err_code)
        self.assert_value_and_error(self.tl.params_134.TOTAL_RUN_TIME.value, expected_total_run_time, err_code)

    def test_complete_database_133(self):
        # Mock package 133 response (complete package 133 is ignored)

        #Not used
        battery_status = [0]
        # Not used
        battery_progress = [0]
        # Not used
        charge_load = [0]
        # Not used
        test_mode = [0]

        battery_voltage = [78, 0]
        expected_battery_voltage = '78'

        battery_capacity = [1, 2]
        expected_battery_capacity = '513'

        # Not used
        battery_time = [0, 0]
        # Not used
        battery_resistance = [0, 0]

        battery_current = [23, 1]
        expected_battery_current = '279'

        # Not used
        next_time_to_test_battery = [0, 0, 0, 0]

        package_133_response = battery_status+battery_progress+charge_load+test_mode+battery_voltage+battery_capacity+battery_time+battery_resistance+battery_current+next_time_to_test_battery
        assert len(package_133_response) == 18

        changed_signals, err_code = self.tl.get_updated_params('133', package_133_response)

        assert len(changed_signals) == len(self.tl.params_133)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_133.BATTERY_VOLTAGE.value, expected_battery_voltage, err_code)
        self.assert_value_and_error(self.tl.params_133.BATTERY_CAPACITY.value, expected_battery_capacity, err_code)
        self.assert_value_and_error(self.tl.params_133.BATTERY_CURRENT.value, expected_battery_current, err_code)

    def test_complete_database_virtual(self):
        """
        Test get_updated_params without mocking the database for all virtual params.
        """
        package_130_response = [1, 22, 92, 13, 4, 29, 2, 21, 29, 2, 21, 0, 0, 170, 170, 170, 170]
        package_2_response = [151, 5, 52, 39, 152, 5, 52, 39, 65, 114, 105, 116, 99, 111, 72,
                              0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 7, 3, 2]
        package_134_response = [100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0, 0, 0, 0, 99, 0, 0, 0, 0, 0, 123, 1, 0, 0,
                                123, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]

        expected_battery_state = '1'
        expected_impulse = '0'
        expected_temp = '0'
        # Response for package 130 is needed for BATTERY_STATE
        changed_signals, err_code = self.tl.get_updated_params('130', package_130_response)
        assert len(changed_signals) == len(self.tl.params_130)
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Update params for package 2. PROGNAME is needed to calculate value of IMPULSE
        changed_signals, err_code = self.tl.get_updated_params('2', package_2_response)
        assert len(changed_signals) == len(self.tl.params_2)
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Update params for package 134, in order to test Temp signal
        changed_signals, err_code = self.tl.get_updated_params('134', package_134_response)
        assert len(changed_signals) == len(self.tl.params_134)
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        changed_signals, err_code = self.tl.get_updated_params('virtual')
        assert len(changed_signals) == len(self.tl.params_virtual)
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_virtual.BATTERY_STATE_130.value, expected_battery_state, err_code)
        self.assert_value_and_error(self.tl.params_virtual.IMPULSE_130.value, expected_impulse, err_code)
        self.assert_value_and_error(self.tl.params_virtual.TEMP_134.value, expected_temp, err_code)

    def test_complete_database_readFileParam(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on read file PAram from the lift.
        This tests the complete enum defined in ThousandLib for read file PAram. I.e. all signals currently used from that
        file.
        """
        # Mock complete readFileParam response.
        door_time = [15,0]
        expected_door_time = '15'

        cabin_light = [60,0]
        expected_cabin_light = '60'

        alarm_time = [0,0]
        expected_alarm_time = '0'

        close_call_delay = [3,0]
        expected_close_call_delay = '3'

        door_open_delay = [0,0]
        expected_door_open_delay = '0'

        fire_floor = [1,0]
        expected_fire_floor = '1'

        return_floor = [0,0]
        expected_return_floor = '0'

        return_time = [60,0]
        expected_return_time = '60'

        valve_intensity = [2,0]
        expected_valve_intensity = '2'

        impulse_cabin = [0,0]
        expected_impulse_cabin = '0'

        beep_platform = [0,0]
        expected_beep_platform = '0'

        beep_arrival = [0,0]
        expected_beep_arrival = '0'

        batt_test_use_emergency = [1,0]
        expected_batt_test_use_emergency = '1'

        door_lock_time = [10,0]
        expected_door_lock_time = '10'

        pump_intensity = [6,0]
        expected_pump_intensity = '6'

        readFile_param_response = door_time + cabin_light + alarm_time + close_call_delay + door_open_delay +\
            fire_floor + return_floor + return_time + valve_intensity + impulse_cabin + beep_platform +\
            beep_arrival + batt_test_use_emergency + door_lock_time + pump_intensity

        assert len(readFile_param_response) == 30

        changed_signals, err_code = self.tl.get_updated_params('readFileParam', readFile_param_response)

        assert len(changed_signals) == len(self.tl.params_readFile_param)

        err_code = self.tl.rs232Codes.NO_ERR.name

        self.assert_value_and_error(self.tl.params_readFile_param.DOOR_TIME.value, expected_door_time, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.CABIN_LIGHT.value, expected_cabin_light, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.ALARM_TIME.value, expected_alarm_time, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.CLOSE_CALL_DELAY.value, expected_close_call_delay, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.DOOR_OPEN_DELAY.value, expected_door_open_delay, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.FIRE_FLOOR.value, expected_fire_floor, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.RETURN_FLOOR.value, expected_return_floor, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.RETURN_TIME.value, expected_return_time, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.VALVE_INTENSITY.value, expected_valve_intensity, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.IMPULSE_CABIN.value, expected_impulse_cabin, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.BEEP_PLATFORM.value, expected_beep_platform, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.BEEP_ARRIVAL.value, expected_beep_arrival, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.BATT_TEST_USE_EMERGENCY.value, expected_batt_test_use_emergency, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.DOOR_LOCK_TIME.value, expected_door_lock_time, err_code)
        self.assert_value_and_error(self.tl.params_readFile_param.PUMP_INTENSITY.value, expected_pump_intensity, err_code)

    def test_complete_database_readFileIntern(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on read file Intern from the lift.
        This tests the complete enum defined in ThousandLib for read file Intern. I.e. all signals currently used from that
        file.
        """
        # Mock complete readFileIntern response.

        freq_control = [0,0]
        expected_freq_control = '0'

        impulse_available = [0,0]
        expected_impulse_available = '0'

        lock_invert = [0,0]
        expected_lock_invert = '0'

        oil_mode = [0,0]
        expected_oil_mode = '0'

        node_direction = [0,0]
        expected_node_direction = '0'

        bottle_volume = [10,0]
        expected_bottle_volume = '10'

        emergency_delay = [70,0]
        expected_emergency_delay = '70'

        b_lift = [0,0]
        expected_b_lift = '0'

        common_light = [0,0]
        expected_common_light = '0'

        auto_lock_menu = [0,0]
        expected_auto_lock_menu = '0'

        battery_capacity = [100,0]
        expected_battery_capacity = '100'

        pump_capacity = [164,1]
        expected_pump_capacity = '420'

        AR_bus_ext = [0,0]
        expected_AR_bus_ext = '0'

        emergency_light_test = [0,0]
        expected_emergency_light_test = '0'

        readFile_intern_response = freq_control + impulse_available + lock_invert + oil_mode + node_direction +\
            bottle_volume + emergency_delay + b_lift + common_light + auto_lock_menu + battery_capacity +\
            pump_capacity + AR_bus_ext + emergency_light_test

        assert len(readFile_intern_response) == 28

        changed_signals, err_code = self.tl.get_updated_params('readFileIntern', readFile_intern_response)
        assert len(changed_signals) == len(self.tl.params_readFile_intern)

        err_code = self.tl.rs232Codes.NO_ERR.name
        self.assert_value_and_error(self.tl.params_readFile_intern.FREQ_CONTROL.value, expected_freq_control, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.IMPULSE_AVAILABLE.value, expected_impulse_available, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.LOCK_INVERT.value, expected_lock_invert, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.OIL_MODE.value, expected_oil_mode, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.NODE_DIRECTION.value, expected_node_direction, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.BOTTLE_VOLUME.value, expected_bottle_volume, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.EMERGENCY_DELAY.value, expected_emergency_delay, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.B_LIFT.value, expected_b_lift, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.COMMON_LIGHT.value, expected_common_light, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.BATT_CAPACITY.value, expected_battery_capacity, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.PUMP_CAPACITY.value, expected_pump_capacity, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.AR_BUS_EXT.value, expected_AR_bus_ext, err_code)
        self.assert_value_and_error(self.tl.params_readFile_intern.EMERGENCY_LIGHT_TEST.value, expected_emergency_light_test, err_code)

    def test_complete_database_readFileNode(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on readFile Node from the lift.
        This tests the complete enum defined in ThousandLib for readFile Node. I.e. all signals currently used from that
        file.
        """
        # Mock complete readFileNode response.

        floor_1_node = [1,0]
        expected_floor_1_node = '1'

        floor_2_node = [1,0]
        expected_floor_2_node = '1'

        floor_3_node = [1,0]
        expected_floor_3_node = '1'

        floor_4_node = [1,0]
        expected_floor_4_node = '1'

        floor_5_node = [1,0]
        expected_floor_5_node = '1'

        floor_6_node = [1,0]
        expected_floor_6_node = '1'

        readFile_node_response = floor_1_node + floor_2_node + floor_3_node + floor_4_node +\
            floor_5_node + floor_6_node

        assert len(readFile_node_response) == 12

        changed_signal, err_code = self.tl.get_updated_params('readFileNode', readFile_node_response)
        assert len(changed_signal) == len(self.tl.params_readFile_node)

        err_code = self.tl.rs232Codes.NO_ERR.name

        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_1_NODE.value, expected_floor_1_node, err_code)
        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_2_NODE.value, expected_floor_2_node, err_code)
        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_3_NODE.value, expected_floor_3_node, err_code)
        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_4_NODE.value, expected_floor_4_node, err_code)
        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_5_NODE.value, expected_floor_5_node, err_code)
        self.assert_value_and_error(self.tl.params_readFile_node.FLOOR_6_NODE.value, expected_floor_6_node, err_code)

    def test_complete_database_readFileLock(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on readFile Lock from the lift.
        This tests the complete enum defined in ThousandLib for readFile Lock. I.e. all signals currently used from that
        file.
        """
        # Mock complete readFileLock response.

        floor_1_lock = [0,0]
        expected_floor_1_lock = '0'

        floor_2_lock = [0,0]
        expected_floor_2_lock = '0'

        floor_3_lock = [0,0]
        expected_floor_3_lock = '0'

        floor_4_lock = [0,0]
        expected_floor_4_lock = '0'

        floor_5_lock = [0,0]
        expected_floor_5_lock = '0'

        floor_6_lock = [0,0]
        expected_floor_6_lock = '0'

        readFile_lock_response = floor_1_lock + floor_2_lock + floor_3_lock + floor_4_lock +\
            floor_5_lock + floor_6_lock

        assert len(readFile_lock_response) == 12

        changed_signal, err_code = self.tl.get_updated_params('readFileLock', readFile_lock_response)
        assert len(changed_signal) == len(self.tl.params_readFile_lock)

        err_code = self.tl.rs232Codes.NO_ERR.name

        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_1_LOCK.value, expected_floor_1_lock, err_code)
        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_2_LOCK.value, expected_floor_2_lock, err_code)
        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_3_LOCK.value, expected_floor_3_lock, err_code)
        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_4_LOCK.value, expected_floor_4_lock, err_code)
        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_5_LOCK.value, expected_floor_5_lock, err_code)
        self.assert_value_and_error(self.tl.params_readFile_lock.FLOOR_6_LOCK.value, expected_floor_6_lock, err_code)

    def test_complete_database_readFileDoor(self):
        """
        Test get_updated_params without mocking the database. I.e. with full response on readFile Door from the lift.
        This tests the complete enum defined in ThousandLib for readFile Door. I.e. all signals currently used from that
        file.
        """
        # Mock complete readFileDoor response.

        floor_1_double_door = [0,0]
        expected_floor_1_double_door = '0'

        floor_2_double_door = [0,0]
        expected_floor_2_double_door = '0'

        floor_3_double_door = [0,0]
        expected_floor_3_double_door = '0'

        floor_4_double_door = [0,0]
        expected_floor_4_double_door = '0'

        floor_5_double_door = [0,0]
        expected_floor_5_double_door = '0'

        floor_6_double_door = [0,0]
        expected_floor_6_double_door = '0'

        readFile_door_response = floor_1_double_door + floor_2_double_door + floor_3_double_door +\
            floor_4_double_door + floor_5_double_door + floor_6_double_door

        assert len(readFile_door_response) == 12

        changed_signal, err_code = self.tl.get_updated_params('readFileDoor', readFile_door_response)
        assert len(changed_signal) == len(self.tl.params_readFile_door)

        err_code = self.tl.rs232Codes.NO_ERR.name

        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_1_DOUBLE_DOOR.value, expected_floor_1_double_door, err_code)
        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_2_DOUBLE_DOOR.value,
                                    expected_floor_2_double_door, err_code)
        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_3_DOUBLE_DOOR.value,
                                    expected_floor_3_double_door, err_code)
        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_4_DOUBLE_DOOR.value,
                                    expected_floor_4_double_door, err_code)
        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_5_DOUBLE_DOOR.value,
                                    expected_floor_5_double_door, err_code)
        self.assert_value_and_error(self.tl.params_readFile_door.FLOOR_6_DOUBLE_DOOR.value,
                                    expected_floor_6_double_door, err_code)

    def assert_value_and_error(self, param_nr, expected_value, expected_err_code):
        val, err_code = self.tl.get_param(param_nr)
        assert val == expected_value
        assert err_code == expected_err_code

    def test_update_impulse(self):
        """
        Test update_impulse.
        """
        # Try updating impulse without setting progname first.
        val, err_code = self.tl._ThousandLib__update_impulse()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Set progname and try unpacking again.
        self.tl.database[self.tl.params_2.PROG_NAME_2.value].value = "AritcoI"
        val, err_code = self.tl._ThousandLib__update_impulse()
        assert val == '1'
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Set progname to "AritcoH" and verify Hold To Run
        self.tl.database[self.tl.params_2.PROG_NAME_2.value].value = "AritcoH"
        val, err_code = self.tl._ThousandLib__update_impulse()
        assert val == '0'
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Set progname to "AritcoJ" and verify correct error code
        self.tl.database[self.tl.params_2.PROG_NAME_2.value].value = "AritcoJ"
        val, err_code = self.tl._ThousandLib__update_impulse()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.DATA_ERR.name

        # Try unpacking impulse when there is no progname in the database
        del self.tl.database[self.tl.params_2.PROG_NAME_2.value]

        val, err_code = self.tl._ThousandLib__update_impulse()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARAM_NOT_IN_DB.name

    def test_update_temp(self):
        """
        Test update_temp.
        """
        # Try updating temperature value with no latest response
        val, err_code = self.tl._ThousandLib__update_temp(self.tl.params_virtual.TEMP_134.value)
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Test, trying to update temperature value with 500 and getting the right response
        self.tl.latest_responses['134'] = 'dummy'
        self.tl._ThousandLib__unpack_signal = MagicMock(return_value=["500", self.tl.rs232Codes.NO_ERR.name])
        val, err_code = self.tl._ThousandLib__update_temp(self.tl.params_virtual.TEMP_134.value)
        assert val == '5'
        assert err_code == self.tl.rs232Codes.NO_ERR.name

        # Test, trying to update temperature value with -500 and getting the right response
        self.tl._ThousandLib__unpack_signal = MagicMock(return_value=["-500", self.tl.rs232Codes.NO_ERR.name])
        val, err_code = self.tl._ThousandLib__update_temp(self.tl.params_virtual.TEMP_134.value)
        assert val == '-5'
        assert err_code == self.tl.rs232Codes.NO_ERR.name

    def test_update_battery_state(self):
        """
        Test update_battery_state.
        """
        # Try updating battery state with no latest response
        val, err_code = self.tl._ThousandLib__update_battery_state(self.tl.params_virtual.BATTERY_STATE_130.value)
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Try updating with erroneous data in latest response
        self.tl.latest_responses['130'] = ['a']
        val, err_code = self.tl._ThousandLib__update_battery_state(self.tl.params_virtual.BATTERY_STATE_130.value)
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Try updating with unsupported data in latest response
        self.tl.latest_responses['130'] = [11]
        val, err_code = self.tl._ThousandLib__update_battery_state(self.tl.params_virtual.BATTERY_STATE_130.value)
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Try updating with proper data in latest response
        self.tl.latest_responses['130'] = [4]
        val, err_code = self.tl._ThousandLib__update_battery_state(self.tl.params_virtual.BATTERY_STATE_130.value)
        assert val == '3'
        assert err_code == self.tl.rs232Codes.NO_ERR.name

    def test_update_floor_lock(self):
        """
        Test updating the virtual floor lock param
        """
        # Test updating floor lock with no latest response
        val, err_code = self.tl._ThousandLib__update_floor_lock()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Try updating with erroneous data in latest response
        self.tl.latest_responses['130'] = ['a']
        val, err_code = self.tl._ThousandLib__update_floor_lock()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Try updating with unsupported data in latest response
        self.tl.latest_responses['130'] = [11]
        val, err_code = self.tl._ThousandLib__update_floor_lock()
        assert val == '-1'
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        self.tl.database[self.tl.params_130.FLOOR_1_FLOOR_LOCK_130.value].value = "1"
        self.tl.database[self.tl.params_130.FLOOR_2_FLOOR_LOCK_130.value].value = "0"
        self.tl.database[self.tl.params_130.FLOOR_3_FLOOR_LOCK_130.value].value = "1"
        self.tl.database[self.tl.params_130.FLOOR_4_FLOOR_LOCK_130.value].value = "0"
        self.tl.database[self.tl.params_130.FLOOR_5_FLOOR_LOCK_130.value].value = "0"
        self.tl.database[self.tl.params_130.FLOOR_6_FLOOR_LOCK_130.value].value = "1"

        val, err_code = self.tl._ThousandLib__update_floor_lock()
        assert val == str(int("100101", 2))
        assert err_code == self.tl.rs232Codes.NO_ERR.name

    def test_update_virtual_params(self):
        """
        Test update_virtual_signals.
        """
        # Test updating virtual signals without any response
        changed_signals, err_code = self.tl._ThousandLib__update_virtual_signals()
        assert changed_signals == []
        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name

        # Test unpacking 2 supported signals and one unsupported
        package_130_response = [1, 22, 92, 13, 4, 29, 2, 21, 29, 2, 21, 0, 0, 170, 170, 170, 170]
        package_2_response = [151, 5, 52, 39, 152, 5, 52, 39, 65, 114, 105, 116, 99, 111, 32, 72, 0, 0, 0,
                              0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 7, 3, 2]
        package_134_response = [100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                0, 0, 0, 0, 0, 0, 0, 0, 99, 0, 0, 0, 0, 0, 123, 1, 0, 0,
                                123, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]

        # Response for package 130 is needed for BATTERY_STATE and FLOOR_LOCK
        _, _ = self.tl.get_updated_params('130', package_130_response)

        # Update params for package 2. PROGNAME is needed to calculate value of IMPULSE
        _, _ = self.tl.get_updated_params('2', package_2_response)

        # Response for package 134 is needed for TEMP
        _, _ = self.tl.get_updated_params('134', package_134_response)

        # Mock virtual params with unsupported signal
        self.tl.params_virtual = Params1k_virtual_mock
        changed_signals, err_code = self.tl._ThousandLib__update_virtual_signals()
        assert changed_signals == [Params1k_virtual_mock.BATTERY_STATE_130.value,
                                   Params1k_virtual_mock.IMPULSE_130.value,
                                   Params1k_virtual_mock.TEMP_134.value,
                                   Params1k_virtual_mock.FLOOR_LOCK.value]
        assert err_code == self.tl.rs232Codes.PARAM_NOT_IN_DB.name

    def test_get_file_for_param(self):
        """
        Test filename response from get_file_for_param
        Should return proper filename if parameters is such a param, else empty string
        """
        param_numbers_param = [97, 111]
        file_param = '/aritco/param'
        param_numbers_intern = [112, 125]
        file_intern = '/aritco/intern'
        param_numbers_node = [126, 131]
        file_node = '/aritco/node'
        param_numbers_lock = [132, 137]
        file_lock = '/aritco/lock'
        param_numbers_door = [138, 143]
        file_door = '/aritco/door'

        for param in range(0, 200):
            print(param)
            file = self.tl.get_file_for_param(param)
            if param_numbers_param[0] <= param <= param_numbers_param[1]:
                assert file == file_param
            elif param_numbers_intern[0] <= param <= param_numbers_intern[1]:
                assert file == file_intern
            elif param_numbers_node[0] <= param <= param_numbers_node[1]:
                assert file == file_node
            elif param_numbers_lock[0] <= param <= param_numbers_lock[1]:
                assert file == file_lock
            elif param_numbers_door[0] <= param <= param_numbers_door[1]:
                assert file == file_door
            else:
                assert not file

    # ---- door_open_count_recalculate tests ----

    def test_door_open_count_recalculate_normal(self):
        """
        Test normal operation: counters increment, changed signals returned.
        Uses multi-byte values to exercise uint32 little-endian unpacking.
        """
        # 6 uint32 counters packed as little-endian (4 bytes each)
        # Values: 10, 20, 300 (multi-byte), 400 (multi-byte), 50, 60
        # 300 = 0x012C LE: [44, 1, 0, 0]; 400 = 0x0190 LE: [144, 1, 0, 0]
        response = [10,0,0,0, 20,0,0,0, 44,1,0,0, 144,1,0,0, 50,0,0,0, 60,0,0,0]

        changed_signals, err_code = self.tl.door_open_count_recalculate(response)

        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 6

        # All 6 door open count param numbers should be in changed_signals
        for signal in self.tl.params_door_open_count:
            assert signal.value in changed_signals

        # Verify database values
        expected_values = [10, 20, 300, 400, 50, 60]
        for i, signal in enumerate(self.tl.params_door_open_count):
            assert self.tl.database[signal.value].value == expected_values[i]

    def test_door_open_count_recalculate_no_change(self):
        """
        Test that calling twice with same values returns empty changed list on second call.
        """
        response = [10,0,0,0, 20,0,0,0, 30,0,0,0, 40,0,0,0, 50,0,0,0, 60,0,0,0]

        # First call sets the values
        self.tl.door_open_count_recalculate(response)

        # Second call with same response should return no changed signals
        changed_signals, err_code = self.tl.door_open_count_recalculate(response)

        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 0

    def test_door_open_count_recalculate_lift_restart(self):
        """
        Test lift restart detection: when counter resets, previous counters are updated.
        """
        # First call: counters at [100, 200, 300, 400, 500, 600]
        response_1 = [100,0,0,0, 200,0,0,0, 44,1,0,0, 144,1,0,0, 244,1,0,0, 88,2,0,0]
        # 44,1 = 256+44 = 300; 144,1 = 256+144 = 400; 244,1 = 256+244 = 500; 88,2 = 512+88 = 600

        changed_signals, err_code = self.tl.door_open_count_recalculate(response_1)
        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 6

        # Verify totals are [100, 200, 300, 400, 500, 600]
        assert self.tl.total_open_door_counters == [100, 200, 300, 400, 500, 600]

        # Second call: counters reset to [5, 5, 5, 5, 5, 5] (lift restarted)
        response_2 = [5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0]

        changed_signals, err_code = self.tl.door_open_count_recalculate(response_2)
        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 6
        for signal in self.tl.params_door_open_count:
            assert signal.value in changed_signals

        # Restart detected: (5 + 0) < 100 for door 1, etc.
        # previous becomes [100, 200, 300, 400, 500, 600]
        # total becomes [5+100, 5+200, 5+300, 5+400, 5+500, 5+600]
        assert self.tl.previous_open_door_counters == [100, 200, 300, 400, 500, 600]
        assert self.tl.total_open_door_counters == [105, 205, 305, 405, 505, 605]
        assert self.tl.reset_saved_open_door_counter is True

    def test_door_open_count_recalculate_unpack_error(self):
        """
        Test that bad response data returns error code and empty list.
        """
        # Response too short - only 2 bytes, first signal needs 4
        response = [1, 2]

        changed_signals, err_code = self.tl.door_open_count_recalculate(response)

        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name
        assert changed_signals == []

    def test_door_open_count_recalculate_cumulative_after_restart(self):
        """
        Test that counters accumulate correctly after a restart.
        After restart, previous is non-zero so subsequent calls add read_value + previous.
        """
        # First call: counters at [100, 100, 100, 100, 100, 100]
        response_1 = [100,0,0,0, 100,0,0,0, 100,0,0,0, 100,0,0,0, 100,0,0,0, 100,0,0,0]
        self.tl.door_open_count_recalculate(response_1)
        assert self.tl.total_open_door_counters == [100, 100, 100, 100, 100, 100]
        assert self.tl.previous_open_door_counters == [0, 0, 0, 0, 0, 0]

        # Second call: lift restarted, counters reset to [5, 5, 5, 5, 5, 5]
        response_2 = [5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0, 5,0,0,0]
        self.tl.door_open_count_recalculate(response_2)
        assert self.tl.previous_open_door_counters == [100, 100, 100, 100, 100, 100]
        assert self.tl.total_open_door_counters == [105, 105, 105, 105, 105, 105]

        # Third call: counters continue after restart to [20, 20, 20, 20, 20, 20]
        # No restart: (20 + 100) = 120 >= 105
        # total = 20 + 100 = 120
        response_3 = [20,0,0,0, 20,0,0,0, 20,0,0,0, 20,0,0,0, 20,0,0,0, 20,0,0,0]
        changed_signals, err_code = self.tl.door_open_count_recalculate(response_3)
        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 6
        assert self.tl.previous_open_door_counters == [100, 100, 100, 100, 100, 100]
        assert self.tl.total_open_door_counters == [120, 120, 120, 120, 120, 120]

    def test_door_open_count_recalculate_unpack_error_midway(self):
        """
        Test that unpack error on a middle door returns empty list immediately.
        Response is long enough for doors 1-3 (12 bytes) but too short for door 4 (needs byte 15).
        Verifies the early-return behavior and that no partial changed_signals leak.
        """
        response = [10,0,0,0, 20,0,0,0, 30,0,0,0, 40,0]  # 14 bytes, door 4 needs 16

        changed_signals, err_code = self.tl.door_open_count_recalculate(response)

        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name
        assert changed_signals == []

    # ---- update_door_closing_time tests ----

    def test_update_door_closing_time_door_1(self):
        """
        Test valid door closing time for door 1.
        """
        # DOOR_NUMBER=1 (uint16 LE at byte 0-1), DOOR_CLOSING_TIME=500 (uint16 LE at byte 2-3)
        # 500 = 0x01F4, LE: [0xF4, 0x01] = [244, 1]
        response = [1, 0, 244, 1]

        changed_signals, err_code = self.tl.update_door_closing_time(response)

        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals) == 1
        assert changed_signals[0] == self.tl.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value
        assert self.tl.database[self.tl.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value].value == '500'

    def test_update_door_closing_time_all_doors(self):
        """
        Test valid door closing time for each door (1-6).
        """
        from lib.thousand_lib import Params1k_door_closing_time
        door_params = [
            Params1k_door_closing_time.DOOR_1_CLOSING_TIME_135,
            Params1k_door_closing_time.DOOR_2_CLOSING_TIME_135,
            Params1k_door_closing_time.DOOR_3_CLOSING_TIME_135,
            Params1k_door_closing_time.DOOR_4_CLOSING_TIME_135,
            Params1k_door_closing_time.DOOR_5_CLOSING_TIME_135,
            Params1k_door_closing_time.DOOR_6_CLOSING_TIME_135,
        ]
        for door_no in range(1, 7):
            self.tl = ThousandLib()  # Fresh instance per door
            # door_no as uint16 LE, closing time 100 as uint16 LE
            response = [door_no, 0, 100, 0]

            changed_signals, err_code = self.tl.update_door_closing_time(response)

            assert err_code == self.tl.rs232Codes.NO_ERR.name
            assert len(changed_signals) == 1
            assert changed_signals[0] == door_params[door_no - 1].value
            assert self.tl.database[door_params[door_no - 1].value].value == '100'

    def test_update_door_closing_time_invalid_door(self):
        """
        Test that invalid door numbers return DATA_ERR.
        """
        # Door number 0 (off-by-one edge case from hardware)
        response = [0, 0, 100, 0]
        changed_signals, err_code = self.tl.update_door_closing_time(response)
        assert err_code == self.tl.rs232Codes.DATA_ERR.name
        assert changed_signals == []

        # Door number 7 (above valid range)
        response = [7, 0, 100, 0]
        changed_signals, err_code = self.tl.update_door_closing_time(response)
        assert err_code == self.tl.rs232Codes.DATA_ERR.name
        assert changed_signals == []

    def test_update_door_closing_time_duplicate_call(self):
        """
        Test that calling twice with same door/time still returns signal in changed_signals.
        Unlike get_updated_params, update_door_closing_time does not check if the value changed.
        """
        response = [1, 0, 100, 0]

        changed_signals_1, err_code = self.tl.update_door_closing_time(response)
        assert len(changed_signals_1) == 1

        changed_signals_2, err_code = self.tl.update_door_closing_time(response)
        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert len(changed_signals_2) == 1
        assert changed_signals_2[0] == self.tl.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value

    def test_update_door_closing_time_empty_response(self):
        """
        Test that empty response returns empty list with NO_ERR.
        """
        response = []

        changed_signals, err_code = self.tl.update_door_closing_time(response)

        assert err_code == self.tl.rs232Codes.NO_ERR.name
        assert changed_signals == []

    def test_update_door_closing_time_unpack_error_door_number(self):
        """
        Test that unpack error on DOOR_NUMBER returns error.
        """
        # Response too short for DOOR_NUMBER (needs 2 bytes at byte_start=0)
        response = [1]

        changed_signals, err_code = self.tl.update_door_closing_time(response)

        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name
        assert changed_signals == []

    def test_update_door_closing_time_unpack_error_closing_time(self):
        """
        Test that unpack error on DOOR_CLOSING_TIME returns error.
        """
        # Response has enough for DOOR_NUMBER but not for DOOR_CLOSING_TIME
        # DOOR_NUMBER: byte_start=0, byte_size=2 -> needs [0] and [1]
        # DOOR_CLOSING_TIME: byte_start=2, byte_size=2 -> needs [2] and [3]
        response = [1, 0]

        changed_signals, err_code = self.tl.update_door_closing_time(response)

        assert err_code == self.tl.rs232Codes.PARTIAL_ERR.name
        assert changed_signals == []

    # ---- reset methods tests ----

    def test_reset_door_closing_time_params(self):
        """
        Test that reset_door_closing_time_params resets params 155-160 to '0'.
        """
        # Set values first
        for signal in self.tl.params_door_closing_time:
            self.tl.database[signal.value].value = '999'

        self.tl.reset_door_closing_time_params()

        for signal in self.tl.params_door_closing_time:
            assert self.tl.database[signal.value].value == '0'

    def test_reset_door_closing_time_params_fresh_instance(self):
        """
        Test that calling reset on a fresh instance (values are '') does not crash.
        """
        self.tl.reset_door_closing_time_params()

        for signal in self.tl.params_door_closing_time:
            assert self.tl.database[signal.value].value == '0'

    def test_reset_135_params(self):
        """
        Test that reset_135_params resets params -1 and -2 to '0'.
        """
        # Set values first
        for signal in self.tl.params_135:
            self.tl.database[signal.value].value = '42'

        self.tl.reset_135_params()

        for signal in self.tl.params_135:
            assert self.tl.database[signal.value].value == '0'

    def test_reset_135_params_fresh_instance(self):
        """
        Test that calling reset on a fresh instance (values are '') does not crash.
        """
        self.tl.reset_135_params()

        for signal in self.tl.params_135:
            assert self.tl.database[signal.value].value == '0'


def set_up_mocked_database():
    database = dict()
    database[mocked_enum.UINT_TEST.value] = Signal("", "UintTest", 0, 32, 0, 4, 'uint')
    database[mocked_enum.WTIME_TEST.value] = Signal("", "WTimeTest", 0, 32, 4, 4, 'wtime')
    database[mocked_enum.BYTE_TEST.value] = Signal("", "ByteTest", 0, 8, 8, 1, 'byte')
    database[mocked_enum.STRING_TEST.value] = Signal("", "StringTest", 0, 32, 9, 8, 'string')
    database[mocked_enum.TIME_TEST.value] = Signal("", "TimeTest", 0, 32, 17, 4, 'time')
    database[mocked_enum.OBJECT_ID_TEST.value] = Signal("", "GenericTextTest", 0, 0, 21, 30, 'generic_text')

    return database


class Params1k_virtual_mock(Enum):
    NOT_SUPPORTED_SIGNAL = -1
    BATTERY_STATE_130 = 9
    IMPULSE_130 = 57
    TEMP_134 = 92
    FLOOR_LOCK = 152


class mocked_enum(Enum):
    UINT_TEST = 0
    WTIME_TEST = 1
    BYTE_TEST = 2
    STRING_TEST = 3
    TIME_TEST = 4
    OBJECT_ID_TEST = 5
