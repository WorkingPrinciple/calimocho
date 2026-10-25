"""Derive a new native-XAML observation recipe without changing frozen009."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tools.build_gameinput_overlay import compile_flags
from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256

BASE = REPO / "build/winehq-11.20/package-uwp-01"
SOURCE_PATHS = ("tools/prepare_native_xaml_recipe.py", "tools/diagnose_package_activation.py",
                "tests/package_exit_probe.c", "tools/build_gameinput_overlay.py")


def merge_overrides(base, historical):
    modules = {}
    for setting in (base, historical):
        for group in setting.split(";"):
            if not group:
                continue
            names, separator, order = group.partition("=")
            if not separator or order not in ("", "n", "b", "n,b", "b,n"):
                raise ValueError("Invalid retained override")
            for name in names.split(","):
                if not name or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in name):
                    raise ValueError("Invalid override module")
                modules[name] = order
    if modules.get("windows.ui.xaml") != "n":
        raise ValueError("Require explicit native-only Windows.UI.Xaml")
    return ";".join(name + "=" + order for name, order in modules.items())


def prepare(root, profile_path, producer):
    root = Path(root).resolve()
    if not root.is_relative_to(REPO / "build") or root.exists():
        raise ValueError("Require a new owned recipe output")
    producer = subprocess.check_output(
        ["git", "rev-parse", "--verify", producer + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for relative in SOURCE_PATHS:
        blob = subprocess.check_output(["git", "show", producer + ":" + relative], cwd=REPO)
        if blob != (REPO / relative).read_bytes():
            raise ValueError("Producer differs from current source: " + relative)
        sources[relative] = hashlib.sha256(blob).hexdigest()
    previous_path = BASE / "cell009-receipt.json"
    if sha256(previous_path) != "12d7676532262d4673f72c99c1915099cf7751da0934897deefb1629bb3138d4":
        raise ValueError("Frozen009 receipt changed")
    previous = json.loads(previous_path.read_text())
    for key in ("verification", "helper", "graph", "framework_registration", "protocol_table",
                "server_registration_table", "launcher_registration"):
        if sha256(Path(previous[key])) != previous[key + "_sha256"]:
            raise ValueError("Frozen009 input changed: " + key)
    deployed = inventory(Path(previous["install"]))
    if deployed != json.loads(Path(previous["inventory"]).read_text())["files"]:
        raise ValueError("Frozen009 deployment changed")
    registry = json.loads(Path(previous["registry"]).read_text())
    if sha256(Path(previous["registry"])) != previous["registry_sha256"]:
        raise ValueError("Frozen009 registry changed")
    entry = registry["engines"][0]
    checked_assets(entry)
    profile_path = Path(profile_path).resolve(strict=True)
    profile = json.loads(profile_path.read_text())
    # The consumer supplies retained002/003 facts, not a guessed DLL set.
    if (profile["basis"] != "retained-cell002-003" or not profile["registrations"]
            or not profile["evidence"]):
        raise ValueError("Require retained native XAML setup facts")
    for item in profile["evidence"]:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("Retained loader/setup evidence changed")
    native = profile["native_input"]
    if (native["destination"] != "drive_c/windows/system32/Windows.UI.Xaml.dll"
            or native["sha256"] != "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899"
            or sha256(Path(native["path"])) != native["sha256"]):
        raise ValueError("Require original native XAML input, not rewritten sibling")
    overrides = merge_overrides(previous["environment"]["WINEDLLOVERRIDES"], profile["overrides"])
    allowed = {}
    for item in profile["registrations"]:
        if (not item["class"].startswith("Windows.UI.Xaml.")
                or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._"
                       for char in item["class"])
                or item["dll_path"].lower() != r"c:\windows\system32\windows.ui.xaml.dll"
                or item.get("threading_model") not in (None, "both", "apartment", "free")):
            raise ValueError("Unexpected native XAML class registration")
        if item["class"] in allowed:
            raise ValueError("Duplicate native XAML class")
        allowed[item["class"]] = item
    if "Windows.UI.Xaml.Application" not in allowed:
        raise ValueError("Native Application class registration missing")
    root.mkdir()
    shutil.copy2(profile_path, root / "native-profile.json")
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing compiler")
    observer = root / "package-exit-probe.exe"
    command = [compiler, "-I" + str(BASE / "source/include"),
               *compile_flags(BASE / "build/include"), "-D_UCRT", "-municode", "-Wall", "-Wextra", "-Werror",
               str(REPO / "tests/package_exit_probe.c"),
               str(BASE / "build/dlls/ntdll/x86_64-windows/libntdll.a"), "-o", str(observer)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (root / "observer-build.log").write_text(result.stdout + result.stderr)
    (root / "observer-build.json").write_text(json.dumps(
        {"argv": command, "exit_code": result.returncode, "source_sha256": sources["tests/package_exit_probe.c"],
         "inputs": {str(path): sha256(path) for path in (
             Path(compiler).resolve(), BASE / "build/dlls/ntdll/x86_64-windows/libntdll.a",
             BASE / "source/include/wine/package.h")}},
        indent=2) + "\n")
    if result.returncode:
        raise RuntimeError("Target exit observer compilation failed; see retained log")
    run = Path("/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-010")
    if run.exists():
        raise FileExistsError("Refuse an existing010 run")
    receipt = copy.deepcopy(previous)
    env = dict(previous["environment"], WINEPREFIX=str(run / "prefix"), WINEDLLOVERRIDES=overrides)
    entry["environment"]["WINEDLLOVERRIDES"] = overrides
    registry_path = root / "native-xaml.registry.local.CELL010-FROZEN.json"
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    collector = root / "diagnose_package_activation-cell010.py"
    shutil.copy2(REPO / "tools/diagnose_package_activation.py", collector)
    registration = root / "native-xaml-CELL010-FROZEN.reg"
    text = "Windows Registry Editor Version 5.00\r\n\r\n"
    for name, item in allowed.items():
        text += ("[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\" + name + "]\r\n"
                 '"DllPath"="' + item["dll_path"].replace("\\", "\\\\") + '"\r\n')
        if item.get("threading_model"):
            text += '"ThreadingModel"="' + item["threading_model"] + '"\r\n'
        text += "\r\n"
    registration.write_bytes(text.encode("utf-16"))
    verification = json.loads(Path(previous["verification"]).read_text())
    target = next(item for item in verification["routes"]
                  if item["scheme"] == "msxboxl" and item["app_id"] == "Microsoft.Xbox.AppL")
    target_image = dos(target["metadata"]["executable"])
    if sha256(Path(target["metadata"]["executable"])) != target["metadata"]["executable_sha256"]:
        raise ValueError("Verified AppL image changed")
    module_paths = {r"C:\windows\system32\Windows.UI.Xaml.dll": {
        "path": r"C:\windows\system32\Windows.UI.Xaml.dll", "source": "prefix-system32"}}
    for path in sorted(Path(verification["snapshot"]).parent.glob("frameworks/*/Microsoft.UI.Xaml.dll")):
        module_paths[dos(path)] = {"path": dos(path), "source": "verified-framework"}
    wine = ["/usr/bin/arch", "-x86_64", entry["wine"]]
    receipt_path = root / "cell010-receipt.json"
    receipt.update(
        scope="cell010 native XAML loader-selection and exact AppL exit observation recipe",
        status="same frozen009 engine; recipe-only discriminator; native010 unexecuted",
        runtime_executed=False, producer_commit=producer, source_inputs=sources,
        predecessor_receipt=str(previous_path), predecessor_receipt_sha256=sha256(previous_path),
        registry=str(registry_path), registry_sha256=sha256(registry_path),
        prefix=str(run / "prefix"), evidence=str(run / "evidence"), environment=env,
        diagnostic_collector=str(collector), diagnostic_collector_sha256=sha256(collector),
        diagnostic_collector_argv=[sys.executable, str(collector), str(receipt_path),
                                   "--output", str(run / "evidence/activation-redacted.json")],
        server_start={"argv": previous["server_start"]["argv"], "environment": dict(
            env, CALIMOCHO_PACKAGE_REGISTRATION=previous["server_registration_table"])},
        collector_limit_seconds=180,
        target_observer={"path": str(observer), "sha256": sha256(observer),
                         "argv": wine + [str(observer)], "image": target_image,
                         "app_id": "Microsoft.Xbox.AppL"},
        xaml_module_paths=module_paths,
        native_xaml_profile=str(root / "native-profile.json"),
        native_xaml_profile_sha256=sha256(root / "native-profile.json"),
        native_xaml_input=native,
        native_xaml_registration=str(registration), native_xaml_registration_sha256=sha256(registration),
        native_xaml_registration_argv=wine + ["regedit", "/S", dos(registration)],
        observer_build=str(root / "observer-build.json"),
        observer_build_sha256=sha256(root / "observer-build.json"),
        preconditions=[
            "Scheduled private/no-input cell010 only; preserve sealed008/009",
            "Create a fresh010 prefix using the existing explicit native-XAML setup and original DLL hash",
            "Import framework_registration_argv, launcher_registration_argv, then native_xaml_registration_argv",
            "Stop/wait the setup server, then start server_start with its explicit table and override environment",
            "Run diagnostic_collector_argv; observe AppL until handle exit or owner-set180-second bound",
            "Unknown/unrecognized module paths are redacted; no raw URI/output is persisted",
            "Stop/wait only010 prefix and retain cleanup proof; never control DIRT5 or foreign prefixes",
        ],
        limitations=[
            "Same frozen009 install, not a new engine or rebuilt ABI",
            "Native DLL setup belongs to the consumer; no Microsoft binary is copied or rewritten by this tool",
            "A native load is not factory, activation, HWND or UI success",
            "Target exit requires exact image and verified AppId token plus signaled process handle",
            "A missed/dead target, observer error or180-second cap leaves exit unknown",
            "Any remaining pipe drain cutoff is explicit; CE exit is never AppL exit",
        ])
    if inventory(Path(previous["install"])) != deployed:
        raise ValueError("Unexpected frozen009 mutation")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--native-profile", required=True, type=Path)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    print(prepare(args.root, args.native_profile, args.producer_commit))
