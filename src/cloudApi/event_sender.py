import json
import logging
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

logger = logging.getLogger(__name__)


class EventSender:
    """
    Class for sending telemetry event messages to IoT Hub.

    Attributes:
        device_client (IoTHubDeviceClient): The IoT Hub device client used to send messages.

    Methods:
        send_event(payload: dict) -> None:
    """
    
    def __init__(self, device_client: IoTHubDeviceClient):
        self.device_client = device_client

    async def send_event(self, payload: dict) -> None:
        """
        Asynchronously send a telemetry event to IoT Hub.

        Usage: await EventSender(device_client).send_event(payload)

        Args:
            payload (dict): The telemetry data to send.

        Returns:
            None
        """
        try:
            message = Message(json.dumps(payload))
            message.custom_properties["LIFT_TYPE"] = "1" # Lift type is set when GW is setting up communicationtowards lift
            
            await self.device_client.send_message(message)
            logger.info(f"Event sent: {payload}")

        except Exception as e:
            logger.error(f"Failed to send event: {e}", exc_info=True)