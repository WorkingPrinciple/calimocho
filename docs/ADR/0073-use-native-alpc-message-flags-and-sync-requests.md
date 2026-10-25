# ADR-0073: Use native ALPC message flags and synchronous requests

## Context

Cell039 ran once. The connect handshake succeeded: the registrar
impersonated the client, accepted, and the app's NtAlpcConnectPortEx
returned 0. The app's first NtAlpcSendWaitReceivePort (CoreMessaging
+21b6) then returned STATUS_NOT_IMPLEMENTED with no FIXME reason. The
call carries one CONTEXT send attribute and the flag 0x20000
(ALPC_MSGFLG_SYNC_REQUEST). The flag gate admitted only the reply and
alertable bits.

The native flag values (phnt `ntlpcapi.h`) are: REPLY_MESSAGE 0x1,
LPC_MODE 0x2, RELEASE_MESSAGE 0x10000, SYNC_REQUEST 0x20000,
TRACK_PORT_REFERENCES 0x40000, WAIT_USER_MODE 0x100000, WAIT_ALERTABLE
0x200000, and an internal reject bit 0x1000000. Wine 11.20's
`winternl.h` defines ALPC_MSGFLG_REPLY_MESSAGE as 0x10000. So a native
server reply (0x1) was sent as a new message, and a native release
(0x10000) was read as a reply. The phnt notes also say that a synchronous
request with a send message rejects RELEASE_MESSAGE.

## Decision

- `winternl.h` uses the native 0x1 for ALPC_MSGFLG_REPLY_MESSAGE. ntdll and
  wineserver both read it from there, so they agree with native callers.
- One pure ntdll helper, `alpc_send_flags_status`, checks the flags:
  - the internal reject bit returns STATUS_INVALID_PARAMETER;
  - SYNC_REQUEST needs a send message and a receive buffer, and no reply
    flag. With RELEASE_MESSAGE and a send message it returns
    STATUS_INVALID_PARAMETER;
  - RELEASE_MESSAGE is otherwise a no-op, because wineserver frees each
    message when it is received;
  - WAIT_USER_MODE and WAIT_ALERTABLE only change the wait;
  - any other bit returns STATUS_NOT_IMPLEMENTED with
    `reason=send_flags value=<mask>`, and an unsupported synchronous shape
    with `reason=sync_request_shape value=<mask>`.
- A send attribute other than CONTEXT returns STATUS_NOT_IMPLEMENTED with
  `reason=send_attrs value=<mask>`.
- Only the reply bit is sent to wineserver.
- A synchronous request uses the existing path: it is sent as LPC_REQUEST,
  and the receive waits for the reply with the same message id on the
  client port.
- A non-zero MessageId without the reply flag is not treated as a reply.

## Consequences

- The host test checks the flag table and the reasons, and the registrar
  shape: a synchronous request with a CONTEXT value reaches the waitable
  connection port as LPC_REQUEST, an unrelated datagram does not satisfy
  the client's wait, the native reply flag routes the reply to the
  client, and a second reply is a mismatch.
- No other Wine code used the old reply value.
- TRACK_PORT_REFERENCES and LPC_MODE are still not implemented.
- Whether native treats a MessageId without the reply flag as a reply was
  not traced. The next run shows which flags the registrar uses to reply.
