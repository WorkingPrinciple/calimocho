# ADR-0064: Authenticate delivered ALPC connection impersonation

## Context

The native registrar impersonates the connecting client before accepting its
connection. Looking up a process from a PID supplied in the client's message
would allow impersonating a different process. The source transport instead
retains delivered connection requests and an owned creator-token snapshot.

## Decision

Support impersonation only for a delivered, still-unaccepted connection request
in the receiving port's server-owned pending registry. Check the message ID,
recorded client process/thread IDs, live client state and connection ownership.
These identifiers select and validate a retained record; they never select a
process token through a PID lookup.

Require explicit client static SecurityImpersonation QoS and enabled
SeImpersonatePrivilege in the receiving caller. Duplicate the retained token
and install it on the calling server thread only after all checks succeed.
Release the previous thread token only after duplication succeeds.

Validate QoS at the Unix client boundary. Reject dynamic tracking, effective-only
filtering and unsupported levels rather than silently ignore them. Connections
without explicit impersonation authorization cannot be impersonated.

This slice does not support impersonating arbitrary delivered datagrams or
ordinary requests. Consumed, cancelled, wrong-port and mismatched requests
fail cleanly. Nonzero impersonation flags remain unsupported.

Enable this source through `--alpc-impersonation` after the token-security
candidate. Keep runtime admission held.

## Consequences

Sanitized host checks execute the actual generated port handler and token
installation helper. Checks cover undelivered and consumed requests, wrong port,
forged process/thread IDs, disabled privilege, insufficient QoS, retained token
identity and ownership cleanup. Existing transport tests run in the same
harness. The isolated Wine build compiles the Unix/server protocol.

This is a narrow registrar handshake primitive, not general ALPC parity or
proof that native ServiceMain starts. SCM construction and dispatch admission
remain unfinished. No Wine service or application is executed.
