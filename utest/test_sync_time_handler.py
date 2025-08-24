#!/usr/bin/env python

import unittest
import sys
import os
from freezegun import freeze_time
import mock
from datetime import datetime, timezone

p = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.pardir, 'src'))
sys.path.append(p)
from lib import syncTimeHandler
from lib.error_signals import SyncTimeCode, MbCode


class TestSyncTimeHandler(unittest.TestCase):

    def setUp(self):
        print("\nSetup: {}".format(self._testMethodName))

        self.handler = syncTimeHandler.SyncTimeHandler()
        assert self.handler.name == "SyncTimeHandler"

    def tearDown(self):
        print("\nTest done: {}".format(self._testMethodName))

    class ModbusStub:
        def write_parameter(self, args):
            raise Exception

    def compare_timestamp(self, year=1970, month=1, day=1, hour=0, minute=0, second=0):
        expected_timestamp = int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp())
        with freeze_time(f"{year}-{month}-{day} {hour}:{minute}:{second}"):
            received_timestamp = self.handler._SyncTimeHandler__get_utc_time()
            self.assertEqual(received_timestamp, expected_timestamp)

    def test_get_utc_time(self):
        self.compare_timestamp()
        self.compare_timestamp(year=2020, month=10, day=30, hour=16)
        self.compare_timestamp(year=2040, month=12, day=5, hour=16, minute=13, second=42)

    def test_response(self):
        error_code = SyncTimeCode.NO_ERR
        return_value = self.handler._SyncTimeHandler__handle_return(error_code)
        assert return_value == (self.handler.name, SyncTimeCode.NO_ERR.name)

    def test_getTime_error_values(self):
        modbus_handler = None

        time_value_error = "not a number"
        expected_return = (self.handler.name, SyncTimeCode.ARG_TYPE_ERR.name)
        assert self.handler.sync_time(time_value_error, modbus_handler) == expected_return

        time_value_error = "-2"
        expected_return = (self.handler.name, SyncTimeCode.ARG_INVALID_ERR.name)
        assert self.handler.sync_time(time_value_error, modbus_handler) == expected_return

    def test_getTime_modbus_handler(self):
        modbus_handler = None
        time_value_ok = "-1"
        expected_return = (self.handler.name, SyncTimeCode.ARG_MODBUS_ERR.name)
        assert self.handler.sync_time(time_value_ok, modbus_handler) == expected_return

    def test_update_parameter_errors(self):
        modbus_handler = None
        time_value_ok = "-1"
        return_value = self.handler._SyncTimeHandler__update_parameter(modbus_handler, time_value_ok)
        assert return_value == (self.handler.name, SyncTimeCode.ARG_MODBUS_ERR.name)

        modbus_handler = self.ModbusStub()
        time_value_ok = "-1"
        return_value = self.handler._SyncTimeHandler__update_parameter(modbus_handler, time_value_ok)
        assert return_value == (self.handler.name, SyncTimeCode.MODBUS_EXCEPTION_ERR.name)

    def test_update_parameter(self):
        for i in range(-1, 10):
            modbus_handler = self.ModbusStub()
            modbus_handler.write_parameter = mock.MagicMock(return_value=(-1, MbCode.SOURCE.name, MbCode.NO_ERR.name))
            assert modbus_handler.write_parameter.call_count == 0

            time_value_ok = str(i)
            return_value = self.handler._SyncTimeHandler__update_parameter(modbus_handler, time_value_ok)
            assert return_value == (self.handler.name, SyncTimeCode.NO_ERR.name)

            assert modbus_handler.write_parameter.call_count == 1
            time_parameter = "4"
            modbus_handler.write_parameter.assert_called_with([time_parameter, time_value_ok])

    def test_modbus_response(self):
        expected_return = (self.handler.name, SyncTimeCode.MODBUS_ERR.name)
        modbus_response = None
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return
        modbus_response = ""
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return
        modbus_response = (MbCode.SOURCE.name, MbCode.COM_ERR.name)
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return
        modbus_response = (-1, -1, MbCode.SOURCE.name, MbCode.COM_ERR.name)
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return

        modbus_response = (-1, MbCode.SOURCE.name, MbCode.COM_ERR.name)
        expected_return = modbus_response[1:]
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return

        modbus_response = (-1, MbCode.SOURCE.name, MbCode.NO_ERR.name)
        expected_return = (self.handler.name, SyncTimeCode.NO_ERR.name)
        assert self.handler._SyncTimeHandler__handle_modbus_response(modbus_response) == expected_return
