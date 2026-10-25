/* Handle provenance in the calling process; no arbitrary names or command lines. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkghandle);
extern void *package_diagnostic_syscall_return(void);
extern NTSTATUS package_diagnostic_stack_return(void **address);

static const char *diagnostic_public_name(const UNICODE_STRING *name)
{
    static const WCHAR ready[] = {'D','B','W','I','N','_','B','U','F','F','E','R','_','R','E','A','D','Y'};
    static const WCHAR data[] = {'D','B','W','I','N','_','D','A','T','A','_','R','E','A','D','Y'};
    SIZE_T i, start = 0, length;
    if (!name || !name->Length) return "unnamed";
    length = name->Length / sizeof(WCHAR);
    for (i = 0; i < length; ++i) if (name->Buffer[i] == '\\') start = i + 1;
    if ((length - start) * sizeof(WCHAR) == sizeof(ready)
        && !memcmp(name->Buffer + start, ready, sizeof(ready))) return "DBWIN_BUFFER_READY";
    if ((length - start) * sizeof(WCHAR) == sizeof(data)
        && !memcmp(name->Buffer + start, data, sizeof(data))) return "DBWIN_DATA_READY";
    return "named-redacted";
}

static inline ULONG diagnostic_process_id(HANDLE handle)
{
    PROCESS_BASIC_INFORMATION info;
    if (NtQueryInformationProcess(handle, ProcessBasicInformation, &info, sizeof(info), NULL)) return 0;
    return info.UniqueProcessId;
}

static void diagnostic_handle(const char *operation, const char *phase, NTSTATUS result,
                              HANDLE handle, HANDLE source, ULONG owner, ULONG peer,
                              const UNICODE_STRING *name)
{
    char module[128], syscall[128];
    ULONG_PTR offset, site;
    void *address = NULL;
    NTSTATUS query;
    static __thread int busy;
    if (!TRACE_ON(pkghandle) || busy) return;
    busy = 1;
    query = package_diagnostic_stack_return(&address);
    diagnostic_address(query ? NULL : address, module, sizeof(module), &offset);
    diagnostic_address(package_diagnostic_syscall_return(), syscall, sizeof(syscall), &site);
    TRACE_(pkghandle)("handle operation=%s phase=%s result=%08x handle=%x source=%x owner=%u peer=%u name=%s query=%08x module=%s offset=%lx syscall=%s site=%lx\n",
                      operation, phase, (unsigned int)result, wine_server_obj_handle(handle),
                      wine_server_obj_handle(source), owner, peer, diagnostic_public_name(name),
                      (unsigned int)query, module, offset, syscall, site);
    busy = 0;
}
