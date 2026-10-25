# ADR-0034: Isolate the generated claims observer diagnostic

## Context

The coordinator relayed owner approval for an isolated diagnostic build
after the source-only work in ADR-0032. The new purpose is narrowly to
replace the missing export abort and observe the next failure. It is not
package claims support.

The first supplied generator output incorrectly mapped process handle -1
to the native result observed for token handle -4. It was rejected without
building. The generator owner corrected the model and supplied replacement
SHA-256 `88f348929f5365edc0c885a02730156cc301c1aae7aae6f6fb2ddc4a3551c241`.
The generated source is retained unchanged.

## Decision

Build a separate copy of the selected source with the generated file,
`-DWHINY_NO_DLLEXPORT`, and an eight-pointer export declaration. Rebuild
only the x86_64 ntdll PE, preserving its existing Unix counterpart and
i386 module. Include neither the ADR-0032 patch nor the minidump overlay.

The table reproduces three exact observed handle values. It does not
validate a borrowed token, determine local package state, or enforce the
unpackaged observer context. Every other input remains unsupported.
There is no `WHINY_UNOBSERVED_STATUS` override.

Copy the private performance install into a new owned directory and
replace only its x86_64 ntdll. Compare all installed files and links.
Emit a distinctly named diagnostic registry with smoke status `not-run`;
do not inherit a historical qualification as candidate proof.

## Consequences

The candidate is an observer-table diagnostic, not native parity for
packaged Xbox tokens, a supported engine release or product acceptance.
The registry is explicitly unqualified. The Xbox owner must adapt its
owned fresh-cell launcher to the exact binding, preserving setup,
timeout and cleanup; the historical hardcoded a5 command cannot select it.

The supplied parity PE is linked to the candidate export but is not
executed on the local ntdll by this build-only slice. Windows-side native
and generated parity reports, when authenticated, remain separate from
local loaded-module qualification. Accepted engines and existing prefixes
remain unchanged.
