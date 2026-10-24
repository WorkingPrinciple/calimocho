# ADR-0021: Local runtime recipes without reviving the engine

## Status

Accepted, 2026-10-24. The archive-only/no-engine scope is superseded by
[ADR-0022](0022-reactivate-isolated-source-builds.md). The non-executing
registry exporter remains a separate local reference tool; its historical
Steam evidence does not establish Xbox compatibility.

## Date

2026-10-24.

## Context

The engine-to-recipe archive decision of 2026-06-01 (formerly ADR-0020)
retired Calimocho's custom Wine engine and global Subnautica 2 shim defaults.
The owner now requests a narrow local adapter for an existing Ode/Exodus
runtime selection. This does not require rebuilding that engine, adding a
game profile, or copying another project's binaries. Keeping the existing
engine registry record intact follows the upstream-first rule.

This source-only slice belongs to REQ-33/43, owner S1 Engines, in the
canonical `dragos-core projects/ode-to-x/SPEC.md`, under COR-29 and the
COR-32 access/resume correction. That file remains the program requirements
authority. REQ-53 (distribution rights) remains Program-owned.
REQ-38 still forbids a Subnautica 2 launch or game/prefix mutation.

The following historical evidence explains why the engine stays retired.

On 2026-06-01 the maintainer verified end-to-end that **Subnautica 2
launches and plays on Apple Silicon, on a fully FOSS-with-Apple-D3DMetal
stack, without paying for CrossOver**. The proven path is:

1. [Porting Kit](https://www.portingkit.com/) (free)
2. Its "Steambuild 32/64bit Metal" port (engine label:
   `WS12WineSikarugir10.0_2_D3DMetal-v2.1` — Wineskin 12 + Wine 10
   Sikarugir + Apple D3DMetal v2.1)
3. Winetricks `mf` (Media Foundation)
4. [CodeWeavers' published lifepod-crash fix](https://www.codeweavers.com/compatibility/crossover/tips/Subnautica_2/lifepod-crash-fix)
   (replace `LifepodVideoLowest.mp4` with a copy of `LifepodVideoLow.mp4`)

That is the project's north star (see AGENTS.md rule #5 and
docs/why-this-exists.md) reached, **by a different path than calimocho
was building**.

During the same session the maintainer also identified **Sikarugir**
(https://github.com/Sikarugir-App/Sikarugir), the active successor to
Whisky, maintained by gcenx + vitor251093, which already does what
calimocho was attempting: a Mac-native wrapper around Wine with a
D3DMetal toggle, with the same non-commercial posture and license
respect this project requires. Per AGENTS.md rule #3 ("If [a sister
project] resumes active development, we point users there and reposition
(or archive)"), and per [ADR-0017](0017-follow-when-foss-exists-lead-when-only-paid-exists.md)
("follow when a FOSS path exists"), continuing to build calimocho's own
Wine engine duplicates Sikarugir's work and is no longer justifiable.

Evidence chain that brought us here (verified, in this session):

- Apple D3DMetal `d3d12.dll` is the same proprietary Apple binary
  shipped both in our `out/engine/lib/external/D3DMetal.framework` and
  in CrossOver 26.1.0's `lib64/apple_gptk/wine/x86_64-windows/d3d12.dll`
  — source markers identical (`D3DMetalDLLsBase-17.12/D3D4Mac/d3d12/d3d12.c`).
- CrossOver 26.1.0 is also Wine 11.0 base (`wine-11.0-8720-g4351038808c`),
  matching calimocho's base. Wine version is not the gap.
- PK's "Steambuild 32/64bit Direct3D" variant uses vkd3d-proton +
  MoltenVK (no Apple D3DMetal), so it fails Subnautica 2's D3D12 init —
  same FOSS gap documented in earlier sessions' research.
- PK's "Steambuild 32/64bit Metal" variant *does* bundle Apple D3DMetal
  v2.1 and successfully launches Subnautica 2 once Media Foundation is
  installed and CodeWeavers' lifepod fix is applied.

What calimocho was missing that PK Metal has:
- Years of gcenx-curated DllOverrides (`*colorcnv`, `*atl*`, `*mf*`,
  `*EACrashReporter.exe=""`, etc.) tuned for Steam + Unreal Engine on
  macOS
- Wineskin's launch wrapper (DYLD env, framework search paths,
  MoltenVK ICD configuration)
- A bundled `winemac.drv` tuned by gcenx for the Sikarugir engine

Closing those gaps in calimocho would mean re-deriving years of
gcenx + vitor251093 work, which AGENTS.md rule #4 (visibly worse on
purpose) and ADR-0017 (follow, don't lead, when FOSS exists) both
forbid.

## Decision

1. **Calimocho stops shipping a Wine engine.** No more `scripts/build-wine.sh`
   runs. No more `out/engine/`. No more `Calimocho.app` Swift wrapper.
2. **The README becomes a recipe**: how to play Subnautica 2 on Apple
   Silicon, for free, using Porting Kit's Steambuild Metal port + the
   two-step fix verified on 2026-06-01.
3. **The engine remains archived.** The 2026-06-01 public archive decision
   is not permission to publish, merge, release, or run CI for this local
   source slice. Only the owner-directed reference adapter below is added.
4. **All credit and donate links go upstream** to:
   - https://www.portingkit.com/ (Porting Kit)
   - https://github.com/Sikarugir-App/Sikarugir (Sikarugir)
   - https://github.com/Gcenx/macOS_Wine_builds (gcenx)
   - https://www.codeweavers.com/crossover (CodeWeavers — also the
     paid option calimocho was trying to be a stopgap for)
   - https://developer.apple.com/games/game-porting-toolkit/ (Apple GPTK)
   - https://www.winehq.org/ (the Wine project itself)
5. **Superseded ADRs are deleted** per AGENTS.md's no-Superseded-stubs
   rule: 0013, 0014, 0015, 0016, 0018, 0019. Their context lives in
   git history; this ADR is the single living record of why the engine
   work stopped.
6. **A recipe contribution** has been sent to PaulTheTall (Porting Kit
   maintainer) suggesting Subnautica 2 be added to the PK database
   with the verified recipe.
7. **Allow a local, non-executing registry recipe exporter.**
   `tools/runtime_recipe.py` selects exactly one existing free Wine record
   by explicit registry path and name. It preserves the complete selected
   record, including environment, dependencies, renderer assets, overlays,
   registry imports, local-only terms metadata, and historical receipts.
   It never invokes `bin/calimocho-wine`, adds its defaults, installs a
   runtime, modifies trust/signing, or manages a prefix. The existing
   Ode/Exodus adapter remains the only execution and prefix-ownership path.
   Exported JSON contains references, not payloads or redistribution grants.
   Tests and export checks do not qualify graphics or gameplay.

## Consequences

### Positive

- The maintainer's actual goal (playing SN2 on Mac, for free, without
  paying CodeWeavers) is met, **today**, by a documented path anyone
  can follow.
- Upstream projects (PK, Sikarugir, gcenx, vitor251093) get credit
  and donations directed at them rather than at calimocho.
- Sikarugir + PK still do the engine work. Local adapter maintenance is
  limited to a small registry reference exporter and deterministic tests.
- Per AGENTS.md rule #4 (anti-undercut), we stop competing for the
  same niche CodeWeavers serves, and stop competing for the same
  niche Sikarugir + PK serve. The project becomes purely additive
  documentation.
- The Subnautica 2 recipe (winetricks `mf` + the lifepod mp4 swap)
  is documented publicly, helping anyone Googling the same crash.

### Negative

- People who Google calimocho will see an archived repo. The README's
  first action is "go to Porting Kit". Some users may feel the project
  didn't deliver what it promised.
- The Swift app shell, the Wine build scripts, the D3DMetal shim
  patches, and the CI work are all retired. That's ~3 months of
  engineering effort that does not ship as a binary.
- A local export can detect a changed pinned file, but is not a runtime
  admission receipt. Directory dependency contents are not fully audited.
  Ode must still enforce full-record prefix ownership and revalidate the
  selected route when launching. Engine switching and save reload remain
  unverified; REQ-33/43 are not accepted by this source slice.

### Neutral

- The historical ADRs and the build/work log remain in git history
  as the record of what was tried and what was learned. This is
  valuable to anyone considering a similar project.
- Sikarugir + PK + gcenx + CodeWeavers continue to exist, are
  actively maintained, and remain the correct answer for someone in
  the same situation as the maintainer.

## Related

- [ADR-0006](0006-sn2-stopgap-scope.md) — calimocho was always a
  stopgap; the trigger condition for archiving changed from "UWE
  ships native SN2" to "a sister project ships an equivalent path".
- [ADR-0008](0008-no-whisky-dependency.md) — Whisky was archived in
  May 2025; Sikarugir is its successor, and is alive.
- [ADR-0017](0017-follow-when-foss-exists-lead-when-only-paid-exists.md)
  — the rule that lets us archive cleanly.
- `docs/handover-2026-06-01-end-of-day.md` — full evidence record of
  the session that produced this decision.
