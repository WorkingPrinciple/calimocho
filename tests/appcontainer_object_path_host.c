#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

typedef int32_t NTSTATUS;
typedef uint32_t ULONG;
typedef uint8_t BYTE, BOOLEAN;
typedef intptr_t LONG_PTR;
typedef size_t SIZE_T;
typedef void *HANDLE;
typedef wchar_t WCHAR;
typedef struct { BYTE Value[6]; } SID_IDENTIFIER_AUTHORITY;
typedef struct { BYTE Revision, SubAuthorityCount; SID_IDENTIFIER_AUTHORITY IdentifierAuthority;
                 ULONG SubAuthority[15]; } SID, *PSID;
typedef struct { uint16_t Length, MaximumLength; WCHAR *Buffer; } UNICODE_STRING;
typedef struct { PSID TokenAppContainer; } TOKEN_APPCONTAINER_INFORMATION;
typedef struct { ULONG placeholder; } TOKEN_STATISTICS;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define TOKEN_QUERY 8
#define STATUS_SUCCESS 0
#define STATUS_INVALID_PARAMETER ((NTSTATUS)0xc000000d)
#define STATUS_INVALID_PARAMETER_MIX ((NTSTATUS)0xc0000030)
#define STATUS_INVALID_SID ((NTSTATUS)0xc0000078)
#define STATUS_NOT_SUPPORTED ((NTSTATUS)0xc00000bb)
#define STATUS_NO_TOKEN ((NTSTATUS)0xc000007c)
#define STATUS_NO_MEMORY ((NTSTATUS)0xc0000017)
#define STATUS_NAME_TOO_LONG ((NTSTATUS)0xc0000106)
#define STATUS_ACCESS_DENIED ((NTSTATUS)0xc0000022)
#define STATUS_INVALID_HANDLE ((NTSTATUS)0xc0000008)
#define STATUS_BUFFER_TOO_SMALL ((NTSTATUS)0xc0000023)
#define STATUS_NOT_IMPLEMENTED ((NTSTATUS)0xc0000002)
#define SECURITY_MAX_SID_SIZE sizeof(SID)
#define SECURITY_APP_PACKAGE_AUTHORITY {{0,0,0,0,0,15}}
#define SECURITY_APP_PACKAGE_BASE_RID 2
#define TRACE(...) ((void)0)
static ULONG warnings;
#define WARN(...) (++warnings)
enum { TokenStatistics, TokenIsAppContainer, TokenAppContainerSid, TokenSessionId, TokenPrivateNameSpace };
static struct test_peb { void *ProcessHeap; } peb = {(void *)0x1234};
static struct { struct test_peb *Peb; } teb = {&peb};
#define NtCurrentTeb() (&teb)
static SID container_sid = {1,8,{{0,0,0,0,0,15}},{2,11,22,33,44,55,66,77}};
static ULONG is_container, session = 3, private_namespace;
static int impersonating, opens, closes, live_allocations, allocations, fail_allocation;
static int failed_class = -1, sid_missing, fail_append;
static NTSTATUS query_error = STATUS_ACCESS_DENIED, thread_error, process_error, conversion_error;
static HANDLE queried, process = (HANDLE)1, thread = (HANDLE)2;

static size_t wide_length(const WCHAR *s)
{
    size_t length = 0;
    while (s[length]) ++length;
    return length;
}
static void from_ascii(WCHAR *out, const char *in)
{
    while ((*out++ = (unsigned char)*in++));
}
static void assert_text(const UNICODE_STRING *s, const char *text)
{
    size_t length = strlen(text), i;
    assert(s->Length == length * 2 && s->MaximumLength == (length + 1) * 2);
    assert(s->Buffer[length] == 0);
    for (i = 0; i < length; ++i) assert(s->Buffer[i] == (BYTE)text[i]);
}
static void assert_empty(const UNICODE_STRING *s)
{
    assert(!s->Buffer && !s->Length && !s->MaximumLength && !live_allocations);
}
static void *RtlAllocateHeap(void *heap, ULONG flags, SIZE_T size)
{
    void *p;
    assert(heap == peb.ProcessHeap && flags == 0);
    if (++allocations == fail_allocation) return NULL;
    p = malloc(size);
    assert(p);
    ++live_allocations;
    return p;
}
static void RtlFreeUnicodeString(UNICODE_STRING *s)
{
    if (s->Buffer) { --live_allocations; free(s->Buffer); }
    memset(s, 0, sizeof(*s));
}
static BOOLEAN RtlValidSid(PSID sid)
{
    return sid->Revision == 1 && sid->SubAuthorityCount <= 15;
}
static NTSTATUS RtlAppendUnicodeStringToString(UNICODE_STRING *out, const UNICODE_STRING *in)
{
    if (fail_append) return STATUS_BUFFER_TOO_SMALL;
    assert(out->Length + in->Length + 2 <= out->MaximumLength);
    memcpy((BYTE *)out->Buffer + out->Length, in->Buffer, in->Length);
    out->Length += in->Length;
    out->Buffer[out->Length / 2] = 0;
    return 0;
}
static NTSTATUS RtlAppendUnicodeToString(UNICODE_STRING *out, const WCHAR *text)
{
    UNICODE_STRING in = {wide_length(text) * 2, 0, (WCHAR *)text};
    return RtlAppendUnicodeStringToString(out, &in);
}
static NTSTATUS RtlIntegerToUnicodeString(ULONG number, ULONG base, UNICODE_STRING *s)
{
    char digits[11];
    assert(base == 10);
    snprintf(digits, sizeof(digits), "%u", number);
    s->Length = strlen(digits) * 2;
    assert(s->MaximumLength > s->Length);
    from_ascii(s->Buffer, digits);
    return 0;
}
static NTSTATUS RtlConvertSidToUnicodeString(UNICODE_STRING *s, PSID sid, BOOLEAN allocate)
{
    char text[200];
    size_t length, i;
    assert(allocate);
    if (conversion_error) return conversion_error;
    length = snprintf(text, sizeof(text), "S-1-%u", sid->IdentifierAuthority.Value[5]);
    for (i = 0; i < sid->SubAuthorityCount; ++i)
        length += snprintf(text + length, sizeof(text) - length, "-%u", sid->SubAuthority[i]);
    s->Buffer = RtlAllocateHeap(peb.ProcessHeap, 0, (length + 1) * 2);
    if (!s->Buffer) return STATUS_NO_MEMORY;
    s->Length = length * 2;
    s->MaximumLength = (length + 1) * 2;
    from_ascii(s->Buffer, text);
    return 0;
}
static NTSTATUS NtOpenThreadToken(HANDLE h, ULONG access, BOOLEAN self, HANDLE *out)
{
    assert(h == (HANDLE)-2 && access == TOKEN_QUERY && self);
    if (thread_error) return thread_error;
    if (!impersonating) return STATUS_NO_TOKEN;
    ++opens;
    *out = thread;
    return 0;
}
static NTSTATUS NtOpenProcessToken(HANDLE h, ULONG access, HANDLE *out)
{
    assert(h == (HANDLE)-1 && access == TOKEN_QUERY);
    if (process_error) return process_error;
    ++opens;
    *out = process;
    return 0;
}
static NTSTATUS NtClose(HANDLE h)
{
    assert(h == process || h == thread);
    ++closes;
    return 0;
}
static NTSTATUS NtQueryInformationToken(HANDLE h, int which, void *out, ULONG size, ULONG *length)
{
    queried = h;
    if (h != process && h != thread && h != (HANDLE)-4) return STATUS_INVALID_HANDLE;
    if (which == failed_class) return query_error;
    switch (which)
    {
    case TokenStatistics:
        assert(size == sizeof(TOKEN_STATISTICS));
        memset(out, 0, size);
        break;
    case TokenIsAppContainer:
        *(ULONG *)out = is_container;
        break;
    case TokenAppContainerSid:
        assert(size >= sizeof(TOKEN_APPCONTAINER_INFORMATION));
        ((TOKEN_APPCONTAINER_INFORMATION *)out)->TokenAppContainer = sid_missing ? NULL : &container_sid;
        break;
    case TokenPrivateNameSpace:
        *(ULONG *)out = private_namespace;
        break;
    case TokenSessionId:
        *(ULONG *)out = session;
        break;
    default: assert(0);
    }
    *length = size;
    return 0;
}
#include "object_path_under_test.c"

int main(void)
{
    struct { uint64_t before; UNICODE_STRING path; uint64_t after; } guard = {123, {0}, 456};
    UNICODE_STRING *p = &guard.path;
    int before;
    ULONG i;
    _Static_assert(sizeof(WCHAR) == 2 && sizeof(UNICODE_STRING) == 16, "captured AMD64 ABI");
    /* XB-58: observed NULL token, NULL SID, absolute, zeroed UNICODE_STRING. */
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_NOT_SUPPORTED);
    assert_empty(p);
    assert(queried == process && opens == closes);
    assert(guard.before == 123 && guard.after == 456);
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, NULL) == STATUS_INVALID_PARAMETER);
    before = opens;
    assert(RtlGetAppContainerNamedObjectPath(process, &container_sid, FALSE, p) == STATUS_INVALID_PARAMETER_MIX);
    assert(opens == before);
    assert(RtlGetAppContainerNamedObjectPath((HANDLE)99, NULL, FALSE, p) == STATUS_INVALID_HANDLE);
    assert_empty(p);
    thread_error = STATUS_ACCESS_DENIED;
    before = opens;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_ACCESS_DENIED);
    assert(opens == before); /* No fallback on denied impersonation. */
    thread_error = 0;
    process_error = STATUS_ACCESS_DENIED;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_ACCESS_DENIED);
    process_error = 0;
    is_container = impersonating = TRUE;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == 0);
    assert(queried == thread && opens == closes && live_allocations == 1);
    assert_text(p, "\\Sessions\\3\\AppContainerNamedObjects\\S-1-15-2-11-22-33-44-55-66-77");
    RtlFreeUnicodeString(p);
    assert_empty(p);
    impersonating = FALSE;
    assert(RtlGetAppContainerNamedObjectPath(process, NULL, TRUE, p) == 0);
    assert_text(p, "AppContainerNamedObjects\\S-1-15-2-11-22-33-44-55-66-77");
    RtlFreeUnicodeString(p);
    is_container = FALSE;
    session = UINT32_MAX;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, FALSE, p) == 0);
    assert(queried == (HANDLE)-4);
    assert_text(p, "\\Sessions\\4294967295\\AppContainerNamedObjects\\S-1-15-2-11-22-33-44-55-66-77");
    RtlFreeUnicodeString(p);
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == 0);
    RtlFreeUnicodeString(p);
    container_sid.Revision = 0;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_INVALID_SID);
    container_sid.Revision = 1;
    container_sid.SubAuthorityCount = 12;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_NOT_SUPPORTED);
    container_sid.SubAuthorityCount = 7;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_INVALID_SID);
    container_sid.SubAuthorityCount = 8;
    container_sid.IdentifierAuthority.Value[5] = 5;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_INVALID_SID);
    container_sid.IdentifierAuthority.Value[5] = 15;
    container_sid.SubAuthority[0] = 1;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_INVALID_SID);
    container_sid.SubAuthority[0] = 2;
    container_sid.SubAuthorityCount = 0;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, TRUE, p) == STATUS_INVALID_SID);
    container_sid.SubAuthorityCount = 8;
    private_namespace = TRUE;
    assert(RtlGetAppContainerNamedObjectPath(NULL, &container_sid, FALSE, p) == STATUS_NOT_SUPPORTED);
    assert_empty(p);
    private_namespace = FALSE;
    is_container = TRUE;
    sid_missing = TRUE;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_INVALID_SID);
    sid_missing = FALSE;
    for (i = TokenStatistics; i <= TokenPrivateNameSpace; ++i)
    {
        failed_class = i;
        query_error = i == TokenPrivateNameSpace ? STATUS_NOT_IMPLEMENTED : STATUS_ACCESS_DENIED;
        assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == query_error);
        assert_empty(p);
        assert(opens == closes);
    }
    failed_class = -1;
    conversion_error = STATUS_BUFFER_TOO_SMALL;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_BUFFER_TOO_SMALL);
    conversion_error = 0;
    fail_append = TRUE;
    assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_BUFFER_TOO_SMALL);
    assert_empty(p);
    assert(opens == closes);
    fail_append = FALSE;
    for (i = 1; i <= 2; ++i)
    {
        allocations = 0;
        fail_allocation = i;
        assert(RtlGetAppContainerNamedObjectPath(NULL, NULL, FALSE, p) == STATUS_NO_MEMORY);
        assert_empty(p);
        assert(opens == closes);
    }
    fail_allocation = 0;
    assert(warnings && opens == closes && !live_allocations);
    assert(guard.before == 123 && guard.after == 456);
    return 0;
}
