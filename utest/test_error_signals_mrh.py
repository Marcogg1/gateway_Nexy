"""Unit tests for the MrhCode error enum."""

import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from lib.error_signals import MrhCode


class TestMrhCode(unittest.TestCase):
    def test_source_is_method_request_handler(self):
        self.assertEqual(MrhCode.SOURCE.value, "MethodRequestHandler")

    def test_has_expected_members(self):
        expected = [
            "SOURCE", "NO_ERR", "ARG_ERR", "TYPE_ERR",
            "URL_ERR", "FILE_NAME_ERR", "SIZE_ERR", "DOWNLOAD_ERR",
        ]
        self.assertEqual([m.name for m in MrhCode], expected)
