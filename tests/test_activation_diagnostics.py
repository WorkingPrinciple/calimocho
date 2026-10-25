import os
from pathlib import Path
import sys
import unittest

from tools.diagnose_package_activation import ActivationTrace, collect


class ActivationDiagnosticsTests(unittest.TestCase):
    def test_child_and_xaml_require_matching_pid_and_load_event(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        trace.stdout("calimocho-activation resume_status 00000000")
        trace.stderr('0068:0070:trace:loaddll:build_module Loaded L"C:\\Windows.UI.Xaml.dll" at 1234: native')
        trace.stderr('0064:0070:trace:loaddll:build_module Loaded L"C:\\Windows.UI.Xaml.dll" at 1234: native')
        self.assertEqual(trace.verdict()["xaml"], "loaded-in-child")
        self.assertTrue(trace.verdict()["resumed"])
        self.assertEqual(len(trace.loads), 2)

    def test_exit_zero_alone_is_not_start_or_xaml_proof(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation exit_code 0")
        trace.stderr('0064:0070:trace:process:example Windows.UI.Xaml.dll token=SECRET')
        self.assertFalse(trace.verdict()["created"])
        self.assertEqual(trace.verdict()["xaml"], "not-observed")
        self.assertNotIn("SECRET", str(trace.verdict()))

    def test_raw_output_and_unknown_fields_are_not_retained(self):
        trace = ActivationTrace()
        trace.stdout("account SECRET")
        trace.stdout("calimocho-activation secret SECRET")
        trace.stderr("XGAMERUNTIME SECRET")
        trace.stderr("0064:0070:err:example:function SECRET")
        self.assertEqual(trace.metadata, {})
        self.assertEqual(trace.errors, 1)
        self.assertNotIn("SECRET", str(vars(trace)))

    def test_other_pid_load_is_not_child_load(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        trace.stderr('0068:0070:trace:loaddll:build_module Loaded L"C:\\Windows.UI.Xaml.dll" at 1234: native')
        self.assertEqual(trace.verdict()["xaml"], "not-observed")
        trace.truncated = True
        self.assertEqual(trace.verdict()["xaml"], "unknown-truncated")

    def test_duplicate_metadata_is_rejected(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        with self.assertRaises(ValueError):
            trace.stdout("calimocho-activation child_pid 101")

    def test_collector_drains_large_redacted_output_and_keeps_final_metadata(self):
        script = (
            "import sys, time\n"
            "sys.stderr.write('SECRET' * (1600000) + '\\n'); sys.stderr.flush()\n"
            "time.sleep(0.05)\n"
            "print('calimocho-activation child_pid 100')\n"
            "print('calimocho-activation resume_status 00000000')\n"
            "print('calimocho-activation exit_code 0')\n"
        )
        observed = collect([sys.executable, "-c", script], dict(os.environ), Path.cwd(), seconds=5)
        self.assertEqual(observed["helper_exit"], 0)
        self.assertTrue(observed["created"])
        self.assertTrue(observed["trace_truncated"])
        self.assertEqual(observed["metadata"]["exit_code"], "0")
        self.assertNotIn("SECRET", str(observed))

    def test_collector_timeout_is_not_success(self):
        observed = collect([sys.executable, "-c", "import time; time.sleep(5)"],
                           dict(os.environ), Path.cwd(), seconds=0.1)
        self.assertTrue(observed["collector_timeout"])
        self.assertNotEqual(observed["helper_exit"], 0)
        self.assertFalse(observed["created"])


if __name__ == "__main__":
    unittest.main()
