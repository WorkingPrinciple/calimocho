"""REQ-104 compiler regression; no Wine, GPU execution, or game interaction."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, output=None):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=120)
    if output:
        output.write_bytes(result.stdout)
    return result


def check(assembler, baseline, patched, output):
    output.mkdir(parents=True, exist_ok=False)
    fixture = Path(__file__).with_name("spirv_vertex_output.spvasm")
    shader = output / "vertex.spv"
    assembled = run([assembler, fixture, shader])
    if assembled.returncode:
        raise RuntimeError(assembled.stderr.decode())
    results = []
    for mode in ("vertex", "tessellation"):
        generated = {}
        for label, compiler in (("baseline", baseline), ("patched", patched)):
            metal = output / f"{mode}-{label}.metal"
            command = [compiler, shader, "--msl", "--msl-version", "20100"]
            if mode == "tessellation":
                command.append("--msl-vertex-for-tessellation")
            translated = run(command, metal)
            if translated.returncode:
                raise RuntimeError(translated.stderr.decode())
            generated[label] = metal.read_text()
            air = metal.with_suffix(".air")
            compiled = run(["xcrun", "-sdk", "macosx", "metal",
                            "-std=macos-metal2.1", "-c", metal, "-o", air])
            log = metal.with_suffix(".log")
            log.write_bytes(compiled.stderr)
            expected_failure = mode == "tessellation" and label == "baseline"
            # REQ-104: reproduce the exact address-space defect, not any compiler failure.
            if expected_failure:
                if (compiled.returncode == 0 or
                        compiled.stderr.count(b"converts between mismatching address spaces") != 8):
                    raise AssertionError("Baseline must reproduce eight address-space errors")
            elif compiled.returncode or not air.is_file() or air.stat().st_size == 0:
                raise AssertionError(f"{mode}-{label}: {compiled.stderr.decode()}")
            # REQ-104: builtin position remains emitted to the captured device buffer.
            if mode == "tessellation" and "out.gl_Position = in.position;" not in generated[label]:
                raise AssertionError("Builtin output handling changed")
            results.append({"mode": mode, "compiler": label,
                            "metal_sha256": digest(metal),
                            "compile_exit": compiled.returncode,
                            "expected_failure": expected_failure,
                            "diagnostic_sha256": digest(log)})
        # Ordinary vertex translation must stay byte-identical.
        if mode == "vertex" and generated["baseline"] != generated["patched"]:
            raise AssertionError("Non-tessellated vertex translation regressed")
        if mode == "tessellation":
            text = generated["patched"]
            for member in ("position", "tile"):
                for component in "xyzw":
                    if f"Out.{member}.{component} = in.position.{component};" not in text:
                        raise AssertionError("A component store is missing")
                if f"out.Out_{member} = Out.{member};" not in text:
                    raise AssertionError("Output block was not copied to the device buffer")
    receipt = {"requirement": "REQ-104", "status": "source-regression-passed",
               "fixture_sha256": digest(fixture), "spirv_sha256": digest(shader),
               "baseline_sha256": digest(baseline), "patched_sha256": digest(patched),
               "assembler_sha256": digest(assembler), "results": results,
               "gpu_executed": False, "game_accepted": False}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembler", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.assembler.resolve(), args.baseline.resolve(),
          args.patched.resolve(), args.output.resolve())
