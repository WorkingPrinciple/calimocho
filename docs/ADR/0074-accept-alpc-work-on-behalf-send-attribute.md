# ADR-0074: Accept the ALPC work-on-behalf send attribute

## Context

Cell040 ran once. The connect still succeeded. The app's first
NtAlpcSendWaitReceivePort (CoreMessaging +21b6) returned
STATUS_NOT_IMPLEMENTED with `reason=send_attrs value=0x2000000`, which is
ALPC_MESSAGE_WORK_ON_BEHALF_ATTRIBUTE. The app then failed fast with
0xd0000002. The new flag support from ADR-0073 was not reached, because the
attribute check came first.

CoreMessaging (read for understanding only) allocates one attribute buffer
with SECURITY, VIEW, CONTEXT and WORK_ON_BEHALF (0xe2000000). It marks
CONTEXT and WORK_ON_BEHALF valid (0x22000000), and it uses the same buffer
to send and to receive. When a received message has a valid WORK_ON_BEHALF
attribute, it reads its own thread ticket with
RtlGetThreadWorkOnBehalfTicket. It adopts the received ticket only if that
call succeeds. Otherwise it handles the message normally.

A work-on-behalf ticket identifies the thread that work is done for. Wine
has no thread tickets: both Rtl ticket functions are explicit
STATUS_NOT_IMPLEMENTED stubs.

## Decision

- One pure ntdll helper, `alpc_send_attrs_status`, checks send attributes:
  - valid bits that are not allocated return STATUS_INVALID_PARAMETER;
  - CONTEXT and WORK_ON_BEHALF are accepted;
  - any other bit returns STATUS_NOT_IMPLEMENTED with
    `reason=send_attrs value=<mask>`.
- The work-on-behalf ticket is not read and not sent to wineserver.
- A receive never marks WORK_ON_BEHALF valid. No ticket value is invented.

## Consequences

- The host test checks the exact CoreMessaging shape (allocated
  0xe2000000, valid 0x22000000), the invalid-parameter case, and the
  reasons for SECURITY, VIEW and unknown bits.
- A static test checks that the receive path never marks the attribute
  valid.
- Native passes the sender's ticket to the receiver for priority and
  accounting. That is not reproduced. If a later caller needs real
  tickets, the Rtl ticket functions and a server field are the next step.
