# ADR-0081: Reproducible engine builds

Status: Accepted (coordinator request after 0.1120.4.4, REQ-115)
Date: 2026-10-26

## Context

Two clean builds of 0.1120.4.3 from the same commit gave byte-identical
Mach-O files, but 403 Windows PE modules differed in 8 bytes each:

- the COFF `TimeDateStamp`, which GNU ld sets to the link time;
- the optional-header `CheckSum`, which GNU ld computes over the image,
  including that timestamp.

The toolchain was only recorded in the build receipt, not pinned, so a
second build on an updated Mac could silently use a different compiler.

Both 0.1120.4.3 builds also reused one set of FreeType and TLS
libraries. Building those twice showed two more differences:

- Each library's install name contained its build directory. Apple ld
  derives the `LC_UUID` from the whole image, so the UUID differed too.
  The release tool rewrites the install name to `@rpath`, but not the
  UUID.
- nettle's objects carry debug information, so ld wrote a debug map
  with absolute object paths and file times, which also changed the
  UUID.

## Decision

- **PE timestamp.** Wine is configured with
  `CROSSLDFLAGS=-Wl,--no-insert-timestamp`, so every PE module Wine
  links has `TimeDateStamp` 0. The Highball tsshim is linked the same
  way, with a relative output name, because GNU ld derives the
  automatic image base from the output path. Wine already writes 0 into
  the PE modules it creates in a prefix (`setupapi/fakedll.c`), and its
  loader only uses the timestamp as a hint before comparing the mapped
  files.
- **PE checksum.** The `CheckSum` stays exactly as GNU ld writes it. We
  do not zero or recompute it. Wine's install step
  (`winebuild --builtin`) marks the DOS stub after linking, so the
  checksum does not match the final file bytes. This is the same in
  every upstream Wine build, and Wine does not check it. With the
  timestamp fixed, the checksum is deterministic.
- **Policy check.** `tools/release_engine.py assemble` fails if any PE
  module linked by GNU ld carries a non-zero `TimeDateStamp`. Wine links
  those with `--build-id`, so they have a `.buildid` section (1519
  modules), and the tsshim is checked by name. About 50 modules have no
  such section: winebuild writes them itself (data-only, type-library
  and forwarder modules) and stores a hash in the stamp, not a time
  (for most of them, the FNV-1 hash of the file name). They are left as
  upstream Wine makes them, and the double build shows they are
  deterministic. Apple's five modules are excluded. `build` fails if
  configure drops the flag.
- **Dependency libraries.** `tools/build_freetype.py` and
  `tools/build_tls.py` configure with the fixed prefix
  `/tmp/calimocho-deps/<name>`. During the build that path is a symlink
  to the real output directory, guarded by a lock and an owner check,
  and removed afterwards. Install names and UUIDs no longer depend on
  the build directory, and configure behaves as before. Its test
  programs still find the libraries, which a nonexistent prefix would
  break: SIP strips `DYLD_*` variables from `/bin/sh`. The TLS
  libraries link with `-Wl,-S`, so ld writes no debug map; the exported
  symbols are unchanged. The build-time `.pc` files are pointed back to
  the real prefix and the `.la` files are removed; neither is shipped.
  The release tool's path scan also rejects `/calimocho-deps/`.
  `release_engine.py build` serves the same paths from configure to
  install, because Wine's `sfnt2fon` build tool loads FreeType. One
  lock covers them, so two builds on one Mac take turns at that stage.
- **Toolchain pin.** `versions.json` `release_engine.toolchain` pins
  the Xcode version and build, the SDK version and build, and the
  version line and SHA-256 of clang, Apple ld, make, bison, flex, both
  mingw-w64 GCC drivers and both mingw-w64 GNU ld binaries. `build` and
  `assemble` refuse to run on any other toolchain. Updating a tool means
  updating the pin, which is a new build number.
- **Gate.** A release is reproducible when two clean builds from the
  same commit, each with its own FreeType and TLS dependency builds,
  assemble into byte-identical unsigned engine trees. Signing adds
  Apple's secure timestamp and is not reproducible by design. The
  comparison is therefore made before signing.

## Consequences

- Anyone with the pinned toolchain can rebuild the engine and compare
  every unsigned file with ours.
- PE modules no longer show when they were linked; `calimocho-engine.json`
  records the source commit instead.
- A Homebrew or Xcode update stops the build until the pin is updated
  on purpose.
- MoltenVK is still a pinned input built earlier by
  `tools/build_moltenvk.py` (SHA-256 in `versions.json`). It is not
  rebuilt for each release.
