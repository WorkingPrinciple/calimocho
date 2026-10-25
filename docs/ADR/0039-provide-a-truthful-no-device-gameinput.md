# ADR-0039: Provide a truthful no-device GameInput

## Context

The Witcher execution owner reports a startup null singleton in the input
and haptics path. Its executable dynamically loads GameInput and resolves
GameInputInitialize and GameInputCreate. The exact Wine 11.20 source has
only a GameInputCreate stub returning E_NOTIMPL, and its spec exports no
GameInputInitialize. Disabling the builtin did not remove the game's fault
in the owner's observation. This establishes an API gap, not proof that
GameInput is the only cause of the game crash.

The owner authorized a truthful implementation that initializes successfully
but exposes no physical devices, with headless testing in an isolated
AGS/minidump sibling. The existing qualified 11d runtime and game prefixes
must not change.

## Decision

Implement the exact v0, v1 and v2 interfaces in Wine's pinned gameinput.idl.
Use separate compiler-checked interface vtables sharing one COM identity
and reference count. v0 has extra slots and different callback signatures;
do not cast a v1 or v2 table into it.

GameInputCreate creates v0. GameInputInitialize accepts those interface IDs
and IUnknown, clears failed outputs and rejects unknown interfaces.
GetCurrentTimestamp uses QPC converted to microseconds without multiplying
the entire counter into an overflowing intermediate. Initialization fails
explicitly if its frequency is unavailable.

There are no device or reading objects. Reading queries clear the output
and return READING_NOT_FOUND. Valid find requests and aggregate creation
return DEVICE_NOT_FOUND. Missing required output pointers are errors.
Blocking enumeration produces no device notifications, rather than
pretending that a controller or keyboard exists.

Registrations receive actual unique managed tokens, synchronized by the
owning object's lock. They never invoke user callbacks because there are
no devices. Stop has no in-flight work to drain; unregister removes a valid
registration, and an unknown token returns false. Final release frees all
remaining registrations. An empty dispatcher owns an unsignaled event,
returns no pending work and duplicates a wait handle for the caller.

Unsupported OEM device integration reports E_NOTIMPL. No undocumented COM
class ID is invented: DllGetClassObject reports CLASS_E_CLASSNOTAVAILABLE,
clears its output and directs callers to Initialize/Create. DllCanUnloadNow
tracks actual input and dispatcher objects.

Build only a new x64 sibling, replacing its single gameinput.dll and
preserving all renderer, AGS and minidump bytes. The module keeps native
preference unless a title-scoped recipe explicitly selects the builtin.
Witcher's later recipe must embed `gameinput=b` rather than depend on an
external override that the registry would replace. Do not add an AGS6
claim or override the owner's existing native per-prefix AGS shim.

## Consequences

This is initialization and honest empty input support, not working
controllers, keyboard/mouse enumeration, vibration, haptics or OEM support.
Games that require a physical GameInput device may still refuse to start.
There is no game-specific crash suppression or fabricated reading.

The headless probe checks the old export/stub failure, all interface
identities and versioned slots, empty readings/finds/enumeration, token
registration/removal, dispatcher handles, timestamp scale and object
lifetime. Typed sources and the probe compile with warnings treated as
errors against the exact generated Wine ABI header. The PE exports exactly
Initialize, Create, DllCanUnloadNow and DllGetClassObject and imports no
renderer or user32 dependency.

Compilation and source checks do not establish installed behavior or
Witcher title-screen acceptance. Native fixtures wait for the scheduler's
explicit between-game slot. The execution owner owns the later game run.
