# calimocho — Development Phases

> **Status as of 2026-10-24: owner-directed source work reactivated.**
> [ADR-0022](ADR/0022-reactivate-isolated-source-builds.md) supersedes
> the archive-only scope for an isolated current-Wine/Exodus investigation.
> The single canonical program scope is
> `dragos-core projects/ode-to-x/SPEC.md`, COR-36 / REQ-69.
> The history below remains the original phase plan, not current acceptance.
> Source compilation and the earlier registry exporter do not complete a
> runtime, graphics, game, distribution or historical phase gate.

> Six phases, each independently shippable. Each phase has explicit
> acceptance criteria (see SPECS.md sections A0-A5). Phase N cannot
> start until Phase N-1's acceptance criteria are all green.
>
> We never gold-plate within a phase. Ship and iterate.

## Phase summary

| Phase | Title | Goal | Demo |
|---|---|---|---|
| **0** | Foundation | Repo, docs, rules, license, build deps. Reproducible source download with sha256 pin. | `git clone` works. `docs/PLAN.md` is current. `scripts/fetch-sources.sh` produces a verified Wine source tarball. |
| **1** | Engine | Build CodeWeavers Wine 11 from source. CLI-only validation: `wine notepad.exe` shows a window. `wine steam.exe` reaches the Steam login UI. No GUI yet. | Maintainer runs `./scripts/build-wine.sh`, then `./scripts/test-engine.sh`, sees Steam login window without black-window bug. |
| **1.5** | CI + GPTK re-hosting | GitHub Actions build pipeline; calimocho-hosted GPTK Redistributables tarball; `versions.json` as single source of truth. Brought forward from Phase 5 per ADR-0011. | Push to any branch runs full pipeline; first PR run on `phase1-engine` passes A1.1–A1.5 end-to-end in CI. |
| **2** | App shell | `Calimocho.app` exists. Menubar item + first-run wizard. Wraps the Phase 1 engine. Manually installed (drag to /Applications; no DMG yet). | Maintainer opens Calimocho.app, clicks "Install Steam", clicks "Launch", sees Steam login window inside the app's launcher. |
| **3** | Game | Subnautica 2 installs from inside Calimocho's Steam, launches, plays. Mods (UE4SS + console commands) installed via Calimocho's bottle config. | Maintainer plays SN2 for 30+ minutes from a single Calimocho.app launch. |
| **4** | Packaging | DMG installer with Calimocho.app inside. Ad-hoc signed. Sigstore signature alongside the DMG. README with screenshots. | A clean M-series Mac downloads the DMG, drags Calimocho.app to /Applications, completes wizard, plays SN2, following only the README. |
| **5** | CI + auto-update | GitHub Actions builds the DMG on push to main. Sparkle auto-update wired (EdDSA-signed appcast). Visual regression test for Steam UI. Weekly SN2 launch test on self-hosted runner. | Push to main creates a DMG as a workflow artifact. Tag creates a GitHub Release. An old version self-updates to the new version via Sparkle. |
| **6+** | Wishlist games (optional) | Test the wishlist games one at a time. Document bottle config per game. Only when the maintainer personally wants to play one. | A row in `games-i-miss-on-my-mac.md` moves from "Wishlist" to "Working". |
| **∞** | Archive | Trigger: Unknown Worlds ships a native macOS build of Subnautica 2. | README updated to point at the native build. Repo set to read-only. Everyone thanked in a final release. |

## Phase 0: Foundation (done as of 2026-05-31)

### Acceptance criteria

- [x] Repo `dragoshont/calimocho` exists, public, LGPL with non-commercial overlay
- [x] AGENTS.md hard rules locked in
- [x] PLAN.md + SPECS.md + ARCHITECTURE.md + TESTING.md + ux/* + ADRs all written
- [x] CodeWeavers Wine 11 source downloaded and sha256 captured
- [x] Apple GPTK 3.0 DMG mounted and the License.rtf read verbatim
- [x] Build dep list pinned (`bison flex mingw-w64 gnutls freetype sdl2 pkg-config`)

### Deliverables

All in repo as of commit `5714053`.

## Phase 1: Engine

### Acceptance criteria

See SPECS.md section A1.

Summary:
- A1.1 `wine --version` reports `wine-11.0`
- A1.2 `wineboot --init` on a clean prefix exits 0, prefix's `system.reg`
  shows `wineVersion.major = 11`
- A1.3 `wine notepad.exe` produces a visible Notepad window within 10 s
- A1.4 `wine steam.exe` produces a visible Steam login window within 60 s
  (not solid black; Tier 3 visual regression test passes)
- A1.5 No file in our build output was copied from
  `/Applications/CrossOver.app/`. Provenance verified by sha256 against
  our build output manifest.

### Deliverables

- `scripts/fetch-sources.sh` (idempotent, sha256-verified)
- `scripts/build-wine.sh` (runs configure + make, captures logs)
- `scripts/test-engine.sh` (runs A1.1 to A1.5 in sequence)
- `out/engine/` directory containing the built Wine + GPTK overlay
- `docs/build-log.md` updated with: configure flags, build duration,
  any errors hit (e.g. EXEEXT autoconf issue) and how they were fixed

### Out of scope for Phase 1

- No SwiftUI app yet
- No DMG
- No Calimocho.app
- No GUI of any kind
- No second bottle, no second game
- ~~No CI~~ — **moved up to Phase 1.5** per [ADR-0011](ADR/0011-ci-and-gptk-redistribution.md)

## Phase 1.5: CI + GPTK re-hosting (added 2026-06-01)

Added per [ADR-0011](ADR/0011-ci-and-gptk-redistribution.md) after PR #1
adversarial review found that script bugs catchable by deterministic
CI were slipping through manual verification. CI work originally
scoped to Phase 5; only the build pipeline portion is brought forward
here. Phase 5 still owns release.yml, auto-update, visual regression
baselines, multi-OS test matrix.

### Acceptance criteria

- A1.5.1 `versions.json` exists at repo root, lists `cx_sources` and
  `gptk_redist` with `url` + `sha256` for each.
- A1.5.2 `scripts/package-gptk-redist.sh` produces a deterministic
  `gptk-redist-<version>-<repack>.tar.zst` containing
  `D3DMetal.framework`, `libd3dshared.dylib`, `License.rtf`, and a
  per-repack `README.md`. The tarball is uploaded to a GitHub Release
  on `dragoshont/calimocho` under tag `gptk-redist-<version>-<repack>`.
- A1.5.3 `scripts/fetch-sources.sh` reads `versions.json` and downloads
  both upstream artifacts with sha256 verification. Works with no
  local DMG, no Apple ID.
- A1.5.4 `scripts/overlay-gptk.sh` prefers the fetched tarball, falls
  back to mounted DMG only for maintainer iteration.
- A1.5.5 `.github/workflows/build.yml` runs on every push and PR.
  Executes prep-build-deps → fetch → patch → build → overlay → sign →
  test. Wall time ≤ 60 min cold, ≤ 15 min cached. Fails the PR on any
  A1.x FAIL.
- A1.5.6 `THIRDPARTY/Apple-GPTK/License.rtf` exists at repo root,
  populated by `overlay-gptk.sh` (per GPTK SLA §2A "include all
  copyright notices").
- A1.5.7 First CI run on `phase1-engine` branch passes end-to-end.
- A1.5.8 `.github/workflows/upstream-watch.yml` runs weekly + on
  demand. Detects new CodeWeavers Wine source releases (scraping
  codeweavers.com/crossover/source), new Apple GPTK releases (via
  Gcenx/game-porting-toolkit), and Whisky un-archive (via repo
  archived field). Opens a deduped GitHub Issue per finding.
- A1.5.9 `scripts/bundle-deps.sh` copies every dylib Wine `dlopen`s
  at runtime (libfreetype, libgnutls, libdbus, libSDL2, plus
  transitive deps) into `out/engine/lib/external/runtime/`. Each
  dylib's license attribution lives in `THIRDPARTY/runtime-libs/README.md`.
  Total bundle size ≤ 15 MB.
- A1.5.10 `out/engine/bin/calimocho-wine` wrapper exists, sets
  `WINEDLLOVERRIDES=mscoree,mshtml=`,
  `DYLD_FALLBACK_LIBRARY_PATH=<engine>/lib/external/runtime:<engine>/lib/external:/usr/lib`,
  and `WINEDEBUG=err-all,fixme-all` (all overridable), then
  `exec`s the real wine binary. Phase 2's
  `Calimocho.app/Contents/Resources/Engine/bin/calimocho-wine` is
  the same script.
- A1.5.11 **Self-contained verification**: copy `out/engine/`
  to an arbitrary path (`/tmp/cal-iso/`), run
  `WINEPREFIX=$(mktemp -d) /tmp/cal-iso/bin/calimocho-wine wineboot --init`
  with `unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH`, prefix
  initializes cleanly with `#arch=win64`, **no** /usr/local in the
  dyld path. Proves the engine drops into Calimocho.app unchanged
  and runs on Macs without Homebrew.

### Phase 1.5 followups (carried into Phase 2)

These remain deferred. Phase 2 cannot close until each is addressed:

- **A1.4 Steam login** — deferred because it requires a Steam-installed
  bottle, which is the Phase 2 wizard's "Install Steam" deliverable.
  Retest A1.4 against the wizard-installed bottle as part of A2.4.
- ~~Bundled runtime libraries~~ — done in A1.5.9 + A1.5.10
  (this Phase 1.5 PR).
- ~~Engine env-var wrapper~~ — done in A1.5.10 (this Phase 1.5 PR).
- **A1.3 visual NCC check** — A1.3 currently passes on "process alive
  after 6s", not on the SPECS-mandated screencapture + ImageMagick NCC
  ≥ 0.85 against `tests/visual/baseline/notepad-window.png`. The
  baseline image and the Tier 3 harness are Phase 5 deliverables; A1.3
  upgrades from PARTIAL to FULL pass when that lands.
- **A1.5 against a real CrossOver install** — A1.5 today SKIPs when
  CrossOver isn't installed. The Phase 5 CI matrix will run A1.5 on a
  runner with CrossOver Trial installed to do a real sha256 comparison.
- **`fixup-config-h.sh` version literal** — currently hardcodes
  `PACKAGE_VERSION "11.0"`. Should read the `VERSION` file from the
  source tree. Owned by next CodeWeavers source bump.

## Phase 2: App shell

### Acceptance criteria

See SPECS.md section A2.

Summary:
- A2.1 Calimocho.app launches and shows a menubar icon
- A2.2 First-run wizard appears when no STEAM bottle exists
- A2.3 First-run wizard's "Install Steam" step actually installs Steam
  into a Calimocho-owned bottle at
  `~/Library/Application Support/Calimocho/Bottles/STEAM/`
- A2.4 Menubar "Open Steam for Windows" launches Steam and the user can
  log in
- A2.5 Quitting Calimocho.app cleans up all spawned Wine processes within
  10 s of quit
- A2.6 The app does not require Whisky.app to be installed (uninstall
  Whisky on the test machine and confirm Calimocho still works)

### Deliverables

- `app/Calimocho.xcodeproj` (SwiftUI project)
- `app/Calimocho/MenuBarController.swift`
- `app/Calimocho/FirstRunWizardWindow.swift`
- `app/Calimocho/EngineLauncher.swift` (spawns wine binary, manages
  WINEPREFIX, redirects stdout/stderr to log files)
- `app/Calimocho/BottleManager.swift`
- `scripts/build-app.sh` (builds Calimocho.app, embeds out/engine,
  ad-hoc signs)
- Updated `docs/build-log.md` with Phase 2 retrospective

### Out of scope for Phase 2

- DMG (Phase 4)
- CI (Phase 5)
- SN2 (Phase 3)
- Sparkle auto-update (Phase 5)
- Settings UI beyond About box (Phase 5 polish)

## Phase 3: Game

### Acceptance criteria

See SPECS.md section A3.

Summary:
- A3.1 Subnautica 2 finishes downloading (15 GB) inside Calimocho's Steam
- A3.2 SN2 reaches main menu within 60 s of clicking Play
- A3.3 D3DMetal is confirmed active (not wined3d fallback)
- A3.4 Gameplay sustains at least 30 FPS at 1080p Medium for 30
  consecutive minutes on M1 Max
- A3.5 Save data persists across game restarts and across Calimocho.app
  restarts
- A3.6 UE4SS + Console Commands mod installed; Ctrl+F2 opens console
  in-game; `god` command works
- A3.7 The maintainer plays a full 30+ minute session with their son
  without a Wine-side crash

### Deliverables

- `bottles/sn2/config.json` (bottle config: Win 10 or 8.1, ESync,
  D3DMetal on, DXVK off, AVX on, xinput1_3 DLL override)
- `scripts/install-sn2-mods.sh` (UE4SS + Console Commands installer,
  same recipe we used for CrossOver in May)
- `scripts/migrate-sn2-from-crossover.sh` (optional one-off: if
  Subnautica2 is installed in a CrossOver bottle, rsync the 15 GB into
  Calimocho's bottle to skip re-download)
- Updated `docs/games-i-miss-on-my-mac.md` with SN2 status "Working"
  and the date tested

### Out of scope for Phase 3

- Hogwarts, Green Hell, They Are Billions stay on Wishlist
- Anti-cheat games (never in scope)
- Native Mac games (those run natively, not our problem)

## Phase 4: Packaging

### Acceptance criteria

See SPECS.md section A4.

Summary:
- A4.1 `scripts/build-dmg.sh` produces `Calimocho-vX.Y.Z.dmg`
- A4.2 DMG passes `hdiutil verify`
- A4.3 DMG mounts on macOS 15 and 26 (last two macOS versions)
- A4.4 Calimocho.app inside the DMG is ad-hoc signed
  (`codesign --verify` exits 0)
- A4.5 A clean M-series Mac that has never had Calimocho installed:
  download DMG → drag to /Applications → right-click → Open → wizard →
  Steam → SN2. All steps complete in under 10 minutes (excluding the
  SN2 game download).
- A4.6 Uninstall via app menu cleans up all files. No orphan processes.

### Deliverables

- `scripts/build-dmg.sh` (uses `create-dmg` or `hdiutil create`)
- `dmg-assets/` (background image, layout config)
- README updated with v1.0 install flow + screenshots
- First version of `tests/manual/release-checklist.md`

### Out of scope for Phase 4

- Apple notarization (never; we are ad-hoc only)
- App Store distribution (impossible; Wine ships a JIT)
- CI builds (Phase 5)
- Auto-update (Phase 5)

## Phase 5: CI + auto-update

### Acceptance criteria

See SPECS.md section A5.

Summary:
- A5.1 `.github/workflows/build.yml` runs on every push to main and PR
- A5.2 build.yml passes Tier 0-3 tests (TESTING.md), produces a DMG as
  workflow artifact
- A5.3 `.github/workflows/release.yml` runs on every tag matching `v*`,
  creates GitHub Release with DMG + sha256 + cosign signature
- A5.4 `.github/workflows/test-matrix.yml` runs weekly on macos-15 and
  macos-26
- A5.5 Sparkle integration in Calimocho.app polls a public appcast.xml,
  detects new version, downloads + verifies EdDSA + replaces app
- A5.6 An old version of Calimocho.app self-updates to a new version
  end-to-end without manual intervention
- A5.7 Build is reproducible: same git ref + same SOURCE_DATE_EPOCH
  produces identical sha256

### Deliverables

- `.github/workflows/build.yml`
- `.github/workflows/release.yml`
- `.github/workflows/test-matrix.yml`
- `.github/workflows/lint.yml`
- `appcast.xml` (published to raw.githubusercontent.com URL)
- `scripts/sign-with-sigstore.sh`
- `scripts/sparkle-eddsa-sign.sh`
- `tests/visual/baseline/` (committed baseline screenshots for Steam UI,
  Notepad window, SN2 main menu)
- `tests/visual/baseline-bottle.tar.zst` (pre-populated bottle for
  visual regression tests, sha256-pinned)

### Out of scope for Phase 5

- Game-launch tests in CI (would need GPU; we use self-hosted M1 Max
  for weekly Tier 4 instead)
- Performance benchmarks (Phase 6+)
- Telemetry, analytics, crash reporting (never; AGENTS.md rule #6)

## Phase 6+: Wishlist games

### Acceptance criteria

Same as A3.1 to A3.7 but for the specific game being tested.

### Deliverables

Per game:
- `bottles/<game-id>/config.json`
- `scripts/install-<game>-mods.sh` if needed
- Update `docs/games-i-miss-on-my-mac.md` with the new row

### Trigger

The maintainer personally wants to play the game. There is no community
process for adding games.

### Out of scope

- Games requiring kernel anti-cheat
- Games already native on Mac
- Games the maintainer does not personally want to play

## Phase ∞: Archive

### Trigger

Unknown Worlds Entertainment ships a native macOS build of Subnautica 2.

### Action

1. Update README: point users at the native Mac build of SN2, thank
   them for their patience.
2. Add a final ADR (e.g. ADR-9999-sunset.md) recording the date and
   reason.
3. Tag a final release v1.x.0-sunset that still works for users who
   want to keep playing on the old recipe.
4. Set the repo to read-only (Settings → General → Archive this
   repository).
5. Thank everyone in the README's final commit: Wine project,
   CodeWeavers, gcenx, Whisky, Apple, KhronosGroup, Unknown Worlds,
   every contributor and tester.

If SN2 never gets a native build and the maintainer stops playing SN2
for any reason, same procedure but trigger is different.

## Cross-phase invariants

- Every phase commit ends with all of:
  - The relevant SPECS.md acceptance criteria green (manual or CI)
  - The `docs/build-log.md` updated with what was learned
  - A `git tag` for the phase if it produced a user-installable artifact
- Phase order is strict; do not skip ahead
- Within a phase: ship the minimum that meets acceptance, then move on
- No new strategic decisions without an ADR
- No commits that violate AGENTS.md rules

## Phase status snapshot

| Phase | Status | Started | Acceptance green |
|---|---|---|---|
| 0 Foundation | DONE | 2026-05-30 | 2026-05-31 |
| 1 Engine | DONE | 2026-05-31 | 2026-06-01 (A1.1, A1.2, A1.3, A1.5, A1.6 green; A1.4 deferred to Phase 2/3 — needs Steam-installed bottle) |
| 1.5 CI + GPTK re-hosting | IN PROGRESS | 2026-06-01 | A1.5.1–A1.5.6 green locally; A1.5.7 pending first green CI run on phase1-engine PR |
| 2 App shell | NOT STARTED | — | — |
| 3 Game | NOT STARTED | — | — |
| 4 Packaging | NOT STARTED | — | — |
| 5 CI + auto-update | scope narrowed → release.yml + Sparkle + visual regression + multi-OS matrix | — | — |
| 6+ Wishlist | NOT STARTED | — | — |
| ∞ Archive | not triggered | — | — |

Update this table as phases advance.
