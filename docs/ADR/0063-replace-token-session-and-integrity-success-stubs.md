# ADR-0063: Replace token session and integrity success stubs

## Context

Wine11.20 returns success from TokenSessionId and TokenIntegrityLevel setters
without changing either value. Its integrity query always returns high
integrity. A registrar constructor relying on these APIs could claim a
session0, system-integrity service token while retaining different state.

## Decision

Query the token's actual stored mandatory label, with medium integrity when
no mandatory label exists. Implement explicit session and integrity setter
requests with server-side handle access and enabled SeTcbPrivilege checks.
Session changes require TOKEN_ADJUST_SESSIONID; integrity changes require
TOKEN_ADJUST_DEFAULT. Validate the exact label shape and mandatory authority.

Store a successful integrity change through Wine's existing label assignment,
update an existing integrity group SID and advance the token modification
identifier. Advance that identifier for successful session changes too.
Propagate assignment failures rather than return success.

This source slice supports privileged setters only. Unprivileged integrity
lowering is not yet qualified and returns STATUS_PRIVILEGE_NOT_HELD, not a
successful no-op. It does not grant privileges or alter credentials.

Enable this source slice through `--token-security` after `--token-identity`.
Retain the ALPC runtime freezer hold.

## Consequences

The sanitized host harness executes the generated query/setter helper and
checks insufficient rights, disabled privilege, malformed labels, assignment
failure, session persistence, actual label readback and modification IDs.
The isolated Wine build compiles both ends of the protocol.

This does not qualify an SCM token constructor or an installed registrar.
It deliberately fails closed for unqualified unprivileged setter behavior.
No prefix, service or application is executed.
