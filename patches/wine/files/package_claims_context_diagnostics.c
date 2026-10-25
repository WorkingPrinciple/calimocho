/* Genuine context binding and fixed-field diagnostics. LGPL-2.1-or-later */
#include <stdarg.h>
#include "ntstatus.h"
#include "windef.h"
#include "winternl.h"
#include "wine/debug.h"
WINE_DEFAULT_DEBUG_CHANNEL(package);
WINE_DECLARE_DEBUG_CHANNEL(pkgstatus);
#include "wine/whiny_context.h"
#ifdef _WIN64
#define WHINY_NO_DLLEXPORT
#define RtlQueryPackageClaims generated_query_package_claims
#include "package_claims_generated.h"
#undef RtlQueryPackageClaims
extern BOOL WINAPI __wine_pkg_diagnostic_active(void);

static void diagnostic_claims_context(const char *handle, unsigned int presence,
                                      int unpackaged, int gamingapp, int32_t result)
{
    static LONG count;
    LONG sequence = InterlockedIncrement(&count);
    if (sequence > 128)
    {
        if (sequence == 129) TRACE_(pkgstatus)("claims-context limited=1\n");
        return;
    }
    TRACE_(pkgstatus)("claims-context handle=%s presence=%02x unpackaged=%u gamingapp=%u result=%08x\n",
                      handle, presence, !!unpackaged, !!gamingapp, (UINT)result);
}

int32_t RtlQueryPackageClaims(void *token, uint16_t *package_name, uint64_t *package_size,
                             uint16_t *app_id, uint64_t *app_size, Guid *dynamic_id,
                             PackageClaim *claim, uint64_t *attributes)
{
    BOOL diagnostic = TRACE_ON(pkgstatus) && __wine_pkg_diagnostic_active();
    int unpackaged = 0, gamingapp = 0;
    int32_t result;
    if (diagnostic)
    {
        unpackaged = whiny_context_active("unpackaged");
        gamingapp = whiny_context_active("packaged-gamingapp-signed");
    }
    result = generated_query_package_claims(token, package_name, package_size, app_id,
                                            app_size, dynamic_id, claim, attributes);
    if (diagnostic)
    {
        const char *category = !token ? "null" : token == (void *)(LONG_PTR)-4 ? "process-token"
            : token == (void *)(LONG_PTR)-6 ? "thread-effective-token"
            : token == (void *)(LONG_PTR)-1 ? "process-handle" : "other";
        unsigned int presence = (!!package_name) | (!!package_size << 1) | (!!app_id << 2)
            | (!!app_size << 3) | (!!dynamic_id << 4) | (!!claim << 5) | (!!attributes << 6);
        diagnostic_claims_context(category, presence, unpackaged, gamingapp, result);
    }
    return result;
}
#else
NTSTATUS WINAPI RtlQueryPackageClaims(HANDLE token, void *package_id, void *package_id_size,
                                     void *app_id, void *app_id_size, void *claim,
                                     void *attributes, void *attributes_size)
{
    return STATUS_NOT_IMPLEMENTED;
}
#endif
