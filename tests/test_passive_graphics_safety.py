import copy
from pathlib import Path
import shutil
import subprocess
import unittest

from tools.passive_graphics_safety import validate_geometry, free_position, obstacles


SNAPSHOT = {
    "foreground_pid": 12, "observed_at": 100,
    "displays": [{"id": 1, "x": 0, "y": 0, "width": 1000, "height": 800}],
    "windows": [{"id": 2, "pid": 12, "layer": 0, "alpha": 1, "on_screen": True, "probe_title": "",
                 "bounds": {"X": 0, "Y": 0, "Width": 400, "Height": 600}}],
}


class PassiveGeometryTests(unittest.TestCase):
    def test_explicit_window_exception_does_not_ignore_other_dock_windows(self):
        data = copy.deepcopy(SNAPSHOT)
        data["windows"][0].update(pid=716, id=33, layer=20)
        data["windows"][0]["bounds"].update(Width=1000, Height=800)
        with self.assertRaises(ValueError):
            free_position(data)
        self.assertEqual(free_position(data, ignored_window=(716, 33)), (40, 50))
        for identity in ((716, 34), (717, 33), (True, 33)):
            with self.assertRaises(ValueError):
                free_position(data, ignored_window=identity)
        data["windows"].append(dict(data["windows"][0], id=34))
        with self.assertRaises(ValueError):
            free_position(data, ignored_window=(716, 33))
        data["windows"].pop()
        data["windows"][0]["layer"] = 19
        with self.assertRaises(ValueError):
            free_position(data, ignored_window=(716, 33))

    def test_paused_ode_excludes_only_exact_foreground_window(self):
        data = copy.deepcopy(SNAPSHOT)
        data["windows"][0]["bounds"].update(Width=1000, Height=800)
        with self.assertRaises(ValueError):
            free_position(data)
        self.assertEqual(free_position(data, (12, 2)), (40, 50))
        for identity in ((13, 2), (12, 3), (True, 2)):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                obstacles(data, identity)
        for pid in (12, 99):
            other = dict(data["windows"][0], id=3, pid=pid)
            data["windows"].append(other)
            with self.subTest(other_pid=pid), self.assertRaises(ValueError):
                free_position(data, (12, 2))
            data["windows"].pop()

    def test_valid_inventory(self):
        self.assertEqual(validate_geometry(SNAPSHOT, now=101), SNAPSHOT)

    def test_unknown_or_malformed_inventory_fails_closed(self):
        changes = [
            ("foreground_pid", None), ("foreground_pid", 0),
            ("observed_at", 0), ("observed_at", 102),
            ("windows", []), ("windows", None), ("displays", []),
            ("windows", [{}]), ("windows", [{"id": 1}]),
            ("windows", [dict(SNAPSHOT["windows"][0], bounds={})]),
            ("windows", [dict(SNAPSHOT["windows"][0], pid=0)]),
            ("windows", [dict(SNAPSHOT["windows"][0], layer=None)]),
            ("windows", [dict(SNAPSHOT["windows"][0], alpha=None)]),
            ("windows", [dict(SNAPSHOT["windows"][0], alpha=1.1)]),
            ("windows", [dict(SNAPSHOT["windows"][0], on_screen=None)]),
            ("windows", [dict(SNAPSHOT["windows"][0], on_screen=1)]),
            ("windows", [dict(SNAPSHOT["windows"][0], bounds={
                "X": 0, "Y": 0, "Width": float("nan"), "Height": 1})]),
            ("windows", SNAPSHOT["windows"] * 2),
        ]
        for key, value in changes:
            data = copy.deepcopy(SNAPSHOT)
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_geometry(data, now=101)

    @unittest.skipUnless(shutil.which("swift"), "Requires installed Swift")
    def test_native_helper_rejects_negative_fixtures_without_window_queries(self):
        source = Path(__file__).resolve().parents[1] / "tools/native_probe_geometry.swift"
        result = subprocess.run(
            [shutil.which("swift"), str(source), "--self-test"],
            check=True, capture_output=True, text=True, timeout=60)
        self.assertIn("PASS fail-closed", result.stdout)


if __name__ == "__main__":
    unittest.main()
