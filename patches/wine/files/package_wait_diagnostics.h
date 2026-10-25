/* Read only unnamed wait-object metadata; never format object names. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgwait);
static LONG diagnostic_wait_sequence;
static BOOL diagnostic_type_equal(const UNICODE_STRING *name, const char *type)
{
    SIZE_T i, length = strlen(type);
    if (name->Length != length * sizeof(WCHAR)) return FALSE;
    for (i = 0; i < length; ++i)
        if (name->Buffer[i] != (unsigned char)type[i]) return FALSE;
    return TRUE;
}
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
#define TYPE(value, text) if (diagnostic_type_equal(&info->TypeName, value)) type = text
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
    else if (!status && !strcmp(type, "semaphore"))
    {
        SEMAPHORE_BASIC_INFORMATION semaphore = {0};
        status = NtQuerySemaphore(handle, SemaphoreBasicInformation, &semaphore, sizeof(semaphore), &size);
        TRACE_(pkgwait)("semaphore id=%u slot=%u query=%08x count=%u maximum=%u\n",
                        sequence, slot, (unsigned int)status,
                        status ? 0 : semaphore.CurrentCount, status ? 0 : semaphore.MaximumCount);
    }
    else if (!status && !strcmp(type, "thread"))
    {
        THREAD_BASIC_INFORMATION thread = {0};
        void *start = NULL;
        char module[128];
        ULONG_PTR offset;
        NTSTATUS address_status;
        status = NtQueryInformationThread(handle, ThreadBasicInformation, &thread, sizeof(thread), NULL);
        address_status = NtQueryInformationThread(handle, ThreadQuerySetWin32StartAddress, &start, sizeof(start), NULL);
        diagnostic_address(address_status || status || thread.ClientId.UniqueProcess != NtCurrentTeb()->ClientId.UniqueProcess
                           ? NULL : start, module, sizeof(module), &offset);
        TRACE_(pkgwait)("thread id=%u slot=%u query=%08x pid=%u tid=%u exit=%08x start-query=%08x module=%s offset=%lx\n",
                        sequence, slot, (unsigned int)status,
                        status ? 0 : HandleToULong(thread.ClientId.UniqueProcess),
                        status ? 0 : HandleToULong(thread.ClientId.UniqueThread),
                        status ? 0 : (unsigned int)thread.ExitStatus, (unsigned int)address_status, module, offset);
    }
    else if (!status && !strcmp(type, "process"))
    {
        PROCESS_BASIC_INFORMATION process = {0};
        char storage[4096], image[128] = "unknown-redacted";
        UNICODE_STRING *name = (void *)storage;
        NTSTATUS image_status;
        SIZE_T i, length, start = 0;
        status = NtQueryInformationProcess(handle, ProcessBasicInformation, &process, sizeof(process), NULL);
        image_status = NtQueryInformationProcess(handle, ProcessImageFileName, storage, sizeof(storage), NULL);
        if (!image_status)
        {
            length = name->Length / sizeof(WCHAR);
            if ((char *)name->Buffer >= storage && (char *)(name->Buffer + length) <= storage + sizeof(storage))
            {
                for (i = 0; i < length; ++i)
                    if (name->Buffer[i] == '\\' || name->Buffer[i] == '/') start = i + 1;
                if (length > start && length - start < sizeof(image))
                {
                    for (i = start; i < length; ++i)
                    {
                        WCHAR c = name->Buffer[i];
                        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                              || (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-')) break;
                    }
                    if (i == length)
                    {
                        for (i = start; i < length; ++i) image[i - start] = name->Buffer[i];
                        image[length - start] = 0;
                    }
                }
            }
        }
        TRACE_(pkgwait)("process id=%u slot=%u query=%08x pid=%lu parent=%lu exit=%08x image-query=%08x image=%s\n",
                        sequence, slot, (unsigned int)status, status ? 0 : process.UniqueProcessId,
                        status ? 0 : process.InheritedFromUniqueProcessId,
                        status ? 0 : (unsigned int)process.ExitStatus, (unsigned int)image_status, image);
    }
}
