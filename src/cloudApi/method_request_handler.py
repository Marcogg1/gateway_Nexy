from collections.abc import Callable
from azure.iot.device import MethodResponse
from azure.iot.device.custom_typing import JSONSerializable
from azure.iot.device.aio import IoTHubDeviceClient
from lib.logging_config import get_logger

logger = get_logger(__name__)


class MethodRequestHandler:
    """Handles direct method requests received from the Azure IoT Hub cloud.

    Dispatches incoming DDM (Direct Device Method) calls to the appropriate
    handler based on the method name. Responds with a JSON payload and HTTP
    status code after each invocation.
    """

    def __init__(self, device_client: IoTHubDeviceClient) -> None:
        """Initialise the handler and build the method dispatch table.

        Args:
            device_client: Authenticated IoT Hub device client used to receive
                method requests and send responses.
        """
        self.device_client = device_client
        self._dispatch: dict[str, Callable] = {
            "gw.read.hostname":            self._gw_read_hostname,
            "gw.read.hw-version":          self._gw_read_hw_version,
            "gw.read.bom-revision":        self._gw_read_bom_revision,
            "gw.read.serial-number":       self._gw_read_serial_number,
            "gw.reboot":                   self._gw_reboot,
            "la.read.ar-number":           self._la_read_ar_number,
            "la.read.parameter":           self._la_read_parameter,
            "la.read.parameters":          self._la_read_parameters,
            "la.read.lift-type":           self._la_read_lift_type,
            "la.write.parameter":          self._la_write_parameter,
            "la.write.read.parameter":     self._la_write_read_parameter,
            "la.write.ar-number":          self._la_write_ar_number,
            "la.send.reboot-request":      self._la_send_reboot_request,
            "la.send.reset-service-memory": self._la_send_reset_service_memory,
            "la.script-request":           self._la_script_request,
            "la.gw-log-generate":          self._la_gw_log_generate,
            "la.lift-log-generate":        self._la_lift_log_generate,
            "la.ll.send-request":          self._la_ll_send_request,
            "la.fwu-trigger":              self._la_fwu_trigger,
            "ca.download-file":            self._ca_download_file,
            "ca.set.config-item":          self._ca_set_config_item,
            "ca.fwu-trigger":              self._ca_fwu_trigger,
            "lcm.fwu-trigger":             self._lcm_fwu_trigger,
        }

    async def listen_for_method(self) -> None:
        """Listen for direct method requests from the cloud and dispatch them.

        Runs an infinite loop that awaits each incoming method request, looks up
        the matching handler in the dispatch table, and sends the response back
        to the cloud. Unknown method names receive a 404 response.
        """
        while True:
            method_request = await self.device_client.receive_method_request()
            logger.info(f"Received method request: {method_request.name}")

            handler = self._dispatch.get(method_request.name)
            if handler:
                response_payload, status = await handler(method_request.payload)
            else:
                logger.warning(f"Unknown method: {method_request.name}")
                response_payload = {"result": False, "message": "Unknown method"}
                status = 404

            method_response = MethodResponse.create_from_method_request(
                method_request, status, response_payload)
            await self.device_client.send_method_response(method_response)
            logger.info(f"Sent method response for: {method_request.name}")

    async def _gw_read_hostname(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the gateway hostname."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "gw.read.hostname method executed"}, 200

    async def _gw_read_hw_version(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the gateway hardware version."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "gw.read.hw-version method executed"}, 200

    async def _gw_read_bom_revision(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the gateway bill-of-materials revision."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "gw.read.bom-revision method executed"}, 200

    async def _gw_read_serial_number(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the gateway serial number."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "gw.read.serial-number method executed"}, 200

    async def _gw_reboot(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger a gateway reboot."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "gw.reboot method executed"}, 200

    async def _la_read_ar_number(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the lift article number."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.read.ar-number method executed"}, 200

    async def _la_read_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Read a single lift parameter by index."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.read.parameter method executed"}, 200

    async def _la_read_parameters(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Read multiple lift parameters in one request."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.read.parameters method executed"}, 200

    async def _la_read_lift_type(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the lift type identifier."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.read.lift-type method executed"}, 200

    async def _la_write_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write a single lift parameter."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.write.parameter method executed"}, 200

    async def _la_write_read_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write a lift parameter and read back the new value."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.write.read.parameter method executed"}, 200

    async def _la_write_ar_number(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write the lift article number."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.write.ar-number method executed"}, 200

    async def _la_send_reboot_request(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Send a reboot request to the lift application."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.send.reboot-request method executed"}, 200

    async def _la_send_reset_service_memory(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Send a reset-service-memory command to the lift application."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.send.reset-service-memory method executed"}, 200

    async def _la_script_request(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Execute a script request on the lift application."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.script-request method executed"}, 200

    async def _la_gw_log_generate(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger gateway log generation."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.gw-log-generate method executed"}, 200

    async def _la_lift_log_generate(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger lift log generation."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.lift-log-generate method executed"}, 200

    async def _la_ll_send_request(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Send a low-level request to the lift application."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.ll.send-request method executed"}, 200

    async def _la_fwu_trigger(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger a firmware update on the lift application."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "la.fwu-trigger method executed"}, 200

    async def _ca_download_file(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Download a file to the cloud agent."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "ca.download-file method executed"}, 200

    async def _ca_set_config_item(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Set a configuration item on the cloud agent."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "ca.set.config-item method executed"}, 200

    async def _ca_fwu_trigger(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger a firmware update on the cloud agent."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "ca.fwu-trigger method executed"}, 200

    async def _lcm_fwu_trigger(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Trigger a firmware update on the lift controller module."""
        logger.debug(f"Payload: {payload}")
        # TODO: send command and payload to correct handler
        return {"result": True, "message": "lcm.fwu-trigger method executed"}, 200
