"""Monitor for IoT Hub connection-state changes and background exceptions."""

from azure.iot.device.aio import IoTHubDeviceClient
from lib.logging_config import get_logger

logger = get_logger(__name__)


class ConnectionMonitor:
    """Logs Azure IoT Hub connection-state changes and background exceptions.

    Registers handlers on the device client so the gateway reacts to the SDK's
    connection callbacks instead of polling. For now the handlers only log;
    future tickets add per-case behaviour (reconnect handling, lift
    notification, network-status file).
    """

    def __init__(self, device_client: IoTHubDeviceClient) -> None:
        """Store the device client whose connection state will be monitored.

        Args:
            device_client: Authenticated IoT Hub device client.
        """
        self.device_client = device_client

    def attach(self) -> None:
        """Register connection-state and background-exception handlers.

        Returns:
            None
        """
        self.device_client.on_connection_state_change = (  # type: ignore[attr-defined]
            self._on_connection_state_change
        )
        self.device_client.on_background_exception = (  # type: ignore[attr-defined]
            self._on_background_exception
        )

    async def _on_connection_state_change(self) -> None:
        """Log the new connection status reported by the SDK.

        The Python SDK handler takes no arguments; the current state is read
        from the client's ``connected`` property.

        Returns:
            None
        """
        connected = self.device_client.connected  # type: ignore[attr-defined]
        status = "CONNECTED" if connected else "DISCONNECTED"
        logger.info("Connection to IoT Hub updated: %s", status)

    async def _on_background_exception(self, exc: Exception) -> None:
        """Log an exception raised on an SDK pipeline thread.

        Args:
            exc: Exception surfaced by the SDK background pipeline.

        Returns:
            None
        """
        logger.error("IoT Hub background exception: %s", exc, exc_info=exc)
