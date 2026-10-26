# calimocho

> **Archived 2026-06-01.** This repo is a recipe. Use Porting Kit
> instead. See below.
>
> Subnautica 2 plays on Apple Silicon, for free, on a fully FOSS +
> Apple D3DMetal stack. Calimocho did not build it. Other people did.
> This README points you at their work, with the two small tweaks the
> maintainer needed to make it work on his M1 Max on 2026-06-01.

![Status: archived](https://img.shields.io/badge/Status-archived-lightgrey)
![Use: non-commercial only](https://img.shields.io/badge/Use-non--commercial%20only-orange.svg)
![Platform: macOS arm64](https://img.shields.io/badge/Platform-macOS%20arm64-lightgrey)

---

## Why this repo is archived

Calimocho was going to be a small Mac app that wrapped Wine + Apple's
Game Porting Toolkit to let you play Subnautica 2 on your Mac without
paying for [CrossOver](https://www.codeweavers.com/crossover).

While building it, the maintainer found that this thing already exists,
is actively maintained, is FOSS, has the same non-commercial license
posture, and works:

- **[Sikarugir](https://github.com/Sikarugir-App/Sikarugir)** by
  [gcenx](https://github.com/Gcenx) and
  [vitor251093](https://github.com/vitor251093), the active successor
  to Whisky.
- **[Porting Kit](https://www.portingkit.com/)** by
  [PaulTheTall](https://www.paulthetall.com/), a friendly macOS-native
  installer that ships a Sikarugir-based Wine + Apple D3DMetal port
  called "Steambuild 32/64bit Metal".

So per this project's own rules
([AGENTS.md rule #3](AGENTS.md) and
[ADR-0017](docs/ADR/0017-follow-when-foss-exists-lead-when-only-paid-exists.md)),
calimocho stops shipping a Wine engine and becomes the document below.

If you want the full reasoning, read
[ADR-0020](docs/ADR/0020-pivot-from-engine-to-recipe-archive.md).

## The recipe (verified 2026-06-01, M1 Max, macOS 15.x)

### What you need

- An Apple Silicon Mac (M1 or later), macOS 14 Sonoma or later, 16 GB
  RAM or more
- A Steam account that owns
  [Subnautica 2](https://store.steampowered.com/app/1962700/Subnautica_2/)
- ~50 GB of free disk for the game install
- Patience for the first launch (it takes a minute, this is normal)

### Steps

1. **Install Porting Kit.** Go to https://www.portingkit.com/, download
   the .zip, move the app to `/Applications`. Open it and let it
   finish first-run setup.
2. **Install the Steam port.** In Porting Kit, search the game
   database for "Steambuild 32 64bit Metal" and click Install. Let it
   finish. The engine is labelled `WS12WineSikarugir10.0_2_D3DMetal-v2.1`
   on screen. That is Wineskin 12 + Wine 10 Sikarugir +
   Apple D3DMetal v2.1.
3. **Launch the port. Log into Steam. Install Subnautica 2.** This is
   the same as it would be on Windows. The download is ~15 GB.
4. **Install Media Foundation.** Right-click the Steambuild Metal app
   in `~/Applications` → **Show Package Contents** → open
   `Wineskin.app` → **Advanced** → **Tools** tab → **Winetricks**. In
   the search box, type `mf`, check the `mf` row ("MS Media
   Foundation"), click **Run**. Wait for it to finish (a few minutes).
   Close Winetricks and Wineskin.
5. **Apply CodeWeavers' lifepod-crash fix.** Without this, the game
   freezes when the opening cinematic starts. Open Terminal and run:
   ```sh
   PFX="$HOME/Applications/Steambuild 32 64bit Metal.app/Contents/SharedSupport/prefix"
   MOVIES="$PFX/drive_c/Program Files (x86)/Steam/steamapps/common/Subnautica2/Subnautica2/Content/Movies"
   mv "$MOVIES/LifepodVideoLowest.mp4" "$MOVIES/LifepodVideoLowest.mp4.broken-original.bak"
   cp "$MOVIES/LifepodVideoLow.mp4"     "$MOVIES/LifepodVideoLowest.mp4"
   ```
   This replaces the corrupt "lowest quality" cinematic with a copy of
   the "low quality" one that decodes fine. The fix and its rationale
   are CodeWeavers':
   https://www.codeweavers.com/compatibility/crossover/tips/Subnautica_2/lifepod-crash-fix
6. **Launch Subnautica 2** from inside the Steambuild Metal port's
   Steam. The opening cinematic plays. Welcome aboard, Pioneer.

### What to do if any step breaks

This recipe is not supported. If a step does not work for you:

- For **Porting Kit** problems, ask
  [Paul](https://www.paulthetall.com/contact/) or in the Porting Kit
  forums.
- For **Sikarugir / Wineskin** problems, check the
  [Sikarugir issue tracker](https://github.com/Sikarugir-App/Sikarugir/issues).
- For **Wine engine** problems, the Wine project's
  [Bugzilla](https://bugs.winehq.org/) is the right place (do not file
  Wine bugs against Porting Kit, Sikarugir, or this repo).
- For **Subnautica 2** problems, the developer's
  [support site](https://support.subnautica.com/) covers most launch
  issues. Verifying the game files via Steam fixes more bugs than
  anything else.
- If the recipe stopped working because of a game update, the answer
  is probably to update Porting Kit and reinstall the port. The
  maintainer no longer tracks SN2 patches against the recipe.

### If you can afford it, please buy CrossOver

[CrossOver](https://www.codeweavers.com/crossover) costs $74 one-time.
It is the polished, supported, commercially-licensed version of what
this recipe hacks together. Every CrossOver license you buy funds the
LGPL Wine patches that the entire macOS-Wine ecosystem (including
Sikarugir, Porting Kit, and this recipe) depends on. The maintainer
is using their CrossOver trial while writing this README. The trial
expires. The price is fair. Please buy it if you can.

## Credits

This recipe is 100% other people's work. The maintainer just wrote it
down. In rough order of who matters most for this specific recipe:

- **[Unknown Worlds Entertainment](https://unknownworlds.com/)** for
  Subnautica, Below Zero, and now Subnautica 2. They shipped native
  Mac builds for the first two. They have not yet shipped one for
  SN2. This recipe exists until they do, then it does not matter
  anymore.
- **[CodeWeavers](https://www.codeweavers.com/)** for 30 years of
  funding the Wine project, for the LGPL Wine patches that make
  macOS Wine possible, for publishing the source under
  [crossover/source](https://www.codeweavers.com/crossover/source),
  and for publishing the
  [lifepod-crash fix](https://www.codeweavers.com/compatibility/crossover/tips/Subnautica_2/lifepod-crash-fix)
  that step 5 of this recipe applies. Their statement that 95% of the
  Wine code they write goes back upstream is not marketing, it is
  what makes any of this possible.
- **[The Wine project](https://www.winehq.org/)** for 30 years of
  reverse-engineering the Windows API into a free, open library.
- **[Apple](https://developer.apple.com/games/game-porting-toolkit/)**
  for the Game Porting Toolkit and its `D3DMetal.framework`, the
  proprietary-but-redistributable D3D12-to-Metal translator that step
  2's "Metal" variant uses.
- **[gcenx (Dean M Greer)](https://github.com/Gcenx)** for maintaining
  [macOS Wine builds](https://github.com/Gcenx/macOS_Wine_builds),
  [game-porting-toolkit](https://github.com/Gcenx/game-porting-toolkit),
  and being one of the two people that keeps the free Mac Wine
  ecosystem alive.
- **[vitor251093](https://github.com/vitor251093)** for modernizing
  the Wineskin codebase, writing Sikarugir from the ground up, and
  being the other half of the duo that keeps the free Mac Wine
  ecosystem alive.
- **[PaulTheTall](https://www.paulthetall.com/)** for
  [Porting Kit](https://www.portingkit.com/), which packages the
  above into something a non-developer can install. Step 1 of this
  recipe is his app.
- **[Isaac Marovitz](https://github.com/IsaacMarovitz)** and the
  Whisky community, archived in May 2025, who proved that a friendly
  SwiftUI front-end to Wine on macOS is possible. Sikarugir is the
  successor.
- **[Khronos Group / MoltenVK](https://github.com/KhronosGroup/MoltenVK)**
  for the Vulkan-to-Metal translator that the engine bundles.

If you are reading this and want to support the work, please donate
upstream rather than to this repo:

- WineHQ: https://www.winehq.org/donate
- CodeWeavers (buy CrossOver): https://www.codeweavers.com/store
- gcenx: https://paypal.me/gcenx and https://ko-fi.com/gcenx
- PaulTheTall: https://www.paulthetall.com/portingkit-2/ has a Donate
  link

## Trademarks

Nominative fair use only. "CrossOver", "CodeWeavers", "Apple",
"macOS", "Apple Silicon", "Game Porting Toolkit", "D3DMetal", "Wine",
"Steam", "Subnautica", "Subnautica 2", "Porting Kit", "Sikarugir",
"Wineskin", and any other marks are referenced for identification only.
calimocho is not affiliated with, endorsed by, or sponsored by any of
these holders.

## License

The recipe and documentation in this repo are LGPL-2.1+, same as the
project always was. See [LICENSE](LICENSE). The recipe instructs you
to install software whose licenses are their own; nothing in this repo
includes or redistributes binaries from any of the projects credited
above.

## Where the engine work went

The previous incarnation of this project tried to build its own Wine
engine + D3DMetal shim. It produced a working `out/engine/` directory,
a SwiftUI menubar app, a CI pipeline, and ~3 months of investigation
documented in the ADR chain. None of that ships anymore. The git
history is the record.

The investigation produced one genuinely useful artifact for anyone
trying to do similar work:
[`docs/handover-2026-06-01-end-of-day.md`](docs/handover-2026-06-01-end-of-day.md)
is the postmortem of why building a competing Wine engine was the
wrong call when Sikarugir + PK already exist. The detailed reasoning
is in [ADR-0020](docs/ADR/0020-pivot-from-engine-to-recipe-archive.md).

## The engine for Xode (2026-10)

The engine came back for one narrow job: the Xode app needs a Wine
engine it can find on a beta tester's Mac. If you just want to play
Windows games on a Mac, buy [CrossOver](https://www.codeweavers.com/crossover)
or use the recipe above.

- Version scheme: `0.<Wine major+minor>.<Apple GPTK major>.<our build>`;
  engine IDs read `<Wine>-<Apple D3DMetal>-<build>`. The
  current one is `0.1120.4.6`, engine ID `calimocho-11.20-4.0b3-06` (Forza Horizon 6 fixes as opt-ins
  that are off for every other game, see
  [ADR-0079](docs/ADR/0079-forza-opt-ins-in-the-general-engine.md)).
- Built from the official Wine 11.20 tarball plus
  [`patches/wine-11.20/`](patches/wine-11.20/) by
  [`tools/release_engine.py`](tools/release_engine.py). All inputs are
  pinned in [`versions.json`](versions.json) under `release_engine`.
- Signed with the maintainer's Developer ID and notarized by Apple
  ([ADR-0078](docs/ADR/0078-developer-id-signed-engine-release.md)).
  Downloads, checksums and the corresponding source are on the
  [GitHub release](https://github.com/WorkingPrinciple/calimocho/releases/tag/engine-0.1120.4.6).
- The engine archive contains Apple's D3DMetal, which Apple allows to
  be distributed for non-commercial purposes only. This repository
  never contains Apple binaries; the build takes them from your own
  copy of Apple's Game Porting Toolkit.
- Release notes, contents and licence details:
  [`docs/release/11.20-4.0b3-06.md`](docs/release/11.20-4.0b3-06.md).
- Tested games, with what we actually saw:
  [`docs/TESTED-GAMES.md`](docs/TESTED-GAMES.md).
