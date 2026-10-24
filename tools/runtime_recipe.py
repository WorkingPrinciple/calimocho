#!/usr/bin/env python3
"""Export one existing Ode runtime record without executing or installing it."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys


MAX_REGISTRY_BYTES = 8 * 1024 * 1024


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def text(value, label):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"{label}: expected a nonempty string")
    return value


def local_path(value, label):
    path = Path(text(value, label))
    if not path.is_absolute():
        raise ValueError(f"{label}: expected an absolute local path")
    return path


def resolve(path):
    try:
        return path.resolve(strict=True)
    except RuntimeError as error:
        raise ValueError(f"Cannot resolve runtime path: {path}: {error}") from error


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def records(value, label):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label}: expected an array of objects")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def export_recipe(registry_path, name):
    registry_path = local_path(str(registry_path), "registry")
    if not registry_path.is_file():
        raise ValueError(f"Registry must be a regular local file: {registry_path}")
    with registry_path.open("rb") as stream:
        raw = stream.read(MAX_REGISTRY_BYTES + 1)
    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValueError("Registry exceeds 8 MiB")
    registry = mapping(json.loads(raw, object_pairs_hook=unique_object,
                                  parse_constant=reject_constant), "registry")
    if type(registry.get("schema_version")) is not int or registry["schema_version"] != 1:
        raise ValueError("Expected Ode registry schema_version 1")
    engines = records(registry.get("engines"), "engines")
    names = [text(row.get("name"), "engine name") for row in engines]
    if len(set(names)) != len(names):
        raise ValueError("Ambiguous registry: duplicate engine names")
    if name not in names:
        raise ValueError(f"Unknown selected engine: {name}; no fallback is selected")
    selected = engines[names.index(name)]
    if selected.get("kind") != "free":
        raise ValueError("This recipe adapter accepts only existing free Wine records")
    for key in ("version", "source_url"):
        text(selected.get(key), key)
    install = local_path(selected.get("install_path"), "install_path")
    if not install.is_dir():
        raise ValueError(f"Missing installation: {install}")
    observed = {}

    def check_file(value, expected=None, executable=False, inside_install=False):
        path = local_path(value, "runtime file")
        resolved = resolve(path)
        if inside_install and not resolved.is_relative_to(resolve(install)):
            raise ValueError(f"Entrypoint escapes selected installation: {path}")
        if not resolved.is_file() or (executable and not os.access(path, os.X_OK)):
            raise ValueError(f"Missing file or non-executable entrypoint: {path}")
        actual = digest(path)
        if expected is not None:
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError(f"Invalid SHA-256 pin: {path}")
            if actual != expected:
                raise ValueError(f"SHA-256 mismatch: {path}")
        observed[str(path)] = {"resolved_path": str(resolved), "sha256": actual}

    pin = text(selected.get("sha256"), "wine sha256")
    check_file(selected.get("wine"), pin, executable=True, inside_install=True)
    # Never infer a wineserver from PATH or from another registered engine.
    check_file(selected.get("wineserver"), executable=True, inside_install=True)
    if Path(selected["wine"]).name == "calimocho-wine":
        raise ValueError("Retired calimocho-wine defaults are not an alternate runtime")
    environment = mapping(selected.get("environment"), "environment")
    for key, value in environment.items():
        text(key, "environment key")
        if "=" in key or not isinstance(value, str) or "\0" in value:
            raise ValueError(f"Invalid environment entry: {key}")
    for key, field in (("WINELOADER", "wine"), ("WINESERVER", "wineserver")):
        if key in environment and environment[key] != selected[field]:
            raise ValueError(f"{key} contradicts selected {field}")
    if "WINEPREFIX" in environment:
        raise ValueError("A runtime recipe cannot select or reuse a prefix")
    for dependency in records(selected.get("dependencies", []), "dependencies"):
        path = local_path(dependency.get("path"), "dependency path")
        if "sha256" in dependency:
            check_file(str(path), text(dependency["sha256"], "dependency sha256"))
        elif not path.is_dir():
            raise ValueError(f"Missing dependency directory: {path}")
    assets = mapping(selected.get("profile_assets", {}), "profile_assets")
    pins = {}
    for asset in records(assets.get("files", []), "profile_assets.files"):
        path = text(asset.get("path"), "asset path")
        pin = text(asset.get("sha256"), "asset sha256")
        check_file(path, pin)
        if path in pins and pins[path] != pin:
            raise ValueError(f"Conflicting asset pins: {path}")
        pins[path] = pin
    for overlay in records(selected.get("prefix_overlays", []), "prefix_overlays"):
        destination = text(overlay.get("destination"), "overlay destination")
        relative = PureWindowsPath(destination)
        if (relative.drive or relative.root or ".." in relative.parts
                or ":" in destination or relative == PureWindowsPath(".")):
            raise ValueError(f"Unsafe prefix overlay destination: {destination}")
        source = text(overlay.get("source"), "overlay source")
        pin = overlay.get("sha256", pins.get(source))
        if pin is None:
            raise ValueError(f"Unpinned overlay source: {source}")
        check_file(source, pin)
    for registration in records(
            selected.get("prefix_registry_imports", []), "prefix_registry_imports"):
        source = text(registration.get("source"), "registry import source")
        pin = registration.get("sha256", pins.get(source))
        if pin is None:
            raise ValueError(f"Unpinned registry import: {source}")
        check_file(source, pin)
    record_bytes = json.dumps(selected, sort_keys=True, separators=(",", ":"),
                              allow_nan=False).encode()
    return {
        "schema_version": 1,
        "host_architecture": text(registry.get("host_architecture"), "host_architecture"),
        "engines": [copy.deepcopy(selected)],
        "blocked": copy.deepcopy(registry.get("blocked", [])),
        "calimocho_recipe": {
            "kind": "local-reference-only",
            "source_registry": str(registry_path),
            "source_registry_sha256": hashlib.sha256(raw).hexdigest(),
            "engine_record_sha256": hashlib.sha256(record_bytes).hexdigest(),
            "observed_files": observed,
            "qualification": "not-tested-by-this-export",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--engine", required=True)
    args = parser.parse_args(argv)
    try:
        recipe = export_recipe(args.registry, args.engine)
    except (OSError, ValueError, RecursionError) as error:
        print(
            "calimocho: ERROR runtime recipe rejected\n"
            f"  Reason: {error}\n"
            "  Fix:    Select an intact explicit Ode registry record; no fallback is used.\n"
            "  Docs:   https://github.com/dragoshont/calimocho/docs/troubleshooting.md",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(recipe, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
