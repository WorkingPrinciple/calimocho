# ADR-0010: Host arch is x86_64; run under Rosetta 2

## Status
Accepted

## Date
2026-06-01

## Context

Phase 1 Engine work started with the implicit assumption that we could
build a native-arm64 Wine 11 loader for Apple Silicon. CodeWeavers'
source nominally supports it (`--enable-archs=x86_64,i386,aarch64`),
and `make` runs to completion with three small patches (arm64 metallayer
guard, arm64 d3dmetal stub, wineloader bundle ID rename — see
ADR-0009).

The resulting binary at `out/engine/lib/wine/aarch64-unix/wine` is
**killed by `AppleSystemPolicy`** at every exec on macOS 26.5:

> kernel: (AppleSystemPolicy) ASP: Security policy would not allow
> process: .../lib/wine/aarch64-unix/wine

Investigation ruled out:
- code signature (ad-hoc, signed, unsigned, with/without entitlements,
  with/without `--options runtime`)
- bundle identifier (both CodeWeavers' original and our renamed
  `app.calimocho.wineloader` are killed)
- filesystem path (`out/`, `/tmp/`, identical result)
- quarantine xattrs (stripped, still killed)
- amfid involvement (none — pure ASP)

The kill is silent: no log line beyond the one above, no exit code
detail, no actionable error. Apple has not documented this policy.

Independent survey of what other Wine-on-Mac stacks actually ship:

| Stack | Host arch | Verified by |
| --- | --- | --- |
| Whisky's bundled Wine 11.9-staging (current) | **x86_64 only** | `file ~/Library/.../Whisky/Libraries/Wine/lib/wine/x86_64-unix/wine` |
| Whisky's prior Wine 7.7 (Apr 2023) | **x86_64 only** | `Libraries.bak-wine7/` |
| CrossOver 26 | **x86_64 only**, runs under Rosetta 2 | CodeWeavers release notes |
| Apple GPTK 3.0 (Mar 2026) | **x86_64 only**, runs under Rosetta 2 | GPTK release notes, `lipo -info redist/lib/external/D3DMetal.framework/D3DMetal` (no arm64 slice) |
| gcenx macOS_Wine_builds | x86_64 + experimental aarch64 staging tarballs | upstream README; aarch64 builds have the Steam black-window bug |

**No production Wine-on-Mac stack ships native arm64.** We are not
hitting a calimocho-specific bug or a signing oversight — we are the
first project to try, and Apple's macOS 26 ASP refuses to cooperate.

Independently: Apple's GPTK `D3DMetal.framework` ships **Intel-only**.
The DX12-to-Metal translator we depend on for SN2's UE5 backend
**cannot** run as native arm64 today regardless of what we do. So even
a hypothetical working arm64 Wine would still need Rosetta to load
D3DMetal — which defeats the purpose of native arm64.

## Decision

Build calimocho's Wine engine as **x86_64 only**, with the `i386`
companion arch for 32-bit Windows DLL support. Run the engine under
Rosetta 2 from the user's native arm64 shell — exactly the way every
other working Wine-on-Mac stack does it.

Concrete changes:

1. `configure --enable-archs=x86_64,i386` (drop any `aarch64`).
2. Drop calimocho patches 0001 (arm64 metallayer guard) and 0002
   (arm64 d3dmetal stub). They were only needed when the loader was
   compiled native arm64. Patch 0003 (wineloader bundle ID rename) is
   kept — it is correct independent of host arch.
3. Engine path becomes `out/engine/lib/wine/x86_64-unix/wine`. Update
   `docs/ARCHITECTURE.md` Layer 2 disk layout accordingly.
4. README's system requirements state: Apple Silicon Mac with Rosetta
   2 installed (`softwareupdate --install-rosetta --agree-to-license`
   is part of the first-run wizard's system check in Phase 2).
5. Add Rosetta 2 presence to A1.2's pre-conditions in
   `docs/SPECS.md` (Rosetta must be installed for the engine to run at
   all).
6. Phase 1 acceptance criteria A1.x text doesn't change in meaning —
   "wine" runs and produces correct output — but the underlying binary
   format is x86_64 Mach-O instead of arm64 Mach-O.

## Consequences

### Positive
- The engine actually runs. macOS 26's ASP has no documented or
  observed issue with ad-hoc-signed x86_64 Wine.
- We can use Apple's GPTK `D3DMetal.framework` unchanged (it's
  x86_64-only, see above) for DX12 → Metal translation. This is the
  whole point of bundling GPTK (ADR-0005). Native arm64 would have
  required either a wined3d software fallback (unplayable for SN2) or
  shipping our own DX12 → Metal translator (out of scope forever).
- Drops two of three calimocho source patches (#0001, #0002 deleted).
  Less divergence from upstream. Better fit with AGENTS rule #3
  (respect upstream).
- Matches the actual support matrix of every shipping Wine-on-Mac
  stack. CrossOver users, Whisky users, and calimocho users all run
  the same x86_64 + Rosetta + D3DMetal sandwich. Bug reports route
  the same way.

### Negative
- Wine binaries run under Rosetta 2's x86_64 emulator. Performance
  cost vs native arm64 is the standard Rosetta overhead (~20–30% on
  CPU-bound code, near-zero on GPU-bound code that goes through
  D3DMetal). Subnautica 2 is GPU-bound. Verified by every CrossOver
  user playing UE5 games on Apple Silicon for 3 years.
- Requires Rosetta 2 to be installed. Default on every Apple Silicon
  Mac since macOS 11; user is prompted to install on first launch of
  any x86_64 binary. First-run wizard in Phase 2 will install it
  explicitly if absent.
- Apple has publicly hinted Rosetta 2 will be deprecated "in a future
  macOS release" (WWDC 2025). Whenever that happens, calimocho will
  archive — same trigger as Unknown Worlds shipping native SN2.
  Documented in PHASES.md ∞ Archive entry.

### Neutral
- The build process gets simpler: one host arch, no cross-compile
  bookkeeping for aarch64 vs x86_64 macdrv code paths.
- The hours spent investigating the ASP kill are captured in
  `docs/build-log.md`. Future maintainers will not need to re-discover
  it.

## Related

- Supersedes the implicit "native arm64" reading of
  [ADR-0001](0001-bundle-codeweavers-wine.md). Update ADR-0001's
  Consequences section to point at this ADR.
- Reinforces [ADR-0005](0005-bundle-gptk-d3dmetal.md): GPTK is
  Intel-only, so the engine must be Intel.
- Reinforces [ADR-0007](0007-compile-never-copy.md): we still build
  from source, just for a different target arch.
- Drops calimocho patches `0001-winemac-metallayer-arm64.patch` and
  `0002-d3dmetal-arm64-stub.patch` (never landed in any shipped
  build).
- Keeps calimocho patch `0003-rename-wineloader-id.patch` (ADR-0009).
