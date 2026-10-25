"""Build a headless exact-factory matrix against an observed public class list."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from tools.build_gameinput_overlay import compile_flags, WINE
from tools.build_uwp_overlay import REPO
from tools.probe_wine_source import sha256


def build(root, export_path):
    root = Path(root).resolve()
    export_path = Path(export_path).resolve(strict=True)
    if not root.is_relative_to(REPO / "build") or root.exists():
        raise ValueError("Require new owned probe output")
    export = json.loads(export_path.read_text())
    classes = sorted(row["className"] for row in export["classes"]
                     if row["className"].startswith("Windows.UI.Xaml."))
    if (not classes or len(classes) > 1024 or len(classes) != len(set(classes))
            or any(not re.fullmatch(r"[A-Za-z0-9_.]{1,511}", name) for name in classes)
            or "Windows.UI.Xaml.FrameworkViewSource" not in classes):
        raise ValueError("Invalid observed XAML class list")
    root.mkdir()
    names = root / "classes.txt"
    names.write_text("\n".join(classes) + "\n", encoding="ascii")
    base = REPO / "build/winehq-11.20/package-uwp-01"
    source = REPO / "tests/native_xaml_factory_probe.c"
    compiler = Path(shutil.which("x86_64-w64-mingw32-gcc")).resolve(strict=True)
    libraries = [base / "build/dlls/combase/x86_64-windows/libcombase.a",
                 WINE / "build/libs/uuid/x86_64-windows/libuuid.a"]
    output = root / "native-xaml-factory-probe.exe"
    command = [str(compiler), "-I" + str(base / "source/include"),
               *compile_flags(base / "build/include"), "-D_UCRT", "-municode",
               "-Wall", "-Wextra", "-Werror", str(source), *map(str, libraries), "-o", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (root / "build.log").write_text(result.stdout + result.stderr)
    receipt = {"scope": "genuine native factory matrix; no ActivateInstance, Run or registration",
               "export": str(export_path), "export_sha256": sha256(export_path),
               "classes": str(names), "classes_sha256": sha256(names), "class_count": len(classes),
               "argv": command, "exit_code": result.returncode, "runtime_executed": False,
               "inputs": {str(path): sha256(path) for path in [source, compiler, *libraries]},
               "expected_native_sha256": "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899"}
    if result.returncode:
        (root / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        raise RuntimeError("Probe compile failed; retained log")
    receipt.update(probe=str(output), probe_sha256=sha256(output))
    path = root / "build-receipt.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--export", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.root, args.export))
