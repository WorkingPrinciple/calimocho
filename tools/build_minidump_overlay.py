"""Build an isolated minidump API-set forwarder; never run or admit Wine."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

if __package__:
    from .probe_wine_source import sha256
else:
    from probe_wine_source import sha256


REPO = Path(__file__).resolve().parents[1]
MODULE = "api-ms-win-core-debug-minidump-l1-1-0"
SOURCE = REPO / "patches/wine/files" / MODULE
BASE = REPO / "build/winehq-11.20/metal-port-11b-private-binding-01"
REGISTRY = BASE / (
    "calimocho-wine11.20-gptk4b3-tls-vulkan-private.registry.local."
    "PERF-FROZEN-170ca4ad.json"
)
REGISTRY_SHA = "170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609"
WINEBUILD = REPO / "build/winehq-11.20/metal-port-11/build/tools/winebuild/winebuild"


def inventory(root):
    return {str(p.relative_to(root)): {"link": str(p.readlink())} if p.is_symlink()
            else {"sha256": sha256(p)}
            for p in sorted(root.rglob("*")) if p.is_file() or p.is_symlink()}


def build(output):
    output = output.resolve()
    if not output.is_relative_to(REPO / "build") or output.exists():
        raise ValueError("Require a new owned build output")
    if sha256(REGISTRY) != REGISTRY_SHA:
        raise ValueError("Frozen performance registry differs from pin")
    engine = json.loads(REGISTRY.read_text())["engines"][0]
    before = inventory(BASE / "install")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "status": "incomplete", "base_registry": str(REGISTRY),
        "base_registry_sha256": REGISTRY_SHA,
        "source": str(SOURCE), "source_files": inventory(SOURCE),
        "winebuild": str(WINEBUILD), "winebuild_sha256": sha256(WINEBUILD),
        "base_environment": engine["environment"],
        "commands": [], "overlay": [],
        "runtime_executed": False, "qualified": False,
    }
    receipt_path = output / "receipt.json"

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    save()
    for arch in ("x86_64", "i386"):
        artifact = output / arch / (MODULE + ".dll")
        artifact.parent.mkdir()
        command = [str(WINEBUILD), "--dll", "--data-only",
                   "--target=" + arch + "-windows",
                   "-E", str(SOURCE / (MODULE + ".spec")), "-o", str(artifact)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        log = output / (arch + "-build.log")
        log.write_text(result.stdout + result.stderr)
        receipt["commands"].append({
            "command": command, "exit_code": result.returncode,
            "log": str(log), "log_sha256": sha256(log),
        })
        save()
        if result.returncode or not artifact.is_file() or not artifact.stat().st_size:
            raise RuntimeError(f"Forwarder build failed; see {log}")
        receipt["overlay"].append({
            "path": f"lib/wine/{arch}-windows/{MODULE}.dll",
            "source": str(artifact), "sha256": sha256(artifact),
        })
    install = output / "install"
    shutil.copytree(BASE / "install", install, symlinks=True)
    for entry in receipt["overlay"]:
        destination = install / entry["path"]
        if destination.exists():
            raise ValueError(f"Refusing to replace existing module: {destination}")
        shutil.copy2(entry["source"], destination)
    after = inventory(install)
    expected = dict(before)
    expected.update({entry["path"]: {"sha256": entry["sha256"]}
                     for entry in receipt["overlay"]})
    if after != expected or inventory(BASE / "install") != before:
        raise RuntimeError("Unexpected install difference or frozen-base mutation")
    receipt["base_unchanged"] = True
    receipt["only_two_forwarders_added"] = True
    receipt["status"] = "built-not-runtime-qualified"
    save()
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(build(parser.parse_args().output))
