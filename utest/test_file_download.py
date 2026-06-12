"""Unit tests for cloudApi.file_download."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from cloudApi import file_download

GOOD_URI = "https://acct.blob.core.windows.net/c/leds.sh?sp=r&sig=abc"
BAD_HOST_URI = "https://evil.example.com/leds.sh"


class TestDownloadFile(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_type_rejected(self):
        fn, fp, code = await file_download.download_file(GOOD_URI, "0xFF", 1000)
        self.assertEqual((fn, fp, code), (None, None, "TYPE_ERR"))

    async def test_bad_host_rejected(self):
        fn, fp, code = await file_download.download_file(BAD_HOST_URI, "0x0B", 1000)
        self.assertEqual(code, "URL_ERR")

    async def test_non_https_scheme_rejected(self):
        """An allowlisted host over http:// (or file://) must be rejected."""
        uri = "http://acct.blob.core.windows.net/c/leds.sh?sig=abc"
        fn, fp, code = await file_download.download_file(uri, "0x0B", 1000)
        self.assertEqual((fn, fp, code), (None, None, "URL_ERR"))

    async def test_traversal_filename_rejected(self):
        uri = "https://acct.blob.core.windows.net/c/..%2f..%2fetc%2fpasswd"
        fn, fp, code = await file_download.download_file(uri, "0x0B", 1000)
        self.assertEqual(code, "FILE_NAME_ERR")

    @patch("cloudApi.file_download.BlobClient")
    async def test_size_cap_rejected(self, mock_blob_cls):
        props = MagicMock()
        props.size = 5000
        mock_blob_cls.from_blob_url.return_value.get_blob_properties.return_value = props
        fn, fp, code = await file_download.download_file(GOOD_URI, "0x0B", 1000)
        self.assertEqual(code, "SIZE_ERR")

    @patch("cloudApi.file_download.download_from_blob", new_callable=AsyncMock)
    @patch("cloudApi.file_download.os.path.exists", return_value=True)
    @patch("cloudApi.file_download.BlobClient")
    async def test_happy_path(self, mock_blob_cls, mock_exists, mock_dl):
        props = MagicMock()
        props.size = 100
        mock_blob_cls.from_blob_url.return_value.get_blob_properties.return_value = props
        fn, fp, code = await file_download.download_file(GOOD_URI, "0x0B", 1000)
        self.assertEqual(fn, "leds.sh")
        self.assertEqual(fp, os.path.join("/data/downloads", "script", "leds.sh"))
        self.assertEqual(code, "NO_ERR")
        mock_dl.assert_awaited_once_with(GOOD_URI, fp)
