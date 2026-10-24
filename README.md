# calimocho

> **Source work reactivated, 2026-10-24.** Calimocho is investigating a
> current Wine runtime selectable through Exodus for Mac. It is not yet
> a qualified game runtime. For a supported product, consider
> [CrossOver](https://www.codeweavers.com/crossover).
>
> The older Porting Kit recipe below records a Steam Subnautica 2 result.
> It does not establish Xbox compatibility or qualify this source build.
> See [ADR-0022](docs/ADR/0022-reactivate-isolated-source-builds.md).

![Use: non-commercial only](https://img.shields.io/badge/Use-non--commercial%20only-orange.svg)
![Platform: macOS arm64](https://img.shields.io/badge/Platform-macOS%20arm64-lightgrey)

---

## Historical archive decision (2026-06-01)

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
calimocho stopped shipping a Wine engine and became the recipe below.
The owner has since reactivated isolated source work; this historical
decision is not a claim that the new runtime is ready.

If you want the full reasoning, read
[ADR-0021](docs/ADR/0021-local-runtime-recipes-without-reviving-engine.md).

## Isolated source builds

The current-Wine target is official WineHQ 11.20, pinned in `versions.json`.
The first integration baseline is public CodeWeavers 26.3 source, which
contains Wine 11.0. It is not the latest-Wine deliverable. Neither build
includes Apple payloads or the retired Calimocho D3D11 shim by default.
Compilation does not establish GPTK ABI compatibility or Xbox gameplay.

Use Python 3.12 or newer for source archive filtering, installed Xcode/CLT,
bison 3 or newer, flex, make and both MinGW PE compilers. These commands
never install global packages. Download the exact source URLs from
`versions.json` into an owned directory first; the scripts verify their
SHA-256 before extraction. A CodeWeavers archive already retained locally
can be reused after verification.

```bash
python3 tools/build_freetype.py \
  --archive /absolute/path/to/freetype-2.13.3.tar.xz \
  --output build/dependencies/freetype-x86_64-new
PATH="/opt/homebrew/opt/bison/bin:$PATH" \
  python3 tools/build_cw_candidate.py \
  --archive /absolute/path/to/crossover-sources-26.3.0.tar.gz \
  --freetype build/dependencies/freetype-x86_64-new/prefix \
  --output build/cw26.3-new
```

Every output must be new. Existing outputs are rejected, not removed.
FreeType has a ten-minute build budget and a local-prefix install step.
Wine configure/compile has a thirty-minute budget. The default Wine targets
are loader, server and macOS driver, not a complete runtime. `--build-all`
compiles all configured runtime/PE targets, without installing or launching.
Logs and `receipt.json` bind source, source edits, tools and artifact bytes.
Keep receipts local: they contain absolute paths.

`--winehq-source /absolute/path/to/pristine/wine-checkout` instead uses the
exact pinned WineHQ commit in a fresh source copy and applies the measured
experimental public-source D3DMetal port. It rejects a modified input
checkout and records every changed file and donor hash. This option is an
integration investigation, not proof of a usable Apple graphics runtime.
The Darwin x86_64 native-GS port also builds
`build/loader/libnative-gs-localtime.dylib` inside the requested output.
The actual loader has a required `LC_LOAD_DYLIB` dependency on
`@loader_path/libnative-gs-localtime.dylib`; no injection environment
variable is needed. Its source/binary/compiler hashes and loader load
commands are recorded in `receipt.json`. Preserve that dependency and
the recorded FreeType environment when testing an isolated install.
A normal `make install` does not install this research helper: retain it
beside the actual loader in `lib/wine/x86_64-unix/`. A missing helper fails
at process load rather than falling back to an unsafe runtime.
The helper uses loader-supported symbol interposition, not instruction
patching, Apple binary changes, or the retired D3D11 shim.
Normal fonts are required. Unresolved TLS, media and graphics dependencies
are reported by configure, not silently treated as game support.

For a separate Direct3D 10/11 research path, public
[DXMT](https://github.com/3Shain/dxmt) describes a Metal translation layer
and is LGPL-2.1-or-later. It is not a Direct3D 12 replacement and has not
been built or qualified here. Keep any future DX11 build and registry
record distinct from the current-Wine DX12 candidate.

Current source/build findings are in [the build log](docs/build-log.md).
The source-built CW26.3 baseline now passes isolated builtin startup and
the D3D12 device-creation probe with the owner's installed GPTK 4.0b3
payload referenced through read-only symlinks. The
[sanitized engine record](docs/evidence/calimocho-cw26.3-gptk4b3.registry.json)
binds its source, loader/server hashes, FreeType path, renderer links and
smoke logs. Its path placeholders are not executable configuration; use
the matching local registry artifact to bind the actual host paths.

WineHQ 11.20 port-09 now passes fresh-prefix builtin startup, `cmd /c ver`,
a registry query and the same D3D12 device-creation probe as the CW baseline:
both return `S_OK`. This requires the source-built localtime helper above.
The helper protects both localtime and libc-internal ctime calls.
See [ADR-0024](docs/ADR/0024-loader-linked-time-slot-protection.md) and the
[parity evidence](docs/evidence/winehq-port09-time-and-conformance.json).
The identical D3D12 conformance executable fails on both WineHQ and CW
with the same refcount failures and missing-window-data swapchain error.
The CW run then times out during exception handling. This shared failure
does not establish a forward-port regression or passing conformance.
A separate owned normal-window probe now completes **120 Presents** on
both runtimes and reads back exactly RGBA `51,102,204,255`. Targeted
on-screen captures show the blue window and are byte-identical.
See [presentation evidence](docs/evidence/req74-d3d12-present-parity.json)
and [ADR-0025](docs/ADR/0025-owned-normal-window-presentation-probe.md).
This is bounded presentation smoke, not gameplay or full graphics coverage.
No game was launched.
Game admission remains coordinator-owned and additionally requires the
canonical route, save-preservation, disk and input-lease checks.

## Local Ode/Exodus runtime reference

The exporter does not make Calimocho a distinct engine to select in Ode. This local source
adapter exports one already installed, explicitly selected free Wine runtime
from Ode's existing engine registry. Use Python 3.9 or newer:

```bash
umask 077
OUTPUT="$(mktemp "${TMPDIR:-/tmp}/selected-runtime.XXXXXX")"
python3 tools/runtime_recipe.py \
  --registry "/absolute/path/to/xode-wine/engines/registry.json" \
  --engine "apple-gptk-4.0b3" > "$OUTPUT"
printf 'Private export: %s\n' "$OUTPUT"
```

Paths are examples, not discovery rules. Use the exact name present in your
registry and a separate output file. No default engine or hidden fallback is
chosen. A successful export is a schema-version-1 registry with the selected
record unchanged. It retains the exact Wine/wineserver paths, environment,
renderer assets, dependencies, overlays, registry imports, and receipts.
Keep runtime lookup paths such as `DYLD_FALLBACK_LIBRARY_PATH` in that
selected record's `environment`; the exporter does not merge ambient shell
values into the recipe.
The additional `calimocho_recipe` metadata records the input and full-record
digests and observed file hashes. It does not change the engine's name.

The existing Ode/Exodus launch adapter consumes this file through
`--registry "$OUTPUT" --engine apple-gptk-4.0b3`,
along with its separately admitted `--prefix`, `--runtime-dll`, and
`--shim-dir` arguments. It remains responsible for full-record prefix
ownership, fresh-process boundaries, save preservation, and launch admission.
This exporter has no launch or prefix option. Do not use the retired
`bin/calimocho-wine` launcher, which injects historical shim defaults.

The exporter checks pinned Wine and asset bytes, records the explicit
wineserver bytes, and rejects missing or ambiguous selection, malformed
records, unsafe overlay destinations, and entrypoints escaping the selected
installation. Directory dependencies are checked for presence, not complete
content integrity. Existing smoke/trust metadata is preserved as data, never
executed or promoted to new evidence. Local paths and source URLs are not a
redistribution licence. Keep exports local.
The export includes absolute local paths, environment settings, and runtime
metadata. The restrictive `umask` and `mktemp` keep this example private to
your account. Do not share, upload, or commit the export; delete it when it is
no longer needed.

The Steam recipe below is historical Steam evidence, not Xbox evidence.
Neither this exporter nor file presence proves graphics, a game launch,
engine switching, or save reload. The owner-directed source work does not
authorize a Subnautica 2 launch or game/prefix mutation. See
[ADR-0021](docs/ADR/0021-local-runtime-recipes-without-reviving-engine.md)
and [troubleshooting](docs/troubleshooting.md).

Focused checks run without executing Wine or changing any real prefix:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_runtime_recipe.py'
```

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
is in [ADR-0021](docs/ADR/0021-local-runtime-recipes-without-reviving-engine.md).
