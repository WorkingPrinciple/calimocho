# ADR-0002: Ad-hoc signing only, no Apple Developer ID

Status: Accepted
Date: 2026-05-31

## Context

Distributing a macOS app requires it to be signed. Three tiers of signing
exist on macOS:

| Tier | Cost | What user sees |
| --- | --- | --- |
| Ad-hoc (`codesign --sign -`) | Free | First launch shows "unidentified developer" dialog. Right-click → Open bypasses. |
| Apple Developer ID + notarization | $99/yr + automation effort | Clean launch, no warnings. |
| Apple App Store | $99/yr + review process | Cannot apply: Wine ships a JIT compiler, which App Store rules forbid. |

Azure Code Signing was checked and only covers Windows Authenticode, not
macOS Gatekeeper. There is no free path to an Apple-trusted certificate.

The maintainer cannot afford $99/yr.

## Decision

calimocho will use ad-hoc signing for all Mach-O binaries and DMG artifacts.

We will also produce a Sigstore/cosign signature per release using GitHub
Actions OIDC, for users who want to cryptographically verify the build
provenance. Sigstore signatures are checked by `cosign verify-blob`, not by
Gatekeeper.

Documentation in README explains the right-click → Open Gatekeeper bypass
clearly, with a screenshot in v0.5+ when we have a real GUI.

## Consequences

### Positive

- Zero recurring cost.
- Sigstore provides independent provenance verification for the paranoid.
- Sparkle auto-updater works fine with ad-hoc binaries when the appcast
  itself is EdDSA-signed (Sparkle's signature is independent of Apple's).

### Negative

- First-run friction for users. They must right-click → Open the .app
  the first time, instead of just double-clicking.
- We cannot publish to homebrew-cask upstream (that requires notarization).
  Our own tap is fine.
- Cannot ship via the Mac App Store (Wine JIT forbidden anyway).

### Neutral

- This matches the friction level of similar free projects
  (Whisky, Heroic Games Launcher historically, Wineskin).

## Related

- AGENTS.md rule #8 (ad-hoc signing only)
- docs/PHASES.md Phase 3 acceptance criteria
