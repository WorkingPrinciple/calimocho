"""Admission evidence rejects false fixture/cleanup claims without running Wine."""
import copy
import json
import unittest

from tools.freeze_gameinput_runtime import ROOT, validate_observation, verify_inputs


class GameInputFreezeTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / "headless-02/receipt.json").read_text())

    def test_actual_pinned_observations(self):
        verify_inputs()
        validate_observation(self.record, "candidate")

    def test_rejects_failed_checks_or_nonzero_candidate_exit(self):
        for key, value in (("exit_code", 1), ("failed_lines", [12]),
                           ("facts", ["no-device callbacks=1 failures=0"]),
                           ("case", "baseline")):
            record = copy.deepcopy(self.record)
            record["observations"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observation(record, "candidate")

    def test_rejects_incomplete_cleanup(self):
        for key, value in (("stop", 2), ("wait", 1), ("prefix_open_files", 0),
                           ("prefix_open_files_empty", False)):
            record = copy.deepcopy(self.record)
            record["observations"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observation(record, "candidate")

    def test_rejects_missing_scope_and_budget_invariants(self):
        for key, value in (("windowless", False), ("base_inventory_unchanged", False),
                           ("elapsed_seconds", 121), ("elapsed_seconds", 0),
                           ("observations", [])):
            record = copy.deepcopy(self.record)
            record[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observation(record, "candidate")
