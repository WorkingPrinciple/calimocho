# AGENTS.md — Operating rules for calimocho contributors

> Read this before changing anything. Applies to humans and AI agents.
> If a rule conflicts with what feels expedient, the rule wins.

## North star

calimocho exists to let the maintainer (and people in the same situation) run
Windows-only games they miss, on their Apple Silicon Mac, **without paying for
CrossOver**. The project is a stopgap until Unknown Worlds ships a native Mac
build of Subnautica 2.

Everything below serves that north star. If something doesn't, drop it.

---

## Hard rules (never break)

### 1. We compile from source. We never ship someone else's binary.
- ✅ Build Wine 11 from WineHQ's or CodeWeavers' published LGPL source
  tarball (the 11.20 engine release uses WineHQ's tarball plus patches
  derived from CodeWeavers' LGPL source)
- ✅ Build vkd3d / DXVK / MoltenVK from source if we ship them
- ❌ Do NOT copy CrossOver's pre-built binaries from
  `/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/`
  into calimocho, ever, even for "just a quick test"
- ❌ Do NOT copy Whisky's bundled Wine 7.7 binaries either
- ✅ EXCEPTION: Apple's GPTK D3DMetal.framework is a binary we redistribute
  per Apple's explicit GPTK SLA permission (§2A iii + §2C, non-commercial).
  That is the one binary we ship unmodified.

**Why this rule exists**: CrossOver's EULA does not grant redistribution
rights for their compiled binaries. CodeWeavers' source is LGPL and freely
buildable. The whole legal premise of calimocho is "build from source you're
allowed to build". Touching their .dylib files violates that premise and
puts us in EULA grey area.

### 2. We are non-commercial. Forever.
- ❌ No paid tier
- ❌ No paid support contracts
- ❌ No paid SaaS or hosted-gaming offering
- ❌ No reselling the project as part of a paid product
- ❌ No bundling in any paid app
- ✅ GitHub Sponsors / Patreon donations to maintain the project are fine
  (FOSS convention), but we point them at WineHQ and CrossOver instead
- ✅ Free for any non-commercial use including community redistribution

**Permitted uses (positive list, for unambiguous user guidance)**:
personal use, family use, free community redistribution, donating to
upstream projects on calimocho's behalf, education, research,
hobbyist tinkering.

**Prohibited uses (the line not to cross)**: selling the binaries,
charging for support, including calimocho in any paid product or
service (cloud gaming, hosted bottles, managed-gaming-as-a-service),
sublicensing for commercial use.

**Why this rule exists**: Apple's GPTK license requires non-commercial.
Going commercial would also actively undercut CodeWeavers and break the
positioning everything else is built on.

### 3. We respect upstream.

This project stands on the unpaid (or differently-paid) work of
specific people and teams. Every release credits all of them, by name,
in README, release notes, About box, CLI banner, and the `THIRDPARTY/`
tree:

- **The Wine project** (winehq.org) — 30 years of reverse engineering
  the Windows API.
- **CodeWeavers** (codeweavers.com/crossover) — most of the upstream
  Wine work that benefits macOS; publishes LGPL source we build from.
- **Apple Game Porting Toolkit team** — ships `D3DMetal.framework` as
  a non-commercially redistributable component (GPTK SLA §2A iii +
  §2C).
- **gcenx** (github.com/Gcenx) — the single volunteer who maintains
  the macOS Wine packaging ecosystem (`macOS_Wine_builds`,
  `game-porting-toolkit`). Without his work, none of the free macOS
  Wine stack ships.
- **KhronosGroup / MoltenVK** — Apache 2.0 Vulkan-to-Metal
  translator bundled with GPTK.
- **Isaac Marovitz and the Whisky community** — archived in May 2025,
  but proved that a friendly SwiftUI front-end to Wine on macOS is
  possible. Credited as inspiration, **never as a runtime dependency**
  (see ADR-0008).
- **Unknown Worlds Entertainment** — shipped native Mac builds of
  Subnautica (2018) and Below Zero (2021). The reason this project
  exists and the reason it will archive.

Operational rules:

- Donation links in README and About box go to WineHQ and CrossOver,
  **never to calimocho itself**.
- If gcenx or CodeWeavers asks us to change something, we comply
  within days.
- If Whisky comes back to active development, we point users there
  and reposition (or archive).
- Each major upstream gets a `docs/relationship-with-<upstream>.md`
  or an ADR recording how we'd respond if they asked us to change or
  stop. We currently have `relationship-with-codeweavers.md`. The
  others get written before any release that would bring meaningful
  traffic.

### 4. We are visibly worse than CrossOver, on purpose.
- No support channel
- No per-game compatibility profiles
- No anti-cheat workarounds
- No notarization
- No day-of game patches
- No fancy native UI polish
- Anyone who needs those things should buy CrossOver, and we say so loudly
  in the README's decision table.

**Why this rule exists**: Free alternatives to paid products are an
ecosystem hazard. We minimize harm by being honestly less polished, so
the only users who pick us are those who would not have paid anyway.

**Concrete anti-undercut levers** (these are commitments, not
aspirations — verifiable per release):

1. **Be visibly worse on purpose, by honesty.** README's decision
   table answers "buy CrossOver" for most rows.
2. **Pre-purchase funnel.** README mentions CrossOver before it
   mentions any install step. The first-run wizard's Welcome screen
   mentions CrossOver before any feature.
3. **Co-promotion in release notes.** Every GitHub Release tagline
   includes a line about supporting CodeWeavers.
4. **Donate up the chain.** README's only donate links go to WineHQ
   and CrossOver. No calimocho donations accepted.
5. **Intentional release lag.** Wait 1–2 weeks after each CrossOver
   release before publishing our matching rebuild. Paying users
   always get the fresh bits first.
6. **No commercial features ever.** No Pro tier. No SaaS. No paid
   Discord. License-required and ethics-required (see rule #2).
7. **Active referral on hard cases.** Every error dialog that
   recommends a fallback includes a "Try CrossOver" button pointing
   at the CrossOver 14-day trial. Every error message in the CLI's
   `Docs:` field links to troubleshooting that mentions CrossOver as
   the supported alternative.
8. **Public non-competition statement.**
   `docs/relationship-with-codeweavers.md` exists so CodeWeavers
   staff Googling us see the honest position.

**Positioning language**: never describe calimocho as a "free
CrossOver alternative". Frame as "Whisky's missing engine update" or
"a recipe for the one game I miss on my Mac". That smaller, more
honest niche is the only one we serve.

**We follow when a FOSS path exists. We lead only when the only
alternative is a paid product, and only as narrowly as needed to
remove that gating.** We ship nothing on the Wine engine layer
that CodeWeavers hasn't shipped first when there is an
already-working FOSS option. If a Wine patch lands upstream but
isn't yet in a CrossOver release, we wait (intentional release
lag, lever 5). But when there is **no** FOSS implementation of a
piece calimocho's users need and the only working answer is a paid
product, we are allowed to write the smallest possible new code
that unblocks the FOSS path, subject to the guardrails in
[ADR-0017](../docs/ADR/0017-follow-when-foss-exists-lead-when-only-paid-exists.md).

### 5. We are SN2-scoped.
- Subnautica 2 is the only "Working" entry in the compat table.
- Other games may appear as "Wishlist" if the maintainer personally wants
  to play them.
- We do not accept "please add support for X" feature requests.
- We do not promise any game keeps working across calimocho releases except
  SN2.
- **Anti-cheat games (kernel anti-cheat, EAC, BattlEye, etc.) are out of
  scope forever.** Not a Wine limitation we'll work around; a deliberate
  scope boundary.
- The project archives when Unknown Worlds ships a native Mac build of SN2.

### 6. We are silent.
- No HackerNews post, no Reddit thread, no blog
- No social media presence beyond the GitHub repo itself
- No promotion of any kind
- Growth is purely organic, by word of mouth or chance
- If someone writes about us externally, we respond politely but do not
  amplify
- **No SEO play.** Do not optimize for queries CrossOver competes for
  ("free CrossOver", "play Windows games Mac", "DX12 Mac"). The README
  is a destination for people who already know what they're looking
  for, not a funnel.
- **No posting in r/macgaming, r/wine_gaming, or any forum CrossOver
  staff frequent.** If a user posts about calimocho there, we don't
  participate in the thread.
- **Bug routing** — only calimocho-specific bugs come to this repo.
  - Wine engine bugs → [winehq.org](https://www.winehq.org/) bugzilla
  - GPTK / D3DMetal bugs → Apple Feedback Assistant
  - Game bugs (SN2 crashes, mod issues) → the game publisher
  - Steam client bugs → Valve
  - macOS bugs → Apple
  The README and the issue template enforce this routing.

### 7. We test before we ship.
- Phase acceptance criteria (`A0.x` through `A5.x`) live in
  [docs/SPECS.md](docs/SPECS.md) and are the only definition of "done".
- A phase does not ship until all of its `A(N).x` criteria are green.
- No release without the relevant phase acceptance evidence captured
  in `docs/build-log.md`.
- Visual regression tests (Tier 3 in [docs/TESTING.md](docs/TESTING.md))
  use ImageMagick NCC ≥ 0.85 against committed baselines — the
  canary for the Steam black-window class of bug.

### 8. We sign releases with the maintainer's Developer ID.
- Changed by the owner on 2026-10-25 (REQ-115): the old "ad-hoc only"
  rule existed because a Developer ID was not in budget. The maintainer
  now has one. See
  [ADR-0078](docs/ADR/0078-developer-id-signed-engine-release.md).
- Release Mach-O files are signed with exactly
  "Developer ID Application: Dragos Hont (M62Z4M5EUY)", inside-out, one
  file at a time:
  `codesign --force --sign <identity> --options runtime --timestamp`.
  Never `--deep`. Each executable gets only the entitlements pinned in
  `versions.json` (today: the Wine loader gets `disable-library-validation`,
  nothing else; see docs/ADR/0080-minimal-engine-entitlements.md).
- Apple's D3DMetal components keep Apple's own signature. We never
  re-sign or modify them (GPTK licence section 2D).
- Notarization and public release uploads are separate owner decisions.
  Until then, the signed archive stays a local artifact.
- Never access, export or log signing key material.
- Ad-hoc signing (`--sign -`) is still fine for local development
  builds that never leave the machine.

---

## Project-specific paths and conventions

These are pointers, not duplications. The authoritative definitions
live where the agent will find them:

- **Engine source layout, bottle paths, log paths, CLI surface, exit
  codes, error template** — [docs/SPECS.md](docs/SPECS.md), "Cross-phase
  invariants" plus the per-phase "file layout" sections.
- **Four-layer architecture and data flows** —
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **6-phase plan and gates** — [docs/PHASES.md](docs/PHASES.md).
- **5-tier test strategy** — [docs/TESTING.md](docs/TESTING.md).
- **UX surface (menubar, wizard, error dialogs)** —
  [docs/ux/APP-DESIGN.md](docs/ux/APP-DESIGN.md).

Key invariants worth restating (because contributors keep tripping on
them):

- Bottle data lives under
  `~/Library/Application Support/Calimocho/Bottles/<NAME>/`. **Never**
  in `~/Library/Containers/com.isaacmarovitz.Whisky/` or anywhere
  Whisky-owned (see [ADR-0008](docs/ADR/0008-no-whisky-dependency.md)).
- Logs live under `~/Library/Logs/Calimocho/`. The app writes
  nowhere else.
- The shipped error template (CLI stderr + GUI dialogs) is fixed:
  ```text
  calimocho: ERROR <short title>
    Reason: <plain English, non-native-English-friendly>
    Fix:    <what to try>
    Docs:   https://github.com/dragoshont/calimocho/docs/troubleshooting.md
  ```
  GUI dialogs additionally include a "Try CrossOver" button on any
  error that recommends fallback (rule #4, lever 7).

**UX scope ceiling** (the GUI is deliberately tiny):

- One user-visible menubar action: "Open Steam for Windows".
- A first-run wizard that installs Steam (five steps; see
  [docs/ux/APP-DESIGN.md](docs/ux/APP-DESIGN.md)).
- Power-user actions (view logs, reset bottle, diagnose, reinstall
  engine) are hidden behind **Option-click** on the menubar item.
- **Never add**: a bottle picker, a Winetricks UI, a DLL override
  panel, a per-game launcher, a download manager, a settings
  inspector, a Wine version switcher. Users who need any of those
  should use CrossOver instead, and the menu's About box says so.

**Trademarks** — nominative fair use only. "CrossOver",
"CodeWeavers", "Apple", "macOS", "Apple Silicon", "Game Porting
Toolkit", "D3DMetal", "Wine", "Steam", "Subnautica" are referenced
for identification only. calimocho is not affiliated with, endorsed
by, or sponsored by any of these holders.

---

## Soft rules (break only with explicit, documented reason)

### Decisions are documented in ADRs
- Any decision that affects more than one file goes in `docs/ADR/NNNN-*.md`
- Use Michael Nygard's Context / Decision / Consequences format
- New ADRs do not require approval; reverse-ADRs do (write 0007 to revert 0003)

### Commit messages explain "why"
- Subject line is "what" (≤72 chars, present tense, no period)
- Body explains "why" in plain English (no em dashes)
- Reference the ADR or PHASE doc that motivated the change
- Co-authored-by trailers when work was done with an AI agent

### Documentation is in plain English
- Aimed at non-native English speakers
- No em dashes (use "—" alternatives: parentheses, colons, or just shorter
  sentences)
- No jargon without explanation
- ASCII art diagrams are fine; complicated graphics are not

### Phase order is strict
- Phase 1 must complete before Phase 2 starts
- Phase 2 must complete before Phase 3 starts
- Do not gold-plate within a phase; ship and iterate

### Build deps are pinned
- Brewfile.lock.json is committed
- Wine source is fetched from a specific CodeWeavers release URL with sha256
- GPTK is downloaded from a pinned gcenx release with sha256
- No "latest" anywhere in CI

### Failure is OK; silent failure is not
- If something doesn't work, document why in `docs/build-log.md`
- If a path is abandoned, write a brief reverse-ADR explaining
- "It didn't work and we moved on" is acceptable history; "we hid the
  evidence" is not

---

## Rules of engagement for AI agents

If you are an AI agent reading this to help with the project:

- You may not bypass any rule above
- You may suggest rule changes only by proposing a new ADR
- If asked to do something that violates a rule, push back politely once,
  then refuse if the user insists. The user can still override by editing
  this file and explaining why
- Prefer fewer, larger, well-documented commits over many tiny ones
- Always run `git status` before committing to catch surprise changes
- Always check `docs/PHASES.md` before starting work to make sure the
  current phase scope matches the task
- Update the todo list when scope shifts mid-session
- When in doubt, write a question to the user rather than guessing

### Pre-PR self-review checklist (recurring mistake catcher)

These rules exist because past PRs surfaced the same classes of bug
again and again in CodeRabbit / Copilot bot review. Run this checklist
mentally before every `gh pr create` or `git push` that opens a PR.

**macOS shell scripts** (every `.sh` we ship):

- macOS ships **bash 3.2**. No associative arrays (`declare -A`), no
  `${var,,}` lowercase, no `mapfile` / `readarray`. Use `case`
  statements and `while read` loops. The CI runner has bash 5, the
  maintainer's Mac does not — the local run is the one that breaks.
- `set -euo pipefail` at the top of every script. Empty/unset
  variable references should fail loud, not silently expand to "".
- Any pipeline that produces a build artifact: verify with
  `[[ -s "$out" ]]` *after* the pipeline. `pipefail` catches process
  exit codes but a disk-full `tar | zstd` can still emit a zero-byte
  file with exit 0.
- `rsync --delete <src>/ <dst>/` will wipe anything in `<dst>/` not in
  `<src>/`. If `<dst>/` is shared with another stage (overlay, sign,
  bundle), add `--exclude=<that-subtree>` and **leave a code comment
  explaining why**.
- Never `pkill -f <pattern>` to clean up. It will SIGKILL processes
  belonging to other Wine instances the user has running. Use
  `wineserver -k` against the specific `$WINEPREFIX` instead.
- `awk` injection / substitution scripts must set a sentinel and exit
  non-zero from `END` if the sentinel was never tripped. Otherwise a
  silent no-op pretends to succeed and the log line lies.
- When parsing `diff -u` output, `+++ b/<path>` headers commonly carry
  a trailing tab + timestamp. Trim with
  `path="${path%%$'\t'*}"` before using.

**macOS dyld / Mach-O** (anything we ship as `.dylib` or `.framework`):

- Every dylib bundled into `out/engine/` must be audited with
  `otool -L` and must have **zero** `/usr/local/...` references.
  Rewrite via `install_name_tool -id @rpath/<base>` +
  `install_name_tool -change /usr/local/... @loader_path/<base>`.
  Verify with a post-rewrite `otool -L | grep /usr/local` that fails
  the script if any leak remains.
- `install_name_tool` invalidates signatures. Sequence is
  always: build → bundle/overlay → install_name_tool → sign. Never
  the other way around.
- Don't rely on `DYLD_FALLBACK_LIBRARY_PATH` basename-fallback as the
  *only* resolution strategy. Apple has narrowed dyld policy several
  times. Bundle should resolve via `@loader_path` for inter-bundle
  refs; env-var fallback is only for Wine's own `dlopen`-by-SONAME.
- Release signing is `tools/release_engine.py sign` (rule 8): Developer
  ID, hardened runtime, secure timestamp, inside-out, no `--deep`, plus
  the Wine entitlements (JIT, dyld env, lib-validation disabled) on
  executables. Re-run it after any post-build mutation.

**Spec-traceability** (every test we write):

- Test for `A(N).x` MUST quote the criterion verbatim in a comment
  above the assertion. If `A1.2` says "system.reg contains
  `#arch=win64`", the test reads
  `grep -Fq '#arch=win64' "$PFX/system.reg"` and the comment above
  cites `# SPECS A1.2: prefix is win64 (system.reg has #arch=win64)`.
  No "substring of one of these patterns" looseness. If you cannot
  write a tight assertion, the test is not yet implementable — mark
  it SKIP with the deferred-phase reason.
- "Process is alive 6 seconds later" is **not** evidence of UI
  rendering. Headless / black-window failures pass that. Either do a
  real screenshot+NCC assertion or mark the criterion SKIP.
- Missing comparison corpus (`A1.5` without CrossOver installed) is
  SKIP, not PASS. Use a distinct exit code from the inner script and
  let the caller print SKIP.

**Provenance & supply chain**:

- Every external file we ingest must be sha256-pinned in
  `versions.json` and verified at fetch time. The one exception is
  the Apple GPTK DMG, which is gated behind Apple ID login —
  document that exception explicitly each time it comes up.
- GitHub Actions: `actions/checkout@v4` needs `persist-credentials:
  false` when the workflow doesn't push. Pinning actions to commit
  SHAs is deferred to Phase 5's supply-chain hardening pass; track
  it there, not piecemeal.
- Any new external URL referenced in code or docs must be hit at
  least once before the commit to confirm it 200s.

**Docs**:

- Every fenced code block has a language tag (`bash`, `text`, `json`,
  ...). markdownlint MD040 fails the lint workflow without it.
- No broken links. If a referenced file doesn't exist yet, either
  create a placeholder or remove the markdown link syntax (plain text
  is fine).
- ADR file names: `NNNN-kebab-title.md`, monotonic. When superseding
  an ADR, **delete the old file** and reference the topic in the new
  one's `Context` — never leave "Superseded by …" stubs.

**Before you push the PR**:

1. `shellcheck scripts/*.sh` — must be clean (Phase 1.5 lint workflow
   enforces this on push).
2. `markdownlint docs/**/*.md` — same.
3. `git diff --stat` reviewed — no unrelated changes snuck in.
4. Every claim in the PR description traces to a commit, ADR, or
   acceptance criterion. No prose-only assertions.
5. If the PR touches anything in the bullet lists above, name the
   bullet you complied with in the commit message body. Makes
   bot-review delta visible.

---

## How to add a new rule

1. Open an issue or just a draft ADR
2. Wait for the maintainer to think about it (24+ hours, not chat-speed)
3. Write the ADR
4. Add the rule here once accepted

## How to remove a rule

Same process. Write a reverse-ADR explaining why the rule no longer fits
the north star.
