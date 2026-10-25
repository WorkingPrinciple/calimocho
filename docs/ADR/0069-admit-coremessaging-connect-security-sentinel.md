# ADR-0069: Admit the CoreMessaging connect security sentinel

## Context

Cell035 ran once. The genuine CoreMessagingRegistrar reached RUNNING and
waits on `\BaseNamedObjects\CoreMessagingRegistrar`. The app connect
failed twice with `reason=send_security_context`.

CoreMessaging.dll code at +0x3f428 to +0x3f4a9 builds the attribute:

- it allocates the attribute buffer with `_o_calloc`, so Flags is 0;
- it calls `AlpcInitializeMessageAttribute(0x80000000)`;
- it sets QoS to NULL and ContextHandle to `(HANDLE)-2`;
- it sets ValidAttributes to 0x80000000.

CoreMessaging does not import NtAlpcCreateSecurityContext. So -2 is not a
created context. phnt's `ntlpcapi.h` names no constant for it, and its
native meaning is not publicly documented.

## Decision

The connect takes ContextHandle `(HANDLE)-2`, with Flags 0 and no QoS,
like NULL. Both select the connection security context that the server
already captures at connect (ADR-0064). Any other non-NULL handle still
fails with `reason=send_security_context value=<handle>`.
NtAlpcCreateSecurityContext and NtAlpcDeleteSecurityContext stay
unimplemented because CoreMessaging does not call them.

## Consequences

Cell036 can show whether the app connects to the running registrar. The
meaning of -2 is inferred from CoreMessaging's use. If native behavior
differs (for example a per-message context), the server side may need
more work.
