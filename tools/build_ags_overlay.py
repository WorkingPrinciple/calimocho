"""Build an opt-in Wine AGS5.4 adapter plus minidump forwarders in a new sibling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from . import build_minidump_overlay as minidump
from .probe_wine_source import sha256


REPO = Path(__file__).resolve().parents[1]
MODULE = "amd_ags_x64"
SOURCE = REPO / "patches/wine/files" / MODULE
WINE = REPO / "build/winehq-11.20/metal-port-11"
BUILD = WINE / "build"


def write_registry(output):
    """Bind only this install; never inherit a base runtime's qualification."""
    output = output.resolve()
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "built-not-runtime-qualified":
        raise ValueError("Require a completed candidate build")
    if minidump.inventory(output / "install") != receipt["installed_files"]:
        raise ValueError("Candidate inventory differs from its build receipt")
    data = json.loads(minidump.REGISTRY.read_text().replace(
        str(minidump.BASE / "install"), str(output / "install")))
    engine = data["engines"][0]
    for field in ("graphics_tests", "tls_positive_test", "tls_negative_test", "build_evidence",
                  "compiled_source_evidence"):
        engine.pop(field, None)
    engine.update(
        name="calimocho-wine11.20-gptk4b3-ags54-minidump",
        version="WineHQ11.20 port11b + opt-in AGS5.4 + minidump (UNQUALIFIED)",
        smoke_test={"status": "not-run", "scope": "No inherited runtime or game result"},
        integrity={"status": "candidate-only", "manifest_path": str(receipt_path),
                   "manifest_sha256": sha256(receipt_path),
                   "scope": "exactly three declared DLL additions; base unchanged"},
    )
    assets = engine["profile_assets"]["files"]
    for item in assets:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError(f"Frozen profile asset changed: {item['path']}")
    for item in receipt["overlay"]:
        assets.append({"path": str(output / "install" / item["path"]), "sha256": item["sha256"]})
    for directory in (SOURCE, minidump.SOURCE):
        for path in sorted(directory.iterdir()):
            if path.is_file():
                engine["source_patches"].append(
                    {"path": str(path), "sha256": sha256(path),
                     "role": "Local Wine-built opt-in compatibility module source"})
    # The generic engine keeps its quiet base selection. Only the separate DIRT5
    # recipe selects the builtin, so other games retain native AGS behavior.
    profile = output / "dirt5-ags54.environment.json"
    with profile.open("x") as stream:
        json.dump({
            "scope": "DIRT5 AGS5.4 with GPTK only; not a general AMD AGS replacement",
            "engine": engine["name"],
            "environment": {"WINEDLLOVERRIDES":
                            engine["environment"]["WINEDLLOVERRIDES"] + ";amd_ags_x64=b"},
            "qualified": False,
        }, stream, indent=2)
        stream.write("\n")
    registry = output / "ags54-minidump.registry.local.UNQUALIFIED.json"
    with registry.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    return registry


def build(output):
    output = output.resolve()
    receipt_path = minidump.build(output)
    receipt = json.loads(receipt_path.read_text())
    receipt.update(status="incomplete-ags", qualified=False,
                   ags_source_files=minidump.inventory(SOURCE),
                   ags_scope="explicit DIRT5/GPTK opt-in; AGS5.4 only, no AMD extensions",
                   selection="WINEDLLOVERRIDES=amd_ags_x64=b",
                   native_preferred_without_override=True)
    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    save()
    source = output / "source" / MODULE
    shutil.copytree(SOURCE, source)
    work = output / "x86_64"
    artifact = work / (MODULE + ".dll")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require the already installed x64 MinGW compiler")
    receipt["compiler"] = compiler
    receipt["compiler_sha256"] = sha256(Path(compiler).resolve())
    for name in ("winebuild", "winegcc"):
        path = BUILD / "tools" / name / name
        receipt[name + "_sha256"] = sha256(path)
    d3d_spec = WINE / "source/dlls/d3d12/d3d12.spec"
    receipt["d3d12_import_spec_sha256"] = sha256(d3d_spec)
    imports = work / "libd3d12.a"
    obj = work / "ags54.o"
    libraries = [
        BUILD / "libs/winecrt0/x86_64-windows/libwinecrt0.a",
        BUILD / "libs/compiler-rt/x86_64-windows/libcompiler-rt.a",
        BUILD / "dlls/ucrtbase/x86_64-windows/libucrtbase.a",
        BUILD / "dlls/kernel32/x86_64-windows/libkernel32.a",
        BUILD / "dlls/ntdll/x86_64-windows/libntdll.a",
    ]
    receipt["link_inputs"] = {str(path): sha256(path) for path in libraries}
    commands = [
        [str(BUILD / "tools/winebuild/winebuild"), "-w", "--implib", "-o", str(imports),
         "--cc-cmd=" + compiler, "--without-dlltool", "-b", "x86_64-w64-mingw32",
         "--export", str(d3d_spec)],
        [compiler, "-c", "-o", str(obj), str(source / "main.c"),
         "-I" + str(source), "-I" + str(BUILD / "include"),
         "-I" + str(WINE / "source/include"), "-I" + str(WINE / "source/include/msvcrt"),
         "-D_UCRT", "-D__WINESRC__", "-D__WINE_PE_BUILD", "-Wall", "-Wextra", "-Werror",
         "-fno-strict-aliasing", "-ffunction-sections", "-mlong-double-64", "-mcx16",
         "-mcmodel=small", "-O2"],
        [str(BUILD / "tools/winegcc/winegcc"), "-o", str(artifact),
         "--wine-objdir", str(BUILD), "--cc-cmd=" + compiler, "-b", "x86_64-w64-mingw32",
         "-Wl,--wine-builtin", "-Wb,--prefer-native", "-shared",
         str(source / (MODULE + ".spec")), str(obj), str(imports),
         *map(str, libraries)],
    ]
    for index, command in enumerate(commands, 1):
        log = output / f"ags-build-{index:02}.log"
        result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=90)
        log.write_text(result.stdout + result.stderr)
        receipt["commands"].append(dict(command=command, exit_code=result.returncode,
                                        log=str(log), log_sha256=sha256(log)))
        save()
        if result.returncode:
            raise RuntimeError(f"AGS build failed; see {log}")
    if not artifact.is_file() or not artifact.stat().st_size:
        raise RuntimeError("AGS build emitted no nonempty PE")
    relative = "lib/wine/x86_64-windows/amd_ags_x64.dll"
    destination = output / "install" / relative
    if destination.exists():
        raise ValueError("Refuse to replace an existing AGS module")
    shutil.copy2(artifact, destination)
    receipt["overlay"].append(dict(path=relative, source=str(artifact), sha256=sha256(artifact)))
    before = minidump.inventory(minidump.BASE / "install")
    expected = dict(before)
    expected.update({entry["path"]: {"sha256": entry["sha256"]}
                     for entry in receipt["overlay"]})
    if minidump.inventory(output / "install") != expected:
        raise RuntimeError("Unexpected candidate file inventory")
    receipt.update(status="built-not-runtime-qualified", only_two_forwarders_added=False,
                   only_three_declared_dlls_added=True, installed_files=expected)
    save()
    write_registry(output)
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(build(parser.parse_args().output))
