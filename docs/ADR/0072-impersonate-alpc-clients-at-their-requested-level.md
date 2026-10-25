# ADR-0072: Impersonate ALPC clients at their requested level

## Context

Cell038 ran once. The server identity check passed (ADR-0071), the
connect was queued, and the registrar received the 0x18-byte connection
request. The registrar then called NtAlpcImpersonateClientOfPort, which
returned STATUS_BAD_IMPERSONATION_LEVEL. ADR-0064 admitted only clients
that connect at SecurityImpersonation. CoreMessaging connects at
SecurityIdentification. The registrar then refused the connection, and
the app got STATUS_PORT_CONNECTION_REFUSED and exited with 0xE0464645.

CoreMessaging impersonates in two ways (read for understanding only):

- +7af2c passes the received connection message, then calls
  OpenThreadToken(TOKEN_QUERY, OpenAsSelf TRUE) and RevertToSelf;
- +874f1 passes a NULL message on the accepted server communication port.

Natively, the server thread gets the client's token at the client's
requested level. At Identification it can query the token but cannot open
objects as the client.

## Decision

- `token_impersonate_alpc` takes the level and duplicates the captured
  client token at that level, not at SecurityImpersonation.
- Both forms accept Identification and Impersonation. Delegation is
  already refused at connect. Anonymous still returns
  STATUS_BAD_IMPERSONATION_LEVEL, because Wine has no anonymous logon
  token to impersonate.
- A new `no_message` request flag covers the NULL message form. It needs
  a server communication port owned by the caller, whose client is still
  connected to it. Otherwise it returns STATUS_INVALID_PORT_HANDLE or
  STATUS_PORT_DISCONNECTED.
- Unsupported shapes keep a fixed failure with a FIXME reason:
  `reason=impersonate_flags` for non-NULL flags, and
  `reason=impersonate_message_on_communication_port` for a message on a
  server communication port.

## Consequences

- The host test covers Identification and Impersonation on a delivered
  request, the token level, revert, the NULL message form after accept,
  and the refusal cases.
- Wine's open_token already returns an Identification thread token and
  refuses only Anonymous tokens. A static test pins that rule.
- Over-grant: Wine's object access checks do not refuse Identification
  tokens. While impersonating at Identification, an object open uses the
  client's access, where native returns STATUS_BAD_IMPERSONATION_LEVEL.
  Fixing this in the shared access check would also block handle creation
  and OpenThreadToken, so it is left for a later slice.
