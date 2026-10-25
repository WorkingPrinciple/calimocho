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
               MVK_CONFIG_USE_METAL_PRIVATE_API="1", MTL_HUD_ENABLED="0",
               REQ104_SAMPLER_WIDTH=str(args.width))
    for label, library in (("baseline", args.baseline), ("candidate", args.candidate)):
        # REQ-104: never imply that a diagnostic can exceed supported limits by default.
        limit = args.candidate_limit if label == "candidate" else 16
        guard_command = [str(args.runner), str(library), "regular", str(args.fixtures / "regular.spv")]
        if limit >= args.width:
            guard_command.append("--limits-only")
        guard = subprocess.run(
            guard_command,
            env=env, capture_output=True, text=True, timeout=45)
        (args.output / f"{label}-guard.stdout.log").write_text(guard.stdout)
        (args.output / f"{label}-guard.stderr.log").write_text(guard.stderr)
        if guard.returncode != (77 if limit < args.width else 0) or f"ordinary_limit={limit} " not in guard.stdout:
            raise AssertionError(f"{label}: reported-limit guard failed; see retained guard logs")
        modes = ("push", "template", "partial", "regular", "mixed", "graphics")
        if args.extended:
            modes += ("resources", "immutable", "immutable-regular", "immutable-mixed",
                      "immutable-combined", "immutable-combined-regular",
                      "push-core", "template-core", "push2", "template2",
                      "push2-khr", "template2-khr")
            if args.candidate_limit > 16:
                modes += ("variable",)
        for mode in modes:
            shader = ("combined" if "combined" in mode else "mixed" if "mixed" in mode
                      else mode if mode in ("regular", "graphics") else "push")
            result = subprocess.run(
                [str(args.runner), str(library), mode,
                 str(args.fixtures / f"{shader}.spv"), "--exercise-unsupported"],
                env=env, capture_output=True, text=True, timeout=45)
            stem = args.output / f"{label}-{mode}"
            stem.with_suffix(".stdout.log").write_text(result.stdout)
            stem.with_suffix(".stderr.log").write_text(result.stderr)
            expected_failure = label == "baseline" and mode in (
                "push", "template", "partial", "graphics", "resources",
                "push-core", "template-core", "push2", "template2", "push2-khr", "template2-khr")
            if label == "baseline" and args.width >= 64 and mode == "mixed":
                expected_failure = True
            # Baseline immutable push layouts can use constexpr samplers.
            # Characterize either exact readback or the known direct-slot failure.
            if label == "baseline" and mode in ("immutable", "immutable-combined", "immutable-mixed"):
                expected_failure = result.returncode != 0
            # REQ-104: reproduce direct sampler allocation, not an unrelated failure.
            if expected_failure:
                correct = (result.returncode == 1 and "VkResult -3" in result.stderr
                           and "sampler" in result.stderr
                           and ("cannot reserve" in result.stderr
                                or "exceeds the maximum" in result.stderr))
            else:
                first = 0xaaaa if args.width == 17 else (args.width // 2) * (args.width // 2 + 1)
                second = ((0x1ffff if args.width == 17 else args.width * (args.width + 1) // 2)
                          if mode == "resources" else first if mode.startswith("immutable")
                          else 0x15555 if args.width == 17 else (args.width // 2) ** 2)
                correct = (result.returncode == 0
                           and result.stdout.count(f"observed=[0x{first:x},0x{second:x}]") == 2
                           and result.stdout.count("result=PASS") == 2
                           and "[mvk-error]" not in result.stderr)
                if mode == "variable":
                    correct = (result.returncode == 0 and result.stdout.count("result=PASS") == 4
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
               "advertised_per_stage_samplers": args.candidate_limit, "tested_width": args.width,
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
    parser.add_argument("--width", type=int, choices=(17, 32, 64, 128), default=17)
    parser.add_argument("--candidate-limit", type=int, choices=(16, 128), default=16)
    parser.add_argument("--extended", action="store_true",
                        help="Include distinct resources and immutable sampler combinations")
    options = parser.parse_args()
    for name in ("runner", "baseline", "candidate", "fixtures", "output"):
        setattr(options, name, getattr(options, name).resolve())
    check(options)
