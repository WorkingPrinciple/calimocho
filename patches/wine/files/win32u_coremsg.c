/* The thread owns its completion port; window slots are checked before use. */
static HWND coremsg_window( struct user_thread_info *info, unsigned int slot )
{
    if (info->coremsg_hwnd[slot] && !is_current_thread_window( info->coremsg_hwnd[slot] ))
        info->coremsg_hwnd[slot] = 0;
    return info->coremsg_hwnd[slot];
}

HANDLE coremsg_initialize( HWND hwnd, DWORD *slot )
{
    struct user_thread_info *info = get_user_thread_info();
    unsigned int i, available = ARRAY_SIZE(info->coremsg_hwnd);
    DWORD tid;
    NTSTATUS status;

    if (!slot) { RtlSetLastWin32Error( ERROR_INVALID_PARAMETER ); return NULL; }
    if (!(tid = get_window_thread( hwnd, NULL )))
    { RtlSetLastWin32Error( ERROR_INVALID_WINDOW_HANDLE ); return NULL; }
    if (tid != HandleToULong( NtCurrentTeb()->ClientId.UniqueThread )) { RtlSetLastWin32Error( ERROR_ACCESS_DENIED ); return NULL; }
    hwnd = get_full_window_handle( hwnd );
    for (i = 0; i < ARRAY_SIZE(info->coremsg_hwnd); i++)
    {
        HWND current = coremsg_window( info, i );
        if (current == hwnd) { RtlSetLastWin32Error( ERROR_INVALID_PARAMETER ); return NULL; }
        if (!current && available == ARRAY_SIZE(info->coremsg_hwnd)) available = i;
    }
    if (available == ARRAY_SIZE(info->coremsg_hwnd))
    { RtlSetLastWin32Error( ERROR_ALREADY_INITIALIZED ); return NULL; }
    if (!info->coremsg_iocp &&
        (status = NtCreateIoCompletion( &info->coremsg_iocp, IO_COMPLETION_ALL_ACCESS, NULL, 0 )))
    {
        info->coremsg_iocp = NULL;
        RtlSetLastWin32Error( RtlNtStatusToDosError( status ) );
        return NULL;
    }
    info->coremsg_hwnd[available] = hwnd;
    *slot = available;
    return info->coremsg_iocp;
}

int coremsg_dispatch_packet(void)
{
    struct user_thread_info *info = get_user_thread_info();
    HWND windows[2];
    ULONG_PTR key, context, *entry;
    IO_STATUS_BLOCK io;
    LARGE_INTEGER zero;
    NTSTATUS status;
    unsigned int i;

    if (!info->coremsg_iocp) return COREMSG_EMPTY;
    zero.QuadPart = 0;
    status = NtRemoveIoCompletion( info->coremsg_iocp, &key, &context, &io, &zero );
    if (status == STATUS_TIMEOUT) return COREMSG_EMPTY;
    if (status) { RtlSetLastWin32Error( RtlNtStatusToDosError( status ) ); return COREMSG_ERROR; }
    /* Only the two marker values, zero- or sign-extended, are control packets. */
    if ((ULONG)context == 0x80000000 || (ULONG)context == 0x80000001)
    {
        ULONG high = (ULONG)((ULONGLONG)context >> 32);
        if (!high || high == 0xffffffff) return COREMSG_MARKER;
    }
    entry = (ULONG_PTR *)NtCurrentTeb()->Win32ClientInfo[61];
    if (!context && entry && key)
    {
        for (i = 0; i < ARRAY_SIZE(info->coremsg_hwnd); i++)
            if (coremsg_window( info, i )) break;
        if (i == ARRAY_SIZE(info->coremsg_hwnd))
        { RtlSetLastWin32Error( ERROR_INVALID_WINDOW_HANDLE ); return COREMSG_ERROR; }
        *(ULONG_PTR *)key = entry[1 + i];
        entry[1 + i] = key;
        return COREMSG_LINKED;
    }
    for (i = 0; i < ARRAY_SIZE(windows); i++) windows[i] = coremsg_window( info, i );
    for (i = 0; i < ARRAY_SIZE(windows); i++)
        if (windows[i]) send_message( windows[i], 0x60, context ? 8 : 3, context );
    return context ? COREMSG_DELIVERED : COREMSG_NOWAKE;
}

BOOL coremsg_marker( HANDLE port, ULONG marker )
{
    NTSTATUS status = NtSetIoCompletion( port, 0, (ULONG_PTR)(LONG_PTR)(LONG)marker, 0, 0 );
    if (status) RtlSetLastWin32Error( RtlNtStatusToDosError( status ) );
    return !status;
}

BOOL coremsg_drain( HWND hwnd )
{
    struct user_thread_info *info = get_user_thread_info();
    unsigned int i;
    int result;

    if (!is_current_thread_window( hwnd ))
    { RtlSetLastWin32Error( ERROR_INVALID_WINDOW_HANDLE ); return FALSE; }
    hwnd = get_full_window_handle( hwnd );
    if (!info->coremsg_iocp) { RtlSetLastWin32Error( ERROR_ACCESS_DENIED ); return FALSE; }
    for (i = 0; i < ARRAY_SIZE(info->coremsg_hwnd); i++)
    {
        if (coremsg_window( info, i ) != hwnd) continue;
        do result = coremsg_dispatch_packet(); while (result == COREMSG_LINKED);
        if (result == COREMSG_ERROR) return FALSE;
        if (result == COREMSG_DELIVERED || result == COREMSG_NOWAKE)
            return coremsg_marker( info->coremsg_iocp, 0x80000001 );
        return TRUE;
    }
    RtlSetLastWin32Error( ERROR_INVALID_PARAMETER );
    return FALSE;
}

DWORD coremsg_queue_readonly( UINT flags )
{
    DWORD result = 0;
    if (flags & ~(QS_ALLINPUT | QS_ALLPOSTMESSAGE | QS_SMRESULT))
    { RtlSetLastWin32Error( ERROR_INVALID_FLAGS ); return 0; }
    check_for_events( flags );
    SERVER_START_REQ( get_queue_status )
    {
        req->clear_bits = 0;
        if (!wine_server_call( req ))
            result = MAKELONG( reply->changed_bits & flags, reply->wake_bits & flags );
    }
    SERVER_END_REQ;
    return result;
}
