# ADR-0082: Signed engine release index

Status: Proposed (REQ-124). Revised after the first independent review
(REVISE on `ac6ef69`). Not adopted until it passes re-review.
Date: 2026-10-26

## Context

X Ode and its backend accept only Calimocho engines whose hashes were
pinned when X Ode was built. A new engine therefore needs a new X Ode
build, even when nothing in X Ode changed. REQ-123 (check for updates in
Settings > Engines) needs a trustworthy list of engine releases that
X Ode can read from public GitHub releases without logging in.

The list must not let a network attacker, a compromised GitHub account,
a stale mirror or a stolen signing key install code we did not release.
It also must not let any of them freeze clients on an old list. Each
engine is already Developer ID signed, notarized and hashed. What is
missing is a signed statement of which releases exist and which X Ode
versions may use them.

## Decision

### Format

- The index is a JSON payload,
  [`calimocho-engine-index-v1.schema.json`](../contracts/calimocho-engine-index-v1.schema.json),
  inside a DSSE v1 envelope,
  [`calimocho-engine-index-envelope-v1.schema.json`](../contracts/calimocho-engine-index-envelope-v1.schema.json).
- **Signatures.** Ed25519 (RFC 8032) over
  `PAE = "DSSEv1" SP LEN(payloadType) SP payloadType SP LEN(payload) SP payload`.
  - LEN is the byte length in ASCII decimal.
  - `keyid` is the lowercase hex SHA-256 of the raw 32-byte public key.
  - An envelope carries up to four signatures.
- **Payload fields.** The payload carries:
  - `epoch`: the signing epoch, at most 2^31−1.
  - `index_version`: at most 2^31−1.
  - `generated_at` and `expires_at`: at most 90 days apart.
  - `publisher`.
  - `engines`.
  - `revoked`: a list of engine IDs with reasons.
- **Engine entries.** Each entry lists the fields REQ-124 asks for, plus
  what the installer checks:
  - engine ID, version, provider, channel and minimum X Ode version;
  - release tag and notes URL;
  - zip name, URL, size and SHA-256;
  - the expansion bound `unpacked` (total uncompressed bytes and
    entries);
  - corresponding-source tar and source commit;
  - install folder;
  - the SHA-256 of `bin/wine`, `bin/wineserver`, the loader,
    `MANIFEST.sha256` and `calimocho-engine.json`;
  - Team ID and notarization ID;
  - the Apple D3DMetal version and binary hash;
  - component versions.
- **What X Ode embeds.** X Ode and the backend embed
  [`calimocho-engine-index-trust.json`](../contracts/calimocho-engine-index-trust.json)
  ([schema](../contracts/calimocho-engine-index-trust-v1.schema.json)) at
  build time. It holds:
  - the trusted public keys, each bound to exactly one epoch;
  - revoked keyids;
  - a floor (`epoch`, `index_version`);
  - engines revoked at build time.
- **What X Ode persists.** X Ode persists
  [`calimocho-engine-index-state`](../contracts/calimocho-engine-index-state-v1.schema.json):
  - the high-water `epoch`, `index_version` and `payload_sha256`;
  - the keyids that set them;
  - every engine revocation seen.

### Client rules (X Ode, normative)

1. **Fetching** (URL rules below):
   - The envelope URL is fixed. Follow at most 5 redirects, and only to
     `https` URLs.
   - Stop reading after 1.5 MiB. The payload may be at most 1 MiB.
2. **Parsing.** Every JSON document (envelope, payload, trust, state)
   is parsed strictly:
   - duplicate object keys, `NaN` and `Infinity` are errors;
   - base64 must be canonical (re-encoding gives the same text).
   - Foundation's JSON parsers do not reliably reject duplicate keys,
     so X Ode needs its own duplicate check.
3. **Patterns.** Every schema `pattern` must match the **whole**
   string. Use `\A…\z` or check that the match range equals the full
   length. A pattern ending in `$` alone also matches before a trailing
   newline in ICU and Python. Strings may not contain control
   characters.
4. **Signatures.** `payloadType` must match exactly. A signature counts
   only if:
   - its `keyid` is an active embedded key that is not in
     `revoked_keyids`;
   - it verifies over PAE;
   - that key's `epoch` equals the payload's `epoch`.

   Unknown keyids are ignored. At least one signature must count.
5. **Content.** Validate the payload against the schema and the rules in
   `tools/engine_index.py check_payload`. URLs must parse as `https`,
   host `github.com`, with no userinfo, port, query or fragment. Each
   path must equal the release path for the entry's tag and file name.
6. **Freshness.** Refuse an index if `now` is later than `expires_at`
   plus 5 minutes, or earlier than `generated_at` minus 5 minutes.
7. **High-water mark.** Load the persisted state. Discard it if any of
   its keyids is in the embedded `revoked_keyids`. Then refuse the index
   if:
   - (`epoch`, `index_version`) is below the embedded floor;
   - `epoch` is below the state's epoch;
   - in the state's epoch, `index_version` is lower than the state's;
   - in the state's epoch, `index_version` is equal but
     `payload_sha256` differs (equivocation).

   A higher epoch starts a new high-water mark.
8. **Persist only after every check passes**, by writing a new file and
   renaming it. Store the union of the revocations from the embedded
   trust, the old state and the payload. Revocations are never removed.
9. **Offering engines.** Offer an engine only if:
   - it is not revoked;
   - `min_xode_version` ≤ the running X Ode version, comparing SemVer
     MAJOR.MINOR.PATCH as integers;
   - its `version` is **strictly newer** than the installed Calimocho
     version, comparing the four dot-separated components as integers
     (so `0.1120.4.10` > `0.1120.4.6`).
10. **Failure never removes anything.** An expired, rolled-back,
    equivocating, unsigned or unreachable index only means "no update
    available". It never disables, hides or uninstalls an installed
    engine. A revoked engine is not offered. X Ode may warn about an
    installed revoked engine, but removing it stays the user's choice.

### Installer rules (X Ode, normative; reference: `check_zip` in the tool)

1. **Staging.** Download into a private staging folder (mode `0700`) on
   the same volume as `~/Library/Application Support/Xode/Engines`.
   Hash while streaming, and stop as soon as the byte count exceeds the
   signed `asset.size`. The size and SHA-256 must match.
2. **Paths.** Before writing anything, read the zip central directory.
   Refuse:
   - more entries than `unpacked.entries`, or a total declared size over
     `unpacked.size`;
   - absolute paths, backslashes, NUL or other control characters;
   - empty, `.` or `..` components;
   - paths outside `<engine_id>/`;
   - duplicate paths;
   - two paths that are equal after Unicode NFC normalisation and case
     folding (APFS is case-insensitive and normalisation-insensitive by
     default).
3. **Member types.** Allow only regular files, directories and symbolic
   links. Refuse hard links, devices and FIFOs.
4. **Symbolic links.**
   - The target must be relative and contain no backslash or NUL.
   - After resolving the whole chain, it must stay inside
     `<engine_id>/` and point to an entry in the archive.
   - No entry may lie under a symbolic link, so nothing is written
     through one.
   - Create links with `symlink()` and never follow them while
     extracting. Open files with `O_NOFOLLOW | O_EXCL`.
5. **Expansion limits.** Count decompressed bytes as they are written.
   Stop when the total exceeds `unpacked.size`, or when one entry
   exceeds its declared size.
6. **Verification before activation.** On the staged tree, before it is
   used:
   - `MANIFEST.sha256` has `manifest_sha256` and matches every file and
     link, with nothing unlisted;
   - the wine, wineserver, loader and engine JSON hashes match the
     entry;
   - `codesign --verify --strict` passes on our Mach-O files, with Team
     ID `M62Z4M5EUY` taken from a constant compiled into X Ode, never
     from the entry;
   - D3DMetal still carries Apple's own signature and `binary_sha256`.
7. **Activation.** Rename the staged folder into
   `Engines/<engine_id>/` in one atomic step. Never replace an existing
   folder; an engine with the same ID that is already installed stays.
8. **Quarantine.** X Ode's downloads carry no `com.apple.quarantine`
   attribute: URLSession does not add one, and X Ode must not opt in
   with `LSFileQuarantineEnabled`. The installer never strips the
   attribute; the checks above stand in for the Gatekeeper prompt. Every
   binary is notarized, so a manually downloaded copy (with quarantine)
   also passes Gatekeeper. The engine is never run from the staging
   folder.

### Admission (backend)

For X Ode 0.2.0 the backend keeps its static pinned admission. Index
entries only drive the update interface and the download and
verification steps. An installed engine is admitted only after X Ode
pins its hashes, as today. Admitting from the index is a separate REQ-33
change and is out of scope before 2026-10-30.

### Hosting

- The index is one asset, `calimocho-engine-index.json`, on a fixed
  prerelease tag `engine-index` that is never marked Latest:
  `https://github.com/WorkingPrinciple/calimocho/releases/download/engine-index/calimocho-engine-index.json`
- GitHub redirects that URL to an `https` asset host. The asset is
  replaced with each engine release, and `index_version` goes up.
- **Nothing is published until this ADR, the tool and the test vector
  pass independent review.**

### Key custody

- **The key.** The production key is
  `b2906316227f06803851b23824ed2ff3a93fd590c0c497752387713fff70dcee`,
  bound to epoch 1. It was created 2026-10-26 on the maintainer's Mac.
- **Where it lives.** The private key is at
  `~/.config/calimocho/engine-index/engine-index-ed25519-2026-10.pem`,
  in a `0700` folder with mode `0600`. That folder is outside every
  repository.
- **Encryption.** The key is PKCS#8 encrypted with AES-256 and a
  passphrase. The maintainer sets the passphrase with
  `tools/engine_index.py encrypt-key`, which re-encrypts in place,
  checks that the public key is unchanged and replaces the file
  atomically. `sign` refuses an unencrypted key.
- **Where it may not go.** The key is never committed, stored in the
  Keychain or given to CI. The tool refuses a key file that group or
  others can access and never prints private key material.
- **Passphrase.** It is typed at the terminal (or passed in
  `CALIMOCHO_ENGINE_INDEX_PASSPHRASE` for one command). It is never
  written to disk on the Mac. The owner keeps it in their password
  manager. A sealed paper copy kept apart from the key backup is the
  escrow.
- **Backup.** The key folder is included in Time Machine, and the Time
  Machine target **must be encrypted**. The owner also keeps one copy on
  an encrypted removable volume. The owner confirms both locations; Ode
  relays this.
- **Recovery drill.** Once per release cycle:
  1. Restore the key from backup to a temporary folder.
  2. Run `pubkey` with the passphrase.
  3. Compare the keyid with the trust file.
  4. Delete the temporary copy.

  If the key or the passphrase is lost, treat it as a rotation.
  Installed engines keep working; only updates stop until an X Ode with
  a new key ships.
- **Test keys.** The test vector uses the public RFC 8032 TEST 1 and
  TEST 2 keys, which are never trusted.

### Rotation and revocation

- **Planned rotation** (no compromise; same epoch):
  1. Create a new key with `keygen` and add it as `active` in the same
     epoch.
  2. Ship an X Ode and backend that trust both keys.
  3. Sign with both keys.
  4. Once the oldest supported X Ode trusts the new key, mark the old
     key `retired`, ship, and destroy the old private key.
- **Compromise:**
  1. Create a new key bound to `epoch + 1`.
  2. Ship an X Ode and backend that list the old keyid in
     `revoked_keyids`, trust the new key, and raise the floor to the new
     epoch.
  3. Sign new indexes only with the new key, in the new epoch.

  What the stolen key can do:
  - It signs only its own epoch, so it cannot move clients to a later
    one.
  - Any high-water mark it set is discarded by builds that revoke it.
  - The `index_version` cap keeps everything finite.
  - It cannot get foreign code installed: every engine must still be
    Developer ID signed by Team `M62Z4M5EUY` (constant in the client),
    carry Apple's D3DMetal signature and match the signed hashes. In
    0.2.0, admission still needs static pins.
- **Engine revocation.** List the engine in `revoked` with a reason in
  the next index, and in `revoked_engines` in the next X Ode build.

### Tools and test vector

- `tools/engine_index.py` (Ed25519 from OpenSSL 3; everything else is
  the Python standard library):
  - `keygen`, `encrypt-key` and `pubkey` manage keys.
  - `entry` reads a release zip and source tar.
  - `payload` and `sign` build the index.
  - `verify` applies the client rules and can update a state file.
  - `check-asset` applies the installer rules to a zip.
- `tests/engine-index/` holds:
  - the known-answer vector (`vector.json`, `payload.json`,
    `envelope.json`) for the real 0.1120.4.6 entry;
  - test trust files;
  - 33 cases with expected `eligible` lists and new state, covering:
    - version filtering;
    - same index, newer index and new epoch;
    - persisted and embedded revocation;
    - a state set by a revoked key;
    - rollback, older epoch and equivocation;
    - the floor, a revoked signing key and the key-to-epoch binding;
    - expiry and future dates;
    - dot and hidden names, newline, NUL, URL userinfo, port and
      `http`;
    - the `index_version` cap, duplicate keys and non-canonical
      base64;
    - tampering, wrong payload type and an untrusted key.

  The content negatives carry valid signatures, so the rules reject
  them, not the cryptography.
- The tests also cover:
  - RFC 8032 TEST 2 and 3 known answers;
  - malicious-zip cases (path, link, type, collision and bound
    violations);
  - parsed-URL checks;
  - key encryption and refusal of unencrypted keys;
  - cross-checks with pyca/cryptography and with CryptoKit
    (`verify_vector.swift`).

## Consequences

- An engine-only update needs no X Ode rebuild to be *offered*. In
  0.2.0, admitting it still needs X Ode to pin its hashes.
- The signing key and its passphrase are new secrets to look after.
  Losing them stops updates but breaks nothing that is installed.
- GitHub can still withhold or delay the index. Expiry limits that to
  90 days, and a stale index never harms installed engines.
