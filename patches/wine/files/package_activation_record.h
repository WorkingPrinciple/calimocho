/* Process-owned local activation record. SPDX-License-Identifier: LGPL-2.1-or-later */
#ifndef __WINE_PACKAGE_ACTIVATION_RECORD_H
#define __WINE_PACKAGE_ACTIVATION_RECORD_H

#define ProcessWineActivation ((PROCESSINFOCLASS)0x5751)
#define WINE_ACTIVATION_PROTOCOL 4
#define WINE_ACTIVATION_URI_CHARS 2048
struct wine_activation_record
{
    unsigned int version, size, kind;
    WCHAR uri[WINE_ACTIVATION_URI_CHARS];
    WCHAR caller_app_id[256];
    WCHAR entrypoint[256];
};
struct wine_package_activation
{
    struct wine_package_identity identity;
    struct wine_activation_record activation;
};
#endif
