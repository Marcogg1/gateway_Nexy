"""
Lift type identification at gateway startup.

Probes ModbusHandler (AHL) and RS232Handler (1k) sequentially to determine
which lift type is connected. Runs once during startup — the identified
lift type is assumed constant for the entire power cycle.
"""

import asyncio
from enum import Enum, unique

from lib.error_signals import MbCode, Rs232Code
from lib.logging_config import get_logger

logger = get_logger(__name__)

LCM_SOFTWARE_VERSION_PARAM = "77"


@unique
class LiftType(Enum):
    """Lift product line connected to the gateway."""
    UNKNOWN = "unknown"
    AHL = "AHL"
    ONE_K = "1k"


async def identify_lift(modbus_handler, rs232_handler) -> LiftType:
    """Probe handlers to determine which lift type is connected.

    Tries ModbusHandler first (AHL lift). If that fails, tries
    RS232Handler (1k lift). Returns UNKNOWN if neither responds.

    The underlying handler calls are synchronous (serial I/O), so they
    are offloaded to a thread via asyncio.to_thread() to avoid blocking
    the event loop.

    Args:
        modbus_handler: ModBusHandler instance (or None to skip).
        rs232_handler: Rs232Handler instance (or None to skip).

    Returns:
        The identified LiftType.
    """
    if modbus_handler is not None:
        try:
            _, _, err = await asyncio.to_thread(
                modbus_handler.read_parameter, [LCM_SOFTWARE_VERSION_PARAM]
            )
            if err == MbCode.NO_ERR.name:
                logger.info("Lift identified as AHL (Modbus responded)")
                return LiftType.AHL
            logger.info("Modbus probe failed with %s, trying RS232", err)
        except Exception:
            logger.warning("Modbus probe raised exception, trying RS232", exc_info=True)
    else:
        logger.info("No ModbusHandler provided, skipping AHL probe")

    if rs232_handler is not None:
        try:
            _, _, err = await asyncio.to_thread(
                rs232_handler.get_ar_version
            )
            if err == Rs232Code.NO_ERR.name:
                logger.info("Lift identified as 1k (RS232 responded)")
                return LiftType.ONE_K
            logger.info("RS232 probe failed with %s", err)
        except Exception:
            logger.warning("RS232 probe raised exception", exc_info=True)
    else:
        logger.info("No RS232Handler provided, skipping 1k probe")

    logger.warning("Neither handler responded — lift type is UNKNOWN")
    return LiftType.UNKNOWN
