# ADR-0077: Bound AppContainer object-path support to token evidence

## Context

XB-58 assigns the Calimocho runtime adapter the named-object-path failure
exposed by cell043. That cell remains sealed. Its revised analysis
SHA-256 is
`873676ec06b47fd28e4f5fbaf0921d6350fa7ba4f19da34efc6fecc5aae693d2`.
The actual `RtlGetAppContainerNamedObjectPath` return is
`STATUS_NOT_IMPLEMENTED` at CoreMessaging+0x6f632. The matching fail-fast
at +0x6f6a4 carries `0xD0000002`. The exact caller supplies null token,
null SID, absolute mode and a zeroed 16-byte AMD64 UNICODE_STRING.

[Microsoft's Win32 documentation][selection] establishes effective
process/thread token selection. [PHNT][native] establishes the native
ABI and RtlFreeUnicodeString ownership. The Win32 caller-buffer contract
must not be substituted for the native allocated-string contract.
[Public namespace research][namespace] describes the per-session
AppContainer namespace.

These references do not establish the current native ntdll result for
a non-AppContainer token. A public legacy kernel reverse-analysis
listing suggests successful empty output, but is not a current AMD64
ntdll oracle. No native implementation is copied or incorporated.
There is no retained native ntdll or authorized Windows differential.

Wine's current token queries report no AppContainer SID and
TokenIsAppContainer=0. Its local package-activation record is explicitly
not lowbox security identity. Deriving a SID from that record would
invent security semantics, not implement the missing function.

## Decision

Implement the supported subset as an original, opt-in source porter.
Use the effective thread token, with process fallback only on
STATUS_NO_TOKEN. Preserve explicit-token query errors. Validate token
access with TokenStatistics before Wine's currently semi-stubbed
AppContainer queries. Never derive a SID from package metadata.

For a supplied or queried valid parent AppContainer SID, construct
`AppContainerNamedObjects\<SID>` in relative mode. Absolute mode adds
`\Sessions\<token-session>\`. An explicit SID uses the current process
token for session context. Require a successful TokenPrivateNameSpace
query before constructing an absolute path; fail if the query is
unsupported or a private namespace is present. Wine does not currently
implement that query. Parent SID format, token/session paths and
ownership are source-grounded support, not measured native parity for
every input or error precedence.

Allocate a counted UTF-16 string on the process heap, including its
terminator. The caller releases successful output with
RtlFreeUnicodeString. Free intermediate strings and locally opened
token handles on success and failure. Reject token plus explicit SID,
invalid SID and null output. Child SIDs and private namespaces remain
unsupported rather than returning an incorrect parent-only path.
Initialize non-null output before rejecting token plus explicit SID.
Do not free incoming output-only storage. This consistent failure-output
policy is tested with stale bytes, not claimed as measured native error
precedence.

For TokenIsAppContainer=0, return STATUS_NOT_SUPPORTED with empty output
and a diagnostic, not success with a guessed empty or BaseNamedObjects
path. This is a deliberate research limitation, not a claim about the
native return status. It leaves the captured Xbox call blocked.

Expose the change only through `--appcontainer-object-path` on a fresh
CoreMessaging dispatch source build. Preserve default builds, cell043
and other lanes. Record source hashes and the unresolved admission
blocker in the build receipt. Refuse runtime freezing for this research
mode, even if the human-readable blocker label is removed.

## Consequences

Host tests check the observed ABI, the unresolved branch's explicit
failure, thread/process selection, explicit token and SID forms,
relative/absolute path bytes, maximum session number, terminator and
counted lengths. They exercise both allocation failures, ownership,
invalid inputs, denied/failed queries and unsupported child/private
namespaces under address and undefined-behavior sanitizers.
Successful path tests inject genuine-shaped token-query fixtures;
they do not establish Wine server lowbox support.

XB-58 remains partial and blocked. Compilation is not runtime acceptance.
No new Xbox runtime cell, cell044 execution receipt or Windows probe is
authorized or produced by this decision. The next discriminator is an
authoritative current-native contract or a separately authorized,
version-pinned observation of null-token/null-SID absolute behavior for
a non-AppContainer effective token, including status and output fields.
No routine implementation approval is needed to resume once that
evidence exists.

[selection]: https://learn.microsoft.com/en-us/windows/win32/api/securityappcontainer/nf-securityappcontainer-getappcontainernamedobjectpath
[native]: https://ntdoc.m417z.com/rtlgetappcontainernamedobjectpath
[namespace]: https://www.tiraniddo.dev/2019/02/a-brief-history-of-basenamedobjects-on.html
