# ADR-0080: Minimal entitlements for the engine executables

Status: Accepted (owner hardening request, REQ-115)
Date: 2026-10-26

## Context

Releases 01 and 02 gave the same five hardened-runtime entitlements to
all three engine executables: `allow-jit`,
`allow-unsigned-executable-memory`, `disable-executable-page-protection`,
`disable-library-validation` and `allow-dyld-environment-variables`.
They were copied from the Phase 1 script without being tested one by one.
The owner asked for a stable, hardened engine. Every entitlement weakens
the hardened runtime, so each one needs a reason that a real launch
proves.

All tests used build 02, re-signed with the Developer ID and the hardened
runtime, in a throwaway prefix. The smoke test was: `wineboot --init`,
`cmd /c ver`, D3D11, D3D12 and Vulkan present probes with read-back, a
WinHTTP HTTPS request, and a JIT probe (`VirtualAlloc`
`PAGE_EXECUTE_READWRITE`, write code, run it, then
`VirtualProtect` RW→RX and run again). Brotato and Halls of Torment then
ran through the Xode CLI.

| Configuration (`bin/wine` / loader / `wineserver`) | Result |
|---|---|
| none / unsigned-memory + library validation off / none | smoke, JIT probe: pass |
| none / unsigned-memory only / none | fails at start: `err:virtual:map_image_into_view failed to set 60000020 protection on ntdll.dll .text`, then a stack overflow |
| none / library validation off only / none | smoke, JIT probe, Brotato, Halls of Torment: pass |

The hardened runtime refuses executable mappings of files that are not
validly signed code unless library validation is off. Wine maps Windows
PE files that way. The JIT probe passed without
`allow-unsigned-executable-memory` because the loader runs as x86_64
under Rosetta.

## Decision

- `lib/wine/x86_64-unix/wine` (the real loader, which runs Windows code)
  gets only `com.apple.security.cs.disable-library-validation`
  (`scripts/entitlements/wine-loader.plist`). The same entitlement also
  lets users swap in their own builds of the LGPL libraries, as LGPL-2.1
  section 6 requires.
- `bin/wine` (the launcher) and `bin/wineserver` get no entitlements.
- `allow-jit`, `allow-unsigned-executable-memory`,
  `disable-executable-page-protection` and
  `allow-dyld-environment-variables` are removed. The engine does not
  depend on `DYLD_*` variables; bundled libraries resolve through
  `@rpath`/`@loader_path`.
- The pins live in `versions.json` (`release_engine.signing.entitlements`).
  `tools/release_engine.py` refuses to sign an executable without a
  recorded decision, and the verify step fails if the signed entitlements
  differ from the pins.

## Consequences

- A game that needs more (for example, one that relies on a JIT that
  only works with `allow-unsigned-executable-memory` on some future
  macOS) will fail to launch. Its error is then the evidence for adding
  that one entitlement in a new build.
- `scripts/wine-entitlements.plist` stays for the archived Phase 1
  scripts only. Release builds do not use it.
