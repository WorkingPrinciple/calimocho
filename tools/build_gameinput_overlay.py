"""Build a no-device GameInput DLL on a NEW immutable-payload 11d sibling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from tools.build_minidump_overlay import inventory
from tools.probe_wine_source import sha256

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/winehq-11.20/metal-port-11d-ags54-02"
REGISTRY = BASE / "ags54-minidump.registry.local.RUNTIME-FROZEN.json"
REGISTRY_SHA = "dcb8489851cafde7ffc9333de3d61a33c61e622b1e4b6a3262016c96ad42b7c7"
WINE = REPO / "build/winehq-11.20/metal-port-11"
SOURCE = REPO / "patches/wine/files/gameinput"
IDL_SHA = "dc2f7e6d20f40eddbffb9e2a899443ec73ed5d884763672a84b1609ae7bd5f1e"


def compile_flags(include):
    return ["-I" + str(include), "-I" + str(WINE / "build/include"),
            "-I" + str(WINE / "source/include"), "-I" + str(WINE / "source/include/msvcrt"),
            "-D__WINE_PE_BUILD", "-D__WINESRC__", "-Wall", "-Wextra",
            "-Wno-unused-parameter", "-Werror", "-O2"]


def build(output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(REPO / "build"):
        raise ValueError("Require a new owned build directory")
    if sha256(REGISTRY) != REGISTRY_SHA:
        raise ValueError("Frozen 11d registry changed")
    if sha256(WINE / "source/include/gameinput.idl") != IDL_SHA:
        raise ValueError("Versioned GameInput ABI source changed")
    before = inventory(BASE / "install")
    if before != json.loads((BASE / "receipt.json").read_text())["installed_files"]:
        raise ValueError("Frozen 11d inventory differs from producer receipt")
    output.mkdir(parents=True)
    include = output / "include"
    include.mkdir()
    shutil.copytree(SOURCE, output / "source")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require the existing MinGW compiler")
    obj = output / "gameinput.o"
    artifact = output / "gameinput.dll"
    libraries = [
        WINE / "build/libs/winecrt0/x86_64-windows/libwinecrt0.a",
        WINE / "build/libs/compiler-rt/x86_64-windows/libcompiler-rt.a",
        WINE / "build/dlls/ucrtbase/x86_64-windows/libucrtbase.a",
        WINE / "build/dlls/kernel32/x86_64-windows/libkernel32.a",
        WINE / "build/dlls/ntdll/x86_64-windows/libntdll.a",
    ]
    receipt = {
        "status": "incomplete", "runtime_executed": False, "qualified": False,
        "base_registry": str(REGISTRY), "base_registry_sha256": REGISTRY_SHA,
        "source_files": inventory(SOURCE), "interface_idl_sha256": IDL_SHA,
        "build_tools": {name: {"path": str(WINE / "build/tools" / name / name),
                               "sha256": sha256(WINE / "build/tools" / name / name)}
                        for name in ("widl", "winegcc", "winebuild")},
        "compiler_sha256": sha256(Path(compiler).resolve()),
        "link_inputs": {str(path): sha256(path) for path in libraries}, "commands": [],
        "scope": "x64 GameInput v0/v1/v2 with zero physical devices; no AGS6 or controller support",
    }
    path = output / "receipt.json"

    def save():
        path.write_text(json.dumps(receipt, indent=2) + "\n")

    commands = [
        [str(WINE / "build/tools/widl/widl"), "-h", "-o", str(include / "gameinput.h"),
         "-I", str(WINE / "source/include"), str(WINE / "source/include/gameinput.idl")],
        [compiler, "-c", *compile_flags(include), "-D_UCRT", "-fno-strict-aliasing",
         "-ffunction-sections", "-mlong-double-64", "-mcx16", "-mcmodel=small",
         str(output / "source/main.c"), "-o", str(obj)],
        [str(WINE / "build/tools/winegcc/winegcc"), "--wine-objdir", str(WINE / "build"),
         "--cc-cmd=" + compiler, "-b", "x86_64-w64-mingw32", "-shared",
         "-Wl,--wine-builtin", "-Wb,--prefer-native", str(output / "source/gameinput.spec"),
         str(obj), *map(str, libraries), "-o", str(artifact)],
        [compiler, *compile_flags(include), str(REPO / "tests/gameinput_probe.c"),
         "-o", str(output / "gameinput-probe.exe")],
    ]
    for index, command in enumerate(commands):
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        log = output / f"build-{index:02}.log"
        log.write_text(result.stdout + result.stderr)
        receipt["commands"].append({"argv": command, "exit_code": result.returncode,
                                    "log": str(log), "log_sha256": sha256(log)})
        save()
        if result.returncode:
            raise RuntimeError("Build failed: " + str(log))
    if not artifact.is_file() or not artifact.stat().st_size:
        raise RuntimeError("GameInput build produced no nonempty PE")
    install = output / "install"
    shutil.copytree(BASE / "install", install, symlinks=True)
    relative = "lib/wine/x86_64-windows/gameinput.dll"
    shutil.copy2(artifact, install / relative)
    expected = dict(before)
    expected[relative] = {"sha256": sha256(artifact)}
    if inventory(install) != expected or inventory(BASE / "install") != before:
        raise ValueError("Unexpected candidate change or frozen 11d mutation")
    receipt.update(status="built-not-runtime-qualified", qualified=False,
                   installed_files=expected, only_one_x64_gameinput_replaced=True,
                   gameinput_sha256=sha256(artifact), probe_sha256=sha256(output / "gameinput-probe.exe"),
                   base_unchanged=True)
    save()
    data = json.loads(REGISTRY.read_text().replace(str(BASE / "install"), str(install)))
    engine = data["engines"][0]
    engine["name"] = "calimocho-wine11.20-gptk4b3-gameinput-empty"
    engine["version"] = "WineHQ11.20 + AGS5.4/minidump + no-device GameInput (UNQUALIFIED)"
    for key in ("graphics_tests", "runtime_qualification"):
        engine.pop(key, None)
    engine["smoke_test"] = {"status": "not-run", "scope": "No inherited engine or game acceptance"}
    engine["integrity"] = {"status": "candidate-only", "manifest_path": str(path), "manifest_sha256": sha256(path)}
    for asset in engine["profile_assets"]["files"]:
        if asset["path"] == str(install / relative):
            asset["sha256"] = sha256(artifact)
    if not any(asset["path"] == str(install / relative) for asset in engine["profile_assets"]["files"]):
        engine["profile_assets"]["files"].append({"path": str(install / relative), "sha256": sha256(artifact)})
    engine["source_patches"] += [{"path": str(file), "sha256": sha256(file),
                                 "role": "no-device GameInput diagnostic source"}
                                for file in sorted(SOURCE.iterdir()) if file.is_file()]
    registry = output / "gameinput.registry.local.UNQUALIFIED.json"
    with registry.open("x") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(build(parser.parse_args().output))
