"""Freeze an already built, isolated REQ-108 opcode diagnostic overlay."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from instrument_fh6 import instrument


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def freeze(output, baseline):
    output = output.resolve()
    baseline = baseline.resolve()
    registry = json.loads(baseline.read_text())
    if digest(baseline) != "170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609":
        raise ValueError("Require the exact authorized frozen 11b baseline")
    engine = registry["engines"][0]
    old_install = Path(engine["install_path"])
    install = output / "install"
    if not install.is_relative_to(Path(__file__).resolve().parents[1] / "build"):
        raise ValueError("Candidate must be inside this worktree's build directory")
    source = output / "source/dlls/ntdll/unix/signal_x86_64.c"
    original_source = old_install.parents[1] / "metal-port-10-03/winehq-source/dlls/ntdll/unix/signal_x86_64.c"
    if source.read_text() != instrument(original_source.read_text()):
        raise ValueError("Unexpected diagnostic source changes")
    relative = Path("lib/wine/x86_64-unix/ntdll.so")
    library = install / relative
    built = output / "build/dlls/ntdll/ntdll.so"
    loads = subprocess.check_output(["otool", "-L", str(built)], text=True)
    if "/usr/local/" in loads:
        raise ValueError("Unexpected /usr/local dependency")
    shutil.copy2(built, library)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", "--options", "runtime", str(library)],
        check=True,
    )
    subprocess.run(["codesign", "--verify", "--strict", str(library)], check=True)
    differences = []
    for path in old_install.rglob("*"):
        target = install / path.relative_to(old_install)
        if path.is_symlink():
            if path.readlink() != target.readlink():
                raise ValueError(f"Changed symlink: {path}")
        elif path.is_file() and digest(path) != digest(target):
            differences.append(str(path.relative_to(old_install)))
    if differences != [str(relative)]:
        raise ValueError(f"Unexpected runtime changes: {differences}")

    receipt = {
        "requirement": "REQ-108",
        "authorization": "COR-148",
        "kind": "diagnostic-only-not-a-fix",
        "baseline_registry": str(baseline),
        "baseline_registry_sha256": digest(baseline),
        "baseline_ntdll_sha256": digest(old_install / relative),
        "source": str(source),
        "source_sha256": digest(source),
        "source_before_sha256": digest(original_source),
        "transformer": str(Path(__file__).with_name("instrument_fh6.py")),
        "transformer_sha256": digest(Path(__file__).with_name("instrument_fh6.py")),
        "build_log_sha256": digest(output / "compile.log"),
        "incremental_build_log_sha256": digest(output / "compile-warning-fix.log"),
        "configure_log_sha256": digest(output / "configure.log"),
        "library": str(library),
        "library_sha256": digest(library),
        "runtime_differences": differences,
        "undeclared_differences": [],
        "runtime_executed": False,
        "game_qualified": False,
        "diagnostics": "16 fault-time bytes via permission-checked reader; existing seh and syscall traces",
        "load_commands": loads,
    }
    receipt_path = output / "receipt-v2.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    engine["baseline_runtime_evidence"] = {
        key: engine.pop(key)
        for key in ("smoke_test", "graphics_tests", "tls_positive_test", "tls_negative_test")
        if key in engine
    }

    def relocate(value):
        if isinstance(value, str):
            return value.replace(str(old_install), str(install))
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        return value

    for key in ("install_path", "wine", "wineserver", "environment", "dependencies", "profile_assets", "gptk_symlink_map"):
        if key in engine:
            engine[key] = relocate(engine[key])
    for asset in engine["profile_assets"]["files"]:
        if asset["path"] == str(library):
            asset["sha256"] = digest(library)
    engine["name"] = "calimocho-wine11.20-fh6-opcode-diag-01"
    engine["version"] += " + COR-148 opcode diagnostic (not a fix)"
    engine["environment"]["WINEDEBUG"] = "-all,+seh,+loaddll,+syscall"
    engine["source_patches"].append({
        "path": str(Path(__file__).with_name("instrument_fh6.py")),
        "sha256": digest(Path(__file__).with_name("instrument_fh6.py")),
        "role": "Read-only fault opcode logging; no exception or syscall behavior edits",
    })
    engine["baseline_build_evidence"] = engine.pop("build_evidence")
    engine["build_evidence"] = {"path": str(receipt_path), "sha256": digest(receipt_path)}
    engine["integrity"] = {
        "status": "unchanged",
        "manifest_path": str(receipt_path),
        "manifest_sha256": digest(receipt_path),
        "scope": "Only declared ntdll.so diagnostic overlay differs from frozen 11b; zero undeclared differences",
    }
    engine["smoke_test"] = {"status": "not-run", "scope": "diagnostic candidate, not baseline qualification"}
    target = output / "fh6-opcode.registry.FROZEN-v2.json"
    if target.exists():
        raise ValueError("Refuse to overwrite an existing frozen registry")
    target.write_text(json.dumps(registry, indent=2) + "\n")
    target.chmod(0o444)
    print(json.dumps({"registry": str(target), "sha256": digest(target), "receipt": str(receipt_path)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    args = parser.parse_args()
    freeze(args.output, args.baseline)
