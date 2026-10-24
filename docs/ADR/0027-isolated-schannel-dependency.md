# ADR-0027: Isolated source-built schannel dependency

## Status

Accepted for the coordinator-directed TLS runtime slice, 2026-10-24.
No game, input, account, shared-registry or system-security action is added.

## Context

The source runtimes were configured without x86_64 GnuTLS and explicitly
reported no schannel support. A coordinator-owned game attempt failed
online activation, but that alone does not prove TLS caused its error.
An owned WinHTTP HTTPS GET on unchanged port-09 independently fails at
WinHttpSendRequest with `0x80090305`, alongside the missing-schannel message.

TLS is a normal Windows networking capability, independent of a game's
activation protocol. The runtime must provide it without weakening
certificate checks or copying a proprietary runtime.

## Decision

Pin official GMP, nettle, libtasn1 and GnuTLS source archives in
`versions.json`, with independently published SHA-256 checksums. Build
x86_64 shared libraries into one owned dependency prefix using installed
tools. Retain source licences, configure/build/install logs and library
hashes/linkage. Use GnuTLS's included unistring; omit p11-kit and optional
internationalized-domain-name support for this bounded ASCII-host probe.
Do not install global packages or change system trust.

Extend the existing Wine builder with an explicit `--tls` prefix.
Configure must find its headers and emit the selected GnuTLS SONAME.
Use `@rpath` and an explicit owned-library LC_RPATH rather than relying
only on dyld's basename fallback. Retain the TLS lib directory alongside
FreeType in the runtime search-path recipe. Absolute dependency references
inside that isolated prefix remain local-only; this is not a relocatable
distribution.

Following the coordinator's urgent narrowing, configure fresh pinned WineHQ
source with the same native-GS transformation, but build only secur32,
bcrypt and crypt32. Overlay their PE pairs and the two Unix modules onto
a copy of port-09. Current WineHQ has no `bcrypt.so`. Preserve the existing
core, required loader-linked time helper and read-only GPTK symlink layout.
Leave the qualified port-09 and CW installs untouched. Do not copy or
re-sign Apple payloads.

Use an owned PE WinHTTP probe to GET `https://www.microsoft.com/`, require
HTTP 200 and print the status/error. Keep ordinary certificate validation
enabled. Test `https://expired.badssl.com/` separately and require evidence
of certificate-date rejection, not just a transport failure. Run in fresh
prefixes with bounded timeouts. Deliver the verified local TLS record
immediately, then add the two presentation/readback observations and
persist a separate sanitized schema-version-1 record.

## Consequences

The new local registry must bind the entire TLS dylib closure, actual Wine
loader, schannel module, helper, renderer, sources and observed receipts.
No prefix or hidden engine fallback belongs in its launch environment.
The public placeholder record is evidence, not executable configuration.

A passing HTTPS probe establishes TLS capability for that request, not
successful game activation, identity/account readiness or game rendering.
The coordinator owns any game retest and canonical acceptance. Rebuilding
the CW baseline is optional only if cheap; preserve its existing evidence
instead of silently changing the known comparison runtime.
