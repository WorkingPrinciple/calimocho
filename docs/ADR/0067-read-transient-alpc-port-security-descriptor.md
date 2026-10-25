# ADR-0067: Read the transient ALPC port security descriptor in sechost

## Context

Cell033 started the CoreMessagingRegistrar svchost with the scoped token
(ADR-0065). ServiceMain reached `RegisterServiceCtrlHandlerExW`, but the
service stayed START_PENDING. The svchost thread then aborted in the Wine
stub `sechost!QueryTransientObjectSecurityDescriptor` (services-start.log
line 741). CoreMessaging asks for the security descriptor of its server
port before it creates `WM_RegistrarServer`.

svchost also printed a FIXME about `SvchostPushServiceGlobals`. In
coremessaging.dll 88c7b4d6 that export is only `ret 0`, so it does not
block the service.

The app side then hit the Wine stub `sechost!WaitServiceState` after its
connect failed.

The earlier lane's builtin relay log (`~/xbox-install/h185.broker.log`)
shows the call shape: type 8, name `WM_RegistrarServer`, and a returned
heap buffer of 0x108 bytes. The descriptor is stored in
`HKLM\Software\Microsoft\SecurityManager\TransientObjects`, under the key
`%5C%5C.%5CAlpcPort%5CWM_RegistrarServer`, as the REG_BINARY value
`SecurityDescriptor`. This is design evidence only. The failure convention
of the native function is not measured.

## Decision

Add a sechost port to the `--registrar-service` build:

- `QueryTransientObjectSecurityDescriptor` admits only type 8 (ALPC port)
  and a plain name. It reads the registry value and requires REG_BINARY and
  a valid self-relative descriptor. It returns a heap copy. Any other type
  or name prints `FIXME reason=transient_type` and returns
  STATUS_NOT_IMPLEMENTED. A missing key or value returns the registry
  status unchanged.
- `FreeTransientObjectSecurityDescriptor` frees that copy.
- `WaitServiceState` follows the documented winsvc.h contract. It polls
  `QueryServiceStatusEx` every 50 ms. It returns the reached state, or 0
  with ERROR_TIMEOUT, ERROR_CANCELLED or the query error.

Cell034 registers the 264-byte descriptor. It was re-authored from the
values in a CrossOver-derived prefix and contains no machine SIDs. Its DACL
has 8 ACEs (OWNER RIGHTS, INTERACTIVE, Authenticated Users, SYSTEM,
Administrators, one S-1-5-32 SID with 8 extra subauthorities, ALL
APPLICATION PACKAGES and one capability SID). The receipt adds
`registrar_transient_readback_argv` so the driver can check the value
before starting the service.

The ALPC connect FIXMEs now print one fixed `reason=` token, and a hex
`value=` where useful. The collector keeps only that token and value.
Incoming message attributes are accepted and returned with
`ValidAttributes = 0`. Outgoing attributes still fail with a FIXME.

## Consequences

Host sanitizer tests cover the real sechost code against a mocked registry
and service status. They do not prove that the registrar reaches RUNNING.
The origin of the S-1-5-32 SID in the descriptor is not known, and the
token still lacks the eight measured S-1-5-32 groups. If CoreMessaging
needs them for access, the connect should fail with a native access
status, not succeed.
