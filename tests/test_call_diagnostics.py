import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import ActivationTrace, CallDiagnostics, collect
from tools.freeze_launcher_runtime import checked_assets
from tools.port_call_diagnostics import BASE, slots, wrappers
from tools.probe_wine_source import sha256


ROOT = REPO / "build/winehq-11.20/package-uwp-calltrace-01"
IID = "{17b0e613-942a-422d-904c-f90dc71a7dae}"


class CallDiagnosticsTests(unittest.TestCase):
    def test_frozen014_producer_install_commands_and_unchanged_native_recipe(self):
        path = ROOT / "cell014-receipt.json"
        receipt = json.loads(path.read_text())
        self.assertEqual(sha256(path), "30b6d6514d58ec6ee188768345673abea86d11d5a0254fce38db9f7484646b48")
        self.assertEqual(receipt["producer_commit"], "f04c70c1e9a8586e62b8f569a1a22f6530ce2d07")
        self.assertFalse(receipt["runtime_executed"])
        for field in ("registry", "inventory", "build_receipt", "staging_receipt", "diagnostic_collector",
                      "helper", "native_fixture", "launcher_registration", "state_observer_build"):
            self.assertEqual(sha256(Path(receipt[field])), receipt[field + "_sha256"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        self.assertEqual(inventory(Path(receipt["install"])), json.loads(Path(receipt["inventory"]).read_text())["files"])
        self.assertEqual(len(json.loads(Path(receipt["inventory"]).read_text())["files"]), 3915)
        self.assertEqual(sha256(Path(receipt["predecessor_receipt"])), receipt["predecessor_receipt_sha256"])
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for field in ("native_xaml_input", "native_xaml_registration", "native_mapping", "native_mapping_count",
                      "factory_observation", "protocol_table", "server_registration_table", "verification", "graph"):
            self.assertEqual(receipt[field], previous[field])
        self.assertEqual(receipt["environment"]["WINEDLLOVERRIDES"], previous["environment"]["WINEDLLOVERRIDES"])
        self.assertTrue(receipt["prefix"].endswith("xbox-calimocho-packaged-20261025-014/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        observer = receipt["state_observer"]
        self.assertEqual(sha256(Path(observer["path"])), observer["sha256"])
        self.assertEqual(observer["argv"][:3], receipt["activation_argv"][:3])
        self.assertEqual(observer["argv"][3], observer["path"])
        self.assertEqual(observer["offset_seconds"], [20, 60])
        self.assertEqual(observer["helper_bound_seconds"], 10)
        for relative, digest in receipt["call_diagnostics"]["files"].items():
            self.assertEqual(sha256(ROOT / "source" / relative), digest)

    def trace(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        trace.stderr('00f0:00f4:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                     'app=L"Microsoft.Xbox.AppL" pid=256 result=00000000 missing=none')
        return trace

    def emit(self, trace, channel, function, text, pid=256):
        trace.stderr(f"{pid:04x}:0104:trace:{channel}:{function} {text}")

    def begin(self, trace):
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1")

    def relay(self, trace, offset, pid=256):
        self.emit(trace, "pkgrelay", "diagnostic_relay",
                  f"relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset={offset:x}", pid)

    def test_query_interface_exact_iid_result_and_return_kind(self):
        trace = self.trace()
        for phase in ("enter", "exit"):
            self.emit(trace, "pkgiface", "diagnostic_interface",
                      f"interface object=CoreApplicationView method=QueryInterface phase={phase} iid={IID} kind=HRESULT result=80004002")
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  "interface object=CoreWindow method=AddRef phase=exit iid=none kind=ULONG result=00000003")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["interface_events"]), 3)
        self.assertNotIn("hresult", result["interface_events"][0])
        self.assertEqual(result["interface_events"][1]["iid"], IID)
        self.assertEqual(result["first_e_nointerface"][0]["hresult"], "0x80004002")
        self.assertEqual(result["interface_events"][2]["refcount"], "0x00000003")

    def test_relay_pid_phase_tail_and_wait_entry_snapshot_are_exact(self):
        trace = self.trace()
        self.relay(trace, 0)
        self.begin(trace)
        for i in range(305):
            self.relay(trace, i)
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1", 512)
        for i in range(310):
            self.relay(trace, i, 512)
        self.emit(trace, "pkgwait", "NtWaitForSingleObject",
                  "wait method=NtWaitForSingleObject phase=enter id=27 count=1 alertable=0 infinite=1")
        self.emit(trace, "pkgwait", "diagnostic_wait", "object id=27 slot=0 handle=88 type=event query=00000000")
        self.emit(trace, "pkgwait", "diagnostic_wait", "event id=27 slot=0 query=00000000 signaled=0")
        self.relay(trace, 999)
        result = trace.verdict()["call_diagnostics"]
        wait = result["waits_without_retained_exit"][0]
        self.assertEqual(len(wait["relay_tail"]), 300)
        self.assertEqual(wait["relay_tail"][0]["caller_offset"], "5")
        self.assertEqual(wait["relay_tail"][-1]["caller_offset"], "130")
        self.assertEqual(wait["objects"], [{"slot": 0, "handle": "0x88", "type": "event", "query_status": "0x00000000"}])
        self.assertIs(wait["events"][0]["signaled"], False)
        self.assertEqual(result["relay_calls_seen"], 306)
        self.assertEqual({row["pid"] for row in result["relay_tail"]}, {256})
        self.emit(trace, "pkgwait", "NtWaitForSingleObject",
                  "wait method=NtWaitForSingleObject phase=exit id=27 result=00000102")
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=0")
        self.relay(trace, 1234)
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(result["waits_without_retained_exit"], [])
        self.assertEqual(result["recent_completed_waits"][0]["result"], "0x00000102")
        self.assertEqual(result["relay_calls_seen"], 306)

    def test_rejects_arbitrary_strings_addresses_methods_and_cross_process_interfaces(self):
        trace = self.trace()
        self.begin(trace)
        for message in (
            "relay module=combase export=SECRET/user caller=Windows.UI.Xaml.dll offset=1",
            "relay module=SECRET export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset=1",
            "relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset=7fff12345678",
            "relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset=1 args=SECRET",
        ):
            self.emit(trace, "pkgrelay", "diagnostic_relay", message)
        for method in ("SECRET", "get_RuntimeSecret"):
            self.emit(trace, "pkgiface", "diagnostic_interface",
                      f"interface object=CoreWindow method={method} phase=exit iid=none kind=HRESULT result=00000000")
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "object id=1 slot=0 handle=20 type=event query=00000000 name=SECRET")
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  f"interface object=CoreFactory method=QueryInterface phase=exit iid={IID} kind=HRESULT result=80004002", 512)
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(result["interface_events"], [])
        self.assertEqual(result["relay_tail"], [])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_limits_keep_first_missing_interface_and_mark_source_tail_unknown(self):
        trace = self.trace()
        self.begin(trace)
        for i in range(65540):
            self.emit(trace, "pkgiface", "diagnostic_interface",
                      f"interface object=CoreFactory method=QueryInterface phase=exit iid={IID} kind=HRESULT result=80004002")
        self.emit(trace, "pkgrelay", "diagnostic_relay", "relay limited=1")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["interface_events"]), 65536)
        self.assertEqual(result["interface_tail_overwritten"], 4)
        self.assertEqual(len(result["first_e_nointerface"]), 1)
        self.assertTrue(result["relay_source_limited"])

    def test_collector_keeps_fixed_diagnostic_tail_past_ordinary_eight_mib_cutoff(self):
        program = (
            "import sys\n"
            "print('calimocho-activation child_pid 240', flush=True)\n"
            "sys.stderr.write('00f0:00f4:trace:pkglaunch:activate_route route scheme=L\"msxboxl\" "
            "app=L\"Microsoft.Xbox.AppL\" pid=256 result=00000000 missing=none\\n')\n"
            "sys.stderr.write(('DISCARDED_SECRET'*512+'\\n')*1200)\n"
            "sys.stderr.write('0100:0104:trace:pkgrelay:__wine_pkg_diagnostic_phase phase initialize=1 xaml=1\\n')\n"
            "sys.stderr.write('0100:0104:trace:pkgrelay:diagnostic_relay relay module=combase "
            "export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset=42\\n')\n")
        result = collect([sys.executable, "-c", program], {}, REPO, seconds=5)
        self.assertGreater(result["bytes_drained"], 8 * 1024 * 1024)
        self.assertTrue(result["trace_truncated"])
        self.assertEqual(result["call_diagnostics"]["relay_calls_seen"], 1)
        self.assertNotIn("DISCARDED_SECRET", json.dumps(result))

    def test_all_122_typed_slots_match_parser_and_generated_forwarders(self):
        build = json.loads((ROOT / "build-receipt.json").read_text())
        coverage = build["call_diagnostics"]["interfaces"]
        self.assertEqual(sum(map(len, coverage.values())), 122)
        for label, names in coverage.items():
            self.assertEqual(set(names), CallDiagnostics.COMMON | CallDiagnostics.METHODS[label])
        generated, names = wrappers(BASE / "build/include/windows.ui.core.h", "ICoreWindow", "window_vtable", "CoreWindow")
        self.assertEqual(len(names), 58)
        for name in names:
            self.assertIn("implementation_window_vtable." + name + "(", generated)
            self.assertIn('"CoreWindow", "' + name + '", "enter"', generated)
            self.assertIn('"CoreWindow", "' + name + '", "exit"', generated)
        with tempfile.TemporaryDirectory() as directory:
            header = Path(directory) / "bad.h"
            header.write_text("typedef struct InvalidVtbl { void (STDMETHODCALLTYPE *Broken)(int); } InvalidVtbl;")
            with self.assertRaises(ValueError):
                slots(header, "Invalid")

    def test_compiled_sources_artifacts_and_sanitized_relay_have_exact_binding(self):
        build = json.loads((ROOT / "build-receipt.json").read_text())
        stage = json.loads((ROOT / "staging-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        self.assertTrue(all(step["exit_code"] == 0 and not step["timed_out"] for step in build["steps"]))
        for relative, digest in build["call_diagnostics"]["files"].items():
            self.assertEqual(sha256(ROOT / "source" / relative), digest)
        for header, digest in build["call_diagnostics"]["headers"].items():
            self.assertEqual(sha256(Path(header)), digest)
        for relative, digest in build["built_files"].items():
            self.assertEqual(sha256(ROOT / relative), digest)
        self.assertEqual(inventory(ROOT / "install"), stage["files"])
        self.assertIn("-DCALIMOCHO_CALL_DIAGNOSTICS", stage["helper_command"])
        relay = (ROOT / "source/dlls/ntdll/relay.c").read_text().split("#elif defined(__x86_64__)", 1)[1]
        relay = relay.split("extern INT_PTR WINAPI relay_call", 1)[0]
        self.assertIn("diagnostic_relay(data, ordinal, stack[-1])", relay)
        self.assertNotIn("trace_string", relay)
        self.assertNotIn("retval=%", relay)
        self.assertNotIn("ret=%", relay)
        for module in ("twinapi.appcore", "windows.ui"):
            source = (ROOT / "source/dlls" / module /
                      ("core_application.c" if module == "twinapi.appcore" else "corewindow_host.c")).read_text()
            self.assertIn("diagnostic_" + ("application_vtable" if module == "twinapi.appcore" else "window_vtable") + "_QueryInterface", source)
        self.assertEqual(sha256(BASE / "cell013-receipt.json"),
                         "a0cf124b6c1040de0cbe180a70c9969612314e95511281cc769d58ee752e0285")
