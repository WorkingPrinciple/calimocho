# ADR-0050: Use the observed native CoreApplication lifetime ABI

## Context

This decision replaces ADR-0044's assumption that the public C++/WinRT
eight-slot IStaticLifetime declaration describes the complete interface
exposed by the OS CoreApplication factory for
`17b0e613-942a-422d-904c-f90dc71a7dae`.

The earlier public-source evidence remains valid for collection access.
C++/WinRT commit `30ac599beedc03d0f38f5fc84c390ee2f8551204` declares
GetCollection at slot7 and collection IID
`1b0d3570-0877-5ec2-8a2c-3b9539506aca`. Its factory cache uses the real
string/object map to retain factories. Those facts did not establish the
full OS-private factory ABI.

Actual017 exited with a read access violation at native XAML+57765e.
Static inspection proves that XAML calls slot11 with a callback and
64-bit token output, then slot12 with the token by value. The eight-slot
implementation instead reached the adjacent collection GetIids entry.
That wrong-ABI call overwrote the callback's vtable pointer.

Read-only inspection of the Windows CoreApplication factory now establishes
a nineteen-slot interface. The actual twinapi.appcore file version is
10.0.26100.9711, not the VM's OS build number. Its SHA-256 is
`000736bd54e9376e78ebe8eef87832606a058e0c2a1df290642177e7858b81a0`.
Factory builder3e7f0 and constructor3e930 associate CoreApplication with
the object. Full-IID comparison at24230/246fa returns object+68, whose
vtable is1a79c8. The next interface starts at1a7a60, after nineteen slots.

The local derived-facts JSON has SHA-256
`8c02195d96ddc0ee346be0019d40c2c9a04ffd5b4c7a243311e89207b2dc88b5`.
The corresponding local disassembly has SHA-256
`e33dbf81d35ffb1c5e37256ce5b5c979e89318a2c200b0ad3a3ab2f572e2142e`.
No proprietary binary or disassembly is redistributed. These are observed
argument shapes, not recovered public method names or universal Windows
version compatibility.

## Decision

Implement all nineteen entries for this factory's private interface. Keep
the IStaticLifetime source name for continuity, without claiming the public
eight-slot declaration is complete.

Slots6 and7 return the same genuine, retained PropertySet map. Preserve its
identity, initialization failure, key/value ownership and map operations.
Slot11 accepts an IUnknown callback and INT64 token output. Clear the token
first, retain the callback with AddRef, store it under the list lock and
return a unique nonzero 64-bit token. Slot12 accepts that token by value,
removes the matching registration and releases its retained reference.
Removing an absent token succeeds. External AddRef/Release calls occur
outside the lock. Run cleanup removes remaining registrations.

The list has32 entries. Capacity exhaustion or exhausted positive token
space returns E_OUTOFMEMORY with zero output and balanced references.
Tokens are opaque monotonically increasing integers, not raw pointers.
Registration does not invent callback delivery. Unlike observed Windows,
this narrow implementation does not marshal callbacks across apartments;
retaining an IUnknown does not prove apartment agility.

Unknown slots8/9/10/13-18 have typed entries. They clear their observed
output width and return E_NOTIMPL with a fixed SlotN fingerprint. Pointer
outputs are pointer-sized, slot14 writes one byte, and slot17 writes four
bytes. A null required output returns E_POINTER. No semantic names, fake
objects, handles or success results are inferred for these slots.

Generate diagnostic forwarders from the current IDL, not a sealed older
header. Preserve complete typed forwarding and fixed-name redaction.
Extend the fixture to guard callback retention and its untouched vtable.
Host tests exercise the actual callback implementation, capacity, token
reuse protection, reference balance and exact-width output canaries.

## Consequences

Build a fresh018 sibling and leave sealed012-017 unchanged. Retain017's
scoped exception capture, prefix-only Auto=0 import/readback, bounded
observation and cleanup rules. The runtime owner alone executes018.
Compilation and host tests do not establish native XAML progress or game
compatibility. A newly reached unsupported slot is an explicit next gap,
not permission to replace it with success.
