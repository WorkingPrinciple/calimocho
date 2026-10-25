/* Windowless package-directory loader sentinel. SPDX-License-Identifier: LGPL-2.1-or-later */
#include <windows.h>
__declspec(dllexport) unsigned int WINAPI graph_marker(void)
{
    return 0x1234abcd;
}
