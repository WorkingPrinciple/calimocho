"""Build the pinned official MoltenVK release in an isolated owned directory."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / "versions.json").read_text())["moltenvk_source"]
COMMIT = PIN["commit"]
URL = PIN["repository"]
DEPENDENCIES = PIN["dependencies"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output, resume=False):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "build"):
        raise ValueError("Build must be in this worktree's build directory")
    output.mkdir(parents=True, exist_ok=resume)
    previous = json.loads((output / "receipt.json").read_text()) if resume else None
    started = (previous["started_epoch"] if previous and "started_epoch" in previous
               else (output / "MoltenVK-init.log").stat().st_mtime if previous
               else time.time())
    receipt = {"source_url": URL, "commit": COMMIT, "tag": "v1.4.2",
               "licence": PIN["license"], "architecture": "x86_64",
               "budget_seconds": 2700, "steps": [], "status": "incomplete",
               "dependencies": DEPENDENCIES, "runtime_executed": False}
    receipt["started_epoch"] = started
    if previous:
        if previous["commit"] != COMMIT or previous["status"] != "failed":
            raise ValueError("Resume requires failed receipt for exact source pin")
        receipt["previous_attempt"] = previous
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_"))}

    def save():
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def run(name, args, cwd=output):
        remaining = 2700 - (time.time() - started)
        if remaining <= 0:
            raise TimeoutError("MoltenVK 45-minute budget exhausted")
        log = output / f"{'resume-' if resume else ''}{name}.log"
        step = {"name": name, "command": list(map(str, args)), "cwd": str(cwd)}
        receipt["steps"].append(step)
        save()
        with log.open("w") as stream:
            process = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                step.update(status="timeout", log_sha256=sha256(log))
                save()
                raise
        step.update(exit_code=code, log_sha256=sha256(log))
        save()
        if code:
            raise RuntimeError(f"{name} failed ({code}); see {log}")

    def checkout(name, repo, commit, directory):
        if resume:
            actual = subprocess.check_output(
                ["git", "-C", str(directory), "rev-parse", "HEAD"],
                text=True, timeout=10).strip()
            if actual != commit:
                raise ValueError(f"{name} resume source identity mismatch")
            if subprocess.check_output(
                    ["git", "-C", str(directory), "status", "--porcelain", "--untracked-files=no"],
                    text=True, timeout=10):
                raise ValueError(f"{name} resume source has tracked changes")
            return
        directory.mkdir(parents=True, exist_ok=False)
        run(f"{name}-init", ["git", "init", "--quiet", str(directory)])
        run(f"{name}-remote", ["git", "-C", str(directory), "remote", "add", "origin", repo])
        run(f"{name}-fetch", ["git", "-C", str(directory), "fetch", "--depth=1", "origin", commit])
        run(f"{name}-checkout", ["git", "-C", str(directory), "checkout", "--detach", "FETCH_HEAD"])
        actual = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"],
                                         text=True, timeout=10).strip()
        if actual != commit:
            raise ValueError(f"{name} source identity mismatch")

    save()
    try:
        source = output / "source"
        checkout("MoltenVK", URL, COMMIT, source)
        receipt["licence_sha256"] = sha256(source / "LICENSE")
        for name, (repo, commit) in DEPENDENCIES.items():
            if (source / "ExternalRevisions" / f"{name}_repo_revision").read_text().strip() != commit:
                raise ValueError(f"{name} differs from official ExternalRevisions")
            directory = source / "External" / name
            if name == "SPIRV-Headers":
                directory = source / "External/SPIRV-Tools/external/spirv-headers"
            checkout(name, f"https://github.com/{repo}.git", commit, directory)
        config = output / "owned.xcconfig"
        config.write_text("ARCHS = x86_64\nONLY_ACTIVE_ARCH = NO\n"
                          "CODE_SIGNING_ALLOWED = NO\nCODE_SIGNING_REQUIRED = NO\n")
        env["XCODE_XCCONFIG_FILE"] = str(config)
        env["CMAKE_BUILD_PARALLEL_LEVEL"] = "4"
        # Upstream invokes xcodebuild by name; constrain all nested invocations too.
        bin_dir = output / "bin"
        bin_dir.mkdir(exist_ok=resume)
        wrapper = bin_dir / "xcodebuild"
        wrapper.write_text(
            '#!/bin/bash\nset -euo pipefail\n'
            'for arg in "$@"; do\n'
            '  if [[ "$arg" == "-create-xcframework" ]]; then\n'
            '    exec /usr/bin/xcodebuild "$@"\n'
            '  fi\n'
            'done\nexec /usr/bin/xcodebuild -jobs 4 "$@"\n')
        wrapper.chmod(0o755)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        receipt["build_config_sha256"] = sha256(config)
        receipt["wrapper_sha256"] = sha256(wrapper)
        run("dependencies", ["/bin/bash", "./fetchDependencies", "--macos", "--keep-cache"], source)
        run("moltenvk", ["xcodebuild", "build", "-quiet", "-project", "MoltenVKPackaging.xcodeproj",
                        "-scheme", "MoltenVK Package (macOS only)", "-configuration", "Release",
                        "-destination", "generic/platform=macOS",
                        "-derivedDataPath", str(output / "derived")], source)
        library = source / "Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
        run("architecture", ["/usr/bin/lipo", "-archs", str(library)])
        archs = (output / f"{'resume-' if resume else ''}architecture.log").read_text().strip()
        if archs != "x86_64":
            raise ValueError(f"Expected x86_64 only, observed {archs}")
        run("linkage", ["/usr/bin/otool", "-L", str(library)])
        receipt.update(status="source-built-not-runtime-qualified",
                       library=str(library), library_sha256=sha256(library))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        receipt.update(status="failed", error=str(error))
        save()
        raise
    save()
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.resume), indent=2))
