# ADR-0082: Signed engine release index

Status: Proposed (REQ-124). Not adopted until it is reviewed independently.
Date: 2026-10-26

## Context

X Ode and its backend accept only Calimocho engines whose hashes were
pinned when X Ode was built. A new engine therefore needs a new X Ode
build, even when nothing in X Ode changed. REQ-123 (check for updates
in Settings > Engines) needs a trustworthy list of engine releases that
X Ode can read from the public GitHub releases without logging in.

The list must not let a network attacker, a compromised GitHub account
or a stale mirror install code that we did not release. Each engine
binary is already signed with the maintainer's Developer ID and
notarized, and its zip has a SHA-256. What is missing is a signed
statement that says which releases exist and which X Ode versions may
use them.

## Decision

### Format

- The index is a JSON payload,
  [`calimocho-engine-index-v1.schema.json`](../contracts/calimocho-engine-index-v1.schema.json),
  inside a DSSE v1 envelope,
  [`calimocho-engine-index-envelope-v1.schema.json`](../contracts/calimocho-engine-index-envelope-v1.schema.json).
  DSSE (the envelope used by in-toto and Sigstore) signs the exact
  payload bytes. There is no JSON canonicalisation to get wrong.
- Signatures are Ed25519 (RFC 8032) over
  `PAE = "DSSEv1" SP LEN(payloadType) SP payloadType SP LEN(payload) SP payload`.
  LEN is the byte length in ASCII decimal. `keyid` is the hex SHA-256
  of the raw 32-byte public key.
- An envelope can carry up to four signatures, so a key rotation can
  overlap.
- The payload lists, for each engine, the fields REQ-124 asks for and
  what the installer needs to check the download:
  - engine ID, version and provider
  - channel
  - minimum X Ode version
  - release tag and notes URL
  - zip name, URL, size and SHA-256
  - the expansion bound (uncompressed size and entry count)
  - corresponding-source tar and source commit
  - install folder
  - the SHA-256 of `bin/wine`, `bin/wineserver`, the loader,
    `MANIFEST.sha256` and `calimocho-engine.json`
  - Developer ID Team ID and notarization ID
  - Apple D3DMetal version and binary SHA-256
  - Wine, D3DMetal and MoltenVK versions

  It also has a monotonic `index_version`, `generated_at`, `expires_at`
  (at most 90 days later) and a `revoked` list.
- URLs must point at `github.com/WorkingPrinciple/calimocho/releases`,
  and each asset URL must match its entry's release tag and file name.

### Client rules (X Ode)

1. Download the envelope and refuse anything over 1.5 MiB. The
   `payloadType` must match exactly.
2. Accept the envelope only if at least one signature whose `keyid` is
   in the trusted set embedded in X Ode verifies. Ignore unknown
   `keyid`s.
3. Decode the payload (at most 1 MiB) and validate it against the
   schema and the rules in `tools/engine_index.py check_payload`.
4. Refuse an index whose `index_version` is lower than the highest one
   already accepted, which X Ode stores. Refuse an expired index and
   one dated in the future. Allow 5 minutes of clock skew.
5. An engine is offered only if `min_xode_version` is at most the
   running X Ode version and the engine is not in `revoked`.
6. After download:
   - The zip size and SHA-256 must match the entry.
   - The zip central directory and the actual extraction must stay
     within `unpacked.size` and `unpacked.entries`.
   - After unpacking, `MANIFEST.sha256` must have `manifest_sha256` and
     must verify every file.
   - The wine, wineserver, loader and engine JSON hashes must match.
   - Our binaries must carry Team ID `M62Z4M5EUY`.
   - D3DMetal must still carry Apple's signature and `binary_sha256`.
7. **Failure never removes anything.** An expired, rolled-back, unsigned
   or unreachable index only means "no update available". It never
   disables, hides or uninstalls an engine that is already installed.
   An engine listed in `revoked` is not offered for installation. X Ode
   may warn about an installed revoked engine, but removing it stays the
   user's choice.

### Admission (backend)

For X Ode 0.2.0 the backend keeps its static pinned admission. Index
entries only drive the update interface and the download and
verification steps. An installed engine is admitted only after X Ode
pins its hashes, as today. Admitting engines from the index directly is
a separate REQ-33 change and is out of scope before 2026-10-30.

### Hosting

The envelope will be one asset, `calimocho-engine-index.json`, on a
fixed prerelease tag `engine-index` that is never marked Latest. Its
URL is:

`https://github.com/WorkingPrinciple/calimocho/releases/download/engine-index/calimocho-engine-index.json`

The asset is replaced with each engine release, and `index_version`
goes up. **Nothing is published until this ADR, the tool and the test
vector have been reviewed independently.**

### Key custody

- **Production key.** Ed25519 key `b2906316227f06803851b23824ed2ff3a93fd590c0c497752387713fff70dcee`,
  created 2026-10-26 on the maintainer's Mac. The private key is at
  `~/.config/calimocho/engine-index/engine-index-ed25519-2026-10.pem`,
  in a `0700` folder with mode `0600`. That folder is outside every
  repository.
- **Where it may not go.** The private key is never committed, never
  stored in the Keychain and never given to CI. `tools/engine_index.py`
  refuses a key file that group or others can read. It never prints a
  private key.
- **Public key.** It is in
  [`calimocho-engine-index-keys.json`](../contracts/calimocho-engine-index-keys.json).
  X Ode and the backend embed the active keys at build time.
- **Backup.** At rest the key is protected by FileVault, and it is
  included in Time Machine. The maintainer keeps one offline copy on an
  encrypted removable volume. The owner confirms the backup location
  (Ode takes this to the owner). A lost key is handled as a rotation:
  installed engines keep working, and only updates stop until an X Ode
  with a new key ships.
- **Test key.** The test vector uses the public RFC 8032 TEST 1 key,
  which is never trusted.

### Rotation and revocation

- **Planned rotation.**
  1. Create a new key and add it to the keys file as `active`.
  2. Ship an X Ode and backend that trust both keys.
  3. Sign indexes with both keys until that X Ode is the minimum in
     use.
  4. Mark the old key `retired`, ship again, and destroy the old
     private key.
- **Compromise.**
  1. Ship an X Ode and backend without the key as soon as possible.
  2. Sign new indexes only with a new key.
  3. Raise `index_version` above anything the attacker could have
     signed.

  Until users update, a stolen index key could only list builds that
  already pass every other check. Each engine must still be Developer
  ID-signed by Team `M62Z4M5EUY`, carry Apple's D3DMetal signature, and
  match the hashes listed in the same signed entry. Admission in 0.2.0
  still requires static pins. So the key alone cannot get foreign code
  installed.
- **Engine revocation.** List the engine in `revoked` with a reason in
  the next index.

### Tools and test vector

- `tools/engine_index.py`:
  - `keygen` and `pubkey` manage keys.
  - `entry` reads a release zip and source tar and records their hashes
    and expansion bound.
  - `payload` builds the canonical index payload.
  - `sign` writes the envelope.
  - `verify` implements the client rules above.

  Ed25519 comes from OpenSSL 3. Everything else is the Python standard
  library.
- `tests/engine-index/` holds:
  - the known-answer vector (`vector.json`, `payload.json`,
    `envelope.json`) for the real 0.1120.4.6 entry
  - three negative envelopes (tampered payload, wrong payload type,
    untrusted key)
  - expiry, future-date, rollback and minimum-version cases
  - RFC 8032 TEST 2 and TEST 3 checks of the OpenSSL signing path
  - a cross-check with pyca/cryptography
  - `verify_vector.swift`, which checks the vector with CryptoKit, the
    framework X Ode uses

## Consequences

- An engine-only update needs no X Ode rebuild to be *offered*. In
  0.2.0, admitting it still needs X Ode to pin its hashes.
- A signing key is a new secret to look after. Losing it stops updates
  but breaks nothing that is installed.
- GitHub can still withhold or delay the index (freeze). Expiry limits
  that to 90 days, and a stale index never harms installed engines.
