# ADR-0058: Fail unsupported CoreMessaging ordinals explicitly

## Context

Native CoreMessaging imports combase ordinals86-88 on demand. The source-built
combase previously assigned these to CoCreateObjectInContext,
CoDeactivateObject and CoDecodeProxy. These Wine assignments do not identify
the native functions. The retained native combase has SHA-256
`ceb91292dac0e179a11e2364ccf9281e6384ae03cd87a965a85eae61045b1e89`;
its export table has no names for those three ordinals. No native signature
or implementation contract has been established.

Whiny WX-01 identifies fifteen delayed import gaps. Three user32 ordinals
are already explicit Wine stubs. The imported private minuser API-set family
has an empty host entry in Wine. No evidence supports implementing dispatcher
initialization, queue draining or scheduling by returning success.

## Decision

Reserve combase86-88 as non-name Wine unimplemented-export stubs. Their
diagnostic identifiers explicitly say they are unsupported ordinal guards,
not verified native function names. A call raises the normal Wine
unimplemented-export exception rather than invoking an unrelated function
or returning a fabricated HRESULT.

Pin the baseline combase specification hash and explicitly preserve every
other ordinal. Move only the three colliding named Wine exports to the next
free ordinals356-358; their names, signatures and implementations stay intact.
Simply adding explicit ordinal entries before automatic entries shifts all
automatic ordinals, so it is not an acceptable implementation.

Carry the generated WX-11 nineteen-slot lifetime wrappers into the new
source-built candidate. Retain emitter input hashes and source provenance.
Do not interpret the emitter contract as a native runtime observation.

Freeze this candidate as cell026 with a fresh026 run root. Bind the retained
owner decision record as supplied evidence, while leaving execution authority
with the existing driver owner. Do not edit the held025 receipt or execute
Wine, setup, activation, a fixture or a game in this source lane.

## Consequences

Host tests check actual staged PE exports, preserved named APIs and other
ordinal bindings, and the generated x64 stub identifiers and common handler.
The allocation test rejects the initial all-ordinal-shift implementation.
Whiny inspection still reports thirteen stubs and two unhosted imports, all
delayed; it must not be reported as complete dispatcher support.

The existing user32 and API-set gaps remain explicit unsupported paths.
Transitive reachability from CoreUICreate initialization remains unproven.
Only a separately authorized bounded execution can establish its first
reached failure. This change prevents a wrong-function call; it does not
make CoreUICreate, XAML initialization, the Xbox app or a game work.
