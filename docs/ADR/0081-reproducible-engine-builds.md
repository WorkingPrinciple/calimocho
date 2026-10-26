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
- **Policy check.** `tools/release_engine.py assemble` fails if any of
  our PE modules (Apple's five are excluded) carries a non-zero
  `TimeDateStamp`. `build` fails if configure drops the flag.
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
