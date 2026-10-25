#!/usr/bin/env python3
"""Build archive-pinned FreeType into an isolated x86_64 prefix."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

from probe_wine_source import REPO, run_step, sha256


def build(archive, output):
    pin = json.loads((REPO / "versions.json").read_text())["freetype_source"]
    if sha256(archive) != pin["sha256"]:
        raise ValueError("FreeType source archive checksum mismatch")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / f"freetype-{pin['version']}"
    with tarfile.open(archive) as stream:
        members = [
            member for member in stream.getmembers()
            if member.name.startswith(f"freetype-{pin['version']}/")
        ]
        if not members:
            raise ValueError("Pinned source archive contains no FreeType")
        stream.extractall(output, members=members, filter="data")
    build_dir = output / "build"
    build_dir.mkdir()
    prefix = output / "prefix"
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"CFLAGS", "CPPFLAGS", "LDFLAGS", "CC", "CXX"}
        and not key.startswith(("DYLD_", "PKG_CONFIG", "WINE", "CX_"))
    }
    environment.update(
        # Map build paths out of __FILE__ strings and debug info (reproducible, no dev paths).
        CC="/usr/bin/clang -arch x86_64", CFLAGS=f"-O2 -ffile-prefix-map={output}/=freetype-build/",
        PKG_CONFIG_LIBDIR=str(output / "no-system-pkgconfig"),
        CONFIG_SITE="/dev/null", LC_ALL="C",
    )
    receipt = {
        "source_url": pin["url"], "archive_sha256": pin["sha256"],
        "version": pin["version"], "architecture": "x86_64",
        "compiler": subprocess.check_output(
            ["/usr/bin/clang", "--version"], text=True, timeout=30),
        "compiler_sha256": sha256(Path("/usr/bin/clang")),
        "sdk": subprocess.check_output(
            ["xcrun", "--show-sdk-path"], text=True, timeout=30).strip(),
        "configure_sha256": sha256(source / "configure"),
        "environment": {key: environment[key] for key in
                        ("CC", "CFLAGS", "PKG_CONFIG_LIBDIR", "CONFIG_SITE", "LC_ALL")},
        "steps": [], "status": "incomplete",
    }
    started = time.monotonic()
    for label, command in (
            ("configure", [
                str(source / "configure"), "--host=x86_64-apple-darwin",
                f"--prefix={prefix}", "--with-zlib=yes", "--with-bzip2=no",
                "--with-png=no", "--with-harfbuzz=no", "--with-brotli=no",
            ]),
            ("compile", ["/usr/bin/make", "-j4"]),
            ("local-install", ["/usr/bin/make", "install"])):
        remaining = 600 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("FreeType build budget exhausted")
        step = run_step(command, build_dir, environment, output / f"{label}.log", remaining)
        receipt["steps"].append(step)
        receipt["status"] = label if step["exit_code"] == 0 else f"{label}-failed"
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"]:
            print(f"{label} failed ({step['exit_code']}): {output / f'{label}.log'}",
                  file=sys.stderr)
            return step["exit_code"] if step["exit_code"] > 0 else 1
    library = prefix / "lib/libfreetype.6.dylib"
    if not library.is_file() or not library.stat().st_size:
        raise ValueError("No nonempty FreeType library after local install")
    receipt["artifact"] = {
        "path": str(library), "sha256": sha256(library),
        "file": subprocess.check_output(["file", str(library)], text=True, timeout=30),
        "linkage": subprocess.check_output(
            ["otool", "-L", str(library)], text=True, timeout=30),
    }
    if "x86_64" not in receipt["artifact"]["file"]:
        raise ValueError("FreeType library is not x86_64")
    receipt["status"] = "built-local-dependency"
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Built isolated FreeType: {library}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        return build(args.archive, args.output)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"calimocho FreeType build: ERROR {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
