import logging
from azure.iot.device import MethodResponse, MethodRequest
from typing import Optional
from azure.iot.device.custom_typing import JSONSerializable
from azure.iot.device.aio import IoTHubDeviceClient

logger = logging.getLogger(__name__)


class MethodRequestHandler:
    def __init__(self, device_client: IoTHubDeviceClient) -> None:
        self.device_client = device_client  

    async def listen_for_method(self) -> None:
        while True:
            method_request = await self.device_client.receive_method_request()
            logger.info(f"Received method request: {method_request.name}")

            if method_request.name == "la.read.parameter":
                logger.info("la.read.parameter method")
                logger.debug(f"Payload: {method_request.payload}")
                response_payload: Optional[JSONSerializable] = {"result": True, "message": "la.read.parameter method executed"}
                status: int = 200
            else:
                logger.warning(f"Unknown method: {method_request.name}")
                response_payload = {"result": False, "message": "Unknown method"}
                status = 404
            # Create a MethodResponse
            method_response = MethodResponse.create_from_method_request(
                method_request, status, response_payload)
            
            await self.device_client.send_method_response(method_response)
            logger.info(f"Sent method response for: {method_request.name}")

