"""Azure Blob Storage download handler."""

import logging
import os

from azure.storage.blob import BlobClient

logger = logging.getLogger(__name__)


async def download_from_blob(blob_url: str, destination_path: str) -> None:
    """
    Download a blob from Azure Blob Storage to a local file.

    This is the Python equivalent of the old C++ DownloadFile() function.
    The cloud provides the full SAS URL via direct methods or desired properties.

    Uses atomic write (download to .tmp, then rename) and is idempotent
    (skips download if file already exists).

    Args:
        blob_url: Full blob URL with SAS token.
        destination_path: Local file path to write the downloaded data.
    """
    # Idempotent: skip if file already exists
    if os.path.exists(destination_path):
        logger.info(f"File already exists at {destination_path}, skipping download")
        return

    tmp_path = f"{destination_path}.tmp"

    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        # Download blob data
        blob_client = BlobClient.from_blob_url(blob_url)
        stream = blob_client.download_blob()
        data = stream.readall()

        # Atomic write: write to .tmp first, then rename
        with open(tmp_path, "wb") as f:
            f.write(data)

        os.replace(tmp_path, destination_path)
        logger.info(f"Downloaded {len(data)} bytes to {destination_path}")

    except Exception as e:
        logger.error(f"Blob download failed: {e}")

        # Clean up .tmp file on failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
