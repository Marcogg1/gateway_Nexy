#!/usr/bin/env python

import os
import sys
import time
from math import ceil
from typing import Type, Any
from datetime import datetime, timezone

path_to_source = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(path_to_source)

from lib.error_signals import SyncTimeCode, MbCode, Rs232Code


class SyncTimeHandler:
    """
    Class to handle Sync Time requests.
    """
    def __init__(self) -> None:
        self.SyncTimeCode: Type[SyncTimeCode] = SyncTimeCode
        self.name: str = self.SyncTimeCode.SOURCE.value
        self.print = print

    def sync_time_rs232(self, epoch_time: str, rs232_handler: Any) -> tuple[Any, str, str]:
        try:
            int(epoch_time)
        except ValueError as e:
            self.print(f"Error: inserted epoch_time '{epoch_time}' is not an int.")
            self.print(e)
            return -1, self.name, self.SyncTimeCode.ARG_TYPE_ERR.name

        if epoch_time == '-1':
            epoch_time = self.__get_utc_time()
            self.print(f"Got time -1, setting UTC_time:{epoch_time}")

        _, _, _, _, err_code = rs232_handler.write_serial(["time", epoch_time])
        if err_code != Rs232Code.NO_ERR.name:
            self.print(f"Error: failed to write time read request to the serial bus.")
            return -1, self.name, err_code

        time.sleep(rs232_handler.serial_timeout)
        _, resp_wanted, _, err_code = rs232_handler.get_signal_from_serial_buffer('time')
        response = resp_wanted[0]['updated']

        if err_code != SyncTimeCode.NO_ERR.name:
            self.print("Error: Failed to get time read response from serial buffer.")
            return -1, self.name, err_code

        if response == 'false':
            err_code = SyncTimeCode.EPOCH_TIME_ERR.name

        return response, self.name, err_code

    def sync_time(self, time_value_str: str, modbus_handler: Any) -> tuple[str, str]:
        try:
            time_value_int: int = int(time_value_str)
        except ValueError as error:
            self.print(error)
            self.print("Error: Time value '{}' in signal is not a number".format(time_value_str))
            return self.name, self.SyncTimeCode.ARG_TYPE_ERR.name

        timestamp: int
        if time_value_int == -1:
            timestamp = self.__get_utc_time()
        elif time_value_int > -1:
            timestamp = time_value_int
        else:
            self.print("Error: Invalid time value in signal")
            return self.name, self.SyncTimeCode.ARG_INVALID_ERR.name

        return self.__update_parameter(modbus_handler, timestamp)

    def __update_parameter(self, modbus_handler: Any, timestamp: int) -> tuple[str, str]:
        if not modbus_handler:
            self.print("Error: No valid Modbus Handler object provided")
            return self.name, self.SyncTimeCode.ARG_MODBUS_ERR.name

        time_parameter_number = "4"
        try:
            modbus_response = modbus_handler.write_parameter([time_parameter_number, str(timestamp)])
        except Exception as error:
            self.print(error)
            return self.name, self.SyncTimeCode.MODBUS_EXCEPTION_ERR.name

        return self.__handle_modbus_response(modbus_response)

    def __handle_modbus_response(self, modbus_response: Any) -> tuple[str, str]:
        expected_response_length: int = 3
        actual_response_length: int = 0
        if modbus_response:
            actual_response_length = len(modbus_response)

        if actual_response_length != expected_response_length:
            self.print("Error: Modbus Handler returned unexpected response: '{}'".format(modbus_response))
            return self.name, self.SyncTimeCode.MODBUS_ERR.name

        if modbus_response[2] != MbCode.NO_ERR.name:
            self.print("Error: Modbus Handler returned error response: '{}'".format(modbus_response))
            source: str = modbus_response[1]
            error_code: Any = modbus_response[2]
            return source, error_code

        return self.name, self.SyncTimeCode.NO_ERR.name

    def __get_utc_time(self) -> int:
        utc: datetime = datetime.now(timezone.utc)
        utc_timestamp: int = ceil(utc.timestamp())
        self.print("UTC timestamp: {}".format(utc_timestamp))
        return utc_timestamp


if __name__ == "__main__":
    handler = SyncTimeHandler()
    handler.sync_time("-1", None)
