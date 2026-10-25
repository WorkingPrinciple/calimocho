#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef unsigned DWORD;
typedef unsigned ULONG;
typedef int LONG;
typedef int BOOL;
typedef unsigned UINT;
typedef unsigned long long ULONGLONG;
typedef uintptr_t ULONG_PTR;
typedef intptr_t LONG_PTR;
typedef uintptr_t WPARAM;
typedef intptr_t LPARAM;
typedef intptr_t LRESULT;
typedef LONG NTSTATUS;
typedef void *HANDLE;
typedef void *HWND;
typedef struct { ULONG_PTR Status; ULONG_PTR Information; } IO_STATUS_BLOCK;
typedef union { long long QuadPart; } LARGE_INTEGER;
#define TRUE 1
#define FALSE 0
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define STATUS_TIMEOUT 0x102
#define IO_COMPLETION_ALL_ACCESS 0x1f0003
#define ERROR_INVALID_PARAMETER 87
#define ERROR_INVALID_WINDOW_HANDLE 1400
#define ERROR_ACCESS_DENIED 5
#define ERROR_ALREADY_INITIALIZED 1247
#define ERROR_INVALID_FLAGS 1004
#define QS_ALLINPUT 0x04ff
#define QS_ALLPOSTMESSAGE 0x0100
#define QS_SMRESULT 0x8000
#define MAKELONG(l, h) ((LONG)(((DWORD)(l) & 0xffff) | (((DWORD)(h) & 0xffff) << 16)))
#define HandleToULong(h) ((ULONG)(ULONG_PTR)(h))
enum { COREMSG_ERROR = -1, COREMSG_EMPTY, COREMSG_DELIVERED, COREMSG_MARKER, COREMSG_LINKED, COREMSG_NOWAKE };

struct user_thread_info { HANDLE coremsg_iocp; HWND coremsg_hwnd[2]; };
static struct user_thread_info info;
static struct { struct { HANDLE UniqueThread; } ClientId; ULONG_PTR Win32ClientInfo[62]; } teb;
#define NtCurrentTeb() (&teb)
static DWORD last_error, window_tid = 7, removed_status;
static ULONG_PTR queued_key, queued_context, set_context;
static int queued, sent, closed_window, created;
static HWND sent_hwnd[4];
static WPARAM sent_wparam[4];
static LPARAM sent_lparam[4];
static ULONG changed = 0x13, wake = 0x31;

static struct user_thread_info *get_user_thread_info(void) { return &info; }
static void RtlSetLastWin32Error(DWORD error) { last_error = error; }
static DWORD RtlNtStatusToDosError(NTSTATUS status) { return 0x7000 + ((DWORD)status & 0xff); }
static HWND is_current_thread_window(HWND hwnd) { return hwnd == (HWND)0x20 && closed_window ? 0 : hwnd; }
static DWORD get_window_thread(HWND hwnd, DWORD *process) { return hwnd ? window_tid : 0; }
static HWND get_full_window_handle(HWND hwnd) { return hwnd; }
static void check_for_events(UINT flags) {}
static NTSTATUS NtCreateIoCompletion(HANDLE *port, DWORD access, void *attr, ULONG count)
{ created++; *port = (HANDLE)0x99; return 0; }
static NTSTATUS NtRemoveIoCompletion(HANDLE port, ULONG_PTR *key, ULONG_PTR *context,
                                     IO_STATUS_BLOCK *io, LARGE_INTEGER *timeout)
{
    assert(port == (HANDLE)0x99 && timeout->QuadPart == 0);
    if (removed_status) return removed_status;
    if (!queued) return STATUS_TIMEOUT;
    queued = 0; *key = queued_key; *context = queued_context;
    return 0;
}
static NTSTATUS NtSetIoCompletion(HANDLE port, ULONG_PTR key, ULONG_PTR context, NTSTATUS status, ULONG_PTR info_)
{ set_context = context; return 0; }
static LRESULT send_message(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam)
{
    assert(msg == 0x60);
    sent_hwnd[sent] = hwnd; sent_wparam[sent] = wparam; sent_lparam[sent++] = lparam;
    return 0;
}
struct get_queue_status_request { int clear_bits; };
struct get_queue_status_reply { ULONG changed_bits, wake_bits; };
static int clear_bits_seen = -1;
#define SERVER_START_REQ(name) do { struct name##_request r, *req = &r; \
    struct name##_reply rr, *reply = &rr; (void)reply;
#define SERVER_END_REQ } while (0)
#define wine_server_call(req) (clear_bits_seen = (req)->clear_bits, rr.changed_bits = changed, \
                               rr.wake_bits = wake, 0)

#include "coremsg.c"

static void queue(ULONG_PTR key, ULONG_PTR context) { queued = 1; queued_key = key; queued_context = context; }

int main(void)
{
    DWORD slot = 9;
    ULONG_PTR node = 0, entry[3] = {0, 0x55, 0};

    teb.ClientId.UniqueThread = (HANDLE)7;
    assert(!coremsg_initialize((HWND)0x20, NULL) && last_error == ERROR_INVALID_PARAMETER);
    assert(!coremsg_initialize(NULL, &slot) && last_error == ERROR_INVALID_WINDOW_HANDLE);
    window_tid = 8;
    assert(!coremsg_initialize((HWND)0x20, &slot) && last_error == ERROR_ACCESS_DENIED && !created);
    window_tid = 7;
    assert(coremsg_initialize((HWND)0x20, &slot) == (HANDLE)0x99 && slot == 0 && created == 1);
    assert(!coremsg_initialize((HWND)0x20, &slot) && last_error == ERROR_INVALID_PARAMETER);
    assert(coremsg_initialize((HWND)0x30, &slot) == (HANDLE)0x99 && slot == 1 && created == 1);
    assert(!coremsg_initialize((HWND)0x40, &slot) && last_error == ERROR_ALREADY_INITIALIZED);

    /* Marker packets are consumed without window delivery; near-markers are data. */
    queue(0, (ULONG_PTR)(LONG_PTR)(LONG)0x80000001);
    assert(coremsg_dispatch_packet() == COREMSG_MARKER && !sent);
    queue(0, 0x80000000u);
    assert(coremsg_dispatch_packet() == COREMSG_MARKER && !sent);
    queue(0, 0x80000002u);
    assert(coremsg_dispatch_packet() == COREMSG_DELIVERED && sent == 2);
    assert(sent_hwnd[0] == (HWND)0x20 && sent_hwnd[1] == (HWND)0x30);
    assert(sent_wparam[0] == 8 && sent_lparam[0] == 0x80000002);
    sent = 0;
    queue(0, 0x1234500080000000ull);
    assert(coremsg_dispatch_packet() == COREMSG_DELIVERED && sent == 2);
    sent = 0;

    /* A zero context without a wait entry wakes with wparam 3. */
    queue(0, 0);
    assert(coremsg_dispatch_packet() == COREMSG_NOWAKE && sent == 2 && sent_wparam[0] == 3);
    sent = 0;

    /* A keyed zero context links the node into the TEB wait list. */
    teb.Win32ClientInfo[61] = (ULONG_PTR)entry;
    queue((ULONG_PTR)&node, 0);
    assert(coremsg_dispatch_packet() == COREMSG_LINKED && !sent);
    assert(node == 0x55 && entry[1] == (ULONG_PTR)&node);

    assert(coremsg_dispatch_packet() == COREMSG_EMPTY);
    removed_status = 0xc0000008;
    assert(coremsg_dispatch_packet() == COREMSG_ERROR && last_error == 0x7008);
    removed_status = 0;

    /* Drain posts the wake marker only after delivering a packet. */
    assert(!coremsg_drain((HWND)0x40) && last_error == ERROR_INVALID_PARAMETER);
    assert(coremsg_drain((HWND)0x20) && set_context == 0);
    queue(0, 0x77);
    assert(coremsg_drain((HWND)0x30) && sent == 2);
    assert(set_context == (ULONG_PTR)(LONG_PTR)(LONG)0x80000001);

    /* A destroyed window slot is released and never targeted. */
    sent = 0;
    closed_window = 1;
    queue(0, 0x77);
    assert(coremsg_dispatch_packet() == COREMSG_DELIVERED && sent == 1 && sent_hwnd[0] == (HWND)0x30);
    assert(!info.coremsg_hwnd[0]);
    assert(!coremsg_drain((HWND)0x20) && last_error == ERROR_INVALID_WINDOW_HANDLE);

    /* Read-only status never clears queue bits. */
    assert(coremsg_queue_readonly(0x10000) == 0 && last_error == ERROR_INVALID_FLAGS);
    assert(coremsg_queue_readonly(0x0011) == (DWORD)MAKELONG(0x11, 0x11) && clear_bits_seen == 0);
    return 0;
}
