"""Create a verified owned package snapshot and host-only server registration."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from tools.package_activation import identity
from tools.verify_installed_appx import verify


def prepare(package, application, roots, openssl, output):
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
    args = parser.parse_args()
    prepare(args.package, args.application, args.root, args.openssl, args.output)


if __name__ == "__main__":
    main()
