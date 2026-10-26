#!/usr/bin/env python3
"""Build pinned official TLS sources into one isolated x86_64 prefix."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

from probe_wine_source import REPO, fixed_install_prefix, relocate_pkgconfig, run_step, sha256


OPTIONS = {
    "gmp": ["--disable-assembly", "--enable-cxx=no"],
    "nettle": ["--disable-documentation", "--disable-openssl"],
    "libtasn1": ["--disable-doc"],
    "gnutls": [
        "--without-p11-kit", "--with-included-unistring", "--without-idn",
        "--disable-doc", "--disable-tools", "--disable-tests", "--disable-cxx",
        "--disable-nls", "--without-brotli", "--without-zstd",
        "--without-zlib",
        # Keep the build prefix out of the library; root-owned standard path, absent on macOS.
        "--with-system-priority-file=/etc/gnutls/config",
    ],
}


def checked_archive(path, pin):
    if sha256(path) != pin["sha256"]:
        raise ValueError(f"{pin['name']}: source archive checksum mismatch")


def build(archives, output):
    pins = json.loads((REPO / "versions.json").read_text())["tls_sources"]
    for pin in pins:
        checked_archive(archives / Path(pin["url"]).name, pin)
    output = output.resolve()
    if output == archives or output in archives.parents or archives in output.parents:
        raise ValueError("TLS build output and archives must be disjoint")
    output.mkdir(parents=True, exist_ok=False)
    prefix = output / "prefix"
    with fixed_install_prefix("tls", prefix) as fixed:
        result = build_in(archives, output, pins, prefix, fixed)
    relocate_pkgconfig(prefix, fixed)
    return result


def build_in(archives, output, pins, prefix, fixed):
    environment = {
        k: v for k, v in os.environ.items()
        if k not in {"CC", "CXX", "CFLAGS", "CPPFLAGS", "CXXFLAGS", "LDFLAGS",
                     "CPATH", "LIBRARY_PATH", "CONFIG_SITE"}
        and not k.startswith(("WINE", "CX_", "DYLD_", "PKG_CONFIG"))
    }
    environment.update(
        CC="/usr/bin/clang -arch x86_64", CXX="/usr/bin/clang++ -arch x86_64",
        # Map build paths out of __FILE__ strings and debug info (reproducible, no dev paths).
        CFLAGS=f"-O2 -ffile-prefix-map={output}/=tls-build/",
        # -Wl,-S: no debug map; its absolute object paths and mtimes would change LC_UUID.
        CPPFLAGS=f"-I{fixed}/include", LDFLAGS=f"-L{fixed}/lib -Wl,-S",
        PKG_CONFIG_LIBDIR=str(prefix / "lib/pkgconfig"),
        DYLD_FALLBACK_LIBRARY_PATH=f"{prefix}/lib:/usr/lib",
        CONFIG_SITE="/dev/null", LC_ALL="C",
    )
    receipt = {
        "architecture": "x86_64", "prefix": str(prefix), "install_prefix": str(fixed),
        "sources": pins,
        "environment": {k: environment[k] for k in (
            "CC", "CXX", "CFLAGS", "CPPFLAGS", "LDFLAGS", "PKG_CONFIG_LIBDIR",
            "DYLD_FALLBACK_LIBRARY_PATH", "CONFIG_SITE", "LC_ALL")},
        "compiler_sha256": sha256(Path("/usr/bin/clang")),
        "steps": [], "status": "incomplete",
    }
    started = time.monotonic()

    def save():
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    for pin in pins:
        name = pin["name"]
        source = output / f"{name}-{pin['version']}"
        with tarfile.open(archives / Path(pin["url"]).name) as stream:
            stream.extractall(output, filter="data")
        if not (source / "configure").is_file():
            raise ValueError(f"{name}: missing expected configure script")
        directory = output / f"{name}-build"
        directory.mkdir()
        commands = [
            ("configure", [str(source / "configure"), "--host=x86_64-apple-darwin",
                           f"--prefix={fixed}", "--disable-static", "--enable-shared"]
             + OPTIONS[name]),
            ("compile", ["/usr/bin/make", "-j4"]),
            ("install", ["/usr/bin/make", "-j1", "install"]),
        ]
        for label, command in commands:
            remaining = 1800 - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("TLS dependency build budget exhausted")
            step = run_step(command, directory, environment,
                            output / f"{name}-{label}.log", remaining)
            receipt["steps"].append(step)
            receipt["status"] = f"{name}-{label}"
            save()
            if step["exit_code"]:
                raise ValueError(f"{name} {label} failed: {step['log']}")
    artifacts = []
    for path in sorted((prefix / "lib").glob("*.dylib")):
        if path.is_symlink():
            continue
        info = subprocess.check_output(["file", str(path)], text=True, timeout=30)
        linkage = subprocess.check_output(["otool", "-L", str(path)], text=True, timeout=30)
        # otool's first line echoes the file's own path.
        loads = linkage.split("\n", 1)[1]
        if "x86_64" not in info or any(s in loads for s in ("/opt/homebrew", "/usr/local",
                                                               str(output))):
            raise ValueError(f"Unexpected architecture or global dependency in {path}")
        artifacts.append({"path": str(path), "sha256": sha256(path),
                          "file": info, "linkage": linkage})
    if not (prefix / "lib/libgnutls.dylib").is_file():
        raise ValueError("No GnuTLS shared library after local install")
    receipt.update(status="built-local-tls-dependencies", artifacts=artifacts)
    save()
    print(f"Built isolated TLS dependencies: {prefix}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        return build(args.archives.resolve(strict=True), args.output)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"calimocho TLS build: ERROR {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
