#!/usr/bin/env python
import datetime
import logging
import sys
import os
import time
import serial
import json
import ast
from typing import Type, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from lib.sync_time_handler import SyncTimeHandler
from lib.error_signals import Rs232Code
from filemgmt.disk_handler import DiskHandler
from lib.thousand_lib import ThousandLib
from lib.logging_config import get_logger

logger = get_logger(__name__)


class Rs232Handler:

    def __init__(self, tl: ThousandLib) -> None:
        """Initializes the rs232 serial client and variables.

        Args:
            tl: ThousandLib instance (shared with LiftProxy).
        """
        self.rs232Codes = Rs232Code
        self.name: str = self.rs232Codes.SOURCE.value
        self.logger = logger
        self.dh = DiskHandler()
        self.rs_port: str = "/dev/ttyLP6"
        self.data_sep: str = 'x'
        self.serial_timeout: float = 0.5
        self.polled_file_package: int = 0
        self.saved_operation_notifications: list = []
        self.saved_vfdResult_notification: list = []
        self.door_closing_time_type: str = '135'
        self.status_type: str = '130'

        self.polled_packages: list = []
        self.supported_cmds: list = ['operation', 'liftRef1', 'liftRef2', 'liftName', 'version', 'oilLevel', 'logfile', 'time',
                               'readFile', 'writeFile', 'childLock', 'floorLock', 'vfdClearTable', 'vfdId', 'vfdRead', 'getOpenCount']
        self.always_polled_packages: list = ['liftRef1', 'liftRef2', 'liftName', 'version', '130', '2', '131', '134', '133', 'doorOpenCount']
        self.file_packages: list = ['readFileParam', 'readFileIntern', 'readFileNode', 'readFileLock', 'readFileDoor']
        self.notification_operation_packages: list = [self.door_closing_time_type, self.status_type]
        self.valid_file_names: list = ['/aritco/param', '/aritco/intern', '/aritco/node', '/aritco/lock', '/aritco/door']

        # These are the versions required for doorOpen commands to work for [U1, U16]
        self.doorOpenCount_version_limits: list = ["4.7", "1.2"]
        self.logfile_length_version_limits: list = ["4.7", "1.3"]

        self.tl: ThousandLib = tl

        self.client: serial.Serial | None = None
        try:
            self.client = serial.Serial(port=self.rs_port,
                                        baudrate=38400,
                                        parity=serial.PARITY_NONE,
                                        stopbits=serial.STOPBITS_ONE,
                                        bytesize=serial.EIGHTBITS)
        except Exception as error:
            logger.error(error)
            self.logger.error(f"Port f{self.rs_port} not found. Running on VM?")

    def __serial_available(self) -> bool:
        return self.client is not None

    def __set_1000_file_dir(self, file_path: str) -> bool:

        try:
            os.makedirs(file_path, exist_ok=True)
        except OSError as e:
            self.logger.error("Failed to create " + file_path + ". 1000 file will not be stored")
            self.logger.error(e)
            return False
        return True

    def handle_sync_time_request(self, time_value_list: list) -> tuple[Any, str, str]:
        sync_time_handler: SyncTimeHandler = SyncTimeHandler()
        return sync_time_handler.sync_time_rs232(time_value_list[0], self)

    def __validate_input_filetype(self, args: list, args_len: int) -> str:
        if not isinstance(args, list) or len(args) != args_len:
            self.logger.error(f"Error: not list or number of input arguments  {args} != {args_len}")
            return self.rs232Codes.ARGS_IN_LEN_ERR.name

        try:
            for x in args:
                if isinstance(x, str) and '0x' in x:
                    int(x,0)
                else:
                    int(x)
        except ValueError:
            self.logger.error("Error: could not convert args to int")
            return self.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

        return self.rs232Codes.NO_ERR.name

    def __validate_serial_inputs(self, args: list) -> tuple[Any,Any,Any,Any,Any,Any,str]:
        """
        Tests that signal that is about to be sent through to the AR-GATE is ok
        :param: args:
        :return: <cmd>, <operation_type>, <data>, <file_name>, <id>, <interval>, <err_code>
        """
        cmd_err: int = -1
        type_err: int = -1
        data_err: int = -1
        file_name_err: int = -1
        id_err: int = -1
        interval_err: int = -1

        if not isinstance(args, list):
            self.logger.error("Error: input argument must be list")
            return cmd_err, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARG_TYPE_ERR.name

        for k in args:
            if not isinstance(k, str):
                self.logger.error("Error: input elements must be strings")
                return cmd_err, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_ELEM_ATTR_ERR.name

        cmd: str = args[0]
        if cmd not in self.supported_cmds:
            self.logger.error(f"Error: cmd {cmd} not supported. Supported cmds: {self.supported_cmds}")
            return cmd_err, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.CMD_NOT_SUPPORTED.name

        operation_type: str = ""
        data: str = ""
        file_name: str = ""
        id: str | int = ""
        interval: str | int = ""

        if cmd == "operation":
            # Expect cmd, operation_type and data next in that order
            # Data will currently only exist for cmd write file.
            if not 2 <= len(args) <= 3:
                self.logger.error(f"Error: arguments list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            # Check if signal can be converted to int
            try:
                int(args[1])
                operation_type = args[1]
            except ValueError as error:
                self.logger.error("Error: signal operation_type could not be converted to int")
                self.logger.error(error)
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

            if len(args) == 3:
                data = args[2]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd in ["liftRef1", "liftRef2", "liftName"]:
            # Expect one more arg of data or no more args
            if not 1 <= len(args) <= 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            if len(args) == 2:
                data = args[1]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "version":
            # Expect AR-gate version, one argument.
            if len(args) != 1:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "getOpenCount":
            # Expect one argument to get number of times the door opens.
            if len(args) != 1:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "time":
            # Expect updated time, true or false
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            if len(args) == 2:
                data = args[1]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == 'oilLevel':
            if not 1 <= len(args) <= 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            if len(args) == 2:
                data = args[1]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "logfile":
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            if len(args) == 2:
                data = args[1]
                if 0 < int(data) > 64:
                    self.logger.error(f"Error: Invalid data value: {data}")
                    return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.DATA_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "readFile":
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            file_name = args[1]
            if file_name not in self.valid_file_names:
                self.logger.error(f"Error: Invalid file name {file_name}. Supported name: {self.valid_file_names}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.FILE_NAME_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "writeFile":
            if len(args) != 3:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name

            file_name = args[1]
            if file_name not in self.valid_file_names:
                self.logger.error(f"Error: Invalid file name {file_name}. Supported name: {self.valid_file_names}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.FILE_NAME_ERR.name

            try:
                write_request_dict = json.loads(args[2])
            except json.decoder.JSONDecodeError as e:
                self.logger.error(f"Failed to parse input as json. {e}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.JSON_ERR.name
            try:
                request_data = write_request_dict["data"]
            except KeyError as error:
                self.logger.error(f"Error. Unable to find expected key {error}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.JSON_KEY_ERR.name
            if not isinstance(request_data, list):
                self.logger.error("Error: Write data must be a list")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

            return cmd, type_err, request_data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "childLock":
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            data = args[1]
            if data not in ["on", "off"]:
                self.logger.error(f"Error: Not setting child lock with unsupported data: {data}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.DATA_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "floorLock":
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            data = args[1]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "vfdClearTable":
            if len(args) != 1:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            return cmd, "", "", "", id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "vfdId":
            if len(args) != 2:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            data = args[1]
            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        elif cmd == "vfdRead":
            if len(args) != 4:
                self.logger.error(f"Error: argument list length {len(args)}")
                return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.ARGS_IN_LEN_ERR.name
            try:
                id = int(args[1])
                data = args[2]
                interval = int(args[3])
            except ValueError as ve:
                self.logger.error("Error: Cannot convert id or interval arguments to int")
                return cmd, type_err, data_err, file_name_err, args[1], args[3], self.rs232Codes.ARGS_IN_ELEM_INT_ERR.name
            except Exception as error:
                self.logger.error(f"Error: Failed to read argument data: {error}")
                return cmd, type_err, data_err, file_name_err, args[1], args[3], self.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

            if not 0 <= id <= 7:
                self.logger.error(f"Error: Invalid ID number: {id}")
                return cmd, type_err, data_err, file_name_err, id, interval_err, self.rs232Codes.VFD_ID_ERR.name

            return cmd, operation_type, data, file_name, id, interval, self.rs232Codes.NO_ERR.name

        else:
            self.logger.error(f"Error: cmd: {cmd} is in supported cmd's list but not actually supported, how?")
            return cmd, type_err, data_err, file_name_err, id_err, interval_err, self.rs232Codes.CMD_NOT_SUPPORTED.name

    def __decode_and_validate_serial_response(self, rsp: str | dict) -> tuple[Any, str]:
        """
        Validate response from AR-GATE
        :param: rsp: (string or dict) Contains a JSON document, or an already parsed one
        :return: rsp_json: (dict) rsp as JSON object
        :return: err_code: (string)
        """
        if isinstance(rsp, dict):
            rsp_json: Any = rsp
        elif isinstance(rsp, str):
            try:
                rsp_json = json.loads(rsp)
            except Exception as error:
                self.logger.error("Error: Failed to convert response to json")
                self.logger.error(error)
                return rsp, self.rs232Codes.JSON_ERR.name
        else:
            self.logger.error("Error: Response not string")
            return rsp, self.rs232Codes.SERIAL_COM_ERR.name

        if not isinstance(rsp_json, dict):
            self.logger.error(f"Error: Managed to convert response but resulting type is: {type(rsp_json)}, not dict")
            return rsp, self.rs232Codes.JSON_ERR.name

        # What a response look like (today at least)
        # {"cmd":"operation","type":130,"data":[1,2,3]}
        # {"cmd":"operation","type":131,"data":[0,0,0,0,0,0,0, ..., 0]}
        # {"cmd":"operation","type":135,"data":[3,0,42,0]
        # {"cmd":"liftRef1","data":"AR111222"}
        # {"cmd":"time", "updated": "true"}
        # {"cmd":"oilLevel","data":75}
        # {"logs":[{"timeDelta":0,"lastRecord":4638,"HsopName":"ARK4","HsopVersion":"P32M","data":"9C....6E","firstRecord":4509}]}
        # {"cmd":"readFile","name":"/aritco/param","data":[1,2,23,23,....],"err":0}
        # {"cmd":"writeFile","name":"/aritco/param","err":0}
        # {"cmd":"vfdClearTable"}
        # {"cmd":"vfdId","data":"0x01,0x03,0x02,0x00,0x33,0xF8,0x51","error":0}
        # {"cmd":"vfdRead","id":0,"error":0}
        # {"cmd":"vfdResult":"id:0,"data":"0x10,0x20,0x30,0x40","timestamp":[201,5,20,3}

        try:
            if "logs" in rsp_json:
                if not isinstance(rsp_json["logs"], list):
                    self.logger.error("Error: Logs not list")
                    return rsp_json, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

            elif rsp_json["cmd"] == "time":
                if not isinstance(rsp_json["updated"], str):
                    self.logger.error("Error: time response not string")
                    return rsp_json, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

            elif rsp_json["cmd"] == "readFile":
                if rsp_json["name"] not in self.valid_file_names:
                    self.logger.error("Error: invalid file name")
                    return rsp_json, self.rs232Codes.DATA_TYPE_ERR.name

                if "data" not in rsp_json:
                    self.logger.error("Error: invalid json response")
                    return rsp_json, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

                if not isinstance((rsp_json["data"]), list):
                    self.logger.error("Error: Data is not in a list")
                    return rsp_json, self.rs232Codes.JSON_ERR.name

                if "err" not in rsp_json:
                    self.logger.error("Error: No error status in read 1k file response")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

            elif rsp_json["cmd"] == "writeFile":
                if rsp_json["name"] not in self.valid_file_names:
                    self.logger.error("Error: invalid file name")
                    return rsp_json, self.rs232Codes.DATA_TYPE_ERR.name

                if "err" not in rsp_json:
                    self.logger.error("Error: No error status in write 1k file response")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

            elif rsp_json["cmd"] == "vfdClearTable":
                if len(rsp_json) != 1:
                    return rsp_json, self.rs232Codes.ARGS_IN_LEN_ERR.name

            elif rsp_json["cmd"] == "vfdId":
                if len(rsp_json) != 3:
                    return rsp_json, self.rs232Codes.ARGS_IN_LEN_ERR.name

                if not isinstance(rsp_json["data"], str):
                    self.logger.error("Error: Faulty data type")
                    return  rsp_json, self.rs232Codes.DATA_TYPE_ERR.name

                if "error" not in rsp_json:
                    self.logger.error("Error: No error status in vfdId 1k response")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

                if rsp_json["error"] not in [0,1,2]:
                    self.logger.error("Error: Invalid VfdId error code")
                    return rsp_json, self.rs232Codes.DATA_ERR.name

            elif rsp_json["cmd"] == 'vfdRead':
                if len(rsp_json) != 3:
                    return rsp_json, self.rs232Codes.ARGS_IN_LEN_ERR.name

                if "id" not in rsp_json:
                    self.logger.error("Error: No id status in vfdRead 1k response")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

                if "error" not in rsp_json:
                    self.logger.error("Error: No error status in vfdRead 1k response")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

                if rsp_json["error"] not in [0,1]:
                    self.logger.error("Error: Invalid VfdRead error code")
                    return rsp_json, self.rs232Codes.DATA_ERR.name

            elif rsp_json["cmd"] == 'vfdResult':
                if len(rsp_json) != 4:
                    return rsp_json, self.rs232Codes.ARGS_IN_LEN_ERR.name

                if "id" not in rsp_json:
                    self.logger.error("Error: No Id in vfdResult 1k notification")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

                if not 0 <= rsp_json["id"] <= 7:
                    self.logger.error("Error: Id invalid value in vfdResult 1k notification")
                    return rsp_json, self.rs232Codes.VFD_ID_ERR.name

                if "timestamp" not in rsp_json:
                    self.logger.error("Error: No timestamp in vfdResult 1k notification")
                    return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

            else:
                rsp_cmd = rsp_json["cmd"]
                rsp_data = rsp_json["data"]
                # Cmd operation contains an extra field.
                if rsp_cmd == "operation":
                    rsp_type = rsp_json["type"]
                if not isinstance(rsp_cmd, str):
                    self.logger.error("Error: 'cmd' not string")
                    return rsp_json, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

        except KeyError as e:
            self.logger.error(f"Error: Unable to find expected key in json response: {e}")
            return rsp_json, self.rs232Codes.JSON_KEY_ERR.name

        return rsp_json, self.rs232Codes.NO_ERR.name

    def write_serial(self, args: list) -> tuple[Any, Any, Any, str, str]:
        """
        Write data on serial bus. If simulator is running, send to socket instead.
        :param: args: (list)
        :return: <cmd>, <operation_type>, <data>, <name>, <err_code>
        """
        if not self.__serial_available():
            self.logger.error("Error: Serial not available for write")
            return -1, -1, -1, self.name, self.rs232Codes.SERIAL_COM_ERR.name

        cmd, operation_type, data, file_name, id, interval, err_code = self.__validate_serial_inputs(args)
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to validate serial inputs.")
            return cmd, operation_type, data, self.name, err_code

        msg: str = ""
        if cmd == "operation":
            if data:
                msg = f'{{"cmd":"{cmd}","type":{operation_type},"data":{data}}}'
            else:
                msg = f'{{"cmd":"{cmd}","type":{operation_type}}}'
        elif cmd == "liftRef1" or cmd == "liftRef2" or cmd == "liftName" or cmd == 'oilLevel':
            if data:
                msg = f'{{"cmd":"{cmd}","data":"{data}"}}'
            else:
                msg = f'{{"cmd":"{cmd}"}}'
        elif cmd == "time":
            msg = f'{{"cmd":"{cmd}","data":"{data}"}}'
        elif cmd == "version":
            msg = f'{{"cmd":"{cmd}"}}'
        elif cmd == "getOpenCount":
            msg = f'{{"cmd":"{cmd}"}}'
        elif cmd == "logfile":
            # check U16 and U1 version
            if self.check_if_above_or_equal_to_versions(self.logfile_length_version_limits):
                msg = f'{{"cmd":"{cmd}","data":"{data}"}}'
                self.logger.debug(f'U16 SW version 1.3 or higher and U1 SW version 4.7 or higher. Writing {msg}')
            else:
                msg = f'{{"cmd":"{cmd}"}}'
                data = '0'
                self.logger.debug(f'U16 SW version 1.2 or lower and U1 SW version 4.6 or lower. Writing {msg}')
        elif cmd == "readFile":
            msg = f'{{"cmd":"{cmd}", "name":"{file_name}"}}'
        elif cmd == "writeFile":
            msg = f'{{"cmd":"{cmd}", "name":"{file_name}", "data":"{data}"}}'
        elif cmd == "childLock":
            msg = f'{{"cmd":"{cmd}", "data":"{data}"}}'
        elif cmd == "floorLock":
            msg = f'{{"cmd":"{cmd}", "data":"{data}"}}'
        elif cmd == "vfdClearTable":
            msg = f'{{"cmd":"{cmd}"}}'
        elif cmd == "vfdId":
            msg = f'{{"cmd":"{cmd}", "data":"{data}"}}'
        elif cmd == "vfdRead":
            msg = f'{{"cmd":"{cmd}", "id":{id}, "data":"{data}", "interval":{interval}}}'
        if not msg:
            self.logger.error("Error: Somehow unsupported cmd fell through validation.")
            return cmd, operation_type, data, self.name, self.rs232Codes.ARGS_IN_ELEM_ATTR_ERR.name

        self.logger.debug(f"Writing {msg}")
        assert self.client is not None
        self.client.write(msg.encode('utf-8'))

        return cmd, operation_type, data, self.name, err_code

    def read_serial(self) -> tuple[Any, Any]:
        """
        Reads the serial buffer. Retries 5 times if buffer is empty.
        :return: rsp_full: (string) Everything that was read from the buffer.
        :return: err_code:
        """
        if not self.__serial_available():
            self.logger.error("Error: Serial not available for read")
            return -1, self.rs232Codes.SERIAL_COM_ERR.name

        rsp: str = ''
        retries: int = 5
        max_iterations: int = 50
        i: int = 0
        iterations: int = 0
        assert self.client is not None
        while i < retries and iterations < max_iterations:
            iterations += 1
            try:
                waiting_bytes: int = self.client.in_waiting
                if waiting_bytes > 0:
                    rsp += self.client.read(size=waiting_bytes).decode('utf-8')
            except serial.SerialException as error:
                self.logger.error("Error: Serial read exception")
                self.logger.error(error)
                return -1, self.rs232Codes.SERIAL_COM_ERR.name
            except UnicodeDecodeError as error:
                self.logger.error(f"Error: Failed to decode serial bytes. Previous rsp: {rsp}")
                self.logger.error(error)
                return -1, self.rs232Codes.SERIAL_DECODE_ERR.name

            if rsp.endswith('}'):
                if not rsp.startswith('{'):
                    frame_start = rsp.find('{')
                    if frame_start == -1:
                        self.logger.error(f"Error: No frame start found in response, discarding: {rsp}")
                        return -1, self.rs232Codes.SERIAL_DECODE_ERR.name
                    self.logger.warning(f"Missing curly brace in beginning of rsp! Stripping away beginning of broken msg: "
                               f"{rsp[:frame_start]}. We should have gotten a decode error previously. Can't save this one")
                    rsp = rsp[frame_start:]

                return rsp, self.rs232Codes.NO_ERR.name

            if waiting_bytes > 0:
                # Progress made: reset the no-progress retry budget
                i = 0
            else:
                i += 1
                self.logger.debug(f"No new bytes, attempt {i}/{retries}")
            if i < retries:
                time.sleep(self.serial_timeout)

        if rsp:
            self.logger.error(f"Error: Incomplete frame after {retries} tries without progress, discarding: {rsp}")
            return -1, self.rs232Codes.SERIAL_DECODE_ERR.name
        self.logger.error(f"Error: No waiting bytes found after {retries} tries.")
        return -1, self.rs232Codes.NO_WAITING_BYTES_ERR.name

    def __split_response(self, rsp_full: Any, wanted_cmd: str, wanted_type: str='') -> tuple[Any, Any, Any, str]:
        """
        Split response from AR-Gate in to status, wanted_cmd/wanted_type and other commands/types.
        Other is anything but status and wanted cmd/type (there shouldn't be any).

        :param rsp_full: (string) Data from the serial buffer.
        :param wanted_cmd: (string) Currently supported cmd's are operation and liftRef1.
        :param wanted_type: This is the signal type in operation. Left blank for other commands.
        :return: <rsp_status>, <rsp_wanted>, <rsp_other>, <err_code>
        """
        self.logger.debug(f"Serial response: {format(rsp_full)}")

        if wanted_cmd == 'operation' and not wanted_type:
            self.logger.error("Cmd Operation must contain a wanted_type")
            return -1, -1, -1, self.rs232Codes.ARG_TYPE_ERR.name

        if len(rsp_full) == 0:
            self.logger.error("Error: Response empty, cannot split")
            return -1, -1, -1, self.rs232Codes.ARG_TYPE_ERR.name

        try:
            # Concatenated responses become a JSON array; the replace() is a
            # no-op for a single frame and yields a one-element list.
            rsp_json: list = json.loads('[' + rsp_full.replace('}{', '},{') + ']')
        except Exception as error:
            self.logger.error("Failed to convert response to list.")
            self.logger.error(error)
            return -1, -1, -1, self.rs232Codes.ARG_TYPE_ERR.name

        # Validate each response
        err_code: str = self.rs232Codes.NO_ERR.name
        rsp_dec: list = []
        for rsp in rsp_json:
            rsp_tmp, err_code = self.__decode_and_validate_serial_response(rsp)
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: Failed to decode and validate: {rsp_tmp}")
                break
            else:
                rsp_dec.append(rsp_tmp)

        # Which field to check will probably have to change in the future
        rsp_status: list = []
        rsp_wanted: list = []
        rsp_other: list = []
        for rsp in rsp_dec:
            if 'logs' in rsp:
                rsp_wanted = rsp
            elif 'time' in rsp:
                rsp_wanted = rsp
            elif rsp["cmd"] == 'vfdResult':
                self.saved_vfdResult_notification.append(rsp)
            else:
                # Get rid of type 130 (status) or 135 (door closing time) messages in buffer.
                if str(rsp["cmd"]) == 'operation' and "type" in rsp and ((str(rsp["type"]) in self.notification_operation_packages)):
                    if str(rsp["type"]) == self.status_type:
                        rsp_status.append(rsp)
                    elif str(rsp["type"]) == self.door_closing_time_type:
                        self.saved_operation_notifications.append(rsp)
                    else:
                        self.logger.error("Error: should never end up here. Throw away response and continue")
                # Check if the wanted command is received.
                elif "cmd" in rsp and str(rsp["cmd"]) == str(wanted_cmd):
                    # Check if type exists and is wanted_type
                    if wanted_type and "type" in rsp and str(rsp["type"]) == wanted_type:
                        rsp_wanted.append(rsp)
                    # No type in response I.e. not operation.
                    elif "type" not in rsp:
                        rsp_wanted.append(rsp)
                    # Correct cmd but wrong type. Should not really happen.
                    else:
                        rsp_other.append(rsp)
                # Not status or wanted cmd.
                else:
                    rsp_other.append(rsp)

        # If __decode_and_va
        # validate_serial_response has failed for one json object, an error code
        # will be raised. However, there might still be data to return.
        if err_code != self.rs232Codes.NO_ERR.name:
            return rsp_status or -1, rsp_wanted or -1, rsp_other or -1, err_code
        else:
            return rsp_status or '', rsp_wanted or '', rsp_other or '', err_code

    def get_signal_from_serial_buffer(self, wanted_command: str, wanted_type: str='') -> tuple[Any, Any, Any, str]:
        """
        Read serial buffer until wanted signal is found (or max 5s).
        Always writes status to file.
        :param wanted_type: This is the signal type in command operation. Left blank for other commands.
        :return status_out: (list) Contains current status, not appended since status will always be returned as is.
        :return wanted_out: (list) Contains the wanted signal. Not appended, functions return when its found.
        :return other_out: (list) Contains everything that shouldn't really be here.
        """
        retries: int = 5
        other_out: list = []
        for i in range(retries):
            full_resp, err_code = self.read_serial()
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: failed to read serial bus.")
                return -1, -1, -1, err_code

            status_out, wanted_out, resp_other, err_code = self.__split_response(full_resp, wanted_command, wanted_type)

            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: failed to split response.")
                return status_out, wanted_out, resp_other, err_code

            if resp_other and resp_other != -1:
                other_out = other_out + resp_other

            if wanted_out == '' and wanted_type != '130':
                self.logger.debug("Wanted data not found. Will retry to read serial.")
                time.sleep(self.serial_timeout)  # Previous timeout = 0.25
            elif status_out == '' and wanted_type == '130':
                self.logger.debug("Wanted notification not found. Will retry to read serial.")
                time.sleep(self.serial_timeout)  # Previous timeout = 0.25
            else:
                return status_out, wanted_out, other_out or '', err_code

        if wanted_command == 'getOpenCount' and wanted_out == '':
            # getOpenCount cmd is not getting a resp from U1
            # Return partial err and continue to poll
            return -1, -1, -1, self.rs232Codes.PARTIAL_ERR.name
        else:
            self.logger.error(f"Error: No response received in {retries} tries. Serial buffer empty?")
            return -1, -1, -1, self.rs232Codes.SERIAL_COM_ERR.name

    def get_generic_text(self, package: str) -> tuple[Any, str, str]:
        """
        Request and return some generic text (liftRef1, liftRef2, liftName (1010, 1011)
        :return: -1 if call failed, <name> , <err_code>
        """
        if not package or package not in ['liftRef1', 'liftRef2', 'liftName']:
            self.logger.error(f"Package is empty or not supported: {package}")
            return -1, self.name, self.rs232Codes.CMD_NOT_SUPPORTED.name

        _, _, _, _, err_code = self.write_serial([package])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: failed to write AR read request to the serial bus.")
            return -1, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer(package)

        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get AR read response from serial buffer.")
            return -1, self.name, err_code

        # Response must be in format <list>
        response: list = [resp_wanted[0]['data']]
        return response, self.name, err_code

    def get_ar_version(self) -> tuple[Any, str, str]:
        """
        Request and return version (1060, 1061)
        :return: <version> -1 if call failed, <name> , <err_code>
        """
        _, _, _, _, err_code = self.write_serial(["version"])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to write ARGATE version to the serial bus.")
            return -1, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('version')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get ARGATE version from serial buffer.")
            return -1, self.name, err_code
        try:
            response: str = resp_wanted[0]['data']
        except Exception as error:
            self.logger.error("Error: Failed to get ARGATE version read response from serial buffer.")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_LEN_ERR.name
        return response, self.name, self.rs232Codes.NO_ERR.name

    def get_updated_open_door_counter_parameters(self, response: Any) -> tuple[list, str]:
        """
        update and calculate parameters for open door counters
        unpack the response from the lift
        check if the lift counters has been reset
        """
        i: int = 0
        total_open_door_counters_to_save: list = [0] * 6

        changed_params, latest_err = self.tl.door_open_count_recalculate(response)
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to recalculate open door counters")
            return [], latest_err

        for signal_nr in self.tl.params_door_open_count:
            total_open_door_counters_to_save[i] = self.tl.database[signal_nr.value].value
            i += 1

        total_filename = os.path.join(self.dh.get_open_door_counter_file_path(),
                                      self.dh.get_open_door_total_counter_file_filename())
        fname_err, latest_err = self.__write_to_open_door_counter_file(total_filename,
                                                                           total_open_door_counters_to_save)
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Not able to save total counter file")

        if self.tl.reset_saved_open_door_counter:
            previous_filename: str = os.path.join(self.dh.get_open_door_counter_file_path(), self.dh.get_open_door_previous_counter_file_filename())

            fname_err, latest_err = self.__write_to_open_door_counter_file(previous_filename, self.tl.previous_open_door_counters)
            if latest_err != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: failed to save open door previous counter to file {fname_err}")

        return changed_params, latest_err

    def get_door_open_count(self) -> tuple[Any, str, str]:
        """
        Get number of door open from 1k
        """
        # Check if reset flag is set and read from if flag is set

        if self.tl.reset_saved_open_door_counter:
            total_filename: str = os.path.join(self.dh.get_open_door_counter_file_path(), self.dh.get_open_door_total_counter_file_filename())
            previous_filename: str = os.path.join(self.dh.get_open_door_counter_file_path(), self.dh.get_open_door_previous_counter_file_filename())

            self.tl.total_open_door_counters = self.__read_open_door_counter_from_file(total_filename).copy()
            self.tl.previous_open_door_counters = self.__read_open_door_counter_from_file(previous_filename).copy()
            self.tl.reset_saved_open_door_counter = False

        _, _, _, _, err_code = self.write_serial(["getOpenCount"])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to write getOpenCount to the serial bus.")
            return -1, self.name, err_code

        time.sleep(self.serial_timeout)

        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('getOpenCount')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get number of time the door has open from serial buffer.")
            return -1, self.name, err_code

        try:
            response: str = resp_wanted[0]['data']
        except Exception as error:
            self.logger.error("Error: Failed to get number of times the door open response from serial buffer.")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_LEN_ERR.name
        return response, self.name, self.rs232Codes.NO_ERR.name

    def __read_open_door_counter_from_file(self, fname: str) -> list:
        """
        Read the data from saved open_door_counter_file
        """
        if os.path.isfile(fname):
            with open(fname, 'r') as f:
                saved_open_door_counters_str = f.read()
                if saved_open_door_counters_str == '':
                    self.logger.warning("Empty door_open_count file")
                    return [0]*6
            saved_open_door_counters = ast.literal_eval(saved_open_door_counters_str)
        else:
            saved_open_door_counters = [0] * 6

        return saved_open_door_counters

    def __write_to_open_door_counter_file(self, fname: str, data: list) -> tuple[str, str]:
        """
        Write open door counter data to file
        """
        fname_err = "file_error"
        err_code = self.rs232Codes.NO_ERR.name

        #check if open_door_counter file exist and create if not
        try:
            open_door_counter_file_path = self.dh.get_open_door_counter_file_path()
            if not os.path.exists(str(open_door_counter_file_path)):
                if not self.__set_1000_file_dir(open_door_counter_file_path):
                    self.logger.error("Error: Failed to create Open Door Counter file directory")
                    err_code = self.rs232Codes.FILE_NAME_ERR.name
                    return fname_err, err_code

            with open(fname, 'w') as f:
                f.write(str(data))

        # TODO fix error codes
        except IOError as io_error:
            self.logger.error("Error: IO Error")
            self.logger.error(io_error)
            err_code = self.rs232Codes.LOG_FILE_EXCEPTION.name
            return fname_err, err_code

        # TODO fix error codes
        except Exception as error:
            self.logger.error("Error: Something went very wrong")
            self.logger.error(error)
            err_code = self.rs232Codes.LOG_FILE_EXCEPTION.name
            return fname_err, err_code

        return fname_err, err_code


    def get_logfile(self, args: list) -> tuple[str, str, str]:
        """
        Request and return 1k logfile (1065, 1066)
        :param file_type: the type of the log 0x10
        :param data: the number of log block to read
        :return: <logfile_name> 'file_error' if call failed, <name> , <err_code>
        """
        fname_err: str = "file_error"
        exp_file_type: str = '0x10'
        err_code: str = self.__validate_input_filetype(args, 2)
        if err_code != self.rs232Codes.NO_ERR.name:
            return fname_err, self.name, err_code

        if args[0] != exp_file_type:
            self.logger.error("Error: not supported file type")
            return fname_err, self.name, self.rs232Codes.DATA_TYPE_ERR.name

        _, _, _, name, err_code = self.write_serial(["logfile", args[1]])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to write 1k logfile to the serial bus.")
            return fname_err, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('logfile')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get 1k logfile from serial buffer.")
            return fname_err, self.name, err_code

        fname_full, err_code = self.__write_log_to_file(resp_wanted)
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to write logfile to file")
            return fname_err, self.name, err_code

        return fname_full, self.name, self.rs232Codes.NO_ERR.name

    def read_1k_file(self, args: list) -> tuple[Any, Any, Any, str, str]:
        """ 
        Request and return 1k files
        :param args[0]: filename, the name of the 1k file (param/intern/node/lock/door)
        :return: <file_data>, <data>
        :return: file_name, <name>, err_code
        """
        if len(args) != 1:
            self.logger.error(f"Error: Wrong number of arguments {len(args)}")
            return -1, -1, -1, self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        err_data: int = -1
        resp_data: list = []
        file_name: str = args[0]

        _, _, _, _, err_code = self.write_serial(['readFile', file_name])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to write 1k files to the serial bus.")
            return -1, err_data, file_name, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_data, _, err_code = self.get_signal_from_serial_buffer('readFile')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to read 1k file data from serial buffer.")
            return resp_data, err_data, file_name, self.name, err_code

        try:
            resp_data_dict = resp_data[0]
        except IndexError as error:
            self.logger.error("Error: Unable to read list index")
            self.logger.error(error)
            return resp_data, err_data, file_name, self.name, self.rs232Codes.LIST_INDEX_ERR.name

        try:
            err_status = resp_data_dict["err"]
        except KeyError as error:
            self.logger.error("Error: Unable to read json key")
            self.logger.error(error)
            return resp_data, err_data, file_name, self.name, self.rs232Codes.JSON_KEY_ERR.name

        if err_status != 0:
            self.logger.error("Error: Unable to open or read from 1k file or default file")
            return resp_data, err_data, file_name, self.name, self.rs232Codes.DATA_ERR.name

        try:
            file_data_resp = resp_data[0]["data"]
        except KeyError as error:
            self.logger.error(f"Error: Unable to find data key in response")
            self.logger.error(error)
            return resp_data, err_data, file_name, self.name, self.rs232Codes.JSON_KEY_ERR.name

        return resp_data, file_data_resp, file_name, self.name, err_code

    def write_1k_file(self, args: list) -> tuple[Any, str, str]:
        """
        To store data to 1k file
        :param args (file_name(str), data(list of bytes)
        return: file_name, name, err_code
        """

        if len(args) != 2:
            self.logger.error("Error: Wrong number of arguments")
            return -1, self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        file_name: str = args[0]
        try:
            data_str = json.dumps({"data": args[1]})
        except Exception as error:
            self.logger.error("Error: Argument is not JSON serializable")
            self.logger.error(error)
            return file_name, self.name, self.rs232Codes.JSON_ERR.name

        _, _, _, _, err_code = self.write_serial(['writeFile', file_name, data_str])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to write to serial bus.")
            return file_name, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_data, _, err_code = self.get_signal_from_serial_buffer('writeFile')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to read 1k file data from serial buffer.")
            return file_name, self.name, err_code

        resp_data_dict: dict[Any, Any] = resp_data[0]
        err_status: str = resp_data_dict["err"]

        if err_status != 0:
            self.logger.error("Error: Unable to open or write to 1k file.")
            return file_name, self.name, self.rs232Codes.DATA_ERR.name

        return file_name, self.name, err_code

    def __write_log_to_file(self, data: dict[Any, Any]) -> tuple[Any, str]:
        """
        Write log data to file
        :param data: log data
        return: logfile_name, err_code
        """
        fname_err: str = "file_error"

        # Check if logfile dir exist and create if not. Return if it fails
        try:
            self.ARK_1000_log_file_path = self.dh.get_1000_log_file_path()
            if not os.path.exists(self.ARK_1000_log_file_path):
                if not self.__set_1000_file_dir(self.ARK_1000_log_file_path):
                    self.logger.error("Error: Failed to create 1000 log file directory")
                    err_code = self.rs232Codes.LOG_FILE_IO_ERR.name
                    return fname_err, err_code

            obj_id, _, err_code = self.read_parameter(["0"])
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: Object ID not set")
                return -1, self.rs232Codes.NO_UPDATED_PARAMS.name

            timestamp: str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

            fname_ret: str = f'{obj_id}_{timestamp}.eventlog'
            fname_full: str = os.path.join(self.dh.get_1000_log_file_path(), fname_ret)

            # Convert dict to string
            data_str: str = json.dumps(data)
            if not isinstance(data_str, str):
                self.logger.error("Error: log data not converted to string before write to file")
                return -1, self.rs232Codes.DATA_TYPE_ERR.name

            # Check if file already exist
            if not os.path.isfile(fname_full):
                with open(fname_full, 'w') as f:
                    f.write(json.dumps(data))
            else:
                self.logger.error("Error: Destination file already exist {}".format(fname_full))
                return -1, self.rs232Codes.LOG_FILE_ALREADY_EXIST.name

        except IOError as io_error:
            self.logger.error(f'Error: IOError')
            self.logger.error(io_error)
            err_code = self.rs232Codes.LOG_FILE_IO_ERR.name
            return fname_err, err_code

        except Exception as error:
            self.logger.error("Error: Something went very wrong")
            self.logger.error(error)
            err_code = self.rs232Codes.LOG_FILE_EXCEPTION.name
            return fname_err, err_code

        self.logger.info(f'ARK 1000 log received and saved in file: {fname_full}')

        return fname_full, err_code

    def write_generic_text(self, args: list) -> tuple[Any, str, str]:
        """
        Write new generic text and return it (1010, 1011)
        :param args: arg[0] liftRef1/liftRef2/liftName, arg[1] new_text
        :return: <name>, <err_code>
        """
        package: str = args[0]
        new_text: str = args[1]

        if package not in ["liftRef1", "liftRef2", "liftName"]:
            self.logger.error(f"Error: Unsupported generic text package: {package}")
            return -1, self.name, self.rs232Codes.CMD_NOT_SUPPORTED.name

        _, _, _, _, err_code = self.write_serial([package, new_text])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: failed to write generic text to the serial bus.")
            return -1, self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer(package)

        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get generic text write response from serial buffer.")
            return -1, self.name, err_code

        if resp_wanted[0]['data'] != new_text:
            self.logger.error(f"Error: Wrong generic text received. Requested: {new_text}, received: {resp_wanted[0]['data']}.")
            return resp_wanted[0]['data'], self.name, self.rs232Codes.DATA_TYPE_ERR.name

        return resp_wanted[0]['data'], self.name, err_code

    def reset_service_memory(self) -> tuple[str, str]:
        """
        Request reset of service memory. Returns an empty list on success. (1020, 1021)
        :return: <service_memory> -1 if call failed, <name> , <err_code>
        """
        _, _, _, _, err_code = self.write_serial(["operation", "132"])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: failed to send reset service memory to the serial bus.")
            return self.name, err_code

        time.sleep(self.serial_timeout)  # Previous timeout = 0.5
        _, _, _, err_code = self.get_signal_from_serial_buffer("operation", "132")

        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get reset service memory response from serial buffer.")
            return self.name, err_code

        return self.name, err_code

    def set_child_lock(self, data: str) -> tuple[Any, str, str]:
        """
        Sets the childLock to either on or off. ChildLock status is read through the 130 package.
        """
        if data not in ["on", "off"]:
            self.logger.error(f"Error: Child lock ata must be either 'on' or 'off', '{data}' is not supported")
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        _, _, data, _, err_code = self.write_serial(["childLock", data])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to write childLock to the serial bus.")
            return -1, self.name, err_code

        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('childLock')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to read childLock status from serial buffer.")
            return -1, self.name, err_code

        try:
            response = resp_wanted[0]['data']
            if not isinstance(response, str):
                self.logger.error("Error: childLock data response is not str.")
                return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name
        except Exception as error:
            self.logger.error("Error: Failed to get the childLock read response from serial buffer.")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        if data != response:
            self.logger.error(f"Error: Sent in data: {data} but response was: {response}")
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        return response, self.name, self.rs232Codes.NO_ERR.name

    def set_floor_lock(self, data_in: str) -> tuple[Any, str, str]:
        """
        Sets floorLock to selected floors.
        """

        _, _, _, _, err_code = self.write_serial(["floorLock", data_in])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to write floorLock to the serial bus.")
            return -1, self.name, err_code

        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('floorLock')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to read floorLock status from serial buffer.")
            return -1, self.name, err_code

        try:
            response = resp_wanted[0]['data']
            if not isinstance(response, list):
                self.logger.error("Error: floorLock data response is not list.")
                return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name
        except Exception as error:
            self.logger.error("Error: Failed to get the floorLock read response from serial buffer.")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        if data_in != str(response):
            self.logger.error(f"Error: Sent in data: {data_in} but response was: {response}")
            return -1, self.name, self.rs232Codes.FLOOR_LOCK_ERR.name

        return response, self.name, self.rs232Codes.NO_ERR.name

    def set_oil_level(self, data_in: str, previous_oilLevel: int) -> tuple[Any, str, str]:
        """
        Sets oil level
        """
        _, _, _, _, err_code = self.write_serial(["oilLevel", data_in])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to write oilLevel to serial bus")
            return -1, self.name, err_code

        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('oilLevel')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to read oil level")
            return -1, self.name, err_code

        try:
            response = [resp_wanted[0]['data']]
            if not isinstance(response, list):
                self.logger.error("Error: oil level data response is not a list")
                return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name
        except Exception as error:
            self.logger.error("Error: Failed to get the oil level read response from serial bus")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        if str(previous_oilLevel) != str(response[0]):
            self.logger.error(f"Error: Failed to set oil level to {data_in}")
            return -1, self.name, self.rs232Codes.DATA_ERR.name

        return response, self.name, self.rs232Codes.NO_ERR.name

    def get_notification(self) -> tuple[list, str]:
        """
        Filter package data by notification type and update parameters
        """
        filtered_notification_pkg: list = []
        response: str = ""
        latest_err_code: str = self.rs232Codes.NO_ERR.name
        door_parameter: list = []

        if len(self.saved_operation_notifications) > 0:
            for saved_rsp in self.saved_operation_notifications:
                try:
                    if str(saved_rsp["type"]) == self.door_closing_time_type:
                        filtered_notification_pkg.append(saved_rsp)
                except Exception as e:
                    self.logger.error("Error: notification package has faulty type")
                    self.logger.error(e)

            response, latest_err_code = self.__repackage_status(filtered_notification_pkg)
            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error when repacking notification. Continue when next data pkg")

            door_parameter, latest_err_code = self.tl.update_door_closing_time(response)
            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error when unpack and update door closing time parameters")

        self.saved_operation_notifications = []
        self.tl.reset_135_params()

        return door_parameter, latest_err_code

    def vfd_clear_table(self) -> tuple[str, str]:
        """
            Send a request to clear the command table of the A-ModCom board
            Return response on success. (1070, 1071)
        """

        _, _, _, _, err_code = self.write_serial(["vfdClearTable"])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: failed to send clear table command to A-ModCom board")
            return self.name, err_code

        time.sleep(self.serial_timeout)

        _, _, _, err_code = self.get_signal_from_serial_buffer("vfdClearTable")
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get clear table response from serial buffer.")

        return self.name, err_code

    def set_vfd_id_1k(self, args: list) -> tuple[Any, str, str]:
        """
        Set id on 1k vfd by a generic data string sent out on modbus via U19 (1075, 1076)
        :param: in_data string
        :return:  response, name, err
        """

        vfd_err_code: int = -1
        expected_len_args: int = 1

        if len(args) != expected_len_args:
            self.logger.error(f"Error: Wrong number of arguments, got: {len(args)}, expected {expected_len_args}")
            return  -1, self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        if not isinstance(args[0], str):
            self.logger.error("Error: In data is not string")
            return -1, self.name, self.rs232Codes.ARG_TYPE_ERR.name

        request_data = args[0].replace("-", ",")

        _, _, _, _, latest_err = self.write_serial(["vfdId", request_data])
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to write vfdId to serial bus")
            return -1, self.name, latest_err

        _, resp_wanted, _, latest_err = self.get_signal_from_serial_buffer('vfdId')
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to read vfdId response")
            return -1, self.name, latest_err

        try:
            response: Any = resp_wanted[0]["data"]
            vfd_err_code = resp_wanted[0]["error"]
        except Exception as e:
            self.logger.error(f"Exception vfd err: {e}")

        response = response.replace(",", "-")

        response = -1 if not response else response

        if vfd_err_code != 0:
            self.logger.error(f"Error: Faulty code from vfdId {vfd_err_code} ")
            if vfd_err_code == 1:
                return response, self.name, self.rs232Codes.VFD_TIMEOUT_ERR.name
            elif vfd_err_code == 2:
                return response, self.name, self.rs232Codes.VFD_NO_PWR_ERR.name
            else:
                return response, self.name, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

        return response, self.name, latest_err

    def set_vfd_read_1k(self, args: list) -> tuple[str, str]:
        """
        Set id on 1k vfd by a generic data string sent out on modbus via U19 (1080, 1081)
        :param: id int, in_data string, interval int
        :return:  response, name, err
        :param: in_data string
        :return:  name, err
        """
        vfd_err_code: int = -1
        expected_len_args: int = 3

        if len(args) != expected_len_args:
            self.logger.error(f"Error: Wrong number of arguments, got: {len(args)}, expected {expected_len_args}")
            return self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        if not isinstance(args[1], str):
            self.logger.error("Error: In data is not string")
            return self.name, self.rs232Codes.ARG_TYPE_ERR.name

        request_data = args[1].replace("-", ",")

        _, _, _, _, latest_err = self.write_serial(["vfdRead", args[0], request_data, args[2]])
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to write vfdRead to serial bus")
            return self.name, latest_err

        _, resp_wanted, _, latest_err = self.get_signal_from_serial_buffer('vfdRead')
        if latest_err != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to read vfdRead response")
            return self.name, latest_err

        try:
            resp_wanted[0]["id"]
            vfd_err_code = resp_wanted[0]["error"]
        except Exception as e:
            self.logger.error(f"Exception vfd err: {e}")

        if vfd_err_code != 0:
            self.logger.error(f"Error: Faulty code from vfdRead {vfd_err_code} ")
            if vfd_err_code == 1:
                return self.name, self.rs232Codes.VFD_ID_ERR.name
            else:
                return self.name, self.rs232Codes.JSON_VALUE_TYPE_ERR.name

        return self.name, latest_err

    def get_vfd_motor_data(self) -> tuple[Any, str]:

        params: list = []
        err_code: str = self.rs232Codes.NO_ERR.name

        if len(self.saved_vfdResult_notification) > 0:
            for saved_rsp in self.saved_vfdResult_notification:
                param, err_code =  self.tl.update_vfd_params(saved_rsp)

                if param:
                    params.append(param[0])

        self.saved_vfdResult_notification = []
        # TODO: Make a list, not set
        return set(params), err_code

    def poll_lift(self, args: list) -> tuple[Any, str, str]:
        """
        Updates all params and return list of updated params (1045, 1046)
        :return: <updated_parameters> -1 if call failed, <name> , <err_code>
        poll_type = 0 read only one file packages per poll
        poll_type = 1 read all file packages per poll
        """
        err_code: str = self.rs232Codes.NO_ERR.name
        updated_parameters: list = []
        expected_len_args: int = 1
        if len(args) != expected_len_args:
            self.logger.error(f"Error: Wrong number of arguments, got: {len(args)}, expected {expected_len_args}")
            return -1, self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        poll_type: str = args[0]

        self.polled_packages = self.always_polled_packages[:]
        if poll_type == '1':
            self.polled_packages += self.file_packages
        elif poll_type == '0':
            current_file_package: str = self.file_packages[self.polled_file_package]
            self.polled_packages.append(current_file_package)
            self.polled_file_package += 1
            if self.polled_file_package >= len(self.file_packages):
                self.polled_file_package = 0
        else:
            self.logger.error(f"Error: Faulty polling argument. Polled type: {poll_type}")
            err_code = self.rs232Codes.ARG_TYPE_ERR.name
            return -1, self.name, err_code

        self.tl.reset_door_closing_time_params()

        for package in self.polled_packages:
            if package == 'doorOpenCount' and not self.check_if_above_or_equal_to_versions(self.doorOpenCount_version_limits):
                self.logger.debug("Not polling doorOpenCount, version not supported.")
                continue

            time.sleep(self.serial_timeout)  # Previous timeout = 0.5
            if package in ['liftRef1', 'liftRef2', 'liftName']:
                response, self.name, latest_err_code = self.get_generic_text(package)
            elif package == 'version':
                response, self.name, latest_err_code = self.get_ar_version()
            elif package == "doorOpenCount":
                response, self.name, latest_err_code = self.get_door_open_count()
            elif package == "readFileParam":
                _, response, _, self.name, latest_err_code = self.read_1k_file(["/aritco/param"])
            elif package == "readFileIntern":
                _, response, _, self.name, latest_err_code = self.read_1k_file(['/aritco/intern'])
            elif package == "readFileNode":
                _, response, _, self.name, latest_err_code = self.read_1k_file(['/aritco/node'])
            elif package == "readFileLock":
                _, response, _, self.name, latest_err_code = self.read_1k_file(['/aritco/lock'])
            elif package == "readFileDoor":
                _, response, _, self.name, latest_err_code = self.read_1k_file(['/aritco/door'])
            else:
                response, self.name, latest_err_code = self.get_operation_package(package)

            if latest_err_code == self.rs232Codes.NO_WAITING_BYTES_ERR.name or \
                    latest_err_code == self.rs232Codes.SERIAL_COM_ERR.name:
                self.logger.error(f"Error: Failed to poll {package} package, no waiting bytes or COM err.")
                return response, self.name, latest_err_code

            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: Failed to get operation package {package}, {latest_err_code}. Continuing poll.")
                err_code = self.rs232Codes.PARTIAL_ERR.name
                continue

            if package == 'doorOpenCount':
                new_parameters: list = []
                new_open_door_counters_parameters, _ = self.get_updated_open_door_counter_parameters(response)
            else:
                new_open_door_counters_parameters = []
                new_parameters, latest_err_code = self.tl.get_updated_params(package, response)
            new_parameters += new_open_door_counters_parameters

            if latest_err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: Failed to get updated params for package {package}, {latest_err_code}. Continuing poll.")
                err_code = self.rs232Codes.PARTIAL_ERR.name
                continue

            if new_parameters:
                updated_parameters += new_parameters

        # Virtual params needs to be handled after all other packages
        new_parameters, latest_err_code = self.tl.get_updated_params('virtual')
        if latest_err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to get updated params for virtual params, {latest_err_code}. Continuing poll.")
            err_code = self.rs232Codes.PARTIAL_ERR.name

        if new_parameters:
            updated_parameters += new_parameters

        new_parameters, latest_err_code = self.get_notification()

        if latest_err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(
                f"Error: Failed to get updated params for notification package, {latest_err_code}. Continuing poll.")
            err_code = self.rs232Codes.PARTIAL_ERR.name
        if new_parameters:
            updated_parameters += new_parameters

        if not updated_parameters:
            if err_code == self.rs232Codes.NO_ERR.name:
                err_code = self.rs232Codes.NO_UPDATED_PARAMS.name
            return "0", self.name, err_code

        new_parameters, latest_err_code = self.get_vfd_motor_data()

        if latest_err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(
                f"Error: Failed to get motor params for vfdResult package, {latest_err_code}. Continuing poll.")
            err_code = self.rs232Codes.PARTIAL_ERR.name
        if new_parameters:
            updated_parameters += new_parameters

        try:
            response = self.data_sep.join(str(elem) for elem in updated_parameters)
        except Exception as error:
            self.logger.error(f"Error: Failed to repackage poll results from list to string: {updated_parameters}")
            self.logger.error(error)
            return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name
        return response, self.name, err_code

    def get_available_params(self) -> tuple[str, str, str]:
        """
        Updates all params and return list of updated params (1055, 1056)
        :return: <available_parameters> -1 if call failed, <name> , <err_code>
        """
        params = self.tl.available_params()

        if not params:
            return "0", self.name, self.rs232Codes.NO_PARAMS_IN_DB.name

        response: str = self.data_sep.join(str(elem) for elem in params)

        return response, self.name, self.rs232Codes.NO_ERR.name

    def get_latest_status(self) -> tuple[Any, str, str]:
        """
        Read the 130 packages and return the latest package
        """
        resp_status, _, _, err_code = self.get_signal_from_serial_buffer('operation', '130')
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error("Error: Failed to get status from serial buffer.")
            return resp_status, self.name, err_code

        status_last, err_code = self.__repackage_status(resp_status)
        if not status_last:
            self.logger.error("No latest status read.")
            return -1, self.name, err_code

        return status_last, self.name, err_code

    def read_parameter(self, args: list[str]) -> tuple[int, str, str]:
        """
        Get parameter for stored values. (1030,1031)
        """
        value, err_code = self.tl.get_param(int(args[0]))
        return value, self.name, err_code

    def write_parameter(self, args: list[str]) -> tuple[int, str, str]:
        """
        Read the file, replace the parameter we are writing to, save the file. (1040,1041)
        """
        data: Any
        # Validate input args
        expected_len_args = 2
        if len(args) != expected_len_args:
            self.logger.error(f"Error: Wrong number of arguments, got: {len(args)}, expected {expected_len_args}")
            return -1, self.name, self.rs232Codes.ARGS_IN_LEN_ERR.name

        param_str: str = args[0]
        value_str: str = args[1]
        try:
            param_int: int = int(param_str)
            value_int: int = int(value_str)
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error: Unable to identify in params for writing 1k param: {param_str}, {value_str}")
            self.logger.error(e)
            return -1, self.name, self.rs232Codes.ARGS_IN_ELEM_INT_ERR.name

        # Check if param already has requested value, if so, do nothing and return gracefully
        current_val, _, err_code = self.read_parameter([param_str])
        if err_code == self.rs232Codes.NO_ERR.name and current_val == value_str:
            self.logger.debug(f"Param {param_str} already has value {value_str}, returning gracefully")
            return 0, self.name, self.rs232Codes.NO_ERR.name

        if param_int == self.tl.params_130.CHILD_LOCK_130.value:
            data = 'on' if value_int else 'off'
            self.logger.debug(f"Setting childLock data to: {data}")
            _, _, err_code = self.set_child_lock(data)
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Got error from child lock")
                return -1, self.name, err_code

        elif param_int == self.tl.params_virtual.FLOOR_LOCK.value:
            if value_int < 0 or value_int > 63:
                self.logger.error(f"Error: invalid value {value_str} to convert to floors to lock")
                return -1, self.name, self.rs232Codes.DATA_ERR.name
            fire_floor, error = self.tl.get_param(self.tl.params_readFile_param.FIRE_FLOOR.value)
            if error != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: Can not read fire floor")
                return -1, self.name, error
            bit_floors: list = []
            total_number_of_floors: int = 6
            # loop backwards from 5 to 0 with range
            # transform value (int) to bit_floors (binary) for max number of floors (6)
            for bit in range(total_number_of_floors-1, -1, -1):
                bit_floors.append((value_int >> bit) & 1)
            self.logger.debug(f"Value in integer transformed to binary {bit_floors}")

            locked_floor_data: list = []
            for floor in range(1, total_number_of_floors + 1):
                if bit_floors[(total_number_of_floors) - floor] == 1:
                    locked_floor_data.append(floor)

            if int(fire_floor) in locked_floor_data:
                self.logger.error(f"Error: Fire floor ({fire_floor}), must not be locked. Rejecting lock request: {locked_floor_data}")
                err_code = self.rs232Codes.FLOOR_LOCK_ERR.name
                return -1, self.name, err_code

            else:
                _, _, err_code = self.set_floor_lock(str(locked_floor_data))
                if err_code != self.rs232Codes.NO_ERR.name:
                    self.logger.error("Error: fault in floor lock")
                    return -1, self.name, err_code

        elif param_int == self.tl.params_130.OIL_LEVEL_130.value:
            if value_int < 0 or value_int > 100:
                self.logger.error(f"Error: invalid value {value_str} ")
                return -1, self.name, self.rs232Codes.DATA_ERR.name
            _, _, err_code = self.set_oil_level(value_str, current_val)
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: Failed to set oil level")
                return -1, self.name, err_code

        else:
            # Check if file is large enough for this param #backwardCompatibility
            # If we cannot read the param from the database, it has never been polled successfully and (probably) does
            # not exist. This means we cannot write to this if there has been no successful poll, but then lift_type is
            # 0 in CA anyway, and we won't be able to DDM write any param.
            _, _, err_code = self.read_parameter([param_str])
            if err_code != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: Unable to read value of param {param_str}, it does not exist in db. Can't write to it!")
                return -1, self.name, self.rs232Codes.WRITE_PARAM_NOT_SUPPORTED_BY_1K.name

            # Check what file the param we want to write is in
            file: str = self.tl.get_file_for_param(param_int)
            if not file:
                return -1,  self.name, self.rs232Codes.WRITE_PARAM_NOT_IN_FILES.name

            # Read that file
            resp_data, _, _, _, err = self.read_1k_file([file])
            if err != self.rs232Codes.NO_ERR.name:
                self.logger.error("Error: Read file prior to write file failed")
                return -1, self.name, err

            resp_data = resp_data[0]
            data = resp_data.get('data')
            if not data:
                self.logger.error("Error: Data not found in the readFile response")
                return -1, self.name, self.rs232Codes.DATA_ERR.name
            self.logger.debug(f"Data from readFile: {data}")

            # Replace the param
            byte_size: int = self.tl.database[param_int].byte_size
            value_in_bytes: bytes = value_int.to_bytes(byte_size, "little", signed=False)

            for byte_number in range(byte_size):
                self.logger.debug(f"We getting current value: {data[self.tl.database[param_int].byte_start + byte_number]}, "
                      f"we replacing with: {value_in_bytes[byte_number]}")
                data[self.tl.database[param_int].byte_start + byte_number] = value_in_bytes[byte_number]
            self.logger.debug(f"New data, ready to ship to GW: {data}")

            # Write the file
            _, _, err = self.write_1k_file([file, data])
            if err != self.rs232Codes.NO_ERR.name:
                self.logger.error(f"Error: Error when writing new data to 1k through writeFile: {err}")
                return -1, self.name, err

        self.tl.database[param_int].value = value_str
        return 0, self.name, self.rs232Codes.NO_ERR.name

    def get_operation_package(self, signal: str) -> tuple[Any, str, str]:
        """
        Read and return an operation package
        """
        # Handle status package separately
        if signal == '130':
            return self.get_latest_status()

        cmd, operation_type, data, name, err_code = self.write_serial(["operation",  signal])
        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: failed to write signal {signal} request to the serial bus.")
            return -1, self.name, err_code

        time.sleep(self.serial_timeout) #Previous timeout = 0.5
        _, resp_wanted, _, err_code = self.get_signal_from_serial_buffer('operation', signal)

        if err_code != self.rs232Codes.NO_ERR.name:
            self.logger.error(f"Error: Failed to get response on signal {signal} from serial buffer.")
            return -1, self.name, err_code
        elif not resp_wanted[0]['data']:
            self.logger.error(f"Error: Received empty data when requesting signal {signal}.")
            return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name

        response = resp_wanted[0]['data']
        if not isinstance(response, list):
            self.logger.error("Error: data in field 'data' is not a list")
            return -1, self.name, self.rs232Codes.DATA_TYPE_ERR.name

        return response, self.name, err_code

    def __repackage_status(self, status: list) -> tuple[Any, str]:
        """
        Return the latest notification/status response
        """
        data_last: list = []
        if len(status) > 0:
            for pkg in status:
                try:
                    data_last = pkg["data"]
                    if not isinstance(data_last, list):
                        self.logger.error(f"The data in field 'data': \"{data_last}\" is not a list")
                        return "", self.rs232Codes.ARG_TYPE_ERR.name
                except Exception as error:
                    self.logger.error("Error: Failed to parse 'data' field from status/notification response")
                    self.logger.error(error)
                    return "", self.rs232Codes.ARG_TYPE_ERR.name
            return data_last, self.rs232Codes.NO_ERR.name
        else:
            self.logger.error("Received empty status.")
            return "", self.rs232Codes.STATUS_ERR.name

    def check_if_above_or_equal_to_versions(self, versions: list) -> bool:
        """
        Check if current version of U1 and U16 is above or equal to in arg version
        :param versions: What versions to compare to. List as [U1, U16] format "X.Y"
        :return: True if above or equal else False
        """
        installed_raw = [self.tl.database[self.tl.params_2.MAIN_VERSION_2.value].value,
                         self.tl.database[self.tl.params_2.SUB_VERSION_2.value].value,
                         self.tl.database[self.tl.params_version.ARGATE_MAIN_VERSION.value].value,
                         self.tl.database[self.tl.params_version.ARGATE_SUB_VERSION.value].value]

        if any(value == "" for value in installed_raw):
            # Version params init to "" until the first successful poll
            self.logger.debug("Version params not polled yet, version comparison not possible")
            return False

        try:
            u1_main_installed: int = int(installed_raw[0])
            u1_sub_installed: int = int(installed_raw[1])
            u16_main_installed: int = int(installed_raw[2])
            u16_sub_installed: int = int(installed_raw[3])

            u1_main_required: int = int(versions[0].split(".")[0])
            u1_sub_required: int = int(versions[0].split(".")[1])
            u16_main_required: int = int(versions[1].split(".")[0])
            u16_sub_required: int = int(versions[1].split(".")[1])
        except (ValueError, IndexError) as error:
            self.logger.warning(f"Version comparison failed on malformed version value: {error}")
            return False

        if u1_main_required > u1_main_installed:
            return False
        elif u1_main_required == u1_main_installed:
            if u1_sub_required > u1_sub_installed:
                return False

        if u16_main_required > u16_main_installed:
            return False
        elif u16_main_required == u16_main_installed:
            if u16_sub_required > u16_sub_installed:
                return False

        return True

def get_and_save_prod_loader_params() -> Any:
    """
    Read and store parameters used when ProdLoader has configured
    """
    prodLoadParaNo: dict[str, Any] = {
                      "liftRef1": "0",
                      "liftRef2": "1",
                      "freqControl": "112",
                      "lock": "114",
                      "platformLight": "120",
                      "oilSystem": "115",
                      "doubleDoors": {
                          "1": "138",
                          "2": "139",
                          "3": "140",
                          "4": "141",
                          "5": "142",
                          "6": "143"
                      },
                      "aGateU16": "124",
                      "emergencyLightTest": "125"}

    prodLoadParaValue: dict[str, Any] = prodLoadParaNo
    double_doors_value: list = []

    rs232: Rs232Handler = Rs232Handler(ThousandLib())
    arg_in: list = ['1']
    res, _, err_code = rs232.poll_lift(arg_in)

    if (err_code == rs232.rs232Codes.NO_ERR.name) or (err_code == rs232.rs232Codes.PARTIAL_ERR.name):

        for key, value in prodLoadParaNo.items():
            if key != "doubleDoors":
                prodLoadParaValue[key], _, _ = rs232.read_parameter([value])
                logger.debug(prodLoadParaValue[key])
            elif key == "doubleDoors":
                for _, double_value in prodLoadParaValue[key].items():
                    param_value, _, _ = rs232.read_parameter([double_value])
                    double_doors_value.append(param_value)
                prodLoadParaValue[key] = double_doors_value
            else:
                logger.error("Very wrong")
        try:
            res = json.dumps(prodLoadParaValue)
        except TypeError:
            logger.error("Unable to serialize the object")
            res = "error"

    else:
        res = "error"

    return res


if __name__ == "__main__":

    obj: Rs232Handler = Rs232Handler(ThousandLib())
    input: str = sys.argv[1]
    logger.info(input)
    if (input == "production_test"):
        rsp = get_and_save_prod_loader_params()
        if (rsp == "error"):
            logger.error("Failed")
            sys.exit(1)
        else:
            sys.stdout.write(rsp)
            sys.exit(0)
    else:
        try:
            input_json: Any = json.loads(input)
        except json.decoder.JSONDecodeError as e:
            logger.error("Failed to parse input as json. Did you escape the quotation marks and comma signs?")
            sys.exit(1)

        if not isinstance(input_json, dict):
            logger.error("Error: Input not json format")
            sys.exit(1)

        assert obj.client is not None
        obj.client.write(input.encode('utf-8'))

        while 1:
            resp_status, resp_wanted, resp_other, err_code = obj.get_signal_from_serial_buffer('operation', '130')
            response = resp_status + resp_wanted + resp_other
            logger.info(response)


