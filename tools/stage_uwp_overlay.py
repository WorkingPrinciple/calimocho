"""Stage the built009 sibling and v7 observer without starting any process."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.build_gameinput_overlay import compile_flags
from tools.build_gameinput_overlay import WINE
from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import BASE, REPO
from tools.probe_wine_source import sha256
from tools.stage_framework_overlay import rebase


def stage(root, resume=False):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or root == BASE:
        raise ValueError("Require a new owned009 install")
    if any(root.glob("*FROZEN*")):
        raise ValueError("Refuse to restage a frozen009 sibling")
    previous_stage = None
    if (root / "install").exists():
        if not resume:
            raise ValueError("Restaging requires explicit resume of an unfrozen candidate")
        previous_stage = json.loads((root / "staging-receipt.json").read_text())
        if inventory(root / "install") != previous_stage["files"]:
            raise ValueError("Existing009 candidate differs from its stage receipt")
    build = json.loads((root / "build-receipt.json").read_text())
    if build["status"] != "built-not-staged-not-executed":
        raise ValueError("Require a completed source build")
    for relative, digest in build["source_inputs"].items():
        if sha256(REPO / relative) != digest:
            raise ValueError("Source changed after build: " + relative)
    for relative, digest in build["built_files"].items():
        if sha256(root / relative) != digest:
            raise ValueError("Built artifact changed: " + relative)
    frozen = json.loads((BASE / "cell008-receipt.json").read_text())
    before = inventory(BASE / "install")
    if before != json.loads(Path(frozen["inventory"]).read_text())["files"]:
        raise ValueError("Frozen008 deployment changed")
    modules = {
        "bin/wineserver": "build/server/wineserver",
        "lib/wine/x86_64-unix/ntdll.so": "build/dlls/ntdll/ntdll.so",
        "lib/wine/x86_64-windows/ntdll.dll": "build/dlls/ntdll/x86_64-windows/ntdll.dll",
        "lib/wine/x86_64-windows/twinapi.appcore.dll": "build/dlls/twinapi.appcore/x86_64-windows/twinapi.appcore.dll",
        "lib/wine/x86_64-windows/windows.ui.dll": "build/dlls/windows.ui/x86_64-windows/windows.ui.dll",
        "lib/wine/x86_64-windows/windows.system.launcher.dll": "windows.system.launcher.dll",
    }
    if "activation_wait_diagnostics" in build:
        modules["lib/wine/x86_64-windows/combase.dll"] = "build/dlls/combase/x86_64-windows/combase.dll"
    if "handle_provenance" in build:
        modules["lib/wine/x86_64-windows/rpcrt4.dll"] = "build/dlls/rpcrt4/x86_64-windows/rpcrt4.dll"
    if "onecore_transform" in build:
        modules["lib/wine/x86_64-windows/user32.dll"] = "build/dlls/user32/x86_64-windows/user32.dll"
    for relative in ("build/server/wineserver", "build/dlls/ntdll/ntdll.so"):
        result = subprocess.run(["/usr/bin/otool", "-L", str(root / relative)],
                                capture_output=True, text=True, check=True)
        if "/usr/local/" in result.stdout or "/opt/homebrew/" in result.stdout:
            raise ValueError("Nonportable new Mach-O linkage")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing compiler")
    attempt = 1
    while (root / ("staging-attempt-%02d" % attempt)).exists():
        attempt += 1
    retained = root / ("staging-attempt-%02d" % attempt)
    retained.mkdir()
    for name in ("package-activation-probe-v7.exe", "helper-v7-build.log",
                 "uwp-activation-probe.exe", "uwp-probe-build.log"):
        previous = root / name
        if previous.exists():
            previous.rename(retained / name)
    helper = root / "package-activation-probe-v7.exe"
    command = [compiler, "-I" + str(root / "source/include"),
               *compile_flags(root / "build/include"), "-D_UCRT", "-municode",
               str(REPO / "tests/package_activation_probe.c")]
    if "call_diagnostics" in build:
        command.append("-DCALIMOCHO_CALL_DIAGNOSTICS")
    if "activation_wait_diagnostics" in build:
        command.append("-DCALIMOCHO_ACTIVATION_WAIT_DIAGNOSTICS")
    if "handle_provenance" in build:
        command.append("-DCALIMOCHO_HANDLE_PROVENANCE")
    if "exception_diagnostics" in build:
        command.append("-DCALIMOCHO_EXCEPTION_DIAGNOSTICS")
    if "status_diagnostics" in build:
        command.append("-DCALIMOCHO_STATUS_DIAGNOSTICS")
    command += [str(root / "build/dlls" / module / "x86_64-windows" / ("lib" + module + ".a"))
                for module in ("ntdll", "kernelbase", "combase")]
    # kernelbase was unchanged, so use the frozen framework build's import library.
    command = [str(BASE.parent / "package-framework-01/build/dlls/kernelbase/x86_64-windows/libkernelbase.a")
               if arg.endswith("/kernelbase/x86_64-windows/libkernelbase.a") else arg for arg in command]
    result = subprocess.run(command + ["-o", str(helper)], capture_output=True, text=True, timeout=60)
    (root / "helper-v7-build.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Helper v7 compilation failed")
    helper_exit = result.returncode
    probe = root / "uwp-activation-probe.exe"
    probe_command = [compiler, "-I" + str(root / "source/include"),
                     "-I" + str(root / "build/dlls/twinapi.appcore"),
                     *compile_flags(root / "build/include"), "-D_UCRT",
                     str(REPO / "tests/uwp_activation_probe.c")]
    probe_command += [str(root / "build/dlls" / module / "x86_64-windows" / ("lib" + module + ".a"))
                      for module in ("ntdll", "combase")]
    probe_command.append(str(WINE / "build/libs/uuid/x86_64-windows/libuuid.a"))
    result = subprocess.run(probe_command + ["-o", str(probe)], capture_output=True, text=True, timeout=60)
    (root / "uwp-probe-build.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("UWP HWND fixture compilation failed")
    install = root / "install"
    if previous_stage is not None:
        install.rename(retained / "previous-install")
        for name in ("staging-receipt.json", "uwp.registry.local.UNQUALIFIED.json"):
            (root / name).rename(retained / name)
    shutil.copytree(BASE / "install", install, symlinks=True)
    for target, relative in modules.items():
        shutil.copy2(root / relative, install / target)
    expected = dict(before, **{target: {"sha256": sha256(root / relative)}
                               for target, relative in modules.items()})
    if inventory(install) != expected or inventory(BASE / "install") != before:
        raise ValueError("Unexpected009 inventory difference or008 mutation")
    registry = json.loads(Path(frozen["registry"]).read_text())
    entry = rebase(registry["engines"][0], BASE / "install", install)
    entry.update(name="calimocho-wine11.20-uwp-protocol-window-diagnostic",
                 install_path=str(install), wineserver_sha256=sha256(install / "bin/wineserver"),
                 integrity={"status": "candidate-only"},
                 smoke_test={"status": "not-run", "scope": "009 source/build only"})
    known = {item.get("path") for item in entry["profile_assets"]["files"]}
    for target in modules:
        path = install / target
        if str(path) not in known:
            entry["profile_assets"]["files"].append({"path": str(path), "sha256": sha256(path)})
    registry["engines"] = [entry]
    path = root / "uwp.registry.local.UNQUALIFIED.json"
    path.write_text(json.dumps(registry, indent=2) + "\n")
    receipt = {
        "status": "staged-not-runtime-qualified", "runtime_executed": False,
        "registry": str(path), "registry_sha256": sha256(path),
        "build_receipt_sha256": sha256(root / "build-receipt.json"),
        "files": expected, "changed_files": list(modules),
        "helper": str(helper), "helper_sha256": sha256(helper),
        "helper_source_sha256": sha256(REPO / "tests/package_activation_probe.c"),
        "helper_command": command + ["-o", str(helper)], "helper_exit": helper_exit,
        "probe": str(probe), "probe_sha256": sha256(probe),
        "probe_source_sha256": sha256(REPO / "tests/uwp_activation_probe.c"),
        "probe_command": probe_command + ["-o", str(probe)], "probe_exit": result.returncode,
    }
    record = root / "staging-receipt.json"
    record.write_text(json.dumps(receipt, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(stage(args.root, args.resume))
