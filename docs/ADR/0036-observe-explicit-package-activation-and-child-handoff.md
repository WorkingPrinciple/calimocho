# ADR-0036: Observe explicit package activation and child handoff

## Context

The Xbox owner reported that cell004's helper exited zero after about
0.75 seconds without observed CE process or handoff telemetry. That is not
evidence of XAML loading, sign-in or successful Xbox activation. The previous
helper returned the child exit code without reporting its process identity.
The owner approved a bounded diagnostic on the same isolated package engine.
Canonical program requirements remain in `dragos-core projects/ode-to-x/SPEC.md`.

## Decision

Add an explicit `--activate-diagnostic` helper mode. Record the actual
`NtCreateUserProcess` image, command line and current directory, creation
status and child PID. While the child is suspended, query its token through
the existing server-owned identity seam. Record the returned full name,
family, AppId and verified flag, rather than echoing the input identity.
A failed token query stops and terminates only that owned child.

Set `WINEDEBUG=err+all,trace+process,trace+loaddll,+pid,+tid` in a private
environment for that child only. The helper's environment remains unchanged.
Explicitly inherit a duplicate of the collector's stderr handle for both
child output streams; keep helper metadata on stdout. The original helper
did not explicitly provide these standard handles.

`tools/diagnose_package_activation.py` drains both streams without saving
raw application output. It retains allowlisted helper fields, counts error
and process events, and records only PID, basename and native/builtin type
for XAML and the two Xbox executables. A XAML load counts for the CE child
only when its Wine PID matches. A different process's module load is separate
handoff evidence, not proof that the CE process loaded it.

Parsing is limited to 8 MiB of trace data and 16 KiB per line, while excess
data is still drained to avoid blocking the child. The collector has a
60-second outer limit. Truncation changes an absent XAML observation to
unknown, never a positive result. No raw XGAMERUNTIME channel is enabled.

The helper waits up to 45 seconds, records its wait result, child exit code,
process exit UTC and observation UTC. At the limit it reports still-running
before requesting termination of that specific process. A resume error also
terminates that owned child instead of leaving it suspended. This remains a
finite diagnostic, not a general launcher.

Keep cell004's helper, engine, registry and signed snapshot immutable.
Deliver a new v3 helper and cell005 receipt, with a new owned cell005 prefix
and evidence directory. Server registration and native XAML prefix setup
remain explicit Xbox-owner steps, not collector side effects.

## Consequences

The source tests distinguish helper success from actual creation/resume,
match module loads by PID, reject duplicate metadata, exercise redaction
and large-output draining, and verify the collector timeout.

Fresh headless fixture08 and fixture09 each passed plain identity, packaged
identity, different-image eligibility and guest-spoof rejection. The native
diagnostic recorded successful creation/resume, actual token metadata,
child-only tracing, process events, exit code 17 and a process exit UTC.
The synthetic host registration test does not establish GamingApp trust.
Both candidate-owned servers were stopped afterward.

Those fixtures open no windows and do not load native XAML. They do not
answer whether the real CE executable starts or hands off successfully.
Cell005 execution and product verdict remain with the Xbox owner.

## Reproduction boundaries

The v3 helper was built with the installed compiler and the frozen candidate's
headers and import libraries. Use a new output filename for any rebuild;
never replace a handed-off helper.

```bash
candidate=build/winehq-11.20/package-identity-01
x86_64-w64-mingw32-gcc -std=c11 -Wall -Wextra -municode -D__WINESRC__ \
  -I"$candidate/source/include" tests/package_activation_probe.c \
  "$candidate/build/dlls/ntdll/x86_64-windows/libntdll.a" \
  "$candidate/build/dlls/kernelbase/x86_64-windows/libkernelbase.a" \
  -ladvapi32 -lkernel32 -o "$candidate/package-activation-probe-NEW.exe"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_activation_diagnostics
```

The cell005 receipt supplies the exact activation argument vector, app working
directory, collector command, output path and ordered server setup. Invoke
the collector rather than writing raw helper stderr to an evidence file.
It checks the helper, collector, registry and core deployed engine hashes
before activation. The app result is written with exclusive creation, never
over an earlier receipt.

## Cell005 correction

The real cell005 run created and resumed CE PID 240 with verified server
metadata. It loaded the native CE executable and exited zero at
`00:47:29.009Z`, about 89 milliseconds after creation. Only that module load
was observed, not XAML. Stream EOF was not received within 60 seconds, despite
only 8,756 bytes. This does not establish why the stream stayed open or an
application hang. Returning zero from the collector on that incomplete
capture was wrong.

The next collector records structured PID/channel/function error fingerprints,
fixed message classes and explicitly labelled numeric statuses. Process-create
facts retain returned child PIDs and allowlisted Xbox image basenames.
Sync entry traces retain only the named-object namespace class; they do not
establish that an existing object was successfully opened. AppLifecycle
activation is classified without retaining arbitrary class names. The child
adds sync/combase tracing and combase FIXME events, because this source's
RoGetActivationFactory entry is a FIXME.

After helper process exit, or the complete child-exit record if earlier, the
collector drains for two seconds. The receipt identifies which observation
started that bound. Missing EOF then yields a separate post-exit-drain limit,
truncated/unknown evidence and a nonzero collector result. This is not proof
of a leaking handle or the owning process. It does not raise a byte limit that
was never reached. Existing cell005 evidence and helper bytes are preserved.
