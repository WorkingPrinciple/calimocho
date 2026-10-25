import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "instrument_fh6", Path(__file__).parents[1] / "tools/instrument_fh6.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstrumentationTests(unittest.TestCase):
    def test_only_inserts_diagnostic_before_original_dispatch(self):
        source = "before\n" + module.ANCHOR + "\nafter"
        result = module.instrument(source)
        self.assertEqual(result.replace(module.DIAGNOSTIC, module.ANCHOR), source)
        self.assertIn("virtual_uninterrupted_read_memory", result)
        self.assertIn("TRAP_x86_PRIVINFLT && TRACE_ON(seh)", result)
        self.assertIn("bytes[16]", result)
        self.assertNotIn("context.c.Rip =", result)

    def test_rejects_missing_duplicate_and_repeated_instrumentation(self):
        for source in ("unrelated", module.ANCHOR * 2, module.DIAGNOSTIC):
            with self.subTest(source=source[:30]), self.assertRaises(ValueError):
                module.instrument(source)


if __name__ == "__main__":
    unittest.main()
