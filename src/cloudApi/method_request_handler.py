import time
from collections.abc import Awaitable, Callable

from azure.iot.device import MethodResponse
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device.custom_typing import JSONSerializable

from config import Config
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.file_download import download_file
from lib.error_signals import LpCode, MrhCode
from lib.logging_config import get_logger
from liftApi.lift_identifier import LiftType
from liftApi.lift_proxy import LiftProxy

logger = get_logger(__name__)

_Handler = Callable[[JSONSerializable], Awaitable[tuple[JSONSerializable, int]]]

_LIFT_TYPE_CODE = {LiftType.UNKNOWN: "0", LiftType.AHL: "1", LiftType.ONE_K: "2"}


def _now() -> int:
    """Current unix timestamp as an int (patch-friendly seam for tests)."""
    return int(time.time())


class MethodRequestHandler:
    """Handles direct method requests received from the Azure IoT Hub cloud.

    Dispatches incoming DDM (Direct Device Method) calls to the appropriate
    handler based on the method name. Responds with a JSON payload and HTTP
    status code after each invocation.
    """

    def __init__(
        self,
        device_client: IoTHubDeviceClient,
        proxy: LiftProxy,
        reporter: DeviceTwinReporter,
        desired_handler: DeviceTwinDesiredHandler,
    ) -> None:
        """Initialise the handler and build the method dispatch table.

        Args:
            device_client: Authenticated IoT Hub device client.
            proxy: LiftProxy for all hardware access.
            reporter: Twin reporter for identity properties (AR number).
            desired_handler: Source of remote-tunable config (download cap).
        """
        self.device_client = device_client
        self._proxy = proxy
        self._reporter = reporter
        self._desired_handler = desired_handler
        self._dispatch: dict[str, _Handler] = {
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
            logger.info("Received method request: %s", method_request.name)

            try:
                handler = self._dispatch.get(method_request.name)
                if handler:
                    response_payload, status = await handler(method_request.payload)
                else:
                    logger.warning("Unknown method: %s", method_request.name)
                    response_payload = {"result": False, "message": "Unknown method"}
                    status = 404

                method_response = MethodResponse.create_from_method_request(
                    method_request, status, response_payload)
                await self.device_client.send_method_response(method_response)
                logger.info("Sent method response for: %s", method_request.name)

            except Exception:
                logger.exception("Unhandled error dispatching method: %s", method_request.name)
                try:
                    error_response = MethodResponse.create_from_method_request(
                        method_request, 500, {"result": False, "message": "Internal error"})
                    await self.device_client.send_method_response(error_response)
                except Exception:
                    logger.exception("Failed to send error response for: %s", method_request.name)

    # --- response/validation helpers ---

    def _arg_error(self) -> tuple[JSONSerializable, int]:
        """400 envelope for a malformed payload."""
        return {"ts": _now(), "es": MrhCode.SOURCE.value, "ec": MrhCode.ARG_ERR.name}, 400

    @staticmethod
    def _get_str(payload: JSONSerializable, key: str) -> str | None:
        """Return payload[key] as a string, or None if missing/not a dict."""
        if not isinstance(payload, dict) or key not in payload:
            return None
        return str(payload[key])

    def _download_max_bytes(self) -> int:
        """Effective download size cap: twin desired property, else config default."""
        default = Config.DOWNLOAD_MAX_BYTES_DEFAULT
        try:
            raw = self._desired_handler.desired_properties.get("downloadMaxBytes")
            if raw is not None:
                value = int(raw)
                if value > 0:
                    return value
        except (TypeError, ValueError, AttributeError):
            logger.debug("Invalid downloadMaxBytes in desired properties, using default")
        return default

    @staticmethod
    def _collect_param_ids(payload: JSONSerializable) -> list[int] | None:
        """Build the param-id list from a parameters[] array and/or from/to range.

        Returns None if the payload is not a dict or yields no ids.
        """
        if not isinstance(payload, dict):
            return None
        ids: list[int] = []
        try:
            for p in payload.get("parameters", []) or []:
                ids.append(int(p))
            if "from" in payload and "to" in payload:
                for p in range(int(payload["from"]), int(payload["to"]) + 1):
                    ids.append(p)
        except (TypeError, ValueError):
            return None
        return ids or None

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
        """Read the article (AR) number live from hardware."""
        value, source, code = await self._proxy.read_ar_number()
        if code == "NO_ERR":
            return {"ts": _now(), "v": str(value)}, 200
        return {"ts": _now(), "es": source, "ec": code}, 200

    async def _la_read_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Read a single lift parameter from the cache."""
        param = self._get_str(payload, "parameter")
        if param is None:
            return self._arg_error()
        value, code = self._proxy.get_param_value(int(param))
        item: dict = {"p": param, "v": str(value)}
        env: dict = {"ts": _now(), "d": [item]}
        if code != LpCode.NO_ERR:
            item["ec"] = code.name
            env["es"] = LpCode.SOURCE.value
        return env, 200

    async def _la_read_parameters(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Read multiple lift parameters from the cache in one request."""
        ids = self._collect_param_ids(payload)
        if ids is None:
            return self._arg_error()
        items: list = []
        any_err = False
        for pid in ids:  # pylint: disable=not-an-iterable
            value, code = self._proxy.get_param_value(pid)
            item: dict = {"p": str(pid), "v": str(value)}
            if code != LpCode.NO_ERR:
                item["ec"] = code.name
                any_err = True
            items.append(item)
        env: dict = {"ts": _now(), "d": items}
        if any_err:
            env["es"] = LpCode.SOURCE.value
        return env, 200

    async def _la_read_lift_type(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Return the identified lift type as a compact code (0/1/2)."""
        lt = _LIFT_TYPE_CODE.get(self._proxy.lift_type, "0")
        return {"ts": _now(), "lt": lt}, 200

    async def _la_write_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write a single lift parameter and emit telemetry on success."""
        param = self._get_str(payload, "parameter")
        value = self._get_str(payload, "value")
        if param is None or value is None:
            return self._arg_error()
        status, source, code = await self._proxy.write_param(param, value)
        item: dict = {"p": param, "v": value, "s": str(status)}
        env: dict = {"ts": _now(), "d": [item]}
        if status == 0:
            await self._proxy.push_param_event([int(param)])
        else:
            item["ec"] = code
            env["es"] = source
        return env, 200

    async def _la_write_read_parameter(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write a parameter, then read it back from the (now-updated) cache."""
        param = self._get_str(payload, "parameter")
        value = self._get_str(payload, "value")
        if param is None or value is None:
            return self._arg_error()
        status, source, code = await self._proxy.write_param(param, value)
        if status != 0:
            return {
                "ts": _now(),
                "es": source,
                "d": [{"p": param, "v": value, "s": str(status), "ec": code}],
            }, 200
        await self._proxy.push_param_event([int(param)])
        rb_value, rb_code = self._proxy.get_param_value(int(param))
        item: dict = {"p": param, "v": str(rb_value), "s": str(status)}
        env: dict = {"ts": _now(), "d": [item]}
        if rb_code != LpCode.NO_ERR:
            item["ec"] = rb_code.name
            env["es"] = LpCode.SOURCE.value
        return env, 200

    async def _la_write_ar_number(self, payload: JSONSerializable) -> tuple[JSONSerializable, int]:
        """Write the article (AR) number; report identity to the twin on success."""
        value = self._get_str(payload, "value")
        if value is None:
            return self._arg_error()
        actual, source, code = await self._proxy.write_ar_number(value)
        if code == "NO_ERR":
            await self._reporter.report_property("la.arNumber", str(actual))
            return {"ts": _now(), "w": value, "v": str(actual), "s": "0"}, 200
        return {"ts": _now(), "w": value, "v": "-1", "s": "-1", "es": source, "ec": code}, 200

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
        """Download a file to a persistent, type-mapped folder (security-checked)."""
        uri = self._get_str(payload, "uri")
        type_code = self._get_str(payload, "type")
        if uri is None or type_code is None:
            return self._arg_error()
        filename, fullpath, code = await download_file(
            uri, type_code, self._download_max_bytes())
        if code == MrhCode.NO_ERR.name:
            return {"ts": _now(), "fn": filename, "fp": fullpath}, 200
        return {"ts": _now(), "es": MrhCode.SOURCE.value, "ec": code}, 200

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
