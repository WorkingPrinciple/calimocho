/*
 * Calimocho sechost additions: transient object security descriptors and WaitServiceState.
 *
 * QueryTransientObjectSecurityDescriptor follows the call shape observed in a
 * builtin relay trace (type 8 for an ALPC port, registry value
 * "SecurityDescriptor" under SecurityManager\TransientObjects). Only the ALPC
 * port type is admitted; any other type or a name that would need escaping
 * fails closed with STATUS_NOT_IMPLEMENTED. The failure status convention of
 * the native function is not measured: open and query errors are returned
 * unchanged as NTSTATUS values.
 *
 * WaitServiceState follows the documented winsvc.h contract (state value on
 * success, otherwise zero with ERROR_TIMEOUT, ERROR_CANCELLED or the query
 * error) using bounded status polling rather than service notifications.
 */

#define TRANSIENT_TYPE_ALPC_PORT 8
#define WAIT_SERVICE_STATE_POLL_MS 50

static const WCHAR transient_prefix[] =
    L"\\Registry\\Machine\\Software\\Microsoft\\SecurityManager\\TransientObjects\\%5C%5C.%5C";

/* Returns the key path length in characters, or 0 when the type or name is not admitted. */
static SIZE_T transient_key_path( DWORD type, const WCHAR *name, WCHAR *buffer, SIZE_T count )
{
    const WCHAR *kind, *p;
    SIZE_T len = 0, i;

    if (type != TRANSIENT_TYPE_ALPC_PORT || !name || !name[0]) return 0;
    kind = L"AlpcPort%5C";
    for (p = name; *p; p++) if (*p == '\\' || *p == '%' || *p == '/') return 0;
    for (p = transient_prefix; *p; p++) if (len < count) buffer[len++] = *p; else return 0;
    for (p = kind; *p; p++) if (len < count) buffer[len++] = *p; else return 0;
    for (i = 0; name[i]; i++) if (len < count) buffer[len++] = name[i]; else return 0;
    if (len >= count) return 0;
    buffer[len] = 0;
    return len;
}

/******************************************************************************
 *     QueryTransientObjectSecurityDescriptor   (sechost.@)
 */
NTSTATUS WINAPI QueryTransientObjectSecurityDescriptor( DWORD type, const WCHAR *name,
                                                        PSECURITY_DESCRIPTOR *descriptor )
{
    WCHAR path[256];
    UNICODE_STRING key_name, value_name;
    OBJECT_ATTRIBUTES attr;
    KEY_VALUE_PARTIAL_INFORMATION *info = NULL;
    ULONG size = sizeof(*info) + 256, needed = 0;
    SIZE_T len;
    HANDLE key;
    NTSTATUS status;
    void *copy;

    if (!descriptor) return STATUS_INVALID_PARAMETER;
    *descriptor = NULL;
    if (!(len = transient_key_path( type, name, path, ARRAY_SIZE(path) )))
    {
        FIXME( "reason=transient_type value=%#lx\n", (unsigned long)type );
        return STATUS_NOT_IMPLEMENTED;
    }
    TRACE( "transient sd type %lu name %s\n", (unsigned long)type, debugstr_w(name) );
    key_name.Buffer = path;
    key_name.Length = len * sizeof(WCHAR);
    key_name.MaximumLength = key_name.Length + sizeof(WCHAR);
    InitializeObjectAttributes( &attr, &key_name, OBJ_CASE_INSENSITIVE, NULL, NULL );
    if ((status = NtOpenKey( &key, KEY_READ, &attr )))
    {
        TRACE( "transient sd open status %#lx\n", (unsigned long)status );
        return status;
    }
    RtlInitUnicodeString( &value_name, L"SecurityDescriptor" );
    for (;;)
    {
        if (!(info = HeapAlloc( GetProcessHeap(), 0, size )))
        {
            status = STATUS_NO_MEMORY;
            break;
        }
        status = NtQueryValueKey( key, &value_name, KeyValuePartialInformation, info, size, &needed );
        if (status != STATUS_BUFFER_OVERFLOW && status != STATUS_BUFFER_TOO_SMALL) break;
        HeapFree( GetProcessHeap(), 0, info );
        info = NULL;
        if (needed <= size || needed > 0x10000)
        {
            status = STATUS_INVALID_SECURITY_DESCR;
            break;
        }
        size = needed;
    }
    NtClose( key );
    if (!status && (info->Type != REG_BINARY ||
                    !RtlValidRelativeSecurityDescriptor( info->Data, info->DataLength, 0 )))
        status = STATUS_INVALID_SECURITY_DESCR;
    if (!status)
    {
        if ((copy = HeapAlloc( GetProcessHeap(), 0, info->DataLength )))
        {
            memcpy( copy, info->Data, info->DataLength );
            *descriptor = copy;
        }
        else status = STATUS_NO_MEMORY;
    }
    TRACE( "transient sd status %#lx size %lu\n", (unsigned long)status,
           info && !status ? (unsigned long)info->DataLength : 0ul );
    HeapFree( GetProcessHeap(), 0, info );
    return status;
}

/******************************************************************************
 *     FreeTransientObjectSecurityDescriptor   (sechost.@)
 */
BOOL WINAPI FreeTransientObjectSecurityDescriptor( PSECURITY_DESCRIPTOR descriptor )
{
    return HeapFree( GetProcessHeap(), 0, descriptor );
}

static BOOL service_state_requested( DWORD notify, DWORD state )
{
    return state >= SERVICE_STOPPED && state <= SERVICE_PAUSED && (notify & (1u << (state - 1)));
}

/******************************************************************************
 *     WaitServiceState   (sechost.@)
 */
DWORD WINAPI WaitServiceState( SC_HANDLE service, DWORD notify, DWORD timeout, HANDLE cancel )
{
    SERVICE_STATUS_PROCESS status;
    DWORD size, start = GetTickCount(), elapsed, wait;

    TRACE( "%p %#lx %lu %p\n", service, (unsigned long)notify, (unsigned long)timeout, cancel );
    for (;;)
    {
        if (!QueryServiceStatusEx( service, SC_STATUS_PROCESS_INFO, (BYTE *)&status, sizeof(status), &size ))
            return 0;
        if (service_state_requested( notify, status.dwCurrentState ))
        {
            TRACE( "state %lu\n", (unsigned long)status.dwCurrentState );
            return status.dwCurrentState;
        }
        elapsed = GetTickCount() - start;
        if (timeout != INFINITE && elapsed >= timeout)
        {
            SetLastError( ERROR_TIMEOUT );
            return 0;
        }
        wait = WAIT_SERVICE_STATE_POLL_MS;
        if (timeout != INFINITE && timeout - elapsed < wait) wait = timeout - elapsed;
        if (cancel)
        {
            switch (WaitForSingleObject( cancel, wait ))
            {
            case WAIT_TIMEOUT:
                break;
            case WAIT_OBJECT_0:
                SetLastError( ERROR_CANCELLED );
                return 0;
            default:
                return 0;
            }
        }
        else Sleep( wait );
    }
}
