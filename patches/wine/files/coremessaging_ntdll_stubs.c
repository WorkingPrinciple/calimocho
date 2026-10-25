/* Explicit unsupported CoreMessaging prerequisites. LGPL-2.1-or-later */
#include <stdarg.h>
#include <string.h>
#include "ntstatus.h"
#include "windef.h"
#include "winternl.h"
#include "wine/debug.h"

WINE_DEFAULT_DEBUG_CHANNEL(package);
WINE_DECLARE_DEBUG_CHANNEL(pkgstatus);
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);

static void diagnostic_coremessaging_stub(const char *name)
{
    static LONG count;
    LONG hit;

    FIXME("%s is not implemented.\n", name);
    if (!TRACE_ON(pkgstatus) || !__wine_pkg_diagnostic_active()) return;
    hit = InterlockedIncrement(&count);
    if (hit <= 128)
        TRACE_(pkgstatus)("coremessaging-stub name=%s hit=%u result=c0000002\n", name, (UINT)hit);
    else if (hit == 129)
        TRACE_(pkgstatus)("coremessaging-stub limited=1\n");
}

NTSTATUS WINAPI RtlGetAppContainerNamedObjectPath(HANDLE token, PSID sid, BOOLEAN relative,
                                                 UNICODE_STRING *path)
{
    diagnostic_coremessaging_stub("RtlGetAppContainerNamedObjectPath");
    if (path) memset(path, 0, sizeof(*path));
    return STATUS_NOT_IMPLEMENTED;
}

NTSTATUS WINAPI RtlGetThreadWorkOnBehalfTicket(ULONGLONG *ticket, ULONG flags)
{
    diagnostic_coremessaging_stub("RtlGetThreadWorkOnBehalfTicket");
    if (ticket) *ticket = 0;
    return STATUS_NOT_IMPLEMENTED;
}

NTSTATUS WINAPI RtlSetThreadWorkOnBehalfTicket(ULONGLONG *ticket)
{
    diagnostic_coremessaging_stub("RtlSetThreadWorkOnBehalfTicket");
    return STATUS_NOT_IMPLEMENTED;
}

NTSTATUS WINAPI NtAlpcConnectPortEx(HANDLE *port, OBJECT_ATTRIBUTES *connection,
                                   OBJECT_ATTRIBUTES *client, ALPC_PORT_ATTRIBUTES *attributes,
                                   ULONG flags, PSECURITY_DESCRIPTOR security,
                                   ALPC_PORT_MESSAGE *message, SIZE_T *length,
                                   ALPC_MESSAGE_ATTRIBUTES *sent,
                                   ALPC_MESSAGE_ATTRIBUTES *received, LARGE_INTEGER *timeout)
{
    diagnostic_coremessaging_stub("NtAlpcConnectPortEx");
    if (port) *port = NULL;
    if (length) *length = 0;
    if (received) received->ValidAttributes = 0;
    return STATUS_NOT_IMPLEMENTED;
}

NTSTATUS WINAPI NtAlpcQueryInformation(HANDLE port, ULONG info_class, void *info,
                                      ULONG length, ULONG *returned)
{
    diagnostic_coremessaging_stub("NtAlpcQueryInformation");
    if (info && length) memset(info, 0, length);
    if (returned) *returned = 0;
    return STATUS_NOT_IMPLEMENTED;
}
