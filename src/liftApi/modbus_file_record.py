"""
Modbus file record operations with customizations for LCM communication.

Parts extracted from pymodbus library [version 2.1.0] with Aritco-specific
modifications marked as ARITCO_DEV. Modifications address SW-2650 issues with
LCM response handling in file transfer operations.

This module provides custom implementations of Modbus file record operations
that properly handle the non-standard response format from Aritco LCM units.
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any

from pymodbus import utilities
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu.file_message import (
    FileRecord,
    ReadFileRecordRequest,
    WriteFileRecordRequest,
)

from lib.logging_config import get_logger

logger = get_logger(__name__)


class FileRecordAritco(FileRecord):
    """Base class for Aritco-customized Modbus file record operations."""

    @staticmethod
    def run(
        ser_client: ModbusSerialClient,
        request: Any,
        exp_len: int,
    ) -> tuple[Any, bytes]:
        """
        Run Modbus ReadFileRecord request and receive response.

        This method has been extracted from the pymodbus library and is a
        customized clone of ModbusTransactionManager.execute() to handle
        Aritco LCM non-standard responses (SW-2650).

        Args:
            ser_client: ModbusSerialClient instance
            request: ReadFileRecord request object
            exp_len: Expected length of response in bytes

        Returns:
            Tuple of (response, raw_data) where response is the pymodbus-styled
            response and data is the raw unparsed response bytes
        """
        _logger = logging.getLogger(__name__)

        # Local Any-typed aliases for pymodbus 2.x internal APIs accessed by
        # ARITCO_DEV customizations (SW-2650). These private attributes do not
        # have public type stubs in pymodbus 3.x.
        transaction: Any = ser_client.transaction
        framer: Any = ser_client.framer
        ModbusTransactionState: Any = getattr(utilities, "ModbusTransactionState", None)

        with transaction._transaction_lock:
            try:
                _logger.debug(
                    f"Current transaction state - "
                    f"{ModbusTransactionState.to_string(transaction.client.state)}"
                )
                retries = transaction.retries
                request.transaction_id = transaction.getNextTID()
                _logger.debug(f"Running transaction {request.transaction_id}")

                _buffer = utilities.hexlify_packets(framer._buffer)
                if _buffer:
                    _logger.debug(f"Clearing current Frame: {_buffer}")
                    transaction.client.framer.resetFrame()

                # ARITCO_DEV: Manually set expected response length so pymodbus
                # waits for the entire response. Otherwise it collects data in
                # batches but fails to stitch them together (SW-2650)
                expected_response_length = exp_len

                # ARITCO_DEV: Change WriteFileRecordRequest from PDU size to ADU
                if isinstance(request, WriteFileRecordRequest):
                    expected_response_length = (
                        transaction._calculate_response_length(
                            expected_response_length
                        )
                    )

                # ARITCO_DEV: Set full = False as our implementation will not
                # trigger cases that would change expected response length
                full = False

                response, last_exception = transaction._transact(
                    request,
                    expected_response_length,
                    full=full,
                )

                # ARITCO_DEV: Extract the raw data from response before sanity
                # checking (SW-2650). Save it while we process through pymodbus
                # which validates CRC and other attributes
                data = response

                if not response and (
                    request.unit_id not in transaction._no_response_devices
                ):
                    transaction._no_response_devices.append(
                        request.unit_id
                    )
                elif (
                    request.unit_id in transaction._no_response_devices
                    and response
                ):
                    transaction._no_response_devices.remove(request.unit_id)

                if not response and transaction.retry_on_empty and retries:
                    while retries > 0:
                        if hasattr(transaction.client, "state"):
                            _logger.debug(
                                "RESETTING Transaction state to 'IDLE' for retry"
                            )
                            transaction.client.state = ModbusTransactionState.IDLE
                        _logger.debug(f"Retry on empty - {retries}")
                        response, last_exception = (
                            transaction._transact(request, expected_response_length)
                        )
                        if not response:
                            retries -= 1
                            continue
                        # Remove entry
                        transaction._no_response_devices.remove(request.unit_id)
                        break

                addTransaction = partial(
                    transaction.addTransaction,
                    tid=request.transaction_id,
                )
                transaction.client.framer.processIncomingPacket(
                    response, addTransaction, request.unit_id
                )
                response = transaction.getTransaction(request.transaction_id)
                if not response:
                    if len(transaction.transactions):
                        response = transaction.getTransaction(tid=0)
                    else:
                        last_exception = last_exception or (
                            "No Response received from the remote unit"
                            "/Unable to decode response"
                        )
                        response = ModbusIOException(last_exception, request.function_code)

                if hasattr(ser_client, "state"):
                    _logger.debug(
                        "Changing transaction state from 'PROCESSING REPLY' "
                        "to 'TRANSACTION_COMPLETE'"
                    )
                    transaction.client.state = ModbusTransactionState.TRANSACTION_COMPLETE

                # ARITCO_DEV: Return both response and raw data (pymodbus returns
                # response only)
                return response, data

            except ModbusIOException as ex:
                # Handle decode errors in processIncomingPacket method
                _logger.exception(ex)
                ser_client.state = ModbusTransactionState.TRANSACTION_COMPLETE  # type: ignore[attr-defined]
                # ARITCO_DEV: Raise exception instead of returning (pymodbus returns)
                raise ex


class ReadFileRecord(FileRecordAritco):
    """Prepares and executes Modbus ReadFileRecord requests."""

    @staticmethod
    def prepare_request(
        unit: int,
        type: int,
        file_number: int,
        record_number: int,
        record_length: int,
    ) -> ReadFileRecordRequest:
        """
        Prepare a Modbus ReadFileRecord request packet.

        Args:
            unit: Modbus address of remote unit
            type: Modbus reference type (e.g. 0x06)
            file_number: File number to read
            record_number: Record number to read
            record_length: Length of record to read in words

        Returns:
            ReadFileRecordRequest packet ready to send
        """
        records = []
        record = FileRecord(
            file_number=file_number,
            record_number=record_number,
            record_length=record_length,
        )
        records.append(record)

        request = ReadFileRecordRequest(records=records, dev_id=unit)
        return request


class WriteFileRecord(FileRecordAritco):
    """Prepares and executes Modbus WriteFileRecord requests."""

    @staticmethod
    def prepare_request(
        unit: int,
        record_number: int,
        data: bytes,
    ) -> tuple[WriteFileRecordRequest, int]:
        """
        Prepare a Modbus WriteFileRecord request packet.

        Args:
            unit: Modbus address of remote unit
            record_number: Record number to write
            data: Data bytes to write

        Returns:
            Tuple of (WriteFileRecordRequest packet, response_length)
        """
        file_number = 0x0001  # Single file to transfer
        request_record = FileRecord(
            file_number=file_number,
            record_number=record_number,
            record_data=data,
        )
        write_request = WriteFileRecordRequest([request_record], dev_id=unit)

        # response_length: data words + 1 (matches pymodbus 2.x FileRecord.response_length)
        response_length = len(request_record.record_data) // 2 + 1
        return write_request, response_length
