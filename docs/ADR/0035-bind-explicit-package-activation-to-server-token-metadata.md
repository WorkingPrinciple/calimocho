# ADR-0035: Bind explicit package activation to server token metadata

## Context

The Xbox diagnostic originally launched `XboxPcApp.exe` directly. That did
not register a package. Wine's existing current-package API stubs also
could not establish whether a process genuinely had package identity.
The owner approved an isolated, explicit manifest activation seam.
Canonical program requirements remain in `dragos-core projects/ode-to-x/SPEC.md`.
This ADR does not establish game or runtime admission.

## Decision

Keep this opt-in source delta in
`patches/wine/0006-explicit-local-package-identity.patch`. It applies after
the existing port11 source integration, based on WineHQ commit
`7298a818b79446bae153b8d5aa27235ab3703bf9`. It is not compatible with
the alternative claims export in patch 0005.

`tools/package_activation.py` parses an exact manifest Application, checks
identity fields and a package-relative executable, and emits bounded UTF-16
activation metadata. It does not confer trust. The private creation
attribute passes metadata to wineserver, which owns a deep copy on the new
process token. Ordinary executable creation clears inherited registration.
Token duplication retains a separate copy until its last handle closes.
There is no metadata setter available to the running application.

The current full name, family name, package ID and application user model ID
APIs read that server metadata. A private ntdll token query exposes the same
record. The server protocol changes from 964 to 965; its server and ntdll
must be built and staged together. Accepted engines are never overlaid.

The unchanged Whiny r5 source is included with `WHINY_NO_DLLEXPORT`.
Its SHA-256 is
`2194a9ac3f418b9af78fcfefae307faaf1260fa6b6932a85df0b8bfbffc8bb72`.
No `WHINY_UNOBSERVED_STATUS` override is used. The generated win64 table is not compiled for i386;
i386 claims calls return `STATUS_NOT_IMPLEMENTED`.

Manifest identity is not signature verification, Store origin, a capability
grant, a licence or Windows activation-token parity. Enabling that context
requires verified content, a pinned Microsoft signing chain, the required
Store signing EKU and the signed full-trust manifest condition. None is
inferred from the publisher string.

`tools/prepare_verified_activation.py` copies and verifies an owned package
snapshot, seals its files read-only, and emits a mode-0600 host registration
record. Wineserver reads that record once at startup through
`CALIMOCHO_PACKAGE_REGISTRATION`, then removes that environment entry.
This is a host-operator interface, not an app environment flag. The record
must match both identity and the exact activated image path. Guest creation
attributes with a nonzero verified flag are rejected. The resulting flag
is stored on the token, not inferred at each claims call. The predicate
also checks the GamingApp family. Use a dedicated candidate server and a
fresh prefix; never inject this registration into an accepted engine.

Wine is not a sandbox against another native process running as the host
user. This local diagnostic registration does not create a new security
boundary or implement Windows Store installation.

## Consequences

The isolated candidate can exercise genuine local registration without
inventing Store claims. `tests/package_activation_probe.c` checks a plain
process and an explicitly activated fixture, buffer sizing, token handle
lifetime, duplicate metadata and an unregistered plain child. It also
checks that packaged claims leave the output sentinel unchanged and return
unsupported.

The fixture is a local conformance-style test, not a Windows reference
run or a complete AppX implementation. It does not implement a package
repository, dependencies, resources, Store services or native XAML activation.
The helper's generic `--activate` mode caps the app at 45 seconds. It remains a bounded diagnostic, not an
installed launcher or a game-readiness claim.

`tools/verify_installed_appx.py` performs offline, read-only host verification.
Microsoft 2010 and 2011 root DER fingerprints are pinned in `versions.json`.
OpenSSL verifies the RFC3161 timestamp signer and message imprint against
the actual code-signature bytes. The timestamp signer requires the exclusive
timeStamping usage and the pinned Microsoft 2010 root. The code-signing
chain is then checked at authenticated genTime, with code-signing and Store
usages and a matching Microsoft publisher.

The critical Microsoft Application Policies extension must equal the
certificate's extended key usages. Unknown critical extensions are rejected
before OpenSSL's compatibility option is used. No expiry override, guessed
verification time, system trust store or online revocation claim is used.
Legacy countersignatures are unsupported and fail closed.

The owner narrowed content verification to installed files because the
original archive is unavailable. AXPC and AXCD remain explicitly unverified
archive-layout digests. The owner then classified AXCT as archive-only too,
because Windows does not retain the content-types file in this installed
package. Its omission is disclosed, not reported as a digest match.
AXBM and the catalogue's AXCI, when present, must match. Every block-map file must match, and
unlisted executables or symlinks are rejected.

The genuine retained GamingApp passes the installed-file policy: timestamp,
signing chains, Store usage, AXBM, AXCI, 946 listed files, no extra executable,
publisher, family and full-trust manifest. Its version is **2609.1001.20.0**,
not the VM observer's 2610.1001.20.0. Explicit manifest activation selects
**XboxPcAppCE.exe**, not the historical plain-launch XboxPcApp.exe.
The signed predicate is eligible only through that verified host handoff.
The version difference remains a compatibility limitation, not packaged
Windows parity evidence.

## Reproduction boundaries

Apply patch 0006 to a new copy of the port11 integrated source, not to an
accepted source or install. Reconfigure a separate build with the existing
pinned local dependency environment. Build these targets together:

```bash
make -j4 server/wineserver dlls/ntdll/all dlls/kernelbase/all
```

Stage the new server, ntdll Unix library, both ntdll PEs and both kernelbase
PEs into a new copy of the private base install. No other file may differ.
The package fixture is compiled with the installed x64 MinGW compiler and
candidate ntdll/kernelbase import libraries. Native fixture execution needs
a finite owner-coordinated slot and a new prefix. A source-only test command is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_package_activation tests.test_package_context tests.test_installed_appx
```

Use `python3 -m tools.prepare_verified_activation --help` for host preparation.
Supply only the pinned root DER files and a fresh output outside the package
tree. The exact cell004 environment, ordered server stop/wait/start commands,
activation argument vector and hashes live in its local receipt. Those
commands are handed to the Xbox lane; preparing the record does not launch it.
