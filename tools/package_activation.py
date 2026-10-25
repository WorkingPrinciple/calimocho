"""Prepare explicit local package activation metadata, never infer registration."""

import argparse
import base64
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import struct
import xml.etree.ElementTree as ET


NAMESPACE = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
STANDARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
MAX_MANIFEST = 1024 * 1024


def publisher_id(publisher):
    digest = hashlib.sha256(publisher.encode("utf-16le")).digest()[:8]
    encoded = base64.b32encode(digest).decode().rstrip("=")
    return encoded.translate(str.maketrans(STANDARD, ALPHABET))


def identity(manifest, application):
    manifest = Path(manifest).resolve(strict=True)
    if manifest.stat().st_size > MAX_MANIFEST:
        raise ValueError("Manifest exceeds bounded parser size")
    raw = manifest.read_bytes()
    if b"<!" in raw or b"\0" in raw:
        raise ValueError("Only UTF-8 manifests without declarations/entities are supported")
    root = ET.fromstring(raw)
    tag = lambda name: "{" + NAMESPACE + "}" + name
    if root.tag != tag("Package"):
        raise ValueError("Unsupported package manifest namespace")
    identities = root.findall(tag("Identity"))
    applications = root.findall(tag("Applications"))
    if len(identities) != 1 or len(applications) != 1:
        raise ValueError("Require exactly one Identity and Applications element")
    package = identities[0].attrib
    name, publisher, version, arch = (package.get(k, "") for k in
                                       ("Name", "Publisher", "Version", "ProcessorArchitecture"))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{2,49}", name) or not publisher:
        raise ValueError("Invalid package name or publisher")
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ValueError("Invalid package version")
    if any(int(n) > 65535 for n in version.split(".")):
        raise ValueError("Package version field exceeds 16 bits")
    version = ".".join(str(int(n)) for n in version.split("."))
    if arch != "x64":
        raise ValueError("Only the isolated x64 activation path is supported")
    resource = package.get("ResourceId", "")
    if not re.fullmatch(r"[A-Za-z0-9.-]{0,30}", resource):
        raise ValueError("Invalid resource identifier")
    entries = [node for node in applications[0].findall(tag("Application"))
               if node.get("Id") == application]
    if len(entries) != 1 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9.]{0,63}", application):
        raise ValueError("Require one exact manifest Application Id")
    relative = PureWindowsPath(entries[0].get("Executable", ""))
    if not relative.parts or relative.anchor or relative.drive or any(
            part in (".", "..") or ":" in part for part in relative.parts):
        raise ValueError("Executable must be a package-relative path")
    executable = manifest.parent.joinpath(*relative.parts).resolve(strict=True)
    if not executable.is_file() or not executable.is_relative_to(manifest.parent):
        raise ValueError("Executable escapes the package root")
    suffix = publisher_id(publisher)
    family = name + "_" + suffix
    full = "_".join((name, version, arch, resource, suffix))
    values = (full, family, application)
    fields = []
    for value in values:
        data = value.encode("utf-16le") + b"\0\0"
        if len(data) > 512:
            raise ValueError("Package identity exceeds protocol capacity")
        fields.append(data.ljust(512, b"\0"))
    blob = struct.pack("<II", 2, 12 + 3 * 512) + b"".join(fields) + struct.pack("<I", 0)
    return {
        "full_name": full, "family_name": family, "app_id": application,
        "manifest": str(manifest), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "executable": str(executable),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "scope": "local activation metadata, not Store trust or capabilities",
    }, blob


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata, blob = identity(args.manifest, args.application)
    args.output.mkdir(exist_ok=False, parents=True)
    (args.output / "identity.bin").write_bytes(blob)
    (args.output / "activation.json").write_text(json.dumps(metadata, indent=2) + "\n")
