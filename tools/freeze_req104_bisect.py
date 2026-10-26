"""Audit and freeze REQ-104 bisect candidates A, B and C (MoltenVK only).

audit:  verifies sources, patches, build config, translator archive, signature,
        architecture, linkage and committed test receipts, then clones the
        170ca install with exactly one replaced file and writes evidence.
freeze: after the evidence is committed, binds each registry to that commit.
No Wine, no game, no prefix and no installed or default engine is touched.
"""

import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

from freeze_nms_shader_candidate import BASE_DIGEST, BASE_LIBRARY, LIBRARY, ROOT, digest, inventory, write_new


BUILD = ROOT / "build/req104"
FROZEN = BUILD / "frozen"
WINE_SHA256 = "f6d0546fad2d0dafaa09a9fe6cabe75bb070567df6b0933ecd3622dcb6349194"
WINESERVER_SHA256 = "e3ec4e7e76cee273f17d5fa3459902642f73d6921e94c576aa74e8cdbdcd7da1"
TEAM = "M62Z4M5EUY"
CLEAN_ARCHIVE = "9b0ffcf11dc1c48d7280dea635673d2e8ddce3f38a245b407500fd08ecc3afaf"
PR2719_ARCHIVE = "b7dfdd453f4846d664c636fc459a1e4220d684b0699643d2d687adcb4ea9756f"
PR2719_PATCH = "patches/spirv-cross/0001-keep-vertex-output-block-in-thread-storage.patch"
PUSH_PATCH = "patches/moltenvk/0002-gate-128-samplers-to-metal3-argument-buffers.patch"
NAMESPACE_PATCH = "patches/moltenvk/0003-namespace-req104-pipeline-cache-uuid.patch"
REUSE_PATCH = "patches/moltenvk/0004-reuse-metal3-push-snapshots-until-changed.patch"
BISECT_RECEIPT = "docs/evidence/req104-bisect-tests.json"
REPRO = BUILD / "R-repro-source/Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
PRIVATE = "MVK_USE_METAL_PRIVATE_API=1"
PUSH = ["REQ104_PUSH_ARGUMENT_BUFFERS=1", "REQ104_SAMPLER_LIMIT=128"]
CANDIDATES = {
    "A": {"engine": "calimocho-req104-A-sampler", "dir": "A-sampler",
          "defines": [PRIVATE, *PUSH, "REQ104_CACHE_NAMESPACE=0x52344131"],
          "moltenvk_patches": [PUSH_PATCH, NAMESPACE_PATCH], "pr2719": False,
          "archive": CLEAN_ARCHIVE, "limit": 128, "namespace": "52344131",
          "sampler_receipt": "docs/evidence/req104-bisect-A-sampler-tests.json",
          "version": "REQ104 bisect A: gated128 push argument buffers, no PR2719, cache namespace R4A1",
          "expected_nms_change": "Sampler warning removed by an honest 128 limit; address-space "
                                 "pipeline failures unchanged from 170ca"},
    "B": {"engine": "calimocho-req104-B-addrspace", "dir": "B-addrspace",
          "defines": [PRIVATE, "REQ104_CACHE_NAMESPACE=0x52344231"],
          "moltenvk_patches": [NAMESPACE_PATCH], "pr2719": True,
          "archive": PR2719_ARCHIVE, "limit": 16, "namespace": "52344231",
          "sampler_receipt": None,
          "version": "REQ104 bisect B: PR2719 shader backport only, cache namespace R4B1",
          "expected_nms_change": "Address-space pipeline failures fixed; sampler warning still shown "
                                 "(limit 16, unchanged)"},
    "C": {"engine": "calimocho-req104-C-pushcache", "dir": "C-pushcache",
          "defines": [PRIVATE, *PUSH, "REQ104_CACHE_NAMESPACE=0x52344331"],
          "moltenvk_patches": [PUSH_PATCH, NAMESPACE_PATCH, REUSE_PATCH], "pr2719": False,
          "archive": CLEAN_ARCHIVE, "limit": 128, "namespace": "52344331",
          "sampler_receipt": "docs/evidence/req104-bisect-C-pushcache-tests.json",
          "version": "REQ104 bisect C: gated128 push argument buffers with snapshot reuse, no PR2719, "
                     "cache namespace R4C1",
          "expected_nms_change": "As A, without A's per-bind push snapshot copy when push data is unchanged"},
}


def out(command, **kwargs):
    return subprocess.check_output(list(map(str, command)), text=True, timeout=120, **kwargs)


def library_paths(spec):
    source = BUILD / f"{spec['dir']}-source"
    return (source, source / "Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib",
            BUILD / "signed" / spec["dir"] / "libMoltenVK.dylib")


def same_except_linkedit_vmsize(stripped, built):
    """codesign --remove-signature keeps the grown __LINKEDIT vmsize; nothing else may differ."""
    if len(stripped) != len(built) or struct.unpack_from("<I", built, 0)[0] != 0xFEEDFACF:
        return False
    ncmds = struct.unpack_from("<I", built, 16)[0]
    offset, field = 32, None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", built, offset)
        if cmd == 0x19 and built[offset + 8:offset + 24].rstrip(b"\0") == b"__LINKEDIT":
            field = offset + 32
        offset += size
    if field is None:
        return False
    return stripped[:field] == built[:field] and stripped[field + 8:] == built[field + 8:]


def verify_signature(library):
    subprocess.run(["codesign", "--verify", "--strict", str(library)], check=True, timeout=60)
    details = subprocess.run(["codesign", "-dvvv", str(library)], capture_output=True, text=True,
                             timeout=60, check=True).stderr
    authority = re.search(r"^Authority=(Developer ID Application: .*\(" + TEAM + r"\))$", details, re.M)
    flags = re.search(r"^CodeDirectory .*flags=(\S+)", details, re.M)
    stamp = re.search(r"^Timestamp=(.+)$", details, re.M)
    if not (authority and flags and "runtime" in flags.group(1) and stamp
            and f"TeamIdentifier={TEAM}" in details):
        raise ValueError("Require Developer ID, hardened runtime and secure timestamp: " + str(library))
    return {"verify_strict": "valid on disk; satisfies its Designated Requirement",
            "authority": authority.group(1), "team": TEAM, "flags": flags.group(1),
            "timestamp": stamp.group(1)}


def audit_sources(label, spec, source):
    pin = json.loads((ROOT / "versions.json").read_text())["req104_moltenvk"]
    paths = {"MoltenVK": source, **{name: source / "External" / name for name in pin["dependencies"]}}
    paths["SPIRV-Headers"] = source / "External/SPIRV-Tools/external/spirv-headers"
    identities = {"MoltenVK": pin["commit"], **pin["dependencies"]}
    for name, path in paths.items():
        if out(["git", "-C", path, "rev-parse", "HEAD"]).strip() != identities[name]:
            raise ValueError(f"{label}: unexpected source revision for {name}")
        if out(["git", "-C", path, "diff", "--cached", "--numstat"]):
            raise ValueError(f"{label}: staged changes in {name}")
        if name not in ("MoltenVK", "SPIRV-Cross") and out(["git", "-C", path, "diff", "--numstat"]):
            raise ValueError(f"{label}: unexpected dependency changes in {name}")
    translator = out(["git", "-C", paths["SPIRV-Cross"], "diff", "--numstat"])
    if spec["pr2719"]:
        if translator != "9\t0\tspirv_msl.cpp\n":
            raise ValueError(f"{label}: SPIRV-Cross must carry only PR2719")
        subprocess.run(["git", "-C", str(paths["SPIRV-Cross"]), "apply", "--reverse", "--check",
                        str(ROOT / PR2719_PATCH)], check=True, timeout=60)
    elif translator:
        raise ValueError(f"{label}: SPIRV-Cross must be clean")
    # Re-create the MoltenVK tree from the pinned commit and the tracked patch stack.
    check = BUILD / f"audit-{spec['dir']}"
    if check.exists():
        shutil.rmtree(check)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(source), str(check)],
                   check=True, timeout=120)
    subprocess.run(["git", "-C", str(check), "checkout", "-q", pin["commit"]], check=True, timeout=120)
    for patch in spec["moltenvk_patches"]:
        subprocess.run(["git", "-C", str(check), "apply", str(ROOT / patch)], check=True, timeout=60)
    if (subprocess.check_output(["git", "-C", str(check), "diff", "--binary"], timeout=60) !=
            subprocess.check_output(["git", "-C", str(source), "diff", "--binary"], timeout=60)):
        raise ValueError(f"{label}: MoltenVK source differs from the tracked patch stack")
    shutil.rmtree(check)
    archive = source / "External/build/Release/SPIRVCross.xcframework/macos-x86_64/libSPIRVCross.a"
    if digest(archive) != spec["archive"]:
        raise ValueError(f"{label}: unexpected SPIRV-Cross archive")
    return identities, archive


def audit_one(label, spec, base_registry, base_inventory, receipt):
    source, built, signed = library_paths(spec)
    identities, archive = audit_sources(label, spec, source)
    config = BUILD / f"{spec['dir']}.xcconfig"
    expected = ("ARCHS = x86_64\nONLY_ACTIVE_ARCH = NO\nCODE_SIGNING_ALLOWED = NO\n"
                "CODE_SIGNING_REQUIRED = NO\nGCC_PREPROCESSOR_DEFINITIONS = $(inherited) "
                + " ".join(spec["defines"]) + "\n")
    if config.read_text() != expected:
        raise ValueError(f"{label}: unexpected build configuration")
    signature = verify_signature(signed)
    if out(["lipo", "-archs", signed]).strip() != "x86_64":
        raise ValueError(f"{label}: expected x86_64")
    linkage = out(["otool", "-L", signed])
    if "/usr/local/" in linkage:
        raise ValueError(f"{label}: nonportable dependency")
    # The signed file must be the build output plus a signature, nothing else.
    stripped = BUILD / "signed" / spec["dir"] / "libMoltenVK.unsigned-check.dylib"
    shutil.copy2(signed, stripped)
    subprocess.run(["codesign", "--remove-signature", str(stripped)], check=True, timeout=60)
    if not same_except_linkedit_vmsize(stripped.read_bytes(), built.read_bytes()):
        raise ValueError(f"{label}: signed library is not the audited build output")
    stripped.unlink()
    tests = {}
    rows = [row for row in receipt["results"] if row["library"] == label]
    if not rows or not all(row["oracle_passed"] and row["library_sha256"] == digest(signed) for row in rows):
        raise ValueError(f"{label}: bisect receipt does not cover this signed library")
    tests["bisect"] = {"path": BISECT_RECEIPT, "sha256": digest(ROOT / BISECT_RECEIPT),
                       "checks": sorted({row["check"] for row in rows})}
    if spec["sampler_receipt"]:
        sampler = json.loads((ROOT / spec["sampler_receipt"]).read_text())
        candidate = [row for row in sampler["results"] if row["library"] == "candidate"]
        if not (sampler["all_oracles_passed"] and sampler["tested_width"] == 128
                and sampler["advertised_per_stage_samplers"] == 128 and len(sampler["results"]) == 38
                and all(row["library_sha256"] == digest(signed) for row in candidate)):
            raise ValueError(f"{label}: sampler receipt does not cover this signed library")
        tests["sampler_128"] = {"path": spec["sampler_receipt"],
                                "sha256": digest(ROOT / spec["sampler_receipt"]),
                                "outcomes": len(sampler["results"]), "all_oracles_passed": True}
    data = json.loads(base_registry.read_text())
    original = Path(data["engines"][0]["install_path"])
    output = FROZEN / spec["engine"]
    if output.exists():
        raise ValueError("Never overwrite a candidate: " + str(output))
    install = output / "install"
    install.parent.mkdir(parents=True)
    # APFS clone; symlinks are copied as symlinks and checked by the inventory below.
    subprocess.run(["cp", "-cRp", str(original), str(install)], check=True, timeout=600)
    if (install / LIBRARY).is_symlink():
        raise ValueError("Refuse symlinked replacement")
    shutil.copy2(signed, install / LIBRARY)
    after = inventory(install)
    changed = {key for key in base_inventory.keys() | after.keys()
               if base_inventory.get(key) != after.get(key)}
    if changed != {str(LIBRARY)}:
        raise ValueError(f"{label}: unexpected inventory changes {sorted(changed)[:5]}")
    if digest(install / "bin/wine") != WINE_SHA256 or digest(install / "bin/wineserver") != WINESERVER_SHA256:
        raise ValueError(f"{label}: wine or wineserver differs from 170ca")
    manifest = output / "inventory.FROZEN.json"
    write_new(manifest, after)
    evidence = {
        "requirement": "REQ-104", "candidate": label, "engine": spec["engine"],
        "status": "signed-non-wine-tested-awaiting-review-and-admission", "qualified": False,
        "base_registry_sha256": BASE_DIGEST, "base_library_sha256": BASE_LIBRARY,
        "wine_sha256": WINE_SHA256, "wineserver_sha256": WINESERVER_SHA256,
        "only_changed_module": str(LIBRARY),
        "unsigned_library_sha256": digest(built), "library_sha256": digest(signed),
        "signature": signature, "architecture": "x86_64", "usr_local_references": 0,
        "signed_equals_build_plus_signature": "codesign --remove-signature output equals the build output except the grown __LINKEDIT vmsize field",
        "source_revisions": identities,
        "moltenvk_patches": [{"path": p, "sha256": digest(ROOT / p)} for p in spec["moltenvk_patches"]],
        "spirv_cross_patch": ({"path": PR2719_PATCH, "sha256": digest(ROOT / PR2719_PATCH),
                               "upstream": "https://github.com/KhronosGroup/SPIRV-Cross/pull/2719"}
                              if spec["pr2719"] else None),
        "spirv_cross_archive_sha256": digest(archive),
        "spirv_cross_archive_note": ("PR2719 archive; differs from 170ca's only in spirv_msl.o"
                                     if spec["pr2719"] else "Byte-identical to the archive inside 170ca"),
        "build_config": {"sha256": digest(config), "defines": spec["defines"]},
        "build_command": ("XCODE_XCCONFIG_FILE=<config> xcodebuild build -quiet -project "
                          "MoltenVKPackaging.xcodeproj -scheme 'MoltenVK Package (macOS only)' "
                          "-configuration Release -destination generic/platform=macOS "
                          "-derivedDataPath <derived> -jobs 4"),
        "toolchain": "Xcode 27.1 (27A9275), same as 170ca",
        "reproducibility_control": {"rebuilt_170ca_source_sha256": digest(REPRO),
                                    "matches_170ca_library": digest(REPRO) == BASE_LIBRARY},
        "advertised_per_stage_samplers": spec["limit"],
        "pipeline_cache_namespace": spec["namespace"],
        "contains_pr2719": spec["pr2719"],
        "tests": tests,
        "inventory_sha256": digest(manifest),
        "expected_nms_change": spec["expected_nms_change"],
        "limitations": [
            "No Wine, NMS launch, warning observation, frame-time or save check was performed",
            "New pipeline cache namespace: the first NMS launch recompiles shaders; judge smoothness after warm-up",
            "Headless compute, fragment and tessellation probes only; not Vulkan conformance",
            "Apple M5 Max only; devices failing the Metal3 gates keep limit 16",
            "REQ80/S2 admission and an owner-judged Ode Play are still required",
        ],
    }
    write_new(ROOT / f"docs/evidence/req104-bisect-{label}.json", evidence)
    registry = derive_registry(data, install, label, spec)
    write_new(output / "registry.UNQUALIFIED.json", registry)
    return {"evidence": f"docs/evidence/req104-bisect-{label}.json", "library_sha256": digest(signed)}


def derive_registry(data, install, label, spec):
    data = copy.deepcopy(data)
    if len(data["engines"]) != 1:
        raise ValueError("Require the exact single-engine base registry")
    entry = data["engines"][0]
    old = entry["install_path"]

    def rebase(value):
        if isinstance(value, str):
            return str(install) + value[len(old):] if value == old or value.startswith(old + "/") else value
        if isinstance(value, list):
            return [rebase(item) for item in value]
        if isinstance(value, dict):
            return {key: rebase(item) for key, item in value.items()}
        return value

    entry = rebase(entry)
    for key in ("smoke_test", "graphics_tests", "tls_positive_test", "tls_negative_test",
                "integrity", "build_evidence", "game_acceptance"):
        entry.pop(key, None)
    entry["name"] = spec["engine"]
    entry["version"] += " + " + spec["version"]
    entry["game_acceptance"] = "Not tested; independent review, REQ80/S2 admission and owner-judged Ode Play required"
    entry["smoke_test"] = {"status": "not-run", "scope": "No runtime qualification inherited"}
    patches = list(spec["moltenvk_patches"]) + ([PR2719_PATCH] if spec["pr2719"] else [])
    for patch in patches:
        entry["source_patches"].append({"path": str(ROOT / patch), "sha256": digest(ROOT / patch),
                                        "role": f"REQ104 bisect {label} MoltenVK-stack source patch"})
    library = install / LIBRARY
    for asset in entry["profile_assets"]["files"] + entry["dependencies"]:
        if asset.get("path") == str(library):
            asset["sha256"] = digest(library)
    data["engines"] = [entry]
    return data


def audit(base_registry, labels):
    if digest(base_registry) != BASE_DIGEST:
        raise ValueError("Require the unchanged 170ca4ad registry")
    data = json.loads(base_registry.read_text())
    entry = data["engines"][0]
    original = Path(entry["install_path"])
    if digest(original / LIBRARY) != BASE_LIBRARY:
        raise ValueError("Base library changed")
    if entry["sha256"] != WINE_SHA256 or entry["wineserver_sha256"] != WINESERVER_SHA256:
        raise ValueError("Base wine identity changed")
    for item in entry["profile_assets"]["files"] + entry["dependencies"]:
        if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
            raise ValueError("Base asset changed: " + item["path"])
    receipt = json.loads((ROOT / BISECT_RECEIPT).read_text())
    if not receipt["all_oracles_passed"]:
        raise ValueError("Bisect receipt did not pass")
    before = inventory(original)
    results = {label: audit_one(label, CANDIDATES[label], base_registry, before, receipt) for label in labels}
    if inventory(original) != before:
        raise ValueError("Base install changed during audit")
    print(json.dumps(results, indent=2))


def freeze(base_registry, labels):
    if digest(base_registry) != BASE_DIGEST:
        raise ValueError("Require the unchanged 170ca4ad registry")
    head = out(["git", "-C", ROOT, "rev-parse", "HEAD"]).strip()
    results = {}
    for label in labels:
        spec = CANDIDATES[label]
        evidence_path = ROOT / f"docs/evidence/req104-bisect-{label}.json"
        relative = evidence_path.relative_to(ROOT)
        tracked = [Path(spec["sampler_receipt"])] if spec["sampler_receipt"] else []
        tracked += [relative, Path(BISECT_RECEIPT), *map(Path, spec["moltenvk_patches"])]
        for path in tracked:
            committed = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{head}:{path}"], timeout=60)
            if committed != (ROOT / path).read_bytes():
                raise ValueError("Commit evidence, receipts and patches first: " + str(path))
        evidence = json.loads(evidence_path.read_text())
        output = FROZEN / spec["engine"]
        install = output / "install"
        manifest = output / "inventory.FROZEN.json"
        if digest(manifest) != evidence["inventory_sha256"]:
            raise ValueError(f"{label}: inventory manifest changed")
        if inventory(install) != json.loads(manifest.read_text()):
            raise ValueError(f"{label}: frozen install changed after audit")
        if digest(install / LIBRARY) != evidence["library_sha256"]:
            raise ValueError(f"{label}: library changed after audit")
        verify_signature(install / LIBRARY)
        data = json.loads((output / "registry.UNQUALIFIED.json").read_text())
        entry = data["engines"][0]
        for item in entry["profile_assets"]["files"] + entry["dependencies"]:
            if "sha256" in item and digest(Path(item["path"])) != item["sha256"]:
                raise ValueError(f"{label}: asset changed: " + item["path"])
        entry.update(producerRepository="https://github.com/WorkingPrinciple/calimocho",
                     producerCommit=head, evidencePath=str(relative), evidenceSha256=digest(evidence_path))
        entry["build_evidence"] = evidence
        entry["integrity"] = {"status": "unchanged", "manifest_path": str(manifest),
                              "manifest_sha256": digest(manifest),
                              "scope": "Signed, non-Wine-tested REQ104 bisect candidate; unqualified"}
        target = output / "registry.SOURCE-FROZEN.json"
        write_new(target, data)
        results[label] = {"engine": spec["engine"], "registry": str(target),
                          "registry_sha256": digest(target), "library_sha256": evidence["library_sha256"]}
    print(json.dumps({"producerCommit": head, "candidates": results}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "freeze"))
    parser.add_argument("--base-registry", required=True, type=Path)
    parser.add_argument("--candidate", action="append", choices=sorted(CANDIDATES), required=True)
    args = parser.parse_args()
    (audit if args.operation == "audit" else freeze)(args.base_registry.resolve(), args.candidate)
