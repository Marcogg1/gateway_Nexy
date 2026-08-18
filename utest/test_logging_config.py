"""Unit tests for logging_config handler path rewriting and fallback."""

import os
import sys
import unittest
from unittest.mock import patch

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from lib import logging_config


class TestSetupLoggingPaths(unittest.TestCase):
    def setUp(self):
        self.captured = {}

        def capture(config):
            self.captured.update(config)

        self.patcher = patch.object(
            logging_config.logging.config, "dictConfig", side_effect=capture
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_file_handler_paths_rewritten_absolute(self):
        logging_config.setup_logging()
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(logging_config.__file__)), "logs"
        )
        file_handlers = 0
        for name, handler in self.captured["handlers"].items():
            if "filename" in handler:
                file_handlers += 1
                self.assertTrue(
                    os.path.isabs(handler["filename"]),
                    f"handler {name} filename not absolute",
                )
                self.assertEqual(os.path.dirname(handler["filename"]), log_dir)
        self.assertGreater(file_handlers, 0)

    def test_log_dir_created(self):
        logging_config.setup_logging()
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(logging_config.__file__)), "logs"
        )
        self.assertTrue(os.path.isdir(log_dir))


class TestSetupLoggingFallback(unittest.TestCase):
    def test_dictconfig_failure_logs_loudly(self):
        with patch.object(
            logging_config.logging.config,
            "dictConfig",
            side_effect=ValueError("boom"),
        ):
            with self.assertLogs(logging_config.__name__, level="ERROR") as cm:
                logging_config.setup_logging()
        self.assertTrue(
            any("File logging is DISABLED" in line for line in cm.output)
        )


class TestNoImportTimeSetup(unittest.TestCase):
    def test_no_module_level_setup_logging_calls(self):
        offenders = []
        for rel in (
            "lib/thousand_lib.py",
            "lib/ahl_lib.py",
            "liftApi/rs232_handler.py",
            "liftApi/modbus_handler.py",
        ):
            path = os.path.join(p, rel)
            with open(path, encoding="utf-8") as f:
                src = f.read()
            # Module-level calls only — a call inside main() would be indented.
            if "\nsetup_logging()" in src:
                offenders.append(rel)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
