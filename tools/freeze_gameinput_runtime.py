"""Bind the observed no-device fixture and full audit to a Witcher-only registry."""
import argparse
import json
from pathlib import Path
import subprocess

from tools.build_gameinput_overlay import BASE, REPO, SOURCE
from tools.build_minidump_overlay import inventory
from tools.freeze_dirt5_runtime import write_new
from tools.probe_wine_source import sha256

ROOT = REPO / "build/winehq-11.20/metal-port-11e-gameinput-04"
EVIDENCE = Path("docs/evidence/11e-gameinput-runtime-provenance.json")
REGISTRY = "gameinput.registry.local.UNQUALIFIED.json"
FINAL_REGISTRY = "witcher-gameinput.registry.local.ADMISSION-FROZEN.json"
ENGINE = "calimocho-wine11.20-gptk4b3-gameinput-empty-witcher"
OVERRIDE = "mscoree,mshtml=;gameinput=b;amd_ags_x64=n"
PINS = {
    "receipt.json": "1889855084c58b2283562f528e680a59da16875dbb137a2e8cb6e37fcadacdb7",
    REGISTRY: "5dfa7555f450d4080a362e1f8e2279d0f3a1a5bd37d95b568e7fe559d5573d41",
    "gameinput.dll": "e814ac3d88ffb9156855bc05bac36b442f30559f3ff9c11aa3cfd963037e83e4",
    "gameinput-probe.exe": "777d066f909584369962f7f3fa682407c18dfd96ccc0193849645bbd3d98fae7",
    "headless-01/receipt.json": "d3c3bc78d12c8fce8071b12d3ea2e17c686c87fc376fa118e7ecaba5ff931ee3",
    "headless-02/receipt.json": "bac29c94313111f4158eb46e9298831715cf1d8803459f9df54c681177d36f25",
    "run_headless.py": "f0062693bcac66c012914c9aeea3b4569bd42ef6e5e038e2fa3ae18a183e8ea8",
}


def validate_observation(record, case):
    expected = {
        "baseline": (1, ["GameInputCreate HRESULT=80004001 Initialize_export=0"], [94, 95]),
        "candidate": (0, ["GameInputCreate HRESULT=00000000 Initialize_export=1",
                          "no-device callbacks=0 failures=0"], []),
    }
    if case not in expected or len(record["observations"]) != 1:
        raise ValueError("Require one actual fixture case")
    observation = record["observations"][0]
    code, facts, failed = expected[case]
    if (observation["case"] != case or observation["exit_code"] != code
            or observation["facts"] != facts or observation["failed_lines"] != failed):
        raise ValueError("Unexpected fixture result")
    if (observation["stop"] not in (0, 1) or observation["wait"] != 0
            or observation["prefix_open_files"] != 1 or not observation["prefix_open_files_empty"]):
        raise ValueError("Fixture cleanup not observed")
    if (not record["windowless"] or not record["base_inventory_unchanged"]
            or not 0 < record["elapsed_seconds"] <= 120):
        raise ValueError("Fixture scope/budget/base invariant failed")


def verify_inputs():
    for name, digest in PINS.items():
        if sha256(ROOT / name) != digest:
            raise ValueError("Observed input changed: " + name)
    for case, name in (("baseline", "headless-01"), ("candidate", "headless-02")):
        record = json.loads((ROOT / name / "receipt.json").read_text())
        validate_observation(record, case)
        if record["probe_sha256"] != PINS["gameinput-probe.exe"]:
            raise ValueError("Executed probe identity differs")
    return json.loads((ROOT / REGISTRY).read_text())


def audit():
    data = verify_inputs()
    receipt = json.loads((ROOT / "receipt.json").read_text())
    if inventory(SOURCE) != receipt["source_files"]:
        raise ValueError("Current GameInput sources differ from built inputs")
    actual = inventory(ROOT / "install")
    baseline = inventory(BASE / "install")
    if actual != receipt["installed_files"] or baseline != json.loads(
            (BASE / "receipt.json").read_text())["installed_files"]:
        raise ValueError("Unresolved deployed inventory difference")
    changed = {name for name in actual.keys() | baseline.keys()
               if actual.get(name) != baseline.get(name)}
    if changed != {"lib/wine/x86_64-windows/gameinput.dll"}:
        raise ValueError("Not the exact one-module sibling")
    entry = data["engines"][0]
    if (entry["environment"]["WINELOADER"] != entry["wine"]
            or entry["environment"]["WINESERVER"] != entry["wineserver"]):
        raise ValueError("Loader/server environment mismatch")
    checked = []
    for item in entry["profile_assets"]["files"] + entry["dependencies"]:
        if "path" in item and "sha256" in item:
            if sha256(Path(item["path"])) != item["sha256"]:
                raise ValueError("Asset/dependency mismatch: " + item["path"])
            checked.append({"path": item["path"], "sha256": item["sha256"]})
    for key, digest in (("wine", "sha256"), ("wineserver", "wineserver_sha256")):
        if sha256(Path(entry[key])) != entry[digest]:
            raise ValueError("Runtime binary mismatch: " + key)
    audit_path = ROOT / "integrity-audit-FROZEN.json"
    write_new(audit_path, {
        "status": "unchanged", "files": actual, "unresolved_differences": [],
        "build_receipt_sha256": PINS["receipt.json"],
        "checked_assets_and_dependencies": checked, "only_one_x64_gameinput_replaced": True,
    })
    audit_path.chmod(0o444)
    write_new(REPO / EVIDENCE, {
        "producerRepository": "https://github.com/dragoshont/calimocho",
        "upstreamWineCommit": entry["source_commit"],
        "implementationCommit": "46a0a85f4b44ff19ef8b50130289df67f13de728",
        "immutableInputs": [{"path": str(ROOT / name), "sha256": digest}
                            for name, digest in PINS.items()],
        "deployedInventoryAudit": {"path": str(audit_path), "sha256": sha256(audit_path),
                                  "status": "unchanged"},
        "wineSha256": entry["sha256"], "wineserverSha256": entry["wineserver_sha256"],
        "variantEngineName": ENGINE, "variantOverride": OVERRIDE,
        "headless": "Actual old stub/export failure; candidate zero callbacks, zero assertion failures",
        "cleanup": "Both -k returned1, -w0, lsof1/empty after natural process exit",
        "retainedHarnessFailure": "First harness required -k0; baseline retained, not replayed",
        "graphics": "Not rerun on 11e; only GameInput differs from qualified 11d",
        "gameAcceptance": "Pending execution-owner admission and Witcher title-screen observation",
        "nativeAgs": "Recipe requires existing owner-managed native amd_ags_x64; not installed or modified here",
        "limitations": "x64 only; no devices, keyboard/mouse capture, haptics, OEM or AGS6 implementation",
    })


def freeze():
    data = verify_inputs()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    committed = subprocess.check_output(["git", "show", commit + ":" + str(EVIDENCE)], cwd=REPO)
    if committed != (REPO / EVIDENCE).read_bytes():
        raise ValueError("Producer evidence is not committed unchanged")
    evidence = json.loads(committed)
    audit_record = evidence["deployedInventoryAudit"]
    if sha256(Path(audit_record["path"])) != audit_record["sha256"]:
        raise ValueError("Deployed audit changed")
    deployed = json.loads(Path(audit_record["path"]).read_text())
    if inventory(ROOT / "install") != deployed["files"]:
        raise ValueError("Deployed runtime changed after audit")
    for item in deployed["checked_assets_and_dependencies"]:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Asset/dependency changed after audit: " + item["path"])
    entry = data["engines"][0]
    entry["name"] = ENGINE
    entry["version"] = "WineHQ11.20 + AGS5.4/minidump + headless-tested no-device GameInput"
    entry["environment"]["WINEDLLOVERRIDES"] = OVERRIDE
    entry["smoke_test"] = {
        "status": "passed", "scope": "Windowless GameInput contract only, not graphics/game acceptance",
        "path": str(ROOT / "headless-02/receipt.json"),
        "sha256": PINS["headless-02/receipt.json"],
    }
    entry["integrity"] = {"status": "unchanged", "manifest_path": audit_record["path"],
                          "manifest_sha256": audit_record["sha256"]}
    entry.update(producerRepository=evidence["producerRepository"], producerCommit=commit,
                 evidencePath=str(EVIDENCE), evidenceSha256=sha256(REPO / EVIDENCE),
                 game_acceptance=evidence["gameAcceptance"])
    output = ROOT / FINAL_REGISTRY
    write_new(output, data)
    output.chmod(0o444)
    print(json.dumps({"registry": str(output), "sha256": sha256(output), "engine": ENGINE,
                      "producerCommit": commit, "evidencePath": str(EVIDENCE),
                      "evidenceSha256": entry["evidenceSha256"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("audit", "freeze"))
    audit() if parser.parse_args().operation == "audit" else freeze()
