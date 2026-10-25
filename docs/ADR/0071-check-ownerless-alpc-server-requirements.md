# ADR-0071: Check ownerless ALPC server requirements

## Context

Cell037 ran once. The registrar re-armed its port wait (wait-packet
association status 0). Both app NtAlpcConnectPortEx calls then returned
STATUS_SERVER_SID_MISMATCH (c00002a0). The wineserver confirmed this, with
no handle and no queued connection.

CoreMessaging builds its ServerSecurityRequirements from this SDDL string
(read for understanding only, nothing copied into code):

```text
D:(A;;0x01;;;S-1-5-80-1021139062-1866602279-1255292388-1008060685-2498416891)
```

That SID is the CoreMessagingRegistrar service SID: SHA1 of the uppercase
UTF-16LE service name, unpacked as five little-endian DWORDs. Our registrar
token already holds this SID as an enabled group (attributes 0xe) and as a
restricting SID.

The descriptor has a DACL but no owner and no group. ADR-0061 checked it
with `token_access_check`, which follows the user-mode AccessCheck rule and
returns STATUS_INVALID_SECURITY_DESCR when the owner or group is missing.
So every connect was reported as an identity mismatch.

## Decision

`token_alpc_identity` evaluates port connect access (1) itself:

- no DACL, or a NULL DACL: access 1 is granted;
- otherwise, ACEs are walked in order, skipping inherit-only ACEs. A deny
  ACE for a SID the token holds (deny-only groups count) removes access 1.
  An allow ACE for an enabled SID grants access 1;
- the result then goes through the existing restricting-SID check, so
  restricted and write-restricted tokens are still enforced.

Ownership never grants access 1 (it only adds READ_CONTROL and WRITE_DAC),
so leaving out the owner and group does not change the result for this
check. The SID form (`RequiredServerSid`) is unchanged.

The freezers admit cell038 (`-ownerless-server-identity`).

## Consequences

- The registrar shape now matches, and a token without the service SID
  still gets STATUS_SERVER_SID_MISMATCH. The host test
  `tests/restricted_token_host.c` covers both, plus the deny-only group,
  deny ACE, inherit-only ACE, full restriction and no-DACL cases.
- That native omits the owner/group requirement here is inferred from
  kernel SeAccessCheck behavior, not traced.
- The eight unexplained S-1-5-32 groups in the native token are still not
  reproduced.
