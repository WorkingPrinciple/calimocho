"""Bounded protocol routes from already authenticated package manifests only."""
import hashlib
from pathlib import Path
import re
import struct

from tools.package_activation import identity, NAMESPACE
from tools.prepare_verified_activation import dos
from tools.verify_installed_appx import package_file, xml

NS = "{" + NAMESPACE + "}"
UAP = "{http://schemas.microsoft.com/appx/manifest/uap/windows10}"
MAX_APPLICATIONS = 32
REGISTRATION_SIZE = 3596


def field(value, capacity):
    encoded = value.encode("utf-16le") + b"\0\0"
    if len(encoded) > capacity * 2:
        raise ValueError("Protocol field exceeds bounded capacity")
    return encoded.ljust(capacity * 2, b"\0")


def application_registration(manifest, app_id, executable=None):
    metadata, blob = identity(manifest, app_id)
    if executable is not None:
        target = package_file(Path(manifest).parent, executable)
        metadata["executable"] = str(target)
        metadata["executable_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    image = "\\??\\" + dos(metadata["executable"])
    registration = blob + field(image, 1024)
    if len(registration) != REGISTRATION_SIZE:
        raise ValueError("Unexpected registration ABI")
    return metadata, registration


def routes(package):
    """Caller must verify the entire owned payload before calling this parser."""
    package = Path(package).resolve(strict=True)
    manifest = package_file(package, "AppxManifest.xml")
    tree = xml(manifest.read_bytes())
    applications = tree.findall(NS + "Applications/" + NS + "Application")
    if not 0 < len(applications) <= MAX_APPLICATIONS:
        raise ValueError("Unsupported application count")
    result, seen, app_ids = [], set(), set()
    for application in applications:
        app_id = application.get("Id", "")
        if app_id in app_ids:
            raise ValueError("Duplicate Application Id")
        app_ids.add(app_id)
        declarations = application.findall(
            NS + "Extensions/" + UAP + "Extension/" + UAP + "Protocol")
        if not declarations:
            continue
        for declaration in declarations:
            scheme = declaration.get("Name", "")
            if not re.fullmatch(r"[a-z][a-z0-9+.-]{0,62}", scheme):
                raise ValueError("Unsupported declared protocol scheme")
            if scheme in seen:
                raise ValueError("Ambiguous declared protocol scheme")
            extension = next(node for node in application.findall(NS + "Extensions/" + UAP + "Extension")
                             if declaration in list(node))
            if extension.get("Category") != "windows.protocol":
                raise ValueError("Protocol declaration has wrong category")
            metadata, registration = application_registration(
                manifest, app_id, extension.get("Executable"))
            seen.add(scheme)
            result.append({
                "scheme": scheme, "app_id": app_id,
                "entry_point": extension.get("EntryPoint", application.get("EntryPoint", "")),
                "metadata": metadata, "registration": registration,
            })
    return result


def artifacts(output, verified):
    """Use the verification receipt from prepare(), never an unverified directory."""
    if not verified.get("installed_content_verified") or not verified.get("signed_context_eligible"):
        raise ValueError("Require verified registered package snapshot")
    output = Path(output).resolve(strict=True)
    package = Path(verified["snapshot"]).resolve(strict=True)
    if package != output / "package":
        raise ValueError("Protocol snapshot must be owned by this activation")
    resolved = routes(package)
    if len(resolved) > 64:
        raise ValueError("Protocol route table exceeds bound")
    primary = (output / "registration.bin").read_bytes()
    if len(primary) != REGISTRATION_SIZE:
        raise ValueError("Unexpected primary registration size")
    registrations = [primary]
    for route in resolved:
        if route["registration"] not in registrations:
            registrations.append(route["registration"])
    if len(registrations) > MAX_APPLICATIONS:
        raise ValueError("Registration table exceeds bound")
    # Server-owned table and guest route table are separate trust surfaces.
    table = struct.pack("<III", 0x52505743, 1, len(registrations)) + b"".join(registrations)
    protocol = struct.pack("<III", 0x50505743, 1, len(resolved))
    protocol += b"".join(field(route["scheme"], 64) + route["registration"] +
                         field(route["entry_point"], 256)
                         for route in resolved)
    result = {"routes": [{key: value for key, value in route.items() if key != "registration"}
                        for route in resolved]}
    for name, content, key in (("registrations.bin", table, "server_registration_table"),
                               ("protocols.bin", protocol, "protocol_table")):
        path = output / name
        with path.open("xb") as stream:
            stream.write(content)
        path.chmod(0o600 if name == "registrations.bin" else 0o444)
        result[key] = str(path)
        result[key + "_sha256"] = hashlib.sha256(content).hexdigest()
    return result
