#!/usr/bin/env python3
import sys
import os
import mock
import json
import serial
import pytest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'src'))
sys.path.append(p)

import liftApi.rs232_handler as RS
from lib.error_signals import SyncTimeCode
from lib.thousand_lib import ThousandLib


# MOCKS
class FileStat:
    def __init__(self):
        self.st_size = 2048


m_bytes_waiting = 0
m_serial_response = b''
m_socket_response = b''


# Monkey patches for Serial methods
def monkey_patch_inwaiting():
    global m_bytes_waiting
    return m_bytes_waiting


def monkey_patch_read(**kwargs):
    global m_serial_response
    return m_serial_response


def monkey_patch_recv(*args):
    global m_socket_response
    return m_socket_response


class _SeqInt:
    """Descriptor returning successive ints on each attribute access, matching pyserial's in_waiting property."""

    def __init__(self, values: list[int]) -> None:
        """Initializes the descriptor with the sequence of values to return.

        Args:
            values: Ints to return in order on successive attribute accesses.
        """
        self._it = iter(values)

    def __get__(self, obj: object, objtype: type | None = None) -> int:
        """Returns the next value in the sequence, or 0 once exhausted.

        A default is required here (rather than raising StopIteration) because
        `Serial` is patched as a class, not an instance, so this descriptor
        persists as a class attribute across tests; monkeypatch.setattr()
        reads the previous test's (already exhausted) instance internally
        before installing a new one.
        """
        return next(self._it, 0)


class Serial:
    """
    Mock class for both serial and socket
    """

    def __init__(self):
        pass


    def in_waiting(self):
        pass

    # serial.Serial
    def read(self):
        pass

    # serial.Serial
    def write(self):
        pass

    # socket
    def recv(self):
        pass


class TestRs232Handler:

    @mock.patch('os.path.exists')
    @mock.patch('socket.socket')
    @mock.patch('serial.Serial')
    def setup_method(self, method, mock_serial, mock_socket, mock_path_exists):
        global m_bytes_waiting, m_serial_response, m_socket_response

        print("\nSetup: {}".format(method.__name__))

        mock_serial.return_value = Serial
        mock_socket.return_value = Serial
        m_bytes_waiting = 0
        m_serial_response = b''
        m_socket_response = b''

        mock_path_exists.return_value = False

        self.rs = RS.Rs232Handler(ThousandLib())
        self.rsCodes = self.rs.rs232Codes
        assert self.rs.name == "Rs232Handler"

    def teardown_method(self, method):
        print("\nTest done: {}\n".format(method.__name__))

    def patch_serial(self, exp_serial, monkeypatch):
        global m_bytes_waiting, m_serial_response, m_socket_response

        monkeypatch.setattr(self.rs.client, 'in_waiting', monkey_patch_inwaiting)
        monkeypatch.setattr(self.rs.client, 'read', monkey_patch_read)
        monkeypatch.setattr(self.rs.client, 'recv', monkey_patch_recv)

        m_bytes_waiting = len(exp_serial)
        m_serial_response = exp_serial
        m_socket_response = exp_serial

    def test_validate_inputs(self):
        """
        Test validation of input argument
        """

        # Testing input args that is not list

        args_in = [None, "-1", {'dict_val': 2}, 55, -1]
        for args_iter in args_in:
            cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_iter)

            assert cmd == -1
            assert operation_type == -1
            assert data == -1
            assert file_name == -1
            assert id == -1
            assert interval == -1
            assert err_code == self.rsCodes.ARG_TYPE_ERR.name

        # Testing non-string args
        # ------------------------------------
        args_in = [["1", 2, "3"], [["1", "2"], "3"]]
        for args_iter in args_in:
            cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_iter)

            assert cmd == -1
            assert operation_type == -1
            assert data == -1
            assert file_name == -1
            assert id == -1
            assert interval == -1
            assert err_code == self.rsCodes.ARGS_IN_ELEM_ATTR_ERR.name

        # Testing non supported cmd's
        # --------------------------------------
        args_in = [["1", "2", "3"], ["short_list"]]
        for args_iter in args_in:
            cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_iter)

            assert cmd == -1
            assert operation_type == -1
            assert data == -1
            assert file_name == -1
            assert id == -1
            assert interval == -1
            assert err_code == self.rsCodes.CMD_NOT_SUPPORTED.name

        # Testing wrong list lengths
        # ----------------------------
        cmd_in = "operation"
        args_in = [cmd_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        cmd_in = "liftRef1"
        type_in = "abc"
        data_in = "123"
        args_in = [cmd_in, type_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing non int signal number for cmd operation
        # ----------------------------
        cmd_in = "operation"
        type_in = "abc"
        data_in = "[1, 2, 3, 4, 5, 6]"
        args_in = [cmd_in, type_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_ELEM_INT_ERR.name

        # Testing correct format for cmd operation
        # ----------------------
        cmd_in = "operation"
        type_in = "131"
        data_in = "[1, 2, 3, 4, 5, 6]"
        args_in = [cmd_in, type_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == type_in
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing correct format for cmd liftRef1
        # ----------------------
        cmd_in = "liftRef1"
        data_in = "AR123"
        args_in = [cmd_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == ""
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing correct format for cmd logfile
        # ----------------------
        cmd_in = "logfile"
        data_in = '2'
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect arg for cmd logfile
        # ---------------------
        data_in = "131"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.DATA_ERR.name

        # Testing correct format for cmd time
        cmd_in = "time"
        data_in = "123456"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect format for cmd time
        args_in = [cmd_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # valid file names to be tested for read and write 1k files
        valid_file_names = ['/aritco/param', '/aritco/intern', '/aritco/node', '/aritco/lock', '/aritco/door']

        # Testing correct format for cmd readFile
        # ---------------------
        cmd_in = "readFile"

        for valid_file_name in valid_file_names:

            file_name_in = valid_file_name
            args_in = [cmd_in, file_name_in]
            cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

            assert cmd == cmd_in
            assert operation_type == ""
            assert data == ""
            assert file_name == valid_file_name
            assert id == ""
            assert interval == ""
            assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect file_name for cmd readFile
        # ---------------------
        cmd_in = "readFile"
        data_in = "/artico/faulty"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.FILE_NAME_ERR.name

        # Testing incorrect number of args for cmd readFile
        # ---------------------
        cmd_in = "readFile"
        data_in = "/artico/param"
        args_in = [cmd_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing correct format for cmd writeFile
        # ---------------------
        for valid_file_name in valid_file_names:
            cmd_in = "writeFile"
            file_name_in = valid_file_name
            data_in = '{"data":[0,0,0,0,0,0,0,0,0,0,0,0]}'
            exp_data_out = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            args_in = [cmd_in, file_name_in, data_in]
            cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

            assert cmd == cmd_in
            assert operation_type == -1
            assert data == exp_data_out
            assert file_name == file_name_in
            assert id == ""
            assert interval == ""
            assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect file_name for cmd writeFile
        # ---------------------
        cmd_in = "writeFile"
        file_name_in = "/aritco/faulty"
        data_in = '{"data":[0,0,0,0,0,0,0,0,0,0,0,0]}'
        args_in = [cmd_in, file_name_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.FILE_NAME_ERR.name

        # Testing incorrect number of args for cmd writeFile
        # ---------------------
        cmd_in = "writeFile"
        file_name_in = "/aritco/door"
        faulty_arg = "Faulty"
        data_in = '{"data":[0,0,0,0,0,0,0,0,0,0,0,0]}'
        args_in = [cmd_in, file_name_in, faulty_arg, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing incorrect data format
        # ---------------------
        cmd_in = "writeFile"
        file_name_in = "/aritco/door"
        data_in = '{"data":"0,0,0,0,0,0,0,0,0,0,0,0"}'
        args_in = [cmd_in, file_name_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.JSON_VALUE_TYPE_ERR.name

        # Testing incorrect data format - key error
        # ---------------------
        cmd_in = "writeFile"
        file_name_in = "/aritco/door"
        data_in = '{"wrongkey":[0,0,0,0,0,0,0,0,0,0,0,0]}'
        args_in = [cmd_in, file_name_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Testing invalid json format for data
        # ---------------------
        cmd_in = "writeFile"
        file_name_in = "/aritco/door"
        data_in = '{"data"}'
        args_in = [cmd_in, file_name_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.JSON_ERR.name

        # Testing childLock
        # ---------------------
        cmd_in = "childLock"
        data_in = "on"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect data in for childLock
        # ---------------------
        cmd_in = "childLock"
        data_in = "onn"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.DATA_ERR.name

        # Testing incorrect args for childLock
        # ---------------------
        cmd_in = "childLock"
        data_in = "on"
        args_in = [cmd_in, data_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing FloorLock
        # ------------------------
        cmd_in = "floorLock"
        data_in = "[2,4,6]"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == data_in
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect args for floorLock
        # ------------------------
        cmd_in = "floorLock"
        data_in = "[2,3,4]"
        args_in = [cmd_in, data_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing correct args for vfdClearTable
        # ------------------------
        cmd_in = "vfdClearTable"
        args_in = [cmd_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == ""
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect args for vfdClearTable
        # ------------------------

        cmd_in = "vfdClearTable"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing correct args for vfdId
        # ----------------------

        cmd_in = "vfdId"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        args_in = [cmd_in, data_in]
        cmd, operation_type, data, file_name, id, interval, err_code = self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        assert file_name == ""
        assert id == ""
        assert interval == ""
        assert err_code == self.rsCodes.NO_ERR.name


        # Testing incorrect args for VfdId
        # ----------------------

        cmd_in = "vfdId"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        data_in_faulty = "0xD3,0xA5,0x0E,0x10"
        args_in = [cmd_in, data_in, data_in_faulty]
        cmd, operation_type, data, file_name, id, interval, err_code =\
            self.rs._Rs232Handler__validate_serial_inputs(args_in)

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == -1
        assert interval == -1
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Testing correct args for vfdRead
        # ----------------------

        cmd_in = "vfdRead"
        id_in = "0"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        interval_in = "24"
        args_in = [cmd_in, id_in, data_in, interval_in]
        cmd, operation_type, data, file_name, id, interval, err_code = \
            (self.rs._Rs232Handler__validate_serial_inputs(args_in))

        assert cmd == cmd_in
        assert operation_type == ""
        assert data == "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        assert file_name == ""
        assert id == int(id_in)
        assert interval == int(interval_in)
        assert err_code == self.rsCodes.NO_ERR.name

        # Testing incorrect args for VfdRead
        # ----------------------

        cmd_in = "vfdRead"
        id_in = "1a"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        interval_in = "24"
        args_in = [cmd_in, id_in, data_in, interval_in]
        cmd, operation_type, data, file_name, id, interval, err_code = \
            (self.rs._Rs232Handler__validate_serial_inputs(args_in))

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == id_in
        assert interval == interval_in
        assert err_code == self.rsCodes.ARGS_IN_ELEM_INT_ERR.name

        # Testing incorrect id number for VfdRead
        # ----------------------

        cmd_in = "vfdRead"
        id_in = "13"
        data_in = "0x01,0x03,0x0C,0x81,0x00,0x01,0xD7,0x72"
        interval_in = "24"
        args_in = [cmd_in, id_in, data_in, interval_in]
        cmd, operation_type, data, file_name, id, interval, err_code = \
            (self.rs._Rs232Handler__validate_serial_inputs(args_in))

        assert cmd == cmd_in
        assert operation_type == -1
        assert data == -1
        assert file_name == -1
        assert id == int(id_in)
        assert interval == -1
        assert err_code == self.rsCodes.VFD_ID_ERR.name

    def test_decode_and_validate_response(self):
        """
        Test validation of AR-GATE response
        """
        # Testing response is string
        # --------------------------
        rsp_out = [None, -1, {'dict_val': 2}, 55, [1, "2", 3]]
        for rsp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_iter)
            assert rsp_val == rsp_iter
            assert err_code == self.rsCodes.SERIAL_COM_ERR.name

        # Testing response can be json'd
        # --------------------------
        rsp_out = ['Not_json', '{"not_json"]', '{"one": 1, "two": 2: 3: 4}', "normal_string", "123"]
        for rsp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_iter)
            assert rsp_val == rsp_iter
            assert err_code == self.rsCodes.JSON_ERR.name

        # Testing responses without "cmd" and "data"
        # --------------------------
        rsp_out = ['{"one":1, "two":2, "three":3}', '{"cmd":1, "not_data":2}',
                   '{"cmd":1}', '{"not_cmd":1, "data":3}']
        for rsp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_iter)
            assert type(rsp_val) == dict
            assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Test cmd not string
        # --------------------------
        rsp_out = ['{"cmd":1, "type":2, "data":[1,2,3]}', '{"logs": "faulty_log_str_rsp"}']
        for rsp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_iter)
            assert type(rsp_val) == dict
            assert err_code == self.rsCodes.JSON_VALUE_TYPE_ERR.name

        # Test invalid 1k file name
        # --------------------------
        resp_iter = '{"cmd":"readFile", "name":"/artico/faukty", "data":[0,1,2,3],"err":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(resp_iter)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.DATA_TYPE_ERR.name

        # Test invalid data key
        # --------------------------
        resp_iter = '{"cmd":"readFile", "name":"/aritco/lock", "defaltDta":[0,0,0,0], "err":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(resp_iter)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_VALUE_TYPE_ERR.name

        # Test invalid vfdClearTable response
        # ---------------------------
        rsp_out = '{"cmd":"vfdClearTable","data":"0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F"}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name


        # Test invalid vfdId response
        # Missing agumets
        # ---------------------------
        rsp_out = '{"cmd":"vfdId","data":"0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F"}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test invalid vfdId response
        # Data resp faulty format
        # ---------------------------
        rsp_out = '{"cmd":"vfdId","data":[0,3,26,10,17,14,31],"error":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.DATA_TYPE_ERR.name

        # Test invalid vfdId response
        # Faulty error respons
        # ---------------------------
        rsp_out = '{"cmd":"vfdId","data":"0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F","eror":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_KEY_ERR.name


        # Test invalid vfdId response
        # Invalid error value respons
        # ---------------------------
        rsp_out = '{"cmd":"vfdId","data":"0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F","error":3}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.DATA_ERR.name


        # Test invalid vfdRead response
        # Invalid error value respons, to many arguments
        # ---------------------------
        rsp_out = '{"cmd":"vfdRead", "id": 0, "data": "0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F", "error" : 0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test invalid vfdRead response
        # Invalid error value respons, id is missing
        # ---------------------------
        rsp_out = '{"cmd":"vfdRead", "data": "0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F", "error" : 0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Test invalid vfdRead response
        # Invalid error value respons, error is missing
        # ---------------------------
        rsp_out = '{"cmd":"vfdRead", "id": 0, "data": "0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F"}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Test invalid vfdRead response
        # Invalid error value respons, faulty error value
        # ---------------------------
        rsp_out = '{"cmd":"vfdRead", "id": 0, "error" : 3}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.DATA_ERR.name


        # Test invalid vfdResult response
        # Invalid error value respons, to many arguments
        # ---------------------------
        rsp_out = '{"cmd":"vfdResult","id":2,"data":"0x01,0x03,0x02,0x00,0x29,0x79,0x9A","timestamp":[164,47,36,0], "error":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test invalid vfdResult response
        # Invalid error value respons, id is missing
        # ---------------------------
        rsp_out = '{"cmd":"vfdResult","data":"0x01,0x03,0x02,0x00,0x29,0x79,0x9A","timestamp":[164,47,36,0], "error":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Test invalid vfdResult response
        # Invalid error value respons, id value is invalid
        # ---------------------------
        rsp_out = '{"cmd":"vfdResult","id":8,"data":"0x01,0x03,0x02,0x00,0x29,0x79,0x9A","timestamp":[164,47,36,0]}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.VFD_ID_ERR.name

        # Test invalid vfdResult response
        # Invalid error value respons, timestamp is missing
        # ---------------------------
        rsp_out = '{"cmd":"vfdResult","id":2,"data":"0x01,0x03,0x02,0x00,0x29,0x79,0x9A", "error":0}'
        rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_out)
        assert type(rsp_val) == dict
        assert err_code == self.rsCodes.JSON_KEY_ERR.name



        # Test invalid data format
        # --------------------------
        rsp_out = ['{"cmd": "readFile", "name": "/aritco/lock", "data": "0,0,0,0", "err": 0}']
        for resp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(resp_iter)
            assert type(rsp_val) == dict
            assert err_code == self.rsCodes.JSON_ERR.name

        # Test invalid error key in read and write file response
        rsp_out = ['{"cmd": "readFile", "name": "/aritco/lock", "data": [0,0,0,0], "err_faulty": 0}',
                   '{"cmd": "writeFile", "name": "/aritco/lock", "err_faulty": 0}']

        for resp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(resp_iter)
            assert type(rsp_val) == dict
            assert err_code == self.rsCodes.JSON_KEY_ERR.name



        # Testing correct responses
        # --------------------------
        rsp_out = ['{"cmd":"1", "type":2, "data":[1,2,3]}',
                   '{"cmd":"operation", "type":130, "data":[64,2,0]}',
                   '{"cmd":"liftRef1", "data":"AR123456"}',
                   '{"logs":[{"timeDelta":0,"lastRecord":4638,"HsopName":"ARK4","HsopVersion":"P32M","data":"9C....6E","firstRecord":4509}]}',
                   '{"cmd":"time", "updated":"true"}',
                   '{"cmd":"readFile","name":"/aritco/door","data":[0,0,0,0,0,0,0,0,0,0,0,0],"err":0}',
                   '{"cmd":"readFile","name":"/aritco/param","data": [15,0,60,0,0,0,3,0,0,0,1,0,0,0,60,0,2,0,0,0,0,0,0,0,1,0,10,0,6,0],"err":0}',
                   '{"cmd":"readFile","name":"/aritco/intern","data": [0,0,0,0,0,0,0,0,0,0,10,0,70,0,0,0,0,0,0,0,100,0,164,1],"err":0}',
                   '{"cmd":"readFile","name":"/aritco/node","data":[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],"err":0}',
                   '{"cmd":"readFile","name":"/aritco/lock","data":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"err":0}',
                   '{"cmd":"readFile","name":"/aritco/door","data":[0,0,0,0,0,0,0,0,0,0,0,0],"err":0}',
                   '{"cmd":"writeFile","name":"/aritco/door","err":0}',
                   '{"cmd":"lockFloor","data":[2,3,4],"err":0}',
                   '{"cmd":"vfdClearTable"}',
                   '{"cmd":"vfdId","data":"0x00, 0x03, 0x1A, 0x0A, 0x11, 0x0E, 0x1F","error":0}',
                   '{"cmd":"vfdRead","id":0,"error": 0}',
                   '{"cmd":"vfdResult","id":2,"data":"0x01,0x03,0x02,0x00,0x29,0x79,0x9A","timestamp":[164,47,36,0]}']

        for rsp_iter in rsp_out:
            rsp_val, err_code = self.rs._Rs232Handler__decode_and_validate_serial_response(rsp_iter)
            assert type(rsp_val) == dict
            assert err_code == self.rsCodes.NO_ERR.name

    def test_read_serial(self, monkeypatch):
        # Test reading one 130 status message
        # -----------------------------------
        exp_serial = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        status, err_code = self.rs.read_serial()

        # read_serial will return the messages as a string
        assert isinstance(status, str)

        # read_serial does not keep json formatting in return messages anymore
        assert status == exp_serial.decode('utf-8')
        assert err_code == self.rsCodes.NO_ERR.name

        # Test reading two 130 status message
        # -----------------------------------
        exp_serial = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_serial += b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 8]}'
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        status, err_code = self.rs.read_serial()

        # read_serial will return response as a string
        assert isinstance(status, str)

        # read_serial will not keep json formatting in return messages
        assert len(status) == len(exp_serial.decode('utf-8'))

    def test_read_serial_half_message(self, monkeypatch):

        # Test reading before full signal is sent from ARGATE serial
        # -----------------------------------
        exp_serial_first = b'{"cmd": "operation", "type": 130, "data":[4, 5, '
        exp_serial_second = b'6, 7]}'

        self.patch_serial(exp_serial_first, monkeypatch)
        self.rs.client.read = mock.MagicMock(side_effect=[exp_serial_first, exp_serial_second])
        self.rs.client.in_waiting = _SeqInt([1, 1, len(exp_serial_first), 0, 1, len(exp_serial_second), 0])

        status, err_code = self.rs.read_serial()
        assert isinstance(status, str)
        assert len(status) == len((exp_serial_first + exp_serial_second).decode('utf-8'))
        assert status == (exp_serial_first + exp_serial_second).decode('utf-8')

    def test_read_serial_no_waiting_byte(self):
        """
        Test to read serial-port when no indata is waiting to be read
        """

        # Set simulator to false in case rs_dev file somehow exists
        exp_code = self.rsCodes.NO_WAITING_BYTES_ERR.name
        exp_rsp_full = -1

        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=True)
        self.rs.client.in_waiting = _SeqInt([0, 0, 0, 0, 0])

        rsp_full, err_code = self.rs.read_serial()
        assert exp_rsp_full == rsp_full
        assert exp_code == err_code

    def test_read_serial_waiting_byte(self, monkeypatch):
        """
        Test to read serial-port when indata is waiting to be read
        """
        global m_serial_response

        # Set simulator to false in case rs_dev file somehow exists
        exp_code = self.rsCodes.NO_ERR.name

        exp_rsp = b'{"cmd": "liftRef1", "data": "AR123456"}'

        monkeypatch.setattr(self.rs.client, 'read', monkey_patch_read)
        m_serial_response = exp_rsp

        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=True)
        self.rs.client.in_waiting = _SeqInt([0, 0, len(exp_rsp), len(exp_rsp), 0, 0])

        rsp_full, err_code = self.rs.read_serial()

        assert exp_rsp.decode('utf-8') == str(rsp_full).replace('\'', '\"')
        assert exp_code == err_code

    def test_read_serial_no_port_available(self, monkeypatch):
        """
        Test to read serial when no serial port is available
        """
        # Mock sets serial available to FALSE
        # Test no serial available
        exp_rsp = -1
        exp_code = self.rsCodes.SERIAL_COM_ERR.name

        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=False)
        self.rs.write_status_to_file = mock.MagicMock(return_value=True)

        rsp, err_code = self.rs.read_serial()
        assert exp_rsp == rsp
        assert exp_code == err_code

    def test_read_serial_read_exception(self, monkeypatch):
        """
        Test to read serial-port when there is indata but read somehow fails.
        """
        # Set simulator to false in case rs_dev file somehow exists
        exp_code = self.rsCodes.SERIAL_COM_ERR.name
        exp_rsp = -1

        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=True)
        self.rs.client.in_waiting = _SeqInt([0, 0, 1, 1, 0, 0])

        self.rs.client.read = mock.MagicMock(side_effect=[serial.SerialException])

        rsp_full, err_code = self.rs.read_serial()

        assert exp_rsp == rsp_full
        assert exp_code == err_code

    def test_read_serial_decode_error(self, monkeypatch):
        """
        Test reading a non-utf-8 decodeable char
        """
        exp_rsp = -1
        exp_code = self.rsCodes.SERIAL_COM_ERR.name

        exp_serial = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}\xf8'
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        status, err_code = self.rs.read_serial()

        assert status == -1
        assert err_code == self.rsCodes.SERIAL_DECODE_ERR.name

    def test_read_serial_missing_curlies(self, monkeypatch):
        """
        Test when missing beginning curly brace
        """
        exp_rsp = -1
        exp_code = self.rsCodes.SERIAL_COM_ERR.name

        exp_serial = b'"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}{whole_response}'
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        status, err_code = self.rs.read_serial()

        assert status == "{whole_response}"
        assert err_code == self.rsCodes.NO_ERR.name

    def test_split_response_multiple_status_msgs(self, monkeypatch):
        """
        Test reading two 'operation' status message and one other
        """
        exp_other = b'{"cmd": "liftRef1", "data": "AR123456"}'
        exp_status = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_status += b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 8]}'

        # Order matters
        exp_serial = exp_other + exp_status
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        response, err_code = self.rs.read_serial()

        # read_serial will return the messages in a string
        assert isinstance(response, str)
        assert len(response) == len(exp_serial.decode('utf-8'))

        # split_response will always return status as status even if wanted_cmd is 'operation'
        wanted_cmd = 'operation'
        wanted_type = '130'
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(response, wanted_cmd, wanted_type)

        # split_response shall return 2 lists and an empty string
        assert isinstance(status, list)
        assert isinstance(wanted, str)
        assert wanted == ''
        assert isinstance(other, list)

        # make sure status contains two messages and other 1
        assert len(status) == 2
        assert len(wanted) == 0
        assert len(other) == 1

        # pack the responses in status list and see if matches what was read from serial "exp_serial"
        # packing order matters
        packed_other = ''
        packed_status = ''

        for msg in other:
            packed_other += str(msg).replace('\'', '\"')
        for msg in status:
            packed_status += str(msg).replace('\'', '\"')

        packed = packed_other + packed_status

        assert len(packed) == len(exp_serial.decode('utf-8'))
        assert len(packed_other) == len(exp_other.decode('utf-8'))
        assert len(packed_status) == len(exp_status.decode('utf-8'))
        assert packed == exp_serial.decode('utf-8')
        assert err_code == self.rsCodes.NO_ERR.name

    def test_split_response_wanted_cmd(self, monkeypatch):
        """
        Test reading two 'operation' status messages, and 'liftRef1' with wanted_cmd set to 'liftRef1'
        """
        exp_wanted = b'{"cmd": "liftRef1", "data": "AR123456"}'
        exp_status = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_status += b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 8]}'

        # Order matters
        exp_serial = exp_wanted + exp_status
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        response, err_code = self.rs.read_serial()

        # split_response will always return status as status even if wanted_cmd is 'operation'
        wanted_cmd = 'liftRef1'
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(response, wanted_cmd)

        # make sure status contains two messages and wanted 1
        assert len(status) == 2
        assert len(wanted) == 1
        assert len(other) == 0

        # pack the responses in status list and see if matches what was read from serial "exp_serial"
        # packing order matters
        packed_wanted = ''
        packed_status = ''

        for msg in wanted:
            packed_wanted += str(msg).replace('\'', '\"')
        for msg in status:
            packed_status += str(msg).replace('\'', '\"')

        packed = packed_wanted + packed_status

        assert len(packed) == len(exp_serial.decode('utf-8'))
        assert len(packed_wanted) == len(exp_wanted.decode('utf-8'))
        assert len(packed_status) == len(exp_status.decode('utf-8'))
        assert packed == exp_serial.decode('utf-8')
        assert err_code == self.rsCodes.NO_ERR.name

    def test_split_response_other_signal(self, monkeypatch):
        """
        Test reading one 'operation' status message, one 'liftRef1' and one other
        """
        exp_wanted = b'{"cmd": "liftRef1", "data": "AR123456"}'
        exp_status = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_other = b'{"cmd": "gg", "type": 130, "data": [4, 5, 6, 8]}'

        # Order matters
        exp_serial = exp_wanted + exp_status + exp_other

        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        response, err_code = self.rs.read_serial()

        # split_response will always return status as status even if wanted_cmd is 'operation'
        wanted_cmd = 'liftRef1'
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(response, wanted_cmd)

        # make sure status contains two messages and wanted 1
        assert len(status) == 1
        assert len(wanted) == 1
        assert len(other) == 1

        # pack the responses in status list and see if matches what was read from serial "exp_serial"
        # packing order matters
        packed_wanted = ''
        packed_status = ''
        packed_other = ''

        for msg in wanted:
            packed_wanted += str(msg).replace('\'', '\"')
        for msg in status:
            packed_status += str(msg).replace('\'', '\"')
        for msg in other:
            packed_other += str(msg).replace('\'', '\"')

        packed = packed_wanted + packed_status + packed_other

        assert len(packed) == len(exp_serial.decode('utf-8'))
        assert len(packed_wanted) == len(exp_wanted.decode('utf-8'))
        assert len(packed_status) == len(exp_status.decode('utf-8'))
        assert len(packed_other) == len(exp_other.decode('utf-8'))
        assert packed == exp_serial.decode('utf-8')
        assert err_code == self.rsCodes.NO_ERR.name

    def test_split_response_fail_states(self):
        """
        Test different fail states of split_response
        """
        # Empty response string
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response('', 'liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == self.rsCodes.ARG_TYPE_ERR.name

        # Validate single  nonsense input (will fail to convert this into list)
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response('nonsense', 'liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == self.rsCodes.ARG_TYPE_ERR.name

        # Validate two nonsense inputs (will fail to convert this into list)
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response('{nonsense1}{nonsense2}', 'liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == self.rsCodes.ARG_TYPE_ERR.name

    def test_split_response_json_key_errors(self):
        """
        Text
        """
        no_err = self.rsCodes.NO_ERR.name
        error = self.rsCodes.JSON_KEY_ERR.name

        rsp = '{"cmd": "liftRef1", "data": "AR123456"}'
        json_rsp = json.loads(rsp)

        self.rs._Rs232Handler__decode_and_validate_serial_response = mock.MagicMock(return_value=[json_rsp, error])
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(rsp, 'liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == error

        # ----------------------------

        rsp_stat = '{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        rsp_obj = '{"cmd": "liftRef1", "data": "AR123456"}'
        json_rsp_stat = json.loads(rsp_stat)
        json_rsp_obj = json.loads(rsp_obj)
        full_rsp = rsp_stat + rsp_obj

        self.rs._Rs232Handler__decode_and_validate_serial_response = mock.MagicMock(
            side_effect=[[json_rsp_stat, no_err], [json_rsp_obj, error]])
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(full_rsp, 'liftRef1')
        assert status == [json_rsp_stat]
        assert wanted == -1
        assert other == -1
        assert err_code == error

        # ----------------------------

        rsp_stat_1 = '{"cmd": "operation", "type": 130, "data": [1, 2, 3, 4]}'
        rsp_obj = '{"cmd": "liftRef1", "data": "AR123456"}'
        rsp_other = '{"cmd": "gg", "type": 130, "data": [4, 5, 6, 8]}'
        rsp_stat_2 = '{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        json_rsp_stat_1 = json.loads(rsp_stat_1)
        json_obj = json.loads(rsp_obj)
        json_other = json.loads(rsp_other)
        json_rsp_stat_2 = json.loads(rsp_stat_2)
        full_rsp = rsp_stat_1 + rsp_obj + rsp_other + rsp_stat_2

        self.rs._Rs232Handler__decode_and_validate_serial_response = mock.MagicMock(
            side_effect=[[json_rsp_stat_1, no_err],
                         [json_obj, no_err],
                         [json_other, no_err],
                         [json_rsp_stat_2, error]])
        status, wanted, other, err_code = self.rs._Rs232Handler__split_response(full_rsp, 'liftRef1')
        assert status == [json_rsp_stat_1]
        assert wanted == [json_obj]
        assert other == [json_other]
        assert err_code == error

    def test_get_latest_status(self):
        """
        Test receiving 130 signal
        """
        self.rs._Rs232Handler__write_status_to_file = mock.MagicMock(return_value=self.rsCodes.NO_ERR.name)

        # ----------------------------
        # Type missing in response
        mock_rsp_status = ['lollipop']
        mock_rsp_wanted = []
        mock_rsp_other = []
        signal = '130'
        mock_err_code = self.rsCodes.JSON_ERR.name
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=(mock_rsp_status,
                                                                             mock_rsp_wanted,
                                                                             mock_rsp_other,
                                                                             mock_err_code))
        rsp_status, name, err_code = self.rs.get_latest_status()
        assert rsp_status == mock_rsp_status
        assert name == self.rsCodes.SOURCE.value
        assert err_code == mock_err_code

        # -----------------------------------------------
        # Correct status right away
        exp_data = [1, 2, 3]
        mock_rsp_status = [json.loads(f'{{"cmd":"operation", "type":130, "data":{exp_data}}}')]
        mock_rsp_wanted = []
        mock_rsp_other = []
        mock_err_code = self.rsCodes.NO_ERR.name
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=(mock_rsp_status,
                                                                             mock_rsp_wanted,
                                                                             mock_rsp_other,
                                                                             mock_err_code))
        rsp, name, err_code = self.rs.get_latest_status()
        assert rsp == exp_data
        assert name == self.rsCodes.SOURCE.value
        assert err_code == mock_err_code

        # ------------------------------------------
        # No status received
        mock_rsp_status = []
        mock_rsp_wanted = []
        mock_rsp_other = json.loads('{"cmd": "liftRef1", "data": "AR123456"}')
        mock_err_code = self.rsCodes.NO_ERR.name
        self.rs.get_signal_from_serial_buffer = mock.MagicMock()
        self.rs.get_signal_from_serial_buffer.side_effect = [(mock_rsp_status,
                                                              mock_rsp_wanted,
                                                              mock_rsp_other,
                                                              mock_err_code)]
        rsp, name, err_code = self.rs.get_latest_status()
        assert rsp == -1
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.STATUS_ERR.name

    def test_write_serial_errors(self):
        """
        Test write_serial fail states
        """
        # Mock sets serial available to FALSE
        # Test no serial available
        exp_cmd = exp_signal_type = exp_data = -1
        exp_name = self.rsCodes.SOURCE.value
        exp_code = self.rsCodes.SERIAL_COM_ERR.name
        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=False)

        cmd, signal_type, data, name, err_code = self.rs.write_serial('unittest')

        assert cmd == exp_cmd
        assert signal_type == exp_signal_type
        assert data == exp_data
        assert name == exp_name
        assert err_code == exp_code

        # Test validate_serial_inputs fail
        self.rs._Rs232Handler__serial_available.return_value = True
        self.rs._Rs232Handler__validate_serial_inputs = mock.MagicMock(return_value=[-1,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     self.rsCodes.ARG_TYPE_ERR.name])

        cmd, signal_type, data, name, err_code = self.rs.write_serial('unittest')
        exp_code = self.rsCodes.ARG_TYPE_ERR.name

        assert cmd == exp_cmd
        assert signal_type == exp_signal_type
        assert data == exp_data
        assert name == exp_name
        assert err_code == exp_code

        # Test when an invalid command falls through validate_serial_inputs
        exp_code = self.rsCodes.ARGS_IN_ELEM_ATTR_ERR.name
        exp_cmd = 'bad_cmd'
        self.rs._Rs232Handler__validate_serial_inputs = mock.MagicMock(return_value=[exp_cmd,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     -1,
                                                                                     self.rsCodes.NO_ERR.name])

        cmd, signal_type, data, name, err_code = self.rs.write_serial('unittest')

        assert cmd == exp_cmd
        assert signal_type == exp_signal_type
        assert data == exp_data
        assert name == exp_name
        assert err_code == exp_code

    def test_get_signal_from_serial_buffer_success(self, monkeypatch):
        """
        Test when wanted signal and status are found in buffer
        """
        exp_wanted = b'{"cmd": "liftRef1", "data": "AR123456"}'
        exp_status = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_status += b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_other = b'{"cmd": "gg", "type": 130, "data": [4, 5, 6, 8]}'

        # Order matters here
        exp_serial = exp_wanted + exp_status + exp_other

        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])

        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('liftRef1')

        assert len(status) == 2
        assert len(wanted) == 1
        assert len(other) == 1

        assert str(status[0]).replace('\'', '\"') + str(status[1]).replace('\'', '\"') == exp_status.decode('utf-8')
        assert str(wanted[0]).replace('\'', '\"') == exp_wanted.decode('utf-8')
        assert str(other[0]).replace('\'', '\"') == exp_other.decode('utf-8')
        assert err_code == self.rsCodes.NO_ERR.name

        # ---------------------------------

        exp_status = b'{"cmd": "operation", "type": 130, "data": [4, 5, 6, 7]}'
        exp_serial = exp_status
        self.patch_serial(exp_serial, monkeypatch)
        self.rs.client.in_waiting = _SeqInt([len(exp_serial), len(exp_serial), 0, 0])
        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('operation', '130')

        assert len(status) == 1
        assert len(wanted) == 0
        assert len(other) == 0

        assert str(status[0]).replace('\'', '\"') == exp_status.decode('utf-8')
        assert wanted == ''
        assert other == ''
        assert err_code == self.rsCodes.NO_ERR.name

    def test_get_signal_from_serial_buffer_fail_states(self):
        """
        Test fail states when reading signal from buffer
        """
        # Mock write_status_to_file so no unnecessary files are created
        self.rs.write_status_to_file = mock.MagicMock(return_value=['', True])

        # Read_serial fail
        exp_error = self.rsCodes.SERIAL_COM_ERR.name
        self.rs.read_serial = mock.MagicMock(return_value=['', exp_error])
        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == exp_error

        # Split_response fails due to empty string
        exp_error = self.rsCodes.ARG_TYPE_ERR.name
        self.rs.read_serial.return_value = ['', self.rsCodes.NO_ERR.name]
        self.rs._Rs232Handler__split_response = mock.MagicMock(return_value=[-1, -1, -1, exp_error])
        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == exp_error

        # No wanted_cmd found
        exp_error = self.rsCodes.SERIAL_COM_ERR.name
        self.rs.read_serial.return_value = ['', self.rsCodes.NO_ERR.name]
        self.rs._Rs232Handler__split_response = mock.MagicMock(return_value=['', '', '', self.rsCodes.NO_ERR.name])
        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('liftRef1')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == exp_error

        # Partial error when getOpenCount cmd has no response
        exp_error = self.rsCodes.PARTIAL_ERR.name
        self.rs.read_serial.return_value = ['', self.rsCodes.NO_ERR.name]
        self.rs._Rs232Handler__split_response = mock.MagicMock(return_value=['', '', '', self.rsCodes.NO_ERR.name])
        status, wanted, other, err_code = self.rs.get_signal_from_serial_buffer('getOpenCount')
        assert status == -1
        assert wanted == -1
        assert other == -1
        assert err_code == exp_error

    def test_get_liftRef1(self):
        """
        Test to check that get liftRef1 works
        """
        # Test the case when everything works fine
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "liftRef1", "data": "test_liftRef1123"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        response, name, error = self.rs.get_generic_text('liftRef1')
        assert response == ['test_liftRef1123']
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test the case when no response is received
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1, -1, -1,
                                                                             self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.get_generic_text('liftRef1')
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.get_generic_text('liftRef1')
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

    def test_get_ar_version(self):
        """
        Test to check that ar version works
        """
        # Test the case when everything works fine
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        exp_data = [1, 3, 1, 2]
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "version", "data": exp_data}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        response, name, error = self.rs.get_ar_version()
        assert response == exp_data
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test the case when no response is received
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1, -1, -1,
                                                                             self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.get_ar_version()
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.get_ar_version()
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

    def test_validate_input_filetype(self):
        """
        Test validation of arguments
        """
        corr_args = ['0x10']
        no_list_args = '0x10'
        to_many_arg = ['0x10', '0x0E']
        faulty_val_args = ['abc']

        res = self.rs._Rs232Handler__validate_input_filetype(corr_args, 1)
        assert res == self.rsCodes.NO_ERR.name

        res = self.rs._Rs232Handler__validate_input_filetype(no_list_args, 1)
        assert res == self.rsCodes.ARGS_IN_LEN_ERR.name

        res = self.rs._Rs232Handler__validate_input_filetype(to_many_arg, 1)
        assert res == self.rsCodes.ARGS_IN_LEN_ERR.name

        res = self.rs._Rs232Handler__validate_input_filetype(faulty_val_args, 1)
        assert res == self.rsCodes.ARGS_IN_ELEM_INT_ERR.name

    def test_get_logfile(self):
        """
        Test to check that get logfile works
        """
        args = ['0x10','2']
        exp_fname = "1000_AR12345_20220404.eventlog"
        exp_fname_error = "file_error"
        # Test the case when everything works fine

        self.rs.write_serial = mock.MagicMock(return_value=
                                              [-1,
                                               -1,
                                               -1,
                                               -1,
                                               self.rsCodes.NO_ERR.name])

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        self.rs._Rs232Handler__write_log_to_file = mock.MagicMock(return_value=
                                                                  [exp_fname,
                                                                   self.rsCodes.NO_ERR.name])

        fname, name, error = self.rs.get_logfile(args)
        assert fname == exp_fname
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test the case when write serial fails
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name]
        #
        fname, name, error = self.rs.get_logfile(args)
        assert fname == exp_fname_error
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.NO_ERR.name]
        self.rs.get_signal_from_serial_buffer.return_value = [-1, [{"logs": "123"}], -1,
                                                              self.rsCodes.SERIAL_COM_ERR.name]

        fname, name, error = self.rs.get_logfile(args)
        assert fname == exp_fname_error
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when faulty format in args
        # self.rs._Rs232Handler__validate_serial_inputs.return_values = [self.rsCodes.ARGS_IN_LEN_ERR.name]
        args = '0x10' + '4'
        self.rs.get_signal_from_serial_buffer.return_value = [-1, -1, -1, self.rsCodes.NO_ERR.name]

        fname, name, error = self.rs.get_logfile(args)
        assert fname == exp_fname_error
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test the case when to faulty file type format in args
        # self.rs._Rs232Handler__validate_input.return_value = [self.rsCodes.ARGS_IN_ELEM_INT_ERR]

        args = ['abc','2']
        fname, name, error = self.rs.get_logfile(args)
        assert fname == exp_fname_error
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.ARGS_IN_ELEM_INT_ERR.name

        # Test the case when wrong file type
        faulty_args = ['0x0F','8']
        fname, name, error = self.rs.get_logfile(faulty_args)
        assert fname == exp_fname_error
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_TYPE_ERR.name

    def test_read_1k_file(self):
        """
        Test to check that 1k files can be read
        """
        file_name = "/aritco/door"

        args = [file_name]
        exp_data = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        exp_1k_file_data = [
            {'cmd': 'readFile', "name": "/aritco/door", "data": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "err": 0}]

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'readFile',
                                                                               'name': '/aritco/door',
                                                                               'data': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                                                        0], 'err': 0}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)

        assert read_data == exp_1k_file_data
        assert data == exp_data
        assert name_1k_file == file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.NO_ERR.name

        # Test json key error
        args = [file_name]
        exp_data = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        exp_1k_file_data = [
            {'cmd': 'readFile', "name": "/aritco/door", "not_data": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "err": 0}]

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'readFile',
                                                                               'name': '/aritco/door',
                                                                               'not_data': [0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                                                            0, 0, 0], 'err': 0}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)

        assert read_data == exp_1k_file_data
        assert data == -1
        assert name_1k_file == file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.JSON_KEY_ERR.name

        # Test when invalid number of args are sent to read_1k_file

        args = []
        exp_data = -1

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             -1
                                                                             - 1,
                                                                             self.rsCodes.NO_ERR.name])

        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)

        assert read_data == -1
        assert data == exp_data
        assert name_1k_file == -1
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test the case when write serial fails
        args = [file_name]
        exp_data = -1

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])

        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)
        assert data == exp_data
        assert read_data == -1
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case no data was read from serial buffer
        args = [file_name]
        exp_data = -1

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(
            return_value=[-1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])

        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)

        assert read_data == -1
        assert data == exp_data
        assert name_1k_file == file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when it's not able to read from file or defaultfile
        args = [file_name]
        exp_data = -1
        exp_1k_file_data = [
            {'cmd': 'readFile', 'name': '/aritco/door', 'data': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'err': -1}]

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(
            return_value=[-1,
                          [{'cmd': 'readFile',
                            'name': '/aritco/door',
                            'data': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                            'err': -1}],
                          -1,
                          self.rsCodes.NO_ERR.name])
        read_data, data, name_1k_file, name, err_code = self.rs.read_1k_file(args)

        assert read_data == exp_1k_file_data
        assert data == exp_data
        assert name_1k_file == file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.DATA_ERR.name

    def test_write_1k_file(self):
        """
        Test to write to 1k files
        """
        cmd = "writeFile"
        exp_file_name = "/aritco/door"

        # No Error
        data_in = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        args = [exp_file_name, data_in]

        self.rs.write_serial = mock.MagicMock(return_value=[cmd, -1, data_in, self.rsCodes.SOURCE.value,
                                                            self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'writeFile',
                                                                               'name': '/aritco/door',
                                                                               'err': 0}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == exp_file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.NO_ERR.name

        # Test when invalid number of arguments are sent to write_1k_file
        args = [exp_file_name]

        self.rs.write_serial = mock.MagicMock(return_value=[cmd, -1, -1, self.rsCodes.SOURCE.value,
                                                            self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'writeFile',
                                                                               'name': '/aritco/door',
                                                                               'err': 0}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == -1
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.ARGS_IN_LEN_ERR.name

        # Test when invalid data in argument is sent to write_1k_file
        data_in = {"data": {1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0}}
        args = [exp_file_name, data_in]

        self.rs.write_serial = mock.MagicMock(return_value=[cmd, -1, -1, self.rsCodes.SOURCE.value,
                                                            self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             -1,
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == exp_file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.JSON_ERR.name

        # Test the case when write serial fails
        data_in = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        args = [exp_file_name, data_in]

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, self.rsCodes.SOURCE.value,
                                                            self.rsCodes.SERIAL_COM_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'writeFile',
                                                                               'name': '/aritco/door',
                                                                               'err': 0}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == exp_file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.SERIAL_COM_ERR.name

        #  Test the case no data was read from serial buffer
        data_in = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        args = [exp_file_name, data_in]

        self.rs.write_serial = mock.MagicMock(
            return_value=[cmd, -1, data_in, self.rsCodes.SOURCE.value, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             -1,
                                                                             -1,
                                                                             self.rsCodes.SERIAL_COM_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == exp_file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when it's not able to write file
        data_in = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        args = [exp_file_name, data_in]

        self.rs.write_serial = mock.MagicMock(return_value=[cmd, -1, data_in, self.rsCodes.SOURCE.value,
                                                            self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1,
                                                                             [{'cmd': 'writeFile',
                                                                               'name': '/aritco/door',
                                                                               'err': -1}],
                                                                             -1,
                                                                             self.rsCodes.NO_ERR.name])

        file_name, name, err_code = self.rs.write_1k_file(args)

        assert file_name == exp_file_name
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.DATA_ERR.name

    def test_write_generic_text(self):
        """
        Test all types of error and success of write_generic_text
        """
        # Test non supported package
        data, name, error = self.rs.write_generic_text(['mumbo_jumbo', 'ar_nr'])
        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.CMD_NOT_SUPPORTED.name

        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftRef1', 'ar_nr'])
        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.NO_ERR.name]
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftRef1', 'ar_nr'])
        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when requested object id doesn't correspond to actual liftRef1
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "liftRef1", "data": "not_ar_nr"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftRef1', 'ar_nr'])
        assert data == 'not_ar_nr'
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_TYPE_ERR.name

        # Test successful writes
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "liftRef1", "data": "ar_nr"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftRef1', 'ar_nr'])
        assert data == 'ar_nr'
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "liftRef2", "data": "some_type"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftRef2', 'some_type'])
        assert data == 'some_type'
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "liftName", "data": "some_name"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        data, name, error = self.rs.write_generic_text(['liftName', 'some_name'])
        assert data == 'some_name'
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

    def test_set_time(self):
        """
        Test successful and unsuccessful tests of set_RTC

        The lowest value the RTC epoch time can be set to is 978307200 "1/1/2021"
        """
        # Successful test
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "time", "updated": "true"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        updated, name, error = self.rs.handle_sync_time_request(["978307200"])
        assert updated == 'true'
        assert name == SyncTimeCode.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Unsuccessful test
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "time", "updated": "false"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        updated, name, error = self.rs.handle_sync_time_request(["978307200"])
        assert updated == 'false'
        assert name == SyncTimeCode.SOURCE.value
        assert error == SyncTimeCode.EPOCH_TIME_ERR.name

        # Wrong input format
        updated, name, error = self.rs.handle_sync_time_request(["a"])
        assert updated == -1
        assert name == SyncTimeCode.SOURCE.value
        assert error == self.rsCodes.ARG_TYPE_ERR.name

    def test_child_lock(self):
        """
        Test the childLock cmd
        """
        # Test the case when everything works fine
        exp_data = "on"
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_data, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "childLock", "data": exp_data}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        response, name, error = self.rs.set_child_lock(exp_data)
        assert response == exp_data
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test when set to on but received off
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_data, -1, self.rsCodes.NO_ERR.name])
        resp_data = "off"
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "childLock", "data": resp_data}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        response, name, error = self.rs.set_child_lock(exp_data)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_ERR.name

        # Test the case when no response is received
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=[-1, -1, -1,
                                                                             self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.set_child_lock(exp_data)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_data, -1, self.rsCodes.SERIAL_COM_ERR.name])
        response, name, error = self.rs.set_child_lock(exp_data)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test if the signal is more than 2 elements
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_data, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "childLock", "data": ['on', 'off']}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        response, name, error = self.rs.set_child_lock(exp_data)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_TYPE_ERR.name

    def test_floor_lock(self):
        """
        Test floorLock cmd
        """
        # Test when everything works OK
        exp_floors = [2,4]
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_floors, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "floorLock", "data":exp_floors}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        response, name, error = self.rs.set_floor_lock(str(exp_floors))

        print(f"utest response value {response}: type {type(response)}")

        assert response == exp_floors
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test the case when exp_floors are different from repsonse
        exp_floors = [1, 3, 5]
        rsp_floors = [1, 2, 5]
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_floors, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "floorLock", "data": rsp_floors}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        response, name, error = self.rs.set_floor_lock(exp_floors)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.FLOOR_LOCK_ERR.name

        # Test the case when no response is received
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1, -1, -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])

        response, name, error = self.rs.set_floor_lock(exp_floors)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, exp_floors, -1, self.rsCodes.SERIAL_COM_ERR.name])

        response, name, error = self.rs.set_floor_lock(exp_floors)
        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

    def test_set_oil_level(self):
        """
        Test oilLevel cmd
        """
        #Test when everything works OK
        old_oil_value = "45"
        new_oil_value = "95"
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, new_oil_value, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd":"oilLevel", "data": old_oil_value}],
                                                               -1,
                                                               self.rsCodes.NO_ERR.name])

        response, name, error = self.rs.set_oil_level(new_oil_value, old_oil_value)

        assert response == [old_oil_value]
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

        # Test when response from U1 is not the old value
        faulty_oil_value = "77"

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, new_oil_value, -1, self.rsCodes.NO_ERR.name])
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd":"oilLevel", "data": faulty_oil_value}],
                                                               -1,
                                                               self.rsCodes.NO_ERR.name])

        response, name, error =self.rs.set_oil_level(new_oil_value, old_oil_value)

        assert response == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_ERR.name

    def test_get_available_params(self):
        """
        Test test_get_available_params
        """
        # Test successful call
        self.rs.tl.available_params = mock.MagicMock(return_value=[1, 3, 4])
        resp, name, err_code = self.rs.get_available_params()

        assert resp == "1x3x4"
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.NO_ERR.name

        # Test no params in db
        self.rs.tl.available_params = mock.MagicMock(return_value=[])
        resp, name, err_code = self.rs.get_available_params()

        assert resp == "0"
        assert name == self.rsCodes.SOURCE.value
        assert err_code == self.rsCodes.NO_PARAMS_IN_DB.name

    def test_reset_service_memory(self):
        """
        Test all types of error and success of reset_service_memory
        """
        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        name, error = self.rs.reset_service_memory()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.NO_ERR.name]
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])
        name, error = self.rs.reset_service_memory()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test successful write
        data_raw = []
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "operation", "type": 132, "data": data_raw}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        name, error = self.rs.reset_service_memory()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

    def test_vfd_clear_table(self):
        """
        Test all types or error and sucess of vfe_clear_table
        """
        # Test the case where write fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        name, error = self.rs.vfd_clear_table()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.NO_ERR.name]
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])
        name, error = self.rs.vfd_clear_table()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test successful write
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "vfdClearTable"}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        name, error = self.rs.vfd_clear_table()
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name


    def test_set_vfd_id_1k(self):
        """
        Test all types or error and success of set_vfd_id
        """
        # Test the case where repackages from hyphen to comma fails due to faulty data format
        self.rs._Rs232Handler__repackage_status = mock.MagicMock(return_value=
                                                                 ["",
                                                                  self.rsCodes.DATA_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k([0x10-0x20])
        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.ARG_TYPE_ERR.name

        # Test the case where write fails
        self.rs._Rs232Handler__repackage_status = mock.MagicMock(return_value=
                                                       ["0x10,0x20",
                                                       self.rsCodes.NO_ERR.name])

        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.NO_ERR.name])

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test invalid error code
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd":"vfdId","data":"0x10,0x20","error":3}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == "0x10-0x20"
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.JSON_VALUE_TYPE_ERR.name

        # Test with timeout response (error=1)

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd":"vfdId","data":"0x10,0x20","error":1}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == "0x10-0x20"
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.VFD_TIMEOUT_ERR.name

        # Test with no power response (error=2)

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "vfdId", "data": "0x10,0x20", "error": 2}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == "0x10-0x20"
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.VFD_NO_PWR_ERR.name

        # Test successful write

        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd":"vfdId","data":"0x10,0x20","error":0}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])

        data, name, error = self.rs.set_vfd_id_1k(["0x10-0x20"])

        assert data == "0x10-0x20"
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

    def test_get_operation_package(self):
        """
        Test all types of error and success of get_operation_package
        """
        operation_package = '2'
        # Test the case when write serial fails
        self.rs.write_serial = mock.MagicMock(return_value=[-1, -1, -1, -1, self.rsCodes.SERIAL_COM_ERR.name])
        program_info, name, error = self.rs.get_operation_package(operation_package)
        assert program_info == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test the case when no response is received
        self.rs.write_serial.return_value = [-1, -1, -1, -1, self.rsCodes.NO_ERR.name]
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                -1,
                                                                -1,
                                                                self.rsCodes.SERIAL_COM_ERR.name])
        program_info, name, error = self.rs.get_operation_package(operation_package)
        assert program_info == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.SERIAL_COM_ERR.name

        # Test empty data is received
        data_raw = []
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "operation", "type": 2, "data": data_raw}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        program_info, name, error = self.rs.get_operation_package(operation_package)
        assert program_info == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_TYPE_ERR.name

        # Test repackage data fail
        data_raw = 123
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "operation", "type": 2, "data": data_raw}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        program_info, name, error = self.rs.get_operation_package(operation_package)
        assert program_info == -1
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.DATA_TYPE_ERR.name

        # Test successful write
        data_raw = [5, 65, 243, 2, 0]
        exp_data = data_raw
        self.rs.get_signal_from_serial_buffer = mock.MagicMock(return_value=
                                                               [-1,
                                                                [{"cmd": "operation", "type": 2, "data": data_raw}],
                                                                -1,
                                                                self.rsCodes.NO_ERR.name])
        program_info, name, error = self.rs.get_operation_package(operation_package)
        assert program_info == exp_data
        assert name == self.rsCodes.SOURCE.value
        assert error == self.rsCodes.NO_ERR.name

    def test_repackage_status(self):
        # Test successful repackaging
        status = [{'cmd': 'operation', 'data': [1, 2, 3, 4], 'type': 130},
                  {'cmd': 'operation', 'data': [4, 5, 6, 7], 'type': 130}]
        exp_data_last = [4, 5, 6, 7]

        data_last, err_code = self.rs._Rs232Handler__repackage_status(status)
        assert data_last == exp_data_last
        assert err_code == self.rsCodes.NO_ERR.name

        # Test reformat fail
        status = [{'cmd': 'operation', 'data': 2, 'type': 130},
                  {'cmd': 'operation', 'data': 5, 'type': 130}]
        exp_data_last = ""

        data_last, err_code = self.rs._Rs232Handler__repackage_status(status)
        assert data_last == exp_data_last
        assert err_code == self.rsCodes.ARG_TYPE_ERR.name

        # Test empty status string
        status = ""
        data_last, err_code = self.rs._Rs232Handler__repackage_status(status)
        assert data_last == ""
        assert err_code == self.rsCodes.STATUS_ERR.name

        # Test 130 and 135 package
        status = [{'cmd': 'operation', 'data': [1, 2, 3, 4], 'type': 130},
                  {'cmd': 'operation', 'data': [5, 6, 7, 8], 'type': 135}]
        exp_data_last = [5, 6, 7, 8]

        data_last, err_code = self.rs._Rs232Handler__repackage_status(status)
        assert data_last == exp_data_last
        assert err_code == self.rsCodes.NO_ERR.name


    def test_write_serial(self):
        """
        Test of serial write
        """

        self.rs._Rs232Handler__serial_available = mock.MagicMock(return_value=True)
        # Test of non supported command introduced after __validate_serial_input
        # -----------------------
        cmd = "obj_id"
        operation_type = "lol"
        data = "ipop"
        file_name = ""
        id = ""
        interval = ""
        self.rs._Rs232Handler__validate_serial_inputs = mock.MagicMock(
            return_value=[cmd, operation_type, data, file_name, id, interval, self.rsCodes.NO_ERR.name])
        args_in = [cmd]
        cmd_rsp, signal_type_rsp, data_rsp, name_rsp, err_code_rsp = self.rs.write_serial(args_in)
        assert cmd_rsp == cmd
        assert signal_type_rsp == operation_type
        assert data_rsp == data
        assert name_rsp == self.rsCodes.SOURCE.value
        assert err_code_rsp == self.rsCodes.ARGS_IN_ELEM_ATTR_ERR.name

        # Test of supported command introduced after __validate_serial_input
        # -----------------------
        cmd = "liftRef1"
        operation_type = "loli"
        data = "pop"
        file_name = ""
        self.rs._Rs232Handler__validate_serial_inputs = mock.MagicMock(
            return_value=[cmd, operation_type, data, file_name, id, interval, self.rsCodes.NO_ERR.name])
        args_in = [cmd]
        cmd_rsp, signal_type_rsp, data_rsp, name_rsp, err_code_rsp = self.rs.write_serial(args_in)
        assert cmd_rsp == cmd
        assert signal_type_rsp == operation_type
        assert data_rsp == data
        assert name_rsp == self.rsCodes.SOURCE.value
        assert err_code_rsp == self.rsCodes.NO_ERR.name

        # Test of supported command introduced after __validate_serial_input
        # -----------------------
        cmd = "operation"
        operation_type = "130"
        data = "[4, 5, 6, 7]"
        file_name = ""
        self.rs._Rs232Handler__validate_serial_inputs = mock.MagicMock(
            return_value=[cmd, operation_type, data, file_name, id, interval, self.rsCodes.NO_ERR.name])
        args_in = [cmd, operation_type, data]
        cmd_rsp, signal_type_rsp, data_rsp, name_rsp, err_code_rsp = self.rs.write_serial(args_in)
        assert cmd_rsp == cmd
        assert signal_type_rsp == operation_type
        assert data_rsp == data
        assert name_rsp == self.rsCodes.SOURCE.value
        assert err_code_rsp == self.rsCodes.NO_ERR.name

    def test_poll_lift_success(self):
        """
        Test poll_lift success
        """
        no_err = self.rs.rs232Codes.NO_ERR.name
        dummy_value = '123'
        dummy_file_name = '456'
        dummy_data_value = '789'
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        self.rs.get_operation_package = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=True)

        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[['doorOpenCount'], no_err])

        # Mock get_updated_params to return package nr as updated param, except for virtual params where
        # 'virtual_return' is returned.
        virtual_return = 'virtual'
        mock_gup = lambda signal, resp=[]: [[signal], no_err] if isinstance(signal, str) else [[virtual_return], no_err]
        self.rs.tl.get_updated_params = mock.MagicMock(side_effect=mock_gup)

        args = ['1']
        response, name, err_code = self.rs.poll_lift(args)

        # get_updated_params is mocked to return the package_nr for each package (except virtual)
        assert response.split(self.rs.data_sep) == self.rs.polled_packages + [str(virtual_return)]
        assert name == self.rs.name
        assert err_code == self.rs.rs232Codes.NO_ERR.name

    def test_poll_lift_one_file_package(self):
        """
        Test poll sequence with only one file packages per poll
        """
        no_err = self.rs.rs232Codes.NO_ERR.name
        dummy_value = '123'
        dummy_file_name = '456'
        dummy_data_value = '789'
        file_packages = ['readFileParam', 'readFileIntern', 'readFileNode', 'readFileLock', 'readFileDoor']
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        self.rs.get_operation_package = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=True)
        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[['doorOpenCount'], no_err])

        # Mock get_updated_params to return package nr as updated param, except for virtual params where
        # 'virtual_return' is returned.
        virtual_return = 'virtual'
        mock_gup = lambda signal, resp=[]: [[signal], no_err] if isinstance(signal, str) else [[virtual_return], no_err]
        self.rs.tl.get_updated_params = mock.MagicMock(side_effect=mock_gup)

        args = ['0']
        response, name, err_code = self.rs.poll_lift(args)
        remaining_file_packages = file_packages[:]

        for i in range(len(file_packages)):

            response, name, err_code = self.rs.poll_lift(args)

            for pack in self.rs.polled_packages:
                if pack in file_packages:
                    remaining_file_packages.remove(pack)

        assert (len(remaining_file_packages) == 0)

    def test_poll_list_one_file_package_order(self):
        """
        Test when not full poll test the order of file_packages
        """
        no_err = self.rs.rs232Codes.NO_ERR.name
        dummy_value = '123'
        dummy_file_name = '456'
        dummy_data_value = '789'
        file_packages = ['readFileParam', 'readFileIntern', 'readFileNode', 'readFileLock', 'readFileDoor']
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        self.rs.get_operation_package = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=True)

        no_of_test_poll = 12
        no_of_file_packages = len(file_packages)

        # Mock get_updated_params to return package nr as updated param, except for virtual params where
        # 'virtual_return' is returned.
        virtual_return = 'virtual'
        mock_gup = lambda signal, resp=[]: [[signal], no_err] if isinstance(signal, str) else [[virtual_return], no_err]
        self.rs.tl.get_updated_params = mock.MagicMock(side_effect=mock_gup)

        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[['doorOpenCount'], no_err])

        for poll in range(no_of_test_poll):
            args = ['0']
            file_pack = []
            response, name, err_code = self.rs.poll_lift(args)
            polled_pack = self.rs.polled_packages
            for curr_pack in polled_pack:
                if curr_pack in file_packages:
                    file_pack.append(curr_pack)
            assert len(file_pack) == 1
            assert file_pack[0] == file_packages[poll%no_of_file_packages]

    def test_poll_lift_failed_package(self):
        """
        Test poll_lift when one package fails
        """
        failed_package = '131'
        dummy_value = '321'
        dummy_file_name = '456'
        dummy_data_value = '789'
        no_err = self.rs.rs232Codes.NO_ERR.name
        # Mock get_liftRef1 since we are calling poll_lift
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        # Mock get_operation_package to fail on package 'failed_package' but succeed on all other packages.
        error_resp = [-1, self.rs.name, self.rs.rs232Codes.DATA_TYPE_ERR.name]

        mock_gup = lambda package: error_resp if package == failed_package else [package, self.rs.name, no_err]
        self.rs.get_operation_package = mock.MagicMock(side_effect=mock_gup)
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=True)
        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[['doorOpenCount'], no_err])

        # Mock get_updated_params to return package_nr, except for virtual params where 'virtual_return' is returned.
        virtual_return = 99
        mock_gop = lambda signal, resp=[]: [[signal], no_err] if isinstance(signal, int) else [[virtual_return], no_err]
        self.rs.tl.get_updated_params = mock.MagicMock(side_effect=mock_gop)

        args = ['1']
        response, name, err_code = self.rs.poll_lift(args)

        # Although package 'failed_package' is ignored these two lists are of equal
        # length due to virtual params being unpacked as well.
        assert len(response.split(self.rs.data_sep)) == len(self.rs.polled_packages)
        assert name == self.rs.name
        assert err_code == self.rs.rs232Codes.PARTIAL_ERR.name

    def test_poll_lift_no_updated_params(self):
        """
        Test poll_lift when there are no new params available
        """
        no_err = self.rs.rs232Codes.NO_ERR.name
        dummy_value = '123'
        dummy_file_name = '456'
        dummy_data_value = '789'
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_operation_package = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        self.rs.tl.get_updated_params = mock.MagicMock(return_value=[[], no_err])
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=True)
        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[[], no_err])

        args = ['1']
        response, name, err_code = self.rs.poll_lift(args)

        assert response == "0"
        assert name == self.rs.name
        assert err_code == self.rs.rs232Codes.NO_UPDATED_PARAMS.name

    def test_door_open_count_not_polled_for_low_version(self):
        """
        Test that doorOpenCount is not polled if version is too low.
        Setting get_door_open_count() to return an error but since check_if_above_or_equal_to_versions() is False it is
        not polled at all. If it was True, then we would get a PARTIAL_ERR from poll_lift().
        """
        no_err = self.rs.rs232Codes.NO_ERR.name
        dummy_value = '123'
        dummy_file_name = '456'
        dummy_data_value = '789'
        self.rs.get_generic_text = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_operation_package = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_ar_version = mock.MagicMock(return_value=[dummy_value, self.rs.name, no_err])
        self.rs.get_door_open_count = mock.MagicMock(return_value=[dummy_value, self.rs.name, self.rs.rs232Codes.PARTIAL_ERR])
        self.rs.read_1k_file = mock.MagicMock(
            return_value=[dummy_value, dummy_data_value, dummy_file_name, self.rs.name, no_err])
        self.rs.tl.get_updated_params = mock.MagicMock(return_value=[[], no_err])
        self.rs.check_if_above_or_equal_to_versions = mock.MagicMock(return_value=False)

        self.rs.get_updated_open_door_counter_parameters = mock.MagicMock(return_value=[[], self.rs.rs232Codes.NO_ERR])

        args = ['1']
        response, name, err_code = self.rs.poll_lift(args)

        # get_updated_params is mocked to return the package_nr for each package (except virtual)
        assert response == "0"
        assert name == self.rs.name
        assert err_code == self.rs.rs232Codes.NO_UPDATED_PARAMS.name

    def test_write_log_to_file_ok(self):
        """
        Test returning OK from __write_log_to_file
        """
        no_err = self.rsCodes.NO_ERR.name

        # Create a dummy file
        testfile = "dummy"
        f = open(testfile, 'w')
        data = {"key1": "value1",
                "key2": "value2"}

        with mock.patch('builtins.open') as my_mock, mock.patch('os.stat') as stat_mock, mock.patch(
                'os.path.isfile') as is_file_mock, mock.patch('os.path.exists') as path_exists_mock:
            stat_mock.return_value = FileStat()
            my_mock.return_value = f
            is_file_mock.return_value = False
            path_exists_mock.return_value = True

            self.rs.read_parameter = mock.MagicMock(return_value=['AR123456', 'name', no_err])

            fname, err_code = self.rs._Rs232Handler__write_log_to_file(data)
            assert err_code == no_err


        f = open(testfile, 'r')

        assert json.dumps(data) in f.readline()
        f.close()

        os.remove(testfile)
        assert not os.path.isfile(testfile)

    @mock.patch('os.path.exists')
    def test_write_log_to_file_nok(self, mock_pathexists):
        """
        Test returning NOK from write_log_to_file
        """
        # We don't need a dummy file handle here since we should never succeed in opening the file.
        # Mock 'open' and raise IOError when called

        error = IOError
        no_err = self.rsCodes.NO_ERR.name
        exp_code = self.rsCodes.LOG_FILE_IO_ERR.name

        data = {"key1": "value1", "key2": "value2"}

        mock_pathexists.return_value = True
        with mock.patch('builtins.open') as my_mock:
            my_mock.side_effect = error

            self.rs.read_parameter = mock.MagicMock(return_value=['AR123456', 'name', no_err])

            _, err_code = self.rs._Rs232Handler__write_log_to_file(data)
            assert err_code == exp_code

        # Mock 'open' and raise ValueError when called
        error = ValueError
        exp_code = self.rsCodes.LOG_FILE_EXCEPTION.name
        with mock.patch('builtins.open') as my_mock:
            my_mock.side_effect = error

            self.rs.read_parameter = mock.MagicMock(return_value=['AR123456', 'name', no_err])

            _, err_code = self.rs._Rs232Handler__write_log_to_file(data)
            assert err_code == exp_code

    @mock.patch('os.path.exists')
    @pytest.mark.skip(reason="File writing does not work as of now on Esseti-GW")
    def test_write_log_to_file_no_dir(self, mock_pathexists):
        """
        Test when log directory is not available and creation failed
        """
        data = {"key1": "value1", "key2": "value2"}
        no_err = self.rsCodes.NO_ERR.name
        mock_pathexists.return_value = False
        self.rs._RS232Handler__set_1000_log_file_dir = mock.MagicMock(return_value=False)

        self.rs.read_parameter = mock.MagicMock(return_value=['AR123456', 'name', no_err])
        _, err_code = self.rs._Rs232Handler__write_log_to_file(data)
        assert err_code == self.rsCodes.LOG_FILE_IO_ERR.name

    def test_write_log_to_file_create_dir(self):
        """
        Test the case when a dir doesn't exist but is created
        """
        data = {"key1": "value1", "key2": "value2"}
        no_err = self.rsCodes.NO_ERR.name
        testfile = "dummy"
        f = open(testfile, 'w')

        with mock.patch('builtins.open') as my_mock, mock.patch('os.stat') as stat_mock, mock.patch(
                'os.path.exists') as path_exist_mock, mock.patch('os.path.isfile') as is_file_mock:
            stat_mock.return_value = FileStat()
            my_mock.return_value = f
            path_exist_mock.return_value = True
            is_file_mock.return_value = False

            self.rs.read_parameter = mock.MagicMock(return_value=['AR123456', 'name', no_err])

            self.rs._RS232Handler__set_1000_log_file_dir = mock.MagicMock(return_value=True)

            _, err_code = self.rs._Rs232Handler__write_log_to_file(data)
            assert err_code == self.rsCodes.NO_ERR.name

        f.close()
        os.remove(testfile)

    def test_write_parameter(self):
        """
        Test everything through the write_parameter function, all fails all the way to the no err in the end
        """
        # Test argument validation
        args = [1]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.ARGS_IN_LEN_ERR.name

        args = [1, 2, 3]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.ARGS_IN_LEN_ERR.name

        args = ['abc', 1]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

        args = [1, 'abc']
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

        args = [1, [17]]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

        # Test the #backwardCompatibility
        self.rs.read_parameter = mock.MagicMock(return_value=['',
                                                                 self.rs.name,
                                                                 self.rs.rs232Codes.PARAM_NOT_SET.name])
        args = [69, 420]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.WRITE_PARAM_NOT_SUPPORTED_BY_1K.name

        # Mocking this to something OK, so we don't hit this error anymore
        self.rs.read_parameter = mock.MagicMock(return_value=['',
                                                                 self.rs.name,
                                                                 self.rs.rs232Codes.NO_ERR.name])

        # Test not getting an ok file back from get_file_for_param
        self.rs.tl.get_file_for_param = mock.MagicMock(return_value='')
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.WRITE_PARAM_NOT_IN_FILES.name

        # Mocking this to something OK, so we don't hit this error anymore
        self.rs.tl.get_file_for_param = mock.MagicMock(return_value='not_empty_string')

        # Test file read error
        self.rs.read_1k_file = mock.MagicMock(return_value=[[{}], '', '', '', self.rs.rs232Codes.DATA_ERR.name])
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.DATA_ERR.name

        self.rs.read_1k_file = mock.MagicMock(return_value=[[{}], '', '', '', self.rs.rs232Codes.LIST_INDEX_ERR.name])
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.LIST_INDEX_ERR.name

        # Testing not getting a good response from the readFile command
        self.rs.read_1k_file = mock.MagicMock(return_value=[[{"no_data_key": "rubbish"}], '', '', '', self.rs.rs232Codes.NO_ERR.name])
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.DATA_ERR.name

        # Testing not getting a good response from the write_1k_file command
        args = [97, 16]
        self.rs.read_1k_file = mock.MagicMock(return_value=[[{"data": [1, 2, 3, 4]}], '', '', '', self.rs.rs232Codes.NO_ERR.name])
        self.rs.write_1k_file = mock.MagicMock(return_value=["", "", self.rs.rs232Codes.DATA_ERR.name])
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.DATA_ERR.name

        # Test everything ok
        self.rs.write_1k_file = mock.MagicMock(return_value=["", "", self.rs.rs232Codes.NO_ERR.name])
        status, name, err = self.rs.write_parameter(args)
        assert status == 0
        assert name == self.rs.name
        assert err == self.rs.rs232Codes.NO_ERR.name

        # Test oil-level value Test limits (0, 100) and off-limits (-1, 101)
        # value = 0
        args = [10, 0]

        self.rs.read_parameter = mock.MagicMock(return_value=["", "", self.rs.rs232Codes.NO_ERR.name])
        self.rs.set_oil_level = mock.MagicMock(return_value=["", "", self.rs.rs232Codes.NO_ERR.name])

        status, name, err = self.rs.write_parameter(args)
        assert status == 0
        assert name == self.rsCodes.SOURCE.value
        assert err == self.rs.rs232Codes.NO_ERR.name

        #value 100
        args = [10, 100]

        status, name, err = self.rs.write_parameter(args)
        assert status == 0
        assert name == self.rsCodes.SOURCE.value
        assert err == self.rs.rs232Codes.NO_ERR.name

        # value -1
        args = [10, -1]

        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rsCodes.SOURCE.value
        assert err == self.rs.rs232Codes.DATA_ERR.name

        # value = 101
        args = [10, 101]
        status, name, err = self.rs.write_parameter(args)
        assert status == -1
        assert name == self.rsCodes.SOURCE.value
        assert err == self.rs.rs232Codes.DATA_ERR.name

    def test_check_if_above_or_equal_to_versions(self):
        self.rs.tl.database[self.rs.tl.params_2.MAIN_VERSION_2.value].value = 4
        self.rs.tl.database[self.rs.tl.params_2.SUB_VERSION_2.value].value = 6
        self.rs.tl.database[self.rs.tl.params_version.ARGATE_MAIN_VERSION.value].value = 1
        self.rs.tl.database[self.rs.tl.params_version.ARGATE_SUB_VERSION.value].value = 1

        assert self.rs.check_if_above_or_equal_to_versions(["0.0", "1.1"])
        assert self.rs.check_if_above_or_equal_to_versions(["0.0", "1.0"])
        assert not self.rs.check_if_above_or_equal_to_versions(["0.0", "1.2"])
        assert not self.rs.check_if_above_or_equal_to_versions(["0.0", "2.1"])
        assert not self.rs.check_if_above_or_equal_to_versions(["0.0", "2.0"])
        assert not self.rs.check_if_above_or_equal_to_versions(["0.0", "2.2"])
        assert self.rs.check_if_above_or_equal_to_versions(["0.0", "0.4"])

        assert self.rs.check_if_above_or_equal_to_versions(["4.6", "0.0"])
        assert not self.rs.check_if_above_or_equal_to_versions(["4.7", "0.0"])
        assert self.rs.check_if_above_or_equal_to_versions(["4.5", "0.0"])
        assert not self.rs.check_if_above_or_equal_to_versions(["5.0", "0.0"])
        assert self.rs.check_if_above_or_equal_to_versions(["3.12", "0.0"])

        assert self.rs.check_if_above_or_equal_to_versions(["4.6", "1.1"])



