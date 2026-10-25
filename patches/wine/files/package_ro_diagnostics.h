/* Approved activatable type names and actual factory-serving image only. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgro);
static void diagnostic_ro(const char *operation, const char *phase, HSTRING classid,
                           REFIID iid, HRESULT result, HMODULE server)
{
    const WCHAR *text;
    WCHAR path[1024];
    char name[512], module[128] = "unknown-redacted";
    UINT32 length, i, start = 0;
    if (!TRACE_ON(pkgro)) return;
    text = WindowsGetStringRawBuffer(classid, &length);
    strcpy(name, "invalid-redacted");
    if (text && length && length < sizeof(name))
    {
        for (i = 0; i < length; ++i)
            if (!((text[i] >= 'A' && text[i] <= 'Z') || (text[i] >= 'a' && text[i] <= 'z')
                  || (text[i] >= '0' && text[i] <= '9') || text[i] == '_' || text[i] == '.')) break;
        if (i == length)
        {
            for (i = 0; i < length; ++i) name[i] = text[i];
            name[length] = 0;
        }
    }
    if (server && (length = GetModuleFileNameW(server, path, ARRAY_SIZE(path))) && length < ARRAY_SIZE(path))
    {
        for (i = 0; i < length; ++i) if (path[i] == '\\' || path[i] == '/') start = i + 1;
        if (length - start < sizeof(module))
        {
            for (i = start; i < length; ++i)
                if (!((path[i] >= 'A' && path[i] <= 'Z') || (path[i] >= 'a' && path[i] <= 'z')
                      || (path[i] >= '0' && path[i] <= '9') || path[i] == '.' || path[i] == '_' || path[i] == '-')) break;
            if (i == length)
            {
                for (i = start; i < length; ++i) module[i - start] = path[i];
                module[length - start] = 0;
            }
        }
    }
    TRACE_(pkgro)("activation operation=%s phase=%s class=%s iid=%s result=%08lx module=%s\n",
                  operation, phase, name, debugstr_guid(iid ? iid : &GUID_NULL), result, module);
}
