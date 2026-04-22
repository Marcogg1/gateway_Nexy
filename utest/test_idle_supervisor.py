"""Unit tests for IdleSupervisor."""

import os
import sys
import unittest

p = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, "src"))
sys.path.append(p)

from liftApi.idle_supervisor import IdleSupervisor, ParamChange


class TestParamChange(unittest.TestCase):
    """Tests for the ParamChange dataclass."""

    def test_has_param_id_and_new_value(self):
        c = ParamChange(param_id=22, new_value=1234)
        self.assertEqual(c.param_id, 22)
        self.assertEqual(c.new_value, 1234)

    def test_is_frozen(self):
        c = ParamChange(param_id=22, new_value=1234)
        with self.assertRaises(Exception):
            c.param_id = 99  # type: ignore[misc]


class TestIdleSupervisor(unittest.TestCase):
    """Tests for IdleSupervisor.on_param_changes."""

    def setUp(self):
        self.supervisor = IdleSupervisor()

    def test_logs_single_change_at_info(self):
        with self.assertLogs("liftApi.idle_supervisor", level="INFO") as cm:
            self.supervisor.on_param_changes([ParamChange(22, 1234)])
        self.assertEqual(len(cm.records), 1)
        self.assertIn("22", cm.output[0])
        self.assertIn("1234", cm.output[0])

    def test_logs_multiple_changes_in_order(self):
        changes = [
            ParamChange(22, 100),
            ParamChange(23, 200),
            ParamChange(24, 300),
        ]
        with self.assertLogs("liftApi.idle_supervisor", level="INFO") as cm:
            self.supervisor.on_param_changes(changes)
        self.assertEqual(len(cm.records), 3)
        self.assertIn("22", cm.output[0])
        self.assertIn("23", cm.output[1])
        self.assertIn("24", cm.output[2])

    def test_empty_list_emits_no_logs(self):
        with self.assertNoLogs("liftApi.idle_supervisor", level="INFO"):
            self.supervisor.on_param_changes([])

    def test_logs_none_value(self):
        with self.assertLogs("liftApi.idle_supervisor", level="INFO") as cm:
            self.supervisor.on_param_changes([ParamChange(22, None)])
        self.assertEqual(len(cm.records), 1)
        self.assertIn("None", cm.output[0])

    def test_log_level_is_info_not_warning(self):
        import logging
        with self.assertLogs("liftApi.idle_supervisor", level="DEBUG") as cm:
            self.supervisor.on_param_changes([ParamChange(22, 1234)])
        self.assertEqual(cm.records[0].levelno, logging.INFO)
