import logging

logger = logging.getLogger(__name__)


class DeviceTwinReporter:

    def __init__(self, device_client) -> None:
        self.device_client = device_client

    async def report_property(self, property_name: str, property_value) -> None:
        
        """
        Reports a property to IoT Hub. Supports dot notation as nested dictionary.
        Example: key="la.arNumber", value="AR998877" → {"la": {"arNumber": "AR998877"}}
        """
        try:
            #Convert dot notation to nested dict
            keys = property_name.split('.')
            reported_properties = property_value
            for k in reversed(keys):
                reported_properties = {k: reported_properties}
            await self.device_client.patch_twin_reported_properties(reported_properties)
        except Exception as e:
            logger.error(f"Error reporting property with dot notation: {e}. Falling back to flat property.", exc_info=True)
