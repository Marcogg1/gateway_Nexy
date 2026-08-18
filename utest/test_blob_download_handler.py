#!/usr/bin/env python

"""Unit tests for blob download functionality."""

import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, mock_open, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.blob_download_handler import download_from_blob


def _mock_stream(*chunks: bytes) -> MagicMock:
    """Build a mock StorageStreamDownloader whose read() yields chunks then b''."""
    stream = MagicMock()
    stream.read.side_effect = list(chunks) + [b""]
    return stream


class TestBlobDownloadHandler(unittest.IsolatedAsyncioTestCase):
    """Test suite for blob download function."""

    def setUp(self):
        """Set up test fixtures."""
        self.blob_url = "https://test.blob.core.windows.net/container/blob?sv=2021&sig=test"
        self.destination_path = "/opt/smartlift/trace/downloaded_file.bin"

    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_from_blob_success(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace
    ):
        """Test successful blob download: BlobClient called, data written, .tmp renamed."""
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = _mock_stream(b"blob ", b"content")
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertTrue(result)
        mock_makedirs.assert_called_once_with(
            os.path.dirname(self.destination_path), exist_ok=True
        )
        mock_blob_client.from_blob_url.assert_called_once_with(
            self.blob_url, connection_timeout=30, read_timeout=60
        )
        mock_blob.download_blob.assert_called_once()
        mock_file.assert_called_once_with(f"{self.destination_path}.tmp", "wb")
        mock_file().write.assert_any_call(b"blob ")
        mock_file().write.assert_any_call(b"content")
        mock_replace.assert_called_once_with(
            f"{self.destination_path}.tmp", self.destination_path
        )

    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_overwrites_existing_file(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace
    ):
        """Test re-download: no exists-check short-circuit, blob fetched and renamed over target."""
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = _mock_stream(b"updated content")
        mock_blob_client.from_blob_url.return_value = mock_blob

        with patch(
            "cloudApi.blob_download_handler.os.path.exists", return_value=True
        ) as mock_exists:
            result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertTrue(result)
        mock_exists.assert_not_called()
        mock_blob_client.from_blob_url.assert_called_once_with(
            self.blob_url, connection_timeout=30, read_timeout=60
        )
        mock_replace.assert_called_once_with(
            f"{self.destination_path}.tmp", self.destination_path
        )

    @patch("cloudApi.blob_download_handler.os.remove")
    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_from_blob_exceeds_max_bytes(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace, mock_remove
    ):
        """Test size cap: transfer aborted mid-stream, .tmp cleaned up, False returned."""
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = _mock_stream(b"x" * 600, b"x" * 600)
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(
            self.blob_url, self.destination_path, max_bytes=1000
        )

        self.assertFalse(result)
        mock_replace.assert_not_called()
        mock_remove.assert_called_once_with(f"{self.destination_path}.tmp")

    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_from_blob_at_max_bytes_ok(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace
    ):
        """Test transfer exactly at the cap succeeds."""
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = _mock_stream(b"x" * 1000)
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(
            self.blob_url, self.destination_path, max_bytes=1000
        )

        self.assertTrue(result)
        mock_replace.assert_called_once()

    @patch("cloudApi.blob_download_handler.os.remove")
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_from_blob_failure(
        self, mock_makedirs, mock_blob_client, mock_remove
    ):
        """Test BlobClient raises: logged, .tmp cleaned up, returns False."""
        mock_blob_client.from_blob_url.side_effect = Exception("Connection error")

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertFalse(result)
        mock_remove.assert_called_once_with(f"{self.destination_path}.tmp")

    @patch("cloudApi.blob_download_handler.os.remove")
    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", side_effect=OSError("Disk full"))
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_download_from_blob_write_failure(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace, mock_remove
    ):
        """Test download OK but write fails: .tmp cleaned up, returns False."""
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = _mock_stream(b"blob content")
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertFalse(result)
        mock_replace.assert_not_called()
        mock_remove.assert_called_once_with(f"{self.destination_path}.tmp")

    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    async def test_transfer_runs_off_event_loop(
        self, mock_makedirs, mock_blob_client, mock_file, mock_replace
    ):
        """Test the blocking SDK read happens on a worker thread, not the loop."""
        loop_thread = threading.get_ident()
        seen: list[int] = []
        stream = MagicMock()

        def read(_size):
            seen.append(threading.get_ident())
            return b"data" if len(seen) == 1 else b""

        stream.read.side_effect = read
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = stream
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertTrue(result)
        self.assertTrue(seen)
        self.assertNotEqual(seen[0], loop_thread)


if __name__ == "__main__":
    unittest.main()
