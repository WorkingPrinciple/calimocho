"""Freeze source/build inputs for cell008 without starting Wine or a prefix."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tools.build_launcher_overlay import BASE, MODULE, REPO
from tools.build_minidump_overlay import inventory
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256
from tools.package_frameworks import resolve
from tools.verify_installed_appx import verify


SOURCES = (
    "tools/build_launcher_overlay.py", "tools/build_launcher_fixture.py",
    "tools/run_launcher_fixture.py", "tools/port_package_protocols.py",
    "tools/package_protocols.py", "tools/prepare_verified_activation.py",
    "tools/diagnose_package_activation.py", "tools/freeze_launcher_runtime.py",
    "tests/launcher_probe.c", "tests/package_activation_probe.c",
)


def committed_sources(commit):
    resolved = subprocess.check_output(
        ["git", "rev-parse", "--verify", commit + "^{commit}"], cwd=REPO, text=True).strip()
    paths = list(SOURCES) + [str(path.relative_to(REPO)) for path in sorted(MODULE.iterdir())]
    result = {}
    for relative in paths:
        blob = subprocess.check_output(["git", "show", resolved + ":" + relative], cwd=REPO)
        if blob != (REPO / relative).read_bytes():
            raise ValueError("Producer commit does not contain current source: " + relative)
        result[relative] = sha256(REPO / relative)
    return resolved, result


def checked_assets(entry):
    install = Path(entry["install_path"]).resolve(strict=True)
    for key in ("wine", "wineserver"):
        path = Path(entry[key]).resolve(strict=True)
        digest = entry["sha256"] if key == "wine" else entry["wineserver_sha256"]
        if path != install / "bin" / key or sha256(path) != digest:
            raise ValueError("Wrong deployed engine identity: " + key)
    if entry["environment"]["WINELOADER"] != entry["wine"] or entry["environment"]["WINESERVER"] != entry["wineserver"]:
        raise ValueError("Loader/server environment differs from exact engine")
    for item in entry["profile_assets"]["files"] + entry["dependencies"]:
        if "path" in item and "sha256" in item and sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Deployed asset differs: " + item["path"])


def freeze(root, commit):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or any(root.glob("*FROZEN*")):
        raise ValueError("Require an unfrozen owned candidate")
    producer, sources = committed_sources(commit)
    build = json.loads((root / "build-receipt.json").read_text())
    install = root / "install"
    if build["status"] != "built-not-runtime-qualified" or build["files"] != inventory(install):
        raise ValueError("Candidate deployment differs from successful build receipt")
    if build["module_sources"] != inventory(MODULE):
        raise ValueError("Launcher source differs from built source")
    helper = root / "package-activation-probe-v6.exe"
    compiled = json.loads((root / "fixture-build-receipt.json").read_text())
    for name in ("launcher-probe.exe", helper.name):
        if compiled[name] != sha256(root / name):
            raise ValueError("Compiled helper/fixture changed: " + name)
    for step in compiled["commands"]:
        candidates = [Path(arg) for arg in step["argv"] if arg.endswith(".c")]
        if len(candidates) != 1 or sha256(candidates[0]) != step["source_sha256"] or step["exit_code"]:
            raise ValueError("Helper source or successful compile receipt changed")
    predecessor = BASE / "cell007-receipt.json"
    if sha256(predecessor) != "16ff32b77465ae2cbc7de440a7743f7b02d312788553bbece526ee1291839ad0":
        raise ValueError("Cell007 receipt changed")
    previous = json.loads(predecessor.read_text())
    if inventory(BASE / "install") != json.loads(Path(previous["inventory"]).read_text())["files"]:
        raise ValueError("Cell007 deployment changed")
    snapshot = root / "activation-cell008"
    verification_path = snapshot / "verification.json"
    verification = json.loads(verification_path.read_text())
    if not verification["installed_content_verified"] or not verification["signed_context_eligible"]:
        raise ValueError("Require the authenticated package/framework snapshot")
    roots = [BASE.parent / "package-identity-01" / ("microsoft-root-" + year + ".der")
             for year in ("2011", "2010")]
    openssl = "/opt/homebrew/opt/openssl@3/bin/openssl"
    fresh = {}
    fresh.update(verify(snapshot / "package", "Microsoft.Xbox.App", roots, openssl, fresh))
    for key in ("signed_digests", "files_verified", "metadata"):
        if fresh[key] != verification[key]:
            raise ValueError("Authenticated package recheck differs: " + key)
    if resolve(snapshot / "package/AppxManifest.xml", snapshot / "frameworks", roots, openssl) != verification["frameworks"]:
        raise ValueError("Authenticated framework graph recheck differs")
    for key in ("graph", "framework_registration", "protocol_table", "server_registration_table"):
        if sha256(Path(verification[key])) != verification[key + "_sha256"]:
            raise ValueError("Verified artifact changed: " + key)
    registry = json.loads((root / "launcher.registry.local.UNQUALIFIED.json").read_text())
    entry = registry["engines"][0]
    checked_assets(entry)
    if Path(entry["install_path"]) != install:
        raise ValueError("Registry names a different candidate")
    manifest = root / "inventory-CELL008-FROZEN.json"
    frozen_registry = root / "launcher.registry.local.CELL008-FROZEN.json"
    collector = root / "diagnose_package_activation-cell008.py"
    launcher_reg = root / "launcher-CELL008-FROZEN.reg"
    receipt_path = root / "cell008-receipt.json"
    for path in (manifest, frozen_registry, collector, launcher_reg, receipt_path):
        if path.exists():
            raise FileExistsError("Refuse to replace an existing handoff artifact: " + str(path))
    manifest.write_text(json.dumps({"files": build["files"],
                                   "basis": "full deployed-vs-build receipt audit; not runtime qualification"},
                                  indent=2) + "\n")
    entry["integrity"] = {"status": "unchanged", "manifest_path": str(manifest),
                          "manifest_sha256": sha256(manifest)}
    frozen_registry.write_text(json.dumps(registry, indent=2) + "\n")
    shutil.copy2(REPO / "tools/diagnose_package_activation.py", collector)
    dll = install / "lib/wine/x86_64-windows/windows.system.launcher.dll"
    lines = ('Windows Registry Editor Version 5.00\r\n\r\n'
             '[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\Windows.System.Launcher]\r\n'
             '"DllPath"="' + dos(dll).replace("\\", "\\\\") + '"\r\n"ThreadingModel"="both"\r\n')
    launcher_reg.write_bytes(lines.encode("utf-16"))
    run = Path("/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-008")
    env = dict(entry["environment"], **verification["environment"],
               WINEPREFIX=str(run / "prefix"), WINEARCH="win64")
    wine = ["/usr/bin/arch", "-x86_64", entry["wine"]]
    server = entry["wineserver"]
    receipt = {
        "scope": "cell008 declared package protocol diagnostic, no UWP delivery yet",
        "status": "source-built; native fixture and real Xbox execution not run here",
        "runtime_executed": False, "producer_commit": producer,
        "source_commit": entry["source_commit"], "source_inputs": sources,
        "engine": entry["name"], "install": str(install),
        "registry": str(frozen_registry), "registry_sha256": sha256(frozen_registry),
        "inventory": str(manifest), "inventory_sha256": sha256(manifest),
        "wine_sha256": entry["sha256"], "wineserver_sha256": entry["wineserver_sha256"],
        "ntdll_sha256": sha256(install / "lib/wine/x86_64-windows/ntdll.dll"),
        "launcher_sha256": sha256(dll),
        "server_source_sha256": sha256(root / "source/server/process.c"),
        "build_receipt": str(root / "build-receipt.json"),
        "build_receipt_sha256": sha256(root / "build-receipt.json"),
        "predecessor_receipt": str(predecessor), "predecessor_receipt_sha256": sha256(predecessor),
        "verification": str(verification_path), "verification_sha256": sha256(verification_path),
        "helper": str(helper), "helper_sha256": sha256(helper),
        "diagnostic_collector": str(collector), "diagnostic_collector_sha256": sha256(collector),
        "prefix": env["WINEPREFIX"], "evidence": str(run / "evidence"),
        "environment": env, "cwd": verification["snapshot"],
        "server_stop": [server, "-k"], "server_wait": [server, "-w"],
        "server_start": {"argv": [server, "-p"], "environment": dict(
            env, CALIMOCHO_PACKAGE_REGISTRATION=verification["server_registration_table"])},
        "activation_argv": wine + [str(helper), "--activate-diagnostic",
                                  dos(snapshot / "identity.bin"), verification["executable_dos"]],
        "framework_registration_argv": wine + ["regedit", "/S", dos(verification["framework_registration"])],
        "launcher_registration": str(launcher_reg), "launcher_registration_sha256": sha256(launcher_reg),
        "launcher_registration_argv": wine + ["regedit", "/S", dos(launcher_reg)],
        "activation_limit_seconds": 45, "collector_limit_seconds": 60,
        "diagnostic_collector_argv": [sys.executable, str(collector), str(receipt_path),
                                     "--output", str(run / "evidence/activation-redacted.json")],
        "preconditions": [
            "Execute only within the scheduler-granted exclusive lane",
            "Use a fresh cell008 prefix; preserve007 and all earlier cells",
            "Retain the Xbox owner's previous explicit native XAML setup; no implicit installer",
            "Import both framework_registration_argv and launcher_registration_argv in this prefix",
            "Stop/wait the setup server, then start server_start with its explicit host-only table",
            "Run diagnostic_collector_argv without saving raw trace or full URI",
            "Stop/wait only this prefix server after observation; retain cleanup evidence",
        ],
        "limitations": [
            "No native fixture, CE route, child process, XAML or UI outcome claimed by this freeze",
            "UWP route returns E_NOTIMPL; full-trust true means process started, not UI success",
            "Unknown scheme false; no host URI/default browser/CrossOver fallback",
            "Both public XAML basenames tracked by PID; CE exit is not child exit",
            "Recorded started child suppresses CE-only cutoff within original60s cap; exit remains unknown",
        ],
    }
    for key in ("graph", "framework_registration", "protocol_table", "server_registration_table"):
        receipt[key], receipt[key + "_sha256"] = verification[key], verification[key + "_sha256"]
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    print(freeze(args.root, args.producer_commit))
