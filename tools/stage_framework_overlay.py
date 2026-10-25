"""Stage built package graph modules into a NEW isolated, unqualified engine."""
import argparse
import copy
import json
from pathlib import Path
import shutil

from tools.build_minidump_overlay import inventory
from tools.probe_wine_source import sha256

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/winehq-11.20/package-identity-01"
REGISTRY_SHA = "7aac753ae2146935772199e898802458fe8875e2b18e92f24c03f6c0f8987a6a"


def rebase(value, old, new):
    if isinstance(value, str):
        return str(new) + value[len(str(old)):] if value.startswith(str(old) + "/") else value
    if isinstance(value, list):
        return [rebase(item, old, new) for item in value]
    if isinstance(value, dict):
        result = {key: rebase(item, old, new) for key, item in value.items()}
        if "path" in result and "sha256" in result and str(result["path"]).startswith(str(new) + "/"):
            result["sha256"] = sha256(Path(result["path"]))
        return result
    return value


def stage(output):
    output = Path(output).resolve(strict=True)
    if not output.is_relative_to(REPO / "build") or (output / "install").exists():
        raise ValueError("Require a new owned install under build")
    predecessor = json.loads((BASE / "cell006-receipt.json").read_text())
    registry = Path(predecessor["registry"])
    if sha256(registry) != REGISTRY_SHA:
        raise ValueError("Package predecessor registry differs from pin")
    install = Path(predecessor["install"])
    before = inventory(install)
    if before != json.loads(Path(predecessor["inventory"]).read_text())["files"]:
        raise ValueError("Package predecessor inventory differs from frozen record")
    destination = output / "install"
    shutil.copytree(install, destination, symlinks=True)
    modules = {}
    for arch in ("i386", "x86_64"):
        for module in ("ntdll", "kernelbase", "combase"):
            source = output / "build/dlls" / module / (arch + "-windows") / (module + ".dll")
            target = f"lib/wine/{arch}-windows/{module}.dll"
            if not source.is_file() or not source.stat().st_size:
                raise ValueError("Missing built module: " + str(source))
            shutil.copy2(source, destination / target)
            modules[target] = {"sha256": sha256(source)}
    after = inventory(destination)
    if after != dict(before, **modules) or inventory(install) != before:
        raise ValueError("Unexpected install difference or predecessor mutation")
    data = json.loads(registry.read_text())
    engine = rebase(copy.deepcopy(data["engines"][0]), install, destination)
    engine["name"] = "calimocho-wine11.20-verified-framework-diagnostic"
    engine["version"] += " + explicit framework graph diagnostic (UNQUALIFIED)"
    engine["install_path"] = str(destination)
    engine["wine"] = str(destination / "bin/wine")
    engine["wineserver"] = str(destination / "bin/wineserver")
    engine["environment"]["WINELOADER"] = engine["wine"]
    engine["environment"]["WINESERVER"] = engine["wineserver"]
    engine["smoke_test"] = {"status": "not-run", "scope": "new framework diagnostic only"}
    for key in ("graphics_tests", "runtime_qualification", "qualification"):
        engine.pop(key, None)
    data["engines"] = [engine]
    new_registry = output / "framework.registry.local.UNQUALIFIED.json"
    with new_registry.open("x") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    receipt = {
        "status": "built-not-runtime-qualified", "runtime_executed": False,
        "predecessor_registry": str(registry), "predecessor_registry_sha256": REGISTRY_SHA,
        "predecessor_unchanged": True, "only_six_pe_modules_replaced": True,
        "registry": str(new_registry), "registry_sha256": sha256(new_registry),
        "install": str(destination), "modules": modules, "files": after,
        "wine_sha256": sha256(destination / "bin/wine"),
        "wineserver_sha256": sha256(destination / "bin/wineserver"),
        "source_patch_sha256": sha256(REPO / "patches/wine/0007-verified-framework-activation.patch"),
        "graph_header_sha256": sha256(REPO / "patches/wine/files/package_graph.h"),
    }
    path = output / "staging-receipt.json"
    with path.open("x") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(stage(parser.parse_args().output))
