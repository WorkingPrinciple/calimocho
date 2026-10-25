/* Exact matching 32-bit return values only; no argument formatting. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgstatus);
static void diagnostic_status_address(const void *address, char *module, ULONG_PTR *offset)
{
    LDR_DATA_TABLE_ENTRY *entry;
    unsigned int i, length;
    strcpy(module, "unknown-redacted");
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
    for (i = 0; i < length; ++i) module[i] = entry->BaseDllName.Buffer[i];
    module[length] = 0;
    *offset = (ULONG_PTR)address - (ULONG_PTR)entry->DllBase;
}
static void diagnostic_status_return(struct relay_private_data *data, unsigned int ordinal,
                                     const void *caller, UINT result)
{
    const char *name = data->entry_points[ordinal].name;
    char module[128];
    ULONG_PTR offset;
    LONG sequence;
    static LONG count;
    if (!__wine_pkg_diagnostic_active() || !TRACE_ON(pkgstatus)
        || (result != 0xc0000002 && result != 0xd0000002) || !name) return;
    sequence = InterlockedIncrement(&count);
    if (sequence > 128)
    {
        if (sequence == 129) TRACE_(pkgstatus)("status-return limited=1\n");
        return;
    }
    diagnostic_status_address(caller, module, &offset);
    TRACE_(pkgstatus)("status-return module=%s export=%s result=%08x caller=%s offset=%Ix\n",
                      data->dllname, name, result, module, offset);
}
