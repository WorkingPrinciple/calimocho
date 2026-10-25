/* Fixed exception metadata only; never dump exception objects or strings. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgexception);
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);

static void diagnostic_exception_address(const void *address, char *name, ULONG_PTR *offset)
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

static void diagnostic_exception(EXCEPTION_RECORD *record)
{
    char module[128], parameter_module[128];
    ULONG_PTR offset, parameter_offset;
    unsigned int i;
    static LONG count;
    LONG sequence;
    if (!TRACE_ON(pkgexception) || !__wine_pkg_diagnostic_active()) return;
    sequence = InterlockedIncrement(&count);
    if (sequence > 32)
    {
        if (sequence == 33) TRACE_(pkgexception)("exception limited=1\n");
        return;
    }
    diagnostic_exception_address(record->ExceptionAddress, module, &offset);
    TRACE_(pkgexception)("exception stage=unhandled-filter id=%ld code=%08lx flags=%08lx count=%lu module=%s offset=%Ix hresult=unknown\n",
                         sequence, record->ExceptionCode, record->ExceptionFlags,
                         record->NumberParameters, module, offset);
    for (i = 0; i < record->NumberParameters && i < EXCEPTION_MAXIMUM_PARAMETERS; ++i)
    {
        ULONG_PTR value = record->ExceptionInformation[i];
        if ((record->ExceptionCode == EXCEPTION_ACCESS_VIOLATION || record->ExceptionCode == EXCEPTION_IN_PAGE_ERROR)
            && (i == 0 || i == 2))
            TRACE_(pkgexception)("parameter id=%ld slot=%u kind=scalar value=%08lx\n", sequence, i, (ULONG)value);
        else if (record->ExceptionCode == 0xe06d7363 && i == 0)
            TRACE_(pkgexception)("parameter id=%ld slot=%u kind=cpp-magic value=%08lx\n", sequence, i, (ULONG)value);
        else
        {
            diagnostic_exception_address((void *)value, parameter_module, &parameter_offset);
            TRACE_(pkgexception)("parameter id=%ld slot=%u kind=address module=%s offset=%Ix\n",
                                 sequence, i, parameter_module, parameter_offset);
        }
    }
}
