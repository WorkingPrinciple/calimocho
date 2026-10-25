/* Host checks for patches/wine/files/sechost_transient_wait.c with mocked Win32/NT calls.
 * Built with -fshort-wchar so L"" literals are 16-bit like the PE build. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef wchar_t WCHAR;
typedef uint32_t DWORD, ULONG;
typedef int32_t LONG, NTSTATUS;
typedef int BOOL;
typedef unsigned char BYTE, BOOLEAN;
typedef size_t SIZE_T;
typedef void *HANDLE, *SC_HANDLE, *PSECURITY_DESCRIPTOR;
typedef DWORD SECURITY_INFORMATION;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define INFINITE 0xffffffffu
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define STATUS_INVALID_PARAMETER ((NTSTATUS)0xc000000d)
#define STATUS_NOT_IMPLEMENTED ((NTSTATUS)0xc0000002)
#define STATUS_OBJECT_NAME_NOT_FOUND ((NTSTATUS)0xc0000034)
#define STATUS_BUFFER_OVERFLOW ((NTSTATUS)0x80000005)
#define STATUS_BUFFER_TOO_SMALL ((NTSTATUS)0xc0000023)
#define STATUS_INVALID_SECURITY_DESCR ((NTSTATUS)0xc0000079)
#define STATUS_NO_MEMORY ((NTSTATUS)0xc0000017)
#define OBJ_CASE_INSENSITIVE 0x40
#define KEY_READ 0x20019
#define REG_BINARY 3
#define SERVICE_STOPPED 1
#define SERVICE_RUNNING 4
#define SERVICE_PAUSED 7
#define SERVICE_START_PENDING 2
#define SC_STATUS_PROCESS_INFO 0
#define WAIT_OBJECT_0 0
#define WAIT_TIMEOUT 258
#define ERROR_TIMEOUT 1460
#define ERROR_CANCELLED 1223
#define ERROR_SERVICE_MARKED_FOR_DELETE 1072

typedef struct { uint16_t Length, MaximumLength; WCHAR *Buffer; } UNICODE_STRING;
typedef struct { ULONG Length; HANDLE RootDirectory; UNICODE_STRING *ObjectName; ULONG Attributes; } OBJECT_ATTRIBUTES;
typedef struct { ULONG TitleIndex, Type, DataLength; BYTE Data[1]; } KEY_VALUE_PARTIAL_INFORMATION;
enum { KeyValuePartialInformation = 2 };
typedef struct { DWORD dwServiceType, dwCurrentState, rest[7]; } SERVICE_STATUS_PROCESS;

#define InitializeObjectAttributes(a, n, f, r, s) \
    do { (a)->Length = sizeof(*(a)); (a)->RootDirectory = (r); (a)->ObjectName = (n); (a)->Attributes = (f); } while (0)
#define FIXME(...) (fixmes++, snprintf(last_fixme, sizeof(last_fixme), __VA_ARGS__))
#define TRACE(...) ((void)0)

static int fixmes, heap_live, opens, closes, queries, sleeps, polls;
static char last_fixme[128], opened[512];
static NTSTATUS open_status;
static BYTE value[264];
static ULONG value_type = REG_BINARY, value_len = sizeof(value);
static BOOLEAN valid_sd = 1;
static DWORD tick, last_error, states[8], state_count, cancel_after = ~0u;
static int query_fails_at = -1;

static const char *debugstr_w(const WCHAR *s) { (void)s; return ""; }
static HANDLE GetProcessHeap(void) { return (HANDLE)1; }
static void *HeapAlloc(HANDLE h, DWORD f, SIZE_T n) { (void)h; (void)f; heap_live++; return malloc(n); }
static BOOL HeapFree(HANDLE h, DWORD f, void *p) { (void)h; (void)f; if (p) { heap_live--; free(p); } return TRUE; }
static void RtlInitUnicodeString(UNICODE_STRING *u, const WCHAR *s)
{
    size_t n = 0; while (s[n]) n++;
    u->Buffer = (WCHAR *)s; u->Length = n * 2; u->MaximumLength = u->Length + 2;
}
static NTSTATUS NtOpenKey(HANDLE *key, DWORD access, OBJECT_ATTRIBUTES *attr)
{
    unsigned i;
    opens++;
    if (access != KEY_READ || attr->Attributes != OBJ_CASE_INSENSITIVE) return STATUS_INVALID_PARAMETER;
    for (i = 0; i < attr->ObjectName->Length / 2 && i < sizeof(opened) - 1; i++) opened[i] = (char)attr->ObjectName->Buffer[i];
    opened[i] = 0;
    *key = (HANDLE)2;
    return open_status;
}
static NTSTATUS NtClose(HANDLE h) { (void)h; closes++; return 0; }
static NTSTATUS NtQueryValueKey(HANDLE key, UNICODE_STRING *name, int cls, void *buf, DWORD size, DWORD *needed)
{
    KEY_VALUE_PARTIAL_INFORMATION *info = buf;
    (void)key; (void)name;
    queries++;
    if (cls != KeyValuePartialInformation) return STATUS_INVALID_PARAMETER;
    *needed = offsetof(KEY_VALUE_PARTIAL_INFORMATION, Data) + value_len;
    if (size < *needed) return STATUS_BUFFER_OVERFLOW;
    info->Type = value_type; info->DataLength = value_len;
    memcpy(info->Data, value, value_len);
    return 0;
}
static BOOLEAN RtlValidRelativeSecurityDescriptor(PSECURITY_DESCRIPTOR sd, ULONG len, SECURITY_INFORMATION si)
{
    (void)sd; (void)si; return valid_sd && len == value_len;
}
static BOOL QueryServiceStatusEx(SC_HANDLE s, int level, BYTE *buf, DWORD size, DWORD *ret)
{
    SERVICE_STATUS_PROCESS *status = (SERVICE_STATUS_PROCESS *)buf;
    (void)s; (void)level; (void)size; (void)ret;
    if ((int)polls == query_fails_at) { polls++; last_error = ERROR_SERVICE_MARKED_FOR_DELETE; return FALSE; }
    status->dwCurrentState = states[(DWORD)polls < state_count ? (DWORD)polls : state_count - 1];
    polls++;
    return TRUE;
}
static DWORD GetTickCount(void) { return tick; }
static void Sleep(DWORD ms) { sleeps++; tick += ms; }
static DWORD WaitForSingleObject(HANDLE h, DWORD ms)
{
    (void)h;
    if ((DWORD)polls >= cancel_after) return WAIT_OBJECT_0;
    tick += ms; return WAIT_TIMEOUT;
}
static void SetLastError(DWORD e) { last_error = e; }

#include "transient_wait_under_test.c"

static int failures;
#define CHECK(c) do { if (!(c)) { failures++; fprintf(stderr, "line %d: %s\n", __LINE__, #c); } } while (0)

static void reset(void)
{
    fixmes = opens = closes = queries = sleeps = polls = 0;
    open_status = 0; value_type = REG_BINARY; value_len = sizeof(value); valid_sd = 1;
    tick = 1000; last_error = 0; state_count = 0; cancel_after = ~0u; query_fails_at = -1;
}

int main(void)
{
    PSECURITY_DESCRIPTOR sd;
    unsigned i;

    for (i = 0; i < sizeof(value); i++) value[i] = (BYTE)i;

    reset();
    sd = (void *)1;
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"WM_RegistrarServer", &sd) == 0);
    CHECK(!strcmp(opened, "\\Registry\\Machine\\Software\\Microsoft\\SecurityManager\\TransientObjects\\"
                          "%5C%5C.%5CAlpcPort%5CWM_RegistrarServer"));
    CHECK(sd && !memcmp(sd, value, sizeof(value)));
    CHECK(queries == 2 && closes == 1 && heap_live == 1);
    CHECK(FreeTransientObjectSecurityDescriptor(sd) == TRUE && heap_live == 0);

    reset();
    CHECK(QueryTransientObjectSecurityDescriptor(7, L"WM_RegistrarServer", &sd) == STATUS_NOT_IMPLEMENTED);
    CHECK(sd == NULL && opens == 0 && fixmes == 1 && !strncmp(last_fixme, "reason=transient_type", 21));
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"a\\b", &sd) == STATUS_NOT_IMPLEMENTED && opens == 0);
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"a%5Cb", &sd) == STATUS_NOT_IMPLEMENTED && opens == 0);
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"", &sd) == STATUS_NOT_IMPLEMENTED);
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"x", NULL) == STATUS_INVALID_PARAMETER);
    {
        WCHAR longname[300];
        for (i = 0; i < 299; i++) longname[i] = 'a';
        longname[299] = 0;
        CHECK(QueryTransientObjectSecurityDescriptor(8, longname, &sd) == STATUS_NOT_IMPLEMENTED && opens == 0);
    }

    reset();
    open_status = STATUS_OBJECT_NAME_NOT_FOUND;
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"WM_RegistrarServer", &sd) == STATUS_OBJECT_NAME_NOT_FOUND);
    CHECK(sd == NULL && heap_live == 0 && closes == 0);

    reset();
    value_type = 1;
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"WM_RegistrarServer", &sd) == STATUS_INVALID_SECURITY_DESCR);
    CHECK(sd == NULL && heap_live == 0 && closes == 1);
    reset();
    valid_sd = 0;
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"WM_RegistrarServer", &sd) == STATUS_INVALID_SECURITY_DESCR);
    CHECK(sd == NULL && heap_live == 0);
    reset();
    value_len = 16;
    CHECK(QueryTransientObjectSecurityDescriptor(8, L"WM_RegistrarServer", &sd) == 0 && queries == 1);
    CHECK(FreeTransientObjectSecurityDescriptor(sd) && heap_live == 0);

    /* WaitServiceState: SERVICE_NOTIFY bit for state s is 1 << (s - 1). */
    reset();
    states[0] = SERVICE_START_PENDING; states[1] = SERVICE_START_PENDING; states[2] = SERVICE_RUNNING; state_count = 3;
    CHECK(WaitServiceState((SC_HANDLE)3, 1u << (SERVICE_RUNNING - 1), 1000, NULL) == SERVICE_RUNNING);
    CHECK(polls == 3 && sleeps == 2);

    reset();
    states[0] = SERVICE_RUNNING; state_count = 1;
    CHECK(WaitServiceState((SC_HANDLE)3, 0x8 | 0x1, 0, NULL) == SERVICE_RUNNING && sleeps == 0);

    reset();
    states[0] = SERVICE_START_PENDING; state_count = 1;
    CHECK(WaitServiceState((SC_HANDLE)3, 0x8, 120, NULL) == 0 && last_error == ERROR_TIMEOUT);
    CHECK(tick == 1120 && sleeps == 3);

    reset();
    states[0] = SERVICE_START_PENDING; state_count = 1; cancel_after = 2;
    CHECK(WaitServiceState((SC_HANDLE)3, 0x8, INFINITE, (HANDLE)4) == 0 && last_error == ERROR_CANCELLED);

    reset();
    states[0] = SERVICE_START_PENDING; state_count = 1; query_fails_at = 1;
    CHECK(WaitServiceState((SC_HANDLE)3, 0x8, INFINITE, NULL) == 0 &&
          last_error == ERROR_SERVICE_MARKED_FOR_DELETE);

    reset();
    states[0] = 0; state_count = 1;
    CHECK(!service_state_requested(0xff, 0) && !service_state_requested(0xff, 8) &&
          service_state_requested(0x40, SERVICE_PAUSED));

    if (failures) return 1;
    puts("sechost transient/wait host checks passed");
    return 0;
}
