# ADR-0068: Validate the transient descriptor in sechost and admit the default connect security attribute

## Context

Cell034 ran once. The app no longer crashed, but two blockers remained.

Registrar: svchost read the 264-byte `WM_RegistrarServer` descriptor and
then returned STATUS_INVALID_SECURITY_DESCR (0xc0000079). The bytes are
well formed. Wine 11.20's `RtlValidRelativeSecurityDescriptor` is a
semi-stub: it compares the BOOLEAN result of `RtlValidSecurityDescriptor`
with `STATUS_SUCCESS` (0), so it rejects every valid descriptor. The
ADR-0067 host test mocked that function, so it did not catch this.

App: `NtAlpcConnectPortEx` returned 0xC0000002 with
`reason=send_attributes value=0x80000000`. CoreMessaging sends only the
security attribute with its connection message. The earlier lane accepted
this attribute only with no flags and no QoS. A security attribute without
flags, QoS or a context handle selects the connection's own security
context. Our server already captures that context at connect (ADR-0064).

## Decision

- sechost checks the descriptor itself and no longer calls the semi-stub.
  It checks the revision, the self-relative bit, the owner and group SIDs,
  the SACL and DACL (revision 2 to 4, size, ACE count, ACE size alignment)
  and the SID in each allowed, denied, audit and alarm ACE. The host test
  feeds it the exact bytes of the frozen .reg value and ten corruptions.
- The connect admits a send security attribute only when Flags is 0 and
  QoS and ContextHandle are NULL. Each other case keeps a fixed reason:
  `send_security_flags`, `send_security_qos`, `send_security_context`, or
  `send_attributes` for any other valid send attribute. Valid bits outside
  the allocated set, or allocated bits outside the defined set, return
  STATUS_INVALID_PARAMETER. A compiled host test runs that exact check.

Wine's own `RtlValidRelativeSecurityDescriptor` is not changed, to keep the
ntdll change set small.

## Consequences

Cell035 can show whether the registrar creates its port and reaches
RUNNING, and whether the app connects. These are not proven by host tests.
The token still lacks the eight measured S-1-5-32 groups, and
identification-level impersonation still returns
STATUS_BAD_IMPERSONATION_LEVEL.
