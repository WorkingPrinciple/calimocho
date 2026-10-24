from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from port_d3dmetal import between, port, replace_once
sys.path.pop(0)


class PortTests(unittest.TestCase):
    def test_replacements_fail_loud_on_missing_or_ambiguous_source(self):
        self.assertEqual(replace_once("one anchor", "anchor", "change"), "one change")
        for content in ("missing", "anchor anchor"):
            with self.assertRaisesRegex(ValueError, "expected one"):
                replace_once(content, "anchor", "change")

    def test_donor_blocks_require_exact_start_and_end(self):
        self.assertEqual(between("before:start body:end", "start", "end"), "start body:")
        for content in ("start only", "start start end"):
            with self.assertRaises(ValueError):
                between(content, "start", "end")

    def test_failed_port_does_not_partially_write_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            donor = root / "donor"
            driver = donor / "dlls/winemac.drv"
            driver.mkdir(parents=True)
            source.mkdir()
            retained = source / "retain"
            retained.write_text("original")
            for name in ("d3dmetal.c", "d3dmetal_objc.m", "d3dmetal_objc.h"):
                (driver / name).write_text("incompatible donor")
            with self.assertRaisesRegex(ValueError, "expected one"):
                port(source, donor)
            self.assertEqual(retained.read_text(), "original")
            self.assertEqual(list(source.iterdir()), [retained])


if __name__ == "__main__":
    unittest.main()
