# ADR-0062: Preserve token owner, group and source identity

## Context

The query-only native registrar measurements identify LocalService as both
owner and primary group. That user SID does not need to appear in the ordinary
group list. Wine11.20 rejects that primary group, ignores NtCreateToken's owner
and source inputs, and reports a zero authentication identifier. Its token
duplication also couples owner to primary group and loses default privilege
attributes.

These are source prerequisites for constructing a service token, not permission
to copy a VM's dynamic identities or claim that a service already runs.

## Decision

Allow the user SID as owner and primary group, independently. Resolve group
selections against copied, server-owned groups. A selected group owner must
have SE_GROUP_OWNER. Reject invalid owner and primary-group selections.

Carry NtCreateToken's source data as a fixed-size variable payload, leaving the
request header within Wine's protocol bounds. Validate payload size, reserved
fields and signed group/privilege counts. Retain the supplied authentication
identifier, exact eight source-name bytes and source identifier. Query source
data with TOKEN_QUERY_SOURCE, separately from TOKEN_QUERY authentication data.

Token duplication remaps owner and primary-group pointers into the duplicate's
own user/groups, preserving identity values and privilege default attributes.
Creation preserves default privilege attributes independently from current
enablement.

Use the explicit `--token-identity` build option on a fresh ALPC identity
candidate. Keep runtime admission held.

## Consequences

Sanitized host checks compile the real identity helper, token-create request
handler and source-query handler. They cover LocalService-style user ownership,
different owner/primary group, copied ownership, malformed counts and payloads,
invalid owner attributes, source-query rights and exact source-name length.
The isolated Wine build checks the Unix client and server protocol together.

This does not implement service-token construction, integrity/session mutation,
message impersonation or complete token API parity. The Windows26300 evidence
does not by itself establish equivalence for the retained Windows26100 native
CoreMessaging binary. No service, prefix or application is run by this change.
