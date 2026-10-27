#!/usr/bin/env python3
"""Build archive-pinned SDL2 into an isolated x86_64 prefix for winebus.sys (ADR-0085)."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

from probe_wine_source import REPO, fixed_install_prefix, relocate_pkgconfig, run_step, sha256

LIBRARY = "libSDL2-2.0.0.dylib"


def build(archive, output):
    pin = json.loads((REPO / "versions.json").read_text())["sdl_source"]
    if sha256(archive) != pin["sha256"]:
        raise ValueError("SDL2 source archive checksum mismatch")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    top = f"SDL2-{pin['version']}/"
    with tarfile.open(archive) as stream:
        members = [member for member in stream.getmembers() if member.name.startswith(top)]
        if not members:
            raise ValueError("Pinned source archive contains no SDL2")
        stream.extractall(output, members=members, filter="data")
    source = output / top.rstrip("/")
    build_dir = output / "build"
    build_dir.mkdir()
    prefix = output / "prefix"
    with fixed_install_prefix("sdl", prefix) as fixed:
        result = build_in(output, pin, source, build_dir, prefix, fixed)
    if result == 0:
        relocate_pkgconfig(prefix, fixed)
    return result


def build_in(output, pin, source, build_dir, prefix, fixed):
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"CFLAGS", "CPPFLAGS", "LDFLAGS", "CC", "CXX", "OBJC"}
        and not key.startswith(("DYLD_", "PKG_CONFIG", "WINE", "CX_", "SDL_"))
    }
    environment.update(
        # Map build paths out of __FILE__ strings and debug info (reproducible, no dev paths).
        CC="/usr/bin/clang -arch x86_64", OBJC="/usr/bin/clang -arch x86_64",
        CFLAGS=f"-O2 -ffile-prefix-map={output}/=sdl-build/",
        PKG_CONFIG_LIBDIR=str(output / "no-system-pkgconfig"),
        CONFIG_SITE="/dev/null", LC_ALL="C",
    )
    receipt = {
        "source_url": pin["url"], "archive_sha256": pin["sha256"],
        "version": pin["version"], "architecture": "x86_64",
        "compiler": subprocess.check_output(["/usr/bin/clang", "--version"], text=True, timeout=30),
        "compiler_sha256": sha256(Path("/usr/bin/clang")),
        "sdk": subprocess.check_output(["xcrun", "--show-sdk-path"], text=True, timeout=30).strip(),
        "configure_sha256": sha256(source / "configure"),
        "configure_flags": pin["configure_flags"],
        "environment": {key: environment[key] for key in
                        ("CC", "OBJC", "CFLAGS", "PKG_CONFIG_LIBDIR", "CONFIG_SITE", "LC_ALL")},
        "steps": [], "status": "incomplete",
    }
    started = time.monotonic()
    for label, command in (
            ("configure", [str(source / "configure"), "--host=x86_64-apple-darwin",
                           f"--prefix={fixed}", *pin["configure_flags"]]),
            ("compile", ["/usr/bin/make", "-j4"]),
            ("local-install", ["/usr/bin/make", "install"])):
        remaining = 900 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("SDL2 build budget exhausted")
        step = run_step(command, build_dir, environment, output / f"{label}.log", remaining)
        receipt["steps"].append(step)
        receipt["status"] = label if step["exit_code"] == 0 else f"{label}-failed"
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"]:
            print(f"{label} failed ({step['exit_code']}): {output / f'{label}.log'}", file=sys.stderr)
            return step["exit_code"] if step["exit_code"] > 0 else 1
    library = prefix / "lib" / LIBRARY
    if not library.is_file() or not library.stat().st_size:
        raise ValueError("No nonempty SDL2 library after local install")
    linkage = subprocess.check_output(["otool", "-L", str(library)], text=True, timeout=30)
    # Only Apple system libraries and frameworks; the engine bundles nothing else for SDL.
    foreign = [line.strip() for line in linkage.splitlines()[1:]
               if line.strip() and not line.strip().startswith(("/usr/lib/", "/System/Library/", str(fixed)))]
    if foreign:
        raise ValueError(f"SDL2 links outside the system: {foreign}")
    if "GameController.framework" not in linkage:
        raise ValueError("SDL2 was built without the GameController (MFi) joystick driver")
    receipt["artifact"] = {
        "path": str(library), "sha256": sha256(library),
        "file": subprocess.check_output(["file", str(library)], text=True, timeout=30),
        "linkage": linkage,
    }
    if "x86_64" not in receipt["artifact"]["file"]:
        raise ValueError("SDL2 library is not x86_64")
    receipt["status"] = "built-local-dependency"
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Built isolated SDL2: {library}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        return build(args.archive, args.output)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"calimocho SDL2 build: ERROR {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
