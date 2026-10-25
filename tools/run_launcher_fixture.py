"""Owned synthetic package fixture; native execution requires the scheduler slot."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time

from tools.build_launcher_overlay import REPO
from tools.diagnose_package_activation import collect
from tools.package_activation import identity
from tools.package_protocols import routes, field
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256


def prepare(root, output):
    output.mkdir(exist_ok=False)
    package = output / "package"
    package.mkdir()
    for name in ("entry.exe", "target.exe"):
        shutil.copy2(root / "launcher-probe.exe", package / name)
    manifest = package / "AppxManifest.xml"
    manifest.write_text(
        '<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" '
        'xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">'
        '<Identity Name="Microsoft.GamingApp" Publisher="CN=FixtureOnly" '
        'Version="1.0.0.0" ProcessorArchitecture="x64"/>'
        '<Applications><Application Id="Entry" Executable="entry.exe"/>'
        '<Application Id="Target" Executable="target.exe" EntryPoint="Windows.FullTrustApplication">'
        '<Extensions><uap:Extension Category="windows.protocol"><uap:Protocol Name="fixture-full"/>'
        '</uap:Extension></Extensions></Application>'
        '<Application Id="Uwp" Executable="target.exe" EntryPoint="Fixture.App">'
        '<Extensions><uap:Extension Category="windows.protocol"><uap:Protocol Name="fixture-uwp"/>'
        '</uap:Extension></Extensions></Application></Applications></Package>')
    metadata, blob = identity(manifest, "Entry")
    (output / "identity.bin").write_bytes(blob)
    resolved = routes(package)
    registration = blob + field("\\??\\" + dos(metadata["executable"]), 1024)
    table = struct.pack("<III", 0x52505743, 1, 3) + registration
    table += b"".join(route["registration"] for route in resolved)
    (output / "registrations.bin").write_bytes(table)
    (output / "registrations.bin").chmod(0o600)
    protocols = struct.pack("<III", 0x50505743, 1, 2)
    protocols += b"".join(field(route["scheme"], 64) + route["registration"] +
                          field(route["entry_point"], 256) for route in resolved)
    (output / "protocols.bin").write_bytes(protocols)
    graph = struct.pack("<III", 0x47505743, 1, 1)
    graph += field(metadata["full_name"], 256) + field(metadata["family_name"], 256) + field(dos(package), 1024)
    (output / "graph.bin").write_bytes(graph)
    registration_text = (
        'Windows Registry Editor Version 5.00\r\n\r\n'
        '[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\Windows.System.Launcher]\r\n'
        '"DllPath"="' + dos(root / "install/lib/wine/x86_64-windows/windows.system.launcher.dll").replace("\\", "\\\\") +
        '"\r\n"ThreadingModel"="both"\r\n')
    (output / "launcher.reg").write_bytes(registration_text.encode("utf-16"))
    return metadata


def run(root, output):
    root, output = Path(root).resolve(strict=True), Path(output).resolve()
    if not root.is_relative_to(REPO / "build") or not output.is_relative_to(root):
        raise ValueError("Require a new fixture directory inside owned candidate")
    metadata = prepare(root, output)
    install = root / "install"
    entry = json.loads((root / "launcher.registry.local.UNQUALIFIED.json").read_text())["engines"][0]
    if entry["wine"] != str(install / "bin/wine") or entry["wineserver"] != str(install / "bin/wineserver"):
        raise ValueError("Registry does not name this candidate")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_", "CALIMOCHO_"))}
    env.update(entry["environment"])
    env.update(WINEPREFIX=str(output / "prefix"), WINEARCH="win64",
               WINEDLLOVERRIDES="mscoree,mshtml=;winemenubuilder.exe=d;explorer.exe=d;winedbg.exe=d",
               CALIMOCHO_PACKAGE_GRAPH=dos(output / "graph.bin"),
               CALIMOCHO_PACKAGE_PROTOCOLS=dos(output / "protocols.bin"),
               CALIMOCHO_LAUNCHER_MARKER=dos(output / "target-marker"))
    wine = ["/usr/bin/arch", "-x86_64", str(install / "bin/wine")]
    started = time.monotonic()
    receipt = {"scope": "synthetic host-admission fixture, NOT verified Microsoft payload or Xbox execution",
               "module_sha256": sha256(root / "windows.system.launcher.dll"),
               "server_sha256": sha256(install / "bin/wineserver"), "steps": []}
    try:
        setup = subprocess.run(wine + ["regedit", "/S", dos(output / "launcher.reg")],
                               env=env, capture_output=True, timeout=25)
        receipt["steps"].append({"step": "fresh-prefix-class-import", "exit_code": setup.returncode})
        if setup.returncode:
            raise RuntimeError("Fresh fixture class import failed")
        for option in ("-k", "-w"):
            stopped = subprocess.run([str(install / "bin/wineserver"), option],
                                     env=env, capture_output=True, timeout=8)
            receipt["steps"].append({"step": "setup-server" + option, "exit_code": stopped.returncode})
            if stopped.returncode not in (0, 1):
                raise RuntimeError("Fixture setup server cleanup failed")
        server_env = dict(env, CALIMOCHO_PACKAGE_REGISTRATION=str(output / "registrations.bin"))
        server = subprocess.run([str(install / "bin/wineserver"), "-p"], env=server_env,
                                capture_output=True, timeout=5)
        receipt["steps"].append({"step": "registered-server-start", "exit_code": server.returncode})
        if server.returncode:
            raise RuntimeError("Fixture registered server failed")
        argv = wine + [str(root / "package-activation-probe-v6.exe"), "--activate-diagnostic",
                       dos(output / "identity.bin"), dos(metadata["executable"])]
        observed = collect(argv, env, output, seconds=45)
        receipt["observed"] = observed
        if (observed["helper_exit"] != 0 or observed["metadata"].get("exit_code") != "0"
                or observed["collector_timeout"] or observed["trace_truncated"]):
            raise RuntimeError("Native Launcher fixture did not pass")
        if (output / "target-marker").read_bytes() != b"target-admitted":
            raise RuntimeError("No admitted target/URI fixture marker")
        receipt["result"] = "passed"
    finally:
        cleanup = []
        for option in ("-k", "-w"):
            result = subprocess.run([str(install / "bin/wineserver"), option],
                                    env=env, capture_output=True, timeout=8)
            cleanup.append({"option": option, "exit_code": result.returncode})
        opened = subprocess.run(["/usr/sbin/lsof", "+D", str(output / "prefix")],
                                capture_output=True, timeout=5)
        receipt.update(cleanup=cleanup, prefix_open_files=opened.returncode,
                       prefix_open_files_empty=not opened.stdout,
                       elapsed_seconds=time.monotonic() - started)
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if cleanup[-1]["exit_code"] or opened.returncode != 1:
        raise RuntimeError("Fixture cleanup incomplete")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--slot-granted", action="store_true", required=True)
    args = parser.parse_args()
    run(args.root, args.output)
