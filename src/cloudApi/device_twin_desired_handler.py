from typing import Any
import asyncio
import logging

logger = logging.getLogger(__name__)


class DeviceTwinDesiredHandler:
    def __init__(self, device_client) -> None:
        logger.info("Initializing DeviceTwinDesiredHandler")
        self.device_client = device_client

        # placeholder for desired properties populated by async factory
        self.desired_properties: Any = {}

    @classmethod
    async def create(cls, device_client):
        """
        Async factory to create and initialize the handler, since __init__ cannot be async.
        Usage:
            handler = await DeviceTwinDesiredHandler.create(device_client)
        """
        self = cls(device_client)
        all_device_twin_properties = await device_client.get_twin()
        desired_properties = all_device_twin_properties.get("desired", {})
     
        logger.info(f"All desired properties: {desired_properties}")

        self.desired_properties = desired_properties
        return self

    async def listen_for_desired_updates(self) -> None:
        logger.info("Listening for desired property updates...")
        while True:
            desired_properties_patch = await self.device_client.receive_twin_desired_properties_patch()
            logger.info(f"Received desired properties patch: {desired_properties_patch}")
            # Handle desired properties if needed in separate class/methods