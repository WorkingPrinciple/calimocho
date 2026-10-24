"""Emit a distinct local port-11 record only from observed owned probe receipts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

if __package__:
    from .probe_wine_source import sha256
else:
    from probe_wine_source import sha256


REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/winehq-11.20/metal-port-10-03"
ROOT = REPO / "build/winehq-11.20/metal-port-11"
NAME = "calimocho-wine11.20-gptk4b3-tls-vulkan"


def replace_strings(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    return value


def observation(path, kind):
    wrapper = json.loads(path.read_text())
    receipt_path = Path(wrapper["receipt"])
    receipt = json.loads(receipt_path.read_text())
    if (wrapper["probe"] != kind or not wrapper["foreground_unchanged"]
            or not wrapper["port10_unchanged"] or not receipt["payload_hashes_unchanged"]
            or receipt["residual_process_groups"]
            or receipt["prefix_open_files_check"] != dict(exit_code=1, stdout="", stderr="")):
        raise ValueError(f"{kind}: failed passive safety/cleanup evidence")
    commands = receipt["commands"]
    probes = [step for step in commands if step["name"] == "create-device"]
    if len(probes) != 1:
        raise ValueError(f"{kind}: missing unique probe")
    probe = probes[0]
    if any(step["timed_out"] or step["exit_code"] != 0 for step in commands if step is not probe):
        raise ValueError(f"{kind}: setup/cleanup command failed")
    if probe["timed_out"] or probe["exit_code"] != (1 if kind == "https-expired" else 0):
        raise ValueError(f"{kind}: incorrect probe outcome")
    stdout = Path(probe["stdout_log"]).read_text(errors="replace")
    stderr = Path(probe["stderr_log"]).read_text(errors="replace")
    if any(sha256(Path(step[f"{channel}_log"])) != step[f"{channel}_sha256"]
           for step in commands for channel in ("stdout", "stderr")):
        raise ValueError(f"{kind}: command logs changed")
    if kind in ("vulkan", "d3d11", "d3d12"):
        if not receipt.get("window_capture", {}).get("nonoverlap"):
            raise ValueError(f"{kind}: missing native non-overlap binding")
        if kind == "vulkan":
            if ("SUMMARY presented=120 expected=120 result=0" not in stdout
                    or "readback RGBA=51,102,204,255 expected=51,102,204,255" not in stdout
                    or stdout.count("vkQueuePresentKHR VkResult=0") != 120):
                raise ValueError("Vulkan: missing exact presentation/readback thresholds")
        elif ("readback_pixel rgba=51,102,204,255 expected=51,102,204,255 matched=1" not in stdout
              or "Present count=120 target=120 last_HRESULT=0x00000000 result=0" not in stdout):
            raise ValueError(f"{kind}: missing pixel/frame evidence")
    elif kind == "https-expired":
        if "cert verify failed: 12037" not in stderr:
            raise ValueError("Expired certificate: missing actual date-invalid diagnostic")
    elif ("HTTPS status=200 certificate_validation=enabled" not in stdout
          or "HTTPS result=0" not in stdout):
        raise ValueError("HTTPS: missing HTTP 200")
    return {"kind": kind, "receipt_path": str(receipt_path), "receipt_sha256": sha256(receipt_path),
            "passive_guard_path": str(path), "passive_guard_sha256": sha256(path),
            "probe_sha256": receipt["probe_sha256"], "commands": commands,
            "process_environment": receipt["environment"], "fresh_prefix": receipt["prefix"]}


def emit(paths, private_api=False):
    observations = {kind: observation(Path(path), kind) for kind, path in paths.items()}
    if set(observations) != {"vulkan", "d3d11", "d3d12", "https", "https-expired"}:
        raise ValueError("Require Vulkan, both D3D and both HTTPS observations")
    if private_api:
        receipt = json.loads(Path(observations["vulkan"]["receipt_path"]).read_text())
        probe = next(step for step in receipt["commands"] if step["name"] == "create-device")
        stdout = Path(probe["stdout_log"]).read_text()
        load = receipt.get("window_capture", {}).get("private_moltenvk_load")
        if ("wideLines supported=1 required=1 enabled=1" not in stdout
                or "vkCreateDevice VkResult=0" not in stdout or not load
                or sha256(Path(load["path"])) != load["sha256"]
                or receipt["environment"].get("MVK_CONFIG_USE_METAL_PRIVATE_API") != "1"
                or receipt["environment"].get("WINELOADER") != str(ROOT / "install/bin/wine")
                or receipt["environment"].get("WINESERVER") != str(ROOT / "install/bin/wineserver")
                or Path(load["path"]) != ROOT / "install/lib/wine/x86_64-unix/libMoltenVK.dylib"):
            raise ValueError("Private API requires actual wideLines device and bound dylib load")
    base_path = BASE / "calimocho-wine11.20-gptk4b3-tls.registry.local.json"
    if sha256(base_path) != "13bc00b7f8e1496cd2b02822d75bc00b2b366b37692ff3701db083b45e56c1c4":
        raise ValueError("Frozen port10 record changed")
    record = replace_strings(json.loads(base_path.read_text()), str(BASE / "install"), str(ROOT / "install"))
    engine = record["engines"][0]
    engine.update(name=NAME, version="WineHQ 11.20 native-GS port-11 + TLS + MoltenVK1.4.2 + GPTK4.0b3",
                  provider={"id": "calimocho", "contract_version": 1})
    engine["environment"]["MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS"] = "1"
    if private_api:
        engine["environment"]["MVK_CONFIG_USE_METAL_PRIVATE_API"] = "1"
        engine["version"] += " private-Metal diagnostic"
    for dep in engine["dependencies"]:
        dep["sha256"] = sha256(Path(dep["path"]))
    mvk = json.loads((ROOT / "receipt.json").read_text())
    if private_api and (load["sha256"] != mvk["moltenvk_sha256"]
                        or load["path"] != mvk["moltenvk"]):
        raise ValueError("Private API receipt and observed loader binding differ")
    engine["dependencies"].append({
        "name": "source-built MoltenVK", "version": "1.4.2", "path": mvk["moltenvk"],
        "sha256": mvk["moltenvk_sha256"], "source_url": "https://github.com/KhronosGroup/MoltenVK.git",
        "source_commit": "db66022459ffb663aa2b50f6b018bc2e124f5edf",
        "license": "Apache-2.0", "architecture": "x86_64",
    })
    assets = engine["profile_assets"]["files"]
    existing = {item["path"] for item in assets}
    for item in mvk["overlay"]:
        path = str(ROOT / "install" / item["path"])
        if path not in existing:
            assets.append({"path": path, "sha256": item["sha256"]})
    for item in assets:
        item["sha256"] = sha256(Path(item["path"]))
    smoke = observations["vulkan"]
    engine["smoke_test"] = {
        "status": "pass", "tested_at": datetime.now(timezone.utc).isoformat(),
        "wine_sha256": engine["sha256"], "probe_sha256": smoke["probe_sha256"],
        "fresh_prefix": smoke["fresh_prefix"],
        "commands": [step["command"] for step in smoke["commands"]],
        "exit_codes": [step["exit_code"] for step in smoke["commands"]],
        "environment": engine["environment"], "process_environment": smoke["process_environment"],
        "log_path": next(step["stdout_log"] for step in smoke["commands"] if step["name"] == "create-device"),
        "receipt_path": smoke["receipt_path"], "receipt_sha256": smoke["receipt_sha256"],
        "scope": "Owned Vulkan instance/device/surface/120 Presents/exact readback; no game/input claim",
    }
    engine["smoke_test"]["log_sha256"] = sha256(Path(engine["smoke_test"]["log_path"]))
    engine["graphics_tests"] = [observations[kind] for kind in ("vulkan", "d3d11", "d3d12")]
    engine["tls_negative_test"] = observations["https-expired"]
    engine["tls_positive_test"] = observations["https"]
    engine.pop("rpath_resolution_test", None)
    engine["build_evidence"] = {
        "base_registry_path": str(base_path), "base_registry_sha256": sha256(base_path),
        "configure_receipt_path": str(ROOT / "receipt.json"),
        "configure_receipt_sha256": sha256(ROOT / "receipt.json"),
        "moltenvk_receipt_sha256": mvk["moltenvk_receipt_sha256"],
        "route": "Separate Vulkan overlay; no mouse correction; local source-built dependencies",
    }
    engine["integrity"] = {
        "status": "unchanged", "manifest_path": str(ROOT / "base-comparison.json"),
        "manifest_sha256": sha256(ROOT / "base-comparison.json"),
        "scope": ("Twelve declared overlay files, including colocated private MoltenVK, differ from port10"
                  if private_api else
                  "Exactly eleven declared Vulkan overlay files differ from unchanged port10"),
    }
    output = ROOT / f"{NAME}.registry.local.json"
    if output.exists():
        raise ValueError("Do not overwrite a frozen emitted record")
    output.write_text(json.dumps(record, indent=2) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for kind in ("vulkan", "d3d11", "d3d12", "https", "https-expired"):
        parser.add_argument(f"--{kind}", required=True, type=Path)
    args = vars(parser.parse_args())
    print(emit({key.replace("_", "-"): value for key, value in args.items()}))
