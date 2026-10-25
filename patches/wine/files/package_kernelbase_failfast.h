/* Fixed fail-fast record metadata only; never dump strings or memory. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgexception);
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);

static void diagnostic_failfast_address(const void *address, char *name, ULONG_PTR *offset)
{
    LDR_DATA_TABLE_ENTRY *entry;
    unsigned int i, length;
    strcpy(name, "unknown-redacted");
    *offset = 0;
    if (LdrFindEntryForAddress(address, &entry)) return;
    length = entry->BaseDllName.Length / sizeof(WCHAR);
    if (!length || length >= 128) return;
    for (i = 0; i < length; ++i)
    {
        WCHAR c = entry->BaseDllName.Buffer[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
              || c == '.' || c == '_' || c == '-')) return;
    }
    for (i = 0; i < length; ++i) name[i] = entry->BaseDllName.Buffer[i];
    name[length] = 0;
    *offset = (ULONG_PTR)address - (ULONG_PTR)entry->DllBase;
}

/* Called on entry, before any termination path. A NULL record is reported as the
 * record kernelbase itself would raise (STATUS_FAIL_FAST_EXCEPTION, caller address). */
static void diagnostic_failfast(const EXCEPTION_RECORD *record, DWORD flags, const void *caller)
{
    char module[128], parameter_module[128];
    ULONG_PTR offset, parameter_offset;
    unsigned int i, count;
    static LONG hits;
    LONG sequence;
    if (!TRACE_ON(pkgexception) || !__wine_pkg_diagnostic_active()) return;
    sequence = InterlockedIncrement(&hits);
    if (sequence > 8)
    {
        if (sequence == 9) TRACE_(pkgexception)("exception limited=1\n");
        return;
    }
    /* Ids 65..72 never collide with the unhandled-filter ids 1..33. */
    sequence += 64;
    count = record ? record->NumberParameters : 0;
    diagnostic_failfast_address(record && !(flags & FAIL_FAST_GENERATE_EXCEPTION_ADDRESS)
                                ? record->ExceptionAddress : caller, module, &offset);
    TRACE_(pkgexception)("exception stage=failfast id=%ld code=%08lx flags=%08lx count=%u module=%s offset=%Ix hresult=unknown failfast_flags=%08lx\n",
                         sequence, record ? record->ExceptionCode : STATUS_FAIL_FAST_EXCEPTION,
                         record ? record->ExceptionFlags : EXCEPTION_NONCONTINUABLE, count, module, offset, flags);
    for (i = 0; i < count && i < EXCEPTION_MAXIMUM_PARAMETERS; ++i)
    {
        ULONG_PTR value = record->ExceptionInformation[i];
        /* Values representable as sign-extended 32 bits (status, HRESULT, small codes) are scalars. */
        if ((LONG_PTR)value == (LONG_PTR)(LONG)value)
            TRACE_(pkgexception)("parameter id=%ld slot=%u kind=scalar value=%08lx\n", sequence, i, (ULONG)value);
        else
        {
            diagnostic_failfast_address((void *)value, parameter_module, &parameter_offset);
            TRACE_(pkgexception)("parameter id=%ld slot=%u kind=address module=%s offset=%Ix\n",
                                 sequence, i, parameter_module, parameter_offset);
        }
    }
}
