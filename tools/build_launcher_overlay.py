"""Build a NEW package-local Launcher and multi-image server; never run Wine."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from tools.build_minidump_overlay import inventory
from tools.build_gameinput_overlay import compile_flags, WINE
from tools.port_package_protocols import port
from tools.probe_wine_source import run_step, sha256
from tools.stage_framework_overlay import rebase

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/winehq-11.20/package-framework-01"
MODULE = REPO / "patches/wine/files/windows.system.launcher"


def registry_for(install, artifact):
    frozen = BASE / "framework.registry.local.CELL007-FROZEN.json"
    registry = json.loads(frozen.read_text())
    entry = rebase(registry["engines"][0], BASE / "install", install)
    entry["install_path"] = str(install)
    entry["name"] = "calimocho-wine11.20-package-protocol-diagnostic"
    entry["wineserver_sha256"] = sha256(install / "bin/wineserver")
    entry["profile_assets"]["files"].append({
        "path": str(install / "lib/wine/x86_64-windows/windows.system.launcher.dll"),
        "sha256": sha256(artifact)})
    entry["smoke_test"] = {"status": "not-run", "scope": "Cell008 source/build only"}
    entry["integrity"] = {"status": "candidate-only"}
    registry["engines"] = [entry]
    return registry


def build(output, resume=False):
    output = Path(output).resolve()
    if (output.exists() and not resume) or not output.is_relative_to(REPO / "build"):
        raise ValueError("Require a new owned build output")
    frozen = BASE / "framework.registry.local.CELL007-FROZEN.json"
    if sha256(frozen) != "56da37e7a6e96870baadd9fa9600ba091830057a6542f5f0eea240e28214a6d0":
        raise ValueError("Cell007 registry changed")
    before = inventory(BASE / "install")
    if before != json.loads((BASE / "inventory-CELL007-FROZEN.json").read_text())["files"]:
        raise ValueError("Cell007 deployed inventory changed")
    if resume and not (output / "build-receipt.json").is_file():
        raise ValueError("Resume requires this builder's retained incomplete receipt")
    if resume and any(output.glob("*FROZEN*")):
        raise ValueError("Refuse to rebuild a frozen candidate")
    deployed_before = None
    if resume and (output / "install").exists():
        previous = json.loads((output / "build-receipt.json").read_text())
        deployed_before = previous.get("files", previous.get("previous_deployed_files"))
        if deployed_before is None or deployed_before != inventory(output / "install"):
            raise ValueError("Cannot resume an unrecognized existing candidate install")
    output.mkdir(parents=True, exist_ok=resume)
    source = output / "source"
    if not resume:
        shutil.copytree(BASE / "source", source, symlinks=True)
        port(source)
    module = source / "dlls/windows.system.launcher"
    shutil.copytree(MODULE, module, dirs_exist_ok=resume)
    upstream = source / "dlls/windows.gaming.input"
    async_source = (upstream / "async.c").read_text()
    boundary = "\nstruct async_result\n"
    if async_source.count(boundary) != 1:
        raise ValueError("Unexpected upstream bool-async boundary")
    private = (upstream / "private.h").read_text()
    macros = private[private.index("#define DEFINE_IINSPECTABLE_("):
                     private.index("static inline const char *debugstr_vector3")]
    async_source = async_source.split(boundary)[0]
    async_source = async_source.replace('#include "private.h"', '#include "private.h"\n' + macros, 1)
    (module / "async.c").write_text(async_source + "\n")
    shutil.copy2(upstream / "async_private.idl", module / "async_private.idl")
    build_dir = output / "build"
    build_dir.mkdir(exist_ok=resume)
    baseline = json.loads((WINE / "receipt.json").read_text())
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_", "PKG_CONFIG"))
           and key not in ("CPATH", "LIBRARY_PATH", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS")}
    env.update(baseline["environment"])
    env["PATH"] = "/opt/homebrew/opt/bison/bin:" + env["PATH"]
    env["ac_cv_lib_soname_MoltenVK"] = "@rpath/libMoltenVK.dylib"
    env["ac_cv_lib_soname_gnutls"] = "@rpath/libgnutls.30.dylib"
    args = [str(source / "configure")] + baseline["steps"][0]["command"][1:]
    args = [arg for arg in args if not arg.startswith("--prefix=")] + ["--prefix=" + str(output / "install")]
    receipt = {"status": "incomplete", "runtime_executed": False, "steps": [],
               "module_sources": inventory(MODULE),
               "upstream_async_sha256": sha256(upstream / "async.c"),
               "upstream_async_idl_sha256": sha256(upstream / "async_private.idl")}
    if deployed_before is not None:
        receipt["previous_deployed_files"] = deployed_before
    record = output / "build-receipt.json"
    logs = output
    if resume:
        attempt = 2
        while (output / ("attempt-%02d" % attempt)).exists():
            attempt += 1
        logs = output / ("attempt-%02d" % attempt)
        logs.mkdir()
        shutil.copy2(record, logs / "previous-build-receipt.json")
        if (output / "windows.system.launcher.dll").exists():
            shutil.copy2(output / "windows.system.launcher.dll", logs / "previous-launcher.dll")

    def run(name, command, directory=build_dir, budget=180):
        step = run_step(command, directory, env, logs / (name + ".log"), budget)
        receipt["steps"].append(step)
        record.write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"] or step["timed_out"]:
            raise RuntimeError("Failed " + name + ": " + str(logs / (name + ".log")))

    run("configure", args, budget=300)
    run("server", ["/usr/bin/make", "-j4", "server/wineserver"], budget=300)
    include = output / "include"
    include.mkdir(exist_ok=resume)
    widl = WINE / "build/tools/widl/widl"
    for name in ("launcher", "async_private"):
        run(name + "-header", [str(widl), "-h", "-o", str(include / (name + ".h")),
                              "-I", str(source / "include"), str(module / (name + ".idl"))])
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing MinGW")
    objects = []
    for name in ("main", "async"):
        obj = output / (name + ".o")
        run(name, [compiler, "-c", "-I" + str(source / "include"),
                   *compile_flags(include), "-I" + str(module),
                   "-D_UCRT", "-fno-strict-aliasing", "-ffunction-sections", "-mlong-double-64",
                   "-mcx16", "-mcmodel=small", str(module / (name + ".c")), "-o", str(obj)])
        objects.append(str(obj))
    libraries = [WINE / "build" / relative for relative in (
        "libs/winecrt0/x86_64-windows/libwinecrt0.a", "libs/compiler-rt/x86_64-windows/libcompiler-rt.a",
        "dlls/ucrtbase/x86_64-windows/libucrtbase.a", "dlls/kernel32/x86_64-windows/libkernel32.a",
        "dlls/ntdll/x86_64-windows/libntdll.a", "dlls/combase/x86_64-windows/libcombase.a",
        "libs/uuid/x86_64-windows/libuuid.a")]
    libraries = [BASE / "build/dlls/ntdll/x86_64-windows/libntdll.a"
                 if path.name == "libntdll.a" else path for path in libraries]
    artifact = output / "windows.system.launcher.dll"
    run("link", [str(WINE / "build/tools/winegcc/winegcc"), "--wine-objdir", str(WINE / "build"),
                 "--cc-cmd=" + compiler, "-b", "x86_64-w64-mingw32", "-shared",
                 "-Wl,--wine-builtin", str(module / "windows.system.launcher.spec"),
                 *objects, *map(str, libraries), "-o", str(artifact)])
    install = output / "install"
    if install.exists():
        if not resume or deployed_before != inventory(install):
            raise ValueError("Cannot preserve an unrecognized existing candidate install")
        install.rename(logs / "previous-install")
        old_registry = output / "launcher.registry.local.UNQUALIFIED.json"
        if old_registry.exists():
            old_registry.rename(logs / "previous-registry.json")
    shutil.copytree(BASE / "install", install, symlinks=True)
    shutil.copy2(artifact, install / "lib/wine/x86_64-windows/windows.system.launcher.dll")
    shutil.copy2(build_dir / "server/wineserver", install / "bin/wineserver")
    actual = inventory(install)
    expected = dict(before)
    for name in ("bin/wineserver", "lib/wine/x86_64-windows/windows.system.launcher.dll"):
        expected[name] = {"sha256": sha256(install / name)}
    if actual != expected or inventory(BASE / "install") != before:
        raise ValueError("Unexpected deployed difference or cell007 mutation")
    registry = registry_for(install, artifact)
    receipt.update(status="built-not-runtime-qualified", files=actual, predecessor_unchanged=True,
                   module_sha256=sha256(artifact), server_sha256=registry["engines"][0]["wineserver_sha256"],
                   link_inputs={str(path): sha256(path) for path in libraries})
    record.write_text(json.dumps(receipt, indent=2) + "\n")
    new_registry = output / "launcher.registry.local.UNQUALIFIED.json"
    new_registry.write_text(json.dumps(registry, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(build(args.output, args.resume))
