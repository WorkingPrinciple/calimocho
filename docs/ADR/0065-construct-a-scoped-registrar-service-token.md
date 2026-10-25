# ADR-0065: Construct a scoped registrar service token

## Context

Wine SCM launches services with its inherited launcher token. Reading ObjectName
alone does not create LocalService identity. The native measurements also bind
service SIDs and restrictions to the configured svchost group, not to constants
copied from one Windows VM.

## Decision

Add an opt-in source path for CoreMessagingRegistrar only. Require configured
LocalService, ServiceSidType3, shared-process type, the explicit svchost command
and a single-member LocalServiceNoNetwork registry group. Reject different
configurations and nonempty RequiredPrivileges unions instead of guessing.

Derive the service SID with RtlCreateServiceSid. Allocate fresh local logon and
source identifiers. Construct LocalService user/owner/primary group, measured
well-known groups, the configured service SID, eleven privileges with separate
default/current attributes, and the SYSTEM/OWNER RIGHTS/service default DACL.
Set session0 and system integrity through the real setters, then add
write-restricting SIDs for the service, Everyone, logon and Write Restricted Code.

Use a temporary SCM thread token to enable SeTcbPrivilege, preserving and
restoring the previous thread token. Never change the SCM process token.
Restoration failure terminates the SCM process rather than launch with a
privileged temporary impersonation accidentally retained.

Read back user, owner, primary group, authentication/source identity, session,
integrity, ordered groups/restrictions, privileges and default DACL before
returning the token. Launch this service with CreateProcessAsUserW and never
fall back to CreateProcessW after token construction fails.

## Consequences

The isolated build compiles SCM together with the token and ALPC source.
The host harness executes the actual configuration, privilege-scope and
readback guards with sanitizers, including every queried field's mismatch and
API-failure paths. Source admission remains explicit through
`--registrar-service`, with registrar_qualified false and the freezer hold.

This is a deliberately narrower host than the measured four-member native
svchost group. It does not copy the other members or the eight measured
unidentified group identities. The collector retained only SID and attributes;
it did not establish capability or local-membership derivation. Their derivation and the retained Windows26100
candidate's requirements are not established. This build must not be treated
as full native token parity or frozen for cell027 runtime execution on that
basis. CoreMessaging dispatch and ALPC wait integration also remain unfinished.
