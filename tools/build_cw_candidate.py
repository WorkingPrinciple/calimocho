#!/usr/bin/env python3
"""Compile coherent CodeWeavers macOS integration in an isolated build tree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

from probe_wine_source import REPO, run_step, sha256
from port_d3dmetal import port


COMPONENT_ARTIFACTS = (
    "loader/wine", "server/wineserver", "dlls/winemac.drv/winemac.so",
    "dlls/ntdll/ntdll.so", "dlls/win32u/win32u.so",
)
FULL_ARTIFACTS = COMPONENT_ARTIFACTS + tuple(
    f"{directory}/{arch}-windows/{name}"
    for arch in ("x86_64", "i386")
    for directory, name in (
        ("dlls/ntdll", "ntdll.dll"), ("dlls/kernel32", "kernel32.dll"),
        ("dlls/winemac.drv", "winemac.drv"),
        ("programs/cmd", "cmd.exe"),
    )
) + ("programs/wineboot/x86_64-windows/wineboot.exe",)
PORT_CHECK_TARGETS = (
    "loader/wine", "server/wineserver", "dlls/winemac.drv/winemac.so",
    "dlls/ntdll/ntdll.so", "dlls/win32u/win32u.so",
    "dlls/ntdll/x86_64-windows/ntdll.dll",
    "dlls/kernel32/x86_64-windows/kernel32.dll",
    "dlls/winemac.drv/x86_64-windows/winemac.drv",
)
PORT_CHECK_ARTIFACTS = PORT_CHECK_TARGETS


def ensure_output_disjoint(output, input_path, label):
    if (output == input_path or output in input_path.parents
            or input_path in output.parents):
        raise ValueError(f"Build output must not overlap {label}")


def toolchain_identity():
    tools = {}
    for name in ("clang", "make"):
        path = Path(subprocess.check_output(
            ["xcrun", "--find", name], text=True, timeout=30).strip()).resolve(strict=True)
        tools[name] = {"path": str(path), "sha256": sha256(path)}
    for name in ("bison", "flex", "x86_64-w64-mingw32-gcc", "i686-w64-mingw32-gcc"):
        installed = shutil.which(name)
        if not installed:
            raise ValueError(f"Required installed tool missing: {name}")
        path = Path(installed).resolve(strict=True)
        tools[name] = {
            "path": str(path), "sha256": sha256(path),
            "version": subprocess.check_output(
                [str(path), "--version"], text=True, timeout=30),
        }
    return {
        "tools": tools,
        "sdk_path": subprocess.check_output(
            ["xcrun", "--show-sdk-path"], text=True, timeout=30).strip(),
        "sdk_version": subprocess.check_output(
            ["xcrun", "--show-sdk-version"], text=True, timeout=30).strip(),
    }


def tree_hash(root):
    result = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            value = "link:" + os.readlink(path)
        elif path.is_file():
            value = sha256(path)
        else:
            continue
        result.update(f"{relative}\0{value}\n".encode())
    return result.hexdigest()


def build(archive, output, freetype, build_all=False, winehq_source=None,
          port_check=False):
    if port_check and (not winehq_source or build_all):
        raise ValueError("--port-check requires --winehq-source and excludes --build-all")
    pin = json.loads((REPO / "versions.json").read_text())["cw_candidate_sources"]
    if sha256(archive) != pin["sha256"]:
        raise ValueError("CodeWeavers source archive checksum mismatch")
    upstream_pin = None
    if winehq_source is not None:
        winehq_source = winehq_source.resolve(strict=True)
    freetype = freetype.resolve(strict=True)
    output = output.resolve()
    if winehq_source is not None:
        ensure_output_disjoint(output, winehq_source, "WineHQ source")
    ensure_output_disjoint(output, freetype, "FreeType prefix")
    if winehq_source is not None:
        upstream_pin = json.loads((REPO / "versions.json").read_text())["winehq_probe"]
        commit = subprocess.check_output(
            ["git", "-C", str(winehq_source), "rev-parse", "HEAD"],
            text=True, timeout=30).strip()
        if commit != upstream_pin["commit"]:
            raise ValueError("WineHQ source commit differs from pin")
        if subprocess.check_output(
                ["git", "-C", str(winehq_source), "status", "--porcelain",
                 "--untracked-files=all"], text=True, timeout=30):
            raise ValueError("WineHQ input source must remain pristine")
    ft_library = freetype / "lib/libfreetype.6.dylib"
    if not ft_library.is_file():
        raise ValueError("Explicit source-built FreeType prefix is missing its library")
    ft_info = subprocess.check_output(["file", str(ft_library)], text=True, timeout=30)
    if "x86_64" not in ft_info:
        raise ValueError("FreeType must contain an x86_64 slice")
    bison = shutil.which("bison")
    if not bison:
        raise ValueError("An installed bison >= 3 is required")
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        members = [
            member for member in stream.getmembers()
            if member.name.startswith("sources/wine/")
        ]
        if not members:
            raise ValueError("No Wine source found in pinned archive")
        stream.extractall(output, members=members, filter="data")
    source = output / "sources/wine"
    pristine_tree = tree_hash(source)
    patches = []
    integration = None
    if winehq_source is not None:
        donor = source
        source = output / "winehq-source"
        source.mkdir()
        snapshot = output / "winehq-source.tar"
        subprocess.run(
            ["git", "-C", str(winehq_source), "archive", "--format=tar",
             f"--output={snapshot}", upstream_pin["commit"]],
            check=True, timeout=60,
        )
        with tarfile.open(snapshot) as stream:
            stream.extractall(source, filter="data")
        pristine_tree = tree_hash(source)
        integration = port(source, donor)
        patches.append({"path": "tools/port_d3dmetal.py",
                        "sha256": sha256(REPO / "tools/port_d3dmetal.py")})
    else:
        patch_file = REPO / "patches/cw26.3/0001-guard-absent-vulkan-soname.patch"
        patch_log = output / "source-patch.log"
        with patch_file.open("rb") as patch_stream, patch_log.open("w") as log:
            subprocess.run(
                ["/usr/bin/patch", "-p1", "--batch", "--forward"],
                cwd=source, stdin=patch_stream, stdout=log,
                stderr=subprocess.STDOUT, check=True, timeout=30,
            )
        patches.append({"path": str(patch_file), "sha256": sha256(patch_file),
                        "log_sha256": sha256(patch_log)})
    directory = output / "build"
    directory.mkdir()
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"CC", "CXX", "CFLAGS", "CPPFLAGS", "CXXFLAGS", "LDFLAGS",
                       "CPATH", "LIBRARY_PATH", "CONFIG_SITE"}
        and not key.startswith(("WINE", "CX_", "DYLD_", "PKG_CONFIG"))
    }
    environment.update(
        CC="/usr/bin/clang -arch x86_64",
        CXX="/usr/bin/clang++ -arch x86_64",
        BISON=bison, LC_ALL="C", CONFIG_SITE="/dev/null",
        PKG_CONFIG_LIBDIR=str(freetype / "lib/pkgconfig"),
        CPPFLAGS=f"-I{freetype / 'include/freetype2'}",
        LDFLAGS=f"-L{freetype / 'lib'}",
    )
    receipt = {
        "source_url": pin["url"], "archive_sha256": pin["sha256"],
        "pristine_source_tree_sha256": pristine_tree,
        "source_tree_sha256": tree_hash(source),
        "patches": patches,
        "winehq_source": upstream_pin,
        "integration": integration,
        "version": (source / "VERSION").read_text().strip(),
        "compiler_sha256": sha256(Path("/usr/bin/clang")),
        "compiler": subprocess.check_output(
            ["/usr/bin/clang", "--version"], text=True, timeout=30),
        "make_sha256": sha256(Path("/usr/bin/make")),
        "bison_sha256": sha256(Path(bison)),
        "toolchain": toolchain_identity(),
        "freetype": {"prefix": str(freetype), "sha256": sha256(ft_library)},
        "configure_sha256": sha256(source / "configure"),
        "environment": {key: environment[key] for key in
                        ("CC", "CXX", "BISON", "LC_ALL", "CONFIG_SITE",
                         "PKG_CONFIG_LIBDIR", "CPPFLAGS", "LDFLAGS")},
        "steps": [], "status": "incomplete",
        "installed": False, "runtime_executed": False,
        "apple_payloads_copied": False, "game_qualified": False,
        "build_all": build_all,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    started = time.monotonic()
    compile_targets = (
        [] if build_all else
        list(PORT_CHECK_TARGETS) if port_check else [
            "loader/wine", "server/wineserver", "dlls/winemac.drv/winemac.so"])
    steps = [
        ("configure", [
            str(source / "configure"), "--host=x86_64-apple-darwin",
            "--enable-archs=x86_64,i386", "--disable-tests", "--without-x",
            "--with-freetype", "--with-coreaudio",
        ]),
        ("compile", ["/usr/bin/make", "-j4"] + compile_targets),
    ]
    if winehq_source is not None:
        interposer_source = REPO / "tools/native_gs_localtime.c"
        interposer = directory / "loader/libnative-gs-localtime.dylib"
        interposer.parent.mkdir(exist_ok=True)
        receipt["native_gs_interposer_source"] = {
            "path": str(interposer_source), "sha256": sha256(interposer_source),
        }
        receipt["runtime_environment"] = {
            "DYLD_FALLBACK_LIBRARY_PATH": f"{freetype / 'lib'}:/usr/lib",
            "WINEDLLOVERRIDES": "mscoree,mshtml=",
        }
        receipt["runtime_dependencies"] = [{
            "path": str(interposer),
            "install_relative_path": "lib/wine/x86_64-unix/libnative-gs-localtime.dylib",
            "loader_dependency": "@loader_path/libnative-gs-localtime.dylib",
            "required_load_command": "LC_LOAD_DYLIB",
        }]
        steps.append(("native-gs-interposer", [
            "/usr/bin/clang", "-arch", "x86_64", "-dynamiclib",
            "-Wall", "-Wextra", "-Werror",
            "-Wl,-install_name,@loader_path/libnative-gs-localtime.dylib",
            "-o", str(interposer),
            str(interposer_source),
        ]))
        steps.append(("native-gs-loader-link", [
            "/usr/bin/make", "-W", "loader/main.o", "loader/wine",
            f"LDFLAGS={environment['LDFLAGS']} -Wl,-needed_library,{interposer}",
        ]))
    for label, command in steps:
        remaining = 1800 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("Candidate configure/compile budget exhausted")
        step = run_step(command, directory, environment, output / f"{label}.log", remaining)
        receipt["steps"].append(step)
        receipt["status"] = label if step["exit_code"] == 0 else f"{label}-failed"
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"]:
            print(f"{label} failed ({step['exit_code']}): {output / f'{label}.log'}",
                  file=sys.stderr)
            return step["exit_code"] if step["exit_code"] > 0 else 1
    if winehq_source is not None:
        load_commands = subprocess.check_output(
            ["otool", "-l", str(directory / "loader/wine")], text=True, timeout=30)
        if not re.search(
            r"\bcmd LC_LOAD_DYLIB\s+cmdsize \d+\s+"
            r"name @loader_path/libnative-gs-localtime\.dylib \(offset \d+\)",
            load_commands,
        ):
            raise ValueError("Wine loader is missing its required native-GS LC_LOAD_DYLIB")
        receipt["native_gs_loader_load_commands"] = load_commands
    receipt["artifacts"] = []
    artifacts = (FULL_ARTIFACTS if build_all else
                 PORT_CHECK_ARTIFACTS if port_check else COMPONENT_ARTIFACTS)
    if winehq_source is not None:
        artifacts += ("loader/libnative-gs-localtime.dylib",)
    for relative in artifacts:
        path = directory / relative
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Expected compiler artifact missing: {path}")
        info = subprocess.check_output(["file", str(path)], text=True, timeout=30)
        artifact = {
            "path": str(path), "sha256": sha256(path),
            "file": info,
        }
        if "Mach-O" in info:
            artifact["linkage"] = subprocess.check_output(
                ["otool", "-L", str(path)], text=True, timeout=30)
        receipt["artifacts"].append(artifact)
    receipt["status"] = (
        "full-build-compiled-not-runtime-qualified" if build_all else
        "port-check-compiled-not-runtime-qualified" if port_check
        else "macos-components-compiled-not-runtime-qualified")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"{receipt['status']}. Receipt: {output / 'receipt.json'}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--freetype", required=True, type=Path)
    parser.add_argument("--build-all", action="store_true",
                        help="Compile all configured PE/runtime components; never install or launch")
    parser.add_argument("--winehq-source", type=Path,
                        help="Pristine pinned WineHQ checkout; port CW integration into a new copy")
    parser.add_argument("--port-check", action="store_true",
                        help="Compile coupled macdrv, ntdll, win32u and key PE modules")
    args = parser.parse_args()
    try:
        return build(args.archive, args.output, args.freetype, args.build_all,
                     args.winehq_source, args.port_check)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"calimocho candidate build: ERROR {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
