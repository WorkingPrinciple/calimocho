"""Configure and build an isolated Vulkan overlay, preserving the port-10 install."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

if __package__:
    from .build_moltenvk import COMMIT
    from .probe_wine_source import run_step, sha256
else:
    from build_moltenvk import COMMIT
    from probe_wine_source import run_step, sha256


REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/winehq-11.20/metal-port-10-03"
MODULES = ("win32u", "winevulkan", "vulkan-1", "winemac.drv")


def build(output, dependency, finish_only=False):
    output = output.resolve()
    dependency = dependency.resolve()
    if not output.is_relative_to(REPO / "build") or (output.exists() and not finish_only):
        raise ValueError("Require a new owned build directory")
    dep = json.loads((dependency / "receipt.json").read_text())
    library = Path(dep["library"])
    if dep["commit"] != COMMIT or dep["status"] != "source-built-not-runtime-qualified":
        raise ValueError("Require successful pinned source-built MoltenVK")
    if sha256(library) != dep["library_sha256"]:
        raise ValueError("MoltenVK artifact checksum mismatch")
    baseline = json.loads((BASE / "receipt.json").read_text())
    output.mkdir(parents=True, exist_ok=finish_only)
    source, directory, install = (output / name for name in ("source", "build", "install"))
    if not finish_only:
        shutil.copytree(BASE / "winehq-source", source, symlinks=True)
        shutil.copytree(BASE / "build", directory, symlinks=True)
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_", "PKG_CONFIG"))
                   and key not in {"CPATH", "LIBRARY_PATH", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS"}}
    environment.update(baseline["environment"])
    tls = REPO / "build/dependencies/tls-x86_64-01/prefix"
    ft = REPO / "build/dependencies/freetype-2.13.3-x86_64-02/prefix"
    environment.update(
        PATH=f"/opt/homebrew/opt/bison/bin:{environment['PATH']}",
        LDFLAGS=f"-L{library.parent} -Wl,-rpath,{library.parent} {environment['LDFLAGS']}",
        ac_cv_lib_soname_MoltenVK="@rpath/libMoltenVK.dylib",
        ac_cv_lib_soname_gnutls="@rpath/libgnutls.30.dylib",
        DYLD_FALLBACK_LIBRARY_PATH=f"{library.parent}:{tls / 'lib'}:{ft / 'lib'}:/usr/lib",
    )
    receipt = {
        "status": "incomplete", "base_install": str(BASE / "install"),
        "base_receipt_sha256": sha256(BASE / "install-receipt.json"),
        "moltenvk_receipt_sha256": sha256(dependency / "receipt.json"),
        "moltenvk_sha256": sha256(library), "moltenvk": str(library),
        "source_tree_route": "copy of port10 exact configured source",
        "environment": {key: environment[key] for key in baseline["environment"]},
        "soname": "@rpath/libMoltenVK.dylib", "steps": [], "overlay": [],
        "runtime_executed": False, "game_qualified": False,
    }
    if finish_only:
        receipt = json.loads((output / "receipt.json").read_text())
        if receipt["moltenvk_sha256"] != sha256(library) or not all(
                step["exit_code"] == 0 and not step["timed_out"] for step in receipt["steps"]):
            raise ValueError("Cannot finish unsuccessful configure/compile")
        receipt["overlay"] = []

    def save():
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def run(name, args, timeout=900):
        step = run_step(args, directory, environment, output / f"{name}.log", timeout)
        receipt["steps"].append(step)
        save()
        if step["exit_code"] or step["timed_out"]:
            raise RuntimeError(f"{name} failed; see {output / (name + '.log')}")

    save()
    args = [str(source / "configure")] + baseline["steps"][0]["command"][1:]
    args = [arg for arg in args if not arg.startswith("--prefix=")]
    args += ["--with-vulkan", f"--prefix={install}"]
    if not finish_only:
        run("configure", args, 300)
    config = (directory / "include/config.h").read_text()
    if '#define SONAME_LIBVULKAN "@rpath/libMoltenVK.dylib"' not in config:
        raise ValueError("Configure did not enable exact Vulkan SONAME")
    receipt["config_sha256"] = sha256(directory / "include/config.h")
    if not finish_only:
        run("compile", ["/usr/bin/make", "-j4"] + [f"dlls/{module}/all" for module in MODULES])
        shutil.copytree(BASE / "install", install, symlinks=True)
    for module in MODULES:
        filename = module if module.endswith(".drv") else module + ".dll"
        for arch in ("x86_64", "i386"):
            relative = f"lib/wine/{arch}-windows/{filename}"
            built = directory / f"dlls/{module}/{arch}-windows/{filename}"
            destination = install / relative
            old = sha256(BASE / "install" / relative)
            shutil.copy2(built, destination)
            receipt["overlay"].append({"path": relative, "old_sha256": old, "sha256": sha256(destination)})
        if module != "vulkan-1":
            unix_name = "winemac" if module == "winemac.drv" else module
            relative = f"lib/wine/x86_64-unix/{unix_name}.so"
            built, destination = directory / f"dlls/{module}/{unix_name}.so", install / relative
            old = sha256(BASE / "install" / relative)
            shutil.copy2(built, destination)
            receipt["overlay"].append({"path": relative, "old_sha256": old, "sha256": sha256(destination)})
    loads = subprocess.check_output(["otool", "-l", str(install / "lib/wine/x86_64-unix/win32u.so")],
                                    text=True, timeout=30)
    if str(library.parent) not in loads:
        raise ValueError("win32u.so lacks explicit MoltenVK RPATH")
    receipt.update(status="overlay-built-not-runtime-qualified", install=str(install),
                   win32u_load_commands=loads)
    save()
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dependency", required=True, type=Path)
    parser.add_argument("--finish-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.dependency, args.finish_only), indent=2))
