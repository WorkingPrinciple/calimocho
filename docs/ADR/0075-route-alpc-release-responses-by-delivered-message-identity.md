# ADR-0075: Route ALPC release responses by delivered message identity

## Context

Cell041 ran once. Its collector timed out and the trace is truncated, so
the target's final state is unknown. The recovered trace proves that the
app connected, sent request id 257, and the registrar received it. The
registrar then sent on its listener handle 0x74 with flags 0x10000
(RELEASE_MESSAGE), Type=1, MessageId=257 and 96 payload bytes. Wine
returned STATUS_INVALID_PORT_HANDLE. No response was queued to the app.

The response helper in native CoreMessaging copies the received 40-byte
PORT_MESSAGE header, changes the payload lengths, and sends it with
RELEASE_MESSAGE on the listener. The original Type, ClientId, MessageId
and callback are deliberately retained. This was read for understanding
only; no native instructions or implementation were copied.

Our ntdll discarded RELEASE_MESSAGE before calling wineserver. The server
therefore classified the retained Type=1 as a new request. A listener has
no single peer for a new request, so that branch correctly rejected it.
Changing which handle CoreMessaging uses would hide the actual problem:
the server must correlate this response with the delivered request.

## Decision

- Preserve RELEASE_MESSAGE across the ntdll/server boundary, together with
  the original ClientId. Reject ClientId values that cannot fit the
  server's process/thread identity fields rather than truncate them.
- RELEASE plus a nonzero MessageId selects a response lookup. Do not
  classify every nonzero MessageId as a reply, and do not change the
  public REPLY_MESSAGE value back to the release value.
- A pending request records its sender's process/thread ids and callback.
  It becomes eligible for a release response only after successful
  receive, not merely after enqueue.
- A release response must match that delivered identity and endpoint.
  A listener may answer its own clients. A communication port may answer
  only its own peer. The response is delivered as LPC_REPLY with the
  original id, and consumes the pending record exactly once.
- Missing, undelivered, duplicate, wrong-ClientId, wrong-callback and
  wrong-connection responses return STATUS_REPLY_MESSAGE_MISMATCH. They
  do not consume the legitimate pending record.
- RELEASE with a zero MessageId remains a fresh send. Explicit REPLY
  routing is preserved.
- Regenerate the server protocol and rebuild ntdll and wineserver together.
  No request numbers are changed.

## Consequences

The host test first runs the actual cell041 server implementation and
reproduces the listener response failure. After the porter, the same
96-byte response reaches the matching client. It also checks the refusal
cases, a response through the correct communication port, a second
connection that cannot steal the response, explicit replies, and a fresh
release datagram. AddressSanitizer and UndefinedBehaviorSanitizer cover
the real server handlers in this fixture.

This is a bounded contract inferred from the observed native caller, not
a claim of fully measured Windows ALPC behavior. Native Windows
differential testing is unavailable. Retained-message release-only calls,
callbacks and the broader release lifecycle remain outside this slice.
Compilation and host checks do not prove that the Xbox app starts.
