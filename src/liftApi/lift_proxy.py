"""LiftProxy — single entry point to lift hardware for all consumers.

Owns the matched handler + lib pair based on the identified lift type.
All lift access (cloud, WiFi, BT) goes through this proxy.
"""

import asyncio

from lib.ahl_lib import AhlLib
from lib.error_signals import LpCode
from lib.logging_config import get_logger
from lib.thousand_lib import ThousandLib
from liftApi.lift_identifier import LiftType, identify_lift
from liftApi.modbus_handler import ModBusHandler
from liftApi.rs232_handler import Rs232Handler

logger = get_logger(__name__)

IDENTIFY_MAX_RETRIES = 10
IDENTIFY_RETRY_DELAY = 5


class LiftProxy:
    """Proxy layer between consumers and lift hardware.

    Creates both handlers, identifies the lift type, and keeps only
    the matched handler + lib pair. Consumers access lift data through
    this proxy — never directly through handlers.

    Usage:
        proxy = await LiftProxy.create()
    """

    def __init__(self) -> None:
        self._handler: ModBusHandler | Rs232Handler | None = None
        self._lib: AhlLib | ThousandLib | None = None
        self._lift_type: LiftType = LiftType.UNKNOWN

    @classmethod
    async def create(cls) -> "LiftProxy":
        """Async factory — creates handlers, identifies lift, keeps matched pair.

        Returns:
            Initialized LiftProxy with the correct handler + lib for the
            connected lift, or UNKNOWN if neither responds.
        """
        proxy = cls()
        await proxy._identify_and_init()
        return proxy

    @property
    def lift_type(self) -> LiftType:
        """The identified lift type (AHL, ONE_K, or UNKNOWN)."""
        return self._lift_type

    @property
    def handler(self) -> ModBusHandler | Rs232Handler | None:
        """The matched hardware handler for the identified lift type."""
        return self._handler

    @property
    def lib(self) -> AhlLib | ThousandLib | None:
        """The parameter library for the identified lift type."""
        return self._lib

    async def _identify_and_init(self) -> None:
        """Create handlers, identify lift with retries, keep matched pair."""
        modbus_handler = await asyncio.to_thread(ModBusHandler)
        rs232_handler = await asyncio.to_thread(Rs232Handler)

        for attempt in range(IDENTIFY_MAX_RETRIES):
            self._lift_type = await identify_lift(modbus_handler, rs232_handler)
            if self._lift_type != LiftType.UNKNOWN:
                break
            if attempt < IDENTIFY_MAX_RETRIES - 1:
                logger.warning(
                    "Identification attempt %d/%d failed, retrying in %ds",
                    attempt + 1, IDENTIFY_MAX_RETRIES, IDENTIFY_RETRY_DELAY
                )
                await asyncio.sleep(IDENTIFY_RETRY_DELAY)

        match self._lift_type:
            case LiftType.AHL:
                self._handler = modbus_handler
                self._lib = AhlLib()
                logger.info("LiftProxy initialized for AHL lift")
            case LiftType.ONE_K:
                self._handler = rs232_handler
                self._lib = ThousandLib()
                logger.info("LiftProxy initialized for 1k lift")
            case LiftType.UNKNOWN:
                logger.error(
                    "%s: %s - Failed to identify lift after %d attempts",
                    LpCode.SOURCE.value, LpCode.IDENTIFY_ERR.name,
                    IDENTIFY_MAX_RETRIES
                )

    def get_param_value(self, param: int) -> tuple[int | str | None, LpCode]:
        """Read a parameter value from the lib's database.

        Args:
            param: Parameter number to read.

        Returns:
            Tuple of (value, LpCode) where value is None on INIT_ERR
            or -1 on lib errors.
        """
        if self._lib is None:
            return None, LpCode.INIT_ERR

        value, err_code_name = self._lib.get_param(param)
        try:
            return value, LpCode[err_code_name]
        except KeyError:
            logger.warning("Unknown error code from lib: %s", err_code_name)
            return value, LpCode.COM_ERR

    async def write_param(self, param: str, value: str) -> tuple[int, str, str]:
        """Write a parameter value to lift hardware via the handler.

        Args:
            param: Parameter number as string.
            value: Value to write as string.

        Returns:
            Tuple of (status, error_source, error_code) matching the
            legacy cloud API contract.
        """
        if self._handler is None:
            return -1, LpCode.SOURCE.value, LpCode.INIT_ERR.name
        return await asyncio.to_thread(
            self._handler.write_parameter, [param, value]
        )
