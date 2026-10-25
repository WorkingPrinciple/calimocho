import json
import hashlib
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import ActivationTrace
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


ROOT = REPO / "build/winehq-11.20/package-uwp-handle-provenance-01"


class HandleProvenanceTests(unittest.TestCase):
    def test_frozen016_binds_exact_sources_all_assets_and_sealed015(self):
        path = ROOT / "cell016-receipt.json"
        receipt = json.loads(path.read_text())
        self.assertEqual(sha256(path), "b55779b754cacf0b091dac907c381a9dcf3133acdbe8169b8f18a226705d38d5")
        self.assertFalse(receipt["runtime_executed"])
        self.assertEqual(receipt["producer_commit"], "2c1cc61777225c92fb64c900692a5378f76375cd")
        self.assertEqual(receipt["predecessor_receipt_sha256"], "58eccd9ec5d9aba954eb80251efadb8d8117b2f49aba6088604e981b5b50a122")
        for key in ("registry", "inventory", "build_receipt", "staging_receipt", "diagnostic_collector",
                    "helper", "native_fixture", "launcher_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[key])), receipt[key + "_sha256"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        files = json.loads(Path(receipt["inventory"]).read_text())["files"]
        self.assertEqual(len(files), 3915)
        self.assertEqual(inventory(Path(receipt["install"])), files)
        checked_assets(json.loads(Path(receipt["registry"]).read_text())["engines"][0])
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for key in ("native_xaml_input", "native_xaml_registration", "native_mapping", "native_mapping_count",
                    "factory_observation", "protocol_table", "server_registration_table", "verification", "graph"):
            self.assertEqual(receipt[key], previous[key])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertTrue(receipt["prefix"].endswith("xbox-calimocho-packaged-20261025-016/prefix"))
        self.assertEqual(receipt["state_observer"]["offset_seconds"], [20, 60])
        self.assertEqual(sha256(Path(receipt["state_observer"]["path"])), receipt["state_observer"]["sha256"])
        self.assertEqual(receipt["state_observer"]["argv"][:3], receipt["activation_argv"][:3])
        self.assertIn("lib/wine/x86_64-windows/rpcrt4.dll", receipt["changed_modules"])
        self.assertEqual(len(receipt["changed_modules"]), 8)

    def trace(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        trace.stderr('00f0:00f4:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                     'app=L"Microsoft.Xbox.AppL" pid=256 result=00000000 missing=none')
        return trace

    def emit(self, trace, channel, function, message, pid=256):
        trace.stderr(f"{pid:04x}:0104:trace:{channel}:{function} {message}")

    def run_phase(self, trace, phase="enter", pid=256):
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  f"interface object=CoreApplication method=Run phase={phase} iid=none kind=HRESULT result=00000000", pid)

    def handle(self, trace, operation="NtCreateEvent", handle="58", owner=256, phase="exit", name="unnamed", pid=256):
        self.emit(trace, "pkghandle", "diagnostic_handle",
                  f"handle operation={operation} phase={phase} result=00000000 handle={handle} source=0 "
                  f"owner={owner} peer=0 name={name} query=00000000 module=kernelbase.dll offset=123 "
                  "syscall=ntdll.dll site=f7d4", pid)

    def wait(self, trace, mode=1):
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1")
        self.emit(trace, "pkgwait", "NtWaitForMultipleObjects",
                  f"wait method=NtWaitForMultipleObjects phase=enter id=7 count=2 alertable=0 infinite=1 waittype={mode}")

    def result(self, trace):
        return trace.verdict()["call_diagnostics"]

    def test_wait_process_identity_exit_and_real_wait_mode(self):
        trace = self.trace()
        self.run_phase(trace)
        self.wait(trace, 0)
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "process id=7 slot=1 query=00000000 pid=240 parent=200 exit=00000103 image-query=00000000 image=XboxPcAppCE.exe")
        row = self.result(trace)["waits_without_retained_exit"][0]
        self.assertEqual(row["wait_type"], "all")
        process = row["processes"][0]
        self.assertEqual((process["pid"], process["parent_pid"]), (240, 200))
        self.assertTrue(process["alive_at_entry"])
        self.assertEqual(process["image"], "XboxPcAppCE.exe")
        self.assertEqual(process["signal_condition"], "this-process-terminates")

    def test_failed_process_query_is_unknown_not_dead(self):
        trace = self.trace()
        self.wait(trace)
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "process id=7 slot=1 query=c0000022 pid=0 parent=0 exit=00000000 image-query=c0000022 image=unknown-redacted")
        process = self.result(trace)["waits_without_retained_exit"][0]["processes"][0]
        for key in ("pid", "parent_pid", "exit_status", "alive_at_entry"):
            self.assertIsNone(process[key])
        self.assertEqual(process["query_status"], "0xc0000022")

    def test_creation_close_and_duplicate_are_run_pid_owner_and_sequence_bound(self):
        trace = self.trace()
        self.handle(trace)
        self.run_phase(trace)
        self.handle(trace)
        self.handle(trace, "NtClose")
        self.handle(trace, "NtDuplicateObject", owner=512)
        self.run_phase(trace, pid=512)
        self.handle(trace, pid=512)
        self.wait(trace)
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "object id=7 slot=0 handle=58 type=event query=00000000")
        self.handle(trace, "NtOpenEvent")
        self.run_phase(trace, "exit")
        self.handle(trace, "NtOpenEvent")
        result = self.result(trace)
        self.assertEqual(len(result["handle_provenance"]), 4)
        candidates = result["waits_without_retained_exit"][0]["handle_provenance_candidates"][0]["events"]
        self.assertEqual([row["operation"] for row in candidates], ["NtCreateEvent", "NtClose"])
        self.assertEqual(candidates[0]["caller_basis"], "user-stack-return-slot-not-a-full-stack")

    def test_actual_ipc_entries_not_success_or_binding_string_inference(self):
        trace = self.trace()
        self.run_phase(trace)
        self.handle(trace, "NtAlpcConnectPort", phase="enter", name="named-redacted")
        self.emit(trace, "pkgrpc", "diagnostic_rpc",
                  "rpc operation=OpenClientConnection phase=enter result=00000000 module=rpcrt4.dll offset=42 endpoint=redacted")
        self.emit(trace, "pkgrpc", "diagnostic_rpc",
                  "rpc operation=OpenClientConnection phase=exit result=000006ba module=rpcrt4.dll offset=42 endpoint=redacted")
        self.emit(trace, "pkgrelay", "diagnostic_relay",
                  "relay module=kernelbase export=OpenProcess caller=combase.dll offset=567")
        result = self.result(trace)
        self.assertNotIn("result", result["handle_provenance"][0])
        self.assertNotIn("result", result["rpc_connection_attempts"][0])
        self.assertEqual(result["rpc_connection_attempts"][1]["result"], "0x000006ba")
        self.assertEqual(result["relay_tail"][0]["caller_module"], "combase.dll")

    def test_privacy_grammar_rejects_arbitrary_names_paths_and_addresses(self):
        trace = self.trace()
        self.run_phase(trace)
        self.handle(trace, name="SECRET_EVENT")
        self.handle(trace, name="/Users/SECRET")
        self.emit(trace, "pkgrpc", "diagnostic_rpc",
                  "rpc operation=OpenClientConnection phase=exit result=00000000 module=/SECRET offset=42 endpoint=redacted")
        self.wait(trace)
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "process id=7 slot=1 query=00000000 pid=240 parent=200 exit=00000103 image-query=00000000 image=C:/SECRET.exe")
        result = self.result(trace)
        self.assertEqual(result["handle_provenance"], [])
        self.assertEqual(result["rpc_connection_attempts"], [])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_handle_ring_and_candidates_have_explicit_bounds(self):
        trace = self.trace()
        self.run_phase(trace)
        for _ in range(4100):
            self.handle(trace)
        self.wait(trace)
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "object id=7 slot=0 handle=58 type=event query=00000000")
        result = self.result(trace)
        self.assertEqual(len(result["handle_provenance"]), 4096)
        self.assertEqual(result["handle_tail_overwritten"], 4)
        candidate = result["waits_without_retained_exit"][0]["handle_provenance_candidates"][0]
        self.assertEqual(len(candidate["events"]), 32)
        self.assertTrue(candidate["tail_limited"])

    def test_built_source_uses_real_queries_and_preserves_original_abi_results(self):
        build = json.loads((ROOT / "build-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        self.assertTrue(all(not step["exit_code"] and not step["timed_out"] for step in build["steps"]))
        for relative, digest in build["handle_provenance"]["files"].items():
            self.assertEqual(sha256(ROOT / "source" / relative), digest)
        sync = (ROOT / "source/dlls/ntdll/unix/sync.c").read_text()
        server = (ROOT / "source/dlls/ntdll/unix/server.c").read_text()
        process = (ROOT / "source/dlls/ntdll/unix/process.c").read_text()
        for name, text in (("NtCreateEvent", sync), ("NtOpenEvent", sync),
                           ("NtDuplicateObject", server), ("NtClose", server),
                           ("NtOpenProcess", process), ("NtCreateUserProcess", process)):
            self.assertIn("result = diagnostic_original_" + name + "(", text)
        self.assertIn("GPT_IMPORT(NtCreateEvent)", sync)
        self.assertIn("GPT_IMPORT(NtClose)", server)
        wait = (ROOT / "source/dlls/ntdll/unix/package_wait_diagnostics.h").read_text()
        self.assertIn("ProcessBasicInformation", wait)
        self.assertIn("ProcessImageFileName", wait)
        self.assertIn("process.InheritedFromUniqueProcessId", wait)
        self.assertIn('waittype=%u', sync)
        rpc = (ROOT / "source/dlls/rpcrt4/rpc_transport.c").read_text()
        self.assertIn("result = Connection->ops->open_connection_client(Connection);", rpc)
        self.assertIn('diagnostic_rpc("exit", result, caller);', rpc)


if __name__ == "__main__":
    unittest.main()
