"""REQ-104 bisect suite: identity, tessellation red/green and push encoding cost.

Runs headless Vulkan probes against exact libMoltenVK.dylib files only.
No Wine, no game, no prefix. GPU work is a few small draws and dispatches.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess


FIXTURES = ("spirv_vertex_output", "spirv_tess_control", "spirv_tess_eval", "spirv_fragment_red")
# label: (advertised samplers, pipeline cache namespace word, contains PR 2719)
EXPECT = {
    "baseline": (16, "00000000", False),
    "A": (128, "52344131", False),
    "B": (16, "52344231", True),
    "C": (128, "52344331", False),
}
ADDRESS_SPACE = "converts between mismatching address spaces"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, stem, env):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=300, env=env)
    stem.with_suffix(".stdout.log").write_text(result.stdout)
    stem.with_suffix(".stderr.log").write_text(result.stderr)
    return result


def logs(stem):
    return {"stdout_sha256": digest(stem.with_suffix(".stdout.log")),
            "stderr_sha256": digest(stem.with_suffix(".stderr.log"))}


def check(args):
    args.output.mkdir(parents=True, exist_ok=False)
    fixtures = args.output / "fixtures"
    fixtures.mkdir()
    tests = Path(__file__).resolve().parent
    for name in FIXTURES:
        assembled = subprocess.run([str(args.assembler), str(tests / f"{name}.spvasm"),
                                    str(fixtures / f"{name}.spv")], capture_output=True, text=True,
                                   timeout=60)
        if assembled.returncode:
            raise RuntimeError(f"{name}: {assembled.stderr}")
    env = dict(os.environ, MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS="1",
               MVK_CONFIG_USE_METAL_PRIVATE_API="1", MTL_HUD_ENABLED="0")
    libraries = {"baseline": args.baseline}
    for item in args.candidate:
        label, _, path = item.partition("=")
        if label not in EXPECT or label == "baseline" or not path:
            raise ValueError("Candidates must be A=PATH, B=PATH or C=PATH")
        libraries[label] = Path(path).resolve()
    rows = []
    uuid_prefixes = set()
    for label, library in libraries.items():
        limit, namespace, has_2719 = EXPECT[label]
        stem = args.output / f"{label}-identity"
        result = run([args.probe, library, "identity"], stem, env)
        match = re.search(r"pipeline_cache_uuid=([0-9a-f]{32}) ordinary_limit=(\d+) ", result.stdout)
        # REQ-104: each candidate reports its own cache namespace and an honest limit.
        identity_ok = (result.returncode == 0 and match is not None
                       and match.group(1)[24:] == namespace and int(match.group(2)) == limit)
        if match:
            uuid_prefixes.add(match.group(1)[:24])
        rows.append({"library": label, "check": "identity", "library_sha256": digest(library),
                     "exit_code": result.returncode,
                     "pipeline_cache_uuid": match.group(1) if match else None,
                     "ordinary_limit": int(match.group(2)) if match else None,
                     "expected_limit": limit, "expected_namespace": namespace,
                     "oracle_passed": identity_ok, **logs(stem)})
        stem = args.output / f"{label}-tess"
        result = run([args.probe, library, "tess", fixtures], stem, env)
        errors = result.stderr.count(ADDRESS_SPACE)
        plain_ok = "plain_result=PASS" in result.stdout
        if has_2719:
            # REQ-104: with PR 2719 the tessellation pipeline compiles and the
            # rendered triangle proves every vertex output component arrived.
            tess_ok = (result.returncode == 0 and plain_ok and "tess_result=PASS" in result.stdout
                       and errors == 0)
        else:
            # REQ-104: without PR 2719 reproduce the exact float4* to device float*
            # address-space failure (eight component stores), not any failure.
            tess_ok = (result.returncode == 3 and plain_ok and "tess_pipeline=-3" in result.stdout
                       and errors == 8)
        rows.append({"library": label, "check": "tess", "library_sha256": digest(library),
                     "exit_code": result.returncode, "address_space_errors": errors,
                     "expects_pr2719": has_2719, "oracle_passed": tess_ok, **logs(stem)})
        print(f"{label}: identity {'PASS' if identity_ok else 'FAIL'}, "
              f"tess {'PASS' if tess_ok else 'FAIL'} (exit {result.returncode}, {errors} errors)",
              flush=True)
    bench = {}
    bench_labels = [label for label in libraries if EXPECT[label][0] >= 128]
    for round_index in range(args.rounds):
        # Interleave libraries so background load affects every candidate alike.
        for label in bench_labels:
            stem = args.output / f"{label}-bench-{round_index}"
            result = run([args.probe, libraries[label], "bench", args.push_shader,
                          args.dispatches, args.repeats], stem, env)
            found = re.findall(r"bench scenario=(\S+) .*median_submit_us_per_dispatch=([0-9.]+) "
                               r"median_total_us_per_dispatch=([0-9.]+)", result.stdout)
            ok = result.returncode == 0 and len(found) == 3 and "[mvk-error]" not in result.stderr
            rows.append({"library": label, "check": f"bench-round-{round_index}",
                         "library_sha256": digest(libraries[label]), "exit_code": result.returncode,
                         "oracle_passed": ok, **logs(stem)})
            for scenario, submit, total in found:
                entry = bench.setdefault(label, {}).setdefault(scenario, {"submit": [], "total": []})
                entry["submit"].append(float(submit))
                entry["total"].append(float(total))
    summary = {label: {scenario: {"median_submit_us_per_dispatch": statistics.median(v["submit"]),
                                  "median_total_us_per_dispatch": statistics.median(v["total"]),
                                  "rounds_submit": v["submit"], "rounds_total": v["total"]}
                       for scenario, v in scenarios.items()}
               for label, scenarios in bench.items()}
    receipt = {
        "requirement": "REQ-104", "suite": "bisect identity, tessellation and push encoding cost",
        "probe_sha256": digest(args.probe), "assembler_sha256": digest(args.assembler),
        "fixtures": {name: {"spvasm_sha256": digest(tests / f"{name}.spvasm"),
                            "spv_sha256": digest(fixtures / f"{name}.spv")} for name in FIXTURES},
        "push_shader_sha256": digest(args.push_shader),
        "environment": {"MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS": "1",
                        "MVK_CONFIG_USE_METAL_PRIVATE_API": "1", "MTL_HUD_ENABLED": "0"},
        "uuid_prefix_identical_across_libraries": len(uuid_prefixes) == 1,
        "bench_parameters": {"dispatches": args.dispatches, "repeats": args.repeats,
                             "rounds": args.rounds, "samplers": 128},
        "bench_summary": summary,
        "results": rows,
        "wine_executed": False, "game_accepted": False,
    }
    receipt["all_oracles_passed"] = (all(row["oracle_passed"] for row in rows)
                                     and receipt["uuid_prefix_identical_across_libraries"])
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if not receipt["all_oracles_passed"]:
        raise AssertionError(f"Unexpected results; see {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("probe", "assembler", "baseline", "push_shader", "output"):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    parser.add_argument("--candidate", action="append", default=[], help="A=PATH, B=PATH or C=PATH")
    parser.add_argument("--dispatches", type=int, default=20000)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--rounds", type=int, default=3)
    options = parser.parse_args()
    for name in ("probe", "assembler", "baseline", "push_shader", "output"):
        setattr(options, name, getattr(options, name).resolve())
    check(options)
