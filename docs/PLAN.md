# calimocho — Product & Engineering Plan

> Strategic document. For tactical details see:
>
> - [PHASES.md](PHASES.md) — the 6-phase delivery plan
> - [SPECS.md](SPECS.md) — per-phase acceptance criteria (A0-A5)
> - [ARCHITECTURE.md](ARCHITECTURE.md) — 4-layer technical design
> - [TESTING.md](TESTING.md) — 5-tier test strategy
> - [ux/USER-JOURNEY.md](ux/USER-JOURNEY.md) — Day 1 / Day 2 / update flows
> - [ux/APP-DESIGN.md](ux/APP-DESIGN.md) — Calimocho.app UX
> - [ADR/](ADR/) — individual architectural decisions, Nygard format
> - [AGENTS.md](../AGENTS.md) — rules of engagement
> - [LICENSE](../LICENSE) + [relationship-with-codeweavers.md](relationship-with-codeweavers.md)

## 1. Vision

**One sentence**: A personal recipe for running Windows games the
maintainer misses on their Mac (currently just Subnautica 2), built
from CodeWeavers' LGPL Wine source and Apple's redistributable GPTK
D3DMetal. A stopgap that archives itself once Unknown Worlds ships a
native macOS build of SN2.

**Three audiences**:

1. The maintainer's family, who wanted to play SN2 together on their Mac.
2. Other Mac users in the same situation (bought Subnautica 1 + Below
   Zero on Mac, can't run SN2, can't afford CrossOver).
3. Future-me and any contributor who wants to understand why this
   exists and how to keep it running until SN2 ships native.

**Non-goals**:

- Not a general Mac gaming platform. Compatibility is the maintainer's
  personal list, not a service.
- Not a CrossOver alternative for commercial use, polish, or support.
- Not a fork of Wine. A distribution layered on upstream + CW patches.
- Not building anything that outlives Unknown Worlds porting SN2 to Mac.

## 2. Architecture summary

Four layers, fully detailed in [ARCHITECTURE.md](ARCHITECTURE.md):

1. **Build pipeline** — CodeWeavers Wine 11 source + Apple GPTK 3 DMG,
   compiled on macOS arm64 via GitHub Actions.
2. **Runtime payload** — Wine 11 binary tree + D3DMetal.framework +
   MoltenVK, ad-hoc signed.
3. **Distribution** — Calimocho.app drag-installed (Phase 2+), DMG with
   Sigstore signature (Phase 4+), Sparkle auto-update (Phase 5+).
4. **Host GUI** — SwiftUI menubar app `Calimocho.app` from Phase 2.

## 3. Delivery model

Six phases, strict ordering, each independently shippable.

See [PHASES.md](PHASES.md) for full breakdown. Summary:

| Phase | Title | Trigger to start |
|---|---|---|
| 0 | Foundation | (done) |
| 1 | Engine | foundation acceptance green |
| 2 | App shell | A1.x green |
| 3 | Game (SN2) | A2.x green |
| 4 | Packaging (DMG) | A3.x green |
| 5 | CI + auto-update | A4.x green |
| 6+ | Wishlist games (optional) | A5.x green + maintainer interest |
| ∞ | Archive | Unknown Worlds ships native SN2 |

## 4. Signing & provenance

**Superseded on 2026-10-25.** Releases are now signed with the
maintainer's Developer ID, with hardened runtime and a secure timestamp.
See [ADR-0078](ADR/0078-developer-id-signed-engine-release.md) and
AGENTS.md rule 8. The original plan below is kept as history.

The original locked decision was ad-hoc signing only, because an Apple
Developer ID was out of budget and Azure Code Signing does not apply to
macOS.

- All Mach-O binaries inside the .app/DMG are ad-hoc signed via
  `codesign --force --deep --sign - --options runtime`.
- DMG is **not** Apple-notarized. README documents the right-click →
  Open Gatekeeper workaround.
- Every release artifact has a **Sigstore/cosign signature** generated
  by GitHub Actions OIDC, so security-minded users can verify
  provenance without trusting any PGP key.
- Sparkle's appcast is **EdDSA-signed** (Sparkle's own mechanism,
  independent of Apple's chain). This is sufficient for safe
  auto-update with ad-hoc-signed app bundles.

We do not ship to the App Store (Wine's JIT violates App Store rules)
and we do not maintain a notarization workflow.

## 5. Distribution channels

| Phase | Channel | Notes |
|---|---|---|
| 2+ | Drag .app from repo `out/` to /Applications | Developer/internal use |
| 4+ | GitHub Releases DMG | Primary user-facing distribution |
| 5+ | Sparkle auto-update from EdDSA-signed appcast | Default for installed users |
| 5+ optional | Own Homebrew tap `dragoshont/homebrew-calimocho` | Never PR to upstream homebrew-cask (would require notarization) |

## 6. Quality bars

Per-phase acceptance criteria are normative and live in
[SPECS.md](SPECS.md). A phase does not ship until all of its `A(N).x`
criteria are green.

Cross-phase invariants (testable, not aspirational):

- AGENTS.md rule #1: no file shipped is byte-identical to a CrossOver
  binary (verified at every build, A1.5).
- AGENTS.md rule #2: no paid features. Verified by manual review of
  every release.
- AGENTS.md rule #6: no telemetry. Verified by audit of network
  endpoints contacted by the shipped app.
- AGENTS.md rule #8: all binaries ad-hoc signed only.

If any hard-rule test fails, the release is blocked.

## 7. Risks & mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| CW changes their source license or withdraws publication | Very low | Catastrophic | Mirror tarballs in our own GH releases as evidence-of-state under fair use |
| Apple GPTK license changes | Low | Catastrophic for DX12 path | Document a Vulkan-only fallback (vkd3d-proton + DXVK + MoltenVK) in build-log; slower but works |
| Build breaks on next macOS version | Medium | Medium | macOS-version-matrixed weekly CI catches it before users see it |
| Steam keeps breaking with new CEF versions | Medium | Medium | Pin to a known-good CW source; document the upgrade dance |
| Anti-cheat games still won't work | Certain | Low (not in scope) | Document loudly in README that competitive multiplayer is out of scope |
| Cease-and-desist from someone | Very low | Medium | Squeaky LGPL; if it happens, comply + document |
| Burnout (solo maintainer) | High | High | Keep scope tight, accept community PRs early, never promise SLA |

## 8. Maintenance cadence

Roughly monthly. CodeWeavers ships ~1-2 source updates per month; we
rebuild on top. No SLA, best-effort, may pause for weeks if life
happens.

## 9. Ecosystem positioning

### License landscape (verified from actual EULAs, 2026-05-31)

| Component | License | Distribution permitted? |
|---|---|---|
| Wine 11.0 (upstream) | LGPL 2.1+ | ✅ Yes, any use including modification |
| CodeWeavers Wine patches | LGPL 2.1+ (CW's LGPL compliance source) | ✅ Yes, any use including modification |
| vkd3d / DXVK / MoltenVK | LGPL / zlib / Apache 2.0 | ✅ Yes |
| Apple GPTK 3.0 D3DMetal.framework | Apple GPTK SLA | ✅ Non-commercial distribution allowed per §2A(iii) + §2C |
| gcenx repacks | Pass-through | ✅ Exercising the underlying upstream rights |

**Key takeaway**: All components are legally redistributable for
non-commercial use. The hard constraint is the non-commercial clause
on Apple's GPTK — it forecloses any commercial product but does not
prevent free open-source distribution, GitHub Sponsors, or community
use.

**Why CrossOver can charge $74/yr and we can't**: CodeWeavers has a
private commercial agreement with Apple. The public GPTK license is
non-commercial only; CodeWeavers operates under a separate paper.

### Anti-undercut levers

We cannot fully avoid undercutting CrossOver — any free alternative
converts *some* potential buyers into non-buyers. We minimize harm
through eight concrete levers:

1. **Be visibly worse on purpose (by honesty, not sabotage).** README
   states we lack support, per-game profiles, anti-cheat,
   notarization, day-of patches, polish. Users who need those things
   self-select to CrossOver.
2. **Pre-purchase funnel.** README has a decision table; for most rows
   the answer is "buy CrossOver." calimocho is the answer only for
   narrow non-commercial cases.
3. **Co-promotion in release notes.** Every GH release tagline
   includes "if this saves you time, please support CodeWeavers."
4. **Donate up the chain.** README's only donate links go to WineHQ +
   CrossOver purchase page. No calimocho donations accepted.
5. **Intentional release lag.** Wait 1-2 weeks after each CrossOver
   release before publishing our rebuild. Paying users always get the
   fresh bits first.
6. **No commercial features ever.** No Pro tier. No SaaS. No paid
   Discord. License-required and ethics-required.
7. **Active referral on hard cases.** When something breaks in
   calimocho, our error dialog recommends the CrossOver 14-day trial
   before opening an issue with us.
8. **Public non-competition statement.** `relationship-with-codeweavers.md`
   exists so CodeWeavers staff Googling us see the honest position.

### Cross-linking obligations (LGPL + good manners)

Every release contains a `THIRDPARTY/` tree with attribution and
license text for: CodeWeavers, gcenx, Apple GPTK, upstream Wine,
MoltenVK. A `THIRDPARTY/README.md` explains who made what and where to
send money or thanks.

## 10. Visibility

**Silent project.** No active promotion. Exists on GitHub for anyone
who finds it. No HN post, no Reddit thread, no blog. If a community
forms organically, great; if not, also great. See AGENTS.md rule #6.
