"""
Lift type identification at gateway startup.

Probes ModbusHandler (AHL) and RS232Handler (1k) sequentially to determine
which lift type is connected. Runs during startup and, while the type is
still UNKNOWN, is re-run periodically in the background by LiftProxy
(AIOT-183) — a lift powered on after the gateway is picked up then. Once
identified, the lift type is assumed constant for the rest of the power
cycle.
"""

import asyncio
from enum import Enum, unique
from typing import TYPE_CHECKING

from lib.error_signals import MbCode, Rs232Code
from lib.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover - avoids an import cycle
    from liftApi.modbus_handler import ModBusHandler
    from liftApi.rs232_handler import Rs232Handler

logger = get_logger(__name__)

LCM_SOFTWARE_VERSION_PARAM = "77"


@unique
class LiftType(Enum):
    """Lift product line connected to the gateway."""
    UNKNOWN = "unknown"
    AHL = "AHL"
    ONE_K = "1k"


async def identify_lift(
    modbus_handler: "ModBusHandler | None",
    rs232_handler: "Rs232Handler | None",
    *,
    quiet: bool = False,
) -> LiftType:
    """Probe handlers to determine which lift type is connected.

    Tries ModbusHandler first (AHL lift). If that fails, tries
    RS232Handler (1k lift). Returns UNKNOWN if neither responds.

    The underlying handler calls are synchronous (serial I/O), so they
    are offloaded to a thread via asyncio.to_thread() to avoid blocking
    the event loop.

    Args:
        modbus_handler: ModBusHandler instance (or None to skip).
        rs232_handler: Rs232Handler instance (or None to skip).
        quiet: When True, the per-round probe-failure lines are logged at
            DEBUG instead of INFO/WARNING. Used by the background
            re-identification loop (AIOT-183 FR-010), which would
            otherwise flood the log with one burst per probe interval.
            Success lines stay at INFO regardless.

    Returns:
        The identified LiftType.
    """
    def log_probe_failure(msg: str, *args: object) -> None:
        """Log a per-round probe failure, demoted to DEBUG when quiet."""
        if quiet:
            logger.debug(msg, *args)
        else:
            logger.info(msg, *args)

    def log_round_miss(msg: str, *args: object) -> None:
        """Log the end-of-round 'nothing responded' line, quiet-aware."""
        if quiet:
            logger.debug(msg, *args)
        else:
            logger.warning(msg, *args)

    if modbus_handler is not None:
        try:
            _, _, err = await asyncio.to_thread(
                modbus_handler.read_parameter, [LCM_SOFTWARE_VERSION_PARAM]
            )
            if err == MbCode.NO_ERR.name:
                logger.info("Lift identified as AHL (Modbus responded)")
                return LiftType.AHL
            log_probe_failure("Modbus probe failed with %s, trying RS232", err)
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
            log_probe_failure("RS232 probe failed with %s", err)
        except Exception as e:
            logger.warning("RS232 probe raised exception: %s", e, exc_info=True)
    else:
        logger.info("No RS232Handler provided, skipping 1k probe")

    log_round_miss("Neither handler responded — lift type is UNKNOWN")
    return LiftType.UNKNOWN
