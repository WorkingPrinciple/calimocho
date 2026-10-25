# ADR-0053: Use the observed packaged claims Site B cell

## Context

Actual020 retained one RtlQueryPackageClaims return with low32 C0000002
at original native XAML+704cfd, after lifetime callback registration and
before the D0000002 fail-fast. Static inspection establishes that Site B
passes null arguments2-6 and non-null claim and attributes outputs.
Actual020 did not capture the token, outputs or selected generated cell.
The existing generated table only covered packaged claim-only success.

The producer supplied Whiny r6 from main8c4d6d9, including the observed
packaged GamingApp r4 row16. Its reference JSON SHA-256 is
`986c9562dcf4ac31432d401e56cd022f8a0362346cf569bb6ca6c28f532f3212`.
The generated artifact SHA-256 is
`2924dd6c183b944d3a177fd2f2bf96571dde92b175b123eee64a938faf4b14d6`.
The producer reports host parity in all contexts. This lane independently
checks the supplied source bytes and compiled behavior, not the VM run.

## Decision

Import the generated artifact unchanged and pin its identity in versions.json.
An explicit claims-site-b build mode replaces the generated claims header in
a fresh owned sibling only. The existing genuine package identity query and
verified GamingApp family predicate remain unchanged. Preserve the historical
patch and frozen020 source, receipts, installs and diagnostics.

For the observed signed GamingApp context, token-4, null arguments2-6,
and non-null claim/attributes outputs, the generated cell returns0 and writes
Flags5, Origin3 and64-bit AttributesPresent3. Unpackaged token-4 still returns
C0000225, leaves the claim untouched and zeroes attributes. Unsupported input
shapes and unknown package contexts remain C0000002, without fake success.
Host checks compile the actual context helper and byte-exact generated source,
including output-width canaries and unknown-context failures.

## Consequences

Cell021 retains020's fail-fast, matching-return, FIXME and owned-COM
diagnostics. Its receipt binds the artifact, unchanged context source,
producer commit, build, installed assets and sealed020 predecessor.
The exclusive runtime owner performs one fresh private-prefix no-input
observation and exact cleanup, with the same180-second cap. No fixture or
Wine process is executed by this source lane. Runtime progress does not
establish actual token/output values or a particular generated branch.
Compilation is not XAML, AppL, UI, game or general Windows parity acceptance.
