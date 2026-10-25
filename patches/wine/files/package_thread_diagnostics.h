/* Real thread creation, saved syscall return site and start image. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgthread);
extern void *package_diagnostic_syscall_return(void);
extern NTSTATUS package_diagnostic_stack_return(void **address);
static void diagnostic_thread(const char *phase, PRTL_THREAD_START_ROUTINE start, HANDLE handle, NTSTATUS result)
{
    char module[128], caller[128], stack_module[128];
    ULONG_PTR offset, site, stack_offset;
    void *stack_return = NULL;
    NTSTATUS stack_status;
    THREAD_BASIC_INFORMATION info = {0};
    NTSTATUS query = STATUS_UNSUCCESSFUL;
    if (!TRACE_ON(pkgthread)) return;
    diagnostic_address((void *)start, module, sizeof(module), &offset);
    diagnostic_address(package_diagnostic_syscall_return(), caller, sizeof(caller), &site);
    stack_status = package_diagnostic_stack_return(&stack_return);
    diagnostic_address(stack_status ? NULL : stack_return, stack_module, sizeof(stack_module), &stack_offset);
    if (!result && handle) query = NtQueryInformationThread(handle, ThreadBasicInformation, &info, sizeof(info), NULL);
    TRACE_(pkgthread)("thread phase=%s result=%08x query=%08x tid=%u pid=%u start=%s offset=%lx syscall=%s site=%lx\n",
                      phase, (unsigned int)result, (unsigned int)query,
                      query ? 0 : HandleToULong(info.ClientId.UniqueThread),
                      query ? 0 : HandleToULong(info.ClientId.UniqueProcess),
                      module, offset, caller, site);
    TRACE_(pkgthread)("creator phase=%s query=%08x module=%s offset=%lx basis=user-stack-return-slot\n",
                      phase, (unsigned int)stack_status, stack_module, stack_offset);
}
