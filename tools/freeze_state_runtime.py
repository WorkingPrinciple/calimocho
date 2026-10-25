"""Build a target-only bounded state observer and freeze a changed013 sibling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.build_gameinput_overlay import WINE, compile_flags
from tools.build_uwp_overlay import REPO
from tools.freeze_static_lifetime_runtime import freeze
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
    root = Path(root).resolve(strict=True)
    record = json.loads((root / "state-observer-build.json").read_text())
    if record["exit_code"] or record["runtime_executed"]:
        raise ValueError("Require compiled unexecuted state observer")
    if sha256(Path(record["output"])) != record["output_sha256"] or sha256(Path(record["source"])) != record["source_sha256"]:
        raise ValueError("State observer source or binary changed")
    if cell not in (13, 14, 15, 16, 17):
        raise ValueError("Unsupported diagnostic cell")
    extra = SOURCES
    previous, digest = PREVIOUS, "d28d3873654eaf4c563db8cf64ef4b2368176729befb6c72eec847b128a9c39f"
    if cell in (14, 15, 16, 17):
        previous = REPO / "build/winehq-11.20/package-uwp-state-01/cell013-receipt.json"
        digest = "a0cf124b6c1040de0cbe180a70c9969612314e95511281cc769d58ee752e0285"
        extra += ("tools/port_call_diagnostics.py", "patches/wine/files/package_call_diagnostics.h",
                  "patches/wine/files/package_relay_diagnostics.h", "patches/wine/files/package_wait_diagnostics.h")
        build = json.loads((root / "build-receipt.json").read_text())
        if "call_diagnostics" not in build:
            raise ValueError("Cell014 requires actual diagnostic source port")
        for relative, value in build["call_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated diagnostic source changed")
        for header, value in build["call_diagnostics"]["headers"].items():
            if sha256(Path(header)) != value:
                raise ValueError("Diagnostic ABI header changed")
    if cell in (15, 16, 17):
        previous = REPO / "build/winehq-11.20/package-uwp-calltrace-01/cell014-receipt.json"
        digest = "30b6d6514d58ec6ee188768345673abea86d11d5a0254fce38db9f7484646b48"
        from tools.port_activation_wait_diagnostics import SOURCES as ACTIVATION_SOURCES
        extra += ACTIVATION_SOURCES
        if "activation_wait_diagnostics" not in build:
            raise ValueError("Cell015 requires actual activation/wait source port")
        for relative, value in build["activation_wait_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated activation/wait source changed")
    if cell in (16, 17):
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
    if cell == 17:
        previous = REPO / "build/winehq-11.20/package-uwp-handle-provenance-01/cell016-receipt.json"
        digest = "b55779b754cacf0b091dac907c381a9dcf3133acdbe8169b8f18a226705d38d5"
        from tools.port_exception_diagnostics import SOURCES as EXCEPTION_SOURCES
        extra += EXCEPTION_SOURCES
        if "exception_diagnostics" not in build:
            raise ValueError("Cell017 requires actual exception source port")
        for relative, value in build["exception_diagnostics"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Generated exception source changed")
    path = freeze(root, producer, cell=cell, predecessor=previous,
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
    if cell in (14, 15, 16, 17):
        receipt["call_diagnostics"] = build["call_diagnostics"]
        receipt["scope"] = "cell014 diagnostic-only complete owned COM vtables, sanitized native-XAML relay and actual wait pairs"
        receipt["preconditions"] += [
            "Fresh%03d once only; all changed modules and compiled diagnostic helper must match this receipt" % cell,
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
    if cell in (15, 16, 17):
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
    if cell in (16, 17):
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
    if cell == 17:
        receipt["scope"] = "cell017 real unhandled-filter exception, no debugger dialog and actual target exit"
        receipt["exception_diagnostics"] = build["exception_diagnostics"]
        registration = root / "aedebug-CELL017-FROZEN.reg"
        registration.write_bytes((
            "Windows Registry Editor Version 5.00\r\n\r\n"
            "[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AeDebug]\r\n"
            '"Auto"="0"\r\n').encode("utf-16"))
        from tools.prepare_verified_activation import dos
        receipt["aedebug_registration"] = str(registration)
        receipt["aedebug_registration_sha256"] = sha256(registration)
        receipt["aedebug_registration_argv"] = receipt["activation_argv"][:3] + ["regedit", "/S", dos(registration)]
        receipt["preconditions"] += [
            "Before target activation import aedebug_registration_argv only into this fresh017 prefix; record import exit and Auto=0 readback",
            "CoreApplication.Run diagnostic source sets SEM_NOGPFAULTERRORBOX and restores previous error mode if Run returns",
            "Observe real target-handle exit/code or preserve unknown at180s; do not launch debugger manually",
        ]
        receipt["limitations"] += [
            "Exact Wine source defaults to winedbg when Debugger is absent; Auto=0 alone can prompt, so scoped no-GPFault error mode bypasses debugger/dialog",
            "Unhandled-filter entry is actual unhandled dispatch, not proof the application filter will terminate; target exit is separate evidence",
            "First32 exception records retain code/flags/image-relative address, typed scalar parameters and redacted/image-relative pointer parameters",
            "C++ object layout is not guessed; HRESULT unknown unless separately observed RoOriginateError/LanguageException, same-thread origin candidates are not definitive exception decoding",
            "Last50 retained admitted relay calls are bound at exception entry; no private exception object, strings or absolute addresses",
            "Fresh private prefix registry change is reversible by removing017 prefix; sealed012-016 and existing prefixes untouched",
        ]
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cell", type=int, choices=(13, 14, 15, 16, 17), default=13)
    args = parser.parse_args()
    if args.compile_only:
        print(json.dumps(compile_observer(args.root, args.resume), indent=2))
    else:
        if not args.producer_commit:
            parser.error("--producer-commit is required when freezing")
        print(prepare(args.root, args.producer_commit, args.cell))
