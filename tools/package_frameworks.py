"""Resolve only manifest-declared, verified x64 Microsoft framework packages."""
import re
from pathlib import Path
from tools.package_activation import NAMESPACE, publisher_id
from tools.verify_installed_appx import (
    MICROSOFT_PUBLISHER, package_file, verify_payload, xml,
)

NS = "{" + NAMESPACE + "}"


def version(text):
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", text):
        raise ValueError("Invalid framework version")
    result = tuple(int(part) for part in text.split("."))
    if any(part > 65535 for part in result):
        raise ValueError("Framework version field exceeds 16 bits")
    return result


def dependencies(manifest):
    return [node.attrib for node in manifest.findall(NS + "Dependencies/" + NS + "PackageDependency")]


def manifest_identity(manifest):
    entries = manifest.findall(NS + "Identity")
    if manifest.tag != NS + "Package" or len(entries) != 1:
        raise ValueError("Require one framework package identity")
    identity = dict(entries[0].attrib)
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{2,49}", identity.get("Name", ""))
            or identity.get("ProcessorArchitecture") != "x64"
            or identity.get("Publisher") != MICROSOFT_PUBLISHER
            or identity.get("ResourceId", "")):
        raise ValueError("Unsupported framework identity")
    identity["Version"] = ".".join(map(str, version(identity.get("Version", ""))))
    identity["family_name"] = identity["Name"] + "_" + publisher_id(identity["Publisher"])
    identity["full_name"] = "_".join((identity["Name"], identity["Version"], "x64", "",
                                      publisher_id(identity["Publisher"])))
    return identity


def classes(manifest, root):
    result = []
    for server in manifest.iter(NS + "InProcessServer"):
        paths = server.findall(NS + "Path")
        if len(paths) != 1 or not paths[0].text:
            raise ValueError("Require one in-process framework server path")
        dll = package_file(root, paths[0].text, allow_missing=True)
        for entry in server.findall(NS + "ActivatableClass"):
            name, threading = entry.get("ActivatableClassId", ""), entry.get("ThreadingModel", "")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,511}", name):
                raise ValueError("Invalid activatable class name")
            if threading not in ("both", "STA", "MTA"):
                raise ValueError("Unsupported activatable class threading model")
            result.append({"class": name, "dll": str(dll), "threading_model": threading,
                           "server_type": "in-process-dll", "server_file_present": dll.is_file()})
    return result


def resolve(application, source_root, roots, openssl):
    """No trust downgrade: cryptographic and complete content checks precede use."""
    source_root = Path(source_root).resolve(strict=True)
    queue = dependencies(xml(Path(application).read_bytes()))
    graph, by_name, registrations = [], {}, {}
    while queue:
        dependency = queue.pop(0)
        name = dependency.get("Name", "")
        minimum = version(dependency.get("MinVersion", ""))
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{2,49}", name)
                or dependency.get("Publisher") != MICROSOFT_PUBLISHER):
            raise ValueError("Unsupported declared framework dependency")
        if name in by_name:
            if version(by_name[name]["identity"]["Version"]) < minimum:
                raise ValueError("Conflicting framework minimum version")
            continue
        if len(graph) >= 16:
            raise ValueError("Framework graph exceeds bounded package count")
        root = source_root / name
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Declared framework missing or symlinked: " + name)
        verification = verify_payload(root, roots, openssl)
        manifest = xml(package_file(root, "AppxManifest.xml").read_bytes())
        info = manifest_identity(manifest)
        if (info["Name"] != name or version(info["Version"]) < minimum
                or manifest.findtext(NS + "Properties/" + NS + "Framework") != "true"):
            raise ValueError("Framework identity, version or type mismatch: " + name)
        entries = classes(manifest, root)
        local_classes = set()
        for entry in entries:
            key = entry["class"].casefold()
            if key in local_classes:
                raise ValueError("Ambiguous framework class: " + entry["class"])
            local_classes.add(key)
            entry["selected_in_graph_order"] = key not in registrations
            if key in registrations:
                entry["shadowed_by"] = registrations[key]["dll"]
            else:
                registrations[key] = entry
        record = {"identity": info, "path": str(root), "verification": verification,
                  "classes": entries, "signed_context_eligible": False}
        graph.append(record)
        by_name[name] = record
        queue.extend(dependencies(manifest))
    return graph
