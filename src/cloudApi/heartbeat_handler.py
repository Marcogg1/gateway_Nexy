"""Heartbeat handler for periodic telemetry to Azure IoT Hub."""

import time
import asyncio
from cloudApi.event_sender import EventSender
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from lib.logging_config import get_logger
from lib.error_signals import HbCode

logger = get_logger(__name__)

DEFAULT_HEARTBEAT_INTERVAL = 900  # seconds


class HeartbeatHandler:
    """Sends periodic heartbeat telemetry to Azure IoT Hub.

    Reports uptime and signal strength on a configurable interval.
    On the first heartbeat, also reports gateway metadata via device
    twin reported properties.

    Args:
        event_sender: EventSender instance for telemetry.
        reporter: DeviceTwinReporter instance for twin properties.
        desired_handler: DeviceTwinDesiredHandler for reading interval config.
    """

    def __init__(
        self,
        event_sender: EventSender,
        reporter: DeviceTwinReporter,
        desired_handler: DeviceTwinDesiredHandler,
    ) -> None:
        self.event_sender = event_sender
        self.reporter = reporter
        self.desired_handler = desired_handler
        self._first_heartbeat = True

    async def run(self) -> None:
        """Main heartbeat loop. Runs forever, sends heartbeat on each interval."""
        logger.info("Heartbeat handler started")
        while True:
            await self.send_heartbeat()
            interval = self.get_interval()
            logger.debug(f"Next heartbeat in {interval}s")
            await asyncio.sleep(interval)

    async def send_heartbeat(self) -> None:
        """Send one heartbeat: telemetry event + first-beat metadata."""
        try:
            payload = {
                "gw.uptime": self.get_uptime(),
                "gw.rssiGsm": self.get_signal_strength(),
            }
            await self.event_sender.send_event(payload)
            logger.info("Heartbeat sent")
        except Exception as e:
            logger.error(f"{HbCode.SOURCE.value}: {HbCode.SEND_EVENT_ERR.name} - {e}", exc_info=True)

        if self._first_heartbeat:
            try:
                await self._report_first_heartbeat_metadata()
                self._first_heartbeat = False
            except Exception as e:
                logger.error(f"{HbCode.SOURCE.value}: {HbCode.REPORT_PROPERTY_ERR.name} - {e}", exc_info=True)

    async def _report_first_heartbeat_metadata(self) -> None:
        """Report gateway metadata on first heartbeat via twin properties."""
        # TODO: Read real values when hardware/config integration is available
        metadata = {
            "gw.serialNumber": "TODO",
            "gw.hardwareVersion": "TODO",
            "ca.softwareVersion": "TODO",
            "gw.wifi": "TODO",
        }
        for key, value in metadata.items():
            await self.reporter.report_property(key, value)
        logger.info("First heartbeat metadata reported")

    def get_interval(self) -> int:
        """Get heartbeat interval from desired properties, or default.

        Reads ``intervals.cloudAgentHeartbeat`` from device twin desired
        properties. Falls back to DEFAULT_HEARTBEAT_INTERVAL on missing
        or invalid values.

        Returns:
            Heartbeat interval in seconds.
        """
        try:
            intervals = self.desired_handler.desired_properties.get("intervals", {})
            value = intervals.get("cloudAgentHeartbeat")
            if value is not None:
                interval = int(value)
                if interval > 0:
                    return interval
                logger.warning(
                    f"Heartbeat interval {interval}s is not positive, "
                    f"using default {DEFAULT_HEARTBEAT_INTERVAL}s"
                )
        except (ValueError, TypeError, AttributeError):
            logger.warning(
                f"{HbCode.SOURCE.value}: {HbCode.INTERVAL_READ_ERR.name} - "
                f"Invalid heartbeat interval, using default {DEFAULT_HEARTBEAT_INTERVAL}s"
            )
        return DEFAULT_HEARTBEAT_INTERVAL

    def get_uptime(self) -> int:
        """Get system uptime in seconds.

        Returns:
            System uptime as integer seconds.
        """
        return int(time.monotonic())

    def get_signal_strength(self) -> str:
        """Get signal strength (RSSI).

        Returns:
            Signal strength string. Currently stubbed as 'N/A'.
        """
        # TODO: Implement when GSM container integration is available
        return "N/A"
