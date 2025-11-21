"""Azure Blob Storage upload handler."""

import logging

from azure.iot.device.aio import IoTHubDeviceClient
from azure.storage.blob import BlobClient

logger = logging.getLogger(__name__)


async def upload_to_blob(
    device_client: IoTHubDeviceClient,
    blob_name: str,
    data: bytes
) -> None:
    """
    Upload data to Azure Blob Storage via IoT Hub.

    This is the Python equivalent of the old C++ UploadToBlob() function.
    It expects data already loaded into memory as bytes.

    Args:
        device_client: Connected IoT Hub device client.
        blob_name: Name for the blob in Azure Storage.
        data: File content as bytes.
    """
    # Try to upload the blob
    try:
        # Get storage info from IoT Hub
        storage_info = await device_client.get_storage_info_for_blob(blob_name)

        # Build blob URL with SAS token
        blob_url = (
            f"https://{storage_info['hostName']}/"
            f"{storage_info['containerName']}/"
            f"{storage_info['blobName']}"
            f"{storage_info['sasToken']}"
        )

        # Upload to blob storage
        blob_client = BlobClient.from_blob_url(blob_url)
        blob_client.upload_blob(data, overwrite=True)

        logger.info(f"Uploaded {len(data)} bytes to {blob_name}")

    except Exception as e:
        logger.error(f"Blob upload failed: {e}")

        # Try to notify IoT Hub of failure
        try:
            await device_client.notify_blob_upload_status(
                storage_info['correlationId'],
                False,
                500,
                str(e)
            )
        except Exception:
            pass
        return  # Exit early on upload failure

    # Upload succeeded - notify IoT Hub of success
    try:
        await device_client.notify_blob_upload_status(
            storage_info['correlationId'],
            True,
            200,
            "OK"
        )
    except Exception as e:
        # Upload succeeded but notification failed - log warning
        logger.warning(f"Blob uploaded successfully but notification failed: {e}")
