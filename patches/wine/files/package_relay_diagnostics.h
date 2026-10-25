/* Native-XAML callsites only, no argument or result-pointer formatting. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgrelay);
static LONG diagnostic_run, diagnostic_initialize;
static ULONG_PTR diagnostic_xaml;
static SIZE_T diagnostic_xaml_size;
static LONG diagnostic_calls;

BOOL WINAPI __wine_pkg_diagnostic_active(void) { return InterlockedCompareExchange(&diagnostic_run, 0, 0); }
void WINAPI __wine_pkg_diagnostic_phase(UINT phase, HMODULE xaml)
{
    if (phase == 1) InterlockedExchange(&diagnostic_run, TRUE);
    else if (phase == 2)
    {
        IMAGE_NT_HEADERS *headers = xaml ? RtlImageNtHeader(xaml) : NULL;
        diagnostic_xaml = (ULONG_PTR)xaml;
        diagnostic_xaml_size = headers ? headers->OptionalHeader.SizeOfImage : 0;
        InterlockedExchange(&diagnostic_initialize, !!diagnostic_xaml_size);
        TRACE_(pkgrelay)("phase initialize=1 xaml=%u\n", !!diagnostic_xaml_size);
    }
    else if (phase == 3)
    {
        TRACE_(pkgrelay)("phase initialize=0\n");
        InterlockedExchange(&diagnostic_initialize, FALSE);
    }
    else if (phase == 4)
    {
        InterlockedExchange(&diagnostic_initialize, FALSE);
        InterlockedExchange(&diagnostic_run, FALSE);
    }
}
static BOOL diagnostic_selected(const char *module, const char *name)
{
    if (!name) return FALSE;
    if (_stricmp(module, "combase") && _stricmp(module, "twinapi.appcore")
        && _stricmp(module, "windows.ui") && _stricmp(module, "coremessaging")
        && _stricmp(module, "ntdll")) return FALSE;
    if (!_stricmp(module, "ntdll") && strncmp(name, "NtWait", 6)
        && strcmp(name, "NtSignalAndWaitForSingleObject") && strcmp(name, "NtDelayExecution")
        && strcmp(name, "RtlWaitOnAddress") && strcmp(name, "RtlEnterCriticalSection")
        && strncmp(name, "RtlAcquireSRWLock", 17)) return FALSE;
    return TRUE;
}
static void diagnostic_relay(struct relay_private_data *data, unsigned int ordinal, ULONG_PTR caller)
{
    const char *name = data->entry_points[ordinal].name;
    LONG count;
    if (!InterlockedCompareExchange(&diagnostic_initialize, 0, 0) || caller < diagnostic_xaml
        || caller - diagnostic_xaml >= diagnostic_xaml_size || !name) return;
    if (!diagnostic_selected(data->dllname, name)) return;
    count = InterlockedIncrement(&diagnostic_calls);
    if (count <= 65536)
        TRACE_(pkgrelay)("relay module=%s export=%s caller=Windows.UI.Xaml.dll offset=%Ix\n",
                        data->dllname, name, caller - diagnostic_xaml);
    else if (count == 65537) TRACE_(pkgrelay)("relay limited=1\n");
}
