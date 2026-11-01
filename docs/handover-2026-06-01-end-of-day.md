# calimocho — Session handover 2026-06-01

## TL;DR for next session

After 6 sessions, today's research and tests produced a sharp
re-anchoring of what works:

| Stack | Steam UI | SN2 launch | Notes |
| --- | --- | --- | --- |
| CrossOver 26 (proprietary `d3d12.so`) | ✅ | ✅ | The maintainer has this working. Trial expires. EULA forbids redistribution. |
| **PK DXVK** variant (vanilla) | ✅ | ❌ | Steam UI works. SN2 D3D12 init fails (vkd3d-proton + MoltenVK FOSS gap). |
| **PK Direct3D** variant (vanilla) | ✅ | ❌ | Steam UI works. SN2 gated by "Microsoft VC++ 2015-2022 Redistributable required". Apple D3DMetal-backed d3d12 path. |
| Our calimocho Wine 11 + own D3DMetal shim | ❌ (black) | n/a | Shim Tier-1 unit test passes; CEF/Steam fails because adapter from wine's `dxgi.dll` is wined3d-backed and D3DMetal can't deref it. |
| Our calimocho + DXVK DLLs from PK | ❌ (still black) | n/a | Wine 11's winemac.drv composition path is the missing piece, not just the DLLs. |

**Key insight from the maintainer (kept losing this; please don't):**
- **PK Direct3D is the strictly-better variant** because it has the
  Apple D3DMetal d3d12 path — the only path with a future for SN2.
- DXVK alone has **no path to SN2** (vkd3d-proton + MoltenVK gap is
  fundamental per the research doc).
- Maintainer's question: can we make **vanilla PK Direct3D** play SN2
  (just by satisfying Steam's vcrun gate), instead of rebuilding our
  own Wine engine that mimics PK?

**Today's last test (failed):** Tried to satisfy PK Direct3D's vcrun
gate by copying CrossOver's vcrun140-family DLLs + 261 lines of
CrossOver registry entries into PK Direct3D's bottle. Result:
**broke PK Direct3D's webhelper** — went into a respawn loop
("Steam Web Helper is not responding" dialog every 10 seconds).
Reverted: DLLs restored, registry sections deleted, SN2 symlink
removed. PK Direct3D should now be back to its working-Steam-UI-but-
SN2-blocked-by-vcrun state.

## Current repo state

- Branch: `phase4-pivot-on-pk` (created today off `phase3-cef-integration`)
- Last commit: `27c3437` — `ADR-0019 (Proposed): pivot calimocho — fork PK instead of own Wine engine`
- Not yet pushed
- Working tree clean
- Earlier branch `phase3-cef-integration` has the research doc and ADRs 0013-0018, pushed at `21149dc`

## Project rule changes locked in this session

- **AGENTS.md rule #4 amended** via ADR-0017: "We follow when a FOSS
  path exists. We lead only when the only alternative is a paid
  product, and only as narrowly as needed to remove that gating."
- ADRs 0013, 0014, 0015, 0016 (the D3DMetal shim direction) are
  **superseded** by today's findings — ADR-0019 proposes deleting
  them per AGENTS "no Superseded stubs" policy when the pivot is
  accepted.
- ADR-0018 (DXVK pivot) is itself superseded by ADR-0019 (PK
  Direct3D pivot — has SN2 future, DXVK does not).

## What's untouched in the bottle / engine

- Our calimocho engine at `out/engine/` is in the state from
  earlier today: Wine 11 + our D3DMetal shim. Untouched after
  cleanup.
- Our calimocho bottle at `~/Library/Application Support/Calimocho/Bottles/STEAM/`
  has Apple's d3d11.dll + dxgi.dll in system32/syswow64 (from
  earlier shim work). Pre-DXVK DLLs already restored from
  `.calimocho-pre-dxvk.bak`.
- PK Direct3D bottle restored to pre-test state:
  - vcrun140 DLLs from CX removed (restored from `.pk-pre-cx-vcrun.bak`)
  - SN2 symlink removed (placeholder restored)
  - 20 vcrun registry sections deleted from `user.reg`
    (backup at `<PK Direct3D prefix>/user.reg.pre-reg-revert.bak`)
- PK DXVK bottle: SN2 symlink already restored earlier. Otherwise
  untouched.
- CrossOver bottle: **never modified by us**.

## Open question that needs the next session

**Why did adding CrossOver's vcrun140 DLLs + 261 reg lines break
PK Direct3D's webhelper?**

Possible explanations (untested):
1. The 261-line .reg import included keys that confused gcenx
   wine-private's installer state machine.
2. The CX DLLs depend on something CX-specific (e.g. a `ucrtbase.dll`
   variant) that PK's vanilla bottle doesn't have, causing crashes
   on load.
3. Too aggressive — we copied the entire vcrun family, including
   `vcruntime140_threads.dll` and `msvcp140_atomic_wait.dll` which
   may have stricter Wine version requirements.

A safer approach next session: don't copy DLLs; **just write the
registry markers Steam's Steamwebhelper actually reads** to satisfy
the vcrun check, and let `winetricks vcrun2022 -q --force` install
the DLLs properly from MS's installer (which we tried first today
but the installer exited with code 5 — possibly because PK's wine
lacks something the installer's manifest extraction needs).

## ⚠️ Don't repeat these mistakes

1. **DXVK pivot kept getting suggested** — but DXVK has no path to
   SN2. Only D3DMetal does. Stay on PK Direct3D.
2. **Tried to modify PK's bottle directly** without understanding
   PK's setup well enough. Result: broke PK's webhelper. Next time:
   test changes incrementally (one DLL at a time, one reg key at a
   time) instead of dumping 20 sections at once.
3. **Conflated "Steam UI loading splash" with "Steam UI works"** —
   the splash always appears; the test is whether you reach login
   form or library. Always check `pgrep` for actual running
   webhelper + AppleScript for actual visible windows.
4. **Never `pkill -f` patterns** that might match native Steam.app.
   Always: `WINEPREFIX="$PK_PREFIX" wineserver -k` or `kill <exact-pid>`.

## What might actually work for the user's goal

**The user has SN2 working in CrossOver today.** That's the
ground-truth. CrossOver expires for them. The realistic options
in priority order:

**A. Reproduce CX's specific recipe step-by-step in PK Direct3D**,
   one piece at a time, instead of dumping all of CX's state. Start
   with: install winetricks vcrun2022 the proper way (PK's
   Wineskin UI has a Winetricks panel — Tools → Winetricks →
   search "vcrun2022" → install). That might not break webhelper
   the way our manual import did. **Cheap test, 10 min.**

**B. If (A) works and vcrun gate clears, apply the SN2 recipe
   (UE4SS xinput proxy, Sentry crashpad disable, Win11 setting,
   AVX advertise) using PK's Wineskin GUI** — these are all things
   Wineskin's Advanced tab exposes. No raw registry hacks.

**C. If SN2 then launches but hits D3DMetal d3d12 issues,
   document them as the next gate**. We have all the env knobs
   from Apple's GPTK Read Me (D3DM_SUPPORT_DXR, D3DM_ENABLE_METALFX,
   etc.) but **set them via PK's Info.plist** not via env override —
   PK loads its env from Info.plist not from shell env.

**D. If (A) fails the same way our manual import did**, the user
   may simply need to **buy CrossOver** (~$74 one-time). That's the
   ADR-0017-honest answer. README documents this; project's
   own purpose is to delay/avoid that.

## What calimocho-the-project ships if (A)/(B)/(C) works

ADR-0019 proposes: **calimocho becomes a thin SwiftUI wrapper
that orchestrates PK Direct3D** instead of shipping its own Wine
engine. The wrapper:
1. Detects/installs PK via `brew install --cask gcenx/wine/game-porting-toolkit`
   (or similar)
2. Programmatically applies the SN2 recipe to PK's bottle
3. Launches Steam through PK
4. Status UI showing what's needed

This drastically reduces our maintenance load (we stop building
Wine entirely) and aligns with ADR-0017 (PK exists, we follow).

## File index

- `docs/research/d3d12-foss-status-2026-06-01.md` — the research doc, source-cited
- `docs/ADR/0017-follow-when-foss-exists-lead-when-only-paid-exists.md` — the rule change
- `docs/ADR/0019-pivot-fork-pk-instead-of-own-engine.md` — the current direction
- `/memories/session/calimocho-d3d12-research-state.md` — session memory with research checklist
- `/memories/repo/calimocho-sn2-recipe.md` — the proven CrossOver recipe for SN2
- This file: `docs/handover-2026-06-01-end-of-day.md`

## Branch to push

`phase4-pivot-on-pk` has 1 unpushed commit (`27c3437` — ADR-0019).
Decide whether to push (probably yes — it's a clean planning ADR)
or rebase off main first to avoid carrying `phase3-cef-integration`'s
later commits that are also valid records of the day.
