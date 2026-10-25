/* Read only unnamed wait-object metadata; never format object names. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgwait);
static LONG diagnostic_wait_sequence;
static void diagnostic_wait(HANDLE handle, unsigned int sequence, unsigned int slot)
{
    char buffer[1024];
    OBJECT_TYPE_INFORMATION *info = (void *)buffer;
    NTSTATUS status;
    const char *type = "unknown";
    EVENT_BASIC_INFORMATION event;
    ULONG size;
    if (!TRACE_ON(pkgwait)) return;
    status = NtQueryObject(handle, ObjectTypeInformation, info, sizeof(buffer), &size);
    if (!status)
    {
#define TYPE(value, text) if (info->TypeName.Length == sizeof(L##value) - sizeof(WCHAR) \
    && !memcmp(info->TypeName.Buffer, L##value, info->TypeName.Length)) type = text
        TYPE("Event", "event");
        else TYPE("Mutant", "mutant");
        else TYPE("Thread", "thread");
        else TYPE("Process", "process");
        else TYPE("Semaphore", "semaphore");
        else TYPE("Timer", "timer");
        else TYPE("ALPC Port", "alpc");
        else TYPE("Port", "port");
#undef TYPE
    }
    TRACE_(pkgwait)("object id=%u slot=%u handle=%x type=%s query=%08x\n",
                    sequence, slot, wine_server_obj_handle(handle), type, (unsigned int)status);
    if (!status && !strcmp(type, "event"))
    {
        status = NtQueryEvent(handle, EventBasicInformation, &event, sizeof(event), &size);
        TRACE_(pkgwait)("event id=%u slot=%u query=%08x signaled=%u\n", sequence, slot,
                        (unsigned int)status, !status && event.EventState > 0);
    }
}
