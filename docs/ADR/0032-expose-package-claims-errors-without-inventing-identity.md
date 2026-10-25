# ADR-0032: Expose package claims errors without inventing identity

## Context

Native Windows.UI.Xaml imports `ntdll!RtlQueryPackageClaims`, which is absent
from selected WineHQ source `7298a818b79446bae153b8d5aa27235ab3703bf9`.
The owner approved a limited source-only export after reviewing the missing
token-attribute substrate. This is not authorization for a build or launch.

The sole Windows operator's finite reference observed 15 calls on OS build
26300, ntdll 10.0.26100.9711. NULL and an invalid literal handle returned
`STATUS_INVALID_HANDLE`. The current-process-token pseudo handle returned
`STATUS_NOT_FOUND` in that independently observed unpackaged process.
Supplied attributes were zeroed even on failure. Other supplied buffers and
byte lengths remained unchanged for the tested 0, 2 and 512-byte capacities.

Reference receipt SHA-256:
`a43b39909feff2c462759c2a7769447f5fda283096a6ec34243b912938cc991f`.
Submitted source SHA-256:
`71ba534ade0c71e291abc41ea1afe5b5e8113d49cef4bee72d153a4d149045d1`.
Native ntdll SHA-256:
`651ac9041af8e6b5ebd331d53163244c0a27d36d1433f0f15cac1f28c5f2e82c`.
These observations do not establish packaged-token, denied-access or all
optional-pointer semantics.

## Decision

Keep the selected source and installed runtimes unchanged. Retain an opt-in
patch against the exact WineHQ pin, outside automatic build selection.
Clear optional attributes first. Validate the borrowed local token through
`NtQueryInformationToken(TokenType)`, whose server path checks object type and
`TOKEN_QUERY`. Return its actual error. Query real `TokenSecurityAttributes`
with a size-only request and propagate its actual error.

The selected source returns `STATUS_NOT_IMPLEMENTED` for that query.
Do not translate missing support into `STATUS_NOT_FOUND`. If the query ever
succeeds, still report unsupported decoding rather than return blanket
success or claim identity. Do not modify package/app buffers, lengths, GUID
or claim output, acquire a replacement token, or close the borrowed handle.

## Consequences

This candidate supplies an export and honest error propagation, not working
package claims or a demonstrated Xbox/XAML fix. Source regressions compile
the actual added function against a mock query, exercising ordering, status
propagation, nullable outputs and sentinel preservation. They neither load
Wine nor query a real token.

A future runtime candidate needs separate build authorization and exact
provenance. Native execution and admission remain separate. Real package
support needs genuine local token attributes and a separately established
decoding contract, not identity copied from a Windows observer.
