# ADR-0061: Bind ALPC connect checks to the creator token

## Context

The registrar client supplies server identity requirements when connecting.
Transport alone cannot satisfy these requirements. Ignoring the required SID
or descriptor would admit an unrelated server. Checking the connecting client's
token instead would authenticate the wrong party.

## Decision

Capture an owned duplicate of the port creator's effective token when creating
each port. Release that token with the port. Compare NtAlpcConnectPort's required
user SID against this snapshot. For NtAlpcConnectPortEx, serialize the supplied
server security descriptor through Wine's object-attribute serializer and check
PORT_CONNECT against the captured token using the real access checker, including
the restricting-SID pass from ADR-0060.

Validate the identity kind and exact SID or descriptor bounds on the server.
Return STATUS_SERVER_SID_MISMATCH for an identity that does not match. Do not
fall back to the connecting client, a supplied PID or a fabricated service SID.

Make this an explicit source-build option, `--alpc-identity`, requiring
`--restricted-token`. Retain the runtime freezer's ALPC admission hold.

## Consequences

The host harness exercises the actual generated ALPC handlers under sanitizers,
including captured identity, accepted and rejected SID/descriptor checks,
malformed identity data and existing transport ownership checks. A separate
compilation of the actual token identity helper and access checker exercises
restricting-SID rejection and admission.

The isolated Wine build establishes source integration, not native registrar
startup. These checks do not construct the SCM service token, authenticate
message impersonation or qualify CoreMessaging dispatch. Cell027 remains
unavailable until those requirements qualify.
