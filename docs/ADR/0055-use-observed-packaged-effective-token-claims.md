# ADR-0055: Use observed packaged effective-token claims

## Context

Actual022 established the thread-effective-token category and claim plus
attributes pointer shape with sampled signed GamingApp context. The r8
table correctly left packaged token-6 unobserved. Source tests did not
resolve the missing native reference.

The producer now reports one native packaged observation through interactive
session1 and Invoke-CommandInDesktopPackage for GamingApp/Microsoft.Xbox.App.
GetCurrentPackageFamilyName returned122 with34 characters required.
Guest output SHA-256 is
`0a5fee773716fc80d0661f08bb2a27602d38d13ba713eed07d7889306389d07b`.
Token-6 Site B returns0, Flags5, Origin3 and AttributesPresent3.
Claim-only and all-null shapes also return0. The producer states that the
reference ntdll identity was unchanged. This source lane does not claim
independent execution of the guest probe.

## Decision

Import unchanged Whiny r9 from main98f23b6, SHA-256
`9978669c98676693e3424653c214dae182d0a6c87f4b996c992632eb002d748a`.
Its observations SHA-256 is
`3e6c9074923d1f9a1e16ff18c8e927e3ab1678dc9c3e1ccc446c6311e0dd8009`.
Pin both identities and the guest reference in versions.json.

Build fresh023 with the existing genuine predicate and022 telemetry wrapper
unchanged. The generated table, not an alias or forced-context override,
adds the two observed packaged-token-6 cells. Other packages and unobserved
pointer shapes remain C0000002. Preserve all sealed predecessors.

## Consequences

Host checks compile the actual wrapper, genuine context helper and unchanged
artifact. Verify exact5/3/3 outputs, claim-only/all-null success, unpackaged
C0000225, unknown-context/shape failures, canaries and telemetry.
The exclusive runtime owner performs one private-prefix no-input observation
with the same cap and exact cleanup. Success at this claims call does not
establish Initialize completion, UI, game compatibility or general parity.
