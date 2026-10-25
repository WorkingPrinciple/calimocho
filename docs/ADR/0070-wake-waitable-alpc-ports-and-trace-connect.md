# ADR-0070: Wake waitable ALPC ports and trace the connect

## Context

Cell036 ran once. The registrar was RUNNING and the app connect was no
longer rejected. But the registrar logged no received connection after its
first NtAlpcSendWaitReceivePort, and the app still exited with the
CoreMessaging fail-fast 0xE0464645.

The registrar port is created with flags 0x70000. Bit 0x40000 is
`ALPC_PORTFLG_NON_BLOCKING_RECEIVE` in Wine's `winternl.h` (phnt calls it a
waitable port). With it, a receive on an empty queue returns
STATUS_UNSUCCESSFUL. CoreMessaging expects that: the receive site at
+0x277b compares the status with 0xc0000001 and returns quietly. It then
waits again through NtCreateWaitCompletionPacket,
NtAssociateWaitCompletionPacket (call sites +0x3bd3 and +0x2272e) and
NtRemoveIoCompletionEx.

Our wineserver accepted only event, timer, semaphore, thread and process
objects as wait-packet targets. An ALPC port got
STATUS_OBJECT_TYPE_MISMATCH, so the registrar was never woken for the
queued connect. The target handle being the port is inferred from the
call sequence, not traced.

The collector could not see NtAlpc* statuses, because syscall exports
bypass relay, and it did not record the fail-fast record.

## Decision

- The wait-packet association accepts any ALPC port target. The port's
  existing signal state (queued message, or a client reply) wakes it.
- A telemetry porter, applied last, adds bounded and redacted traces:
  - every ntdll unix NtAlpc* return, with a fixed target class
    (`registrar`, `registrar-relative`, `other`, `none`), on pkgstatus and
    on the alpc channel; port names are never printed;
  - the RaiseFailFastException record in kernelbase, on pkgexception:
    code, flags, parameter count, address as module+offset, and each
    parameter as a 32-bit scalar or module+offset;
  - wineserver lines on stderr for connect, connect result, accept,
    receive, queue (with waiter presence) and wait-packet association.
- The collector keeps these as `alpc_returns` and as fail-fast rows in
  `unhandled_filter_exceptions` with stage `raise-failfast-entry`.

## Consequences

Cell037 shows whether the registrar now receives and accepts the connect,
and if the app still fails, which ALPC status and which fail-fast record
come first. Whether native allows ports without the waitable flag as
wait-packet targets is unmeasured. kernelbase.dll is now rebuilt and
staged; its exports are unchanged.
