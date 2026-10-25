"""Audit immutable 11d inputs, then derive a producer-bound DIRT5-only registry."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.build_minidump_overlay import inventory
from tools.probe_wine_source import sha256

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "build/winehq-11.20/metal-port-11d-ags54-02"
EVIDENCE = Path("docs/evidence/11d-dirt5-runtime-provenance.json")
PINS = {
    "receipt.json": "46a47c2d47e8c43b5edbaac44accb8fb97972fab35a8c8be0d13a90b0c7b1589",
    "ags54-minidump.registry.local.RUNTIME-FROZEN.json": "dcb8489851cafde7ffc9333de3d61a33c61e622b1e4b6a3262016c96ad42b7c7",
    "graphics-qualification-frozen.json": "6f2ded3a44931662b70999246e6b65f22064a8214ab0359c0599d5459b53b5a5",
    "headless-qualification-frozen.json": "2842fd44e7a15a300012d54f19ae9a295e2ab6dd00ccfea6795ef8f1cbbb5e41",
    "dirt5-ags54.environment.json": "d3d4c0a98994e5b6ead1e664eb8b227ea3ff5779aa2993f2c843b8de82810f6f",
}


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")


def audit():
    for name, digest in PINS.items():
        if sha256(ROOT / name) != digest:
            raise ValueError("Frozen input changed: " + name)
    build = json.loads((ROOT / "receipt.json").read_text())
    actual = inventory(ROOT / "install")
    if actual != build["installed_files"]:
        raise ValueError("Unresolved deployed inventory difference")
    entry = json.loads((ROOT / "ags54-minidump.registry.local.RUNTIME-FROZEN.json").read_text())["engines"][0]
    if entry["environment"]["WINELOADER"] != entry["wine"] or entry["environment"]["WINESERVER"] != entry["wineserver"]:
        raise ValueError("Loader/server environment mismatch")
    external = entry["profile_assets"]["files"] + entry["dependencies"]
    checked = []
    for asset in external:
        if "path" in asset and "sha256" in asset:
            if sha256(Path(asset["path"])) != asset["sha256"]:
                raise ValueError("Asset/dependency hash mismatch: " + asset["path"])
            checked.append({"path": asset["path"], "sha256": asset["sha256"]})
    for key, digest in (("wine", "sha256"), ("wineserver", "wineserver_sha256")):
        if sha256(Path(entry[key])) != entry[digest]:
            raise ValueError("Runtime binary mismatch: " + key)
    audit_path = ROOT / "dirt5-integrity-audit-FROZEN.json"
    write_new(audit_path, {
        "status": "unchanged", "scope": "full deployed inventory vs producer receipt, not game qualification",
        "build_receipt_sha256": PINS["receipt.json"], "files": actual,
        "unresolved_differences": [], "checked_assets_and_dependencies": checked,
    })
    audit_path.chmod(0o444)
    write_new(REPO / EVIDENCE, {
        "producerRepository": "https://github.com/dragoshont/calimocho",
        "upstreamWineCommit": entry["source_commit"],
        "immutableInputs": [{"path": str(ROOT / name), "sha256": digest} for name, digest in PINS.items()],
        "deployedInventoryAudit": {"path": str(audit_path), "sha256": sha256(audit_path), "status": "unchanged"},
        "wineSha256": entry["sha256"], "wineserverSha256": entry["wineserver_sha256"],
        "variantEngineName": entry["name"] + "-dirt5",
        "variantOverride": "mscoree,mshtml=;amd_ags_x64=b",
        "graphics": "Vulkan/D3D11/D3D12:120 presents, exact RGBA51,102,204,255",
        "headless": "actual AGS device/minidump and HTTPS positive/expired-certificate negative",
        "gameAcceptance": "not observed by producer; execution owner must admit and test",
        "displayException": {"ownerAuthorizedDockPid": 716, "windowId": 33, "qualificationOnly": True},
    })


def freeze():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    committed = subprocess.check_output(["git", "show", commit + ":" + str(EVIDENCE)], cwd=REPO)
    if committed != (REPO / EVIDENCE).read_bytes():
        raise ValueError("Evidence must be committed, unchanged producer bytes")
    evidence = json.loads(committed)
    for item in evidence["immutableInputs"] + [evidence["deployedInventoryAudit"]]:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Bound input changed: " + item["path"])
    data = json.loads((ROOT / "ags54-minidump.registry.local.RUNTIME-FROZEN.json").read_text())
    entry = data["engines"][0]
    entry["name"] = evidence["variantEngineName"]
    entry["environment"]["WINEDLLOVERRIDES"] = evidence["variantOverride"]
    entry["integrity"] = {
        "status": "unchanged", "manifest_path": evidence["deployedInventoryAudit"]["path"],
        "manifest_sha256": evidence["deployedInventoryAudit"]["sha256"],
    }
    entry.update(producerRepository=evidence["producerRepository"], producerCommit=commit,
                 evidencePath=str(EVIDENCE), evidenceSha256=sha256(REPO / EVIDENCE))
    entry["game_acceptance"] = "pending owner admission and DIRT5 observation"
    path = ROOT / "dirt5-ags54-minidump.registry.local.ADMISSION-FROZEN.json"
    write_new(path, data)
    path.chmod(0o444)
    print(json.dumps({"registry": str(path), "sha256": sha256(path), "engine": entry["name"],
                      "producerCommit": commit, "evidencePath": str(EVIDENCE),
                      "evidenceSha256": entry["evidenceSha256"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "freeze"))
    args = parser.parse_args()
    audit() if args.operation == "audit" else freeze()
