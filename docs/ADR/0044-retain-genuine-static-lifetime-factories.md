# ADR-0044: Retain genuine static lifetime factories

## Context

Actual011 activated native XAML Application, FrameworkViewSource and
FrameworkView successfully, then queried CoreApplication for
`17b0e613-942a-422d-904c-f90dc71a7dae`. The local factory returned
E_NOINTERFACE and AppL fail-fasted with0xC0000602. No window or application
activation callback was observed. The011 evidence is sealed.

The IID is not a Windows.ApplicationModel.Core metadata interface.
Microsoft's C++/WinRT source identifies it as IStaticLifetime:
[base_abi.h](https://github.com/microsoft/cppwinrt/blob/30ac599beedc03d0f38f5fc84c390ee2f8551204/strings/base_abi.h).
Its IInspectable ABI has a reserved method followed by GetCollection.
The same source defines collection IID
`1b0d3570-0877-5ec2-8a2c-3b9539506aca`, whose slots match the string/object
map's Lookup, Size, HasKey, GetView, Insert, Remove and Clear.

The caller in
[base_implements.h](https://github.com/microsoft/cppwinrt/blob/30ac599beedc03d0f38f5fc84c390ee2f8551204/strings/base_implements.h)
obtains that collection from CoreApplication, looks up the runtime class,
and inserts a real retained factory when missing. Microsoft's
[factory cache test](https://github.com/microsoft/cppwinrt/blob/30ac599beedc03d0f38f5fc84c390ee2f8551204/test/old_tests/UnitTests/factory_cache.cpp)
also queries IMap of string and IInspectable and clears the store.
All three pinned source URLs were fetched successfully. No private ABI
is inferred from binary offsets or guessed from the CoreApplication name.

Re-fetched source identities at the pinned commit:

| File | SHA-256 |
| --- | --- |
| `strings/base_abi.h` | `ccbadb65527e8e97dfaa646947fb463cbf061b168eb198b709fddd35b1084dc7` |
| `strings/base_implements.h` | `b7869ec74f826ff9cc13bf6ce74988842fb47e55ff59eab60e924a87cebd28e1` |
| `test/old_tests/UnitTests/factory_cache.cpp` | `f34f902f046074a0409571863ba7a563e705a8138666963b6bf26061745b15d1` |

## Decision

Implement the exact IStaticLifetime interface on the CoreApplication factory,
with a distinct vtable and shared COM identity/reference count. GetCollection
returns a stable process-lifetime collection. Its custom collection IID and
real IMap IID select the same actual map ABI, not an unrelated IUnknown.

Delegate storage, key duplication, value retention, replacement, lookup,
removal, clearing and map views to Wine's existing multi-threaded PropertySet
map. A process-lifetime reference keeps the store alive across caller releases.
The wrapper preserves one COM identity for its admitted interfaces. Initialize
once and retain the actual failure HRESULT rather than silently returning an
empty success. Do not log class keys or values.

The reserved method has no documented semantics. It returns E_NOTIMPL and a
fixed missing-method fingerprint. Other unknown interfaces remain explicit
E_NOINTERFACE. Factory support does not imply invented lifecycle behavior.

Build a new012 sibling and preserve frozen009 and sealed010/011. Reuse011's
558 observed native XAML mappings, original native DLL setup, exact package
graph and bounded exit observer. Rebind every engine/helper/collector/import
command to the new install where necessary. The newly compiled six modules
have distinct identities even where their source behavior is unchanged.

The owned fixture has a separate headless static-lifetime mode. It checks
both collection IIDs, stable identity, missing-key errors, retained lookup,
replacement, removal and clearing. Its original window mode remains separate.

## Consequences

Source/build and collection contract evidence remain separate from native
XAML execution. The implementation does not alias the unknown IID to
ICoreApplication or return unconditional QueryInterface success.
Actual012 must establish whether native XAML progresses past this cache
request and expose the next real missing surface.
