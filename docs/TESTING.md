# calimocho TESTING

> How we know each phase works, and how we keep it working as Wine,
> Apple GPTK, Steam, and macOS evolve.
>
> Companion to SPECS.md (the contracts being tested).

## Five tiers

| Tier | Scope | Where it runs | When |
| --- | --- | --- | --- |
| 0 | Lint and structural sanity | Locally + every PR | Every push |
| 1 | Engine smoke (wine --version, wineboot, prefix init) | macos-15 arm runner | Every PR |
| 2 | Application smoke (notepad.exe, basic window) | macos-15 arm runner | Every PR |
| 3 | Steam UI visual regression | macos-15 arm runner | Every PR |
| 4 | Game launch (SN2 reaches main menu) | maintainer's M1 Max + weekly cron | Weekly cron + before each release |

Plus a manual checklist for every release (the human ritual that catches
weird stuff CI does not).

## Tier 0: Lint

Runs on every push, in under 30 seconds.

```yaml
# .github/workflows/lint.yml (excerpt)
- shellcheck: all *.sh under scripts/ and bin/
- actionlint: all .github/workflows/*.yml
- markdownlint: README.md, docs/**/*.md (with config in
  .markdownlint.yaml; relaxed rules for the long PLAN.md and PHASES.md)
- yamllint: any .yml file
```

Fails the PR if anything is dirty. Easy to fix. Catches typos in scripts
and broken workflow syntax.

## Tier 1: Engine smoke

After build, before any UI test. Runs in CI right after Wine compiles.

```bash
# tests/smoke/01-wine-version.sh
out/Engine/bin/wine --version | grep -q '^wine-11\.0' || exit 1

# tests/smoke/02-wineboot.sh
export WINEPREFIX=$(mktemp -d)
out/Engine/bin/wine wineboot --init
grep -q 'wineVersion.*11' "$WINEPREFIX/system.reg" || exit 1
out/Engine/bin/wine wineboot --shutdown

# tests/smoke/03-prefix-clean-shutdown.sh
# verify no zombie wineserver / winedevice after shutdown
pgrep -lf wineserver | head | grep -v "$WINEPREFIX" || exit 1
```

If any of these fail, the build is broken at a fundamental level. CI
fails red, the PR is blocked.

## Tier 2: Application smoke

Spawn a real Windows binary, verify it created a visible window.

```bash
# tests/smoke/04-notepad-window.sh
export WINEPREFIX=$(mktemp -d)
out/Engine/bin/wine wineboot --init
out/Engine/bin/wine notepad.exe &
WINE_PID=$!
sleep 10
screencapture -x /tmp/notepad-test.png
# verify a window-frame-like rectangle is present using ImageMagick
magick compare -metric AE /tmp/notepad-test.png \
  tests/visual/baseline/notepad-frame.png /tmp/diff.png
DIFF=$(magick identify -format '%@' /tmp/diff.png | cut -d+ -f2)
if (( DIFF > 5000 )); then echo "notepad window not detected"; exit 1; fi
kill -TERM $WINE_PID 2>/dev/null
out/Engine/bin/wine wineboot --shutdown
```

This catches situations where Wine compiles but rendering is broken (the
black-window problem we saw with upstream Wine 11 staging).

## Tier 3: Steam UI visual regression

This is the test that gates Phase 1 completion.

```bash
# tests/smoke/05-steam-login-window.sh
export WINEPREFIX=~/test-bottles/steam-ci
# bottle is pre-populated with a logged-out Steam install, refreshed
# manually from time to time
out/Engine/bin/wine "C:\\Program Files (x86)\\Steam\\steam.exe" \
  -cef-disable-gpu -no-cef-sandbox &
WINE_PID=$!
sleep 45
screencapture -x /tmp/steam-test.png
# region match the login window (top 800px, center 600px)
magick convert /tmp/steam-test.png -crop 600x800+700+200 /tmp/steam-cropped.png
magick compare -metric NCC /tmp/steam-cropped.png \
  tests/visual/baseline/steam-login.png NULL: 2>&1 | \
  awk '{ if ($1 < 0.85) exit 1 }'
kill -TERM $WINE_PID 2>/dev/null
sleep 5
pkill -9 -f wineserver
```

Baseline `tests/visual/baseline/steam-login.png` captured manually once
on a known-good calimocho build. Re-captured manually when Valve
significantly changes the Steam login screen (every ~6 months in our
experience).

NCC (Normalized Cross-Correlation) of 0.85 means "the test image is
85% correlated to the baseline". Allows for anti-aliasing variance,
timestamp pixels, etc.

A black window scores ~0.1 NCC versus the baseline. So this test is the
canary for the bug we already know about.

### Steam account for CI

A dedicated free Steam account `calimocho-ci@` exists with no purchased
games. Its credentials are stored as GitHub Actions secrets. The
pre-populated bottle is built once per quarter and stored in
`tests/visual/baseline-bottle/` as a tar.zst (~200 MB).

We do NOT log in during CI tests. The bottle is in the logged-out state
on purpose; we only test that the login window renders. Anything beyond
that would require live Steam credentials in CI, which is a security
risk and probably also a Steam ToS issue.

## Tier 4: Game launch

Weekly cron + manual before each release. Cannot run on GitHub-hosted
runners (no GPU; SN2 needs Metal). Runs on the maintainer's M1 Max as a
self-hosted runner, in a quiet hour (3 AM local).

```bash
# tests/games/01-sn2-main-menu.sh
# Assumes SN2 is already installed in the test bottle.
export WINEPREFIX=~/test-bottles/steam-with-sn2
out/Engine/bin/wine "C:\\Program Files (x86)\\Steam\\steam.exe" \
  -applaunch 2864380 &
WINE_PID=$!
# Wait for SN2 main menu to render. Take a screenshot every 10s for
# 2 minutes, comparing against baseline.
for i in $(seq 1 12); do
  sleep 10
  screencapture -x /tmp/sn2-$i.png
  if magick compare -metric NCC /tmp/sn2-$i.png \
       tests/visual/baseline/sn2-main-menu.png NULL: 2>&1 | \
       awk '{ exit $1 < 0.80 ? 1 : 0 }'; then
    echo "SN2 main menu detected at iteration $i ($(( i * 10 ))s)"
    pkill -TERM Subnautica2
    sleep 30  # let game shut down cleanly so steam logs aren't corrupted
    pkill -9 -f wineserver
    exit 0
  fi
done
pkill -9 -f Subnautica2
pkill -9 -f wineserver
exit 1
```

Reports go to a GitHub Issue auto-created/updated by the workflow titled
"Tier 4 test results — week of YYYY-MM-DD".

### What Tier 4 does NOT test

- Sustained framerate (manual; subjective)
- Multiplayer (anti-cheat risk to our CI account)
- Saving and loading (would require deterministic Steam Cloud state)
- Any game other than SN2 (not in scope per ADR-0006)

Those are manual-only.

## Manual checklist (every release)

Lives in `tests/manual/release-checklist.md`. Updated at the start of
each release branch.

```markdown
- [ ] Tier 0-4 all green
- [ ] DMG mounts cleanly
- [ ] App icon appears (not the generic placeholder)
- [ ] First-run wizard appears on a fresh machine (test in a fresh VM or
      a Mac that's never had Calimocho)
- [ ] Steam installs via wizard
- [ ] Can sign in to a real Steam account
- [ ] Subnautica 2 launches and plays for 10 min without crashing
- [ ] Sparkle update simulator works (open prior version, point appcast
      at this version, verify update flow)
- [ ] Uninstall via menu works (full and partial paths both clean)
- [ ] No leftover processes after uninstall
- [ ] No leftover files under /Applications/ after uninstall
- [ ] README install steps still match reality
- [ ] CHANGELOG.md updated
- [ ] Version bumped in Info.plist and bin/calimocho
- [ ] git tag matches the release version
- [ ] Sigstore signature present on every release artifact
- [ ] At least one stranger (friend who is not on this project) can
      install from the README in under 10 minutes
```

If any unchecked item blocks the release, fix it and re-test before
publishing.

## CI matrix

```yaml
# .github/workflows/test-matrix.yml (excerpt)
strategy:
  matrix:
    os: [macos-15, macos-26]   # known supported macOS versions
    arch: [arm64]              # we don't support Intel; documented
include:
  - os: macos-26
    flag: --enable-experimental-features
    allow-failure: true        # next macOS may break; investigate, do
                               # not block release
```

Runs Tier 0-3 on each matrix entry. Tier 4 stays self-hosted.

## Test data versioning

- Baseline screenshots versioned under `tests/visual/baseline/`
  with sha256 manifest in `tests/visual/baselines.txt`
- When a baseline is updated, the manifest commit must include the
  reason (Valve changed Steam UI, etc.)
- Pre-populated bottle tarballs stored under
  `tests/visual/baseline-bottle/` (also sha256-pinned, also in manifest)
- All baselines refreshed manually by the maintainer; no auto-update

## Test budget

- Tier 0: 30s per run, costs zero CI minutes (free tier)
- Tier 1: 1 min per run
- Tier 2: 3 min per run
- Tier 3: 6 min per run
- Tiers 0-3 together per PR: about 10 minutes of GitHub-hosted arm64
- Tier 4: 5 min per run, runs weekly only
- Monthly budget for our setup: about 200 minutes/month, well within
  the maintainer's generous GitHub plan

If we exceed budget for any reason, we drop Tier 3 visual regression to
weekly. We never drop Tier 0-2.

## Test failure handling

| Tier failing | Severity | Response |
| --- | --- | --- |
| 0 | Block PR | Fix in same PR |
| 1 | Block PR | Build issue; fix in same PR or revert offending change |
| 2 | Block PR | Investigate; may indicate Wine regression. File against `tests/known-flaky.md` if it passes on retry |
| 3 | Block PR | Steam UI is the make-or-break thing. PR cannot merge. Look at the diff image as artifact and decide what changed |
| 4 | Open auto-issue | Investigate within a week. If it's a CrossOver-upstream regression, document and move on. If it's our regression, fix before next release |
| Manual checklist | Block release | Fix or document as known issue in release notes |

## Things we explicitly do not test (yet)

- Performance benchmarks (Phase 6+, not v1.0)
- Memory leak detection (TODO if a leak is reported by users)
- macOS versions newer than the matrix entries (added when GitHub Actions runners exist)
- Intel Macs (out of scope; documented in README)
- Anti-cheat games (out of scope per AGENTS.md rule #5)
- Multi-bottle setups (we ship exactly one bottle: STEAM)
- Network-isolated environments (Steam requires the internet anyway)
