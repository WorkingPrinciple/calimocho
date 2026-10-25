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


def prepare(root, producer):
    root = Path(root).resolve(strict=True)
    record = json.loads((root / "state-observer-build.json").read_text())
    if record["exit_code"] or record["runtime_executed"]:
        raise ValueError("Require compiled unexecuted state observer")
    if sha256(Path(record["output"])) != record["output_sha256"] or sha256(Path(record["source"])) != record["source_sha256"]:
        raise ValueError("State observer source or binary changed")
    path = freeze(root, producer, cell=13, predecessor=PREVIOUS,
                  predecessor_sha256="d28d3873654eaf4c563db8cf64ef4b2368176729befb6c72eec847b128a9c39f",
                  extra_sources=SOURCES)
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
    receipt["scope"] = "cell013 bounded actual AppL progress, thread and window discriminator"
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
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.compile_only:
        print(json.dumps(compile_observer(args.root, args.resume), indent=2))
    else:
        if not args.producer_commit:
            parser.error("--producer-commit is required when freezing")
        print(prepare(args.root, args.producer_commit))
