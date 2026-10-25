"""Compile the owned Launcher fixture/helper without executing a native process."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.build_gameinput_overlay import compile_flags, WINE
from tools.build_launcher_overlay import BASE, REPO
from tools.probe_wine_source import sha256


def build(root, helper_only=False, resume=False):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build"):
        raise ValueError("Require owned candidate build")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing compiler")
    flags = [compiler, "-I" + str(root / "source/include"),
             *compile_flags(root / "include"), "-D_UCRT"]
    libraries = [str(BASE / "build/dlls" / module / "x86_64-windows" / ("lib" + module + ".a"))
                 for module in ("ntdll", "kernelbase", "combase")]
    sources = (("launcher-probe.exe", "tests/launcher_probe.c", []),
               ("package-activation-probe-v6.exe", "tests/package_activation_probe.c", ["-municode"]))
    receipt = {"runtime_executed": False, "commands": []}
    if resume:
        if any(root.glob("*FROZEN*")):
            raise ValueError("Refuse to rebuild fixtures in a frozen candidate")
        attempt = 2
        while (root / ("fixture-attempt-%02d" % attempt)).exists():
            attempt += 1
        retained = root / ("fixture-attempt-%02d" % attempt)
        retained.mkdir()
        for name in [name for name, _, _ in sources if not helper_only or name != "launcher-probe.exe"]:
            for path in (root / name, root / (name + ".build.log")):
                if path.exists():
                    path.rename(retained / path.name)
        record = root / "fixture-build-receipt.json"
        if record.exists():
            shutil.copy2(record, retained / record.name)
    for name, relative, extra in sources:
        if helper_only and name == "launcher-probe.exe":
            continue
        source = REPO / relative
        target = root / name
        if target.exists():
            raise ValueError("Refuse to overwrite built fixture")
        command = flags + extra + [str(source), *libraries, "-o", str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        log = root / (name + ".build.log")
        if log.exists():
            attempt = 1
            while log.with_suffix(".failed-%02d.log" % attempt).exists():
                attempt += 1
            shutil.copy2(log, log.with_suffix(".failed-%02d.log" % attempt))
        log.write_text(result.stdout + result.stderr)
        receipt["commands"].append({"argv": command, "exit_code": result.returncode,
                                    "source_sha256": sha256(source), "log_sha256": sha256(log)})
        (root / "fixture-build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError("Fixture compile failed: " + str(log))
        receipt[name] = sha256(target)
    (root / "fixture-build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--helper-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    build(args.root, args.helper_only, args.resume)
