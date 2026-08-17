#!/usr/bin/env python

"""
Integration test for blob upload and download handlers.
This script connects to Azure IoT Hub, uploads a test file to blob storage,
then downloads it back and verifies the content matches.

This is not a unit test; it requires actual Azure resources to run.
It provisions a device via DPS, connects to IoT Hub, and uploads/downloads a blob.

It is not meant to be run frequently, this is to ensure end-to-end functionality works.
"""

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloudApi.blob_download_handler import download_from_blob
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
    """Run blob upload and download integration test."""
    device_client = None

    logger.info("=" * 60)
    logger.info("BLOB UPLOAD + DOWNLOAD INTEGRATION TEST")
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

    # Step 6: Build download URL from storage info
    logger.info("Step 6: Getting storage info for download URL...")
    try:
        storage_info = await device_client.get_storage_info_for_blob(blob_name)
        download_url = (
            f"https://{storage_info['hostName']}/"
            f"{storage_info['containerName']}/"
            f"{storage_info['blobName']}"
            f"{storage_info['sasToken']}"
        )
    except Exception as e:
        logger.error(f"Failed to get storage info for download: {e}", exc_info=True)
        await device_client.disconnect()
        return 1
    logger.info(f"Download URL built successfully")

    # Step 7: Download blob to temp file
    logger.info("Step 7: Downloading blob...")
    temp_download_path = os.path.join(tempfile.gettempdir(), f"download_{blob_name}")
    # Start from a clean path so the verify step below checks this download
    if os.path.exists(temp_download_path):
        os.remove(temp_download_path)
    try:
        await download_from_blob(download_url, temp_download_path)
    except Exception as e:
        logger.error(f"Blob download failed: {e}", exc_info=True)
        await device_client.disconnect()
        return 1

    # Step 8: Verify downloaded content matches uploaded data
    logger.info("Step 8: Verifying downloaded content...")
    try:
        with open(temp_download_path, "rb") as f:
            downloaded_data = f.read()
        assert downloaded_data == test_data, (
            f"Content mismatch! Uploaded {len(test_data)} bytes, "
            f"downloaded {len(downloaded_data)} bytes"
        )
        logger.info(f"Content verified: {len(downloaded_data)} bytes match")
    except FileNotFoundError:
        logger.error(f"Downloaded file not found at {temp_download_path}")
        await device_client.disconnect()
        return 1

    # Step 9: Clean up downloaded file
    logger.info("Step 9: Cleaning up temp file...")
    try:
        os.remove(temp_download_path)
        logger.info("Temp file removed")
    except OSError:
        pass

    logger.info("=" * 60)
    logger.info("TEST COMPLETED SUCCESSFULLY!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Verified: upload + download round-trip content matches")
    logger.info("")

    # Cleanup
    logger.info("Disconnecting...")
    await device_client.disconnect()
    logger.info("Disconnected.")

    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
