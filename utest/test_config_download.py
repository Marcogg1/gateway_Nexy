"""Unit tests for download-related Config constants."""

import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from config import Config


class TestDownloadConfig(unittest.TestCase):
    def test_download_root(self):
        self.assertEqual(Config.DOWNLOAD_ROOT, "/data/downloads")

    def test_type_dirs_mapping(self):
        self.assertEqual(Config.DOWNLOAD_TYPE_DIRS["0x07"], "up")
        self.assertEqual(Config.DOWNLOAD_TYPE_DIRS["0x08"], "liftAgent")
        self.assertEqual(Config.DOWNLOAD_TYPE_DIRS["0x0B"], "script")

    def test_host_allowlist_is_list(self):
        self.assertIsInstance(Config.DOWNLOAD_HOST_ALLOWLIST, list)
        self.assertTrue(Config.DOWNLOAD_HOST_ALLOWLIST)

    def test_max_bytes_default_positive(self):
        self.assertGreater(Config.DOWNLOAD_MAX_BYTES_DEFAULT, 0)
