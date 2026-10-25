# ADR-0033: Forward the minidump API set to dbghelp

## Context

The DIRT 5 run `d84750b1` failed while loading `game_release.exe` because
`api-ms-win-core-debug-minidump-l1-1-0.dll` was missing. The coordinator
reported loader status `c0000135` and process exit 53.
Selected WineHQ 11.20 source has both minidump exports in dbghelp but no
matching API-set mapping in `dlls/apisetschema/apisetschema.spec`.

## Decision

Add an explicit data-only forwarding module using Wine's spec and
`-Wb,--data-only` convention. Forward both functions to existing dbghelp,
preserving its argument declarations. Do not substitute successful no-ops
for dump operations.

Build the module with existing local Wine tools for x86_64 and i386. Copy
the frozen private performance install into a new owned sibling and add
only these two DLLs. Preserve the performance environment in the build
receipt. Do not edit the accepted source, installs or registry records.

This standalone overlay avoids regenerating the accepted API-set schema.
A future integrated Wine build must register the directory with configure,
or use a centralized schema mapping, rather than assume this overlay is
automatically included in the ordinary Wine build.

## Consequences

The builder records source, tool, command and DLL hashes and compares every
copied file with the frozen base. Build success is not runtime qualification
or DIRT 5 compatibility. Before admission, the new sibling needs loader
resolution checks and the existing graphics/TLS qualification, with an
exclusive native interval. No package-claims candidate is included.
