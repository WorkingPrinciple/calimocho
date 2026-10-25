"""Freeze REQ-104's experimental push-argument-buffer candidate after GPU tests."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from freeze_nms_shader_candidate import (
    BASE_DIGEST, BASE_LIBRARY, BUILD, LIBRARY, ROOT,
    derive_registry, digest, inventory, write_new,
)


ENGINE = "calimocho-wine11.20-gptk4b3-req104-push-ab-01"
PATCH = ROOT / "patches/moltenvk/0001-snapshot-metal3-push-argument-buffers.patch"
SOURCE = BUILD / "push-ab-01-source"
CONFIG = BUILD / "push-ab-01.xcconfig"
EVIDENCE = ROOT / "docs/evidence/req104-push-argument-buffers.json"


def prepare(base, receipt):
    if digest(base) != BASE_DIGEST:
        raise ValueError("Require unchanged 170ca base registry")
    result = json.loads(receipt.read_text())
    expected = {(label, mode) for label in ("baseline", "candidate")
                for mode in ("push", "template", "partial", "regular", "mixed", "graphics")}
    if (not result["all_oracles_passed"] or
            {(r["library"], r["mode"]) for r in result["results"]} != expected or
            result["advertised_per_stage_samplers"] != 16):
        raise ValueError("Require all baseline red and candidate green GPU oracles")
    library = SOURCE / "Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
    for row in result["results"]:
        expected_digest = BASE_LIBRARY if row["library"] == "baseline" else digest(library)
        if not row["oracle_passed"] or row["library_sha256"] != expected_digest:
            raise ValueError("Test library identity differs")
    actual_patch = subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--binary"])
    if actual_patch != PATCH.read_bytes():
        raise ValueError("Source differs from retained patch")
    subprocess.run(["git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(PATCH)],
                   check=True, timeout=15)
    subprocess.run(["codesign", "--verify", "--strict", str(library)], check=True, timeout=15)
    if subprocess.check_output(["lipo", "-archs", str(library)], text=True).strip() != "x86_64":
        raise ValueError("Require x86_64 candidate")
    if "/usr/local/" in subprocess.check_output(["otool", "-L", str(library)], text=True):
        raise ValueError("Nonportable dylib dependency")
    if "REQ104_PUSH_ARGUMENT_BUFFERS=1" not in CONFIG.read_text():
        raise ValueError("Experimental build define missing")
    pins = json.loads((ROOT / "versions.json").read_text())["req104_moltenvk"]
    revisions = {}
    directories = {"MoltenVK": SOURCE}
    directories.update({name: SOURCE / "External" / name for name in pins["dependencies"]})
    directories["SPIRV-Headers"] = SOURCE / "External/SPIRV-Tools/external/spirv-headers"
    identities = {"MoltenVK": pins["commit"], **pins["dependencies"]}
    for name, path in directories.items():
        revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                           text=True).strip()
        if revision != identities[name]:
            raise ValueError("Unexpected source revision " + name)
        revisions[name] = revision
    translator = SOURCE / "External/SPIRV-Cross"
    translator_patch = ROOT / pins["translator_patch"]["path"]
    if digest(translator_patch) != pins["translator_patch"]["sha256"]:
        raise ValueError("Shader patch pin differs")
    subprocess.run(["git", "-C", str(translator), "apply", "--reverse", "--check",
                    str(translator_patch)], check=True, timeout=15)
    return library, result, revisions


def freeze(base, receipt, output):
    library, result, revisions = prepare(base, receipt)
    if output.exists():
        raise ValueError("Never overwrite a candidate")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for file in (PATCH, EVIDENCE):
        committed = subprocess.check_output(["git", "show", f"{head}:{file.relative_to(ROOT)}"],
                                            cwd=ROOT)
        if committed != file.read_bytes():
            raise ValueError("Commit candidate source/evidence first")
    evidence = json.loads(EVIDENCE.read_text())
    if (evidence["candidate_library_sha256"] != digest(library) or
            evidence["test_receipt_sha256"] != digest(receipt) or
            evidence["patch_sha256"] != digest(PATCH)):
        raise ValueError("Committed evidence differs from tested inputs")
    data = json.loads(base.read_text())
    install = output / "install"
    original = Path(data["engines"][0]["install_path"])
    if digest(original / LIBRARY) != BASE_LIBRARY:
        raise ValueError("Base runtime changed")
    old_inventory = inventory(original)
    for item in data["engines"][0]["profile_assets"]["files"] + data["engines"][0]["dependencies"]:
        if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Base asset changed: " + item["path"])
    shutil.copytree(original, install, symlinks=True)
    if (install / LIBRARY).is_symlink():
        raise ValueError("Refuse symlinked replacement destination")
    shutil.copy2(library, install / LIBRARY)
    new_inventory = inventory(install)
    differences = [key for key in old_inventory.keys() | new_inventory.keys()
                   if old_inventory.get(key) != new_inventory.get(key)]
    if differences != [str(LIBRARY)] or inventory(original) != old_inventory:
        raise ValueError("Unexpected install differences: " + repr(differences))
    write_new(output / "inventory.FROZEN.json", new_inventory)
    registry = derive_registry(data, install)
    engine = registry["engines"][0]
    engine["name"] = ENGINE
    engine["version"] += " + experimental Metal3 push snapshots (ordinary limit16)"
    engine["game_acceptance"] = "Unqualified; no NMS or performance acceptance"
    engine.update(producerRepository="https://github.com/dragoshont/calimocho",
                  producerCommit=head, evidencePath=str(EVIDENCE.relative_to(ROOT)),
                  evidenceSha256=digest(EVIDENCE))
    engine["source_patches"].append({
        "path": str(PATCH), "sha256": digest(PATCH),
        "role": "Experimental Metal3 push snapshots; capability unchanged",
    })
    engine["build_evidence"] = {
        "producer_commit": head, "source_revisions": revisions,
        "path": str(EVIDENCE), "sha256": digest(EVIDENCE),
        "test_receipt": str(receipt), "test_receipt_sha256": digest(receipt),
        "inventory_sha256": digest(output / "inventory.FROZEN.json"),
        "config_sha256": digest(CONFIG), "qualified": False,
    }
    engine["integrity"] = {
        "status": "unchanged", "manifest_path": str(output / "inventory.FROZEN.json"),
        "manifest_sha256": digest(output / "inventory.FROZEN.json"),
        "scope": "Experimental source candidate; no runtime qualification",
    }
    write_new(output / "registry.SOURCE-FROZEN.json", registry)
    print(json.dumps({"engine": ENGINE, "registry": str(output / "registry.SOURCE-FROZEN.json"),
                      "registry_sha256": digest(output / "registry.SOURCE-FROZEN.json"),
                      "test_receipt_sha256": digest(receipt),
                      "qualified": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-registry", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.parent != BUILD.resolve():
        raise ValueError("Candidate must be a new child of owned build/req104")
    freeze(args.base_registry.resolve(), args.receipt.resolve(), destination)
