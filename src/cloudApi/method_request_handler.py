import logging
from azure.iot.device import MethodResponse
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

            if method_request.name == "gw.read.hostname":
                logger.info("gw.read.hostname method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload: JSONSerializable = {"result": True, "message": "gw.read.hostname method executed"}
                status: int = 200
            elif method_request.name == "gw.read.hw-version":
                logger.info("gw.read.hw-version method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "gw.read.hw-version method executed"}
                status = 200
            elif method_request.name == "gw.read.bom-revision":
                logger.info("gw.read.bom-revision method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "gw.read.bom-revision method executed"}
                status = 200
            elif method_request.name == "gw.read.serial-number":
                logger.info("gw.read.serial-number method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "gw.read.serial-number method executed"}
                status = 200
            elif method_request.name == "gw.reboot":
                logger.info("gw.reboot method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "gw.reboot method executed"}
                status = 200
            elif method_request.name == "la.read.ar-number":
                logger.info("la.read.ar-number method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.read.ar-number method executed"}
                status = 200
            elif method_request.name == "la.read.parameter":
                logger.info("la.read.parameter method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.read.parameter method executed"}
                status = 200
            elif method_request.name == "la.read.parameters":
                logger.info("la.read.parameters method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.read.parameters method executed"}
                status = 200
            elif method_request.name == "la.read.lift-type":
                logger.info("la.read.lift-type method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.read.lift-type method executed"}
                status = 200
            elif method_request.name == "la.write.parameter":
                logger.info("la.write.parameter method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.write.parameter method executed"}
                status = 200
            elif method_request.name == "la.write.read.parameter":
                logger.info("la.write.read.parameter method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.write.read.parameter method executed"}
                status = 200
            elif method_request.name == "la.write.ar-number":
                logger.info("la.write.ar-number method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.write.ar-number method executed"}
                status = 200
            elif method_request.name == "la.send.reboot-request":
                logger.info("la.send.reboot-request method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.send.reboot-request method executed"}
                status = 200
            elif method_request.name == "la.send.reset-service-memory":
                logger.info("la.send.reset-service-memory method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.send.reset-service-memory method executed"}
                status = 200
            elif method_request.name == "la.script-request":
                logger.info("la.script-request method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.script-request method executed"}
                status = 200
            elif method_request.name == "la.gw-log-generate":
                logger.info("la.gw-log-generate method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.gw-log-generate method executed"}
                status = 200
            elif method_request.name == "la.lift-log-generate":
                logger.info("la.lift-log-generate method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.lift-log-generate method executed"}
                status = 200
            elif method_request.name == "la.ll.send-request":
                logger.info("la.ll.send-request method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.ll.send-request method executed"}
                status = 200
            elif method_request.name == "la.fwu-trigger":
                logger.info("la.fwu-trigger method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "la.fwu-trigger method executed"}
                status = 200
            elif method_request.name == "ca.download-file":
                logger.info("ca.download-file method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "ca.download-file method executed"}
                status = 200
            elif method_request.name == "ca.set.config-item":
                logger.info("ca.set.config-item method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "ca.set.config-item method executed"}
                status = 200
            elif method_request.name == "ca.fwu-trigger":
                logger.info("ca.fwu-trigger method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "ca.fwu-trigger method executed"}
                status = 200
            elif method_request.name == "lcm.fwu-trigger":
                logger.info("lcm.fwu-trigger method")
                logger.debug(f"Payload: {method_request.payload}")
                # TODO: send command and payload to correct handler
                response_payload = {"result": True, "message": "lcm.fwu-trigger method executed"}
                status = 200
            else:
                logger.warning(f"Unknown method: {method_request.name}")
                response_payload = {"result": False, "message": "Unknown method"}
                status = 404
            # Create a MethodResponse
            method_response = MethodResponse.create_from_method_request(
                method_request, status, response_payload)
            
            await self.device_client.send_method_response(method_response)
            logger.info(f"Sent method response for: {method_request.name}")
