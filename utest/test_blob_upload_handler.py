#!/usr/bin/env python

"""Unit tests for blob upload functionality."""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi.blob_upload_handler import upload_to_blob


class TestBlobUpload(unittest.TestCase):
    """Test suite for blob upload function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_client.get_storage_info_for_blob = AsyncMock()
        self.mock_client.notify_blob_upload_status = AsyncMock()

        self.storage_info = {
            'correlationId': 'test-123',
            'hostName': 'test.blob.core.windows.net',
            'containerName': 'test-container',
            'blobName': 'test.txt',
            'sasToken': '?sv=2021&sig=test'
        }

    @patch('cloudApi.blob_upload_handler.BlobClient')
    async def test_upload_success(self, mock_blob_client_class):
        """Test successful blob upload."""
        self.mock_client.get_storage_info_for_blob.return_value = self.storage_info
        mock_blob = MagicMock()
        mock_blob_client_class.from_blob_url.return_value = mock_blob

        # Should complete without raising exception
        await upload_to_blob(self.mock_client, 'test.txt', b'test data')

        # Verify upload was called
        mock_blob.upload_blob.assert_called_once_with(b'test data', overwrite=True)

        # Verify success notification
        self.mock_client.notify_blob_upload_status.assert_called_once_with(
            'test-123', True, 200, 'OK'
        )

    async def test_upload_storage_info_failure(self):
        """Test handles storage info failure gracefully."""
        self.mock_client.get_storage_info_for_blob.side_effect = Exception('IoT Hub error')

        # Should complete without raising exception (errors logged only)
        await upload_to_blob(self.mock_client, 'test.txt', b'data')

        # Verify no notification (since we don't have correlation_id)
        self.mock_client.notify_blob_upload_status.assert_not_called()

    @patch('cloudApi.blob_upload_handler.BlobClient')
    async def test_upload_blob_failure(self, mock_blob_client_class):
        """Test handles blob storage failure gracefully."""
        self.mock_client.get_storage_info_for_blob.return_value = self.storage_info
        mock_blob = MagicMock()
        mock_blob.upload_blob.side_effect = Exception('Storage error')
        mock_blob_client_class.from_blob_url.return_value = mock_blob

        # Should complete without raising exception (errors logged only)
        await upload_to_blob(self.mock_client, 'test.txt', b'data')

        # Verify failure notification was sent
        self.mock_client.notify_blob_upload_status.assert_called_once()
        args = self.mock_client.notify_blob_upload_status.call_args[0]
        self.assertEqual(args[0], 'test-123')  # correlation_id
        self.assertEqual(args[1], False)       # success = False
        self.assertEqual(args[2], 500)         # status code


def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply decorator to async tests
for name in dir(TestBlobUpload):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestBlobUpload, name)):
        setattr(TestBlobUpload, name, async_test(getattr(TestBlobUpload, name)))


if __name__ == '__main__':
    unittest.main()
