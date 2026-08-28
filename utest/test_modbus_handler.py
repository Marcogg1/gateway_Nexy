#!/usr/bin/env python3
"""
Unit tests for ModBusHandler.

Tests cover parameter read/write operations, log generation, and special
handlers for reset alarms, speed config, and floor locks.
"""
import ctypes
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src directory to path
p = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(p))

# pylint: disable=wrong-import-position,protected-access
from liftApi.modbus_handler import (
    ModBusHandler,
    WriteRecordConfig,
    LogConfig,
    parse_int_value,
)
from lib.error_signals import MbCode


class TestParseIntValue(unittest.TestCase):
    """Tests for the shared parameter value parser."""

    def test_decimal(self) -> None:
        """Test plain decimal string."""
        assert parse_int_value("42") == 42

    def test_leading_zero_decimal(self) -> None:
        """Test leading-zero decimals parse as decimal, not octal."""
        assert parse_int_value("042") == 42

    def test_hex_lowercase(self) -> None:
        """Test 0x-prefixed hex string."""
        assert parse_int_value("0x10") == 16

    def test_hex_uppercase(self) -> None:
        """Test 0X-prefixed hex string."""
        assert parse_int_value("0X10") == 16

    def test_hex_negative(self) -> None:
        """Test negative hex string."""
        assert parse_int_value("-0x10") == -16

    def test_hex_is_bit_pattern(self) -> None:
        """Test hex above INT32_MAX normalizes to its signed 32-bit decode."""
        assert parse_int_value("0xFFFFFFFF") == -1
        assert parse_int_value("0xB2D05E00") == -1294967296

    def test_hex_beyond_32_bits_not_wrapped(self) -> None:
        """Test hex wider than 32 bits passes through for bounds rejection."""
        assert parse_int_value("0x1FFFFFFFF") == 0x1FFFFFFFF

    def test_negative(self) -> None:
        """Test negative decimal string."""
        assert parse_int_value("-1") == -1

    def test_int_passthrough(self) -> None:
        """Test int input passes through."""
        assert parse_int_value(42) == 42

    def test_invalid_raises_value_error(self) -> None:
        """Test non-numeric string raises."""
        with self.assertRaises(ValueError):
            parse_int_value("abc")


class TestWriteRecordConfig(unittest.TestCase):
    """Tests for WriteRecordConfig dataclass."""

    def test_max_write_record_length(self) -> None:
        """Test calculation of max write record length."""
        config = WriteRecordConfig()
        # 253 - 2 - 7 = 244
        assert config.max_write_record_length == 244

    def test_custom_pdu_size(self) -> None:
        """Test with custom PDU size."""
        config = WriteRecordConfig(modbus_pdu_max_size=200)
        # 200 - 2 - 7 = 191
        assert config.max_write_record_length == 191


class TestLogConfig(unittest.TestCase):
    """Tests for LogConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default LogConfig values."""
        config = LogConfig()
        assert config.filename == ""
        assert config.header == b"\n\x14"
        assert "0x06" in config.types
        assert "0x02" in config.types
        assert config.sizes.log["0x06"] == 2048
        assert config.sizes.log["0x02"] == 16 * 2048


# pylint: disable=too-many-public-methods
class TestModBusHandler(unittest.TestCase):
    """Test suite for ModBusHandler."""

    def setUp(self) -> None:
        """Setup test fixtures before each test."""
        print(f"\nSetup: {self._testMethodName}")
        # Mock serial + RS485 + disk to avoid hardware dependency
        with patch("pymodbus.client.ModbusSerialClient"), \
             patch("filemgmt.disk_handler.DiskHandler"):
            self.handler = ModBusHandler()
            self.handler.disk_handler = MagicMock()
            self.handler.disk_handler.get_trace_log_path = MagicMock(
                return_value="/tmp/logs"
            )
            self.handler.disk_handler.get_upgrade_package_path = MagicMock(
                return_value="/tmp/up"
            )
            self.handler.disk_handler.check_enough_free_space = MagicMock(
                return_value=True
            )
        assert self.handler.name == "ModBusHandler"

    def tearDown(self) -> None:
        """Cleanup after each test."""
        print(f"\nTest done: {self._testMethodName}")

    # ---- Connection Tests ----

    def test_setup_connection_marks_link_down_when_port_missing(self) -> None:
        """_modbus_link is False when the RS485 tty path does not exist."""
        assert self.handler._modbus_link is False

    def test_test_connection_returns_false_when_port_missing(self) -> None:
        """_test_connection returns False when the RS485 tty path is absent."""
        result = self.handler._test_connection()
        assert result is False
        assert self.handler._modbus_link is False

    def test_setup_connection_connects_when_port_present(self) -> None:
        """_modbus_link is True and connect() is called when the tty exists."""
        with patch("liftApi.modbus_handler.os.path.exists", return_value=True), \
             patch("liftApi.modbus_handler.ModbusSerialClient") as mock_client, \
             patch("filemgmt.disk_handler.DiskHandler"):
            handler = ModBusHandler()
        assert handler._modbus_link is True
        mock_client.return_value.connect.assert_called_once()

    # ---- Input Validation Tests ----

    def test_validate_inputs_valid(self) -> None:
        """Test validation with valid inputs."""
        ret = self.handler._validate_inputs(["100"], 1)
        assert ret[0] == 0
        assert ret[2] == MbCode.NO_ERR.name

    def test_validate_inputs_invalid_length(self) -> None:
        """Test validation with wrong argument count."""
        ret = self.handler._validate_inputs(["100", "200"], 1)
        assert ret[0] != 0
        assert ret[2] == MbCode.ARG_ERR.name

    def test_validate_inputs_invalid_type(self) -> None:
        """Test validation with non-list input."""
        ret = self.handler._validate_inputs("100", 1)  # type: ignore[arg-type]
        assert ret[0] != 0
        assert ret[2] == MbCode.ARG_ERR.name

    def test_validate_inputs_non_numeric(self) -> None:
        """Test validation with non-numeric input."""
        ret = self.handler._validate_inputs(["abc"], 1)
        assert ret[0] != 0
        assert ret[2] == MbCode.ARG_INT_ERR.name

    def test_validate_inputs_hex_string(self) -> None:
        """Test validation with hex string input."""
        ret = self.handler._validate_inputs(["0xFF"], 1)
        assert ret[0] == 0
        assert ret[2] == MbCode.NO_ERR.name

    def test_validate_inputs_uppercase_hex_string(self) -> None:
        """Test uppercase 0X hex validates the same as it packs."""
        ret = self.handler._validate_inputs(["0X10"], 1)
        assert ret[0] == 0
        assert ret[2] == MbCode.NO_ERR.name

    # ---- Parameter Conversion Tests ----

    def test_convert_param_addr_send(self) -> None:
        """Test parameter address conversion for sending."""
        converted = self.handler._convert_param_addr("100", direction="send")
        assert converted == 200

    def test_convert_param_addr_receive(self) -> None:
        """Test parameter address conversion for receiving."""
        converted = self.handler._convert_param_addr("200", direction="rec")
        assert converted == 100

    def test_convert_param_addr_invalid_float(self) -> None:
        """Test conversion fails with float."""
        with self.assertRaises(ValueError):
            self.handler._convert_param_addr(1.5)  # type: ignore[arg-type]

    def test_convert_param_addr_invalid_string(self) -> None:
        """Test conversion fails with non-numeric string."""
        with self.assertRaises(ValueError):
            self.handler._convert_param_addr("abc")

    # ---- Write Parameter Response Validation Tests ----

    @staticmethod
    def _write_response(address: int, count: int) -> MagicMock:
        """Build a WriteMultipleRegisterResponse-like mock with PDU attributes."""
        response = MagicMock(spec=["isError", "function_code", "address", "count"])
        response.isError.return_value = False
        response.function_code = 0x10
        response.address = address
        response.count = count
        return response

    def test_validate_write_param_response_match(self) -> None:
        """Test ack echoing the converted address and count 2 passes."""
        response = self._write_response(address=200, count=2)
        status, name, code = self.handler._validate_write_param_response(
            response, "100"
        )
        assert (status, name, code) == (0, "ModBusHandler", MbCode.NO_ERR.name)

    def test_validate_write_param_response_address_mismatch(self) -> None:
        """Test ack with wrong echoed address is rejected."""
        response = self._write_response(address=198, count=2)
        status, _, code = self.handler._validate_write_param_response(response, "100")
        assert (status, code) == (-1, MbCode.COM_ERR.name)

    def test_validate_write_param_response_count_mismatch(self) -> None:
        """Test ack with wrong register count is rejected."""
        response = self._write_response(address=200, count=1)
        status, _, code = self.handler._validate_write_param_response(response, "100")
        assert (status, code) == (-1, MbCode.COM_ERR.name)

    def test_validate_write_param_response_missing_pdu_attrs(self) -> None:
        """Test response lacking address/count attributes is rejected, not crash."""
        response = MagicMock(spec=["isError", "function_code"])
        response.isError.return_value = False
        response.function_code = 0x10
        status, _, code = self.handler._validate_write_param_response(response, "100")
        assert (status, code) == (-1, MbCode.COM_ERR.name)

    # ---- Read Parameter Response Validation Tests ----

    @staticmethod
    def _read_response(registers: list[int]) -> MagicMock:
        """Build a ReadHoldingRegistersResponse-like mock."""
        response = MagicMock(spec=["isError", "function_code", "registers"])
        response.isError.return_value = False
        response.function_code = 0x03
        response.registers = registers
        return response

    def test_validate_read_param_response_positive(self) -> None:
        """Test positive 32-bit value decodes from two registers."""
        response = self._read_response([0x0001, 0x0001])
        value, _, code = self.handler._validate_read_param_response(response)
        assert (value, code) == (65537, MbCode.NO_ERR.name)

    def test_validate_read_param_response_negative(self) -> None:
        """Test negative 32-bit value decodes as signed, not unsigned."""
        response = self._read_response([0xFFFF, 0xFFFF])
        value, _, code = self.handler._validate_read_param_response(response)
        assert (value, code) == (-1, MbCode.NO_ERR.name)

    def test_validate_read_param_response_negative_on_64bit_c_long(self) -> None:
        """Test sign decode is independent of platform c_long width (LP64 prod)."""
        with patch("liftApi.modbus_handler.ctypes.c_long", ctypes.c_int64):
            response = self._read_response([0xFFFF, 0xFFFF])
            value, _, code = self.handler._validate_read_param_response(response)
        assert (value, code) == (-1, MbCode.NO_ERR.name)

    def test_validate_read_param_response_int32_min(self) -> None:
        """Test INT32_MIN decodes correctly."""
        response = self._read_response([0x8000, 0x0000])
        value, _, code = self.handler._validate_read_param_response(response)
        assert (value, code) == (-(1 << 31), MbCode.NO_ERR.name)

    # ---- Value Packing Tests ----

    def test_pack_value_positive(self) -> None:
        """Test packing positive 32-bit value."""
        packed = self.handler._pack_value("65537")  # 0x00010001
        assert packed == [0x0001, 0x0001]

    def test_pack_value_zero(self) -> None:
        """Test packing zero."""
        packed = self.handler._pack_value("0")
        assert packed == [0x0000, 0x0000]

    def test_pack_value_large(self) -> None:
        """Test packing large value."""
        packed = self.handler._pack_value("0xFFFFFFFF")
        assert packed == [0xFFFF, 0xFFFF]

    def test_pack_value_negative(self) -> None:
        """Test packing negative value."""
        packed = self.handler._pack_value("-1")
        assert packed == [0xFFFF, 0xFFFF]

    def test_pack_value_int32_min(self) -> None:
        """Test packing INT32_MIN."""
        packed = self.handler._pack_value(str(-(1 << 31)))
        assert packed == [0x8000, 0x0000]

    def test_pack_value_out_of_bounds(self) -> None:
        """Test packing value out of bounds."""
        with self.assertRaises(ValueError):
            self.handler._pack_value(str(1 << 32))

    def test_pack_value_below_int32_min(self) -> None:
        """Test values below INT32_MIN are rejected, not silently wrapped."""
        with self.assertRaises(ValueError):
            self.handler._pack_value(str(-(1 << 31) - 1))

    def test_pack_value_decimal_above_int32_max(self) -> None:
        """Test decimal above INT32_MAX is rejected — it would read back negative."""
        with self.assertRaises(ValueError):
            self.handler._pack_value("3000000000")

    def test_pack_value_hex_above_int32_max(self) -> None:
        """Test hex above INT32_MAX packs as its 32-bit pattern."""
        packed = self.handler._pack_value("0xB2D05E00")
        assert packed == [0xB2D0, 0x5E00]

    def test_pack_value_invalid_type(self) -> None:
        """Test packing with invalid type."""
        with self.assertRaises(TypeError):
            self.handler._pack_value(None)  # type: ignore[arg-type]

    # ---- UP File Validation Tests ----

    def test_validate_up_file_valid(self) -> None:
        """Test valid UP filename."""
        result = self.handler._validate_up_file("up_192_20240101.up")
        assert result is True

    def test_validate_up_file_too_short(self) -> None:
        """Test UP filename too short."""
        result = self.handler._validate_up_file("a.up")
        assert result is False

    def test_validate_up_file_wrong_extension(self) -> None:
        """Test UP filename with wrong extension."""
        result = self.handler._validate_up_file("up_192_20240101.bin")
        assert result is False

    def test_validate_up_file_uppercase_extension(self) -> None:
        """Test UP filename with uppercase extension."""
        result = self.handler._validate_up_file("up_192_20240101.UP")
        assert result is True

    # ---- Special Handler Tests ----

    def test_handle_reset_alarms_no_reset_param(self) -> None:
        """Test reset alarms handler with non-reset parameter."""
        value, err = self.handler._handle_reset_alarms("100", "5")
        assert value == "5"
        assert err == MbCode.NO_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_reset_alarms_old_version(self, mock_read: MagicMock) -> None:
        """Test bitshift workaround for old LCM versions."""
        # Mock LCM version ≤349
        mock_read.return_value = (300, "ModBusHandler", MbCode.NO_ERR.name)

        value, err = self.handler._handle_reset_alarms("102", "5")

        # Value should be bitshifted: 5 << 1 = 10
        assert value == "10"
        assert err == MbCode.NO_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_reset_alarms_new_version(self, mock_read: MagicMock) -> None:
        """Test no bitshift for newer LCM versions."""
        # Mock LCM version >349
        mock_read.return_value = (400, "ModBusHandler", MbCode.NO_ERR.name)

        value, err = self.handler._handle_reset_alarms("102", "5")

        # Value should NOT be bitshifted
        assert value == "5"
        assert err == MbCode.NO_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_reset_alarms_read_error(self, mock_read: MagicMock) -> None:
        """Test reset alarms handler with read error."""
        mock_read.return_value = (
            -1,
            "ModBusHandler",
            MbCode.COM_ERR.name,
        )

        value, err = self.handler._handle_reset_alarms("102", "5")

        assert value == "5"
        assert err == MbCode.COM_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_floor_lock_valid(self, mock_read: MagicMock) -> None:
        """Test floor lock handler with valid floor."""
        # Fire floor = 3 (bit 2 set)
        mock_read.return_value = (3, "ModBusHandler", MbCode.NO_ERR.name)

        # Try to lock floor 2 (bit 1 set, value = 0x02)
        err = self.handler._handle_floor_lock("0x02")

        assert err == MbCode.NO_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_floor_lock_fire_floor(self, mock_read: MagicMock) -> None:
        """Test floor lock handler prevents fire floor lock."""
        # Fire floor = 3 (bit 2 set, value = 4)
        mock_read.return_value = (3, "ModBusHandler", MbCode.NO_ERR.name)

        # Try to lock floor 3 (bit 2 set = value 4)
        err = self.handler._handle_floor_lock("4")

        assert err == MbCode.FLOOR_LOCK_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_floor_lock_read_error(self, mock_read: MagicMock) -> None:
        """Test floor lock handler with read error."""
        mock_read.return_value = (
            -1,
            "ModBusHandler",
            MbCode.COM_ERR.name,
        )

        err = self.handler._handle_floor_lock("4")

        assert err == MbCode.COM_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_speed_config_valid(self, mock_read: MagicMock) -> None:
        """Test speed config handler with valid speed."""
        # OSM support = 300
        mock_read.return_value = (300, "ModBusHandler", MbCode.NO_ERR.name)

        err = self.handler._handle_speed_config("200")

        assert err == MbCode.NO_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_speed_config_unsupported_osm(self, mock_read: MagicMock) -> None:
        """Test speed config with unsupported OSM."""
        # OSM support != 300
        mock_read.return_value = (400, "ModBusHandler", MbCode.NO_ERR.name)

        err = self.handler._handle_speed_config("200")

        assert err == MbCode.CUSTOM_SPEED_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_speed_config_out_of_range(self, mock_read: MagicMock) -> None:
        """Test speed config with out of range value."""
        # OSM support = 300
        mock_read.return_value = (300, "ModBusHandler", MbCode.NO_ERR.name)

        err = self.handler._handle_speed_config("500")

        assert err == MbCode.CUSTOM_SPEED_ERR.name

    @patch.object(ModBusHandler, "read_parameter")
    def test_handle_speed_config_read_error(self, mock_read: MagicMock) -> None:
        """Test speed config handler with read error."""
        mock_read.return_value = (
            -1,
            "ModBusHandler",
            MbCode.COM_ERR.name,
        )

        err = self.handler._handle_speed_config("200")

        assert err == MbCode.COM_ERR.name

    def test_handle_reboot_request_no_reboot(self) -> None:
        """Test reboot handler ignores non-reboot values."""
        # Should not raise any exception
        self.handler._handle_reboot_request("1")

    @patch("subprocess.Popen")
    def test_handle_reboot_request_value_2(self, mock_popen: MagicMock) -> None:
        """Test reboot handler with value 2."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        self.handler._handle_reboot_request("2")

        mock_popen.assert_called_once()

    # ---- Log Type Validation Tests ----

    def test_log_config_types_order(self) -> None:
        """Test log types are in expected order."""
        config = LogConfig()
        # Order matters for implementation
        assert config.types[0] == "0x06"
        assert config.types[1] == "0x02"


class TestSetupConnectionReuse(unittest.TestCase):
    """Tests for stale-client handling in _setup_connection."""

    def setUp(self) -> None:
        with patch("pymodbus.client.ModbusSerialClient"), \
             patch("filemgmt.disk_handler.DiskHandler"):
            self.handler = ModBusHandler()

    def test_setup_connection_closes_stale_client(self) -> None:
        """Recreating the client must close the old one (exclusive port)."""
        stale = MagicMock()
        self.handler.client = stale
        with patch("liftApi.modbus_handler.ModbusSerialClient"):
            self.handler._setup_connection()
        stale.close.assert_called_once()

    def test_setup_connection_survives_close_failure(self) -> None:
        """A failing close must not prevent the reconnect."""
        stale = MagicMock()
        stale.close.side_effect = OSError("fd gone")
        self.handler.client = stale
        with patch("liftApi.modbus_handler.ModbusSerialClient") as mock_cls:
            self.handler._setup_connection()
        self.assertIs(self.handler.client, mock_cls.return_value)


class TestModBusHandlerClose(unittest.TestCase):
    """Tests for the idempotent close() used when the proxy drops a handler."""

    def setUp(self) -> None:
        with patch("pymodbus.client.ModbusSerialClient"), \
             patch("filemgmt.disk_handler.DiskHandler"):
            self.handler = ModBusHandler()

    def test_close_closes_client(self) -> None:
        """close() closes the underlying Modbus client."""
        client = MagicMock()
        self.handler.client = client
        self.handler.close()
        client.close.assert_called_once()

    def test_close_clears_client_reference(self) -> None:
        """close() drops the client reference so later calls hit the assert."""
        self.handler.client = MagicMock()
        self.handler.close()
        self.assertIsNone(self.handler.client)

    def test_close_is_idempotent(self) -> None:
        """A second close() is a no-op and does not re-close the client."""
        client = MagicMock()
        self.handler.client = client
        self.handler.close()
        self.handler.close()
        client.close.assert_called_once()
        self.assertIsNone(self.handler.client)

    def test_close_survives_client_failure(self) -> None:
        """A raising client.close() is logged, not propagated."""
        client = MagicMock()
        client.close.side_effect = OSError("fd gone")
        self.handler.client = client
        with self.assertLogs("liftApi.modbus_handler", level="WARNING"):
            self.handler.close()
        self.assertIsNone(self.handler.client)


if __name__ == "__main__":
    unittest.main()

    def test_close_marks_the_link_down(self):
        """A closed handler must not silently reopen the exclusive port.

        check_modbus_connection reopens the port whenever _modbus_link
        flips back to True, so close() has to clear it (AIOT-183).
        """
        self.handler._modbus_link = True
        self.handler.close()
        assert self.handler._modbus_link is False
