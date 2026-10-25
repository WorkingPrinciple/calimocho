"""Prepare and freeze REQ-104's isolated, unadmitted shader-only candidate."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/req104"
CANDIDATE = BUILD / "candidate-01"
EVIDENCE = Path("docs/evidence/req104-nms-shader-candidate.json")
BASE_DIGEST = "170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609"
BASE_LIBRARY = "4b4bc6fe5fd68f8e2fda12b6a153e69f838d78f72623d062ebcb42374833a385"
LIBRARY = Path("lib/wine/x86_64-unix/libMoltenVK.dylib")
ENGINE = "calimocho-wine11.20-gptk4b3-req104-shader-candidate"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
    path.chmod(0o444)


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        name = str(path.relative_to(root))
        if path.is_symlink():
            result[name] = {"symlink": str(path.readlink())}
        elif path.is_file():
            result[name] = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777}
    return result


def source_audit(pin):
    source = BUILD / "MoltenVK"
    directories = {"MoltenVK": source}
    directories.update({name: source / "External" / name for name in pin["dependencies"]})
    directories["SPIRV-Headers"] = source / "External/SPIRV-Tools/external/spirv-headers"
    identities = {"MoltenVK": pin["commit"], **pin["dependencies"]}
    result = {}
    for name, path in directories.items():
        actual = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True, timeout=10).strip()
        changes = subprocess.check_output(
            ["git", "-C", str(path), "diff", "--numstat"], text=True, timeout=10)
        staged = subprocess.check_output(
            ["git", "-C", str(path), "diff", "--cached", "--numstat"], text=True, timeout=10)
        expected = "9\t0\tspirv_msl.cpp\n" if name == "SPIRV-Cross" else ""
        if actual != identities[name] or changes != expected or staged:
            raise ValueError("Unexpected source identity or changes: " + name)
        result[name] = {"commit": actual, "tracked_changes": changes}
    translator = source / "External/SPIRV-Cross"
    subprocess.run(["git", "-C", str(translator), "apply", "--reverse", "--check",
                    str(ROOT / pin["translator_patch"]["path"])], check=True, timeout=10)
    result["SPIRV-Cross"]["compiled_file_sha256"] = digest(translator / "spirv_msl.cpp")
    return result


def derive_registry(data, install):
    data = copy.deepcopy(data)
    if len(data["engines"]) != 1:
        raise ValueError("Require the exact single-engine base registry")
    entry = data["engines"][0]
    old = entry["install_path"]

    def rebase(value):
        if isinstance(value, str):
            if value == old or value.startswith(old + "/"):
                return str(install) + value[len(old):]
            return value
        if isinstance(value, list):
            return [rebase(item) for item in value]
        if isinstance(value, dict):
            return {key: rebase(item) for key, item in value.items()}
        return value

    entry = rebase(entry)
    for key in ("smoke_test", "graphics_tests", "tls_positive_test", "tls_negative_test",
                "integrity", "build_evidence", "game_acceptance"):
        entry.pop(key, None)
    entry["name"] = ENGINE
    entry["version"] += " + unadmitted REQ104 shader backport"
    entry["game_acceptance"] = "Not tested; REQ80/S2 admission and parent-authorized Ode Play required"
    entry["smoke_test"] = {"status": "not-run", "scope": "No runtime qualification inherited"}
    entry["source_patches"].append({
        "path": str(ROOT / "patches/spirv-cross/0001-keep-vertex-output-block-in-thread-storage.patch"),
        "sha256": digest(ROOT / "patches/spirv-cross/0001-keep-vertex-output-block-in-thread-storage.patch"),
        "role": "SPIRV-Cross upstream PR2719 backport, not a Wine patch",
    })
    for asset in entry["profile_assets"]["files"] + entry["dependencies"]:
        if asset.get("path") == str(install / LIBRARY):
            asset["sha256"] = digest(install / LIBRARY)
    data["engines"] = [entry]
    return data


def audit(base_registry):
    if digest(base_registry) != BASE_DIGEST:
        raise ValueError("Require unchanged active frozen 170ca4ad registry")
    data = json.loads(base_registry.read_text())
    entry = data["engines"][0]
    base = Path(entry["install_path"])
    library = BUILD / "MoltenVK/Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
    if digest(base / LIBRARY) != BASE_LIBRARY or digest(library) == BASE_LIBRARY:
        raise ValueError("Require unchanged base library and genuinely rebuilt candidate")
    subprocess.run(["codesign", "--verify", "--strict", library], check=True, timeout=30)
    pin = json.loads((ROOT / "versions.json").read_text())["req104_moltenvk"]
    if digest(ROOT / pin["translator_patch"]["path"]) != pin["translator_patch"]["sha256"]:
        raise ValueError("Patch pin differs")
    sources = source_audit(pin)
    regression = BUILD / "regression-01/receipt.json"
    if json.loads(regression.read_text())["status"] != "source-regression-passed":
        raise ValueError("Require completed exact-error compiler regression")
    before = inventory(base)
    for item in entry["profile_assets"]["files"] + entry["dependencies"]:
        if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Base asset/dependency differs: " + item["path"])
    CANDIDATE.mkdir(parents=True, exist_ok=False)
    install = CANDIDATE / "install"
    shutil.copytree(base, install, symlinks=True)
    destination = install / LIBRARY
    if destination.is_symlink():
        raise ValueError("Refuse to replace a symlinked library")
    shutil.copy2(library, destination)
    after = inventory(install)
    changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
    if changed != [str(LIBRARY)] or inventory(base) != before:
        raise ValueError("Require exactly one changed module and unchanged source runtime")
    derived = derive_registry(data, install)
    write_new(CANDIDATE / "registry.UNQUALIFIED.json", derived)
    manifest = CANDIDATE / "inventory.FROZEN.json"
    write_new(manifest, after)
    build_files = [
        BUILD / "owned.xcconfig", regression, library,
        BUILD / "dependency-build.log", BUILD / "moltenvk-relinked-build.log",
        BUILD / "dependencies-derived/Build/Products/Release/libSPIRVCross.a",
        BUILD / "sampler-limits.json", BUILD / "vulkan-sampler-limits",
    ]
    evidence = {
        "requirement": "REQ-104", "status": "source-tested-not-runtime-admitted",
        "producerRepository": "https://github.com/dragoshont/calimocho",
        "upstreamWineCommit": entry["source_commit"],
        "base_registry": {"path": str(base_registry), "sha256": BASE_DIGEST},
        "base_library_sha256": BASE_LIBRARY,
        "candidate_library_sha256": digest(destination),
        "candidate_engine": ENGINE, "source_pins": pin,
        "verified_sources": sources,
        "compiler_regression": json.loads(regression.read_text()),
        "native_limits_query": json.loads((BUILD / "sampler-limits.json").read_text()),
        "inventory": {"path": str(manifest), "sha256": digest(manifest)},
        "only_changed_module": str(LIBRARY),
        "base_inventory_unchanged": True,
        "immutable_inputs": [{"path": str(path), "sha256": digest(path)} for path in build_files],
        "source_patch": {"path": pin["translator_patch"]["path"],
                         "sha256": pin["translator_patch"]["sha256"]},
        "unqualified_registry_sha256": digest(CANDIDATE / "registry.UNQUALIFIED.json"),
        "limitations": [
            "Sampler capacity unchanged; startup warning unresolved",
            "Integer-format blending warning separate and unresolved",
            "No Vulkan pipeline execution or NMS rendering acceptance",
            "No runtime, prefix, settings or active registry changed",
            "REQ80/S2 admission and parent-authorized Ode Play required",
        ],
    }
    write_new(ROOT / EVIDENCE, evidence)
    print(json.dumps({"evidence": str(EVIDENCE), "sha256": digest(ROOT / EVIDENCE)}, indent=2))


def freeze():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    committed = subprocess.check_output(["git", "show", commit + ":" + str(EVIDENCE)], cwd=ROOT)
    if committed != (ROOT / EVIDENCE).read_bytes():
        raise ValueError("Evidence must be committed unchanged")
    evidence = json.loads(committed)
    patch = evidence["source_patch"]
    if digest(ROOT / patch["path"]) != patch["sha256"]:
        raise ValueError("Source patch changed after audit")
    if source_audit(evidence["source_pins"]) != evidence["verified_sources"]:
        raise ValueError("Source identity changed after audit")
    for item in evidence["immutable_inputs"] + [evidence["inventory"], evidence["base_registry"]]:
        if digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Frozen input changed: " + item["path"])
    if inventory(CANDIDATE / "install") != json.loads(Path(evidence["inventory"]["path"]).read_text()):
        raise ValueError("Candidate inventory changed after audit")
    unqualified = CANDIDATE / "registry.UNQUALIFIED.json"
    if digest(unqualified) != evidence["unqualified_registry_sha256"]:
        raise ValueError("Unqualified registry changed")
    data = json.loads(unqualified.read_text())
    entry = data["engines"][0]
    for item in entry["profile_assets"]["files"] + entry["dependencies"]:
        if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Candidate asset/dependency changed: " + item["path"])
    entry.update(producerRepository=evidence["producerRepository"], producerCommit=commit,
                 evidencePath=str(EVIDENCE), evidenceSha256=digest(ROOT / EVIDENCE))
    entry["integrity"] = {"status": "unchanged",
                          "manifest_path": evidence["inventory"]["path"],
                          "manifest_sha256": evidence["inventory"]["sha256"],
                          "scope": "Source-built shader candidate only; no runtime qualification"}
    output = CANDIDATE / "registry.SOURCE-FROZEN.json"
    write_new(output, data)
    print(json.dumps({"registry": str(output), "sha256": digest(output),
                      "producerCommit": commit, "engine": ENGINE}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "freeze"))
    parser.add_argument("--base-registry", type=Path)
    args = parser.parse_args()
    if args.operation == "audit":
        if args.base_registry is None:
            parser.error("audit requires --base-registry")
        audit(args.base_registry)
    else:
        freeze()
