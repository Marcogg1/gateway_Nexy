"""Secure file download for the ca.download-file direct method.

Validates the request (type → directory, host allowlist, filename
sanitisation, size cap) before delegating the actual transfer to
download_from_blob(). Returns legacy-style (value, ..., error_code)
so the DDM handler can build its response envelope.
"""

import asyncio
import os
from fnmatch import fnmatch
from urllib.parse import urlparse, unquote

from azure.storage.blob import BlobClient

from config import Config
from lib.error_signals import MrhCode
from lib.logging_config import get_logger
from cloudApi.blob_download_handler import download_from_blob

logger = get_logger(__name__)


def _host_allowed(host: str) -> bool:
    """True if host matches any pattern in the configured allowlist."""
    return any(fnmatch(host, pat) for pat in Config.DOWNLOAD_HOST_ALLOWLIST)


def _safe_filename(uri: str) -> str | None:
    """Extract a safe basename from the URI path, or None if unsafe.

    Strips the query string (SAS token) and rejects path separators and
    traversal components, including percent-encoded slashes (%2f, %5c).
    """
    raw_path = urlparse(uri).path
    # Reject percent-encoded path separators before unquoting.
    if "%2f" in raw_path.lower() or "%5c" in raw_path.lower():
        return None
    name = os.path.basename(unquote(raw_path))
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return None
    return name


async def download_file(
    uri: str, type_code: str, max_bytes: int
) -> tuple[str | None, str | None, str]:
    """Validate and download a file for ca.download-file.

    Args:
        uri: Full blob URL (may include a SAS query string).
        type_code: Hex type code selecting the target subdirectory.
        max_bytes: Maximum allowed download size.

    Returns:
        Tuple of (filename, fullpath, error_code_name). filename/fullpath
        are None on any error; error_code is an MrhCode member name.
    """
    subdir = Config.DOWNLOAD_TYPE_DIRS.get(type_code)
    if subdir is None:
        logger.warning("Unknown download type: %s", type_code)
        return None, None, MrhCode.TYPE_ERR.name

    host = urlparse(uri).hostname or ""
    if not _host_allowed(host):
        logger.warning("Download host not allowed: %s", host)
        return None, None, MrhCode.URL_ERR.name

    filename = _safe_filename(uri)
    if filename is None:
        logger.warning("Unsafe download filename from uri")
        return None, None, MrhCode.FILE_NAME_ERR.name

    target_dir = os.path.join(Config.DOWNLOAD_ROOT, subdir)
    fullpath = os.path.join(target_dir, filename)
    # Containment: resolved path must stay under the target directory.
    if not os.path.realpath(fullpath).startswith(os.path.realpath(target_dir) + os.sep):
        logger.warning("Download path escapes target directory")
        return None, None, MrhCode.FILE_NAME_ERR.name

    try:
        props = await asyncio.to_thread(
            lambda: BlobClient.from_blob_url(uri).get_blob_properties()
        )
        if props.size is not None and props.size > max_bytes:
            logger.warning("Download exceeds cap: %s > %s", props.size, max_bytes)
            return None, None, MrhCode.SIZE_ERR.name
    except Exception as e:
        logger.error("Failed to read blob properties: %s", e)
        return None, None, MrhCode.DOWNLOAD_ERR.name

    # download_from_blob swallows its own exceptions, so confirm via existence.
    await download_from_blob(uri, fullpath)
    if not os.path.exists(fullpath):
        logger.error("Download did not produce a file at %s", fullpath)
        return None, None, MrhCode.DOWNLOAD_ERR.name

    return filename, fullpath, MrhCode.NO_ERR.name
