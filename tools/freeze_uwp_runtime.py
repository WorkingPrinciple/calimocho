"""Pin cell009 source/build handoff without claiming native or UI qualification."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import hashlib

from tools.build_uwp_overlay import BASE, REPO
from tools.build_minidump_overlay import inventory
from tools.freeze_launcher_runtime import checked_assets
from tools.package_frameworks import resolve
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256
from tools.verify_installed_appx import verify

SOURCE_PATHS = (
    "tools/port_uwp_activation.py", "tools/build_uwp_overlay.py", "tools/stage_uwp_overlay.py",
    "tools/freeze_uwp_runtime.py", "tools/prepare_verified_activation.py", "tools/package_frameworks.py",
    "tools/package_protocols.py", "tools/diagnose_package_activation.py",
    "tests/package_activation_probe.c", "tests/uwp_activation_probe.c",
    "patches/wine/files/package_activation_record.h", "patches/wine/files/package_activation.idl",
    "patches/wine/files/core_application_activated.c", "patches/wine/files/corewindow_host.c",
)


def freeze(root, producer):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or root == BASE or any(root.glob("*FROZEN*")):
        raise ValueError("Require an unfrozen009 sibling")
    producer = subprocess.check_output(["git", "rev-parse", "--verify", producer + "^{commit}"],
                                       cwd=REPO, text=True).strip()
    sources = {}
    for relative in SOURCE_PATHS:
        blob = subprocess.check_output(["git", "show", producer + ":" + relative], cwd=REPO)
        if blob != (REPO / relative).read_bytes():
            raise ValueError("Producer does not contain current source: " + relative)
        sources[relative] = hashlib.sha256(blob).hexdigest()
    stage = json.loads((root / "staging-receipt.json").read_text())
    build = json.loads((root / "build-receipt.json").read_text())
    install = root / "install"
    if (stage["runtime_executed"] or stage["status"] != "staged-not-runtime-qualified"
            or inventory(install) != stage["files"] or stage["helper_exit"]):
        raise ValueError("Staged009 inventory changed")
    if (build["status"] != "built-not-staged-not-executed" or build["runtime_executed"]
            or not build["steps"] or any(step["exit_code"] or step["timed_out"] for step in build["steps"])):
        raise ValueError("Require successful009 source build")
    if sha256(root / "build-receipt.json") != stage["build_receipt_sha256"]:
        raise ValueError("Build receipt changed after staging")
    for relative, digest in build["built_files"].items():
        if sha256(root / relative) != digest:
            raise ValueError("Compiled009 artifact changed")
    for relative, digest in build["source_inputs"].items():
        if sha256(REPO / relative) != digest:
            raise ValueError("Built source changed")
    for name in ("helper", "probe"):
        if sha256(Path(stage[name])) != stage[name + "_sha256"]:
            raise ValueError("Built observer/fixture changed")
    for key, relative in (("helper_source_sha256", "tests/package_activation_probe.c"),
                          ("probe_source_sha256", "tests/uwp_activation_probe.c")):
        if stage[key] != sources[relative]:
            raise ValueError("Observer/fixture source differs from committed producer")
    snapshot = root / "activation-cell009"
    verification_path = snapshot / "verification.json"
    verification = json.loads(verification_path.read_text())
    roots = [BASE.parent / "package-identity-01" / ("microsoft-root-" + year + ".der")
             for year in ("2011", "2010")]
    openssl = "/opt/homebrew/opt/openssl@3/bin/openssl"
    fresh = {}
    fresh.update(verify(snapshot / "package", "Microsoft.Xbox.App", roots, openssl, fresh))
    if not verification["installed_content_verified"] or not verification["signed_context_eligible"]:
        raise ValueError("Unverified009 snapshot")
    for key in ("signed_digests", "files_verified", "metadata"):
        if fresh[key] != verification[key]:
            raise ValueError("Authenticated009 app recheck differs")
    if resolve(snapshot / "package/AppxManifest.xml", snapshot / "frameworks", roots, openssl) != verification["frameworks"]:
        raise ValueError("Authenticated009 framework recheck differs")
    if not verification.get("application_classes") or any(not item["server_file_present"]
                                                         for item in verification["application_classes"]):
        raise ValueError("Missing verified application-class registrations")
    for key in ("graph", "framework_registration", "protocol_table", "server_registration_table"):
        if sha256(Path(verification[key])) != verification[key + "_sha256"]:
            raise ValueError("009 activation artifact changed")
    previous_path = BASE / "cell008-receipt.json"
    previous = json.loads(previous_path.read_text())
    if sha256(previous_path) != build["predecessor_receipt_sha256"]:
        raise ValueError("Frozen008 receipt changed")
    if inventory(BASE / "install") != json.loads(Path(previous["inventory"]).read_text())["files"]:
        raise ValueError("Frozen008 deployment changed")
    registry = json.loads(Path(stage["registry"]).read_text())
    if sha256(Path(stage["registry"])) != stage["registry_sha256"]:
        raise ValueError("Unqualified009 registry changed")
    entry = registry["engines"][0]
    checked_assets(entry)
    manifest = root / "inventory-CELL009-FROZEN.json"
    frozen_registry = root / "uwp.registry.local.CELL009-FROZEN.json"
    collector = root / "diagnose_package_activation-cell009.py"
    launcher_reg = root / "launcher-CELL009-FROZEN.reg"
    receipt_path = root / "cell009-receipt.json"
    for path in (manifest, frozen_registry, collector, launcher_reg, receipt_path):
        if path.exists():
            raise FileExistsError("Refuse to overwrite009 handoff")
    manifest.write_text(json.dumps({"files": stage["files"], "basis": "full deployed-vs-build audit, not UI qualification"},
                                  indent=2) + "\n")
    entry["integrity"] = {"status": "unchanged", "manifest_path": str(manifest),
                          "manifest_sha256": sha256(manifest)}
    entry["version"] += " + process-bound protocol/CoreWindow diagnostic (UNQUALIFIED)"
    for relative in SOURCE_PATHS:
        if relative.startswith("patches/") or relative in ("tools/port_uwp_activation.py", "tools/build_uwp_overlay.py"):
            entry["source_patches"].append({"path": str(REPO / relative), "sha256": sources[relative],
                                            "role": "009 source-built local UWP activation"})
    frozen_registry.write_text(json.dumps(registry, indent=2) + "\n")
    shutil.copy2(REPO / "tools/diagnose_package_activation.py", collector)
    dll = install / "lib/wine/x86_64-windows/windows.system.launcher.dll"
    launcher_reg.write_bytes((
        'Windows Registry Editor Version 5.00\r\n\r\n'
        '[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\Windows.System.Launcher]\r\n'
        '"DllPath"="' + dos(dll).replace("\\", "\\\\") + '"\r\n"ThreadingModel"="both"\r\n').encode("utf-16"))
    run = Path("/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-009")
    env = dict(entry["environment"], **verification["environment"], WINEPREFIX=str(run / "prefix"), WINEARCH="win64")
    wine = ["/usr/bin/arch", "-x86_64", entry["wine"]]
    server = entry["wineserver"]
    receipt = copy.deepcopy(previous)
    receipt.update(
        scope="cell009 process-bound UWP protocol and genuine HWND/CoreDispatcher diagnostic",
        status="source-built; native fixture and real Xbox execution not run here",
        runtime_executed=False, producer_commit=producer, source_inputs=sources,
        engine=entry["name"], install=str(install), registry=str(frozen_registry),
        registry_sha256=sha256(frozen_registry), inventory=str(manifest), inventory_sha256=sha256(manifest),
        wine_sha256=entry["sha256"], wineserver_sha256=entry["wineserver_sha256"],
        ntdll_sha256=sha256(install / "lib/wine/x86_64-windows/ntdll.dll"),
        launcher_sha256=sha256(dll), server_source_sha256=sha256(root / "source/server/process.c"),
        build_receipt=str(root / "build-receipt.json"), build_receipt_sha256=sha256(root / "build-receipt.json"),
        staging_receipt=str(root / "staging-receipt.json"), staging_receipt_sha256=sha256(root / "staging-receipt.json"),
        predecessor_receipt=str(previous_path), predecessor_receipt_sha256=sha256(previous_path),
        verification=str(verification_path), verification_sha256=sha256(verification_path),
        helper=stage["helper"], helper_sha256=stage["helper_sha256"],
        diagnostic_collector=str(collector), diagnostic_collector_sha256=sha256(collector),
        native_fixture=stage["probe"], native_fixture_sha256=stage["probe_sha256"],
        native_fixture_status="compiled, not executed; requires scheduled window slot",
        prefix=env["WINEPREFIX"], evidence=str(run / "evidence"), environment=env, cwd=verification["snapshot"],
        server_stop=[server, "-k"], server_wait=[server, "-w"],
        server_start={"argv": [server, "-p"], "environment": dict(
            env, CALIMOCHO_PACKAGE_REGISTRATION=verification["server_registration_table"])},
        activation_argv=wine + [stage["helper"], "--activate-diagnostic",
                                dos(snapshot / "identity.bin"), verification["executable_dos"]],
        framework_registration_argv=wine + ["regedit", "/S", dos(verification["framework_registration"])],
        launcher_registration=str(launcher_reg), launcher_registration_sha256=sha256(launcher_reg),
        launcher_registration_argv=wine + ["regedit", "/S", dos(launcher_reg)],
        application_class_count=len(verification["application_classes"]),
        diagnostic_collector_argv=[sys.executable, str(collector), str(receipt_path),
                                   "--output", str(run / "evidence/activation-redacted.json")],
        preconditions=[
            "Execute008 first;009 only within scheduler-granted window/runtime lane",
            "Use a fresh009 prefix; preserve008/007 and all earlier cells",
            "Retain Xbox owner's previous explicit native XAML setup; no hidden installer",
            "Import framework_registration_argv (now includes authenticated main-app classes) and launcher_registration_argv",
            "Stop/wait setup server, then start server_start with the host-only table",
            "Run bounded diagnostic_collector_argv; do not save raw output/full URI",
            "Stop/wait only009 prefix server and retain cleanup evidence",
        ],
        limitations=[
            "Compilation and integrity audit do not establish UWP/XAML/window/UI acceptance",
            "Protocol record is current-process/server-owned; caller AppId comes from admitted server token",
            "CoreApplication queues Activated for delivery in the view's Run dispatcher, not after its blocking loop returns",
            "A real HWND is created hidden; Activate shows it only during the scheduled runtime",
            "Only activation/size window events implemented; other queried methods/IIDs report explicit failure",
            "No Store/licence/service/token-broker forwarding, host URI, default browser or CrossOver fallback",
            "No actual008/009 scheme, process, activation callback, HWND or UI outcome claimed here",
        ],
    )
    for key in ("graph", "framework_registration", "protocol_table", "server_registration_table"):
        receipt[key], receipt[key + "_sha256"] = verification[key], verification[key + "_sha256"]
    receipt["changed_modules"] = stage["changed_files"]
    receipt["generated_source_sha256"] = {
        relative: sha256(root / "source" / relative) for relative in (
            "server/process.c", "server/process.h", "server/token.c", "server/protocol.def",
            "dlls/ntdll/unix/process.c", "dlls/windows.system.launcher/main.c",
            "dlls/twinapi.appcore/core_application.c", "dlls/windows.ui/corewindow_host.c")}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    print(freeze(args.root, args.producer_commit))
