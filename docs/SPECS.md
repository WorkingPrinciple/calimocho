# calimocho SPECS

> Source of truth for "what does each part promise". Architecture
> ("how it's built") is in ARCHITECTURE.md. Phases ("when each part
> ships") are in PHASES.md.
>
> Acceptance criteria are grouped by phase. A criterion ID like
> `A2.3` means Phase 2, criterion 3. Criteria are immutable once
> shipped (a new test gets a new ID, never re-uses an old one).

## Glossary

- **Engine**: the bundled Wine 11 + GPTK D3DMetal + MoltenVK runtime
- **Bottle**: a Wine prefix (a directory simulating a Windows C: drive)
- **Calimocho.app**: the SwiftUI menubar app that wraps the engine. Exists
  from Phase 2 onwards. **Calimocho.app does not depend on Whisky.app**,
  ever.
- **WINEPREFIX**: the path to a bottle, set as an environment variable
  when spawning wine

---

## Phase 0 acceptance criteria (foundation)

All completed as of commit `5714053`.

- A0.1 GitHub repo `dragoshont/calimocho` exists, public
- A0.2 README declares the project intent, decision table, full attribution
- A0.3 LICENSE captures both LGPL (our scripts) and non-commercial overlay
  (the bundled distribution)
- A0.4 AGENTS.md captures 8 hard rules + rules of engagement for AI agents
- A0.5 PLAN, PHASES, SPECS, ARCHITECTURE, TESTING, ux/* docs all exist
- A0.6 7 ADRs in `docs/ADR/`
- A0.7 CodeWeavers Wine 11.0 source tarball downloaded
  (`crossover-sources-26.1.0.tar.gz`, sha256 captured)
- A0.8 Apple GPTK 3.0 DMG read end-to-end; License.rtf transcribed for
  reference

---

## Phase 1 acceptance criteria (engine)

> Host arch: x86_64 (runs under Rosetta 2 on Apple Silicon — see
> [ADR-0010](ADR/0010-host-arch-x86_64-rosetta.md)). Rosetta 2 must
> be installed on the test machine; `softwareupdate --install-rosetta
> --agree-to-license` if absent.

A1.1 The built `wine` binary in `out/engine/bin/wine` reports version
`wine-11.0` when invoked with `--version`. Exit code 0. The binary is
x86_64 Mach-O (verified with `file`).

A1.2 `out/engine/bin/wine wineboot --init` against a clean WINEPREFIX
exits 0. The resulting `system.reg` includes a `wineVersion.major = 11`
line and a `#arch=win64` header. Bottle is initialized in under 90 s on
M1 Max.

A1.3 `out/engine/bin/wine notepad.exe` produces a visible window with a
title bar, menu bar, and editable text area within 10 s. Verified by
screencapture + ImageMagick NCC comparison against
`tests/visual/baseline/notepad-window.png` (threshold 0.85).

A1.4 `out/engine/bin/wine "C:\\Program Files (x86)\\Steam\\steam.exe"`
in a pre-installed bottle produces a visible Steam login window within
60 s. The window is not solid black. Verified by screencapture + NCC
comparison against `tests/visual/baseline/steam-login.png` (threshold
0.85).

A1.5 No file under `out/engine/` has the same sha256 as any file under
`/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/`.
Verified by `scripts/verify-no-copied-binaries.sh`.

A1.6 The build log (`docs/build-log.md`) contains: the configure flags
used, the build duration, every error encountered, and the fix applied.
At minimum the EXEEXT/PACKAGE_VERSION autoconf substitution issue is
documented with the patch script committed in `scripts/fixup-config-h.sh`.

### Phase 1 CLI surface (scripts, not yet a user-facing CLI)

These are developer scripts. They run from the repo root.

```text
scripts/fetch-sources.sh         # download Wine source + GPTK, verify sha256
scripts/build-wine.sh            # configure + make Wine 11
scripts/overlay-gptk.sh          # copy D3DMetal.framework into out/engine
scripts/test-engine.sh           # run A1.1 to A1.5 in sequence
scripts/verify-no-copied-binaries.sh  # AGENTS.md rule #1 enforcement
```

Each script:
- Exits 0 on success, non-zero on failure
- Logs to stderr with timestamps
- Honors `--verbose` for extra output
- Honors `--dry-run` (where it makes sense; no-op file changes, full log)

### Phase 1 file layout (developer side)

```text
~/Repo/calimocho/
├── build/wine/           # configure + make output, gitignored
│   ├── _install/         # `make install` destination
│   ├── config.log
│   └── ...
└── out/engine/           # what eventually becomes Calimocho.app bundled content
    ├── bin/
    │   ├── wine                          (x86_64 Mach-O)
    │   ├── wine64 -> wine
    │   ├── wineserver                    (x86_64 Mach-O)
    │   ├── wineserver64 -> wineserver
    │   └── wineboot -> wine
    ├── lib/
    │   ├── wine/
    │   │   ├── i386-windows/
    │   │   ├── x86_64-unix/
    │   │   ├── x86_64-windows/
    │   │   └── x86_32on64-unix/
    │   └── external/
    │       ├── D3DMetal.framework/
    │       └── libd3dshared.dylib
    └── share/wine/
```

All host-side binaries are x86_64 (no `aarch64-unix/`). See
[ADR-0010](ADR/0010-host-arch-x86_64-rosetta.md) for why.

There is no install target in Phase 1. The engine lives in `out/engine/`
and is invoked directly. We do not touch Whisky's Libraries folder. We
do not install anything to /Applications.

---

## Phase 2 acceptance criteria (app shell)

A2.1 `Calimocho.app` builds via `scripts/build-app.sh` and is ad-hoc
signed (`codesign --verify out/Calimocho.app` exits 0 with no
identifier warnings).

A2.2 Launching `Calimocho.app` creates a menubar item with the 🍷 icon
within 2 s. The Dock shows no icon (it is menubar-only).

A2.3 On first launch with no existing bottle at
`~/Library/Application Support/Calimocho/Bottles/STEAM/`, the first-run
wizard appears as documented in [ux/APP-DESIGN.md](ux/APP-DESIGN.md).
The five wizard steps complete successfully in this exact order:
  1. Welcome (always advances)
  2. System check (advances only if Mac is arm64 + macOS ≥ 15 + ≥20 GB
     free + network reachable)
  3. Install Steam (creates the STEAM bottle, downloads
     `SteamSetup.exe` from
     `https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe`,
     runs the installer inside the bottle silently)
  4. Progress (real progress bar, updates at least every 5 s)
  5. Done (offers "Launch Steam Now" or "Launch Steam Later")

A2.4 Clicking the menubar "Open Steam for Windows" launches Steam and
the user reaches the Library view after signing in. Signing in is
manual (we never store credentials).

A2.5 Quitting `Calimocho.app` via the menu's Quit item terminates all
spawned wine processes (wine, wineserver, winedevice, steam.exe,
steamwebhelper) within 10 s of clicking Quit. Verified by
`pgrep -lf 'wine|steam.exe|steamwebhelper'` returning empty.

A2.6 `Calimocho.app` works correctly on a Mac with Whisky.app
uninstalled. Verified by:
  1. `brew uninstall --cask whisky`
  2. `rm -rf ~/Library/Application Support/com.isaacmarovitz.Whisky`
  3. `rm -rf ~/Library/Containers/com.isaacmarovitz.Whisky`
  4. Reboot
  5. Open `Calimocho.app`, complete wizard, launch Steam, see Library

A2.7 The app launches at most one Steam process at a time. Clicking
"Open Steam for Windows" while Steam is already running brings the
existing Steam to the front (does not spawn a duplicate).

A2.8 All persistent state lives under
`~/Library/Application Support/Calimocho/`. Logs live under
`~/Library/Logs/Calimocho/`. The app writes nowhere else.

### Phase 2 CLI surface (the `calimocho` CLI tool starts here)

The CLI lives inside the .app bundle at
`/Applications/Calimocho.app/Contents/Resources/calimocho`. For developer
convenience a symlink can be created at `~/bin/calimocho`. The same
binary is also accessible from the repo's `bin/calimocho` during
development.

```text
calimocho help
calimocho version
calimocho status              # bottle exists? engine ok? Steam installed?
calimocho install-steam       # run the wizard's Install Steam step from CLI
calimocho launch-steam        # spawn Steam (same as menubar click)
calimocho stop                # gracefully terminate the entire bottle process tree
calimocho diagnose            # write a redacted bundle of logs + config
calimocho uninstall           # remove bottle data + (optionally) /Applications/Calimocho.app
```

### Phase 2 exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | general failure (see stderr or log) |
| 2 | usage error (bad flag, missing required arg) |
| 3 | engine missing or broken |
| 4 | bottle missing (run install-steam first) |
| 5 | bottle exists but is corrupt |
| 6 | Wine process group failed to terminate within 10 s |
| 7 | user aborted |
| 8 | network unreachable when one is required (e.g. install-steam) |
| 9 | disk full or insufficient space |
| 64-78 | reserved (sysexits.h) |

### Phase 2 file layout

```text
/Applications/Calimocho.app/
└── Contents/
    ├── Info.plist
    ├── MacOS/Calimocho                          # the SwiftUI binary
    ├── Resources/
    │   ├── Engine/                              # contents of out/engine
    │   ├── calimocho                            # the CLI binary
    │   └── Assets.car
    ├── Frameworks/Sparkle.framework             # added in Phase 5
    └── _CodeSignature/

~/Library/Application Support/Calimocho/
├── Bottles/
│   └── STEAM/
│       ├── drive_c/
│       ├── system.reg
│       └── config.json                          # OUR per-bottle config
├── config.json                                  # global app config
└── (no Whisky-style Containers/ folder; we own everything)

~/Library/Logs/Calimocho/
├── calimocho-YYYYMMDD.log                       # one file per day
└── wine-STEAM-YYYYMMDD.log                      # per-bottle wine stderr
```

---

## Phase 3 acceptance criteria (Subnautica 2)

A3.1 From a logged-in Steam inside Calimocho, the user can search "Subnautica 2",
click Install, and the 15 GB download completes successfully.

A3.2 SN2 reaches the main menu within 60 s of clicking Play in Steam.

A3.3 D3DMetal is the active DX12 backend. Verified by:
  - `file` on the bottle's `d3d12.dll` reports a size larger than 1 MB
    and Mach-O references to `D3DMetal.framework` (not Wine's wined3d
    stub which is under 100 KB).
  - The bottle's `Saved/Logs/Subnautica2.log` (UE5's log) contains
    "RHI: D3D12" or equivalent.

A3.4 Gameplay sustains at least 30 FPS at 1080p Medium for 30
consecutive minutes on M1 Max. Verified via the game's built-in FPS
counter screenshot at minutes 0, 10, 20, 30.

A3.5 Save data persists across game restarts and across Calimocho.app
restarts and across a macOS reboot.

A3.6 UE4SS + Console Commands mod installed via
`scripts/install-sn2-mods.sh`. Ctrl+F2 in-game opens the console.
Typing `god` (and the matching enter / send) toggles invincibility.

A3.7 The maintainer plays a full 30+ minute session with their son
without a Wine-side crash. Game-side Early Access crashes
(e.g. the corroded-boxes intro bug) count as game bugs, not Wine bugs.

### Phase 3 CLI surface additions

```text
calimocho bottle list                       # show bottles (always: STEAM)
calimocho bottle config STEAM               # print bottle config (Win ver, sync, DLL overrides)
calimocho game install sn2                  # install SN2 game files + mods + bottle config
calimocho game migrate-from-crossover sn2   # one-off: rsync 15 GB from CrossOver bottle
calimocho game launch sn2                   # launch Steam + click Play SN2
calimocho game uninstall sn2                # remove SN2 game files but leave Steam/bottle
```

### Phase 3 file layout

In the bottle:
```text
~/Library/Application Support/Calimocho/Bottles/STEAM/drive_c/Program Files (x86)/Steam/
└── steamapps/
    ├── appmanifest_2864380.acf
    ├── common/
    │   └── Subnautica2/
    │       └── Subnautica2/
    │           └── Binaries/
    │               └── Win64/
    │                   ├── Subnautica2-Win64-Shipping.exe
    │                   ├── xinput1_3.dll              # UE4SS DLL proxy
    │                   ├── ue4ss/
    │                   │   ├── UE4SS.dll
    │                   │   ├── UE4SS-settings.ini
    │                   │   └── Mods/
    │                   │       ├── DebugUIToggle/     # F2 console toggle mod
    │                   │       └── ...
    │                   └── ...
```

In the repo:
```text
bottles/sn2/config.json
bottles/sn2/dll-overrides.reg          # xinput1_3 native,builtin
bottles/sn2/launch-args.json
scripts/install-sn2-mods.sh
scripts/migrate-sn2-from-crossover.sh
```

---

## Phase 4 acceptance criteria (DMG packaging)

A4.1 `scripts/build-dmg.sh` produces `out/dmg/Calimocho-vX.Y.Z.dmg`.

A4.2 The DMG passes `hdiutil verify out/dmg/Calimocho-vX.Y.Z.dmg`
(exit 0, no warnings).

A4.3 The DMG mounts on macOS 15 and 26 (the last two macOS versions at
Phase 4 time).

A4.4 `Calimocho.app` inside the DMG is ad-hoc signed
(`codesign --verify` exits 0 with no identifier warnings).

A4.5 A clean M-series Mac (one that has never had Calimocho installed)
can: download DMG → drag Calimocho.app to /Applications → right-click →
Open → complete first-run wizard → launch Steam → install SN2 →
reach SN2 main menu. All steps complete in under 15 minutes of user
clicking, excluding the SN2 game download itself.

A4.6 Uninstalling via `Option-click menu → Uninstall Calimocho` removes
all calimocho files (`/Applications/Calimocho.app`,
`~/Library/Application Support/Calimocho/`,
`~/Library/Logs/Calimocho/`). No orphan wine processes. No leftover
launchd jobs. Verified by `find / -iname '*calimocho*' 2>/dev/null`
returning only the DMG in ~/Downloads (which is the user's
responsibility to delete).

A4.7 README.md install instructions match the exact UX of A4.5. If they
differ, README is wrong, not the app.

A4.8 **The DMG is self-contained**. `Calimocho.app` ships with the
full engine and Apple GPTK Redistributables pre-bundled:

```text
Calimocho.app/Contents/Resources/Engine/
├── bin/wine
├── lib/wine/{i386-windows,x86_64-windows,x86_64-unix}/
└── lib/external/
    ├── D3DMetal.framework/
    └── libd3dshared.dylib
Calimocho.app/Contents/Resources/THIRDPARTY/Apple-GPTK/License.rtf
```

A user installing calimocho does **not** download GPTK separately,
does **not** need an Apple Developer ID, does **not** wait for
first-launch lazy downloads. One drag from the DMG to /Applications
puts everything in place. Verified by:

```bash
hdiutil attach Calimocho-vX.Y.Z.dmg -nobrowse -quiet
test -f "/Volumes/Calimocho/Calimocho.app/Contents/Resources/Engine/bin/wine"
test -d "/Volumes/Calimocho/Calimocho.app/Contents/Resources/Engine/lib/external/D3DMetal.framework"
test -f "/Volumes/Calimocho/Calimocho.app/Contents/Resources/THIRDPARTY/Apple-GPTK/License.rtf"
hdiutil detach "/Volumes/Calimocho" -quiet
```

This matches the distribution model of every shipping Wine-on-Mac
stack (CrossOver, Whisky) and is permitted by Apple GPTK SLA §2A(iii)
+ §2C — see [ADR-0011](ADR/0011-ci-and-gptk-redistribution.md).

A4.9 DMG size budget: ≤ 250 MB. (Wine engine ~150 MB + GPTK redist
~16 MB + SwiftUI app ~10 MB + DMG metadata + slack ≈ 200 MB target,
250 MB hard ceiling. Exceeding the ceiling indicates dead weight
that needs trimming — e.g. debug symbols, unused locales.)

A4.10 **LGPL written-offer compliance**. The DMG contains
`Calimocho.app/Contents/Resources/THIRDPARTY/Wine/NOTICE` (verbatim
copy of `THIRDPARTY/Wine/NOTICE` from the source repo at the matching
release tag). The About box exposes a "License & attribution" item
that opens this file. The NOTICE pins the upstream CodeWeavers Wine
tarball URL + sha256 and links the calimocho release tag whose
`scripts/patches/` directory holds the in-tree modifications. Phase 5
`release.yml` blocks publishing if the NOTICE is missing from the
DMG. See [ADR-0012](ADR/0012-lgpl-written-offer-compliance.md).

### Phase 4 deliverables

- `scripts/build-dmg.sh` (uses `hdiutil` or `create-dmg`)
- `dmg-assets/background.png` (the drag-here image)
- `dmg-assets/dmg-layout.applescript` (icon positioning)
- `tests/manual/release-checklist.md` (v1.0 release checklist)
- README updated with v1.0 install flow + at least 2 screenshots

### Phase 4 NOT in scope

- Apple notarization (never; AGENTS.md rule #8)
- App Store distribution (never; Wine JIT)
- Auto-update via Sparkle (Phase 5)
- Homebrew tap (Phase 5 optional)
- **Lazy/on-demand GPTK download**. Calimocho explicitly does NOT
  ask the user to download GPTK at first run (CrossOver and Whisky
  both pre-bundle it; we match that pattern per A4.8). The legal
  basis is in ADR-0011.

---

## Phase 5 acceptance criteria (CI + auto-update)

A5.1 `.github/workflows/build.yml` runs on every push to main and every
pull request opened against main. The workflow lints, builds, runs
Tier 0-3 tests from TESTING.md, and uploads a DMG as a workflow
artifact.

A5.2 The build.yml total wall time is under 60 minutes (cold cache) or
under 15 minutes (warm cache).

A5.3 `.github/workflows/release.yml` runs on every tag matching `v*`.
It builds the DMG, signs it with Sigstore (cosign + GH OIDC), and
creates a GitHub Release with: DMG, sha256, Sigstore signature bundle,
source tarball link, release notes pulled from CHANGELOG.md.

A5.4 `.github/workflows/test-matrix.yml` runs weekly (cron) on
macos-15 and macos-26. Failures are reported as auto-created GitHub
issues with the workflow logs attached.

A5.5 Sparkle is integrated into `Calimocho.app`. The app polls
`https://raw.githubusercontent.com/dragoshont/calimocho/main/appcast.xml`
(or HTTPS equivalent) once per day. When a new version is detected, the
user sees a non-blocking dialog as documented in
[ux/USER-JOURNEY.md](ux/USER-JOURNEY.md) "Update day".

A5.6 An end-to-end auto-update test:
  1. Install Calimocho vX.Y.Z manually
  2. Tag vX.Y.(Z+1) in this repo
  3. Wait for release.yml to publish the new DMG + appcast update
  4. Open the older Calimocho.app
  5. Within 60 s, the update notification appears
  6. Clicking "Install and Relaunch" replaces the app with vX.Y.(Z+1)
  7. The bottle, Steam install, and SN2 saves are all untouched

A5.7 Builds are reproducible: building the same git ref with the same
`SOURCE_DATE_EPOCH` value produces a DMG with identical sha256.
Verified by running build.yml twice against the same commit.

A5.8 Visual regression tests (Tier 3) catch the Steam UI black-window
bug. Confirmed by intentionally regressing to upstream Wine 11.9 (no
CW patches), pushing a PR, and observing build.yml fail with the
expected red.

### Phase 5 deliverables

- `.github/workflows/lint.yml`
- `.github/workflows/build.yml`
- `.github/workflows/release.yml`
- `.github/workflows/test-matrix.yml`
- `appcast.xml` + EdDSA signing key (private key in `~/.calimocho-keys/`,
  never committed; public key embedded in Calimocho.app at build time)
- `scripts/sparkle-eddsa-sign.sh`
- `scripts/sign-with-sigstore.sh`
- `tests/visual/baseline/` (committed PNG baselines)
- `tests/visual/baseline-bottle.tar.zst` (sha256-pinned, downloaded by
  CI from a GitHub Release attachment to keep repo size sane)
- `CHANGELOG.md` (Keep-A-Changelog format)
- Optional: `Formula/calimocho.rb` for the `dragoshont/homebrew-calimocho`
  tap

### Phase 5 NOT in scope

- Game-launch tests on GitHub-hosted runners (no GPU; we use the
  maintainer's M1 Max for weekly Tier 4 instead)
- Performance benchmarks
- Telemetry
- Crash reporting
- Cloud bottle sync

---

## Phase 6+ acceptance criteria (wishlist games, optional)

Per game added:

A6.N.1 The game is in `docs/games-i-miss-on-my-mac.md` Wishlist row
before testing.

A6.N.2 The bottle config required for the game is committed in
`bottles/<game-id>/config.json` and documented in
`bottles/<game-id>/README.md`.

A6.N.3 The game reaches its main menu and at least one minute of
gameplay.

A6.N.4 The maintainer plays at least 10 minutes without a Wine-side
crash.

A6.N.5 The row in `games-i-miss-on-my-mac.md` is updated from "Wishlist"
to "Working" with hardware tested and date.

A6.N.6 The maintainer commits to test the game again before each
Calimocho release to confirm it still works. If it stops working, the
row moves back to "Wishlist" with a "regression at vX.Y.Z" note.

---

## Cross-phase invariants

### Versioning

- Semantic versioning: `MAJOR.MINOR.PATCH`
- `0.x.y` until Phase 5 acceptance is met everywhere
- `1.0.0` when Phase 5 is shipped on a tagged release
- Tags are immutable
- Releases are GitHub Releases tied to tags

### Hashes published per release

- DMG sha256 (in release notes)
- Tarball sha256 (in release notes)
- Wine binary sha256 (in `out/engine/MANIFEST.sha256`, committed to the
  release)
- D3DMetal binary sha256 (same MANIFEST)

### Logging

- All logs under `~/Library/Logs/Calimocho/`
- Filename: `calimocho-YYYYMMDD.log` (one per day, rotated)
- Per-bottle wine stderr: `wine-<bottle-name>-YYYYMMDD.log`
- `calimocho diagnose` collects the last 7 days + relevant bottle logs
  into a single redacted zip under `~/Downloads/`

### Configuration

- User-tunable settings: `~/Library/Application Support/Calimocho/config.json`
- Pinned versions for the build: `versions.json` at repo root
- No env-var-only configuration; everything has a documented config-file key
- Default values documented inline in `versions.json` and `config.json`

### Error messages

Both CLI (stderr) and GUI (dialogs) follow:

```text
calimocho: ERROR <short title>
  Reason: <what happened, plain English, non-native-English-friendly>
  Fix:    <what to try>
  Docs:   https://github.com/dragoshont/calimocho/docs/troubleshooting.md
```

GUI dialogs include the same fields plus an explicit "Try CrossOver"
button on any error that recommends fallback.

### Hard rules from AGENTS.md (re-stated here for testability)

These are testable specs, not aspirations:

- AGENTS rule #1: No file under `out/engine/` has a sha256 matching any
  file under `/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/`.
  Verified by A1.5.
- AGENTS rule #2: No paid features anywhere. Verified by manual review of
  every release: no "Pro", no "Premium", no "Cloud", no payment URLs.
- AGENTS rule #6: No telemetry. Verified by: built app contains no calls
  to network endpoints other than (a) Sparkle's appcast URL, (b)
  Apple's notarization service (which we do not use), (c) Wine's own
  network behavior at runtime which is the user's traffic, not ours.
- AGENTS rule #8: All binaries are ad-hoc signed. Verified by
  `codesign --display --verbose out/Calimocho.app` reporting
  `Authority=(unsigned)` or `Signed Identifier=ad-hoc`.

If any of these hard-rule tests fail, the release is blocked.
