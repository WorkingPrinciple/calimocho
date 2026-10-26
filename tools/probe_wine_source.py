#!/usr/bin/env python3
"""Configure pristine pinned WineHQ source and compile only its Wine server."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[1]
BUDGET_SECONDS = 30 * 60


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def run_step(command, directory, environment, log, timeout):
    with log.open("w") as stream:
        stream.write(json.dumps({"command": command, "cwd": str(directory)}) + "\n")
        stream.flush()
        process = subprocess.Popen(
            command, cwd=directory, env=environment, stdout=stream,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            code = 124
    return {"command": command, "exit_code": code, "timed_out": timed_out,
            "log": str(log), "log_sha256": sha256(log)}


FIXED_PREFIX_ROOT = Path("/tmp/calimocho-deps")


@contextlib.contextmanager
def fixed_install_prefixes(prefixes):
    """Serve real prefixes at /tmp/calimocho-deps/<name> while something builds (ADR-0081).

    prefixes maps a name to its real directory; yields the same names mapped to the fixed paths.
    A library's install name comes from --prefix, and ld derives its LC_UUID from the image,
    install name included. Configuring with a fixed path keeps both independent of the build
    directory. The symlinks let configure test programs, make install and build tools linked
    against the libraries (Wine's sfnt2fon) load them; DYLD_* variables cannot do that because
    SIP strips them from /bin/sh and /usr/bin/nice. One lock covers all names, so builds that
    need the paths run one after another; the symlinks are removed afterwards.
    """
    descriptor = os.open(f"{FIXED_PREFIX_ROOT}.lock",
                         os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    links = []
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            FIXED_PREFIX_ROOT.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = FIXED_PREFIX_ROOT.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError(f"{FIXED_PREFIX_ROOT} must be a directory you own")
        for name, real in prefixes.items():
            link = FIXED_PREFIX_ROOT / name
            if link.is_symlink():
                link.unlink()  # left by an interrupted build; we hold the lock
            elif link.exists():
                raise ValueError(f"{link} exists and is not a symlink")
            Path(real).mkdir(parents=True, exist_ok=True)
            link.symlink_to(real)
            links.append(link)
        yield {name: FIXED_PREFIX_ROOT / name for name in prefixes}
    finally:
        for link in links:
            link.unlink()
        os.close(descriptor)


@contextlib.contextmanager
def fixed_install_prefix(name, real):
    """fixed_install_prefixes for one dependency; yields its fixed path."""
    with fixed_install_prefixes({name: real}) as fixed:
        yield fixed[name]


def relocate_pkgconfig(prefix, fixed):
    """Point build-time .pc files from the fixed prefix to the real one; they are never shipped."""
    for pc in sorted((prefix / "lib/pkgconfig").glob("*.pc")):
        text = pc.read_text()
        if f"prefix={fixed}\n" not in text:
            raise ValueError(f"{pc.name} lacks prefix={fixed}")
        pc.write_text(text.replace(f"prefix={fixed}\n", f"prefix={prefix}\n", 1))
    for archive in (prefix / "lib").glob("*.la"):
        archive.unlink()


def probe(source, output, without_freetype=False):
    started = time.monotonic()
    source = source.resolve(strict=True)
    pin = json.loads((REPO / "versions.json").read_text())["winehq_probe"]
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True, timeout=30).strip()
    if commit != pin["commit"]:
        raise ValueError(f"Source commit differs from pin: {commit}")
    if subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain",
             "--untracked-files=all"], text=True, timeout=30):
        raise ValueError("Source must be pristine; no historical patches are applied")
    output = output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Build output must be outside the source tree")
    bison = shutil.which("bison")
    if not bison:
        raise ValueError("No installed bison; no dependency installation attempted")
    output.mkdir(parents=True, exist_ok=False)
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("WINE", "CX_", "DYLD_", "CFLAGS", "CPPFLAGS",
                               "CXXFLAGS", "LDFLAGS", "PKG_CONFIG"))
    }
    environment.update(CC="/usr/bin/clang -arch x86_64",
                       CXX="/usr/bin/clang++ -arch x86_64",
                       BISON=bison, LC_ALL="C", CONFIG_SITE="/dev/null")
    receipt = {
        "source": str(source), "commit": commit, "version": pin["version"],
        "source_tree": subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
            text=True, timeout=30).strip(),
        "configure_sha256": sha256(source / "configure"),
        "budget_seconds": BUDGET_SECONDS,
        "environment": {key: environment[key] for key in
                        ("CC", "CXX", "BISON", "LC_ALL", "CONFIG_SITE")},
        "steps": [], "status": "incomplete",
        "without_freetype": without_freetype,
        "runtime_executed": False, "installed": False,
        "qualification": "compile-only; no graphics or game evidence",
    }
    receipt_path = output / "probe-receipt.json"

    def save():
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    save()
    configure = [
        str(source / "configure"), "--host=x86_64-apple-darwin",
        "--enable-archs=x86_64,i386", "--disable-tests", "--without-x",
    ]
    if without_freetype:
        configure.append("--without-freetype")
    for label, command in (
            ("configure", configure),
            ("compile", ["/usr/bin/make", "-j4", "server/wineserver"])):
        remaining = BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            receipt["status"] = "budget-exhausted"
            save()
            return 124
        receipt["steps"].append(run_step(
            command, output, environment, output / f"{label}.log", remaining))
        code = receipt["steps"][-1]["exit_code"]
        if code:
            receipt["status"] = f"{label}-failed"
            save()
            print(f"{label} failed ({code}); see {output / f'{label}.log'}",
                  file=sys.stderr)
            return code if code > 0 else 1
        save()
    artifact = output / "server/wineserver"
    if not artifact.is_file() or not artifact.stat().st_size:
        receipt["status"] = "artifact-missing"
        save()
        raise ValueError("Compile exited zero without a nonempty Wine server")
    receipt["artifact"] = {
        "path": str(artifact), "sha256": sha256(artifact),
        "size": artifact.stat().st_size,
    }
    receipt["status"] = "compiled"
    save()
    print(f"Compiled Wine server only: {artifact}\nReceipt: {receipt_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--without-freetype", action="store_true",
        help="Explicit server-only diagnostic without fonts; not a usable game runtime")
    args = parser.parse_args()
    try:
        return probe(args.source, args.output, args.without_freetype)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"calimocho source probe: ERROR {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
