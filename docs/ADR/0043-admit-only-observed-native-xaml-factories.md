# ADR-0043: Admit only observed native XAML factories

## Context

Actual010 selects native XAML and its Application factory succeeds.
FrameworkViewSource is requested next but has no registered server.
The observed Registry64 export from Windows26300.9711 maps that class to
system32 Windows.UI.Xaml.dll. The export contains851 classes and18 hashed
DLL targets, but its XAML SHA-25667d90ad2 differs from the retained original
16302bfe. A matching basename does not establish matching implementation.

The owner approved probing the retained DLL's real factories against the
exported XAML class names, then mapping only observed supported classes.
This is an explicit cross-build diagnostic exception, not a same-build claim
or permission to bulk-import unproven classes. Headless factory probing in
a private prefix does not require the game's input/display lane.

## Decision

An owned probe loads the exact prefix system32 XAML DLL, calls its genuine
DllGetActivationFactory for each bounded class name and queries the returned
object for IActivationFactory. The matrix mode does not call ActivateInstance,
CoreApplication.Run, display a window or change registration. Record fixed
index, HRESULT, presence and summary fields, bound to the exact class list,
probe binary and retained native DLL identity.

Accept only a complete, unique, consistent matrix. A failed or missing row
is not support. Register only observed supported Windows.UI.Xaml classes
whose exported target is that exact system32 DLL. Preserve observed value
names and types, including numeric Threading; do not invent ThreadingModel.
Label the result "cross-build mapping: native export26300.9711 to retained
16302bfe, support observed by probe". Factory support alone does not establish
ActivateInstance or application behavior.

Other exported targets require exact native hash evidence before selection.
Absent or mismatched native DLLs remain explicit decisions, never redirected
to XAML. Keep Wine009 CoreApplication and CoreWindow where no matching native
target is admitted. Do not install, copy or rewrite any native DLL here.

The resulting011 recipe uses the same frozen009 engine, explicit native
override and bounded010 collector, in a fresh private prefix. Preserve
sealed010 and retain first missing factory/IID/method as the next result.

## Consequences

The Windows export is useful mapping evidence but not portable ABI proof.
The matrix scales the exact missing-class investigation without fabricating
native implementations or launching hundreds of runtime objects.
Only actual probe output can authorize the supported-class list.
Source checks and compilation do not replace that observation or011 execution.
