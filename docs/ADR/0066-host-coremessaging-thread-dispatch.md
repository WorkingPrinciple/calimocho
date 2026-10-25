# ADR-0066: Host CoreMessaging thread dispatch in user32 and win32u

## Context

Whiny WX-01 found that native CoreMessaging 88c7b4d6 delay-imports three user32
ordinal stubs: #2541 GetQueueStatusReadonly, #2669 InitThreadCoreMessagingIocp2
and #2670 DrainThreadCoreMessagingCompletions2. It also delay-imports
GetQueueStatusForCoreMessaging and ScheduleCoreMessagingDispatch through
`ext-ms-win-rtcore-minuser-private-ext-l1-1-1`, which had no host.

The earlier Wine 11.0 lane at `wine-v20-src` commit `3ee99fb` reached
broker-visible NavigateToView with its own implementation. That code is
protocol evidence only. It was one launch, and one of its paths (Schedule
operation 2) called a stub that returned success.

## Decision

Add an opt-in `--coremsg-dispatch` port after the registrar port:

- win32u owns one CoreMessaging completion port per thread and two window
  slots. Slots are only accepted for windows of the calling thread and are
  released when the window is gone.
- Packets follow the retained protocol. The two marker values
  0x80000000/0x80000001 (zero- or sign-extended only) are control packets.
  A keyed zero context with a TEB wait entry links the wait node. A zero
  context without one sends `WM_COREMSG` (0x60) with wparam 3. Any other
  context sends wparam 8 with lparam set to the context.
- `NtUserMsgWaitForMultipleObjectsEx` waits on the completion port as an
  extra handle and dispatches packets before reporting message availability.
- Drain posts the wake marker only after it delivers a packet.
- The read-only queue status uses the server queue request with
  `clear_bits = 0`.
- Wine hashes apiset names without the final version number, so the existing
  `minuser-private-ext-l1-1-3` entry is hosted on user32. Adding a separate
  `l1-1-1` row is a duplicate-hash build error.

Unsupported behavior fails clean, not with success. Schedule operation 2
returns `ERROR_NOT_SUPPORTED`, because no native evidence shows its effect.
Wait-all with a CoreMessaging port also returns `ERROR_NOT_SUPPORTED`.

## Consequences

`package-coremsg-dispatch-02` builds win32u, user32 and apisetschema. A
`whiny inspect` of the native CoreMessaging against that source now reports 10
delay-load gaps instead of 15. The remaining gaps are the explicit combase
#86 to #88 fail-clean guards (ADR-0058), the sechost transient descriptor
and capability stubs, and the WinRT error stubs.

Host sanitizer tests cover the actual packet, slot, drain and read-only status
code. They are not proof of runtime dispatch or UI. The registrar remains
`registrar_qualified: false` (ADR-0065), so this does not admit cell027.
