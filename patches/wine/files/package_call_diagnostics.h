/* Fixed-metadata diagnostic wrappers, no interface semantics. LGPL-2.1-or-later */
WINE_DECLARE_DEBUG_CHANNEL(pkgiface);
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);
extern void WINAPI __wine_pkg_diagnostic_phase(UINT phase, HMODULE xaml);

static void diagnostic_interface(const char *object, const char *method, const char *phase,
                                 const GUID *iid, ULONG result, const char *kind)
{
    if (!__wine_pkg_diagnostic_active()) return;
    if (iid)
        TRACE_(pkgiface)("interface object=%s method=%s phase=%s iid=%s kind=%s result=%08lx\n",
                        object, method, phase, debugstr_guid(iid), kind, result);
    else
        TRACE_(pkgiface)("interface object=%s method=%s phase=%s iid=none kind=%s result=%08lx\n",
                        object, method, phase, kind, result);
}
