/* SPDX-License-Identifier: LGPL-2.1-or-later */
#include <stdarg.h>
#include <stdlib.h>
#define COBJMACROS
#include "windef.h"
#include "winbase.h"
#include "winternl.h"
#include "ntstatus.h"
#include "winstring.h"
#include "objbase.h"
#include "activation.h"
#include "propvarutil.h"
#define WIDL_using_Windows_Foundation
#define WIDL_using_Windows_System
#define WIDL_using_Wine_Internal
#include "launcher.h"
#include "async_private.h"
#undef Size
extern HRESULT async_operation_boolean_create(IUnknown *, IUnknown *, async_operation_callback,
                                               IAsyncOperation_boolean **);
