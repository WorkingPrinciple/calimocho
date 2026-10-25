/* Public statuses and image-relative callers only. LGPL-2.1-or-later */
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);
#include "package_address_diagnostics.h"

static void diagnostic_error_context(const char *operation, const char *kind, HRESULT result, const void *caller)
{
    static LONG calls, failfasts;
    LONG sequence;
    BOOL failfast = !strcmp(operation, "RoFailFastWithErrorContextInternal2");
    char module[128];
    ULONG_PTR offset;
    if (!TRACE_ON(pkgro) || !__wine_pkg_diagnostic_active()) return;
    sequence = InterlockedIncrement(failfast ? &failfasts : &calls);
    if (sequence > (failfast ? 32 : 512))
    {
        if (sequence == (failfast ? 33 : 513))
            TRACE_(pkgro)("error-context limited=%s\n", failfast ? "failfast" : "operations");
        return;
    }
    diagnostic_address(caller, module, sizeof(module), &offset);
    TRACE_(pkgro)("error-context operation=%s kind=%s hresult=%08lx module=%s offset=%Ix\n",
                  operation, kind, result, module, offset);
}
