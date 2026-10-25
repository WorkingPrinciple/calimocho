/* Actual RPC connection attempt; no binding strings or endpoint names. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgrpc);
static void diagnostic_rpc(const char *phase, RPC_STATUS result, const void *caller)
{
    HMODULE module;
    WCHAR path[1024];
    char name[128] = "unknown-redacted";
    DWORD length, i, start = 0;
    ULONG_PTR offset = 0;
    if (!TRACE_ON(pkgrpc)) return;
    if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (const WCHAR *)caller, &module)
        && (length = GetModuleFileNameW(module, path, ARRAY_SIZE(path))) && length < ARRAY_SIZE(path))
    {
        for (i = 0; i < length; ++i) if (path[i] == '\\' || path[i] == '/') start = i + 1;
        if (length > start && length - start < sizeof(name))
        {
            for (i = start; i < length; ++i)
                if (!((path[i] >= 'A' && path[i] <= 'Z') || (path[i] >= 'a' && path[i] <= 'z')
                      || (path[i] >= '0' && path[i] <= '9') || path[i] == '_' || path[i] == '.' || path[i] == '-')) break;
            if (i == length)
            {
                for (i = start; i < length; ++i) name[i - start] = path[i];
                name[length - start] = 0;
                offset = (ULONG_PTR)caller - (ULONG_PTR)module;
            }
        }
    }
    TRACE_(pkgrpc)("rpc operation=OpenClientConnection phase=%s result=%08lx module=%s offset=%Ix endpoint=redacted\n",
                   phase, result, name, offset);
}
