"""Build a target-only bounded state observer and freeze a changed013 sibling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.build_gameinput_overlay import WINE, compile_flags
from tools.build_uwp_overlay import REPO
from tools.freeze_static_lifetime_runtime import freeze
from tools.freeze_registrar_cell import add_headless_setup, add_registrar_handoff, registrar_sources, registrar_stack_build
from tools.probe_wine_source import sha256

PREVIOUS = REPO / "build/winehq-11.20/package-uwp-static-lifetime-01/cell012-receipt.json"
SOURCES = ("tools/freeze_state_runtime.py", "tests/package_state_probe.c")


def compile_observer(root, resume=False):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or any(root.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned013 build")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing MinGW compiler")
    output = root / "package-state-probe.exe"
    if output.exists():
        if not resume:
            raise FileExistsError("Refuse replacing state observer without explicit compile resume")
        previous = json.loads((root / "state-observer-build.json").read_text())
        if sha256(output) != previous["output_sha256"]:
            raise ValueError("Previous observer differs from compilation receipt")
        attempt = 1
        while (root / ("state-observer-retained-%02d" % attempt)).exists():
            attempt += 1
        retained = root / ("state-observer-retained-%02d" % attempt)
        retained.mkdir()
        output.rename(retained / output.name)
        (root / "state-observer-build.json").rename(retained / "state-observer-build.json")
    attempt = 1
    while (root / ("state-observer-build-%02d.log" % attempt)).exists():
        attempt += 1
    source = REPO / "tests/package_state_probe.c"
    command = [compiler, "-I" + str(root / "source/include"),
               *compile_flags(root / "build/include"), "-D_UCRT", "-municode", str(source)]
    command += [str(WINE / "build/dlls" / name / "x86_64-windows" / ("lib" + name + ".a"))
                for name in ("kernel32", "advapi32", "user32", "dbghelp")]
    command += [str(root / "build/dlls/ntdll/x86_64-windows/libntdll.a"), "-o", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    log = root / ("state-observer-build-%02d.log" % attempt)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("State observer compilation failed; see retained log")
    record = {"command": command, "exit_code": result.returncode, "log": str(log),
              "source": str(source), "source_sha256": sha256(source),
              "output": str(output), "output_sha256": sha256(output), "runtime_executed": False}
    (root / "state-observer-build.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def prepare(root, producer, cell=13):
    requested_cell = cell
    # Cells026-029 carry the same diagnostic contract into fresh run namespaces.
    if cell in (26, 27, 28, 29):
        cell = 25
    root = Path(root).resolve(strict=True)
    record = json.loads((root / "state-observer-build.json").read_text())
    if record["exit_code"] or record["runtime_executed"]:
        raise ValueError("Require compiled unexecuted state observer")
    if sha256(Path(record["output"])) != record["output_sha256"] or sha256(Path(record["source"])) != record["source_sha256"]:
        raise ValueError("State observer source or binary changed")
    if cell not in (13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        raise ValueError("Unsupported diagnostic cell")
    extra = SOURCES
    previous, digest = PREVIOUS, "d28d3873654eaf4c563db8cf64ef4b2368176729befb6c72eec847b128a9c39f"
    if cell in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-state-01/cell013-receipt.json"
        digest = "a0cf124b6c1040de0cbe180a70c9969612314e95511281cc769d58ee752e0285"
        extra += ("tools/port_call_diagnostics.py", "patches/wine/files/package_call_diagnostics.h",
                  "patches/wine/files/package_relay_diagnostics.h", "patches/wine/files/package_wait_diagnostics.h",
                  "patches/wine/contracts/istaticlifetime-diagnostics.json",
                  "patches/wine/files/whiny_diagnostics_17b0e613_942a_422d_904c_f90dc71a7dae.h",
                  "patches/wine/files/istaticlifetime-relay-filter.txt")
        build = json.loads((root / "build-receipt.json").read_text())
        if "call_diagnostics" not in build:
            raise ValueError("Cell014 requires actual diagnostic source port")
        whiny = build["call_diagnostics"].get("whiny_wx11")
        if not whiny or whiny["commit"] != "fe9ebc055ed857d7d63072539659a8f404064d02":
            raise ValueError("Cell014 requires the WX-11-generated StaticLifetime diagnostics")
        if (sha256(Path(whiny["contract"])) != whiny["contract_sha256"]
                or sha256(Path(whiny["header"])) != whiny["header_sha256"]
                or sha256(Path(whiny["relay_filter"])) != whiny["relay_filter_sha256"]):
            raise ValueError("WX-11 emitter inputs changed")
        if whiny["slot_count"] != 19 or whiny["wrapped_slots"] != list(range(19)) or whiny["passthrough_slots"]:
            raise ValueError("WX-11 interface coverage changed")
        for relative, value in build["call_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated diagnostic source changed")
        for header, value in build["call_diagnostics"]["headers"].items():
            if sha256(Path(header)) != value:
                raise ValueError("Diagnostic ABI header changed")
    if cell in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-calltrace-01/cell014-receipt.json"
        digest = "30b6d6514d58ec6ee188768345673abea86d11d5a0254fce38db9f7484646b48"
        from tools.port_activation_wait_diagnostics import SOURCES as ACTIVATION_SOURCES
        extra += ACTIVATION_SOURCES
        if "activation_wait_diagnostics" not in build:
            raise ValueError("Cell015 requires actual activation/wait source port")
        for relative, value in build["activation_wait_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated activation/wait source changed")
    if cell in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-activation-waits-01/cell015-receipt.json"
        digest = "58eccd9ec5d9aba954eb80251efadb8d8117b2f49aba6088604e981b5b50a122"
        from tools.port_handle_provenance import SOURCES as HANDLE_SOURCES
        extra += HANDLE_SOURCES
        if "handle_provenance" not in build:
            raise ValueError("Cell016 requires actual handle/IPC provenance port")
        from tools.port_handle_provenance import PREVIOUS as HANDLE_BASELINE
        for relative, value in build["handle_provenance"]["baseline_files"].items():
            if sha256(HANDLE_BASELINE / "source" / relative) != value:
                raise ValueError("Sealed handle/IPC baseline source changed")
        for relative, value in build["handle_provenance"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated handle/IPC source changed")
    if cell in (17, 18, 19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-handle-provenance-01/cell016-receipt.json"
        digest = "b55779b754cacf0b091dac907c381a9dcf3133acdbe8169b8f18a226705d38d5"
        from tools.port_exception_diagnostics import SOURCES as EXCEPTION_SOURCES
        extra += EXCEPTION_SOURCES
        if "exception_diagnostics" not in build:
            raise ValueError("Cell017 requires actual exception source port")
        for relative, value in build["exception_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated exception source changed")
    if cell in (18, 19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-exception-01/cell017-receipt.json"
        digest = "0a757c6da94c8f6b3b5cabaa3130597c878082a6e9ab861b78b08646efa94389"
        extra += ("tests/test_lifetime19.py",
                  "docs/ADR/0050-use-the-observed-native-coreapplication-lifetime-abi.md")
        abi_facts = Path("/Users/dragoshont/.copilot/session-state/de639724-87ed-4a4b-bf11-0e161cba9ff3/files/twinapi-static-abi-r01.json")
        abi_digest = "8c02195d96ddc0ee346be0019d40c2c9a04ffd5b4c7a243311e89207b2dc88b5"
        if sha256(abi_facts) != abi_digest:
            raise ValueError("Observed native lifetime ABI facts changed")
    if cell in (19, 20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-lifetime19-01/cell018-receipt.json"
        digest = "e75c54e81fec44d3bcb6984bd648b396b4d27f4dcfa7437e07e44ec62c1f4b45"
        from tools.port_failfast_diagnostics import SOURCES as FAILFAST_SOURCES
        extra += FAILFAST_SOURCES + ("tests/test_failfast_diagnostics.py",
                                    "docs/ADR/0051-observe-failfast-status-and-error-context.md")
        if "failfast_diagnostics" not in build:
            raise ValueError("Cell019 requires actual fail-fast diagnostic port")
        for relative, value in build["failfast_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated fail-fast source changed")
    if cell in (20, 21, 22, 23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-failfast-01/cell019-receipt.json"
        digest = "245aa4ca6780a68ee8473404ba9b4055524046edf6f5adce1fa42ebfe9474233"
        from tools.port_status_diagnostics import SOURCES as STATUS_SOURCES
        extra += STATUS_SOURCES + ("tests/test_status_diagnostics.py",
                                   "docs/ADR/0052-discriminate-not-implemented-returns.md")
        if "status_diagnostics" not in build:
            raise ValueError("Cell020 requires actual status-return diagnostic port")
        for relative, value in build["status_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated status-return source changed")
    if cell == 21:
        previous = REPO / "build/winehq-11.20/package-uwp-status-01/cell020-receipt.json"
        digest = "014ba68ad3c03834a0dbda2cd0c904bf276a7a6f8ef168a4d274458c726213ee"
        from tools.port_claims_site_b import SOURCES as CLAIMS_SOURCES
        extra += CLAIMS_SOURCES + ("tests/test_claims_site_b.py",
                                  "docs/ADR/0053-use-observed-packaged-claims-site-b.md")
        if "claims_site_b" not in build:
            raise ValueError("Cell021 requires the pinned claims Site B source port")
        for relative, value in build["claims_site_b"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated Site B source or context changed")
    if cell == 22:
        previous = REPO / "build/winehq-11.20/package-uwp-claims-site-b-01/cell021-receipt.json"
        digest = "633a1ed482e280bf73ed59781e2cfa0a1a340d37a9ea6c981e5bf50828e6164f"
        from tools.port_claims_thread_token import SOURCES as THREAD_TOKEN_SOURCES
        extra += THREAD_TOKEN_SOURCES + ("tests/test_claims_thread_token.py",
                                         "docs/ADR/0054-observe-thread-token-claims-context.md")
        if "claims_thread_token" not in build:
            raise ValueError("Cell022 requires pinned r8 claims and context diagnostics")
        for relative, value in build["claims_thread_token"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Thread-token generated source or context changed")
    if cell in (23, 24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-claims-thread-token-01/cell022-receipt.json"
        digest = "f02c2ccbb85538da61c56c14fb6370b7e1882bb36cdc9267663120af7faf5b7a"
        from tools.port_claims_thread_token import PACKAGED_SOURCES
        extra += PACKAGED_SOURCES + ("tests/test_claims_packaged_thread.py",
                                     "docs/ADR/0055-use-observed-packaged-effective-token-claims.md")
        if "claims_packaged_thread" not in build:
            raise ValueError("Cell023 requires pinned r9 packaged effective-token claims")
        for relative, value in build["claims_packaged_thread"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Packaged effective-token source or context changed")
    if cell in (24, 25):
        previous = REPO / "build/winehq-11.20/package-uwp-claims-packaged-thread-01/cell023-receipt.json"
        digest = "e4899d28429cb7af93d3c311066bee13de2a13cd9e703698816347dc6837fa1f"
        from tools.port_onecore_transform import SOURCES as ONECORE_SOURCES
        extra += ONECORE_SOURCES + ("tests/test_onecore_transform.py",
                                    "docs/ADR/0056-expose-observed-onecore-transform-query.md")
        if "onecore_transform" not in build:
            raise ValueError("Cell024 requires observed user32 query source")
        for relative, value in build["onecore_transform"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("OneCore query source changed")
    if cell == 25:
        previous = REPO / "build/winehq-11.20/package-uwp-onecore-transform-01/cell024-receipt.json"
        digest = "ba82f32c76a161273ad171065fd1de0eeaa8ce26ed76fe26b0652c5148ec952f"
        from tools.port_coremessaging_prerequisites import SOURCES as COREMESSAGING_SOURCES
        extra += COREMESSAGING_SOURCES + (
            "tools/qualify_coremessaging_imports.py", "tests/test_coremessaging_imports.py",
            "tests/test_wait_completion_packet.py", "tests/wait_completion_packet_host.c",
            "tests/test_coremessaging_ntdll_stubs.py",
            "docs/ADR/0057-qualify-native-coremessaging-prerequisites.md")
        if "coremessaging_prerequisites" not in build:
            raise ValueError("Cell025 requires real wait packets and explicit unsupported native prerequisites")
        for relative, value in build["coremessaging_prerequisites"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("CoreMessaging source changed: " + relative)
        from tools.qualify_coremessaging_imports import PE, qualify
        pins = json.loads((REPO / "versions.json").read_text())["native_coremessaging_reference"]
        native = Path(pins["path"])
        if not native.is_file() or native.is_symlink() or (
                native.stat().st_size != pins["size"] or sha256(native) != pins["sha256"]):
            raise ValueError("Retained native CoreMessaging identity changed")
        native_closure = qualify(native, root / "install", root / "source")
        if PE(root / "install/lib/wine/x86_64-windows/ucrtbase.dll").exports().get(
                "__C_specific_handler_noexcept") != pins["observed_noexcept_forwarder"]:
            raise ValueError("Observed AMD64 CRT forwarder not reproduced")
    cell026 = {}
    if requested_cell in (26, 27, 28, 29):
        extra += ("docs/ADR/0058-fail-unsupported-coremessaging-ordinals-explicitly.md",)
        from tools.qualify_coremessaging_imports import qualify_ordinal_guards
        cell026["ordinal_guard_qualification"] = qualify_ordinal_guards(root / "install")
        inspection = root / "whiny-coremessaging-inspect.json"
        inspected = json.loads(inspection.read_text())
        if inspected["sha256"] != pins["sha256"]:
            raise ValueError("Whiny inspected a different CoreMessaging input")
        if inspected["wine_build"]["sources"] != [str(root / "source")] or (
                inspected["wine_build"]["installs"] != [str(root / "install/lib/wine/x86_64-windows")]):
            raise ValueError("Whiny inspection is not bound to this candidate")
        if any(not row["delayed"] for row in inspected["imports"]
               if row["wine"]["status"] not in ("implemented", "native-override")):
            raise ValueError("Whiny reports a new mandatory import gap")
        cell026["whiny_inspection"] = {"path": str(inspection), "sha256": sha256(inspection),
                                      "status": inspected["status"],
                                      "wine_statuses": inspected["summary"]["wine_statuses"]}
        resume = Path("/Users/dragoshont/.copilot/session-state/0ab735d8-8917-47c8-ab05-4c047158e199/files/owner-resume-20261025-1542.json")
        resume_digest = "0494ca577f87491f5a6df940c6aa8b95bc13d470e19c69dd71024ecf4aff8c44"
        if sha256(resume) != resume_digest:
            raise ValueError("Relayed owner decision record changed")
        cell026.update(cell="%03d" % requested_cell, owner_resume_sha256=resume_digest,
                       owner_resume_record=str(resume))
    if requested_cell in (27, 28, 29):
        extra += registrar_sources()
        cell026.update(registrar_stack_build(root, build))
    path = freeze(root, producer, cell=requested_cell, predecessor=previous,
                  predecessor_sha256=digest, extra_sources=extra)
    receipt = json.loads(path.read_text())
    observer = receipt["target_observer"]
    receipt["state_observer"] = {
        "path": record["output"], "sha256": record["output_sha256"],
        "image": observer["image"], "app_id": observer["app_id"],
        "argv": observer["argv"][:3] + [record["output"]],
        "offset_seconds": [20, 60], "helper_bound_seconds": 10,
        "thread_limit": 64, "frame_limit": 16, "module_limit": 512,
        "basis": "exact image and admitted token, EnumWindows plus Wine debugger local-module stack walking",
    }
    receipt["state_observer_build"] = str(root / "state-observer-build.json")
    receipt["state_observer_build_sha256"] = sha256(root / "state-observer-build.json")
    receipt["scope"] = "cell%03d bounded actual AppL progress, thread and window discriminator" % cell
    receipt["preconditions"] += [
        "Observer samples target-only state about20/60 seconds after recorded AppL handoff;180s cap unchanged",
        "Debugger attachment briefly suspends target threads and is measurement, not unperturbed runtime proof",
        "Debug kill-on-exit disabled before attach; each helper detaches or reports explicit failure; do not replay",
        "If a verified CalimochoCoreWindow is visible, owner maps exact Wine HWND to exact Mac window and captures one private target-only screenshot with SHA-256",
        "If exact HWND-to-Mac mapping or screenshot permission is unavailable, record that limitation; no desktop capture or guessed window",
    ]
    receipt["limitations"] += [
        "Only fixed method names/phases/HRESULTs retained; map keys, object values, addresses and arbitrary titles excluded",
        "Stack frames use basename plus module-relative offsets; unknown mappings are redacted",
        "Snapshot failures/truncation and debugger perturbation remain explicit; no inferred deadlock or UI acceptance",
    ]
    if cell in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        receipt["call_diagnostics"] = build["call_diagnostics"]
        receipt["scope"] = "cell014 diagnostic-only complete owned COM vtables, sanitized native-XAML relay and actual wait pairs"
        receipt["preconditions"] += [
            "Fresh%03d once only; all changed modules and compiled diagnostic helper must match this receipt" % requested_cell,
            "No game/input/window control; same actual AppL256/native16302 recipe and180s cap",
        ]
        receipt["limitations"] += [
            "122 typed vtable slots forward unchanged; diagnostics perturb timing and do not fix an interface",
            "Relay covers only actual x64 Wine relay thunks and direct native XAML return sites during Initialize",
            "Norelay/syscall or indirect native-to-native calls are not relay evidence; actual NtWait wrappers supply separate metadata",
            "Relay has65536 source-call cap and last300 retained callsites; source limit and collector ring overwrite are explicit",
            "COM event tail bounded65536 plus first32 HRESULT failures; absence beyond a reached limit is not a negative claim",
            "Wait object type and event state are read-only observations before actual wait, not a proven cause",
            "Collector retains fixed diagnostic grammar past ordinary8MiB cutoff; no argument strings, object names or absolute addresses",
        ]
    if cell in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell015 public activation entry/result/provider, actual wait object state and thread creation/liveness"
        receipt["activation_wait_diagnostics"] = build["activation_wait_diagnostics"]
        receipt["limitations"] += [
            "014 successful object queries were classifiedunknown by a host-wchar/UTF16 width bug; corrected source is separate and never rewrites014",
            "RoGetActivationFactory and RoActivateInstance entry/exit capture every call, independently of Initialize, capped4096 retained events",
            "Successful factory exit reports the actual serving image selected by combase; instance exit provider is associated through its nested factory trace",
            "RoGetActivatableClassRegistration remains Wine's existing ABI-unknown stub; no guessed signature, class decoding or unconditional success; actual stub failures are marked",
            "Event/semaphore signalers are not intrinsic owner facts; remainunknown unless separate observed code establishes one",
            "Thread creation records actual NtCreateThreadEx entry/return during Initialize, start image, saved syscall return and read-only user-stack return-slot candidate",
            "Creator return-slot metadata is not a recovered full stack or proven semantic call chain; remote-process thread creation is outside this in-process scope",
            "Snapshot alive means observed thread exit status; pending wait entries are correlated separately, not guessed OS thread-state enums",
        ]
    if cell in (16, 17, 18, 19, 20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell016 process-handle identity, event/process creation provenance and IPC attempts"
        receipt["handle_provenance"] = build["handle_provenance"]
        receipt["limitations"] += [
            "Wait type is actual WaitAll/WaitAny; prior count/alertability metadata did not establish OR semantics",
            "Process basic/image queries retain PID, parent, exit status and validated basename; failed queries remain unknown",
            "Handle tail4096 from CoreApplication.Run, chronological per-wait candidates32 per slot; pre-Run creation/inheritance unavailable",
            "NtClose events distinguish observed reuse; candidates are not automatically a proven complete lineage",
            "Only exact known-public DBWIN event basenames retained; other names are unnamed or named-redacted",
            "NtCreateUserProcess/OpenProcess/duplicate/event and LPC/ALPC entry/exit forward original ABI and results unchanged",
            "Saved syscall and user-return-slot sites are not a full creator stack or semantic module attribution",
            "Sanitized relay covers only actual thunks from native XAML/combase/twinapi to selected exports; norelay/internal calls unavailable",
            "RPC OpenClientConnection is the actual transport attempt,1024 retained entry/exit events; endpoints and binding strings excluded",
            "No process/broker, event, RPC service or success behavior is synthesized; absent covered calls do not prove absence of all IPC",
        ]
    if cell in (17, 18, 19, 20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell017 real unhandled-filter exception, no debugger dialog and actual target exit"
        receipt["exception_diagnostics"] = build["exception_diagnostics"]
        registration = root / ("aedebug-CELL%03d-FROZEN.reg" % cell)
        registration.write_bytes((
            "Windows Registry Editor Version 5.00\r\n\r\n"
            "[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AeDebug]\r\n"
            '"Auto"="0"\r\n').encode("utf-16"))
        from tools.prepare_verified_activation import dos
        receipt["aedebug_registration"] = str(registration)
        receipt["aedebug_registration_sha256"] = sha256(registration)
        receipt["aedebug_registration_argv"] = receipt["activation_argv"][:3] + ["regedit", "/S", dos(registration)]
        receipt["preconditions"] += [
            "Before target activation import aedebug_registration_argv only into this fresh%03d prefix; record import exit and Auto=0 readback" % cell,
            "CoreApplication.Run diagnostic source sets SEM_NOGPFAULTERRORBOX and restores previous error mode if Run returns",
            "Observe real target-handle exit/code or preserve unknown at180s; do not launch debugger manually",
        ]
        receipt["limitations"] += [
            "Exact Wine source defaults to winedbg when Debugger is absent; Auto=0 alone can prompt, so scoped no-GPFault error mode bypasses debugger/dialog",
            "Unhandled-filter entry is actual unhandled dispatch, not proof the application filter will terminate; target exit is separate evidence",
            "First32 exception records retain code/flags/image-relative address, typed scalar parameters and redacted/image-relative pointer parameters",
            "C++ object layout is not guessed; HRESULT unknown unless separately observed RoOriginateError/LanguageException, same-thread origin candidates are not definitive exception decoding",
            "Last50 retained admitted relay calls are bound at exception entry; no private exception object, strings or absolute addresses",
            "Fresh private prefix registry change is reversible by removing%03d prefix; sealed predecessors and existing prefixes untouched" % cell,
        ]
    if cell in (18, 19, 20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell018 corrected nineteen-slot native lifetime ABI and unchanged exception observation"
        receipt["limitations"] = [item for item in receipt["limitations"]
                                 if not item.startswith(("Reserved undocumented slot", "122 typed",
                                                         "IStaticLifetime is Microsoft's"))]
        receipt["lifetime_abi"] = {
            "facts": str(abi_facts), "facts_sha256": abi_digest,
            "observed_file_version": "10.0.26100.9711",
            "observed_binary_sha256": "000736bd54e9376e78ebe8eef87832606a058e0c2a1df290642177e7858b81a0",
            "slots": 19, "add_callback_slot": 11, "remove_callback_slot": 12,
            "unknown_slots": [8, 9, 10, 13, 14, 15, 16, 17, 18],
        }
        receipt["limitations"] += [
            "Nineteen-slot factory ABI observed statically in twinapi.appcore10.0.26100.9711, not an eight-slot cppwinrt-only contract",
            "Slots6/7 return retained collection;11/12 own callbacks with AddRef/Release and64-bit tokens; unknown slots return logged E_NOTIMPL with exact-width cleared outputs",
            "Callback registration retains references but does not claim Windows apartment marshaling or invented event delivery",
            "Up to32 callbacks; exhaustion returns E_OUTOFMEMORY and zero token; remove absent token succeeds",
            "Headless fixture extended to exercise slot11/12 and callback-vptr preservation; compiled only, execution requires runtime owner",
        ]
        receipt["native_fixture_argv"][-1] = "--static-lifetime"
        receipt["native_fixture_status"] = "compiled headless map and nineteen-slot callback contract fixture, not executed"
    if cell in (19, 20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell019 diagnostic-only fail-fast HRESULT and restricted-error caller context"
        receipt["failfast_diagnostics"] = build["failfast_diagnostics"]
        receipt["limitations"] += [
            "Fail-fast logs actual HRESULT argument and image-relative return site before original RaiseFailFastException; target exit observed separately",
            "Collector error-context scope starts at Initialize entry and ends at CoreApplication.Run exit; process exit may end it without a Run return",
            "Last30 admitted relay and last30 owned COM events copied at fail-fast; no raw argument or callback/token output",
            "RoOriginate operations retain input HRESULT; Get/SetRestrictedErrorInfo retain unchanged actual E_NOTIMPL stub return, not an object HRESULT",
            "No restricted error objects, strings, stowed exception structures or private message text decoded",
            "Source caps32 fail-fast and512 other context calls; collector first32 fail-fast plus512 tail with explicit loss counters",
        ]
    if cell in (20, 21, 22, 23, 24, 25):
        receipt["scope"] = "cell020 diagnostic-only Run-scoped FIXME fingerprints and matching scalar relay returns"
        receipt["status_diagnostics"] = build["status_diagnostics"]
        receipt["limitations"] += [
            "XboxPcApp.exe:fixme+all is app-qualified by exact Wine debug parser; only Run-scoped function/channel fingerprints retained, arguments discarded",
            "Debug emission is process-lifetime; collector Run admission is narrower; no raw log is persisted",
            "Actual x64 relay returns matching low32 C0000002/D0000002 retain export and image-relative caller, not an inferred originating syscall",
            "Wine relay I encoding on x64 does not distinguish pointers from status returns; rows are matching bits, owned COM HRESULT rows are independently typed",
            "Norelay exports/syscalls/native-to-native bypasses are uncovered; no syscall-return completeness claim",
            "Source caps128 matching relay returns, collector128 tail/explicit overwrite; first128 FIXME records with explicit not-retained count",
            "019 disassembly proves incoming ECX forwarded before reuse; D0000002 is HRESULT_FROM_NT(STATUS_NOT_IMPLEMENTED), not demonstrated capture corruption",
            "The twinapi+9031 callsite is inside already-instrumented AddCallback; CoreApplicationView slots6-10/QI remain fully typed, unsupported QIs remain E_NOINTERFACE",
        ]
    if cell == 21:
        receipt["scope"] = "cell021 observation-backed packaged claims Site B with unchanged020 diagnostics"
        receipt["claims_site_b"] = build["claims_site_b"]
        receipt["generated_source_sha256"].update(build["claims_site_b"]["files"])
        receipt["limitations"] += [
            "Unchanged Whiny r6 generated artifact, SHA2924dd6c, adds only observed signed GamingApp self-token claim-plus-attributes success",
            "Existing genuine package identity and verified GamingApp family predicate unchanged; no context override or blanket success",
            "Host compiled checks establish scoped claim/attributes outputs, not actual021 argument values or generated branch selection",
            "Actual021 must separately establish target progress or next concrete failure; no game, UI or native parity acceptance",
        ]
    if cell == 22:
        receipt.pop("claims_site_b", None)
        receipt["scope"] = "cell022 unchanged r8 effective-token claims and sanitized genuine-context samples"
        receipt["claims_thread_token"] = build["claims_thread_token"]
        receipt["generated_source_sha256"].update(build["claims_thread_token"]["files"])
        receipt["limitations"] += [
            "Generated r8 artifact5acbb35e adds observed unpackaged token-6 C0000225 only; packaged token-6 remains unobserved/C0000002",
            "No token-6 to token-4 alias; genuine package predicate unchanged",
            "Claims telemetry samples both genuine context booleans before the generated call, not the actual selected branch",
            "Presence bits0-6 describe package name/size, app id/size, dynamic id, claim and attributes pointers without addresses or contents",
            "Handle category, presence bits, sampled context booleans and returned status only; source cap128 and collector128 tail with explicit loss",
        ]
    if cell in (23, 24, 25):
        receipt.pop("claims_thread_token", None)
        receipt["scope"] = "cell023 observation-backed packaged effective-token claims with unchanged022 telemetry"
        receipt["claims_packaged_thread"] = build["claims_packaged_thread"]
        receipt["generated_source_sha256"].update(build["claims_packaged_thread"]["files"])
        receipt["limitations"] = [item for item in receipt["limitations"]
                                 if not item.startswith("Generated r8 artifact")]
        receipt["limitations"] += [
            "Unchanged r9 artifact9978669c adds genuinely observed signed GamingApp token-6 claim-only/all-null and claim-plus-attributes success",
            "Genuine predicate and022 telemetry wrapper unchanged; no token alias or forced context",
            "Context samples remain distinct from selected-branch tracing; no raw pointer, claim or attributes contents retained",
            "Source128 and collector128 claims-context limits retained; actual lifecycle progress and target exit require independent observation",
        ]
    if cell in (24, 25):
        receipt["scope"] = "cell024 observed desktop and GamingApp OneCore transform query export"
        receipt["runtime_execution_hold"] = "User-directed screen stop; explicit user resume required before024 or any screen-affecting launch"
        receipt["preconditions"].insert(0, receipt["runtime_execution_hold"])
        receipt["onecore_transform"] = build["onecore_transform"]
        receipt["generated_source_sha256"].update(build["onecore_transform"]["files"])
        receipt["limitations"] += [
            "IsOneCoreTransformMode BOOL(void) returns false, matching two native calls in each observed desktop and signed GamingApp context",
            "No runtime OneCore enable path, true-mode emulation, win32u setter or broad API-set remapping added",
            "Other process modes including ShellExperienceHost are unobserved; this is not general OneCore transform support",
            "Existing API-set suffix-family mapping unchanged; exact missing user32 export alone is added",
        ]
    if cell == 25:
        receipt["scope"] = "cell%03d native-only CoreMessaging with genuine wait packets; static-qualified, runtime held" % requested_cell
        receipt["runtime_execution_hold"] = "User-directed screen stop; distinct explicit cell025 user resume required before any Wine/fixture/app launch"
        receipt["preconditions"][0] = receipt["runtime_execution_hold"]
        receipt["preconditions"].append(
            "Execution owner must verify and copy only native_coremessaging into this fresh%03d prefix, then read back exact SHA before activation; no proprietary input in Calimocho install" % requested_cell)
        receipt["coremessaging_prerequisites"] = build["coremessaging_prerequisites"]
        receipt["generated_source_sha256"].update(build["coremessaging_prerequisites"]["files"])
        receipt["native_coremessaging"] = {
            "path": str(native), "sha256": pins["sha256"], "size": pins["size"],
            "file_product_version": pins["file_product_version"],
            "destination": str(Path(receipt["prefix"]) / "drive_c/windows/system32/CoreMessaging.dll"),
            "override": "coremessaging=n", "provenance": pins["provenance"], "rights": pins["rights"],
            "status": "retained external local evaluation input; not copied or loaded"}
        receipt["native_coremessaging_import_qualification"] = native_closure
        environment = receipt["environment"]
        environment["WINEDLLOVERRIDES"] += ";coremessaging=n"
        receipt["server_start"]["environment"]["WINEDLLOVERRIDES"] = environment["WINEDLLOVERRIDES"]
        registry_path = Path(receipt["registry"])
        registry = json.loads(registry_path.read_text())
        entry = registry["engines"][0]
        entry["environment"]["WINEDLLOVERRIDES"] = environment["WINEDLLOVERRIDES"]
        entry["profile_assets"]["files"].append({
            "path": str(native), "sha256": pins["sha256"], "role": "local-only native CoreMessaging evaluation input"})
        from tools.freeze_launcher_runtime import checked_assets
        checked_assets(entry)
        registry_path.write_text(json.dumps(registry, indent=2) + "\n")
        receipt["registry_sha256"] = sha256(registry_path)
        receipt["limitations"] += [
            "Three server wait APIs implement one-shot IOCP delivery; unsupported target classes fail explicitly, host checks are not native parity",
            "Five typed unsupported ntdll exports clear outputs and return C0000002; run-scoped fixed-name hit cap128 plus one source-limit marker",
            "Observed native AMD64 ucrtbase noexcept export forwards exactly to ntdll.__C_specific_handler; no guessed handler semantics",
            "All mandatory public imports and recursive forwarders statically resolve; nineteen delay descriptors and CoreUICreate initialization remain unqualified",
            "Native CoreMessaging same file/product version as original XAML is compatible-candidate evidence, not fresh signature or host-build-chain proof",
            "No025 native execution, UI/Bridge acceptance or general screen/VM resume; consumed024 decision is not025 authorization",
        ]
    if requested_cell in (26, 27, 28, 29):
        receipt.update(cell026)
        receipt["runtime_execution_hold"] = "Execution owner must independently reconcile retained owner decision for once-only%03d; source lane does not grant runtime authority" % requested_cell
        receipt["preconditions"][0] = receipt["runtime_execution_hold"]
        receipt["limitations"] += [
            "Combase86-88 are explicit unsupported ordinal exports, not inferred native names or dispatcher implementations",
            "All other combase ordinals preserved; three colliding named exports moved to356-358",
            "Private user32 dispatcher ordinals and unhosted API-set remain unsupported; actual first reached call is unobserved",
        ]
    if requested_cell in (27, 28, 29):
        add_registrar_handoff(root, receipt, requested_cell)
    if requested_cell >= 29:
        add_headless_setup(receipt)
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cell", type=int, choices=(13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29), default=13)
    args = parser.parse_args()
    if args.compile_only:
        print(json.dumps(compile_observer(args.root, args.resume), indent=2))
    else:
        if not args.producer_commit:
            parser.error("--producer-commit is required when freezing")
        print(prepare(args.root, args.producer_commit, args.cell))
