#!/usr/bin/env python

"""Unit tests for blob download functionality."""

import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.blob_download_handler import download_from_blob


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
    @patch("cloudApi.blob_download_handler.os.path.exists", return_value=False)
    async def test_download_from_blob_success(
        self, mock_exists, mock_makedirs, mock_blob_client, mock_file, mock_replace
    ):
        """Test successful blob download: BlobClient called, data written, .tmp renamed."""
        mock_stream = MagicMock()
        mock_stream.readall.return_value = b"blob content"
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = mock_stream
        mock_blob_client.from_blob_url.return_value = mock_blob

        await download_from_blob(self.blob_url, self.destination_path)

        mock_exists.assert_called_once_with(self.destination_path)
        mock_makedirs.assert_called_once_with(
            os.path.dirname(self.destination_path), exist_ok=True
        )
        mock_blob_client.from_blob_url.assert_called_once_with(self.blob_url)
        mock_blob.download_blob.assert_called_once()
        mock_stream.readall.assert_called_once()
        mock_file.assert_called_once_with(f"{self.destination_path}.tmp", "wb")
        mock_file().write.assert_called_once_with(b"blob content")
        mock_replace.assert_called_once_with(
            f"{self.destination_path}.tmp", self.destination_path
        )

    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.path.exists", return_value=True)
    async def test_download_from_blob_file_exists(self, mock_exists, mock_blob_client):
        """Test file exists: BlobClient never called, early return."""
        await download_from_blob(self.blob_url, self.destination_path)

        mock_exists.assert_called_once_with(self.destination_path)
        mock_blob_client.from_blob_url.assert_not_called()

    @patch("cloudApi.blob_download_handler.os.remove")
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    @patch("cloudApi.blob_download_handler.os.path.exists", return_value=False)
    async def test_download_from_blob_failure(
        self, mock_exists, mock_makedirs, mock_blob_client, mock_remove
    ):
        """Test BlobClient raises: logged, .tmp cleaned up, returns None."""
        mock_blob_client.from_blob_url.side_effect = Exception("Connection error")

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertIsNone(result)
        mock_remove.assert_called_once_with(f"{self.destination_path}.tmp")

    @patch("cloudApi.blob_download_handler.os.remove")
    @patch("cloudApi.blob_download_handler.os.replace")
    @patch("builtins.open", side_effect=OSError("Disk full"))
    @patch("cloudApi.blob_download_handler.BlobClient")
    @patch("cloudApi.blob_download_handler.os.makedirs")
    @patch("cloudApi.blob_download_handler.os.path.exists", return_value=False)
    async def test_download_from_blob_write_failure(
        self, mock_exists, mock_makedirs, mock_blob_client, mock_file, mock_replace, mock_remove
    ):
        """Test download OK but write fails: .tmp cleaned up."""
        mock_stream = MagicMock()
        mock_stream.readall.return_value = b"blob content"
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = mock_stream
        mock_blob_client.from_blob_url.return_value = mock_blob

        result = await download_from_blob(self.blob_url, self.destination_path)

        self.assertIsNone(result)
        mock_replace.assert_not_called()
        mock_remove.assert_called_once_with(f"{self.destination_path}.tmp")


if __name__ == "__main__":
    unittest.main()
