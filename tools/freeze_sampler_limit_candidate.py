"""Freeze an unexecuted REQ-104 128-gated candidate for serialized GPU testing."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from freeze_nms_shader_candidate import (
    BASE_DIGEST, BASE_LIBRARY, BUILD, LIBRARY, ROOT,
    derive_registry, digest, inventory, write_new,
)


SOURCE = BUILD / "push-ab-02-source"
OUTPUT = BUILD / "push-ab-candidate-02"
PATCH = ROOT / "patches/moltenvk/0002-gate-128-samplers-to-metal3-argument-buffers.patch"
EVIDENCE = ROOT / "docs/evidence/req104-sampler-limit-candidate.json"
CONFIG = BUILD / "push-ab-02.xcconfig"
ENGINE = "calimocho-wine11.20-gptk4b3-req104-push-ab-128-02"


def audit(base):
    if digest(base) != BASE_DIGEST:
        raise ValueError("Base registry changed")
    data = json.loads(base.read_text())
    original = Path(data["engines"][0]["install_path"])
    if digest(original / LIBRARY) != BASE_LIBRARY:
        raise ValueError("Base library changed")
    library = SOURCE / "Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
    subprocess.run(["codesign", "--verify", "--strict", str(library)], check=True)
    if subprocess.check_output(["lipo", "-archs", str(library)], text=True).strip() != "x86_64":
        raise ValueError("Expected x86_64")
    if "/usr/local/" in subprocess.check_output(["otool", "-L", str(library)], text=True):
        raise ValueError("Nonportable dependency")
    if subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--binary"]) != PATCH.read_bytes():
        raise ValueError("Source differs from complete variant patch")
    subprocess.run(["git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(PATCH)], check=True)
    pin = json.loads((ROOT / "versions.json").read_text())["req104_moltenvk"]
    if "REQ104_SAMPLER_LIMIT=128" not in CONFIG.read_text():
        raise ValueError("Expected experimental128 build definition")
    paths = {"MoltenVK": SOURCE, **{name: SOURCE / "External" / name for name in pin["dependencies"]}}
    paths["SPIRV-Headers"] = SOURCE / "External/SPIRV-Tools/external/spirv-headers"
    identities = {"MoltenVK": pin["commit"], **pin["dependencies"]}
    for name, path in paths.items():
        if subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                   text=True).strip() != identities[name]:
            raise ValueError("Unexpected source revision: " + name)
        if name != "MoltenVK":
            changes = subprocess.check_output(["git", "-C", str(path), "diff", "--numstat"],
                                              text=True)
            if changes != ("9\t0\tspirv_msl.cpp\n" if name == "SPIRV-Cross" else ""):
                raise ValueError("Unexpected dependency changes: " + name)
    translator_patch = ROOT / pin["translator_patch"]["path"]
    if digest(translator_patch) != pin["translator_patch"]["sha256"]:
        raise ValueError("Shader patch pin changed")
    subprocess.run(["git", "-C", str(paths["SPIRV-Cross"]), "apply", "--reverse", "--check",
                    str(ROOT / pin["translator_patch"]["path"])], check=True)
    return {
        "requirement": "REQ-104", "engine": ENGINE,
        "status": "source-built-awaiting-promoted-candidate-gpu-tests",
        "qualified": False, "advertised_sampler_limit_if_gated": 128,
        "fallback_limit": 16, "direct_metal_slot_limit_unchanged": True,
        "candidate_library_sha256": digest(library), "patch_sha256": digest(PATCH),
        "build_config_sha256": digest(CONFIG), "source_revisions": identities,
        "base_registry_sha256": BASE_DIGEST,
        "prior_candidate_sweeps": {
            str(width): digest(BUILD / f"sweep-01-results-{width}/receipt.json")
            for width in (17, 32, 64, 128)
        },
        "limitations": [
            "Prior sweeps used push-ab-01, not this binary",
            "128 prior aggregate failed: corrected immutable combined fixture requires rerun",
            "Promoted limit and variable-count query require new GPU suite",
            "No NMS warning removal or performance acceptance",
            "REQ80/S2 runtime admission required",
            "No remote publication or default changes",
        ],
        "apple_limit_source": "https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf",
        "apple_limit_table_date": "2026-05-21",
        "apple_limit_page": 8,
        "apple_limit_observed": "Apple6 128; Apple7/8 996; Apple9/10 500K samplers per stage in argument buffers",
    }


def freeze(base):
    observed = audit(base)
    if json.loads(EVIDENCE.read_text()) != observed:
        raise ValueError("Evidence no longer matches source inputs")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    for path in (EVIDENCE, PATCH):
        if subprocess.check_output(["git", "show", f"{head}:{path.relative_to(ROOT)}"]) != path.read_bytes():
            raise ValueError("Commit evidence and patch first")
    if OUTPUT.exists():
        raise ValueError("Never overwrite a candidate")
    data = json.loads(base.read_text())
    original = Path(data["engines"][0]["install_path"])
    for item in data["engines"][0]["profile_assets"]["files"] + data["engines"][0]["dependencies"]:
        if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Base asset changed: " + item["path"])
    before = inventory(original)
    install = OUTPUT / "install"
    shutil.copytree(original, install, symlinks=True)
    if (install / LIBRARY).is_symlink():
        raise ValueError("Refuse symlinked replacement")
    shutil.copy2(SOURCE / "Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib",
                 install / LIBRARY)
    after = inventory(install)
    if ({key for key in before.keys() | after.keys() if before.get(key) != after.get(key)} !=
            {str(LIBRARY)} or inventory(original) != before):
        raise ValueError("Unexpected inventory changes")
    manifest = OUTPUT / "inventory.FROZEN.json"
    write_new(manifest, after)
    registry = derive_registry(data, install)
    entry = registry["engines"][0]
    entry.update(name=ENGINE, producerRepository="https://github.com/dragoshont/calimocho",
                 producerCommit=head, evidencePath=str(EVIDENCE.relative_to(ROOT)),
                 evidenceSha256=digest(EVIDENCE),
                 game_acceptance="Not tested; promoted candidate GPU suite and REQ80 admission required")
    entry["version"] += " + experimental gated128 push snapshots, GPU tests pending"
    entry["source_patches"].append({"path": str(PATCH), "sha256": digest(PATCH),
                                    "role": "Complete variant, includes push snapshots; apply instead of patch0001"})
    entry["build_evidence"] = observed
    entry["integrity"] = {"status": "unchanged", "manifest_path": str(manifest),
                          "manifest_sha256": digest(manifest), "scope": "Source-only, unqualified"}
    target = OUTPUT / "registry.SOURCE-FROZEN.json"
    write_new(target, registry)
    print(json.dumps({"registry": str(target), "registry_sha256": digest(target),
                      "producerCommit": head, "qualified": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "freeze"))
    parser.add_argument("--base-registry", required=True, type=Path)
    args = parser.parse_args()
    if args.operation == "audit":
        write_new(EVIDENCE, audit(args.base_registry.resolve()))
    else:
        freeze(args.base_registry.resolve())
