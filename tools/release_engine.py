#!/usr/bin/env python3
"""Build, assemble, sign, package and verify a Calimocho engine release.

Run the subcommands in order:

  build     extract the pinned Wine tarball, apply patches/wine-11.20/series,
            configure, compile and install into <work>/destdir
  assemble  lay out a relocatable engine tree, bundle the source-built
            dependencies with @rpath/@loader_path install names, add the
            owner's own copy of the Apple GPTK components (hash-pinned,
            never downloaded and never modified) and write the manifest
  sign      sign every Calimocho Mach-O inside-out with a Developer ID,
            hardened runtime and a secure timestamp (Apple components keep
            Apple's own signature)
  package   write MANIFEST.sha256, a zip archive and the corresponding-source
            tarball for the LGPL components
  verify    unpack the archive into a scratch directory and check every
            signature, the manifest and the Gatekeeper assessment
  registry  render an absolute-path engine registry for an installed copy

Every input is pinned in versions.json under "release_engine". See
docs/ADR/0078-developer-id-signed-engine-release.md.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
APPLE_UNIX_LINKS = ("d3d10", "d3d11", "d3d12", "d3d12core", "dxgi")
FORBIDDEN_LINKAGE = ("/Users/", "/opt/homebrew", "/usr/local", "/private/", "/tmp/")


def pins(args=None):
    return json.loads((REPO / "versions.json").read_text())["release_engine"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            value = "link:" + os.readlink(path)
        elif path.is_file():
            value = sha256(path)
        else:
            continue
        digest.update(f"{relative}\0{value}\n".encode())
    return digest.hexdigest()


def run(command, cwd=None, env=None, log=None, timeout=None):
    print("+ " + " ".join(str(part) for part in command), flush=True)
    if log is None:
        return subprocess.run(command, cwd=cwd, env=env, check=True, timeout=timeout)
    with Path(log).open("w") as stream:
        started = time.monotonic()
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
        stream.write(f"\n# exit {result.returncode} after {time.monotonic() - started:.1f}s\n")
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed ({result.returncode}); see {log}")
    return result


def output(command):
    return subprocess.check_output(command, text=True, timeout=120)


def is_macho(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(4) in MACHO_MAGIC


def is_executable_macho(path):
    return "executable" in output(["file", "-b", str(path)])


def macho_files(root):
    return sorted(p for p in Path(root).rglob("*") if is_macho(p))


def ensure_outside_repo_sources(path):
    path = Path(path).resolve()
    if REPO in path.parents and not (REPO / "build") in path.parents and path != REPO / "build":
        raise ValueError(f"{path} must live under {REPO / 'build'} or outside the repository")
    return path


def toolchain():
    tools = {}
    for name in ("clang", "make"):
        resolved = Path(output(["xcrun", "--find", name]).strip()).resolve()
        tools[name] = {"path": str(resolved), "sha256": sha256(resolved)}
    for name in ("bison", "flex", "x86_64-w64-mingw32-gcc", "i686-w64-mingw32-gcc"):
        found = shutil.which(name, path=f"/opt/homebrew/opt/bison/bin:{os.environ['PATH']}")
        if not found:
            raise ValueError(f"Required build tool missing: {name}")
        resolved = Path(found).resolve()
        tools[name] = {"path": str(resolved), "sha256": sha256(resolved),
                       "version": output([str(resolved), "--version"]).splitlines()[0]}
    return {"tools": tools,
            "clang_version": output(["/usr/bin/clang", "--version"]).splitlines()[0],
            "sdk_version": output(["xcrun", "--show-sdk-version"]).strip()}


# --------------------------------------------------------------------- build

def build(args):
    pin = pins(args)
    work = ensure_outside_repo_sources(args.work)
    archive = Path(args.wine_archive).resolve(strict=True)
    if sha256(archive) != pin["wine"]["sha256"]:
        raise ValueError("Wine source archive checksum differs from versions.json")
    freetype = Path(args.freetype).resolve(strict=True)
    tls = Path(args.tls).resolve(strict=True)
    moltenvk = moltenvk_library(Path(args.moltenvk).resolve(strict=True), pin)
    work.mkdir(parents=True, exist_ok=False)
    commit = output(["git", "-C", str(REPO), "rev-parse", "HEAD"]).strip()
    clean = not output(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"]).strip()
    receipt = {"version": pin["version"], "wine": pin["wine"], "patches": [],
               "source_commit": commit, "source_tree_clean": clean,
               "toolchain": toolchain(), "steps": [], "status": "incomplete"}

    def save():
        (work / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    with tarfile.open(archive) as stream:
        stream.extractall(work, filter="data")
    source = work / f"wine-{pin['wine']['version']}"
    receipt["pristine_tree_sha256"] = tree_hash(source)
    for series, pinned in [(REPO / pin["patch_series"], pin["patches"])]:
        for name in series.read_text().split():
            patch = series.parent / name
            expected = pinned.get(name)
            if expected is None or sha256(patch) != expected:
                raise ValueError(f"Patch {name} is not pinned in versions.json")
            run(["/usr/bin/patch", "-p1", "--batch", "--forward", "--no-backup-if-mismatch",
                 "-i", str(patch)], cwd=source)
            receipt["patches"].append({"name": name, "sha256": expected})
    leftovers = [p for p in source.rglob("*") if p.suffix in (".rej", ".orig")]
    if leftovers:
        raise ValueError(f"Patch left rejects or backups: {leftovers[:5]}")
    receipt["patched_tree_sha256"] = tree_hash(source)
    save()

    directory = work / "build"
    directory.mkdir()
    prefix_map = f"-ffile-prefix-map={work}/=calimocho-build/"
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("WINE", "CX_", "DYLD_", "MVK_", "PKG_CONFIG"))
                   and k not in {"CC", "CXX", "CFLAGS", "CPPFLAGS", "CXXFLAGS", "LDFLAGS",
                                 "CPATH", "LIBRARY_PATH", "CONFIG_SITE", "CROSSCFLAGS"}}
    environment.update(
        PATH=f"/opt/homebrew/opt/bison/bin:{environment['PATH']}",
        CC="/usr/bin/clang -arch x86_64", CXX="/usr/bin/clang++ -arch x86_64",
        CFLAGS=f"-O2 {prefix_map}", CROSSCFLAGS=f"-O2 {prefix_map}",
        LC_ALL="C", CONFIG_SITE="/dev/null",
        PKG_CONFIG_LIBDIR=f"{tls / 'lib/pkgconfig'}:{freetype / 'lib/pkgconfig'}",
        CPPFLAGS=f"-I{freetype / 'include/freetype2'}",
        # Link-time search paths only; runtime resolution is @rpath -> @loader_path/.
        LDFLAGS=(f"-L{moltenvk.parent} -L{tls / 'lib'} -L{freetype / 'lib'} "
                 "-Wl,-rpath,@loader_path/"),
        ac_cv_lib_soname_MoltenVK="@rpath/libMoltenVK.dylib",
        ac_cv_lib_soname_gnutls="@rpath/libgnutls.30.dylib",
        ac_cv_lib_soname_freetype="@rpath/libfreetype.6.dylib",
        DYLD_FALLBACK_LIBRARY_PATH=f"{moltenvk.parent}:{tls / 'lib'}:{freetype / 'lib'}:/usr/lib",
    )
    receipt["environment"] = {k: environment[k] for k in (
        "CC", "CXX", "CFLAGS", "CROSSCFLAGS", "CPPFLAGS", "LDFLAGS", "PKG_CONFIG_LIBDIR",
        "ac_cv_lib_soname_MoltenVK", "ac_cv_lib_soname_gnutls", "ac_cv_lib_soname_freetype")}
    receipt["inputs"] = {"freetype_prefix": str(freetype), "tls_prefix": str(tls),
                         "moltenvk_library": str(moltenvk), "moltenvk_sha256": sha256(moltenvk)}
    jobs = str(args.jobs)
    configure = [str(source / "configure"), "--host=x86_64-apple-darwin",
                 "--enable-archs=x86_64,i386", "--disable-tests", "--without-x",
                 "--with-freetype", "--with-coreaudio", "--with-gnutls", "--with-vulkan",
                 f"--prefix={pin['configure_prefix']}"]
    nice = ["/usr/bin/nice", "-n", "10"]
    steps = [("configure", configure, 1800), ("compile", nice + ["/usr/bin/make", f"-j{jobs}"], 4 * 3600)]
    for label, command, timeout in steps:
        started = time.monotonic()
        run(command, cwd=directory, env=environment, log=work / f"{label}.log", timeout=timeout)
        receipt["steps"].append({"step": label, "command": command,
                                 "seconds": round(time.monotonic() - started, 1)})
        save()
        if label == "configure":
            config = (directory / "include/config.h").read_text()
            for name, value in pin["configure_sonames"].items():
                if f'#define {name} "{value}"' not in config.splitlines():
                    raise ValueError(f"configure did not select {name} {value}")

    helper = directory / "loader/libnative-gs-localtime.dylib"
    run(["/usr/bin/clang", "-arch", "x86_64", "-dynamiclib", "-O2", "-Wall", "-Wextra", "-Werror",
         "-Wl,-install_name,@loader_path/libnative-gs-localtime.dylib",
         "-o", str(helper), str(REPO / "tools/native_gs_localtime.c")],
        cwd=directory, env=environment, log=work / "native-gs-helper.log")
    run(["/usr/bin/make", "-W", "loader/main.o", "loader/wine",
         f"LDFLAGS={environment['LDFLAGS']} -Wl,-needed_library,{helper}"],
        cwd=directory, env=environment, log=work / "native-gs-loader-link.log")
    loads = output(["otool", "-l", str(directory / "loader/wine")])
    if not re.search(r"cmd LC_LOAD_DYLIB\s+cmdsize \d+\s+name @loader_path/libnative-gs-localtime\.dylib",
                     loads):
        raise ValueError("Wine loader lacks its native-GS LC_LOAD_DYLIB")

    destdir = work / "destdir"
    run(["/usr/bin/make", "install-lib", f"DESTDIR={destdir}"], cwd=directory,
        env=environment, log=work / "install.log", timeout=3600)
    stage = destdir / pin["configure_prefix"].lstrip("/")
    shutil.copy2(helper, stage / "lib/wine/x86_64-unix/libnative-gs-localtime.dylib")
    receipt["stage"] = str(stage)
    receipt["status"] = "built"
    save()
    print(f"Built Wine {pin['wine']['version']} into {stage}")


def moltenvk_library(directory, pin):
    receipt = json.loads((directory / "receipt.json").read_text())
    mvk = pin["moltenvk"]
    library = Path(receipt["library"])
    if receipt.get("commit") != mvk["commit"] or receipt.get("metal_private_api") is not mvk["metal_private_api"]:
        raise ValueError("MoltenVK receipt does not match the pinned commit/configuration")
    if sha256(library) != mvk["library_sha256"]:
        raise ValueError("MoltenVK library differs from the pinned build")
    return library


# ------------------------------------------------------------------ assemble

def rewrite_dependency(path, local_names):
    """Point a bundled dylib at its siblings via @loader_path and drop absolute rpaths."""
    run(["install_name_tool", "-id", f"@rpath/{path.name}", str(path)])
    for line in output(["otool", "-L", str(path)]).splitlines()[1:]:
        dependency = line.strip().split(" (")[0]
        base = Path(dependency).name
        if dependency.startswith("/") and base in local_names:
            run(["install_name_tool", "-change", dependency, f"@loader_path/{base}", str(path)])
    for match in re.finditer(r"cmd LC_RPATH\s+cmdsize \d+\s+path (\S+)", output(["otool", "-l", str(path)])):
        if match.group(1).startswith("/"):
            run(["install_name_tool", "-delete_rpath", match.group(1), str(path)])


def bundled_dependencies(args, pin, moltenvk):
    tls = Path(args.tls).resolve(strict=True) / "lib"
    freetype = Path(args.freetype).resolve(strict=True) / "lib"
    result = {}
    for name in pin["bundled_dylibs"]:
        source = (freetype / name) if name.startswith("libfreetype") else (tls / name)
        if name == "libMoltenVK.dylib":
            source = moltenvk
        result[name] = source.resolve(strict=True)
    return result


def copy_apple(args, pin, root):
    gptk = Path(args.gptk).resolve(strict=True)
    apple = pin["apple_gptk"]
    for relative, expected in apple["files"].items():
        if sha256(gptk / relative) != expected:
            raise ValueError(f"Apple GPTK file differs from the pinned {apple['version']}: {relative}")
    external = gptk / "redist/lib/external"
    shutil.copytree(external, root / "lib/external", symlinks=True)
    for name in apple["pe_modules"]:
        target = root / "lib/wine/x86_64-windows" / name
        if target.exists() or target.is_symlink():
            target.unlink()
        shutil.copy2(gptk / "redist/lib/wine/x86_64-windows" / name, target)
    for name in APPLE_UNIX_LINKS:
        link = root / "lib/wine/x86_64-unix" / f"{name}.so"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to("../../external/libd3dshared.dylib")
    licences = root / "licenses/apple-gptk"
    licences.mkdir(parents=True)
    for name in ("License.rtf", "Acknowledgements.rtf"):
        shutil.copy2(gptk / name, licences / name)
    for path in [root / "lib/external/D3DMetal.framework", root / "lib/external/libd3dshared.dylib"]:
        run(["codesign", "--verify", "--strict", str(path)])


def build_tsshim(pin, root, work, receipt):
    """Build Highball's GPL-3.0 tsshim d3d12.dll in front of Apple's unmodified d3d12.dll."""
    import urllib.request
    shim = pin["tsshim"]
    directory = work / "tsshim"
    directory.mkdir(exist_ok=True)
    for name, item in shim["files"].items():
        target = directory / name
        if not target.exists():
            urllib.request.urlretrieve(item["url"], target)
        if sha256(target) != item["sha256"]:
            raise ValueError(f"tsshim {name} differs from the pinned upstream file")
    # Wine 11 matches builtin modules by their export name, so the shim gets its own export
    # name; Apple's d3d12.dll keeps its bytes and only lives under another file name.
    definition = (directory / "d3d12.def").read_text()
    if not definition.startswith("LIBRARY d3d12.dll\n"):
        raise ValueError("Unexpected tsshim definition header")
    (directory / "d3d12-calimocho.def").write_text(
        definition.replace("LIBRARY d3d12.dll\n", f"LIBRARY {shim['tsshim_export_name']}\n", 1))
    built = directory / "d3d12.dll"
    run(["x86_64-w64-mingw32-gcc", "-shared", "-O2", "-Wall", "-static-libgcc", "-s",
         f"-ffile-prefix-map={directory}/=tsshim/", "-o", str(built),
         str(directory / "d3d12.c"), str(directory / "d3d12-calimocho.def")],
        log=directory / "compile.log")
    run([str(work / "build/tools/winebuild/winebuild"), "--builtin", str(built)])
    # Apple's d3d12.dll stays where it is. The shim is a separate builtin that only takes over
    # when a title profile copies it into the prefix as system32\d3d12.dll (Wine resolves the
    # placeholder by export name) and points HB_D3D12_REAL at Apple's file.
    windows = root / "lib/wine/x86_64-windows"
    shutil.copy2(built, windows / shim["tsshim_export_name"])
    licence = root / "licenses/highball-tsshim"
    licence.mkdir(parents=True)
    for name in ("d3d12.c", "d3d12.def", "LICENSE"):
        shutil.copy2(directory / name, licence / name)
    (licence / "CHANGES.md").write_text(
        f"Built from {shim['repository']} commit {shim['commit']} (GPL-3.0).\n"
        f"Calimocho change: the export name in d3d12.def is {shim['tsshim_export_name']} "
        "instead of d3d12.dll, and the shim is installed under that name, so Wine still "
        "loads Apple's unmodified d3d12.dll by default. A title profile enables the shim by "
        "copying it into the prefix as system32\\d3d12.dll and setting HB_D3D12_REAL to the "
        "Windows path of the engine's lib/wine/x86_64-windows/d3d12.dll.\n")
    receipt["tsshim_sha256"] = sha256(windows / shim["tsshim_export_name"])


def assemble(args):
    pin = pins(args)
    work = Path(args.work).resolve(strict=True)
    receipt = json.loads((work / "build-receipt.json").read_text())
    if receipt.get("status") != "built":
        raise ValueError("Run build successfully first")
    stage = Path(receipt["stage"])
    out = ensure_outside_repo_sources(args.out)
    root = out / pin["engine_id"]
    if root.exists():
        raise ValueError(f"{root} exists; assemble into a fresh directory")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stage, root, symlinks=True)
    shutil.rmtree(root / "share/man", ignore_errors=True)

    moltenvk = moltenvk_library(Path(args.moltenvk).resolve(strict=True), pin)
    unix = root / "lib/wine/x86_64-unix"
    dependencies = bundled_dependencies(args, pin, moltenvk)
    for name, source in dependencies.items():
        shutil.copy2(source, unix / name)
        (unix / name).chmod(0o755)
    for name in dependencies:
        rewrite_dependency(unix / name, set(dependencies))
    copy_apple(args, pin, root)
    if "tsshim" in pin:
        build_tsshim(pin, root, work, receipt)
    copy_licences(args, pin, root, moltenvk)
    for document in ("NOTICE", "TRADEMARKS.md", "LICENSE", "COPYING.LIB"):
        shutil.copy2(REPO / document, root / document)
    (root / "SOURCE.md").write_text(source_document(pin))
    strip_debug_symbols(root)
    scan_for_build_paths(root, [str(work), str(REPO), str(Path(args.freetype).resolve()),
                                str(Path(args.tls).resolve())])
    leaks = []
    for path in macho_files(root):
        if (root / "lib/external") in path.parents:
            continue
        # Drop otool's first line, which echoes the file's own path.
        text = "".join(output(["otool", flag, str(path)]).split("\n", 1)[1] for flag in ("-L", "-l"))
        leaks += [f"{path.relative_to(root)}: {marker}" for marker in FORBIDDEN_LINKAGE if marker in text]
    if leaks:
        raise ValueError("Absolute build paths remain in load commands:\n" + "\n".join(leaks))
    write_engine_manifest(pin, root, receipt)
    print(f"Assembled {root}")


def strip_debug_symbols(root):
    """Drop debug symbols (stabs/DWARF) from our Mach-O files; the exported ABI must not change."""
    apple = root / "lib/external"
    for path in macho_files(root):
        if apple in path.parents:
            continue
        before = output(["nm", "-gU", str(path)])
        run(["strip", "-S", str(path)])
        if output(["nm", "-gU", str(path)]) != before:
            raise ValueError(f"strip -S changed the exported symbols of {path}")


def scan_for_build_paths(root, roots):
    """Fail if any shipped file outside Apple's untouched files names a build or user path."""
    markers = [b"/Users/", b"/opt/homebrew/", b"/private/var/folders/", b"/var/folders/"]
    markers += [r.encode() for r in roots]
    hits = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or (root / "lib/external") in path.parents:
            continue
        data = path.read_bytes()
        hits += [f"{path.relative_to(root)}: {m.decode()}" for m in markers if m in data]
    if hits:
        raise ValueError("Build or user paths found in shipped files:\n" + "\n".join(hits[:40]))


def copy_licences(args, pin, root, moltenvk):
    licences = root / "licenses"
    work = Path(args.work).resolve()
    wine = work / f"wine-{pin['wine']['version']}"
    (licences / "wine").mkdir(parents=True, exist_ok=True)
    for name in ("COPYING.LIB", "LICENSE", "AUTHORS"):
        shutil.copy2(wine / name, licences / "wine" / name)
    # Libraries Wine vendors under libs/ and compiles into the shipped modules keep their own terms.
    for library in sorted((wine / "libs").iterdir()):
        texts = [f for f in sorted(library.glob("*")) if f.is_file()
                 and re.match(r"(LICEN[CS]E|COPYING|COPYRIGHT)", f.name, re.I)]
        if texts:
            destination = licences / "wine/libs" / library.name
            destination.mkdir(parents=True, exist_ok=True)
            for text in texts:
                shutil.copy2(text, destination / text.name)
    archives = Path(args.dependency_archives).resolve(strict=True)
    for item in pin["dependency_sources"]:
        archive = archives / Path(item["url"]).name
        if sha256(archive) != item["sha256"]:
            raise ValueError(f"Dependency source archive differs from pin: {archive.name}")
        destination = licences / item["name"]
        destination.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as stream:
            for member in item["licence_members"]:
                data = stream.extractfile(member)
                if data is None:
                    raise ValueError(f"{archive.name} lacks {member}")
                (destination / Path(member).name).write_bytes(data.read())
    # .../source/Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib
    mvk_source = moltenvk.parents[6]
    destination = licences / "moltenvk"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mvk_source / "LICENSE", destination / "LICENSE")
    externals = sorted((mvk_source / "External").glob("*"))
    externals.append(mvk_source / "External/SPIRV-Tools/external/spirv-headers")
    for external in externals:
        name = "SPIRV-Headers" if external.name == "spirv-headers" else external.name
        for candidate in ("LICENSE", "LICENSE.txt", "LICENSE.md"):
            if (external / candidate).is_file():
                shutil.copy2(external / candidate, destination / f"{name}-{candidate}")
                break
        if (external / "LICENSES").is_dir():
            shutil.copytree(external / "LICENSES", destination / f"{name}-LICENSES", dirs_exist_ok=True)
    (destination / "NOTICE-STATUS.txt").write_text(
        "MoltenVK v1.4.2 and the components above ship no Apache-2.0 NOTICE file; "
        "their LICENSE texts are reproduced here.\n")
    # xxHash is compiled into Apple's D3DMetal; Apple ships its licence inside the framework.
    xxhash = root / "lib/external/D3DMetal.framework/Versions/A/Resources/LICENSE"
    if xxhash.is_file():
        (licences / "xxhash").mkdir(exist_ok=True)
        shutil.copy2(xxhash, licences / "xxhash/LICENSE")
    (licences / "freetype/ELECTED.txt").write_text(
        "Calimocho distributes FreeType under the FreeType License (FTL.TXT), one of the two "
        "licences FreeType offers. Portions of this software are copyright \u00a9 1996-2024 The "
        "FreeType Project (www.freetype.org). All rights reserved.\n".replace(
            "1996-2024", pin["freetype_credit_years"]))


def source_document(pin):
    lines = [
        f"# Calimocho {pin['version']}: corresponding source",
        "",
        "This engine contains Wine and libraries licensed under the GNU LGPL.",
        "You can rebuild it from these exact inputs:",
        "",
        f"- Wine {pin['wine']['version']}: {pin['wine']['url']}",
        f"  (sha256 {pin['wine']['sha256']}, tag {pin['wine']['tag']}, commit {pin['wine']['commit']})",
        f"- Calimocho patches and build scripts: {pin['source_repository']}",
        f"  (tag {pin['source_tag']}, files patches/wine-11.20/ and tools/release_engine.py)",
        "- CodeWeavers' LGPL source the D3DMetal integration patch is derived from:",
        f"  {pin['cw_donor']['url']} (sha256 {pin['cw_donor']['sha256']})",
    ]
    for item in pin["dependency_sources"]:
        lines.append(f"- {item['name']} {item['version']}: {item['url']} (sha256 {item['sha256']}, {item['license']})")
    lines += [
        "",
        "The release ships next to a corresponding-source tarball",
        f"(`{pin['engine_id']}-source.tar`) with the Wine tarball, the patches,",
        "the build scripts and the LGPL dependency tarballs.",
        "",
        "Written offer: for at least three years after this release, anyone",
        "can ask for the complete corresponding source of the LGPL components",
        f"by opening an issue at {pin['source_repository']}/issues. We will",
        "provide it at no charge beyond the cost of physically performing the",
        "transfer.",
        "",
        "Apple's D3DMetal.framework, libd3dshared.dylib and the Direct3D PE",
        "modules under lib/wine/x86_64-windows that come from the Game Porting",
        "Toolkit are NOT covered by the LGPL. They are Apple software under",
        "licenses/apple-gptk/License.rtf (non-commercial distribution only).",
        "",
    ]
    return "\n".join(lines)


def write_engine_manifest(pin, root, receipt):
    apple = pin["apple_gptk"]
    manifest = {
        "schema": "calimocho-engine/1",
        "engine_id": pin["engine_id"],
        "version": pin["version"],
        "source_commit": receipt.get("source_commit"),
        "source_tree_clean": receipt.get("source_tree_clean"),
        "provider": {"id": "calimocho", "contract_version": 1},
        "architecture": "x86_64 (Apple Silicon via Rosetta 2)",
        "components": {
            "wine": {"version": pin["wine"]["version"], "source_sha256": pin["wine"]["sha256"],
                     "patches": [p["name"] for p in receipt["patches"]]},
            "apple_d3dmetal": {"version": apple["version"], "bundle_id": apple["bundle_id"],
                               "source_version": apple["source_version"],
                               "binary_sha256": apple["files"][apple["binary"]]},
            "freetype": {"version": next(d["version"] for d in pin["dependency_sources"] if d["name"] == "freetype")},
            "gnutls": {"version": next(d["version"] for d in pin["dependency_sources"] if d["name"] == "gnutls")},
            "moltenvk": {"tag": pin["moltenvk"]["tag"], "commit": pin["moltenvk"]["commit"],
                         "metal_private_api": pin["moltenvk"]["metal_private_api"]},
        },
        "paths": {"wine": "bin/wine", "wineserver": "bin/wineserver"},
        "opt_ins": {name: {k: v for k, v in item.items() if not k.startswith("_")}
                    for name, item in pin.get("opt_ins", {}).items()},
        "environment": pin["environment"],
        "signing": {"team_id": pin["signing"]["team_id"],
                    "authority": pin["signing"]["authority"]},
        "install_location": pin["install_location"],
        "notes": "Paths are relative to this file. ${ENGINE_ROOT} in environment values is the "
                 "directory holding this file. SHA-256 pins for the signed bin/wine and "
                 "bin/wineserver are in MANIFEST.sha256 and the release notes.",
    }
    (root / "calimocho-engine.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # One-line version marker read by generic folder-engine importers.
    (root / "VERSION").write_text(f"{pin['version']}\n")


# ---------------------------------------------------------------------- sign

def sign(args):
    pin = pins(args)
    root = Path(args.root).resolve(strict=True)
    identity = pin["signing"]["identity_sha1"]
    entitlements = pin["signing"]["entitlements"]
    apple = root / "lib/external"
    ours = [p for p in macho_files(root) if apple not in p.parents]
    libraries = [p for p in ours if not is_executable_macho(p)]
    executables = [p for p in ours if is_executable_macho(p)]
    base = ["codesign", "--force", "--sign", identity, "--options", "runtime", "--timestamp"]
    # Inside-out: libraries and plug-ins before the executables that load them.
    for start in range(0, len(libraries), 40):
        run(base + [str(p) for p in libraries[start:start + 40]])
    for path in executables:
        relative = path.relative_to(root).as_posix()
        if relative.startswith("_") or relative not in entitlements:
            raise ValueError(f"No entitlement decision recorded for executable {relative}")
        extra = ["--entitlements", str(REPO / entitlements[relative])] if entitlements[relative] else []
        run(base + extra + [str(path)])
    report = verify_signatures(root, pin)
    (root.parent / f"{root.name}.signing.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Signed {len(libraries)} libraries and {len(executables)} executables")


def verify_signatures(root, pin):
    team = pin["signing"]["team_id"]
    authority = pin["signing"]["authority"]
    report = {"ours": [], "apple": []}
    for path in macho_files(root):
        relative = path.relative_to(root).as_posix()
        subprocess.run(["codesign", "--verify", "--strict", "--verbose=2", str(path)],
                       check=True, capture_output=True, text=True)
        details = subprocess.run(["codesign", "-dvvv", str(path)], capture_output=True, text=True).stderr
        if relative.startswith("lib/external/"):
            if "Authority=Software Signing" not in details:
                raise ValueError(f"Apple component lost Apple's signature: {relative}")
            report["apple"].append(relative)
            continue
        problems = [text for text, ok in (
            ("authority", f"Authority={authority}" in details),
            ("team", f"TeamIdentifier={team}" in details),
            ("runtime", re.search(r"flags=0x\w+\(.*runtime.*\)", details) is not None),
            ("timestamp", "Timestamp=" in details),
        ) if not ok]
        if problems:
            raise ValueError(f"{relative}: signature lacks {', '.join(problems)}")
        if is_executable_macho(path):
            wanted = pin["signing"]["entitlements"].get(relative)
            have = subprocess.run(["codesign", "-d", "--entitlements", "-", "--xml", str(path)],
                                  capture_output=True).stdout
            keys = sorted(re.findall(rb"<key>([^<]+)</key>", have))
            expected = sorted(re.findall(rb"<key>([^<]+)</key>", (REPO / wanted).read_bytes())) if wanted else []
            if keys != expected:
                raise ValueError(f"{relative}: entitlements {keys} differ from the pinned {expected}")
            report.setdefault("entitlements", {})[relative] = [k.decode() for k in keys]
        report["ours"].append(relative)
    for framework in (root / "lib/external").glob("*.framework"):
        subprocess.run(["codesign", "--verify", "--strict", str(framework)], check=True)
        report["apple"].append(framework.relative_to(root).as_posix())
    return report


# ------------------------------------------------------------------- package

def write_manifest(root):
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            lines.append(f"link {os.readlink(path)}  {path.relative_to(root).as_posix()}")
        elif path.is_file() and path.name != "MANIFEST.sha256":
            lines.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")


def package(args):
    pin = pins(args)
    root = Path(args.root).resolve(strict=True)
    verify_signatures(root, pin)
    write_manifest(root)
    out = root.parent
    archive = out / f"{pin['engine_id']}-macos.zip"
    if archive.exists():
        raise ValueError(f"{archive} exists")
    run(["ditto", "-c", "-k", "--norsrc", "--noextattr", "--noacl", "--keepParent",
         str(root), str(archive)])
    (out / f"{archive.name}.sha256").write_text(f"{sha256(archive)}  {archive.name}\n")
    source = out / f"{pin['engine_id']}-source.tar"
    with tarfile.open(source, "w") as stream:
        prefix = f"{pin['engine_id']}-source"
        stream.add(args.wine_archive, f"{prefix}/{Path(args.wine_archive).name}")
        for relative in pin["source_bundle_files"]:
            stream.add(REPO / relative, f"{prefix}/{relative}")
        shim = root / "licenses/highball-tsshim"
        if shim.is_dir():
            for path in sorted(shim.iterdir()):
                stream.add(path, f"{prefix}/highball-tsshim/{path.name}")
        for item in pin["dependency_sources"]:
            name = Path(item["url"]).name
            path = Path(args.dependency_archives).resolve(strict=True) / name
            if sha256(path) != item["sha256"]:
                raise ValueError(f"Dependency source archive differs from pin: {name}")
            stream.add(path, f"{prefix}/dependencies/{name}")
    (out / f"{source.name}.sha256").write_text(f"{sha256(source)}  {source.name}\n")
    print(f"{archive}\n{sha256(archive)}\n{source}\n{sha256(source)}")


def verify(args):
    pin = pins(args)
    archive = Path(args.archive).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=args.scratch) as scratch:
        run(["ditto", "-x", "-k", str(archive), scratch])
        root = Path(scratch) / pin["engine_id"]
        report = verify_signatures(root, pin)
        for line in (root / "MANIFEST.sha256").read_text().splitlines():
            digest, relative = line.split("  ", 1)
            if digest.startswith("link "):
                if os.readlink(root / relative) != digest[5:]:
                    raise ValueError(f"Symlink differs: {relative}")
            elif sha256(root / relative) != digest:
                raise ValueError(f"Manifest mismatch: {relative}")
        assessments = {}
        for relative in ("bin/wine", "bin/wineserver", "lib/wine/x86_64-unix/wine"):
            result = subprocess.run(["spctl", "--assess", "--type", "execute", "-vvv",
                                     str(root / relative)], capture_output=True, text=True)
            assessments[relative] = {"exit": result.returncode,
                                     "output": result.stderr.replace(scratch, "<root>").strip()}
        report.update(archive=str(archive), archive_sha256=sha256(archive),
                      spctl=assessments, manifest="ok",
                      wine_sha256=sha256(root / "bin/wine"),
                      wineserver_sha256=sha256(root / "bin/wineserver"))
    print(json.dumps(report, indent=2))


def registry(args):
    """Render the current Ode registry format for one installed engine."""
    pin = pins(args)
    root = Path(args.root).resolve(strict=True)
    manifest = json.loads((root / "calimocho-engine.json").read_text())

    def expand(value):
        return (value.replace("${ENGINE_ROOT_WINDOWS}", str(root).replace("/", "\\"))
                .replace("${ENGINE_ROOT}", str(root)))

    engine = {
        "name": manifest["engine_id"],
        "kind": "free",
        "version": f"Calimocho {manifest['version']} (Wine {pin['wine']['version']}, "
                   f"D3DMetal {pin['apple_gptk']['version']}, MoltenVK {pin['moltenvk']['tag']})",
        "install_path": str(root),
        "wine": str(root / "bin/wine"),
        "wineserver": str(root / "bin/wineserver"),
        "sha256": sha256(root / "bin/wine"),
        "wineserver_sha256": sha256(root / "bin/wineserver"),
        "environment": {key: expand(value) for key, value in manifest["environment"].items()},
        # A per-title opt-in (for example the FH6 profile) only for test registries.
        **({"name": f"{manifest['engine_id']}-{args.opt_in}"} if args.opt_in else {}),
        "provider": manifest["provider"],
        "renderer": f"apple-{pin['apple_gptk']['version']}",
        "source_url": pin["source_repository"],
        "smoke_test": {"status": args.smoke_status, "evidence": args.smoke_evidence or ""},
        "local_only": False,
        "license_note": "Wine and bundled libraries: LGPL (see SOURCE.md). Apple GPTK "
                        "components: Apple SLA, non-commercial distribution only.",
    }
    if args.opt_in:
        opt_in = manifest["opt_ins"][args.opt_in]
        engine["environment"].update({key: expand(value) for key, value in opt_in["environment"].items()})
        engine.pop("provider")
    document = {"schema_version": 1, "host_architecture": "arm64", "blocked": [], "engines": [engine]}
    Path(args.output).write_text(json.dumps(document, indent=2) + "\n")
    print(f"{args.output}\n{sha256(Path(args.output))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    common_inputs = argparse.ArgumentParser(add_help=False)
    common_inputs.add_argument("--freetype", required=True, help="source-built FreeType prefix")
    common_inputs.add_argument("--tls", required=True, help="source-built GnuTLS stack prefix")
    common_inputs.add_argument("--moltenvk", required=True, help="tools/build_moltenvk.py output directory")
    p = commands.add_parser("build", parents=[common_inputs])
    p.add_argument("--work", required=True)
    p.add_argument("--wine-archive", required=True)
    p.add_argument("--jobs", type=int, default=4)
    p.set_defaults(func=build)
    p = commands.add_parser("assemble", parents=[common_inputs])
    p.add_argument("--work", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--gptk", required=True,
                   help="Apple 'Evaluation environment for Windows games' folder (your own copy)")
    p.add_argument("--dependency-archives", required=True,
                   help="directory with the pinned dependency source tarballs (licence texts)")
    p.set_defaults(func=assemble)
    p = commands.add_parser("sign")
    p.add_argument("--root", required=True)
    p.set_defaults(func=sign)
    p = commands.add_parser("package")
    p.add_argument("--root", required=True)
    p.add_argument("--wine-archive", required=True)
    p.add_argument("--dependency-archives", required=True)
    p.set_defaults(func=package)
    p = commands.add_parser("verify")
    p.add_argument("--archive", required=True)
    p.add_argument("--scratch", required=True)
    p.set_defaults(func=verify)
    p = commands.add_parser("registry")
    p.add_argument("--root", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--smoke-status", choices=("pass", "fail", "not-run"), required=True)
    p.add_argument("--smoke-evidence")
    p.add_argument("--opt-in", help="add a title opt-in environment (test registry, no provider)")
    p.set_defaults(func=registry)
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, RuntimeError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"calimocho: ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
