"""Azure Blob Storage download handler."""

import asyncio
import logging
import os
import re
from urllib.parse import urlparse, urlunparse

from azure.storage.blob import BlobClient

logger = logging.getLogger(__name__)

# Mask the SAS signature wherever it appears in free text (e.g. SDK
# exception messages that embed the full request URL).
_SAS_SIG_RE = re.compile(r"(sig=)[^&\s]+", re.IGNORECASE)

# Socket-level timeouts for the sync SDK — without a read timeout a stalled
# connection would pin the worker thread indefinitely.
_CONNECT_TIMEOUT_S = 30
_READ_TIMEOUT_S = 60


def _transfer_to_file(blob_url: str, tmp_path: str, max_bytes: int | None) -> int:
    """Blocking chunked download to tmp_path; runs in a worker thread.

    Streams in chunks so the size cap bounds actual received bytes (the
    blob's reported size can't be trusted) and the whole file is never
    buffered in memory.

    Args:
        blob_url: Full blob URL with SAS token.
        tmp_path: Temporary file path to write into.
        max_bytes: Abort once more than this many bytes received. None
            means no limit.

    Returns:
        Total bytes written.

    Raises:
        ValueError: If the transfer exceeds max_bytes.
    """
    blob_client = BlobClient.from_blob_url(
        blob_url,
        connection_timeout=_CONNECT_TIMEOUT_S,
        read_timeout=_READ_TIMEOUT_S,
    )
    stream = blob_client.download_blob()
    total = 0
    with open(tmp_path, "wb") as f:
        while chunk := stream.read(65536):
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValueError(
                    f"transfer exceeded size cap ({total} > {max_bytes} bytes)"
                )
            f.write(chunk)
    return total


def _redact_sas(text: str) -> str:
    """Strip the query string from a blob URL and mask any sig= token."""
    try:
        text = urlunparse(urlparse(text)._replace(query=""))
    except ValueError:
        pass
    return _SAS_SIG_RE.sub(r"\1***", text)


async def download_from_blob(
    blob_url: str, destination_path: str, max_bytes: int | None = None
) -> bool:
    """
    Download a blob from Azure Blob Storage to a local file.

    This is the Python equivalent of the old C++ DownloadFile() function.
    The cloud provides the full SAS URL via direct methods or desired properties.

    Uses atomic write (download to .tmp, then rename), so an existing file
    is replaced only after the new content has been fully downloaded; a
    failed download leaves any existing file untouched. Unlike the legacy
    C++ code this overwrites an existing file, so repeated downloads pick
    up updated content.

    Args:
        blob_url: Full blob URL with SAS token.
        destination_path: Local file path to write the downloaded data.
        max_bytes: Abort the transfer once more than this many bytes have
            been received. None means no limit.

    Returns:
        True if the file was downloaded and moved into place, False on
        any failure (already logged).
    """
    tmp_path = f"{destination_path}.tmp"

    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        # Sync Azure SDK — run in a worker thread so a large or stalled
        # transfer can't block heartbeats and direct methods on the loop.
        total = await asyncio.to_thread(
            _transfer_to_file, blob_url, tmp_path, max_bytes
        )

        # Atomic write: rename .tmp over the destination
        os.replace(tmp_path, destination_path)
        logger.info(f"Downloaded {total} bytes to {destination_path}")
        return True

    except Exception as e:
        # Azure SDK errors often embed the full request URL incl. the SAS
        # signature; scrub before logging so credentials don't reach logs.
        logger.error("Blob download failed for %s: %s",
                     _redact_sas(blob_url), _redact_sas(str(e)))

        # Clean up .tmp file on failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False
