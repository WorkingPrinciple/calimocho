# ADR-0056: Expose the observed OneCore transform query

## Context

Actual023 progresses past the claims call, then fails delay-loading
IsOneCoreTransformMode. The existing API-set family resolves to user32;
the actual staged user32 has no such export. No broad mapping is needed.

The producer's once-only native iocm-r2 observation uses interactive session1.
USER32.dll10.0.26100.8117 SHA-256
`f285937030bcb325cad39ee5be4818f6666241229adeadea4ff1ae469dfd7ef3`
exports the query at RVA72a70 as an import jump. The target win32u query
is a zero-argument syscall stub. Mode state is not implemented in the
user-mode export. The public phnt prototype is BOOL(void).

Two consecutive calls return0 in each observed context: unpackaged desktop
and signed GamingApp. The output SHA-256 values are
`945ae1f2b3d4fdbe311253b9658cf02187684bdb14a81a8c1f01f87a2bc372ee`
and `12b6c7b5ab380c7b55f5dc01d4fa5995a13de4f5994e6b6557873ae8a970b14f`.
The collection envelope and embedded output hashes were read independently.
The packaged observation reports package query122/34 required characters;
the unpackaged query reports15700. No true-mode state was observed.

## Decision

Add only the user32 BOOL(void) query, returning FALSE for this runtime's
non-enabled mode, matching both observed native contexts. There is no
OneCore mode-enabling path in this runtime. Do not add a pretend setter,
other OneCore exports, API-set redirects or an unnecessary win32u layer.
Retain023 claims, genuine predicate and telemetry unchanged.

This is an observation-backed narrow compatibility implementation, not a
general implementation of Windows kernel mode state. True OneCore modes,
ShellExperienceHost and mode transitions remain unobserved and unsupported.

## Consequences

Build a fresh024 sibling with one additional changed module, user32.
Tests compile the actual query, check its export wiring and idempotent port,
and verify the staged PE export. The exclusive runtime owner performs one
no-input observation with unchanged policy and exact cleanup. Passing this
import does not establish Initialize completion, rendered UI or game support.
