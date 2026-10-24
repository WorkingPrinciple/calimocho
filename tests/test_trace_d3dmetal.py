from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from trace_d3dmetal import trace_callbacks, trace_thread_start
sys.path.pop(0)


class TraceTests(unittest.TestCase):
    def test_callback_return_expression_is_evaluated_once(self):
        source = (
            'static BOOL my_callback(void)\n{\n'
            '    TRACE("original\\n");\n'
            '    if (failed) return FALSE;\n'
            '    return called_once();\n}\n'
        )
        traced = trace_callbacks(source, expected=1)
        self.assertIn("boundary enter my_callback", traced)
        self.assertEqual(traced.count("boundary leave my_callback result="), 2)
        self.assertIn("__typeof__(called_once()) boundary_result = (called_once());", traced)
        self.assertIn("return boundary_result;", traced)
        with self.assertRaises(ValueError):
            trace_callbacks(traced, expected=1)

    def test_void_early_and_expression_returns_have_exit_traces(self):
        source = (
            'static void my_callback(void)\n{\n'
            '    TRACE("original\\n");\n'
            '    if (failed) return;\n'
            '    return do_work();\n}\n'
        )
        traced = trace_callbacks(source, expected=1)
        self.assertIn('do_work(); TRACE("boundary leave my_callback void', traced)
        self.assertEqual(traced.count("boundary leave my_callback void"), 3)
        self.assertNotIn("boundary_result", traced)

    def test_incompatible_source_fails_loudly(self):
        for source in ("missing", 'static BOOL my_callback(void)\n{\n    return TRUE;\n}\n'):
            with self.assertRaises(ValueError):
                trace_callbacks(source)
        with self.assertRaises(ValueError):
            trace_thread_start("missing")


if __name__ == "__main__":
    unittest.main()
