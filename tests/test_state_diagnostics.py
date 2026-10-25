import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.diagnose_package_activation import ActivationTrace, StateSnapshots, state_rows
from tools.probe_wine_source import sha256


class StateDiagnosticsTests(unittest.TestCase):
    def test_frozen013_binds_new_helpers_and_preserves_012_and_observed_native_inputs(self):
        path = REPO / "build/winehq-11.20/package-uwp-state-01/cell013-receipt.json"
        receipt = json.loads(path.read_text())
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        self.assertEqual(sha256(Path(receipt["predecessor_receipt"])),
                         "d28d3873654eaf4c563db8cf64ef4b2368176729befb6c72eec847b128a9c39f")
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        files = json.loads(Path(receipt["inventory"]).read_text())["files"]
        self.assertEqual(inventory(Path(receipt["install"])), files)
        self.assertEqual(len(files), 3915)
        for key in ("registry", "inventory", "build_receipt", "staging_receipt", "diagnostic_collector",
                    "helper", "native_fixture", "launcher_registration", "state_observer_build"):
            self.assertEqual(sha256(Path(receipt[key])), receipt[key + "_sha256"])
        observer = receipt["state_observer"]
        self.assertEqual(sha256(Path(observer["path"])), observer["sha256"])
        self.assertEqual(observer["argv"][:3], receipt["activation_argv"][:3])
        self.assertEqual(observer["argv"][3], observer["path"])
        self.assertEqual(observer["image"], receipt["target_observer"]["image"])
        self.assertEqual(observer["app_id"], "Microsoft.Xbox.AppL")
        self.assertEqual(observer["offset_seconds"], [20, 60])
        self.assertEqual(observer["helper_bound_seconds"], 10)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        self.assertEqual(receipt["native_xaml_input"], previous["native_xaml_input"])
        self.assertEqual(receipt["native_xaml_registration"], previous["native_xaml_registration"])
        self.assertEqual(receipt["native_mapping_count"], 558)
        self.assertEqual(receipt["environment"]["WINEDLLOVERRIDES"], previous["environment"]["WINEDLLOVERRIDES"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        self.assertFalse(receipt["runtime_executed"])

    def test_progress_parser_matches_emitted_shape_and_only_retains_target_fixed_fields(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        trace.stderr('00f0:00f4:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                     'app=L"Microsoft.Xbox.AppL" pid=256 result=00000000 missing=none')
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=StaticLifetime.GetCollection phase=enter result=00000000")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=StaticLifetime.PropertySet phase=exit result=80040154")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=StaticLifetime.Lookup phase=exit result=8000000b")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=FrameworkView.Initialize phase=enter result=00000000")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=FrameworkView.Initialize phase=exit result=00000000")
        trace.stderr("0200:0104:trace:pkgcore:progress progress method=Activated phase=exit result=00000000")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=SECRET phase=enter result=00000000")
        trace.stderr("0100:0104:trace:pkgcore:progress progress method=StaticLifetime.Insert phase=exit result=00000000 SECRET")
        records = trace.verdict()["method_progress"]
        self.assertEqual(len(records), 5)
        self.assertNotIn("hresult", records[0])
        self.assertEqual(records[1]["hresult"], "0x80040154")
        self.assertEqual(records[2]["hresult"], "0x8000000b")
        self.assertNotIn("SECRET", str(trace.verdict()))
        trace.stderr("0100:0104:trace:pkgcore:progress progress limited=1")
        self.assertTrue(trace.truncated)

    def test_fixed_snapshot_grammar_redacts_raw_stack_text_and_paths(self):
        output = (
            b"state pid=256 verified=1\n"
            b"state threads-before-attach=7\n"
            b"state tid=260 frame=0 module=ntdll.dll offset=1234\n"
            b"state hwnd=10066 class=CalimochoCoreWindow visible=1 width=800 height=600\n"
            b"state detached=1 stacks=1 target-exited=0\n"
            b"RAW C:\\SECRET\\private.dll 0x12345678\n"
            b"state tid=260 frame=0 module=C:\\SECRET offset=1234\n"
        )
        result = state_rows(output)
        self.assertTrue(result["format_error"])
        self.assertEqual(len(result["rows"]), 5)
        self.assertNotIn("SECRET", str(result))
        self.assertTrue(state_rows(b"x" * (256 * 1024 + 1))["truncated"])

    def test_snapshot_schedule_only_runs_twice_for_exact_target_and_waits_to_offsets(self):
        calls = []
        class Process:
            returncode = 0
            def poll(self):
                return 0
            def wait(self, timeout):
                return 0
        def spawn(argv, **kwargs):
            calls.append(argv)
            kwargs["stdout"].write(b"state pid=256 verified=1\nstate detached=1 stacks=1 target-exited=0\n")
            kwargs["stdout"].flush()
            return Process()
        observer = StateSnapshots({"argv": ["fixture"], "image": "IMAGE", "app_id": "Microsoft.Xbox.AppL"},
                                  dict(os.environ), Path.cwd())
        with patch("tools.diagnose_package_activation.subprocess.Popen", side_effect=spawn):
            observer.tick(0, None)
            observer.tick(5, 256)
            observer.tick(24.9, 256)
            self.assertEqual(calls, [])
            observer.tick(25, 256)
            observer.tick(26, 256)
            observer.tick(65, 256)
            observer.tick(66, 256)
            observer.tick(100, 256)
        self.assertEqual(calls, [["fixture", "256", "IMAGE", "Microsoft.Xbox.AppL"]] * 2)
        self.assertEqual([result["scheduled_seconds"] for result in observer.results], [20, 60])
        self.assertTrue(all(not result["bounded"] for result in observer.results))

    def test_snapshot_bounds_and_kills_only_its_helper(self):
        class Process:
            returncode = None
            killed = False
            def poll(self):
                return self.returncode
            def kill(self):
                self.killed = True
                self.returncode = -9
            def wait(self, timeout):
                return self.returncode
        process = Process()
        observer = StateSnapshots({"argv": ["fixture"], "image": "IMAGE", "app_id": "Microsoft.Xbox.AppL"},
                                  {}, Path.cwd())
        with patch("tools.diagnose_package_activation.subprocess.Popen", return_value=process):
            observer.tick(0, 256)
            observer.tick(20, 256)
            observer.tick(30, 256)
            observer.tick(60, 256, target_exited=True)
        self.assertTrue(process.killed)
        self.assertEqual(len(observer.results), 1)
        self.assertEqual(observer.results[0]["reason"], "snapshot-bound")

    def test_013_compiled_source_and_safety_contract(self):
        root = REPO / "build/winehq-11.20/package-uwp-state-01"
        build = json.loads((root / "build-receipt.json").read_text())
        stage = json.loads((root / "staging-receipt.json").read_text())
        observer = json.loads((root / "state-observer-build.json").read_text())
        for path, digest in build["source_inputs"].items():
            self.assertEqual(sha256(REPO / path), digest)
        self.assertEqual(inventory(root / "install"), stage["files"])
        self.assertEqual(sha256(Path(observer["source"])), observer["source_sha256"])
        self.assertEqual(sha256(Path(observer["output"])), observer["output_sha256"])
        self.assertEqual(observer["exit_code"], 0)
        source = Path(observer["source"]).read_text()
        self.assertLess(source.index("wine_query_package_identity"), source.index("DebugActiveProcess(target)"))
        self.assertLess(source.index("DebugSetProcessKillOnExit(FALSE)"), source.index("DebugActiveProcess(target)"))
        self.assertIn("DebugActiveProcessStop(target)", source)
        self.assertIn('SymInitialize(process, "", FALSE)', source)
        self.assertNotIn("GetWindowText", source)
        self.assertNotIn("SendMessage", source)
        self.assertNotIn("TerminateProcess", source)
        core = (root / "source/dlls/twinapi.appcore/core_application.c").read_text()
        self.assertIn('TRACE("progress method=%s phase=%s result=%08lx\\n"', core)
        self.assertIn('progress("FrameworkView.SetWindow", "enter", S_OK)', core)
        self.assertIn('progress("StaticLifetime.GetCollection", "enter", S_OK)', core)
