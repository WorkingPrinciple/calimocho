# ADR-0030: Capture FH6 fault bytes without changing exception behavior

## Context

REQ-108 diagnostic run 92ce1731 reproduced the startup illegal instruction
at 0x1453076BC. The game registered a vectored exception handler, which
returned continue-search. The retained executable establishes disk bytes,
not the bytes present in memory when the fault occurred.

COR-148 authorizes one isolated diagnostic build and serialized launch.
The program coordinator owns the canonical requirements and launch policy.
The existing Wine syscall channel already records service names,
arguments and return statuses.

## Decision

Build an isolated ntdll Unix overlay on the frozen 11b runtime. Before the
existing invalid-opcode dispatch, read at most 16 instruction bytes through
Wine's permission-checked, uninterrupted memory reader. Log the byte count,
bytes, instruction pointer, stack pointer and code segment on the existing
seh channel. Preserve all exception dispatch and return behavior.

Reuse the seh handler logs and syscall channel rather than changing
handler code, syscall tables, dispatcher assembly or game bytes. Freeze
source, build and registry evidence and obtain S2 diagnostic admission
before the separately authorized launch. Do not replace installed files
or modify another contributor's source or build.

## Consequences

The next capture can distinguish disk bytes from fault-time memory bytes.
Tracing changes timing and is not a fix or a gameplay qualification.
No protection bypass, CPU instruction emulation or graphics workaround
is authorized by this decision.
