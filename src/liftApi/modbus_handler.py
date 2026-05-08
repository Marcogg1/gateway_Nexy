"""
Modbus RTU communication handler for LCM (Lift Control Module).

Handles serial communication with lift control hardware including:
- Parameter read/write operations
- Trace log retrieval from buffer and SRAM
- Upgrade package upload (.up files)
- Special handling for reset alarms, speed config, floor locks
- Time synchronization integration

Communication uses Modbus RTU protocol over the onboard RS485 bus.
"""
# pylint: disable=too-many-lines
from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from pymodbus.client import ModbusSerialClient
from pymodbus.pdu.file_message import WriteFileRecordResponse

from filemgmt.disk_handler import DiskHandler
from lib.error_signals import MbCode
from lib.logging_config import get_logger, setup_logging
from lib.rs485_serial import RS485Serial
from liftApi.modbus_file_record import ReadFileRecord, WriteFileRecord

setup_logging()
logger = get_logger(__name__)


@dataclass
class WriteRecordConfig:
    """Modbus write record size specifications."""

    modbus_pdu_max_size: int = 253
    request_header_size: int = 2
    sub_request_header_size: int = 7

    @property
    def max_write_record_length(self) -> int:
        """Maximum number of bytes that can be written in one record."""
        return (
            self.modbus_pdu_max_size
            - self.request_header_size
            - self.sub_request_header_size
        )


@dataclass
class LogSizes:
    """Log size specifications in bytes."""

    header: int = 3
    crc: int = 2
    filename: int = 32
    record_length: int = 0x73  # Number of Modbus words (dual-byte)
    log: dict[str, int] = field(
        default_factory=lambda: {
            "0x06": 2048,
            "0x02": 16 * 2048,
        }
    )
    nr_records: dict[str, int] = field(
        default_factory=lambda: {
            "0x06": 10,
            "0x02": 143,
        }
    )


@dataclass
class LogConfig:
    """Log retrieval configuration."""

    filename: str = ""
    storage_path: Path = field(default_factory=Path)
    header: bytes = b"\n\x14"
    sizes: LogSizes = field(default_factory=LogSizes)
    types: list[str] = field(default_factory=lambda: ["0x06", "0x02"])
    err_cnt_max: int = 10


def check_modbus_connection(
    method: Callable[..., Any],
) -> Callable[..., Any]:
    """
    Decorator to check Modbus connection before executing method.

    Verifies that the Modbus link is operational before allowing method
    execution. If connection is not available, returns error code.

    Args:
        method: The method to wrap

    Returns:
        Wrapper function that checks connection before execution
    """

    @wraps(method)
    def wrapper(
        self: ModBusHandler, *args: Any, **kwargs: Any
    ) -> tuple[Any, str, str]:
        """Check connection and execute method."""
        # pylint: disable=protected-access
        if not self._test_connection():
            logger.error("Modbus connection not available")
            return -1, self.name, MbCode.LINK_ERR.name

        if not self._modbus_link:
            self._setup_connection()
            if not self._modbus_link:
                logger.error("Failed to setup Modbus connection")
                return -1, self.name, MbCode.LINK_ERR.name

        return method(self, *args, **kwargs)

    return wrapper


# pylint: disable=too-many-instance-attributes
class ModBusHandler:
    """Handler for Modbus RTU communication with LCM.

    Manages serial connection and communication protocol for reading/writing
    parameters, retrieving logs, and uploading firmware packages.
    """

    def __init__(self) -> None:
        """Initialize Modbus handler and establish connection."""
        self._modbus_link = False
        self.name = MbCode.SOURCE.value
        self.rs_port = "/dev/ttyLP1"
        self.gpio_chip = "/dev/gpiochip1"
        self.de_line = 2
        self.lcm_address = 0x0A
        self.client: ModbusSerialClient | None = None

        # Initialize disk handler
        try:
            self.disk_handler = DiskHandler()
        except SystemExit as e:
            logger.error("Fatal error during DiskHandler initialization")
            raise SystemExit from e

        # Initialize configurations
        self.write_record = WriteRecordConfig()
        self.log = self._init_log_config()

        # Parameter definitions
        self.param_dict: dict[str, str] = {
            "LCM_SOFTWARE_VERSION": "77",
            "RESET_ALARM_LEVEL_1": "102",
            "RESET_ALARM_LEVEL_2": "103",
            "RESET_ALARM_LEVEL_3": "104",
        }

        # Setup connection
        self._setup_connection()

    def _init_log_config(self) -> LogConfig:
        """Initialize log configuration with disk handler path."""
        config = LogConfig()
        config.storage_path = Path(self.disk_handler.get_trace_log_path())
        return config

    def _setup_connection(self) -> None:
        """Open Modbus serial connection on the onboard RS485 bus."""
        self._modbus_link = os.path.exists(self.rs_port)
        logger.info("Using port %s", self.rs_port)

        self.client = ModbusSerialClient(
            port=self.rs_port,
            baudrate=115200,
            timeout=3,
            parity="N",
            stopbits=1,
            bytesize=8,
        )

        self.client.connect()
        try:
            if self.client.socket is not None:
                self.client.socket.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.client.socket = RS485Serial(
            port=self.rs_port,
            baudrate=115200,
            timeout=3,
            parity="N",
            stopbits=1,
            bytesize=8,
            gpio_chip=self.gpio_chip,
            de_line=self.de_line,
        )

    def _test_connection(self) -> bool:
        """Test if onboard RS485 device exists.

        Returns:
            True if the tty path is present, False otherwise.
        """
        if os.path.exists(self.rs_port):
            return True
        logger.error("No Modbus device found at '%s'", self.rs_port)
        self._modbus_link = False
        return False

    @check_modbus_connection
    def read_parameter(self, par: list[str]) -> tuple[Any, str, str]:
        """
        Read value of parameter from LCM.

        Args:
            par: List with single parameter number as string

        Returns:
            Tuple of (parameter_value, handler_name, error_code)
        """
        ret = self._validate_inputs(par, 1)

        if ret[0] != 0:
            return ret

        logger.info("Read parameter %s", par)

        max_tries = 3
        for i in range(max_tries):
            # Read parameter. Assign all exceptions from pymodbus to COM_ERR
            try:
                response = self._serial_read_param(par[0])
            except Exception as e:  # pylint: disable=broad-exception-caught
                response = str(type(e).__name__)

            ret = self._validate_read_param_response(response)
            if ret[2] == MbCode.NO_ERR.name:
                break

            # This error is returned if parameter does not exist or is not
            # externally readable, no need to try again
            if ret[2] == MbCode.LCM_ERR.name:
                break

            logger.warning(
                "Modbus error %s, try: %d of %d", ret[2], i + 1, max_tries
            )

        return ret

    @check_modbus_connection
    def write_parameter(self, args: list[str]) -> tuple[Any, str, str]:
        """
        Write value to LCM parameter.

        Handles special parameters for reset alarms, speed config, and
        floor locks.

        Args:
            args: List of [parameter, value] to write

        Returns:
            Tuple of (status, handler_name, error_code)
        """
        err = MbCode.NO_ERR.name
        sw_installation_cmd = "108"
        lift_speed_parameter = "30"
        floor_lock_parameter = "363"

        ret = self._validate_inputs(args, 2)

        if ret[0] != 0:
            return ret

        param = args[0]
        value = args[1]

        logger.info("Write parameter %s with value %s", param, value)

        # Check if reboot signal
        if param == sw_installation_cmd:
            self._handle_reboot_request(value)

        # Check if custom lift speed request
        if param == lift_speed_parameter:
            err = self._handle_speed_config(value)

        # Check if floor lock request
        if param == floor_lock_parameter:
            err = self._handle_floor_lock(value)

        if err != MbCode.NO_ERR.name:
            logger.error("Failed to set custom parameter. Returned %s.", err)
            return -1, self.name, err

        # Check if reset alarms request
        value, err = self._handle_reset_alarms(param, value)
        if err != MbCode.NO_ERR.name:
            logger.error(
                "Failed to prepare for write to reset alarms params. "
                "Returned %s", err
            )
            return -1, self.name, err

        max_tries = 3
        for i in range(max_tries):
            # Write parameter. Assign all exceptions from pymodbus to COM_ERR
            try:
                response = self._serial_write_param(param, value)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Modbus error: %s", e)
                response = str(type(e).__name__)

            ret = self._validate_write_param_response(response, param)
            if ret[2] == MbCode.NO_ERR.name:
                break

            logger.error(
                "Modbus error %s, try: %d of %d", ret[2], i + 1, max_tries
            )

        return ret

    @check_modbus_connection
    def log_generate(self, log_type: list[str]) -> tuple[Any, str, str]:
        """
        Generate and retrieve trace log from LCM buffer.

        Args:
            log_type: List with [log_type, length] where log_type is '0x06'
                     or '0x02'

        Returns:
            Tuple of (filename, handler_name, error_code)
        """
        # Validate inputs
        ret = self._validate_inputs(log_type, 2)

        if ret[0] != 0:
            return ret

        # Switch to log-type
        if log_type[0] in ("0x06", "0x02"):
            return self.generate_trace_log(log_type[0])

        logger.error("Log type not recognized: %s", log_type[0])
        return -1, self.name, MbCode.LOG_TYPE_ERR.name

    def generate_trace_log(self, log_type: str = "") -> tuple[Any, str, str]:
        """
        Request and retrieve trace log from LCM's trace buffer.

        Since communication diverges from Modbus spec, several attributes are
        specialised in this function. See SW-2650 for details.

        NOTES:
        1. Record lengths chosen carefully, considering SW-2650 and the
           235-byte Modbus PDU limit.
        2. Uses custom ReadFileRecord to handle non-standard LCM responses.
        3. Always retries from record 0 to stay synced with LCM read position.
        4. First record contains filename which is extracted and used.

        Args:
            log_type: Type of log ('0x06' for trace buffer, '0x02' for SRAM)

        Returns:
            Tuple of (filename, handler_name, error_code)
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        if log_type not in self.log.types:
            logger.error("Log type not recognized: %s", log_type)
            return -1, self.name, MbCode.LOG_TYPE_ERR.name

        # Set variables
        nr_records = self.log.sizes.nr_records[log_type]
        exp_rsp_len = [
            self.log.sizes.record_length * 2
            + self.log.sizes.header
            + self.log.sizes.crc
        ] * (nr_records - 1)
        exp_rsp_len.extend(
            [
                (
                    (
                        self.log.sizes.log[log_type]
                        + self.log.sizes.filename
                    )
                    % (self.log.sizes.record_length * 2)
                )
                + self.log.sizes.header
                + self.log.sizes.crc
            ]
        )

        if log_type == "0x02":
            file_type = 0x03
        elif log_type == "0x06":
            file_type = 0x00
        else:
            file_type = 0x00

        # file_number[0:1] is called 'unit' in LCM
        # file_number[2:3] is called 'fileType' in LCM
        file_number = 0x1700 + file_type

        # Initialize loop variables
        record_number = 0
        err_cnt = 0
        last_err = MbCode.NO_ERR.name
        data = b""
        self.log.filename = ""

        assert self.client is not None

        # Break when all records read or error counter reached max
        while (
            0 <= record_number < nr_records
            and err_cnt < self.log.err_cnt_max
        ):
            if record_number == 0:
                # Reinitialize data array and filename every time we retry
                data = b""
                self.log.filename = ""

            try:
                # Prepare the File Record Request
                request = ReadFileRecord.prepare_request(
                    unit=self.lcm_address,
                    type=0x06,
                    file_number=file_number,
                    record_number=record_number,
                    record_length=self.log.sizes.record_length,
                )

                try:
                    # Make the request
                    response, data_tmp = ReadFileRecord.run(
                        self.client, request, exp_rsp_len[record_number]
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(e)
                    logger.info("Trying again...")
                    err_cnt += 1
                    record_number = 0
                    last_err = MbCode.LOG_RUN_ERR.name
                    continue

                # Validate the response
                ret, idx, last_err = self._validate_read_file_response(
                    record_number,
                    response,
                    data_tmp,
                    exp_rsp_len[record_number],
                )

                # If response not valid, increment error counter, reset
                # record number (SW-2650) and try again
                if not ret:
                    logger.info("Trying again...")
                    err_cnt += 1
                    record_number = 0
                    if last_err == MbCode.NO_ERR.name:
                        last_err = MbCode.LOG_RSP_ERR.name
                    continue

                # Append the data to array
                data += data_tmp[
                    self.log.sizes.header + idx : -self.log.sizes.crc
                ]

                # Increment to next record number
                record_number += 1

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(e)
                logger.info("Trying again...")
                record_number = 0
                err_cnt += 1
                continue

        if err_cnt >= self.log.err_cnt_max:
            logger.error("Too many errors encountered %d", err_cnt)
            if last_err == MbCode.NO_ERR.name:
                last_err = MbCode.LOG_ERR_CNT.name
            return -1, self.name, last_err

        ret, fname = self._save_log(self.log.filename, data, wtype="wb")

        if not ret:
            return -1, self.name, MbCode.LOG_SAVE_ERR.name

        if (
            not self.disk_handler.check_enough_free_space()
            and last_err == MbCode.NO_ERR.name
        ):
            last_err = MbCode.DISK_LIMIT_ERR.name

        return fname, self.name, last_err

    @check_modbus_connection
    def write_upgrade_package(
        self,
        filename_list: list[str],
        up_folder: Path | None = None,
    ) -> tuple[int, str, str]:
        """
        Upload firmware upgrade package to LCM.

        Validates UP file format and header before transfer.

        Args:
            filename_list: List containing filename to upload
            up_folder: Optional path to upgrade package folder

        Returns:
            Tuple of (status, handler_name, error_code)
        """
        if not up_folder:
            up_folder = Path(self.disk_handler.get_upgrade_package_path())

        filename = filename_list[0]
        file_path = up_folder / filename
        data_list, return_code = self._get_record_data_from_file(str(file_path))

        if data_list is None:
            logger.error("Failed to get record data from file")
            return 1, self.name, return_code

        # Validate UP file to prevent transferring any random file to LCM
        if not self._validate_up_file(filename):
            return 1, self.name, MbCode.FILE_NAME_ERR.name

        if not self._validate_up_header(str(file_path)):
            return 1, self.name, MbCode.FILE_HEADER_ERR.name

        error_counter = 0
        record_number = 0
        max_tries = 20

        while record_number < len(data_list) and error_counter < max_tries:
            logger.info("Write data, record number %d", record_number)

            try:
                write_response = self._write_data(
                    record_number, data_list[record_number]
                )
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.error("Exception during writing data")
                logger.error(error)
                error_counter += 1
                continue

            response_ok = self._validate_write_file_response(write_response)
            if not response_ok:
                error_counter += 1
                continue
            record_number += 1
            error_counter = 0

        if error_counter > 0:
            logger.error("Error count: %d", error_counter)
            return 1, self.name, MbCode.FILE_TRANSFER_ERR.name

        return 0, self.name, MbCode.NO_ERR.name

    def _validate_inputs(
        self, args: list[str], args_len: int
    ) -> tuple[int, str, str]:
        """
        Validate input arguments.

        Args:
            args: Input argument list
            args_len: Expected length of list

        Returns:
            Tuple of (valid, handler_name, error_code)
        """
        if not isinstance(args, list) or len(args) != args_len:
            logger.error(
                "Not list or number of input arguments %s != %s",
                args,
                args_len,
            )
            return -1, self.name, MbCode.ARG_ERR.name

        try:
            # Test int conversion on args
            for x in args:
                if isinstance(x, str) and "0x" in x:
                    # Handle hex-strings
                    int(x, 0)
                else:
                    int(x)

        except ValueError:
            logger.error("Could not convert args to int")
            return -1, self.name, MbCode.ARG_INT_ERR.name

        return 0, self.name, MbCode.NO_ERR.name

    def _validate_read_param_response(
        self, response: Any
    ) -> tuple[Any, str, str]:
        """
        Validate response from read parameter operation.

        Args:
            response: Response object from Modbus read

        Returns:
            Tuple of (value, handler_name, error_code)
        """
        # pylint: disable=too-many-return-statements
        if isinstance(response, str):
            logger.error("Exception, modbus communication error")
            return -1, self.name, MbCode.COM_ERR.name

        if not (
            hasattr(response, "registers")
            and hasattr(response, "isError")
            and hasattr(response, "function_code")
        ):
            logger.error("Invalid response, modbus communication error")
            return -1, self.name, MbCode.COM_ERR.name

        if response.isError():
            logger.error("Modbus communication error")
            return response.function_code, self.name, MbCode.COM_ERR.name

        if len(response.registers) != 2:
            logger.error("Number of return registers incorrect")
            return -1, self.name, MbCode.REG_ERR.name

        dead = int("0xDEAD", 16)
        if (
            response.registers[0] == dead
            and response.registers[1] == dead
        ):
            logger.error("LCM returned error value")
            return -1, self.name, MbCode.LCM_ERR.name

        value = (response.registers[0] << 16) + response.registers[1]
        value = ctypes.c_long(value).value

        return value, self.name, MbCode.NO_ERR.name

    def _validate_write_param_response(
        self, response: Any, param: str
    ) -> tuple[int, str, str]:
        """
        Validate response from write parameter operation.

        Args:
            response: Response object from Modbus write
            param: Parameter that was written

        Returns:
            Tuple of (status, handler_name, error_code)
        """
        # pylint: disable=too-many-branches,too-many-statements,too-many-return-statements
        if isinstance(response, str):
            logger.error("Exception, modbus communication error")
            return -1, self.name, MbCode.COM_ERR.name

        if not (
            hasattr(response, "isError") and hasattr(response, "function_code")
        ):
            logger.error("Invalid response, modbus communication error")
            return -1, self.name, MbCode.COM_ERR.name

        if response.isError():
            logger.error("Modbus communication error")
            return -1, self.name, MbCode.COM_ERR.name

        # From code documentation `register_write_message.py`
        # "The normal response returns the function code, starting address,
        # and quantity of registers written."
        response = str(response)

        if "WriteMultipleRegisterResponse" not in response:
            logger.error(
                "Keyword missing. Response could not be decoded"
            )
            return -1, self.name, MbCode.COM_ERR.name

        try:
            rec_param = str(response).split("(")[1].split(",")[0]
            rec_count = str(response).split(")", maxsplit=1)[0].split(",")[1]
        except Exception:  # pylint: disable=broad-exception-caught
            logger.error("Parsing return values failed")
            return -1, self.name, MbCode.COM_ERR.name

        if (
            str(param)
            != str(self._convert_param_addr(rec_param, direction="rec"))
            or rec_count != "2"
        ):
            logger.error("Response could not be decoded")
            return -1, self.name, MbCode.COM_ERR.name

        return 0, self.name, MbCode.NO_ERR.name

    def _validate_read_file_response(
        self,
        record_number: int,
        response: Any,
        data_tmp: bytes,
        exp_len: int,
    ) -> tuple[bool, int, str]:
        """
        Validate response from Modbus ReadFileRecord.

        Args:
            record_number: Record number being read
            response: Modbus response object
            data_tmp: Raw response data bytes
            exp_len: Expected response length

        Returns:
            Tuple of (valid, data_index, error_code)
        """
        # pylint: disable=too-many-branches,too-many-statements
        valid = True
        err = MbCode.NO_ERR.name
        idx = 0

        # Validate input parameters
        if not (isinstance(record_number, int) and record_number >= 0):
            logger.error("Record number must be positive integer")
            valid = False

        if not hasattr(response, "isError"):
            logger.error("Response not a ModBus ReadFileRecord response")
            valid = False

        if not isinstance(data_tmp, bytes):
            logger.error("Input data must be byte string")
            valid = False

        if not (isinstance(exp_len, int) and exp_len >= 0):
            logger.error("Expected length must be positive integer")
            valid = False

        if not valid:
            # No point in proceeding, return here
            return valid, idx, MbCode.LOG_ATTR_ERR.name

        # Compute length of data
        data_len = len(data_tmp) - self.log.sizes.header - self.log.sizes.crc

        if data_len <= 0:
            logger.warning("No payload in received record")
            if valid:
                err = MbCode.LOG_NO_LD_ERR.name
                valid = False
        else:
            # Check header bytes
            if data_tmp[0] != self.log.header[0]:
                logger.warning("Linefeed not found in header")
                if valid:
                    err = MbCode.LOG_LD_PARSE_ERR.name
                    valid = False

            if data_tmp[1] != self.log.header[1]:
                logger.warning("Function code not found in header")
                if valid:
                    err = MbCode.LOG_LD_PARSE_ERR.name
                    valid = False

            if data_tmp[2] != data_len:
                logger.warning(
                    "Expected length not matched in header %s - %s",
                    data_tmp[2],
                    data_len,
                )
                if valid:
                    err = MbCode.LOG_LD_PARSE_ERR.name
                    valid = False

        if data_len != exp_len - self.log.sizes.header - self.log.sizes.crc:
            logger.warning(
                "Record length does not match expected %s - %s",
                data_len,
                exp_len,
            )
            if valid:
                err = MbCode.LOG_REC_LEN_ERR.name
                valid = False

        if response.isError():
            logger.warning("Error from modbus response %s", response)
            if valid:
                err = MbCode.LOG_RSP_ERR.name
                valid = False

        if record_number == 0:
            # The first record will contain the file name
            data_fname = data_tmp[
                self.log.sizes.header : self.log.sizes.header
                + self.log.sizes.filename
            ]
            needle = b".sw_traces"

            if needle in data_fname:
                idx = data_fname.find(needle)
                self.log.filename = os.path.join(
                    self.log.storage_path,
                    data_fname[: idx + len(needle)].decode("utf-8"),
                )
                idx = self.log.sizes.filename

            else:
                logger.warning(
                    'Keyword "%s" not found in data. Trying again...',
                    needle.decode("utf-8"),
                )
                if valid:
                    err = MbCode.LOG_FNAME_ERR.name
                    valid = False

        return valid, idx, err

    def _save_log(
        self, fname_fullpath: str, data: bytes, wtype: str = "w"
    ) -> tuple[bool, str]:
        """
        Write log data to file with timestamp and LCM version.

        Args:
            fname_fullpath: Full path to save file
            data: Binary log data
            wtype: Write mode ('wb' for binary)

        Returns:
            Tuple of (success, filename_only)
        """
        fname_ret = ""

        try:
            # Strip to dirs
            fname_dirs = os.path.abspath(os.path.dirname(fname_fullpath))

            # Strip to filename only, not full path
            fname_ret = os.path.basename(fname_fullpath)

            # Make an attempt to retrieve LCM version to include in filename
            version_str = ""
            version, _, err_code = self.read_parameter(
                [self.param_dict["LCM_SOFTWARE_VERSION"]]
            )
            if err_code == MbCode.NO_ERR.name:
                if isinstance(version, int):
                    version_str = (
                        f"{(version >> 16) & 0xFF}."
                        f"{(version >> 8) & 0xFF}."
                        f"{version & 0xFF}"
                    )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            fname_ret = (
                f"{fname_ret.split('.')[0]}"
                f"_v{version_str}"
                f"_{timestamp}"
                f".{fname_ret.split('.')[1]}"
            )

            fname_fullpath = os.path.join(fname_dirs, fname_ret)
            logger.info("Saving log file to %s", fname_fullpath)

            os.makedirs(fname_dirs, exist_ok=True)

            with open(fname_fullpath, wtype) as f:  # pylint: disable=unspecified-encoding
                f.write(data)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(e)
            logger.error("Failed to save log file")
            return False, fname_ret

        return True, fname_ret

    def _get_record_data_from_file(
        self, file_path: str
    ) -> tuple[list[bytes] | None, str]:
        """
        Split data from file into packages with maximum Modbus size.

        Args:
            file_path: Path to file to read from

        Returns:
            Tuple of (data_list, error_code)
        """
        data_list: list[bytes] = []

        try:
            with open(file_path, mode="rb") as up_file:
                __data = up_file.read(self.write_record.max_write_record_length)
                while __data:
                    data_list.append(__data)
                    __data = up_file.read(
                        self.write_record.max_write_record_length
                    )
                logger.info(
                    "UP '%s' divided into %d record numbers",
                    file_path,
                    len(data_list),
                )

        except FileNotFoundError as error:
            logger.error(error)
            return None, MbCode.FILE_NOT_FOUND.name

        if not data_list:
            logger.error("%s is empty", file_path)
            return None, MbCode.FILE_EMPTY.name

        return data_list, MbCode.NO_ERR.name

    def _validate_write_file_response(self, write_response: Any) -> bool:
        """
        Validate response after write file operation.

        Args:
            write_response: Response after write operation

        Returns:
            True if response is valid, False otherwise
        """
        if write_response.isError():
            logger.error("Write Response Error")
            logger.error(write_response)
            try:
                logger.error(write_response.message)
            except AttributeError:
                pass
            return False

        request_response = WriteFileRecordResponse(write_response)
        if request_response.isError():
            logger.error("WriteFileRecordResponse Error")
            logger.error(request_response)
            try:
                logger.error(request_response.message)  # type: ignore[attr-defined]
            except AttributeError:
                pass
            return False

        return True

    def _write_data(self, record_number: int, data: bytes) -> Any:
        """
        Prepare write request and write data over Modbus.

        Args:
            record_number: Current record number
            data: Data to be sent

        Returns:
            Response from write operation
        """
        write_request, response_length = WriteFileRecord.prepare_request(
            unit=self.lcm_address,
            record_number=record_number,
            data=data,
        )

        # Returned 'response length' is the length of the data, plus 1
        # (hard coded in PyModBus lib without comment). Change so 'response
        # length' also expects the record headers and remove hard coded plus 1.
        response_length += (
            self.write_record.request_header_size
            + self.write_record.sub_request_header_size
            - 1
        )

        # Execute the write request
        assert self.client is not None
        write_response, _ = WriteFileRecord.run(
            self.client, write_request, response_length
        )

        return write_response

    def _validate_up_file(self, filename: str) -> bool:
        """
        Validate that file seems to be a UP file.

        Args:
            filename: UP filename

        Returns:
            True if valid UP filename, False otherwise
        """
        # UP filename: 'up_<UP number>_<release version>.up'
        minimal_filename_length = len("XY.up")
        extra_characters_allowed = 10
        maximal_filename_length = len("up_XYZ_YEAR.up") + extra_characters_allowed
        file_extension = "up"

        if not (
            minimal_filename_length
            <= len(filename)
            <= maximal_filename_length
        ):
            logger.error("UP filename '%s' length is wrong", filename)
            return False

        if not filename.lower().endswith(file_extension):
            logger.error(
                "UP filename '%s' does not have correct "
                "file extension ('%s')",
                filename,
                file_extension,
            )
            return False

        return True

    def _validate_up_header(self, file_path: str) -> bool:
        """
        Validate that UP file has correct header.

        Args:
            file_path: Full path to file

        Returns:
            True if valid UP header, False otherwise
        """
        # Hex dump of UP file/header
        bytes_to_read = 16
        command = f"xxd -l {bytes_to_read} {file_path}"

        try:
            process = subprocess.run(
                command,
                check=True,
                timeout=10,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to hex dump UP file '%s'", file_path)
            logger.error(error)
            return False

        string_to_find = "aritco"
        try:
            standard_out = process.stdout.decode("latin-1")
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decode output from hex dump of UP header")
            logger.error(error)
            return False

        if string_to_find not in standard_out:
            logger.error("Could not find %s in UP header", string_to_find)
            if standard_out:
                logger.error(standard_out)
            try:
                error_out = process.stderr.decode("latin-1")
                if error_out:
                    logger.error(error_out)
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.error(error)
            return False

        logger.info("Header in UP file is correct")
        return True

    def _convert_param_addr(self, param: str | int, direction: str = "send") -> int:
        """
        Convert between LCM and Modbus parameter addressing.

        LCM requires addresses multiplied by 2 for Modbus communication.

        Args:
            param: Parameter address as string or int
            direction: 'send' to multiply by 2, 'rec' to divide by 2

        Returns:
            Converted parameter address

        Raises:
            ValueError: If param is invalid or negative result
        """
        if (isinstance(param, str) and not param.isdigit()) or isinstance(
            param, float
        ):
            logger.error(
                "Negative or float input parameters not accepted"
            )
            raise ValueError

        addr_result: int
        try:
            if direction == "send":
                addr_result = 2 * int(param)
            elif direction == "rec":
                addr_result = int(int(param) / 2)
            else:
                addr_result = int(param)

        except (ValueError, TypeError) as exc:
            logger.error("Failed to convert address")
            raise ValueError from exc

        if addr_result < 0:
            logger.error("Cannot convert non-negative addresses")
            raise ValueError

        return addr_result

    def _pack_value(self, val: str | int) -> list[int]:
        """
        Pack 32-bit value into two 16-bit registers for Modbus.

        Args:
            val: Value to pack (string or int)

        Returns:
            List of [MSB, LSB] as 16-bit unsigned integers

        Raises:
            ValueError: If value out of bounds or invalid
            TypeError: If value type cannot be converted
        """
        try:
            # Handle hex strings
            if isinstance(val, str) and "0x" in val.lower():
                val = int(val, 0)
            else:
                val = int(val)

        except ValueError as e:
            logger.error("Cannot pack value %s", e)
            raise ValueError from e

        except TypeError as e:
            logger.error("Cannot pack value. %s.", e)
            raise TypeError from e

        if val >= (1 << 32) or val < -(1 << 32):
            logger.error("Value out of bounds")
            raise ValueError

        ret_val = []
        val_msb = (val >> 16) & 0xFFFF
        val_lsb = val & 0xFFFF

        ret_val.append(val_msb)
        ret_val.append(val_lsb)

        return ret_val

    def _serial_write_param(self, param: str, val: str) -> Any:
        """
        Write single parameter value over Modbus.

        Args:
            param: Parameter address as string
            val: Value to write as string

        Returns:
            Modbus write response object
        """
        addr = self._convert_param_addr(param)
        packed = self._pack_value(val)

        assert self.client is not None
        return self.client.write_registers(
            address=addr, values=packed, device_id=self.lcm_address
        )

    def _serial_read_param(self, param: str) -> Any:
        """
        Read single parameter value over Modbus.

        Args:
            param: LCM parameter to read as string

        Returns:
            Modbus read response object
        """
        addr = self._convert_param_addr(param)

        assert self.client is not None
        return self.client.read_holding_registers(
            address=addr, count=2, device_id=self.lcm_address
        )

    def _handle_reset_alarms(self, param: str, value: str) -> tuple[str, str]:
        """
        Handle reset alarms with SW-2905 workaround.

        For LCM versions ≤349, bitshifts the value before writing.

        Args:
            param: Parameter ID
            value: Value to write

        Returns:
            Tuple of (adjusted_value, error_code)
        """
        # This is the latest sw version for which we handle this fix
        lcm_sw_version_break = 349

        reset_alarm_params = [
            self.param_dict["RESET_ALARM_LEVEL_1"],
            self.param_dict["RESET_ALARM_LEVEL_2"],
            self.param_dict["RESET_ALARM_LEVEL_3"],
        ]

        if param in reset_alarm_params:
            version, _, err_code = self.read_parameter(
                [self.param_dict["LCM_SOFTWARE_VERSION"]]
            )

            if err_code != MbCode.NO_ERR.name:
                return value, err_code

            if not isinstance(version, int):
                logger.error(
                    "Handle reset alarms not received int"
                )
                return value, MbCode.ARG_ERR.name

            if version <= lcm_sw_version_break:
                logger.info(
                    "Hotfix in RESET_ALARM for LCM version %s <= %s",
                    version,
                    lcm_sw_version_break,
                )
                try:
                    # Bitshift the value (SW-2905)
                    value = str(int(value) << 1)
                    err = MbCode.NO_ERR.name

                except (ValueError, TypeError) as e:
                    logger.error("Value to reset alarms incorrect")
                    logger.error(e)
                    err = MbCode.ARG_INT_ERR.name

                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Fatal error in handling of reset alarms value")
                    logger.error(e)
                    err = MbCode.ARG_ERR.name

            else:
                err = MbCode.NO_ERR.name

        else:
            err = MbCode.NO_ERR.name

        return value, err

    def _handle_reboot_request(self, value: str) -> None:
        """
        Handle reboot request from LCM.

        Synchronizes disk before request is sent to prevent data loss during
        reboot caused by power loss on GW.

        Args:
            value: Reboot value/command
        """
        restart_values = ["2", "4"]
        if value in restart_values:
            logger.info("Reboot signal received, synchronizing cache first.")

            cmd = "sync && journalctl --rotate && journalctl --sync"

            try:
                with subprocess.Popen(cmd, shell=True) as p:
                    p.wait(timeout=30)
                logger.info("Sync complete")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("%s", e)

    def _handle_speed_config(self, value: str) -> str:
        """
        Handle speed config request from LCM.

        Validates OSM rated speed before setting custom lift speed.

        Args:
            value: Lift speed value to set

        Returns:
            Error code
        """
        osm_speed_parameter = 359
        osm_support = 300
        min_custom_speed = 150
        max_custom_speed = 300

        ret = self.read_parameter([str(osm_speed_parameter)])
        if ret[2] != MbCode.NO_ERR.name:
            logger.error(
                "Failed to read OSM speed param, not setting custom speed"
            )
            return ret[2]

        if ret[0] != osm_support:
            logger.error(
                "Not supported OSM speed: %s, not setting custom speed",
                ret[0],
            )
            return MbCode.CUSTOM_SPEED_ERR.name

        # We know this is an int cause it was validated earlier
        new_lift_speed = int(value)
        if new_lift_speed not in range(min_custom_speed, max_custom_speed + 1):
            logger.error(
                "Custom speed value: %s is not in range [%s, %s]. "
                "Not setting this custom speed.",
                new_lift_speed,
                min_custom_speed,
                max_custom_speed,
            )
            return MbCode.CUSTOM_SPEED_ERR.name

        return MbCode.NO_ERR.name

    def _handle_floor_lock(self, value: str) -> str:
        """
        Handle floor lock write request from LCM.

        Prevents locking the fire floor.

        Args:
            value: Floor lock bitmask value

        Returns:
            Error code
        """
        fire_floor_parameter = "11"

        ret = self.read_parameter([fire_floor_parameter])
        if ret[2] != MbCode.NO_ERR.name:
            logger.error(
                "Failed to read fire floor param, not setting floor lock"
            )
            return ret[2]

        fire_floor = 1 << (ret[0] - 1)

        # We know value is an int cause it was validated earlier
        # Handle hex strings
        if isinstance(value, str) and "0x" in value.lower():
            value_int = int(value, 0)
        else:
            value_int = int(value)

        if (fire_floor & value_int) > 0:
            logger.error(
                "Fire floor (%s) cannot be locked. Rejecting lock request: %s",
                ret[0],
                value,
            )
            return MbCode.FLOOR_LOCK_ERR.name

        return MbCode.NO_ERR.name


# Script support for dev
if __name__ == "__main__":
    import sys

    mb = ModBusHandler()

    if len(sys.argv) == 2:
        if sys.argv[1].lower() == "up":
            try:
                mb.write_upgrade_package(["up_192.up"])
            except KeyboardInterrupt:
                print("Error: KeyboardInterrupt")
        elif sys.argv[1].lower() == "log":
            mb.generate_trace_log("0x06")
        else:
            result = mb.read_parameter([int(sys.argv[1])])
            print(result)
    elif len(sys.argv) == 3:
        result = mb.write_parameter([int(sys.argv[1]), int(sys.argv[2])])
        print(result)
