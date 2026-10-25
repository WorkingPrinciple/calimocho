"""Derive cell011 only from a complete genuine native-factory observation."""
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
from tools.native_activation_map import render_registrations, select, supported_factories
from tools.probe_wine_source import sha256

BASE = REPO / "build/winehq-11.20/package-uwp-native-xaml-01"
PROBE = REPO / "build/winehq-11.20/native-xaml-factory-probe-02"
SOURCES = ("tools/prepare_observed_xaml_recipe.py", "tools/native_activation_map.py",
           "tests/native_xaml_factory_probe.c", "tools/build_native_xaml_probe.py")
NATIVE_SHA = "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899"


def prepare(root, observation_path, producer):
    root = Path(root).resolve()
    observation_path = Path(observation_path).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or root.exists():
        raise ValueError("Require a new owned011 recipe output")
    producer = subprocess.check_output(
        ["git", "rev-parse", "--verify", producer + "^{commit}"], cwd=REPO, text=True).strip()
    source_inputs = {}
    for relative in SOURCES:
        blob = subprocess.check_output(["git", "show", producer + ":" + relative], cwd=REPO)
        if blob != (REPO / relative).read_bytes():
            raise ValueError("Producer source differs: " + relative)
        source_inputs[relative] = hashlib.sha256(blob).hexdigest()
    old_path = BASE / "cell010-receipt.json"
    if sha256(old_path) != "2111cfeb4d62e2fe0dcc11cfd3d70114a53a587e7f333fca0f971387956a7d16":
        raise ValueError("Sealed010 recipe changed")
    old = json.loads(old_path.read_text())
    entry = json.loads(Path(old["registry"]).read_text())["engines"][0]
    if sha256(Path(old["registry"])) != old["registry_sha256"]:
        raise ValueError("Sealed010 registry changed")
    checked_assets(entry)
    if inventory(Path(old["install"])) != json.loads(Path(old["inventory"]).read_text())["files"]:
        raise ValueError("Frozen engine changed")
    probe_path = PROBE / "build-receipt.json"
    probe = json.loads(probe_path.read_text())
    for key in ("classes", "probe", "export"):
        if sha256(Path(probe[key])) != probe[key + "_sha256"]:
            raise ValueError("Probe input changed: " + key)
    for path, digest in probe["inputs"].items():
        if sha256(Path(path)) != digest:
            raise ValueError("Probe build input changed: " + path)
    observed = json.loads(observation_path.read_text())
    if (observed["probe_sha256"] != probe["probe_sha256"]
            or observed["classes_sha256"] != probe["classes_sha256"]
            or observed["native_sha256"] != NATIVE_SHA
            or observed["exit_code"] != 0 or observed["timed_out"]
            or not observed["cleanup_complete"]):
        raise ValueError("Require completed exact native-factory observation and owned cleanup")
    output = Path(observed["output"]).resolve(strict=True)
    if sha256(output) != observed["output_sha256"]:
        raise ValueError("Native probe observation changed")
    classes = Path(probe["classes"]).read_text(encoding="ascii").splitlines()
    supported = supported_factories(classes, output.read_text(encoding="ascii"))
    if "Windows.UI.Xaml.FrameworkViewSource" not in supported:
        raise ValueError("Actual missing FrameworkViewSource factory is not supported")
    export = json.loads(Path(probe["export"]).read_text())
    decisions = select(export, [{"dll_path": r"C:\Windows\System32\Windows.UI.Xaml.dll",
                                 "sha256": NATIVE_SHA}])
    rows = []
    for row in export["classes"]:
        if row["className"] in supported:
            if (row["values"]["DllPath"].lower() != r"c:\windows\system32\windows.ui.xaml.dll"
                    or row["values"]["ActivationType"] != 0 or row["values"]["Server"] is not None):
                continue
            rows.append(row)
    selected = {row["className"] for row in rows}
    if "Windows.UI.Xaml.FrameworkViewSource" not in selected:
        raise ValueError("No admissible observed FrameworkViewSource mapping")
    for item in decisions["decisions"]:
        if item["class"] in selected:
            item["decision"] = "cross-build-mapping:factory-support-observed"
        elif item["class"] in classes and item["class"] not in supported:
            item["decision"] = "native-factory-unsupported"
    label = ("cross-build mapping: native export " + export["osBuild"]
             + " -> retained " + NATIVE_SHA + ", support observed by probe")
    decisions.update(mapping_basis=label, probe_supported_count=len(supported),
                     selected_classes=sorted(selected),
                     missing_classes=sorted(set(classes) - selected))
    reg_bytes = render_registrations(rows)
    run = Path("/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-011")
    if run.exists():
        raise FileExistsError("Refuse existing011 run")
    root.mkdir()
    registration = root / "observed-native-xaml-CELL011-FROZEN.reg"
    registration.write_bytes(reg_bytes)
    mapping = root / "native-mapping-decisions.json"
    mapping.write_text(json.dumps(decisions, indent=2) + "\n")
    shutil.copy2(observation_path, root / "factory-observation.json")
    shutil.copy2(output, root / "factory-results.txt")
    receipt = copy.deepcopy(old)
    env = dict(old["environment"], WINEPREFIX=str(run / "prefix"))
    receipt_path = root / "cell011-receipt.json"
    wine = ["/usr/bin/arch", "-x86_64", entry["wine"]]
    from tools.prepare_verified_activation import dos
    receipt.update(
        scope="cell011 observed native XAML factory mappings, same frozen009 engine",
        status="recipe derived from actual factory probe;011 native execution unobserved",
        producer_commit=producer, source_inputs=source_inputs, runtime_executed=False,
        predecessor_receipt=str(old_path), predecessor_receipt_sha256=sha256(old_path),
        environment=env, prefix=str(run / "prefix"), evidence=str(run / "evidence"),
        server_start={"argv": old["server_start"]["argv"], "environment": dict(
            env, CALIMOCHO_PACKAGE_REGISTRATION=old["server_registration_table"])},
        native_xaml_registration=str(registration), native_xaml_registration_sha256=sha256(registration),
        native_xaml_registration_argv=wine + ["regedit", "/S", dos(registration)],
        native_mapping=str(mapping), native_mapping_sha256=sha256(mapping),
        native_mapping_basis=label, native_mapping_count=len(rows),
        factory_observation=str(root / "factory-observation.json"),
        factory_observation_sha256=sha256(root / "factory-observation.json"),
        factory_results=str(root / "factory-results.txt"),
        factory_results_sha256=sha256(root / "factory-results.txt"),
        diagnostic_collector_argv=[sys.executable, old["diagnostic_collector"], str(receipt_path),
                                   "--output", str(run / "evidence/activation-redacted.json")],
        preconditions=[
            "Scheduled private/no-input011; preserve sealed008/009/010",
            "Fresh011 prefix with retained original16302bfe native XAML setup, no binary rewrite",
            "Import framework_registration_argv, launcher_registration_argv, then native_xaml_registration_argv",
            "Native mapping imports only actual supported system32 XAML factories; absent DLL classes remain missing",
            "Keep009 builtin CoreApplication and CoreWindow; no matching native target admitted",
            "Stop/wait setup server, start server_start with explicit table/environment",
            "Use bounded collector/target observer, then clean only011 prefix and retain proof",
        ],
        limitations=old["limitations"] + [
            label,
            "Factory/QI support does not establish ActivateInstance, event delivery, window or UI acceptance",
            "Windows export's original DLL hash differs; no same-build/hash match claimed",
        ])
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    print(prepare(args.root, args.observation, args.producer_commit))
