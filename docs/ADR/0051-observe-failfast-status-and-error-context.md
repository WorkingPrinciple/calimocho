# ADR-0051: Observe fail-fast status and error context

## Context

Actual018 called the corrected lifetime slot11 and returned S_OK. It no
longer retained the earlier XAML+57765e access violation. Native XAML
instead called RoFailFastWithErrorContextInternal2 from+33f121 and the
exact target handle observed exit0xc0000602.

The existing unhandled-filter hook did not capture that fail-fast path.
Neither its HRESULT nor a restricted error object was retained. No
failing owned COM HRESULT identifies the next missing behavior. A new
diagnostic cell is authorized, not a guessed implementation fix.

## Decision

Instrument the actual source-built combase export before its unchanged
RaiseFailFastException call. Retain the HRESULT argument and a validated
image basename plus module-relative return address. At that observed
entry, the collector copies the last30 admitted relays and last30 owned
COM events for that process. These are observed tails, not full stacks.

Instrument RoOriginateError, RoOriginateErrorW and
RoOriginateLanguageException with their input HRESULT and caller.
Instrument GetRestrictedErrorInfo and SetRestrictedErrorInfo with the
actual existing E_NOTIMPL stub return and caller. The latter do not have
an HRESULT argument. Do not dereference their error objects to invent
one. Leave all original return values and output behavior unchanged.

Replace diagnostic-site message/pointer dumps with fixed redacted text.
Do not decode strings, stowed exception information, error objects or
callback outputs. Reuse the existing bounded image-address formatter.

Source instrumentation is active only in the existing Run diagnostic
scope. Collector admission begins at Initialize entry and ends when
Run returns, or observation ends at target exit. Cap source events at32
fail-fast calls and512 other calls. Preserve the first32 fail-fast
records, a512-event context tail and explicit source-limit/overwrite
indicators. Every admitted record labels argument versus return HRESULT.

## Consequences

Use a new source-built019 sibling. Preserve018 and all older source,
recipe and actual-result identities. Keep the same prefix-only AeDebug
policy, no-input180-second budget, exact target-handle exit observer and
exclusive runtime owner. No automatic headless fixture or game launch.

The actual HRESULT may identify the next missing surface. It does not
alone establish a root cause, native UI acceptance or game compatibility.
No guessed fix is included in this diagnostic cell.
