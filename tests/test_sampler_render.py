"""REQ-104 isolated GPU regression runner. Requires an exclusive execution grant."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(args):
    if not args.execute:
        raise ValueError("GPU execution requires --execute and an exclusive parent grant")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    env = dict(os.environ, MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS="1",
               MVK_CONFIG_USE_METAL_PRIVATE_API="1", MTL_HUD_ENABLED="0")
    for label, library in (("baseline", args.baseline), ("candidate", args.candidate)):
        # REQ-104: never imply that a diagnostic can exceed supported limits by default.
        guard = subprocess.run(
            [str(args.runner), str(library), "regular", str(args.fixtures / "regular.spv")],
            env=env, capture_output=True, text=True, timeout=45)
        if guard.returncode != 77:
            raise AssertionError(f"{label}: expected honest-limit guard exit77")
        for mode in ("push", "template", "partial", "regular", "mixed", "graphics"):
            shader = mode if mode in ("regular", "mixed", "graphics") else "push"
            result = subprocess.run(
                [str(args.runner), str(library), mode,
                 str(args.fixtures / f"{shader}.spv"), "--exercise-unsupported"],
                env=env, capture_output=True, text=True, timeout=45)
            stem = args.output / f"{label}-{mode}"
            stem.with_suffix(".stdout.log").write_text(result.stdout)
            stem.with_suffix(".stderr.log").write_text(result.stderr)
            expected_failure = label == "baseline" and mode not in ("regular", "mixed")
            # REQ-104: reproduce direct sampler allocation, not an unrelated failure.
            if expected_failure:
                correct = (result.returncode == 1 and "VkResult -3" in result.stderr
                           and "sampler" in result.stderr
                           and ("cannot reserve" in result.stderr
                                or "exceeds the maximum" in result.stderr))
            else:
                correct = (result.returncode == 0
                           and result.stdout.count("observed=[0xaaaa,0x15555]") == 2
                           and result.stdout.count("result=PASS") == 2
                           and "[mvk-error]" not in result.stderr)
            rows.append({"library": label, "mode": mode,
                         "library_sha256": digest(library),
                         "shader_sha256": digest(args.fixtures / f"{shader}.spv"),
                         "stdout_sha256": digest(stem.with_suffix(".stdout.log")),
                         "stderr_sha256": digest(stem.with_suffix(".stderr.log")),
                         "exit_code": result.returncode, "expected_failure": expected_failure,
                         "oracle_passed": correct})
            print(f"{label}-{mode}: {'PASS' if correct else 'FAIL'} exit{result.returncode}",
                  flush=True)
    receipt = {"requirement": "REQ-104", "runner_sha256": digest(args.runner),
               "diagnostic_exceeds_advertised_limit": True,
               "advertised_per_stage_samplers": 16,
               "nms_threshold": "unknown", "game_accepted": False,
               "results": rows, "all_oracles_passed": all(row["oracle_passed"] for row in rows)}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not receipt["all_oracles_passed"]:
        raise AssertionError(f"Unexpected results; see {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runner", "baseline", "candidate", "fixtures", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    options = parser.parse_args()
    for name in ("runner", "baseline", "candidate", "fixtures", "output"):
        setattr(options, name, getattr(options, name).resolve())
    check(options)
