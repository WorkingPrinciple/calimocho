"""Build a new cell009 process-record sibling, never execute Wine."""
import argparse
import json
import os
from pathlib import Path
import shutil

from tools.build_gameinput_overlay import WINE, compile_flags
from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import port
from tools.port_uwp_activation import replace
from tools.probe_wine_source import run_step, sha256

BASE = REPO / "build/winehq-11.20/package-launcher-01"


def build(root, resume=False, call_diagnostics=False):
    root = Path(root).resolve()
    if not root.is_relative_to(REPO / "build") or root == BASE:
        raise ValueError("Require a new owned009 sibling")
    if any(root.glob("*FROZEN*")):
        raise ValueError("Refuse to rebuild a frozen009 sibling")
    frozen = BASE / "cell008-receipt.json"
    if sha256(frozen) != "ac5b627263c409b804e3f812160c6dd0ba8d39cec52910255725939de12915bc":
        raise ValueError("Frozen008 receipt changed")
    if resume:
        if not (root / "build-receipt.json").is_file():
            raise ValueError("Resume requires this builder's receipt")
        previous = json.loads((root / "build-receipt.json").read_text())
        if "steps" in previous and bool(previous.get("call_diagnostics")) != call_diagnostics:
            raise ValueError("Resume must preserve the diagnostic build mode")
    else:
        root.mkdir(exist_ok=False)
        shutil.copytree(BASE / "source", root / "source", symlinks=True)
        port(root / "source")
    module = root / "source/dlls/twinapi.appcore"
    for original, destination in (("core_application_activated.c", "core_application.c"),
                                  ("package_activation.idl", "package_activation.idl")):
        shutil.copy2(REPO / "patches/wine/files" / original, module / destination)
    makefile = module / "Makefile.in"
    text = makefile.read_text()
    if "\tpackage_activation.idl" not in text:
        makefile.write_text(text.replace("\tcore_application.c \\", "\tcore_application.c \\\n\tpackage_activation.idl \\"))
    text = makefile.read_text()
    makefile.write_text(text.replace("IMPORTS   = combase advapi32", "IMPORTS   = combase advapi32 ntdll"))
    ui = root / "source/dlls/windows.ui"
    shutil.copy2(REPO / "patches/wine/files/corewindow_host.c", ui / "corewindow_host.c")
    ui_make = ui / "Makefile.in"
    if "\tcorewindow_host.c" not in ui_make.read_text():
        replace(root / "source", "dlls/windows.ui/Makefile.in", "\tcorewindow.c \\",
                "\tcorewindow.c \\\n\tcorewindow_host.c \\")
        replace(root / "source", "dlls/windows.ui/corewindow.c", '#include "private.h"',
                '#include "private.h"\nextern HRESULT WINAPI wine_get_core_window(ICoreWindow **out);')
        replace(root / "source", "dlls/windows.ui/corewindow.c", "*windows = NULL;\n    return S_OK;",
                "return wine_get_core_window(windows);")
        spec = ui / "windows.ui.spec"
        spec.write_text(spec.read_text() + "\n@ stdcall __wine_create_core_window(ptr)\n")
    record = root / "build-receipt.json"
    if not record.exists():
        record.write_text(json.dumps({"status": "source-port-incomplete", "runtime_executed": False}) + "\n")
    diagnostic_port = None
    if call_diagnostics:
        from tools.port_call_diagnostics import port as diagnostic_port_source
        diagnostic_port = diagnostic_port_source(root / "source")
    attempt = 1
    while (root / ("attempt-%02d" % attempt)).exists():
        attempt += 1
    logs = root / ("attempt-%02d" % attempt)
    logs.mkdir()
    if record.exists():
        shutil.copy2(record, logs / "previous-receipt.json")
    directory = root / "build"
    directory.mkdir(exist_ok=True)
    baseline = json.loads((WINE / "receipt.json").read_text())
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_", "PKG_CONFIG"))
           and key not in ("CPATH", "LIBRARY_PATH", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS")}
    env.update(baseline["environment"])
    env["PATH"] = "/opt/homebrew/opt/bison/bin:" + env["PATH"]
    env["ac_cv_lib_soname_MoltenVK"] = "@rpath/libMoltenVK.dylib"
    env["ac_cv_lib_soname_gnutls"] = "@rpath/libgnutls.30.dylib"
    receipt = {"status": "incomplete", "runtime_executed": False, "steps": [],
               "predecessor_receipt_sha256": sha256(frozen)}
    if diagnostic_port is not None:
        receipt["call_diagnostics"] = diagnostic_port

    def run(name, command, budget=300, cwd=directory):
        step = run_step(command, cwd, env, logs / (name + ".log"), budget)
        receipt["steps"].append(step)
        record.write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"] or step["timed_out"]:
            raise RuntimeError("Build failed: " + str(logs / (name + ".log")))

    args = [str(root / "source/configure")] + baseline["steps"][0]["command"][1:]
    args = [arg for arg in args if not arg.startswith("--prefix=")] + ["--prefix=" + str(root / "install")]
    run("protocol", ["/usr/bin/perl", "tools/make_requests"], cwd=root / "source")
    run("configure", args)
    run("server-ntdll", ["/usr/bin/make", "-j4", "server/wineserver",
                       "dlls/ntdll/ntdll.so", "dlls/ntdll/x86_64-windows/ntdll.dll",
                       "dlls/twinapi.appcore/x86_64-windows/twinapi.appcore.dll",
                       "dlls/windows.ui/x86_64-windows/windows.ui.dll"], budget=600)
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing MinGW compiler")
    launcher = root / "source/dlls/windows.system.launcher"
    include = root / "launcher-include"
    include.mkdir(exist_ok=True)
    for name in ("launcher", "async_private"):
        run(name + "-header", [str(WINE / "build/tools/widl/widl"), "-h",
                              "-o", str(include / (name + ".h")),
                              "-I", str(root / "source/include"), str(launcher / (name + ".idl"))])
    objects = []
    for name in ("main", "async"):
        obj = root / (name + ".o")
        run("launcher-" + name, [compiler, "-c", "-I" + str(root / "source/include"),
                                *compile_flags(include), "-I" + str(launcher),
                                "-D_UCRT", "-fno-strict-aliasing", "-ffunction-sections",
                                "-mlong-double-64", "-mcx16", "-mcmodel=small",
                                str(launcher / (name + ".c")), "-o", str(obj)])
        objects.append(str(obj))
    libraries = [directory / relative for relative in (
        "libs/winecrt0/x86_64-windows/libwinecrt0.a", "libs/compiler-rt/x86_64-windows/libcompiler-rt.a",
        "dlls/ucrtbase/x86_64-windows/libucrtbase.a", "dlls/kernel32/x86_64-windows/libkernel32.a",
        "dlls/ntdll/x86_64-windows/libntdll.a", "dlls/combase/x86_64-windows/libcombase.a",
        "libs/uuid/x86_64-windows/libuuid.a")]
    # UUIDs are generated only by targets that need them; use the exact frozen base archive.
    libraries[-1] = WINE / "build/libs/uuid/x86_64-windows/libuuid.a"
    run("launcher-link", [str(WINE / "build/tools/winegcc/winegcc"), "--wine-objdir", str(directory),
                          "--cc-cmd=" + compiler, "-b", "x86_64-w64-mingw32", "-shared",
                          "-Wl,--wine-builtin", str(launcher / "windows.system.launcher.spec"),
                          *objects, *map(str, libraries), "-o", str(root / "windows.system.launcher.dll")])
    receipt["status"] = "built-not-staged-not-executed"
    receipt["source_inputs"] = {
        str(path.relative_to(REPO)): sha256(path) for path in (
            REPO / "tools/port_uwp_activation.py", REPO / "tools/build_uwp_overlay.py",
            REPO / "patches/wine/files/core_application_activated.c",
            REPO / "patches/wine/files/corewindow_host.c",
            REPO / "patches/wine/files/package_activation.idl",
            REPO / "patches/wine/files/package_activation_record.h")}
    if call_diagnostics:
        for relative in ("tools/port_call_diagnostics.py",
                         "patches/wine/files/package_call_diagnostics.h",
                         "patches/wine/files/package_relay_diagnostics.h",
                         "patches/wine/files/package_wait_diagnostics.h"):
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    receipt["built_files"] = {str(path.relative_to(root)): sha256(path) for path in (
        directory / "server/wineserver", directory / "dlls/ntdll/ntdll.so",
        directory / "dlls/ntdll/x86_64-windows/ntdll.dll",
        directory / "dlls/twinapi.appcore/x86_64-windows/twinapi.appcore.dll",
        directory / "dlls/windows.ui/x86_64-windows/windows.ui.dll",
        root / "windows.system.launcher.dll")}
    record.write_text(json.dumps(receipt, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--call-diagnostics", action="store_true")
    args = parser.parse_args()
    print(build(args.root, args.resume, args.call_diagnostics))
