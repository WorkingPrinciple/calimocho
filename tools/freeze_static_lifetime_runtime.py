"""Freeze a new012 source-built sibling using the actual011 supported XAML recipe."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256

PREVIOUS = REPO / "build/winehq-11.20/package-uwp-observed-xaml-01/cell011-receipt.json"
SOURCES = ("tools/freeze_static_lifetime_runtime.py", "tools/build_uwp_overlay.py",
           "tools/stage_uwp_overlay.py", "tools/diagnose_package_activation.py",
           "tools/port_uwp_activation.py", "patches/wine/files/core_application_activated.c",
           "patches/wine/files/corewindow_host.c", "patches/wine/files/package_activation.idl",
           "patches/wine/files/package_activation_record.h", "tests/uwp_activation_probe.c",
           "tests/package_activation_probe.c")


# Cells027-036 admit ALPC only together with the registrar token and thread dispatch it depends on.
REGISTRAR_STACK = ("alpc_transport", "restricted_token", "alpc_identity", "token_identity", "token_security",
                   "alpc_impersonation", "registrar_service", "coremsg_dispatch")


def freeze(root, producer, *, cell=12, predecessor=PREVIOUS,
           predecessor_sha256="7c61c26de2fcbaf1814e09b1e2b91afd925f49c5f1827ae73b33fe44ac78a83c",
           extra_sources=()):
    root = Path(root).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or any(root.glob("*FROZEN*")):
        raise ValueError("Require an unfrozen owned012 sibling")
    build_path = root / "build-receipt.json"
    build = json.loads(build_path.read_text())
    if "alpc_transport" in build and (cell not in (27, 28, 29, 30, 31, 32, 33, 34, 35, 36) or any(key not in build for key in REGISTRAR_STACK)):
        raise ValueError("Transport-only ALPC builds are not registrar-qualified or runtime-admissible")
    producer = subprocess.check_output(
        ["git", "rev-parse", "--verify", producer + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for relative in SOURCES + tuple(extra_sources):
        blob = subprocess.check_output(["git", "show", producer + ":" + relative], cwd=REPO)
        if blob != (REPO / relative).read_bytes():
            raise ValueError("Producer source changed: " + relative)
        sources[relative] = hashlib.sha256(blob).hexdigest()
    if cell not in (12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36) or sha256(predecessor) != predecessor_sha256:
        raise ValueError("Sealed predecessor recipe changed or unsupported cell")
    previous = json.loads(predecessor.read_text())
    label = "%03d" % cell
    run = Path("/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-" + label)
    if run.exists():
        raise FileExistsError("Refuse existing012 run")
    for key in ("native_xaml_registration", "native_mapping", "factory_observation", "factory_results",
                "verification", "graph", "framework_registration", "protocol_table", "server_registration_table"):
        if sha256(Path(previous[key])) != previous[key + "_sha256"]:
            raise ValueError("011 bound input changed: " + key)
    if inventory(Path(previous["install"])) != json.loads(Path(previous["inventory"]).read_text())["files"]:
        raise ValueError("Frozen009 install changed")
    if sha256(Path(previous["target_observer"]["path"])) != previous["target_observer"]["sha256"]:
        raise ValueError("Target handle observer changed")
    stage_path = root / "staging-receipt.json"
    stage = json.loads(stage_path.read_text())
    if (stage["runtime_executed"] or stage["status"] != "staged-not-runtime-qualified"
            or build["runtime_executed"] or build["status"] != "built-not-staged-not-executed"
            or sha256(build_path) != stage["build_receipt_sha256"]
            or not build["steps"] or any(step["exit_code"] or step["timed_out"] for step in build["steps"])):
        raise ValueError("Require successful012 source build and unexecuted stage")
    for relative, digest in build["source_inputs"].items():
        if sha256(REPO / relative) != digest:
            raise ValueError("Built source changed")
    for relative, digest in build["built_files"].items():
        if sha256(root / relative) != digest:
            raise ValueError("Compiled artifact changed")
    install = root / "install"
    if inventory(install) != stage["files"] or stage["helper_exit"] or stage["probe_exit"]:
        raise ValueError("Staged012 inventory changed")
    for key in ("helper", "probe"):
        if (sha256(Path(stage[key])) != stage[key + "_sha256"]
                or stage[key + "_source_sha256"] != sources[
                    "tests/package_activation_probe.c" if key == "helper" else "tests/uwp_activation_probe.c"]):
            raise ValueError("Compiled fixture/observer changed")
    registry = json.loads(Path(stage["registry"]).read_text())
    if sha256(Path(stage["registry"])) != stage["registry_sha256"]:
        raise ValueError("Candidate registry changed")
    entry = registry["engines"][0]
    checked_assets(entry)
    manifest = root / ("inventory-CELL" + label + "-FROZEN.json")
    registry_path = root / ("static-lifetime.registry.local.CELL" + label + "-FROZEN.json")
    collector = root / ("diagnose_package_activation-cell" + label + ".py")
    registration = root / ("launcher-CELL" + label + "-FROZEN.reg")
    receipt_path = root / ("cell" + label + "-receipt.json")
    for path in (manifest, registry_path, collector, registration, receipt_path):
        if path.exists():
            raise FileExistsError("Refuse existing012 handoff artifact")
    manifest.write_text(json.dumps({"files": stage["files"], "basis": "source/build integrity, not native acceptance"},
                                   indent=2) + "\n")
    entry["environment"]["WINEDLLOVERRIDES"] = previous["environment"]["WINEDLLOVERRIDES"]
    entry["name"] = "calimocho-wine11.20-static-lifetime-diagnostic" + {
        12: "", 13: "-state", 14: "-calltrace", 15: "-activation-waits", 16: "-handle-provenance", 17: "-exception", 18: "-lifetime19", 19: "-failfast", 20: "-status", 21: "-claims-site-b", 22: "-claims-thread-token", 23: "-claims-packaged-thread", 24: "-onecore-transform", 25: "-native-coremessaging", 26: "-native-coremessaging-ordinal-guards",
        27: "-registrar-dispatch", 28: "-registrar-start-diagnostics", 29: "-headless-setup", 30: "-setup-timeout", 31: "-setup-timeout-rerun", 32: "-registrar-token-worker", 33: "-server-request-limits", 34: "-transient-sd", 35: "-connect-security", 36: "-connect-security-sentinel"}[cell]
    entry["version"] += " + genuine IStaticLifetime map (UNQUALIFIED)"
    entry["integrity"] = {"status": "unchanged", "manifest_path": str(manifest),
                          "manifest_sha256": sha256(manifest)}
    entry["source_patches"] += [
        {"path": str(REPO / relative), "sha256": digest, "role": "012 static-lifetime source"}
        for relative, digest in sources.items() if relative.startswith("patches/")]
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    shutil.copy2(REPO / "tools/diagnose_package_activation.py", collector)
    dll = install / "lib/wine/x86_64-windows/windows.system.launcher.dll"
    registration.write_bytes((
        "Windows Registry Editor Version 5.00\r\n\r\n"
        "[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\Windows.System.Launcher]\r\n"
        '"DllPath"="' + dos(dll).replace("\\", "\\\\") + '"\r\n"ThreadingModel"="both"\r\n').encode("utf-16"))
    env = dict(previous["environment"], **entry["environment"],
               WINEPREFIX=str(run / "prefix"), WINEARCH="win64")
    wine = ["/usr/bin/arch", "-x86_64", entry["wine"]]
    receipt = copy.deepcopy(previous)
    receipt.update(
        scope="cell" + label + " genuine CoreApplication IStaticLifetime and static factory collection",
        status="source-built" + label + "; native unexecuted", runtime_executed=False,
        producer_commit=producer, source_inputs=sources,
        predecessor_receipt=str(predecessor), predecessor_receipt_sha256=sha256(predecessor),
        engine=entry["name"], install=str(install), registry=str(registry_path),
        registry_sha256=sha256(registry_path), inventory=str(manifest), inventory_sha256=sha256(manifest),
        wine_sha256=entry["sha256"], wineserver_sha256=entry["wineserver_sha256"],
        ntdll_sha256=sha256(install / "lib/wine/x86_64-windows/ntdll.dll"),
        launcher_sha256=sha256(dll), server_source_sha256=sha256(root / "source/server/process.c"),
        build_receipt=str(build_path), build_receipt_sha256=sha256(build_path),
        staging_receipt=str(stage_path), staging_receipt_sha256=sha256(stage_path),
        helper=stage["helper"], helper_sha256=stage["helper_sha256"],
        diagnostic_collector=str(collector), diagnostic_collector_sha256=sha256(collector),
        diagnostic_collector_argv=[sys.executable, str(collector), str(receipt_path),
                                   "--output", str(run / "evidence/activation-redacted.json")],
        prefix=str(run / "prefix"), evidence=str(run / "evidence"), environment=env,
        server_stop=[entry["wineserver"], "-k"], server_wait=[entry["wineserver"], "-w"],
        server_start={"argv": [entry["wineserver"], "-p"], "environment": dict(
            env, CALIMOCHO_PACKAGE_REGISTRATION=previous["server_registration_table"])},
        activation_argv=wine + [stage["helper"], *previous["activation_argv"][4:]],
        framework_registration_argv=wine + previous["framework_registration_argv"][3:],
        native_xaml_registration_argv=wine + previous["native_xaml_registration_argv"][3:],
        launcher_registration=str(registration), launcher_registration_sha256=sha256(registration),
        launcher_registration_argv=wine + ["regedit", "/S", dos(registration)],
        target_observer=dict(previous["target_observer"], argv=wine + [previous["target_observer"]["path"]]),
        native_fixture=stage["probe"], native_fixture_sha256=stage["probe_sha256"],
        native_fixture_argv=wine + [stage["probe"], "--static-lifetime"],
        native_fixture_status="compiled headless map contract fixture, not executed",
        changed_modules=stage["changed_files"],
        generated_source_sha256={
            relative: sha256(root / "source" / relative)
            for relative in previous["generated_source_sha256"]},
        preconditions=[
            "Fresh private/no-input" + label + " prefix; preserve all sealed predecessors",
            "Use retained original native XAML input and558 supported011 mappings, no native DLL rewrite",
            "Import framework_registration_argv, launcher_registration_argv, native_xaml_registration_argv",
            "Stop/wait setup server, then start server_start using explicit host-only table",
            "Execute bounded collector/target observer; clean only" + label + " prefix and retain proof",
        ],
        limitations=[item for item in previous["limitations"]
                     if item != "Same frozen009 install, not a new engine or rebuilt ABI"] + [
            "IStaticLifetime is Microsoft's C++/WinRT lifetime cache ABI, not a CoreApplication SDK statics interface",
            "Collection delegates real thread-safe string/object storage to Wine PropertySet with retained references",
            "Reserved undocumented slot returns explicit E_NOTIMPL; unknown interfaces remain E_NOINTERFACE",
            "012 source/build does not prove native XAML progression, activation delivery or UI",
        ])
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    print(freeze(args.root, args.producer_commit))
