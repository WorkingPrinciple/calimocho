# ADR-0060: Enforce restricting SIDs in source token checks

## Context

Registrar admission needs a restricted LocalService token, not an inherited
launcher token with a service SID added. Wine11.20 currently logs that
NtFilterToken restricting SIDs are unsupported and still returns a duplicated
token. It has no restricting-SID query or second discretionary access-check
pass. This can report successful filtering without enforcing the restriction.

The retained native write-overlap probe has sixty rows for file, registry
and two synthetic generic mappings. It establishes that write-restricted
tokens restrict write-only mapping bits plus DELETE, WRITE_DAC and WRITE_OWNER.
Read/execute overlap is not subject to that second pass.

## Decision

Add restricting-SID ownership to the server token, preserve it on duplication
and release it on destruction. Marshal separate disabled and restricting SID
arrays for NtFilterToken, validate their exact lengths on the server and
deduplicate restricting SIDs. Filtering an already restricted token uses the
intersection, not a union. An empty intersection remains restricted and must
not become unrestricted on a later filter.

Implement TokenRestrictedSids and restriction-status queries through the real
server token. The source must not return the ordinary group list as its
restricting list. Preserve existing restrictions when no new list is supplied.

Intersect the normal access result with a second ordered DACL pass using only
restricting SIDs. Write-restricted tokens apply that pass only to the measured
write mask. Handle MAXIMUM_ALLOWED by intersecting actual grants, not by
returning a guessed all-access mask. Owner grants in the normal pass must not
bypass restrictions. Null DACLs retain their unrestricted meaning.

Support WRITE_RESTRICTED filtering explicitly. Reject other not-yet-implemented
filter flags instead of logging and ignoring them. No credential, account,
service, prefix or runtime operation is performed by this source change.

The source-only build requires the opt-in ALPC candidate and remains blocked
by ADR-0059's runtime freezer guard. This primitive is necessary for faithful
registrar startup; it is not sufficient for admission.

## Consequences

Host tests compile the actual generated token access checker, restricting-SID
helpers, filter handler and group-query handler with address and undefined
behavior sanitizers. Checks cover second-pass denies, owner rights,
MAXIMUM_ALLOWED, write/read overlap, empty intersections, copied ownership,
allocation failure, buffer sizing, malformed SID arrays and unsupported flags.

The same checker matches all sixty rows of the retained native overlap probe,
including the twelve expected generic-mask API failures. The probe's own
exit1 means those twelve API calls failed as recorded; it does not invalidate
the individual measurements or mean all sixty accesses should succeed.
The evidence is xm commit `c1ad52800417fa8be1c3783b733b3cacffcd59aa`,
`scripts/macos/compatibility/xaml-startup/probe-outputs/native-write-overlap.txt`,
SHA-256
`a6e3a715a14fe7131a87dc2f7bc1a7886792666b765b887ceb5067892c2f445d`.

This is not a complete Windows security implementation. It does not add SCM
service-token construction, ALPC server-identity checks, message impersonation,
access-information hashing or the other token-filter flags. Existing
unrestricted-token behavior stays on the original access-check path.
