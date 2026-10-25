import os
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.diagnose_package_activation import ActivationTrace, collect


class ActivationDiagnosticsTests(unittest.TestCase):
    def test_missing_launcher_interface_and_method_are_bounded_and_ce_pid_only(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        iid = "{277151c3-9e3e-42f6-91a4-5dfdeb232451}"
        trace.stderr("0064:0070:trace:pkglaunch:factory_query missing-iid=" + iid + " result=80004002")
        trace.stderr("0064:0070:trace:pkglaunch:launch_uri_options "
                     "unsupported method=LaunchUriWithOptionsAsync result=80004001")
        trace.stderr("0068:0070:trace:pkglaunch:factory_query missing-iid=" + iid + " result=80004002")
        trace.stderr("0064:0070:trace:pkglaunch:factory_query missing-iid=SECRET result=80004002")
        trace.stderr("0064:0070:trace:pkglaunch:launch_uri_options "
                     "unsupported method=SECRET result=80004001")
        results = trace.verdict()["activation_results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["missing_iid"], iid)
        self.assertEqual(results[1]["missing_method"], "LaunchUriWithOptionsAsync")
        self.assertNotIn("SECRET", str(trace.verdict()))

    def test_protocol_route_is_exact_pid_bound_and_no_full_uri_is_retained(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        route = ('0064:0070:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                 'app=L"Microsoft.Xbox.AppL" pid=200 result=00000000 missing=none')
        trace.stderr(route)
        trace.stderr(route.replace("0064:", "0068:").replace("pid=200", "pid=300"))
        trace.stderr('00c8:00cc:trace:loaddll:build_module Loaded L"C:\\Microsoft.UI.Xaml.dll" at 1234: native')
        trace.stderr(route.replace('scheme=L"msxboxl"', 'scheme=L"msxboxl://SECRET"'))
        verdict = trace.verdict()
        self.assertEqual(len(verdict["protocol_results"]), 1)
        self.assertEqual(verdict["protocol_results"][0]["child_pid"], 200)
        self.assertEqual(verdict["protocol_target_loads"][0]["module"], "microsoft.ui.xaml.dll")
        self.assertEqual(verdict["protocol_target_state"], "unknown")
        self.assertNotIn("SECRET", str(verdict))
        self.assertEqual(verdict["xaml"], "not-observed")

    def test_both_exact_xaml_modules_are_retained_with_pid(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 100")
        trace.stderr('0064:0070:trace:loaddll:build_module Loaded L"C:\\Microsoft.UI.Xaml.dll" at 1234: native')
        self.assertEqual(trace.verdict()["xaml"], "loaded-in-child")
        self.assertEqual(trace.verdict()["module_loads"][0]["pid"], 100)

    def test_recorded_protocol_child_prevents_direct_ce_exit_cutoff(self):
        script = (
            "import subprocess,sys\n"
            "print('calimocho-activation child_pid 100')\n"
            "print('calimocho-activation exit_observed_utc 2026-10-25T00:00:00Z')\n"
            "print('calimocho-activation elapsed_ms 91',flush=True)\n"
            "print('0064:0070:trace:pkglaunch:activate_route route scheme=L\"msxboxl\" "
            "app=L\"Microsoft.Xbox.AppL\" pid=200 result=00000000 missing=none',file=sys.stderr,flush=True)\n"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(0.35)'])\n"
        )
        result = collect([sys.executable, "-c", script], dict(os.environ), Path.cwd(),
                         seconds=2, post_exit_seconds=0.05)
        self.assertFalse(result["post_exit_drain_limited"])
        self.assertFalse(result["collector_timeout"])
        self.assertEqual(result["capture_end"], "stream-eof")
        self.assertEqual(result["protocol_target_state"], "unknown")

    def test_completed_factory_result_is_exact_and_ce_pid_only(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        record = ('00f0:00f4:trace:pkgactivate:trace_package_activation '
                  'operation=RoGetActivationFactory class=L"Microsoft.Windows.AppLifecycle.AppInstance" '
                  'iid={00000035-0000-0000-c000-000000000046} hr=80040154 '
                  'registration=0 server=absent')
        trace.stderr(record)
        trace.stderr(record.replace("00f0:", "00fc:"))
        results = trace.verdict()["activation_results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["runtime_class"], "Microsoft.Windows.AppLifecycle.AppInstance")
        self.assertEqual(results[0]["hresult"], "0x80040154")
        self.assertFalse(results[0]["registration_present"])
        trace.stderr(record.replace("Microsoft.Windows.AppLifecycle.AppInstance", "SECRET/path"))
        self.assertNotIn("SECRET", str(trace.verdict()))
        self.assertEqual(trace.verdict()["activation_results"][-1]["message_class"],
                         "activation-result-format-redacted")

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

    def test_error_fingerprint_and_handoff_discard_free_text(self):
        trace = ActivationTrace()
        trace.stderr("00f0:00f4:err:module:import_dll Library SECRET.dll not found, status c0000135 token=SECRET")
        trace.stderr('00f0:00f4:trace:process:NtCreateUserProcess L"Z:\\private\\XboxPcApp.exe" pid 0100 tid 0104 handles 0x4/0x8 SECRET')
        trace.stderr('00f0:00f4:trace:sync:NtOpenMutant access 0x1, name L"\\BaseNamedObjects\\SECRET"')
        trace.stderr('00f0:00f4:fixme:combase:RoGetActivationFactory ("Microsoft.Windows.AppLifecycle.AppInstance", SECRET): semi-stub')
        result = trace.verdict()
        self.assertEqual(result["error_fingerprints"][0]["function"], "import_dll")
        self.assertEqual(result["error_fingerprints"][0]["message_class"], "module-not-found")
        self.assertEqual(result["handoff_facts"][0]["child_pid"], 256)
        self.assertEqual(result["sync_facts"][0]["name_class"], "base-named-object")
        self.assertEqual(result["activation_facts"][0]["activation_class"], "app-lifecycle")
        self.assertNotIn("SECRET", str(result))

    def test_post_exit_drain_is_bounded_and_not_collector_timeout(self):
        script = (
            "import subprocess,sys,time\n"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(0.6)'])\n"
            "print('calimocho-activation exit_observed_utc 2026-10-25T00:00:00Z')\n"
            "print('calimocho-activation elapsed_ms 91',flush=True)\n"
        )
        result = collect([sys.executable, "-c", script], dict(os.environ), Path.cwd(),
                         seconds=3, post_exit_seconds=0.1)
        self.assertTrue(result["post_exit_drain_limited"])
        self.assertTrue(result["trace_truncated"])
        self.assertFalse(result["collector_timeout"])
        self.assertEqual(result["capture_end"], "post-exit-drain-limit")

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

    def test_cli_returns_nonzero_for_truncated_capture_despite_exit_zero(self):
        collector = Path(__file__).resolve().parents[1] / "tools/diagnose_package_activation.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            for filename in ("bin/wine", "bin/wineserver", "lib/wine/x86_64-windows/ntdll.dll"):
                path = install / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test identity")
            dummy = root / "identity"
            dummy.write_bytes(b"test identity")
            digest = hashlib.sha256(dummy.read_bytes()).hexdigest()
            script = (
                "import sys\n"
                "sys.stderr.write('PRIVATE'*1600000+'\\n');sys.stderr.flush()\n"
                "print('calimocho-activation child_pid 100')\n"
                "print('calimocho-activation resume_status 00000000')\n"
            )
            receipt = {
                "helper": str(dummy), "helper_sha256": digest,
                "registry": str(dummy), "registry_sha256": digest,
                "diagnostic_collector": str(collector),
                "diagnostic_collector_sha256": hashlib.sha256(collector.read_bytes()).hexdigest(),
                "install": str(install), "wine_sha256": digest, "wineserver_sha256": digest,
                "ntdll_sha256": digest, "environment": {}, "cwd": str(root),
                "activation_argv": [sys.executable, "-c", script],
            }
            source = root / "receipt.json"
            source.write_text(json.dumps(receipt))
            output = root / "observed.json"
            result = subprocess.run([sys.executable, str(collector), str(source),
                                     "--output", str(output)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            observed = json.loads(output.read_text())
            self.assertEqual(observed["helper_exit"], 0)
            self.assertTrue(observed["trace_truncated"])
            self.assertNotIn("PRIVATE", output.read_text())


if __name__ == "__main__":
    unittest.main()
