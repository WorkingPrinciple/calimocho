# ADR-0059: Qualify ALPC transport before registrar admission

## Context

The execution owner reports that cell026 reaches native CoreMessaging
initialization, then calls NtAlpcConnectPortEx and receives
STATUS_NOT_IMPLEMENTED. The source lane has not executed that runtime.

Historical source commit
`3ee99fb8caee9af215021f407d6710c9f0d25b4c` in the retained local
`wine-v20-src` repository contains experimental ALPC transport. Its protocol
observations are useful, but its weak endpoint references, synthesized
work-on-behalf tickets, reply-error suppression and client-PID-based
impersonation are not an acceptable implementation to adopt unchanged.
The current working directory in that repository also has uncommitted
changes, so only pinned committed blobs are eligible inputs.

The historical navigation broker is not the registrar host. The genuine
registrar runs its ServiceMain in Wine's svchost. No retained implementation
of the earlier service-token constructor exists. The service-registration
values are metadata, not permission to copy a CrossOver-derived prefix.

## Decision

Add an explicitly opt-in, source-only `--alpc-transport` build mode on a
fresh owned CoreMessaging sibling. Read only committed historical blobs
and record their hashes. Adapt to the actual Wine11.20 types and server
object API rather than importing the older ABI declarations.

Pending connection and request records own their endpoint references.
Receiving a connection request transfers ownership into the pending list.
Close, disconnect, rejection and handle-allocation failure release those
references and notify waiters. Queued ordinary messages retain a context
snapshot, not a weak pointer to a potentially destroyed sender.

Preserve asynchronous connection replies for the explicit receive.
Consume synchronous connection replies when retrieved. Keep undersized
receive messages queued for retry. Match replies against outstanding
server records and preserve mismatch errors. Connection-port datagrams
may target their own queue. Use the actual Wine11.20 reply flag, not the
historical experiment's different constant.

New port creator handles receive full port access. Named opens check
PORT_CONNECT, and operations on existing handles require that right.
The native creator-access measurement is pinned to xm commit
`c1ad52800417fa8be1c3783b733b3cacffcd59aa`, file
`scripts/macos/compatibility/xaml-startup/probe-outputs/native-alpc-creator-access.txt`,
SHA-256
`5462b0d29a1c108e5a4ce91fccec1e1372a1f6f01e7c71b3bba85092d3d5844b`.
This measurement does not qualify Wine's missing restricted-token checks
on the parent directory.

Do not synthesize work-on-behalf identity, impersonate a client-supplied
PID, ignore a requested security descriptor, or swallow reply errors.
Security requirements, client attributes, authenticated impersonation,
unsupported flags and synchronous message requests fail explicitly.
The transport currently supports payloads up to 32768 bytes and rejects
larger requested port limits. It is not a complete native ALPC implementation.

Reject these transport-only builds in the runtime freezer. Do not publish
a cell027 receipt, registry or run command before the registrar's service
identity and security checks qualify. Existing frozen builds and owner
execution authority remain unchanged.

## Consequences

Host tests compile the actual generated server handler body with a
deterministic object adapter and address/undefined-behavior sanitizers.
They exercise queued and received connection ownership, asynchronous
reply retention, synchronous connection signal consumption, reply
matching, receive-buffer retry, datagrams, access rejection, handle
allocation failures and cleanup. Separate tests reject frozen source
mutation and transport-only runtime freezing. These are source checks,
not Wine application or native compatibility evidence.

Remaining registrar work includes SCM honoring ObjectName/ServiceSidType,
LocalService primary-token construction, restricting-SID queries and the
second access-check pass, descriptor/SID matching, message-bound
impersonation, and qualified dispatch/wait integration. None is replaced
by returning success from this transport.

A new read-only native token measurement is retained externally as
`coremessaging-service-token.json`, SHA-256
`6afa5ecde2142102e7b7dfd019fc45242673e03d32ad87b2658aba72992114a3`.
It measures Windows build26300 and CoreMessaging
`e770ec95d5bac814efd8b76f8c37caee2a6d05aa8f0fe57f7e14a29b5f513b16`,
not the held candidate's build26100 component. It confirms LocalService,
session0, authentication LUID0x3e5, eleven privileges and seven restricting
SIDs for that shared host. Its logon SID and group membership are runtime
observations, not constants to copy into a new service token. Its
write-restricted flag interpretation is not behavioral access-check proof.
