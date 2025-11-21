#!/usr/bin/env python

"""
Integration test for blob upload handler.
This script connects to Azure IoT Hub and uploads a test file to blob storage.

This is not a unit test; it requires actual Azure resources to run.
It provisions a device via DPS, connects to IoT Hub, and uploads a blob.

It is not meant to be run frequently, this is to ensure end-to-end functionality works.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloudApi.blob_upload_handler import upload_to_blob
from cloudApi.device_client import DeviceClientFactory
from cloudApi.dps_client import DPSClient
from config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run blob upload integration test."""
    device_client = None

    logger.info("=" * 60)
    logger.info("BLOB UPLOAD INTEGRATION TEST")
    logger.info("=" * 60)

    # Step 1: Provision device
    logger.info("Step 1: Provisioning device...")
    try:
        dps = DPSClient()
        registration_result = await dps.create_provisioning_device()
    except Exception as e:
        logger.error(f"Device provisioning failed: {e}", exc_info=True)
        return 1
    logger.info(f"Device provisioned to hub: {registration_result.registration_state.assigned_hub}")

    # Step 2: Create device client
    logger.info("Step 2: Creating device client...")
    try:
        factory = DeviceClientFactory(registration_result)
        device_client = factory.create_client()
    except Exception as e:
        logger.error(f"Device client creation failed: {e}", exc_info=True)
        return 1

    # Step 3: Connect to IoT Hub
    logger.info("Step 3: Connecting to IoT Hub...")
    try:
        await device_client.connect()
    except Exception as e:
        logger.error(f"IoT Hub connection failed: {e}", exc_info=True)
        return 1
    logger.info("Connected successfully!")

    # Step 4: Create test data
    logger.info("Step 4: Creating test data...")
    test_data = f"Blob upload test from GatewayApp\nTimestamp: {asyncio.get_event_loop().time()}\n".encode('utf-8')
    blob_name = f"test_upload_{Config.DEVICE_NAME}.txt"
    logger.info(f"Blob name: {blob_name}")
    logger.info(f"Data size: {len(test_data)} bytes")

    # Step 5: Upload to blob
    logger.info("Step 5: Uploading to blob storage...")
    try:
        await upload_to_blob(device_client, blob_name, test_data)
    except Exception as e:
        logger.error(f"Blob upload failed: {e}", exc_info=True)
        await device_client.disconnect()
        return 1

    logger.info("=" * 60)
    logger.info("TEST COMPLETED SUCCESSFULLY!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Check IoT Hub device messages in Azure Portal")
    logger.info("2. Check blob storage container for the uploaded file")
    logger.info(f"   - Blob name: {blob_name}")
    logger.info("")

    # Cleanup
    logger.info("Disconnecting...")
    await device_client.disconnect()
    logger.info("Disconnected.")

    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
