#!/usr/bin/env python

import os
import sys
from datetime import datetime
from math import ceil

path_to_source = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
sys.path.append(path_to_source)

from wrappers import printWrapper
from lib.liftAgent_error_signals import SyncTimeCode, MbCode


class SyncTimeHandler:
    """
    Class to handle Sync Time requests.
    """
    def __init__(self):
        self.SyncTimeCode = SyncTimeCode
        self.name = self.SyncTimeCode.SOURCE.value
        self.print = printWrapper.Print(self.name).print

    def sync_time_rs232(self, time_value):
        try:
            time_value = int(time_value)
        except ValueError as error:
            self.print(error)
            self.print("Error: Time value '{}' in signal is not a number".format(time_value))
            return self.__handle_return(self.SyncTimeCode.ARG_TYPE_ERR)

        if time_value == -1:
            timestamp = self.__get_utc_time()
        else:
            self.print("Error: Invalid time value in signal")
            return self.__handle_return(self.SyncTimeCode.ARG_INVALID_ERR)

        return timestamp

    def sync_time(self, time_value, modbus_handler):
        try:
            time_value = int(time_value)
        except ValueError as error:
            self.print(error)
            self.print("Error: Time value '{}' in signal is not a number".format(time_value))
            return self.__handle_return(self.SyncTimeCode.ARG_TYPE_ERR)

        if time_value == -1:
            timestamp = self.__get_utc_time()
        elif time_value > -1:
            timestamp = time_value
        else:
            self.print("Error: Invalid time value in signal")
            return self.__handle_return(self.SyncTimeCode.ARG_INVALID_ERR)

        return self.__update_parameter(modbus_handler, timestamp)

    def __update_parameter(self, modbus_handler, timestamp):
        if not modbus_handler:
            self.print("Error: No valid Modbus Handler object provided")
            return self.__handle_return(self.SyncTimeCode.ARG_MODBUS_ERR)

        time_parameter_number = "4"
        try:
            modbus_response = modbus_handler.write_parameter([time_parameter_number, str(timestamp)])
        except Exception as error:
            self.print(error)
            return self.__handle_return(self.SyncTimeCode.MODBUS_EXCEPTION_ERR)

        return self.__handle_modbus_response(modbus_response)

    def __handle_modbus_response(self, modbus_response):
        expected_response_length = 3
        actual_response_length = 0
        if modbus_response:
            actual_response_length = len(modbus_response)

        if actual_response_length != expected_response_length:
            self.print("Error: Modbus Handler returned unexpected response: '{}'".format(modbus_response))
            return self.__handle_return(self.SyncTimeCode.MODBUS_ERR)

        if modbus_response[2] != MbCode.NO_ERR.name:
            self.print("Error: Modbus Handler returned error response: '{}'".format(modbus_response))
            source = modbus_response[1]
            error_code = modbus_response[2]
            return source, error_code

        return self.__handle_return(self.SyncTimeCode.NO_ERR)

    def __handle_return(self, error_code):
        return self.name, error_code.name

    def __get_utc_time(self):
        utc = datetime.utcnow()
        utc_timestamp = ceil(utc.timestamp())
        self.print("UTC timestamp: {}".format(utc_timestamp))
        return utc_timestamp


if __name__ == "__main__":
    handler = SyncTimeHandler()
    handler.sync_time("-1", None)
