# ADR-0057: Qualify native CoreMessaging prerequisites

## Context

Actual024 passes the previous OneCore query import and fails at the Wine
CoreMessaging CoreUICreate stub. Native XAML calls it at RVA4fed65.
Replacing the private dispatcher with a guessed factory or success status
would hide the missing runtime rather than implement it.

The owner's retained local CoreMessaging input has SHA-256
`88c7b4d6ee26f7695de0885f39db2949ad77bffc20902b0d19fde7f7ad9d31bc`.
Its AMD64 file/product version10.0.26100.9444 matches original XAML16302bfe.
The execution owner found matching historical source/hash records for the
owner's Windows system files. This is compatible-candidate evidence, not
fresh signature verification or original host-build-chain proof. Microsoft
evaluation input is not Wine source and must not be committed or distributed.

Eight direct ntdll imports are absent from frozen024. Three implement wait
completion packets; five require other unsupported NT facilities. Even
present ALPC APIs have partial or unimplemented behavior. Delayed private
user32 and combase ordinal imports remain unqualified. Static import
resolution cannot establish that CoreUICreate or Initialize works.

The retained native DLL's delay-import table also names combase ordinals
86-88, user32 ordinals 2541, 2669 and 2670, and
`GetQueueStatusForCoreMessaging` plus `ScheduleCoreMessagingDispatch` from
`ext-ms-win-rtcore-minuser-private-ext-l1-1-1.dll`. Wine's current combase
exports those ordinals as `CoCreateObjectInContext`,
`CoDeactivateObject` and `CoDecodeProxy`. The matching native combase export
table is not available, so those names are only the Wine-side bindings, not
verified native function identities. Do not assign aliases or implement
ordinal behavior from those names.

Wine marks the three user32 ordinals as stubs, with corresponding win32u
syscall stubs. The API-set schema has no host for the imported
`...private-ext-l1-1-1` family. These imports are delay-loaded, so they are
call-time gaps rather than initial module-load failures. The inspected
`CoreUICreate` thunk and `CoreUICreateEx` body do not directly reference
these IAT entries; `CoreUICreateEx` calls an internal helper, and transitive
reachability from that helper is unproven. Static call sites elsewhere in
CoreMessaging do not establish that these imports run during creation.

Full mandatory-import inspection also finds missing
`ucrtbase!__C_specific_handler_noexcept`. Public export metadata in the
retained native CRT, SHA-256
`1a6f2371123e37cfa6138840f31a2cb82db10f1fb36fad87ea732a4e3c6841f5`,
forwards this name directly to `ntdll.__C_specific_handler`. This is an
observed public forwarder, not an inferred private exception-handler ABI.

## Decision

Implement the three wait-completion APIs through real wineserver objects,
not client-side worker threads or synthetic success. Associations retain
the packet, target and completion port, and reserve the completion message
before the wait. A signal consumes the wait as appropriate and queues the
exact caller-supplied key, context, status and information once. The packet
remains busy until dequeued or cancelled. Cancellation distinguishes
waiting, queued and inactive states and supports removing a queued packet.
Closing the packet or the last port handle cancels its owned associations.

Reuse server wait queues with an explicit callback on packet entries.
Existing thread entries initialize that callback to NULL. Initially support
server-observable events, timers, semaphores, processes and threads, which
do not require a thread-owned mutex acquisition. Reject other target types
and unsupported in-process-only synchronization explicitly, not with success.

Expose the other five prerequisites with source-qualified signatures,
STATUS_NOT_IMPLEMENTED and cleared output fields. Preserve input-only
arguments and allocation masks. Emit standard failure diagnostics plus a
bounded, run-scoped fixed-name stub-hit counter without raw handles,
addresses, ticket contents or application strings.

Reproduce that exact AMD64 CRT forwarder in source-built ucrtbase, without
copying the native binary or inventing noexcept exception semantics.
Resolve every mandatory import and recursive public export forwarder
against the staged source-built modules and unchanged API-set schema.
Retain all nineteen delay-import descriptors as unqualified, not success.

The wait-completion contract is Microsoft's documented
[create](https://learn.microsoft.com/en-us/windows/win32/devnotes/ntcreatewaitcompletionpacket),
[associate](https://learn.microsoft.com/en-us/windows/win32/devnotes/ntassociatewaitcompletionpacket)
and [cancel](https://learn.microsoft.com/en-us/windows/win32/devnotes/ntcancelwaitcompletionpacket)
behavior. The remaining signatures come from phnt at commit
`4da2e8aa33cb583f64ba124bf6f7f4838c34b213`, ntrtl.h and ntlpcapi.h,
through the linked NtDoc declarations. No Microsoft implementation is copied.

## Consequences

Qualify actual server handlers with deterministic compiled host tests,
including unsignaled and already-signaled association, payload preservation,
busy rejection, cancellation, dequeue/rearm and handle cleanup. Compile
the full server and ntdll source together because the protocol changes.
These are source checks, not native Windows parity or product acceptance.

Any later025 recipe must preserve024 telemetry and identity, reference the
retained native CoreMessaging input explicitly with a native-only override,
retain the runtime hold, and never overwrite a frozen predecessor. It is
not execution-ready until all mandatory import and staging checks pass.
The consumed024 grant authorizes neither025 nor any VM or screen action.
