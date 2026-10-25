# ADR-0042: Select retained native XAML explicitly

## Context

Actual cell009 reached the `msxboxl` route, started AppL with S_OK and loaded
native XboxPcApp.exe. Its next observed factory request was
Windows.UI.Xaml.Application, IID `06499997-f7b4-45fe-b763-7577d1d3cb4a`,
which returned CLASS_E_CLASSNOTAVAILABLE. The trace identified the loaded
Windows.UI.Xaml.dll as builtin despite a retained native file in the prefix.
The009 recipe omitted the native override used by controlled cells002/003.
No CoreApplication event or window result was observed, so this is not
evidence that their new interfaces failed.

The owner approved a separate010 loader discriminator using the same009
engine, retained native-XAML setup and a180-second AppL observation bound.
The original DLL is already retained by the consumer. It is not a Calimocho
redistributable, a CrossOver payload to copy or a binary to rewrite here.

## Decision

Derive a new recipe and registry with explicit `windows.ui.xaml=n`, preserving
unrelated override settings. The retained002/003 set adds no other native
XAML sibling override. Their explicit registration sets only DllPath for
Windows.UI.Xaml.Application to `C:\Windows\System32\Windows.UI.Xaml.dll`.
Do not invent ThreadingModel or change the other builtin class registrations.
Bind the retained setup artifacts and original native DLL hash in the new
receipt. The consumer performs its existing explicit fresh-prefix setup.
The producer neither copies nor rewrites any Microsoft binary.

Reuse the exact frozen009 install, package snapshot and process identity
table. This is a recipe, not another engine. Preserve sealed008/009 and use
a fresh010 prefix and evidence directory. No ABI implementation is justified
by the builtin loader failure.

The changed collector records native/builtin kind and exact module path only
when that path matches the receipt's public XAML allowlist. Unknown paths
are redacted. Track both Windows.UI.Xaml and Microsoft.UI.Xaml by PID.

An additional owned observer opens only the recorded AppL PID, verifies its
exact executable and server-admitted AppId token, then waits on that process
handle. A signaled handle plus GetExitCodeProcess records actual exit.
An exit call alone or CE exit never substitutes for that observation.
Observer startup failure, identity mismatch, an already-gone target or the
owner-set180-second cap leaves exit unknown. A remaining pipe-drain cutoff
is explicit rather than claiming complete capture.

## Consequences

The current cell009 result establishes a real local process handoff, not
successful UWP event delivery, XAML startup or UI. Its60-second truncated
capture stays sealed. Cell010 has a separate observer and collector identity
and must prove native loader selection before a missing factory is interpreted
as an ABI gap. No input, foreign-prefix mutation or DIRT5 control is added.
