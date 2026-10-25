"""Create a verified owned package snapshot and host-only server registration."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

from tools.package_activation import identity
from tools.verify_installed_appx import verify
from tools.package_frameworks import resolve


def dos(path):
    value = "Z:" + str(Path(path).resolve()).replace("/", "\\")
    if any(character in value for character in (';', '"', "\r", "\n", "\0")):
        raise ValueError("Unsupported package graph path characters")
    return value


def graph_artifacts(output, metadata, graph):
    entries = [{"full_name": metadata["full_name"], "family_name": metadata["family_name"],
                "path": str(output / "package")}]
    entries += [{"full_name": item["identity"]["full_name"],
                 "family_name": item["identity"]["family_name"], "path": item["path"]}
                for item in graph]
    blob = struct.pack("<III", 0x47505743, 1, len(entries))
    for entry in entries:
        for value, capacity in ((entry["full_name"], 256), (entry["family_name"], 256),
                                (dos(entry["path"]), 1024)):
            data = value.encode("utf-16le") + b"\0\0"
            if len(data) > capacity * 2:
                raise ValueError("Package graph field exceeds capacity")
            blob += data.ljust(capacity * 2, b"\0")
    graph_path = output / "package-graph.bin"
    with graph_path.open("xb") as stream:
        stream.write(blob)
    graph_path.chmod(0o444)
    lines = ["Windows Registry Editor Version 5.00", ""]
    for package in graph:
        for entry in package["classes"]:
            if not entry["selected_in_graph_order"]:
                continue
            lines.append("[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\"
                         + entry["class"] + "]")
            for key, value in (("DllPath", dos(entry["dll"])),
                               ("ThreadingModel", entry["threading_model"])):
                lines.append('"' + key + '"="' + value.replace("\\", "\\\\") + '"')
            lines.append("")
    registration = output / "framework-classes.reg"
    with registration.open("xb") as stream:
        stream.write(("\r\n".join(lines) + "\r\n").encode("utf-16"))
    registration.chmod(0o444)
    return {"graph": str(graph_path), "graph_sha256": hashlib.sha256(blob).hexdigest(),
            "framework_registration": str(registration),
            "framework_registration_sha256": hashlib.sha256(registration.read_bytes()).hexdigest(),
            "graph_entries": entries, "frameworks": graph,
            "environment": {"CALIMOCHO_PACKAGE_GRAPH": dos(graph_path)}}


def prepare(package, application, roots, openssl, output, framework_root=None):
    package = Path(package).resolve(strict=True)
    output = Path(output).resolve()
    if output == package or package in output.parents:
        raise ValueError("Activation output must be outside the source package")
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "package"
    shutil.copytree(package, snapshot, symlinks=True)
    progress = {"installed_content_verified": False, "signed_context_eligible": False}
    try:
        receipt = verify(snapshot, application, roots, openssl, progress)
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as error:
        # Keep the failed snapshot and partial evidence, but never registration bytes.
        progress["error"] = str(error)
        (output / "verification-failed.json").write_text(json.dumps(progress, indent=2) + "\n")
        raise
    progress.update(receipt)
    metadata, blob = identity(snapshot / "AppxManifest.xml", application)
    if framework_root is not None:
        # Resolve authenticated declarations first, then reverify the copied bytes.
        observed = resolve(snapshot / "AppxManifest.xml", framework_root, roots, openssl)
        destination = output / "frameworks"
        destination.mkdir()
        for item in observed:
            shutil.copytree(item["path"], destination / item["identity"]["Name"], symlinks=True)
        graph = resolve(snapshot / "AppxManifest.xml", destination, roots, openssl)
        progress.update(graph_artifacts(output, metadata, graph))
        for path in destination.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        for path in sorted(destination.rglob("*"), reverse=True):
            if path.is_dir():
                path.chmod(0o555)
        destination.chmod(0o555)
    image = "\\??\\Z:" + metadata["executable"].replace("/", "\\")
    image_bytes = image.encode("utf-16le") + b"\0\0"
    if len(image_bytes) > 2048:
        raise ValueError("Verified executable exceeds server registration capacity")
    registration = blob + image_bytes.ljust(2048, b"\0")
    for path in snapshot.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    for path in sorted(snapshot.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
    snapshot.chmod(0o555)
    for name, content in (("identity.bin", blob), ("registration.bin", registration)):
        descriptor = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    progress.update({
        "snapshot": str(snapshot), "executable_dos": image[4:],
        "registration_sha256": hashlib.sha256(registration).hexdigest(),
        "identity_sha256": hashlib.sha256(blob).hexdigest(),
        "host_authority": "server startup record, not a guest-supplied verified flag",
        "limitation": "Wine is not a sandbox against another native process running as this host user",
    })
    (output / "verification.json").write_text(json.dumps(progress, indent=2) + "\n")
    return progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--framework-root", type=Path)
    args = parser.parse_args()
    prepare(args.package, args.application, args.root, args.openssl, args.output, args.framework_root)


if __name__ == "__main__":
    main()
