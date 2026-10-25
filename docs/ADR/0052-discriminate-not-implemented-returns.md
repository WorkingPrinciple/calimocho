# ADR-0052: Discriminate not-implemented returns

## Context

Actual019 observed RoFailFastWithErrorContextInternal2's HRESULT argument
`0xd0000002`, with no admitted restricted-error origin. The hook's return
site was ntdll+10e03; the independent relay's caller was XAML+33f121.
These are distinct observations.

Disassembly of the exact019 combase export shows `mov r8d,ecx` before
ECX is reused and the diagnostic helper is called. The captured argument
is not demonstrated register corruption. Pinned Wine headers define
STATUS_NOT_IMPLEMENTED as0xc0000002 and HRESULT_FROM_NT as adding the NT
facility bit, yielding0xd0000002. This identifies a status family, not
the originating API.

Twinapi+9031 is the return site of AcquireSRWLockExclusive inside the
already-instrumented AddCallback implementation. CoreApplicationView's
eleven-slot public interface, including slots6-10 and every QI, already
has typed entry/exit logging. No requested View2/3/5/6 QI was observed;
unknown interfaces remain E_NOINTERFACE, not invented longer tables.

## Decision

Use the existing Wine app-qualified debug syntax
`XboxPcApp.exe:fixme+all`. The exact pinned parser compares the executable
basename after the colon prefix. Debug emission is enabled for that
process's lifetime, while the collector retains only actual Run-scoped
function/channel fingerprints. Drop all FIXME arguments and messages.
Keep the first128 fingerprints with an explicit not-retained count.
A FIXME is not automatically a failing status or the cause.

Add a filter at actual x64 relay return. When the low32 bits equal
0xc0000002 or0xd0000002, retain export name and validated image-relative
caller. Expand thunk admission for this diagnostic mode, not normal
entry logging. Source cap128 and collector tail128 have explicit loss
markers. Independently retain typed owned-COM HRESULT0xd0000002 results.

Wine's x64 relay return encoding does not distinguish pointers from
status values. Label relay rows as matching bits, not guaranteed HRESULTs.
Norelay exports, direct syscalls and native-to-native bypasses are not
covered. Absence of a matching relay row does not clear those paths.
Keep019's exact fail-fast HRESULT/caller capture and tail binding.

## Consequences

Build a fresh020 sibling with no functional fix. Preserve019 and every
predecessor. The exclusive runtime owner performs once-only no-input
observation, capped180 seconds, under the same prefix policy and cleanup.
Do not decode stowed objects or add speculative interfaces. The first
retained FIXME or matching status is a lead requiring source correlation,
not automatic proof that implementing that stub completes XAML.
