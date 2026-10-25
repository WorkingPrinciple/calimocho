# ADR-0079: Forza Horizon 6 opt-ins in the general engine

Status: Accepted (owner decision, REQ-115)
Date: 2026-10-26

## Context

Engine release 11.20-4.0b3-01
([ADR-0078](0078-developer-id-signed-engine-release.md)) left out
everything Forza Horizon 6 needed beyond generic Wine fixes. The owner
still wants to "ship Forza as it is now". On 2026-10-25 he decided to
add the Forza fixes "as Forza-only opt-ins, but only after checking the
shim's licence". Every other game must keep its -01 behaviour.

The Forza research found these needs:

- two CodeWeavers Rosetta hacks (re-toggling W^X and X faults, and
  reading the live MXCSR);
- the Highball fiber slot, NX and threadpool fixes;
- the winemac icon-reply copy;
- an NVIDIA GPU identity for D3DMetal;
- Highball's `tsshim`, a `d3d12.dll` that sits in front of Apple's and
  fills D3D12 gaps (timestamp queries, the shader-model fallback, MSAA
  depth resolve and append-aligned input layouts).

The tsshim licence was checked against the upstream text: it is GPL-3.0
(<https://github.com/gauthierpiarrette/highball>, commit
`1512223fff145eae3b4c9fb588edf86758bc756b`, `LICENSE`).

Highball itself lays Apple's `d3d12.dll` next to the shim as
`apd12.dll` with two bytes of its export name patched. That modifies
Apple's binary, which the GPTK licence (section 2D) forbids, and AGENTS
rule 1 says D3DMetal ships unmodified.

## Decision

1. One engine, `11.20-4.0b3-02`. The Forza patches (0006-0013 in
   `patches/wine-11.20/`) are compiled in. Each one is off unless its
   environment flag is `1`:

   | Flag | Fix |
   |---|---|
   | `CALIMOCHO_FIX_ROSETTA_WX` | Retoggle execute on Rosetta W^X and X faults |
   | `CALIMOCHO_FIX_ROSETTA_MXCSR` | Use the live MXCSR in Rosetta signal contexts |
   | `CALIMOCHO_FIX_FIBER_GS` | Hand %gs:0x20 to fiber threads |
   | `CALIMOCHO_FIX_NX_ALWAYS` | Keep NX on |
   | `CALIMOCHO_FIX_THREADPOOL_IO` | Release a threadpool I/O object exactly once |
   | `CALIMOCHO_FIX_ICON_REPLY` | Copy the app-icon callback reply |

   The GPU identity (`D3DM_VENDOR_ID`/`D3DM_DEVICE_ID`) and
   `XODUS_MUTE_AUDIO` were already inert unless set.
2. The tsshim is built from the pinned upstream source. The only change
   is the export name in `d3d12.def`. It is installed as
   `lib/wine/x86_64-windows/d3d12_tsshim.dll`. Apple's `d3d12.dll`
   stays unmodified and remains the default for every title. Wine 11
   resolves the prefix placeholder by its export name, so the shim
   takes over only when a title profile:
   - copies it into the prefix as `system32\d3d12.dll`, and
   - points `HB_D3D12_REAL` at Apple's file.

   The shim's source and GPL-3.0 text ship in `licenses/highball-tsshim/`
   and in the corresponding-source tarball.
3. The FH6 flags, environment and profile steps are pinned in
   `versions.json` under `release_engine.opt_ins.fh6` and copied into
   `calimocho-engine.json`. Xode's FH6 profile applies them; no other
   profile does.

## Consequences

- Every other title runs the -02 binaries with the flags unset. Each
  release must check this with the same smoke probes and a sample of
  games used for -01.
- Forza still needs the Xbox GDK runtime fixes (PlayFab/XSTS tokens and
  PFX local saves). They live in the xgameruntime lane, not in the
  engine.
- The engine now carries one GPL-3.0 component. Its source must travel
  with every release.
- The CodeWeavers hacks are copied from LGPL source and keep their
  headers.
