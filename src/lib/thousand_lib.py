#!/usr/bin/env python

import os
import sys
import time
from enum import Enum
from typing import Any, Type
from _collections_abc import dict_keys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from lib.error_signals import Rs232Code


class ThousandLib:
    """
    Class contains database and functionality for unpacking 1k lift signals.
    """
    def __init__(self) -> None:
        self.name: str = 'ThousandLib'
        self.print = print  # TODO: Remove after adding logging
        self.database: dict = dict()
        self.params_lift_ar: Type[Params1k_lift_AR] = Params1k_lift_AR
        self.params_lift_type: Type[Params1k_lift_type] = Params1k_lift_type
        self.params_lift_name: Type[Params1k_lift_name] = Params1k_lift_name
        self.params_version: Type[Params1k_version] = Params1k_version
        self.params_2: Type[Params1k_2] = Params1k_2
        self.params_130: Type[Params1k_130] = Params1k_130
        self.params_131: Type[Params1k_131] = Params1k_131
        self.params_133: Type[Params1k_133] = Params1k_133
        self.params_134: Type[Params1k_134] = Params1k_134
        self.params_135: Type[Params1k_135] = Params1k_135
        self.params_door_closing_time: Type[Params1k_door_closing_time] = Params1k_door_closing_time
        self.params_virtual: Type[Params1k_virtual] = Params1k_virtual
        self.params_readFile_param: Type[Params1k_readFile_param] = Params1k_readFile_param
        self.params_readFile_intern: Type[Params1k_readFile_intern] = Params1k_readFile_intern
        self.params_readFile_node: Type[Params1k_readFile_node] = Params1k_readFile_node
        self.params_readFile_lock: Type[Params1k_readFile_lock] = Params1k_readFile_lock
        self.params_readFile_door: Type[Params1k_readFile_door] = Params1k_readFile_door
        self.params_vfdResult: Type[Params1k_vfd_data] = Params1k_vfd_data
        self.params_door_open_count: Type[Param1k_door_open_count] = Param1k_door_open_count
        self.latest_responses: dict = dict()
        # Whitespace is not supported CA->Azure. Comma is not supported by signal library.
        # NULL is handled separately.
        self.unsupported_chars: list = [" ", ","]
        self.__init_database()
        self.rs232Codes = Rs232Code
        self.previous_open_door_counters: list = [0] * 6
        self.total_open_door_counters: list = [0] * 6
        self.reset_saved_open_door_counter: bool = True

    def get_param(self, param: int) -> tuple[int, Any]:
        """
        Return a parameter if it exists in the database
        :param: param: parameter number for wanted param
        :return: value of wanted param
        :return: err_code: error code
        """
        try:
            val = self.database[param].value
            if val == "":
                self.print(f"Value for param {param} not set. Has the param been polled? Or is the param empty on U1?")
                return -1, self.rs232Codes.PARAM_NOT_SET.name
        except Exception as e:
            self.print(e)
            return -1, self.rs232Codes.PARAM_NOT_IN_DB.name
        # self.__reset_vfd_motor_param_after_read(param)
        return val, self.rs232Codes.NO_ERR.name

    def get_file_for_param(self, param: int) -> str:
        """
        Return a file for where the specified param can be found
        Creates a list with all param numbers for each enum and then compares arg against list
        """
        readFile_param_params: list = [item.value for item in self.params_readFile_param]
        readFile_intern_params: list = [item.value for item in self.params_readFile_intern]
        readFile_node_params: list = [item.value for item in self.params_readFile_node]
        readFile_lock_params: list = [item.value for item in self.params_readFile_lock]
        readFile_door_params: list = [item.value for item in self.params_readFile_door]

        if param in readFile_param_params:
            return '/aritco/param'
        elif param in readFile_intern_params:
            return '/aritco/intern'
        elif param in readFile_node_params:
            return '/aritco/node'
        elif param in readFile_lock_params:
            return '/aritco/lock'
        elif param in readFile_door_params:
            return '/aritco/door'
        else:
            return ""

    def get_updated_params(self, package_id: str, response: list = []) -> tuple[list, str]:
        """
        Unpack a complete lift response
        :param: package_id: the package to unpack.
        :param: response: complete package response from ARK.
        :return: changed_signals: param_nr for parameter that has update values.
        :return: err_code: Error code
        """
        err_code: str = self.rs232Codes.PACKAGE_NOT_SUPPORTED.name
        changed_signals: list = []
        signals_to_unpack: Any
        if package_id == 'liftRef1':
            signals_to_unpack = self.params_lift_ar
        elif package_id == 'liftRef2':
            signals_to_unpack = self.params_lift_type
        elif package_id == 'liftName':
            signals_to_unpack = self.params_lift_name
        elif package_id == 'version':
            signals_to_unpack = self.params_version
        elif package_id == '131':
            signals_to_unpack = self.params_131
        elif package_id == '130':
            signals_to_unpack = self.params_130
        elif package_id == '2':
            signals_to_unpack = self.params_2
        elif package_id == '133':
            signals_to_unpack = self.params_133
        elif package_id == '134':
            signals_to_unpack = self.params_134
        elif package_id == '135':
            signals_to_unpack = self.params_135
        elif package_id == 'readFileParam':
            signals_to_unpack = self.params_readFile_param
        elif package_id == 'readFileIntern':
            signals_to_unpack = self.params_readFile_intern
        elif package_id == 'readFileNode':
            signals_to_unpack = self.params_readFile_node
        elif package_id == 'readFileLock':
            signals_to_unpack = self.params_readFile_lock
        elif package_id == 'readFileDoor':
            signals_to_unpack = self.params_readFile_door
        elif package_id == 'virtual':
            return self.__update_virtual_signals()
        else:
            return changed_signals, err_code

        err_code = self.rs232Codes.NO_ERR.name

        self.latest_responses[package_id] = response
        for signal_nr in signals_to_unpack:
            latest_val, latest_err_code = self.__unpack_signal(self.database[signal_nr.value], response)

            if latest_err_code != self.rs232Codes.NO_ERR.name:
                err_code = latest_err_code
                continue

            if self.database[signal_nr.value].value != latest_val:
                self.database[signal_nr.value].value = latest_val
                changed_signals.append(signal_nr.value)

        return changed_signals, err_code

    def available_params(self) -> dict_keys[Any, Any]:
        """
        Get list of all available parameters
        :return: lift containing all available params
        """
        return self.database.keys()

    def __update_virtual_signals(self) -> tuple[list, str]:
        """
        Handle all signals that require some special step of unpacking
        :param: signal_nr: Signal to be updated
        :param: latest_raw_val: Latest received value from ARK
        :return: changed_signals: param_nr for parameter that has update values.
        :return: err_code: Error code
        """

        changed_signals: list = []
        err_code: str = self.rs232Codes.NO_ERR.name

        for signal in self.params_virtual:
            if signal.value == self.params_virtual.BATTERY_STATE_130.value:
                new_val, latest_err_code = self.__update_battery_state(signal.value)
            elif signal.value == self.params_virtual.IMPULSE_130.value:
                new_val, latest_err_code = self.__update_impulse()
            elif signal.value == self.params_virtual.TEMP_134.value:
                new_val, latest_err_code = self.__update_temp(signal.value)
            elif signal.value == self.params_virtual.FLOOR_LOCK.value:
                new_val, latest_err_code = self.__update_floor_lock()
            else:
                self.print(f"Error: Virtual signal {signal.name} is not supported.")
                latest_err_code = self.rs232Codes.PARAM_NOT_IN_DB.name

            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.print(f"Error: Failed to unpack signal {signal.name}. Reason: {latest_err_code}")
                err_code = latest_err_code
                continue

            if self.database[signal.value].value != new_val:
                self.database[signal.value].value = new_val
                changed_signals.append(signal.value)

        return changed_signals, err_code

    def door_open_count_recalculate(self, response: list) -> tuple[list, str]:
        """
        unpack response from lift
        calculate if lift has restarted
        """
        i: int = 0

        changed_signals: list = []
        err_code: str = self.rs232Codes.NO_ERR.name
        for signal_nr in self.params_door_open_count:
            read_value, latest_err_code = self.__unpack_signal(self.database[signal_nr.value], response)
            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.print("Error: Faulty when unpacking door open counter")
                return [], latest_err_code

            if (int(read_value) + self.previous_open_door_counters[i]) < self.total_open_door_counters[i]:
                self.previous_open_door_counters[i] = self.total_open_door_counters[i]
                self.reset_saved_open_door_counter = True

            self.total_open_door_counters[i] = int(read_value) + self.previous_open_door_counters[i]

            if self.database[signal_nr.value].value != self.total_open_door_counters[i]:
                self.database[signal_nr.value].value = self.total_open_door_counters[i]
                changed_signals.append(signal_nr.value)

            i += 1
        return changed_signals, err_code


    def reset_door_closing_time_params(self) -> None:
        """
        To reset door closing params after params has been read and sent to cloud
         """
        for signal in self.params_door_closing_time:
            self.database[signal.value].value = '0'

    def reset_135_params(self) -> None:
        """
        To reset params used to unpack 135 pkg
        """
        for signal in self.params_135:
            self.database[signal.value].value = '0'

    def update_door_closing_time(self, response: list) -> tuple[list, str]:
        """
        Unpack and update door closing time parameters
        : param: response : input 135 packag
        : return : changed_signals, err_code : list with updated door closing time signal
        """
        latest_err_code: str = self.rs232Codes.NO_ERR.name
        err_code: str = self.rs232Codes.NO_ERR.name
        changed_signals: list = []
        if len(response) != 0:
            door_no, latest_err_code = self.__unpack_signal(self.database[Params1k_135.DOOR_NUMBER.value], response)
            if latest_err_code != self.rs232Codes.NO_ERR.name:
                print("Error: error when unpack signal Params1k_135.DOOR_NUMBER")
                return [], latest_err_code
            door_time, latest_err_code = self.__unpack_signal(self.database[Params1k_135.DOOR_CLOSING_TIME.value], response)
            if latest_err_code != self.rs232Codes.NO_ERR.name:
                print("Error: error when unpack signal Params1k_135.DOOR_CLOSING_TIME")
                return [], latest_err_code

            if door_no == '1':
                self.database[self.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value
            elif door_no == '2':
                self.database[self.params_door_closing_time.DOOR_2_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_2_CLOSING_TIME_135.value
            elif door_no == '3':
                self.database[self.params_door_closing_time.DOOR_3_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_3_CLOSING_TIME_135.value
            elif door_no == '4':
                self.database[self.params_door_closing_time.DOOR_4_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_4_CLOSING_TIME_135.value
            elif door_no == '5':
                self.database[self.params_door_closing_time.DOOR_5_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_5_CLOSING_TIME_135.value
            elif door_no == '6':
                self.database[self.params_door_closing_time.DOOR_6_CLOSING_TIME_135.value].value = door_time
                signal = self.params_door_closing_time.DOOR_6_CLOSING_TIME_135.value
            else:
                self.print("Error: Invalid door number when setting door closing time")
                err_code = self.rs232Codes.DATA_ERR.name
                return [], err_code

            if signal:
                changed_signals.append(signal)

        return changed_signals, err_code

    def update_vfd_params(self, resp: dict) -> tuple[list, str]:
        """
        Take the vfdResult data and extract motor data into the different motor data parameters
        Para 169 - VFD Motor Current
        Para 170 - VFD Motor Power
        Para 171 - VFD Line Mains Voltage
        Para 172 - VFD Drive Thermal State
        :param: resp json with VFD motor data
        :return: changed_signals (list, error)
        """

        id: int = resp["id"]
        data: str = resp["data"]
        changed_signal: list = []
        err_code: str = self.rs232Codes.NO_ERR.name
        signal_nr: Enum

        # The value shall be unpacked for all four parameters from 'data'
        # when the basis to interpret the data for the is available
        if id == 0:
            signal_nr = self.params_vfdResult.VFD_MOTOR_CURRENT

        elif id == 1:
            signal_nr = self.params_vfdResult.VFD_MOTOR_POWER

        elif id == 2:
            signal_nr = self.params_vfdResult.VFD_LINE_MAINS_VOLTAGE

        elif id == 3:
            signal_nr = self.params_vfdResult.VFD_DRIVE_THERMAL_STATE

        else:
            self.print(f"Error: Invalid or not used VFD ID: {id}")
            return [], self.rs232Codes.VFD_ID_ERR.name

        if signal_nr:
            self.database[signal_nr.value].value = \
                self.__unpack_vfdResult_data(self.database[signal_nr.value], data)
            changed_signal.append(signal_nr.value)
        else:
            self.print("Error: Signal nr is missing")
            return [], self.rs232Codes.VFD_ID_ERR.name

        return changed_signal, err_code

    def __update_floor_lock(self) -> tuple[str, str]:
        """
        Convert the six floor lock params to one floor lock param with the same logic as AHL.
        Bitwise indication for which floor is locked, 1 = locked, 0 = unlocked.
        """
        floor_1_lock:int = self.database[self.params_130.FLOOR_1_FLOOR_LOCK_130.value].value
        floor_2_lock:int = self.database[self.params_130.FLOOR_2_FLOOR_LOCK_130.value].value
        floor_3_lock:int = self.database[self.params_130.FLOOR_3_FLOOR_LOCK_130.value].value
        floor_4_lock:int = self.database[self.params_130.FLOOR_4_FLOOR_LOCK_130.value].value
        floor_5_lock:int = self.database[self.params_130.FLOOR_5_FLOOR_LOCK_130.value].value
        floor_6_lock:int = self.database[self.params_130.FLOOR_6_FLOOR_LOCK_130.value].value

        if None in (floor_1_lock, floor_2_lock, floor_3_lock, floor_4_lock, floor_5_lock, floor_6_lock):
            self.print("Error: One or more of the individual floor lock variables are not set, cannot calculate"
                       "the virtual floor lock variable.")
            return '-1', self.rs232Codes.PARTIAL_ERR.name

        bin_val:str = f"{floor_6_lock}{floor_5_lock}{floor_4_lock}{floor_3_lock}{floor_2_lock}{floor_1_lock}"
        try:
            int_val:int = int(bin_val, 2)
            str_val:str = str(int_val)
        except ValueError as e:
            self.print(e)
            self.print(f"Error: Failed to convert: {bin_val} to integer")
            return '-1', self.rs232Codes.PARTIAL_ERR.name

        return str_val, self.rs232Codes.NO_ERR.name

    def __update_temp(self, signal_nr: int) -> tuple[str, str]:
        """
        Unpacks the virtual Temp signal.
        Update the temp signal to correct value
        :returns: <val>, <error_code>
        """
        try:
            latest_raw, _ = self.__unpack_signal(self.database[signal_nr], self.latest_responses['134'])
        except KeyError as e:
            self.print(e)
            self.print(f"Error: No latest response to use for unpacking signal {self.database[signal_nr]}.")
            return '-1', self.rs232Codes.PARTIAL_ERR.name
        try:
            int_val:int = int(int(latest_raw)/100)
            str_val:str = str(int_val)
        except Exception as e:
            self.print(e)
            self.print("Error: Temp_134.value is missing in database")
            return "-1", self.rs232Codes.PARTIAL_ERR.name

        return str_val, self.rs232Codes.NO_ERR.name

    def __update_impulse(self) -> tuple[str, str]:
        """
        Parse progname and set if Hold to run or Automatic run.
        The value is always stored as the last character.
        :return: <val>, <err_code>
        """
        try:
            if self.database[self.params_2.PROG_NAME_2.value].value != "":
                progname:str = self.database[self.params_2.PROG_NAME_2.value].value
            else:
                return '-1', self.rs232Codes.PARTIAL_ERR.name
        except Exception as e:
            self.print("Error: PROG_NAME_2 missing in database. Cant unpack impulse.")
            self.print(e)
            return '-1', self.rs232Codes.PARAM_NOT_IN_DB.name

        # Hold to run or automatic run is stored in the last character of progname as H or I.
        # Check the last char and return "1" as Automatic Run (I) or "0" as Hold to Run (H)
        if progname[0:7] == "AritcoI":
            return '1', self.rs232Codes.NO_ERR.name
        elif progname[0:7] == "AritcoH":
            return '0', self.rs232Codes.NO_ERR.name
        else:
            return '-1', self.rs232Codes.DATA_ERR.name

    def __update_battery_state(self, signal_nr: int) -> tuple[str, str]:
        """
        Remap battery state from Digisign enum to Aritco enum.
        :return: <val>, <err_code>
        """
        try:
            latest_raw_val, latest_err_code = self.__unpack_signal(self.database[signal_nr],
                                                                   self.latest_responses['130'])
        except KeyError as error:
            self.print(f"Error: No latest response to use for unpacking signal {signal_nr}.")
            self.print(error)
            return '-1', self.rs232Codes.PARTIAL_ERR.name

        val: str
        if latest_err_code == self.rs232Codes.NO_ERR.name:
            if latest_raw_val == '1':
                val = '1'
            elif latest_raw_val in ['2', '3']:
                val = '2'
            elif latest_raw_val == '4':
                val = '3'
            elif latest_raw_val in ['5', '6', '7']:
                val = '4'
            else:
                return '-1', self.rs232Codes.PARTIAL_ERR.name
            return val, latest_err_code
        else:
            return '-1', self.rs232Codes.PARTIAL_ERR.name

    def __unpack_signal(self, signal: Any, response: list) -> tuple[str, str]:
        """
        Unpack signals depending on signal_type
        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: unpacked signal
        :return: err_code: Error code
        """
        unpacked_val: int = -1
        unpacked_as_str: str = str(unpacked_val)

        if 'generic_text' not in signal.signal_type:
            try:
                self.__validate_bytes(signal, response)
            except Exception as e:
                self.print(e)
                return unpacked_as_str, self.rs232Codes.PARTIAL_ERR.name

        if signal.signal_type == 'uint':
            unpacked_val = self.__unpack_uint(signal, response)
            unpacked_as_str = str(unpacked_val)

        elif signal.signal_type == 'wtime':
            unpacked_val = self.__unpack_weekly_timer(signal, response)
            unpacked_as_str = str(unpacked_val)

        elif signal.signal_type == 'byte':
            unpacked_val = self.__unpack_byte(signal, response)
            unpacked_as_str = str(unpacked_val)

        elif signal.signal_type == 'string':
            unpacked_as_str = self.__unpack_string(signal, response)

        elif signal.signal_type == 'time':
            unpacked_val = self.__unpack_as_epoch_time(signal, response)
            unpacked_as_str = str(unpacked_val)

        elif 'generic_text' in signal.signal_type:
            unpacked_as_str = self.__unpack_generic_text(signal, response)

        else:
            self.print(f"Signal type not supported: {signal.signal_type}.")
            return unpacked_as_str, self.rs232Codes.PARTIAL_ERR.name

        return unpacked_as_str, self.rs232Codes.NO_ERR.name

    def __validate_bytes(self, signal: Any, response: list) -> None:
        """
        Validate response from serial buffer.
        Validates that the required number of bytes exists in response.
        Validates that no nonsense data has been received as response.
        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: true if ok, otherwise error
        """
        try:
            for i in range(int(signal.byte_start), int(signal.byte_start+signal.byte_size)):
                byte:str = response[i]
                byte_as_int:int = int(byte)
                if not 0 <= byte_as_int <= 255:
                    raise ValueError
        except IndexError as e:
            # Don't print error messages when new GW tries to read data not part of the ARGate response
            raise IndexError()
        except ValueError as e:
            self.print(e)
            raise ValueError("Bad data received on serial bus?")

    @staticmethod
    def __unpack_uint(signal: Any, response: list) -> int:
        """
        Unpack uint32 packed as little endian.

        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: data_out: unpacked value
        """
        data_out:int = 0
        for i in range(signal.byte_size-1, -1, -1):
            data_out = data_out << 8
            data_out = data_out | response[signal.byte_start+i]
        return data_out

    def __unpack_weekly_timer(self, signal: Any, response: list) -> int:
        """
        Unpack signals that are set as max seconds in a week (60*60*24*7) and ticks down.
        A value of (max_time - unpacked_time) = 20 means that the alarm occurred 20 seconds ago

        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: unpacked_time: epoch time - time when the last alarm occurred
        """
        unpacked_time:int = self.__unpack_uint(signal, response)
        max_time:int = 60*60*24*7
        if not unpacked_time == 0:
            unpacked_time = int(time.time()) - (max_time - unpacked_time)
        return unpacked_time

    @staticmethod
    def __unpack_byte(signal: Any, response: list) -> int:
        """
        Unpack signals of size 8 bits or fewer.

        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: data_out: unpacked_data
        """
        data_out:int = response[signal.byte_start]
        data_out = data_out >> signal.bit_start
        data_out = data_out & (pow(2, signal.bit_size)-1)
        return data_out

    def __unpack_string(self, signal: Any, response: list) -> str:
        """
        Unpack a list of bytes packed as ascii and returns a string of chars.
        Breaks at NULL and ignores other unsupported characters.

        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: data_out: string as chars
        """
        data_out:str = ""
        for i in range(0, signal.byte_size):
            # Assume string ends with NULL
            if response[signal.byte_start+i] == 0:
                break
            unpacked_char:str = chr(response[signal.byte_start+i])
            # Ignore unsupported characters
            if unpacked_char not in self.unsupported_chars:
                data_out += unpacked_char
        return data_out

    def __unpack_generic_text(self, signal: Any, response: list) -> str:
        """
        Unpack a number that can be byte_size long and return as a string.
        Breaks at NULL
        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: data_out: string
        """
        generic_text: str
        if len(response[signal.byte_start]) >= signal.byte_size:
            self.print("The generic texts number's length was above what is supported (how)?")
            self.print(f"Original text: {response[signal.byte_start]},"
                       f"new text: {response[signal.byte_start][:signal.byte_size-1]}")
            generic_text = response[signal.byte_start][:signal.byte_size-1]
        else:
            generic_text = response[signal.byte_start]

        if ',' in generic_text or '_' in generic_text:
            self.print("Commas, underscores not supported in generic texts, replacing with spaces.")
            generic_text = generic_text.replace(',', ' ')
            generic_text = generic_text.replace('_', ' ')
        return generic_text

    def __unpack_as_epoch_time(self, signal: Any, response: list) -> int:
        """
        Unpack a signal containing seconds since 2001-01-01 and return epoch time (not accounting for leap seconds).

        Max value received from the lift is max of uint32. I.e unpack_as_epoch_time can potentially return
        a value greater than the max value of uint32. This causes no problem since the value is packed as a string
        before being sent to CA.

        :param: signal: the signal to unpack.
        :param: response: complete package response from ARK.
        :return: data_out: epoch time
        """
        s_1970_to_2001:int = 978307200
        s_since_2001:int = self.__unpack_uint(signal, response)
        data_out:int = s_1970_to_2001+s_since_2001
        return data_out

    def __unpack_vfdResult_data(self, signal: Any, data: str) -> int:
        """
        Unpack a signal containing response data from vfd
        Result from vfdResult is sent as big endian
        """
        data_list:list = data.split(",")
        data_out:int = 0
        for i in range(signal.byte_start-1, signal.byte_start+signal.byte_size-1):
            data_out = data_out << 8
            data_out = data_out | int(data_list[i], 16)

        return data_out

    def __init_database(self) -> None:
        """
        Set the complete protocol for the 1k series.
        """
        try:
            # Signal(value, name, bit_start, bit_size, byte_start, byte_size, signal_type)
            self.database[self.params_lift_ar.AR_NUMBER.value] = Signal("", "AR_number", 0, 0, 0, 39, 'generic_text_ar_number')
            self.database[self.params_lift_type.LIFT_TYPE.value] = Signal("", "LiftType", 0, 0, 0, 39, 'generic_text_lift_type')
            self.database[self.params_2.FILE_DATE_2.value] = Signal("", "FileDate", 0, 32, 0, 4, 'time')
            self.database[self.params_2.PROG_DATE_2.value] = Signal("", "ProgDate", 0, 32, 4, 4, 'time')
            self.database[self.params_2.PROG_NAME_2.value] = Signal("", "ProgName", 0, 8*20, 8, 20, 'string')
            self.database[self.params_2.MAIN_VERSION_2.value] = Signal("", "MainVersion", 0, 8, 28, 1, 'byte')
            self.database[self.params_2.SUB_VERSION_2.value] = Signal("", "SubVersion", 0, 8, 29, 1, 'byte')
            self.database[self.params_2.OS_VERSION_2.value] = Signal("", "OSVersion", 0, 8, 30, 1, 'byte')
            self.database[self.params_2.HW_VERSION_2.value] = Signal("", "HardwareVersion", 0, 8, 31, 1, 'byte')
            # self.database[self.params_130.BATTERY_STATE_130.value] = Signal("", "BatteryState", 0, 4, 0, 1, 'byte')

            self.database[self.params_virtual.BATTERY_STATE_130.value] = Signal("", "BatteryState", 0, 4, 0, 1, 'byte')

            self.database[self.params_130.OIL_LEVEL_130.value] = Signal("", "OilLevel", 0, 8, 2, 1, 'byte')
            self.database[self.params_130.SAFETY_130.value] = Signal("", "Safety", 4, 4, 0, 1, 'byte')
            self.database[self.params_130.FLOOR_130.value] = Signal("", "Floor", 0, 8, 1, 1, 'byte')
            self.database[self.params_130.LOAD_CURRENT_130.value] = Signal("", "LoadCurrent", 0, 8, 3, 1, 'byte')
            self.database[self.params_130.NO_NODES_130.value] = Signal("", "NoNodes", 0, 4, 4, 1, 'byte')
            self.database[self.params_130.FLOOR_1_FIRE_130.value] = Signal("", "Floor1Fire", 0, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_1_CABIN_130.value] = Signal("", "Floor1Cabin", 1, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_1_SHAFT_130.value] = Signal("", "Floor1Shaft", 2, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_1_LOCK_130.value] = Signal("", "Floor1Lock", 3, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_1_INPUT_130.value] = Signal("", "Floor1Input", 4, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_1_FLOOR_LOCK_130.value] = Signal("", "Floor1FloorLock", 5, 1, 5, 1, 'byte')
            self.database[self.params_130.FLOOR_2_FIRE_130.value] = Signal("", "Floor2Fire", 0, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_2_CABIN_130.value] = Signal("", "Floor2Cabin", 1, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_2_SHAFT_130.value] = Signal("", "Floor2Shaft", 2, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_2_LOCK_130.value] = Signal("", "Floor2Lock", 3, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_2_INPUT_130.value] = Signal("", "Floor2Input", 4, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_2_FLOOR_LOCK_130.value] = Signal("", "Floor2FloorLock", 5, 1, 6, 1, 'byte')
            self.database[self.params_130.FLOOR_3_FIRE_130.value] = Signal("", "Floor3Fire", 0, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_3_CABIN_130.value] = Signal("", "Floor3Cabin", 1, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_3_SHAFT_130.value] = Signal("", "Floor3Shaft", 2, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_3_LOCK_130.value] = Signal("", "Floor3Lock", 3, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_3_INPUT_130.value] = Signal("", "Floor3Input", 4, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_3_FLOOR_LOCK_130.value] = Signal("", "Floor3FloorLock", 5, 1, 7, 1, 'byte')
            self.database[self.params_130.FLOOR_4_FIRE_130.value] = Signal("", "Floor4Fire", 0, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_4_CABIN_130.value] = Signal("", "Floor4Cabin", 1, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_4_SHAFT_130.value] = Signal("", "Floor4Shaft", 2, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_4_LOCK_130.value] = Signal("", "Floor4Lock", 3, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_4_INPUT_130.value] = Signal("", "Floor4Input", 4, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_4_FLOOR_LOCK_130.value] = Signal("", "Floor4FloorLock", 5, 1, 8, 1, 'byte')
            self.database[self.params_130.FLOOR_5_FIRE_130.value] = Signal("", "Floor5Fire", 0, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_5_CABIN_130.value] = Signal("", "Floor5Cabin", 1, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_5_SHAFT_130.value] = Signal("", "Floor5Shaft", 2, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_5_LOCK_130.value] = Signal("", "Floor5Lock", 3, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_5_INPUT_130.value] = Signal("", "Floor5Input", 4, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_5_FLOOR_LOCK_130.value] = Signal("", "Floor5FloorLock", 5, 1, 9, 1, 'byte')
            self.database[self.params_130.FLOOR_6_FIRE_130.value] = Signal("", "Floor6Fire", 0, 1, 10, 1, 'byte')
            self.database[self.params_130.FLOOR_6_CABIN_130.value] = Signal("", "Floor6Cabin", 1, 1, 10, 1, 'byte')
            self.database[self.params_130.FLOOR_6_SHAFT_130.value] = Signal("", "Floor6Shaft", 2, 1, 10, 1, 'byte')
            self.database[self.params_130.FLOOR_6_LOCK_130.value] = Signal("", "Floor6Lock", 3, 1, 10, 1, 'byte')
            self.database[self.params_130.FLOOR_6_INPUT_130.value] = Signal("", "Floor6Input", 4, 1, 10, 1, 'byte')
            self.database[self.params_130.FLOOR_6_FLOOR_LOCK_130.value] = Signal("", "Floor6FloorLock", 5, 1, 10, 1, 'byte')
            self.database[self.params_130.HAS_PUMP_130.value] = Signal("", "HasPump", 0, 1, 13, 1, 'byte')
            self.database[self.params_130.POWER_IN_130.value] = Signal("", "PowerIn", 1, 1, 13, 1, 'byte')
            self.database[self.params_130.DOOR_NOT_OPEN_130.value] = Signal("", "DoorNotOpen", 2, 1, 13, 1, 'byte')
            # self.database[self.params_130.DOOR_OPENER_130.value] = Signal("", "DoorOpener", 3, 1, 13, 1, 'byte')
            self.database[self.params_130.ALARM_ACTIVE_130.value] = Signal("", "AlarmActive", 4, 1, 13, 1, 'byte')
            self.database[self.params_130.LIFT_LOCKED_130.value] = Signal("", "LiftLocked", 5, 1, 13, 1, 'byte')
            self.database[self.params_130.DOOR_OPEN_1MIN_130.value] = Signal("", "DoorOpen1min", 6, 1, 13, 1, 'byte')
            self.database[self.params_130.CONTACTOR_STUCK_130.value] = Signal("", "ContactorStuck", 7, 1, 13, 1, 'byte')
            # self.database[self.params_130.CONTACTOR_CHECK_130.value] = Signal("", "ContactorCheck", 0, 1, 15, 1, 'byte')
            # self.database[self.params_130.FRICTION_TEST_130.value] = Signal("", "FrictionTest", 1, 1, 15, 1, 'byte')
            self.database[self.params_130.BATT_MISSING_130.value] = Signal("", "BatteryMissing", 2, 1, 14, 1, 'byte')
            self.database[self.params_130.BATT_CHANGE_130.value] = Signal("", "BatteryChange", 3, 1, 14, 1, 'byte')
            self.database[self.params_130.BATT_BAD_130.value] = Signal("", "BatteryBad", 4, 1, 14, 1, 'byte')
            self.database[self.params_130.BATT_CHARGER_ERR_130.value] = Signal("", "BatteryChargerError", 5, 1, 14, 1, 'byte')
            self.database[self.params_130.CABIN_LIFT_130.value] = Signal("", "CabinLift", 6, 1, 14, 1, 'byte')
            # self.database[self.params_130.B_LIFT.value] = Signal("", "BLift", 7, 1, 15, 1, 'byte') Same as B_lift in "intern" file
            # self.database[self.params_130.IMPULSE_130.value] = Signal("", "Impulse", 0, 1, 15, 1, 'byte') Same as "impuls_cabin" in "param" file

            self.database[self.params_virtual.IMPULSE_130.value] = Signal("", "Impulse", 0, 1, 15, 1, 'byte')

            self.database[self.params_130.EMERG_FAIL_130.value] = Signal("", "EmergencyFail", 1, 1, 15, 1, 'byte')
            self.database[self.params_130.LIFT_NEEDS_SERVICE_130.value] = Signal("", "LiftNeedsService", 2, 1, 15, 1, 'byte')
            self.database[self.params_130.OVER_CURRENT_130.value] = Signal("", "OverCurrent", 3, 1, 15, 1, 'byte')
            self.database[self.params_130.REDUCE_LIGHT_130.value] = Signal("", "ReduceLight", 4, 1, 15, 1, 'byte')
            # self.database[self.params_130.PHOTO_CELL_130.value] = Signal("", "PhotoCell", 5, 1, 16, 1, 'byte')
            self.database[self.params_130.RUN_TIME_130.value] = Signal("", "RunTime", 6, 1, 15, 1, 'byte')
            self.database[self.params_130.FIRE_130.value] = Signal("", "Fire", 7, 1, 15, 1, 'byte')
            self.database[self.params_130.PLUG_23_130.value] = Signal("", "Plug23", 0, 1, 16, 1, 'byte')
            self.database[self.params_130.OVER_LOAD_130.value] = Signal("", "Overload", 1, 1, 16, 1, 'byte')
            # self.database[self.params_130.OIL_OUT_ON_130.value] = Signal("", "OilOutOn", 2, 1, 16, 1, 'byte')
            # self.database[self.params_130.BUSY_TIMER_130.value] = Signal("", "BusyTimer", 3, 1, 16, 1, 'byte')
            # self.database[self.params_130.BUSY_CABIN_130.value] = Signal("", "BusyTimer", 4, 1, 16, 1, 'byte')
            self.database[self.params_130.CHILD_LOCK_130.value] = Signal("", "ChildLock", 5, 1, 16, 1, 'byte')
            self.database[self.params_130.BATTERY_TESTING_130.value] = Signal("", "BatteryTest", 6, 1, 16, 1, 'byte')
            self.database[self.params_130.BATTERY_TEST_SUSPENDED_130.value] = Signal("", "BattTestSus", 7, 1, 16, 1, 'byte')
            self.database[self.params_virtual.FLOOR_LOCK.value] = Signal("", "FloorLock", 0, 0, 0, 0, 'byte')

            self.database[self.params_134.TOTAL_STARTS.value] = Signal("", "TotalStarts", 0, 32, 32, 4, 'uint')
            self.database[self.params_134.TOTAL_RUN_TIME.value] = Signal("", "TotalRuntime", 0, 32, 36, 4, 'uint')

            self.database[self.params_131.DOOR_IN_RUN.value] = Signal("", "DoorInRun", 0, 32, 0, 4, 'wtime')
            self.database[self.params_131.LOCK_IN_RUN.value] = Signal("", "LockInRun", 0, 32, 4, 4, 'wtime')
            self.database[self.params_131.FLOOR_1_DUBBEL.value] = Signal("", "Floor1Dubbel", 0, 32, 8, 4, 'wtime')
            self.database[self.params_131.FLOOR_X_DUBBEL.value] = Signal("", "FloorXDubbel", 0, 32, 12, 4, 'wtime')
            self.database[self.params_131.FLOOR_TOP_DUBBEL.value] = Signal("", "FloorTopDubbel", 0, 32, 16, 4, 'wtime')
            self.database[self.params_131.STEP_FAIL.value] = Signal("", "StepFail", 0, 32, 20, 4, 'wtime')
            self.database[self.params_131.BATTERY_BAD.value] = Signal("", "BatteryBad", 0, 32, 24, 4, 'wtime')
            self.database[self.params_131.BATTERY_MISSING.value] = Signal("", "BatteryMissing", 0, 32, 28, 4, 'wtime')
            self.database[self.params_131.EMERG_LIGHT.value] = Signal("", "EmergLight", 0, 32, 32, 4, 'wtime')
            self.database[self.params_131.OVERLOAD_24V.value] = Signal("", "24vOverload", 0, 32, 36, 4, 'wtime')
            self.database[self.params_131.DOOR_OPEN_1_MIN.value] = Signal("", "DoorOpen1Min", 0, 32, 40, 4, 'wtime')
            self.database[self.params_131.CHECK_CONTACTOR.value] = Signal("", "ContactorCheck", 0, 32, 44, 4, 'wtime')
            self.database[self.params_131.SHAFT_UNIT_GONE.value] = Signal("", "ShaftUnitGone", 0, 32, 48, 4, 'wtime')
            self.database[self.params_131.BATT_TEST_FAIL.value] = Signal("", "BattTestFail", 0, 32, 52, 4, 'wtime')
            self.database[self.params_131.BATT_CHARGE_FAIL.value] = Signal("", "BattChargeFail", 0, 32, 56, 4, 'wtime')
            self.database[self.params_131.FIRE_BLOCK.value] = Signal("", "FireBlock", 0, 32, 60, 4, 'wtime')
            self.database[self.params_131.TEST_FRICTION.value] = Signal("", "FrictionTest", 0, 32, 64, 4, 'wtime')
            self.database[self.params_131.VPLUG23_14V.value] = Signal("", "Vplug23-14V", 0, 32, 68, 4, 'wtime')
            self.database[self.params_131.LOCK_FLOOR.value] = Signal("", "LockFloor", 0, 32, 80, 4, 'wtime')
            self.database[self.params_131.RUN_TIMEOUT.value] = Signal("", "RunTimeout", 0, 32, 84, 4, 'wtime')
            self.database[self.params_131.OIL_SHORT_CIRCUIT.value] = Signal("", "OilShortCircuit", 0, 32, 88, 4, 'wtime')
            self.database[self.params_131.BATT_FUSE.value] = Signal("", "BattFuse", 0, 32, 92, 4, 'wtime')
            self.database[self.params_131.PLATFORM_SAFETY.value] = Signal("", "PlatformSafety", 0, 32, 96, 4, 'wtime')

            # self.database[self.params_133.BATT_STATUS.value] = Signal("", "BatteryStatus", 0, 8, 0, 1,'byte')
            # self.database[self.params_133.BATT_PROGRESS.value] = Signal("", "BatteryProgress", 0, 8, 1, 1,'byte')
            # self.database[self.params_133.CHARGE_LOAD.value] = Signal("", "ChargeLoad", 0, 8, 2, 1,'byte')
            # self.database[self.params_133.TEST_MODE.value] = Signal("", "TestMode", 0, 1, 3, 1,'byte')
            self.database[self.params_133.BATTERY_VOLTAGE.value] = Signal("", "BatteryVoltage", 0, 16, 4, 2,'uint')
            self.database[self.params_133.BATTERY_CAPACITY.value] = Signal("", "BatteryCapacity", 0, 16, 6, 2,'uint')
            # self.database[self.params_133.BATTERY_TIME.value] = Signal("", "BatteryTime", 0, 16, 8, 2,'uint')
            # self.database[self.params_133.BATTERY_RESISTANCE.value] = Signal("", "BatteryResistance", 0, 16, 10, 2,'uint')
            self.database[self.params_133.BATTERY_CURRENT.value] = Signal("", "BatteryCurrent", 0, 16, 12, 2,'uint')
            # self.database[self.params_133.NEXT_TIME_TO_TEST_BATTERT.value] = Signal("", "NextBatteryTest", 0, 32, 14, 4,'uint')

            self.database[self.params_134.CURRENT.value] = Signal("", "Current", 0, 16, 0, 2, 'uint')
            # self.database[self.params_134.LOAD] = Signal("", "Load", 0, 16, 2, 2,'uint')
            # self.database[self.params_134.SAFE_OUT] = Signal("", "SafeOut", 0, 16, 4, 2,'uint')
            # self.database[self.params_134.SAFE_PLATFORM] = Signal("", "SafePlatform", 0, 16, 6, 2,'uint')
            # self.database[self.params_134.SAFE_DOOR] = Signal("", "SafeDoor", 0, 16, 8, 2,'uint')
            # self.database[self.params_134.SAFE_LOCK] = Signal("", "SafeLock", 0, 16, 10, 2,'uint')
            # self.database[self.params_134.POWER_IN] = Signal("", "PowerIn", 0, 16, 12, 2,'uint')
            # self.database[self.params_134.V_IN] = Signal("", "VIn", 0, 16, 14, 2,'uint')
            # self.database[self.params_134.V_OUT] = Signal("", "Vout", 0, 16, 16, 2,'uint')
            # self.database[self.params_134.RIPPLE] = Signal("", "Ripple", 0, 16, 18, 2,'uint')
            # self.database[self.params_134.BATT_OUT] = Signal("", "BattOut", 0, 16, 20, 2,'uint')
            # self.database[self.params_134.PLUG_23] = Signal("", "Plug23", 0, 16, 22, 2,'uint')
            # self.database[self.params_134.RELAY_SENSE] = Signal("", "RelaySense", 0, 16, 24, 2,'uint')
            # self.database[self.params_134.TEMP.value] = Signal("", "Temp", 0, 16, 26, 2,'uint')
            # self.database[self.params_134.SYSTEM_UP_TIMER] = Signal("", "SystemUpTimer", 0, 32, 28, 4,'uint')
            # self.database[self.params_134.TRIP_START] = Signal("", "TripStart", 0, 32, 40, 4,'uint')
            # self.database[self.params_134.TRIP_RUN_TIME] = Signal("", "TripRunTime", 0, 32, 44, 4,'uint')
            self.database[self.params_virtual.TEMP_134.value] = Signal("", "Temp", 0, 16, 26, 2, 'uint')

            self.database[self.params_135.DOOR_NUMBER.value] = Signal("", "DoorNumber", 0, 16, 0, 2, 'uint')
            self.database[self.params_135.DOOR_CLOSING_TIME.value] = Signal("", "DoorClosingTime", 0, 16, 2, 2, 'uint')

            self.database[self.params_door_closing_time.DOOR_1_CLOSING_TIME_135.value] = Signal("", "Door1ClosingTime", 0, 0, 0,0,'uint')
            self.database[self.params_door_closing_time.DOOR_2_CLOSING_TIME_135.value] = Signal("", "Door2ClosingTime", 0, 0, 0,0,'uint')
            self.database[self.params_door_closing_time.DOOR_3_CLOSING_TIME_135.value] = Signal("", "Door3ClosingTime", 0, 0, 0,0,'uint')
            self.database[self.params_door_closing_time.DOOR_4_CLOSING_TIME_135.value] = Signal("", "Door4ClosingTime", 0, 0, 0,0,'uint')
            self.database[self.params_door_closing_time.DOOR_5_CLOSING_TIME_135.value] = Signal("", "Door5ClosingTime", 0, 0, 0,0,'uint')
            self.database[self.params_door_closing_time.DOOR_6_CLOSING_TIME_135.value] = Signal("", "Door6ClosingTime", 0, 0, 0,0,'uint')

            self.database[self.params_version.ARGATE_MAIN_VERSION.value] = Signal("", "ArMainVersion", 0, 8, 0, 1, 'byte')
            self.database[self.params_version.ARGATE_SUB_VERSION.value] = Signal("", "ArSubVersion", 0, 8, 1, 1, 'byte')
            self.database[self.params_version.ARGATE_HW_VERSION.value] = Signal("", "ArHwVersion", 0, 8, 2, 1, 'byte')
            self.database[self.params_version.ARGATE_OP_VERSION.value] = Signal("", "ArOpVersion", 0, 8, 3, 1, 'byte')
            self.database[self.params_version.ARGATE_MIN_VERSION.value] = Signal("", "ArMinVersion", 0, 8, 4, 1, 'byte')
            self.database[self.params_version.ARGATE_BETA_VERSION.value] = Signal("", "ArBetaVersion", 0, 8, 5, 1,'byte')
            self.database[self.params_version.U19_HW_VERSION.value] = Signal("", "U19HwVersion", 0, 8, 6, 1, 'byte')
            self.database[self.params_version.U19_OP_VERSION.value] = Signal("", "U19OpVersion", 0, 8, 7, 1, 'byte')
            self.database[self.params_version.U19_MAIN_VERSION.value] = Signal("", "U19MainVersion", 0, 8, 8, 1, 'byte')
            self.database[self.params_version.U19_SUB_VERSION.value] = Signal("", "U19SubVersion", 0, 8, 9, 1, 'byte')
            self.database[self.params_version.U19_MIN_VERSION.value] = Signal("", "U19MinVersion", 0, 8, 10, 1, 'byte')
            self.database[self.params_version.U19_BETA_VERSION.value] = Signal("", "U19BetaVersion", 0, 8, 11, 1,'byte')

            self.database[self.params_readFile_param.DOOR_TIME.value] = Signal("", "DoorTime", 0, 16, 0, 2, 'uint')
            self.database[self.params_readFile_param.CABIN_LIGHT.value] = Signal("", "CabinLight", 0, 16, 2, 2, 'uint')
            self.database[self.params_readFile_param.ALARM_TIME.value] = Signal("", "AlarmTime", 0, 16, 4, 2, 'uint')
            self.database[self.params_readFile_param.CLOSE_CALL_DELAY.value] = Signal("", "CloseCallDelay", 0, 16, 6, 2, 'uint')
            self.database[self.params_readFile_param.DOOR_OPEN_DELAY.value] = Signal("", "DoorOpenDelay", 0, 16, 8, 2, 'uint')
            self.database[self.params_readFile_param.FIRE_FLOOR.value] = Signal("", "FireFloor", 0, 16, 10, 2, 'uint')
            self.database[self.params_readFile_param.RETURN_FLOOR.value] = Signal("", "ReturnFloor", 0, 16, 12, 2, 'uint')
            self.database[self.params_readFile_param.RETURN_TIME.value] = Signal("", "ReturnTime", 0, 16, 14, 2, 'uint')
            self.database[self.params_readFile_param.VALVE_INTENSITY.value] = Signal("", "ValveIntensity", 0, 16, 16, 2, 'uint')
            self.database[self.params_readFile_param.IMPULSE_CABIN.value] = Signal("", "ImpulseCabin", 0, 16, 18, 2, 'uint')
            self.database[self.params_readFile_param.BEEP_PLATFORM.value] = Signal("", "BeepPlatform", 0, 16, 20, 2, 'uint')
            self.database[self.params_readFile_param.BEEP_ARRIVAL.value] = Signal("", "BeepArrival", 0, 16, 22, 2, 'uint')
            self.database[self.params_readFile_param.BATT_TEST_USE_EMERGENCY.value] = Signal("", "BattTestUseEmergency", 0, 16, 24, 2, 'uint')
            self.database[self.params_readFile_param.DOOR_LOCK_TIME.value] = Signal("", "DoorLockTime", 0, 16, 26, 2, 'uint')
            self.database[self.params_readFile_param.PUMP_INTENSITY.value] = Signal("", "PumpIntensity", 0, 16, 28, 2, 'uint')

            self.database[self.params_readFile_intern.FREQ_CONTROL.value] = Signal("", "FreqControl", 0, 16, 0, 2, 'uint')
            self.database[self.params_readFile_intern.IMPULSE_AVAILABLE.value] = Signal("", "ImpulseAvailable", 0, 16, 2, 2, 'uint')
            self.database[self.params_readFile_intern.LOCK_INVERT.value] = Signal("", "LockInvert", 0, 16, 4, 2, 'uint')
            self.database[self.params_readFile_intern.OIL_MODE.value] = Signal("", "OilMode", 0, 16, 6, 2, 'uint')
            self.database[self.params_readFile_intern.NODE_DIRECTION.value] = Signal("", "NodeDirection", 0, 16, 8, 2, 'uint')
            self.database[self.params_readFile_intern.BOTTLE_VOLUME.value] = Signal("", "BottleVolume", 0, 16, 10, 2, 'uint')
            self.database[self.params_readFile_intern.EMERGENCY_DELAY.value] = Signal("", "EmergencyDelay", 0, 16, 12, 2, 'uint')
            self.database[self.params_readFile_intern.B_LIFT.value] = Signal("", "BLift", 0, 16, 14, 2, 'uint')
            self.database[self.params_readFile_intern.COMMON_LIGHT.value] = Signal("", "CommonLight", 0, 16, 16, 2, 'uint')
            self.database[self.params_readFile_intern.AUTO_LOCK_MENU.value] = Signal("", "AutoLockMenu", 0, 16, 18, 2, 'uint')
            self.database[self.params_readFile_intern.BATT_CAPACITY.value] = Signal("", "BatteryCapacity", 0, 16, 20, 2, 'uint')
            self.database[self.params_readFile_intern.PUMP_CAPACITY.value] = Signal("", "PumpCapacity", 0, 16, 22, 2, 'uint')
            self.database[self.params_readFile_intern.AR_BUS_EXT.value] = Signal("", "ARBusExtended", 0, 16, 24, 2, 'uint')
            self.database[self.params_readFile_intern.EMERGENCY_LIGHT_TEST.value] = Signal("", "EmergencyLightTest", 0, 16, 26, 2, 'uint')

            self.database[self.params_readFile_node.FLOOR_1_NODE.value] = Signal("", "Floor1Node", 0, 16, 0, 2, 'uint')
            self.database[self.params_readFile_node.FLOOR_2_NODE.value] = Signal("", "Floor2Node", 0, 16, 2, 2, 'uint')
            self.database[self.params_readFile_node.FLOOR_3_NODE.value] = Signal("", "Floor3Node", 0, 16, 4, 2, 'uint')
            self.database[self.params_readFile_node.FLOOR_4_NODE.value] = Signal("", "Floor4Node", 0, 16, 6, 2, 'uint')
            self.database[self.params_readFile_node.FLOOR_5_NODE.value] = Signal("", "Floor5Node", 0, 16, 8, 2, 'uint')
            self.database[self.params_readFile_node.FLOOR_6_NODE.value] = Signal("", "Floor6Node", 0, 16, 10, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_1_LOCK.value] = Signal("", "Floor1Lock", 0, 16, 0, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_2_LOCK.value] = Signal("", "Floor2Lock", 0, 16, 2, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_3_LOCK.value] = Signal("", "Floor3Lock", 0, 16, 4, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_4_LOCK.value] = Signal("", "Floor4Lock", 0, 16, 6, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_5_LOCK.value] = Signal("", "Floor5Lock", 0, 16, 8, 2, 'uint')
            self.database[self.params_readFile_lock.FLOOR_6_LOCK.value] = Signal("", "Floor6Lock", 0, 16, 10, 2, 'uint')

            self.database[self.params_readFile_door.FLOOR_1_DOUBLE_DOOR.value] = Signal("", "Floor1DoubleDoor", 0, 16, 0, 2, 'uint')
            self.database[self.params_readFile_door.FLOOR_2_DOUBLE_DOOR.value] = Signal("", "Floor2DoubleDoor", 0, 16, 2, 2, 'uint')
            self.database[self.params_readFile_door.FLOOR_3_DOUBLE_DOOR.value] = Signal("", "Floor3DoubleDoor", 0, 16, 4, 2, 'uint')
            self.database[self.params_readFile_door.FLOOR_4_DOUBLE_DOOR.value] = Signal("", "Floor4DoubleDoor", 0, 16, 6, 2, 'uint')
            self.database[self.params_readFile_door.FLOOR_5_DOUBLE_DOOR.value] = Signal("", "Floor5DoubleDoor", 0, 16, 8, 2, 'uint')
            self.database[self.params_readFile_door.FLOOR_6_DOUBLE_DOOR.value] = Signal("", "Floor6DoubleDoor", 0, 16, 10, 2, 'uint')

            self.database[self.params_lift_name.LIFT_NAME.value] = Signal("", "LiftName", 0, 0, 0, 39, 'generic_text_lift_name')

            self.database[self.params_vfdResult.VFD_MOTOR_POWER.value] = Signal("", "VfdMotorPower", 0,0,4,2,'vfd')
            self.database[self.params_vfdResult.VFD_MOTOR_CURRENT.value] = Signal("", "VfdMotorCurrent",0,0,4,2,'vfd')
            self.database[self.params_vfdResult.VFD_DRIVE_THERMAL_STATE.value] = Signal("","VfdDriveThermalState", 0,0,4,2,'vfd')
            self.database[self.params_vfdResult.VFD_LINE_MAINS_VOLTAGE.value] = Signal("", "VfdLineMainsVoltage", 0,0,4,2,'vfd')

            self.database[self.params_door_open_count.DOOR_1_OPEN_COUNT.value] = Signal("", 'Door1OpenCount', 0,32,0,4,'uint')
            self.database[self.params_door_open_count.DOOR_2_OPEN_COUNT.value] = Signal("", 'Door2OpenCount', 0,32,4,4,'uint')
            self.database[self.params_door_open_count.DOOR_3_OPEN_COUNT.value] = Signal("", 'Door3OpenCount', 0,32,8,4,'uint')
            self.database[self.params_door_open_count.DOOR_4_OPEN_COUNT.value] = Signal("", 'Door4OpenCount', 0,32,12,4,'uint')
            self.database[self.params_door_open_count.DOOR_5_OPEN_COUNT.value] = Signal("", 'Door5OpenCount', 0,32,16,4,'uint')
            self.database[self.params_door_open_count.DOOR_6_OPEN_COUNT.value] = Signal("", 'Door6OpenCount', 0,32,20,4,'uint')

        except Exception as error:
            self.print("Error: Init database failed")
            self.print(error)
            raise error


class Signal:
    """
    Class containing data required to unpack one signal. Also stores its value and name.
    """
    def __init__(self, value: str, name: str, bit_start: int, bit_size: int,
                 byte_start: int, byte_size: int, signal_type: str):
        self.print_name = "Signal_1k"
        self.print = print
        try:
            self.name: str | int = self.__assert_and_return(name, str)
            self.value: str | int = self.__assert_and_return(value, str)
            self.bit_start: str | int = self.__assert_and_return(bit_start, int)
            self.bit_size: str | int = self.__assert_and_return(bit_size, int)
            self.byte_start: str | int = self.__assert_and_return(byte_start, int)
            self.byte_size: str | int = self.__assert_and_return(byte_size, int)
            self.signal_type: str | int = self.__assert_and_return(signal_type, str)
        except TypeError as e:
            self.print(e)
            raise e

        if self.signal_type == "byte" and int(self.bit_start) + int(self.bit_size) > 8:
            raise ValueError(f"Bit start {self.bit_start} + bit size {self.bit_size} is greater than 8.")

    def __assert_and_return(self, value: str | int, val_type: Any) -> str | int:
        """
        Check type of value and return value if correct. Otherwise raise exception.

        :param: value: What to check type for.
        :param: val_type: Expected type of value.
        :return: value: If type is expected type return value.
        """
        if not isinstance(value, val_type):
            signal_name: str | int = self.name if hasattr(self, 'name') else ""
            raise TypeError(f'Wrong type input to Signal {signal_name}. Expected {val_type} got {type(value)}')
        return value


class Params1k_lift_AR(Enum):
    AR_NUMBER = 0


class Params1k_lift_type(Enum):
    LIFT_TYPE = 1


class Params1k_lift_name(Enum):
    LIFT_NAME = 144


class Params1k_version(Enum):
    ARGATE_MAIN_VERSION = 93
    ARGATE_SUB_VERSION = 94
    ARGATE_HW_VERSION = 95
    ARGATE_OP_VERSION = 96
    ARGATE_MIN_VERSION = 161
    ARGATE_BETA_VERSION = 162
    U19_HW_VERSION = 163
    U19_OP_VERSION = 164
    U19_MAIN_VERSION = 165
    U19_SUB_VERSION = 166
    U19_MIN_VERSION = 167
    U19_BETA_VERSION = 168


class Params1k_virtual(Enum):
    BATTERY_STATE_130 = 9
    IMPULSE_130 = 57
    TEMP_134 = 92
    FLOOR_LOCK = 152



class Params1k_2(Enum):
    FILE_DATE_2 = 2
    PROG_DATE_2 = 3
    PROG_NAME_2 = 4
    MAIN_VERSION_2 = 5
    SUB_VERSION_2 = 6
    OS_VERSION_2 = 7
    HW_VERSION_2 = 8


class Params1k_130(Enum):
    # BATTERY_STATE_130 = 9
    OIL_LEVEL_130 = 10
    SAFETY_130 = 11
    FLOOR_130 = 12
    LOAD_CURRENT_130 = 13
    NO_NODES_130 = 14
    FLOOR_1_FIRE_130 = 15
    FLOOR_1_CABIN_130 = 16
    FLOOR_1_SHAFT_130 = 17
    FLOOR_1_LOCK_130 = 18
    FLOOR_1_INPUT_130 = 19
    FLOOR_1_FLOOR_LOCK_130 = 146
    FLOOR_2_FIRE_130 = 20
    FLOOR_2_CABIN_130 = 21
    FLOOR_2_SHAFT_130 = 22
    FLOOR_2_LOCK_130 = 23
    FLOOR_2_INPUT_130 = 24
    FLOOR_2_FLOOR_LOCK_130 = 147
    FLOOR_3_FIRE_130 = 25
    FLOOR_3_CABIN_130 = 26
    FLOOR_3_SHAFT_130 = 27
    FLOOR_3_LOCK_130 = 28
    FLOOR_3_INPUT_130 = 29
    FLOOR_3_FLOOR_LOCK_130 = 148
    FLOOR_4_FIRE_130 = 30
    FLOOR_4_CABIN_130 = 31
    FLOOR_4_SHAFT_130 = 32
    FLOOR_4_LOCK_130 = 33
    FLOOR_4_INPUT_130 = 34
    FLOOR_4_FLOOR_LOCK_130 = 149
    FLOOR_5_FIRE_130 = 35
    FLOOR_5_CABIN_130 = 36
    FLOOR_5_SHAFT_130 = 37
    FLOOR_5_LOCK_130 = 38
    FLOOR_5_INPUT_130 = 39
    FLOOR_5_FLOOR_LOCK_130 = 150
    FLOOR_6_FIRE_130 = 40
    FLOOR_6_CABIN_130 = 41
    FLOOR_6_SHAFT_130 = 42
    FLOOR_6_LOCK_130 = 43
    FLOOR_6_INPUT_130 = 44
    FLOOR_6_FLOOR_LOCK_130 = 151
    HAS_PUMP_130 = 45
    POWER_IN_130 = 46
    DOOR_NOT_OPEN_130 = 47
    ALARM_ACTIVE_130 = 48
    LIFT_LOCKED_130 = 49
    DOOR_OPEN_1MIN_130 = 50
    CONTACTOR_STUCK_130 = 51
    BATT_MISSING_130 = 52
    BATT_CHANGE_130 = 53
    BATT_BAD_130 = 54
    BATT_CHARGER_ERR_130 = 55
    CABIN_LIFT_130 = 56
    # IMPULSE_130 = 58 // Virtual
    # BATT_MODE_130 = 59 // Virtual signal
    EMERG_FAIL_130 = 58
    LIFT_NEEDS_SERVICE_130 = 59
    OVER_CURRENT_130 = 60
    REDUCE_LIGHT_130 = 61
    RUN_TIME_130 = 62
    FIRE_130 = 63
    PLUG_23_130 = 64
    OVER_LOAD_130 = 65
    CHILD_LOCK_130 = 145
    BATTERY_TESTING_130 = 153
    BATTERY_TEST_SUSPENDED_130 = 154

class Params1k_131(Enum):
    DOOR_IN_RUN = 68
    LOCK_IN_RUN = 69
    FLOOR_1_DUBBEL = 70
    FLOOR_X_DUBBEL = 71
    FLOOR_TOP_DUBBEL = 72
    STEP_FAIL = 73
    BATTERY_BAD = 74
    BATTERY_MISSING = 75
    EMERG_LIGHT = 76
    OVERLOAD_24V = 77
    DOOR_OPEN_1_MIN = 78
    CHECK_CONTACTOR = 79
    SHAFT_UNIT_GONE = 80
    BATT_TEST_FAIL = 81
    BATT_CHARGE_FAIL = 82
    FIRE_BLOCK = 83
    TEST_FRICTION = 84
    VPLUG23_14V = 85
    LOCK_FLOOR = 86
    RUN_TIMEOUT = 87
    OIL_SHORT_CIRCUIT = 88
    BATT_FUSE = 89
    PLATFORM_SAFETY = 90

class Params1k_133(Enum):
    # BATT_STATUS = -1
    # BATT_PROGRESS = -1
    # CHARGE_LOAD = -1
    # TEST_MODE = -1
    BATTERY_VOLTAGE = 179
    BATTERY_CAPACITY = 180
    # BATTERY_TIME = -1
    # BATTERY_RESISTANCE = -1
    BATTERY_CURRENT = 181
    # NEXT_TIME_TO_TEST_BATTERY = -1

class Params1k_134(Enum):
    CURRENT = 91
    # LOAD = -1
    # SAFE_OUT = -1
    # SAFE_PLATFORM = -1
    # SAFE_DOOR = -1
    # SAFE_LOCK = -1
    # POWER_IN = -1
    # V_IN = -1
    # V_OUT = -1
    # RIPPLE = -1
    # BATT_OUT = -1
    # PLUG_23 = -1
    # RELAY_SENSE = -1
    # TEMP = 94 //Virtual signal
    # SYSTEM_UP_TIMER = -1
    TOTAL_STARTS = 66
    TOTAL_RUN_TIME = 67
    # TRIP_START = -1
    # TRIP_RUN_TIME = -1

class Params1k_135(Enum):
    DOOR_NUMBER = -1
    DOOR_CLOSING_TIME = -2

class Params1k_readFile_param(Enum):
    DOOR_TIME = 97
    CABIN_LIGHT = 98
    ALARM_TIME = 99
    CLOSE_CALL_DELAY = 100
    DOOR_OPEN_DELAY = 101
    FIRE_FLOOR = 102
    RETURN_FLOOR = 103
    RETURN_TIME = 104
    VALVE_INTENSITY = 105
    IMPULSE_CABIN = 106
    BEEP_PLATFORM = 107
    BEEP_ARRIVAL = 108
    BATT_TEST_USE_EMERGENCY = 109
    DOOR_LOCK_TIME = 110
    PUMP_INTENSITY = 111


class Params1k_readFile_intern(Enum):
    FREQ_CONTROL = 112
    IMPULSE_AVAILABLE = 113
    LOCK_INVERT = 114
    OIL_MODE = 115
    NODE_DIRECTION = 116
    BOTTLE_VOLUME = 117
    EMERGENCY_DELAY = 118
    B_LIFT = 119
    COMMON_LIGHT = 120
    AUTO_LOCK_MENU = 121
    BATT_CAPACITY = 122
    PUMP_CAPACITY = 123
    AR_BUS_EXT = 124
    EMERGENCY_LIGHT_TEST = 125


class Params1k_readFile_node(Enum):
    FLOOR_1_NODE = 126
    FLOOR_2_NODE = 127
    FLOOR_3_NODE = 128
    FLOOR_4_NODE = 129
    FLOOR_5_NODE = 130
    FLOOR_6_NODE = 131


class Params1k_readFile_lock(Enum):
    FLOOR_1_LOCK = 132
    FLOOR_2_LOCK = 133
    FLOOR_3_LOCK = 134
    FLOOR_4_LOCK = 135
    FLOOR_5_LOCK = 136
    FLOOR_6_LOCK = 137


class Params1k_readFile_door(Enum):
    FLOOR_1_DOUBLE_DOOR = 138
    FLOOR_2_DOUBLE_DOOR = 139
    FLOOR_3_DOUBLE_DOOR = 140
    FLOOR_4_DOUBLE_DOOR = 141
    FLOOR_5_DOUBLE_DOOR = 142
    FLOOR_6_DOUBLE_DOOR = 143

class Params1k_door_closing_time(Enum):
    DOOR_1_CLOSING_TIME_135 = 155
    DOOR_2_CLOSING_TIME_135 = 156
    DOOR_3_CLOSING_TIME_135 = 157
    DOOR_4_CLOSING_TIME_135 = 158
    DOOR_5_CLOSING_TIME_135 = 159
    DOOR_6_CLOSING_TIME_135 = 160

class Params1k_vfd_data(Enum):
    VFD_MOTOR_CURRENT = 169
    VFD_MOTOR_POWER = 170
    VFD_LINE_MAINS_VOLTAGE = 171
    VFD_DRIVE_THERMAL_STATE = 172

class Param1k_door_open_count(Enum):
    DOOR_1_OPEN_COUNT = 173
    DOOR_2_OPEN_COUNT = 174
    DOOR_3_OPEN_COUNT = 175
    DOOR_4_OPEN_COUNT = 176
    DOOR_5_OPEN_COUNT = 177
    DOOR_6_OPEN_COUNT = 178