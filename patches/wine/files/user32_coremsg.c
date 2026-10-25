HANDLE WINAPI InitThreadCoreMessagingIocp2( HWND hwnd, DWORD *slot )
{
    return (HANDLE)NtUserCallTwoParam( HandleToUlong(hwnd), (ULONG_PTR)slot,
                                      NtUserCallTwoParam_CoreMessagingInitialize );
}

BOOL WINAPI DrainThreadCoreMessagingCompletions2( HWND hwnd )
{
    return NtUserCallTwoParam( HandleToUlong(hwnd), 0, NtUserCallTwoParam_CoreMessagingDrain );
}

DWORD WINAPI GetQueueStatusReadonly( UINT flags )
{
    return NtUserCallTwoParam( flags, 0, NtUserCallTwoParam_CoreMessagingQueueReadonly );
}

DWORD WINAPI GetQueueStatusForCoreMessaging( UINT flags )
{
    return NtUserGetQueueStatus( flags );
}

INT WINAPI ScheduleCoreMessagingDispatch( HWND hwnd, UINT operation, WPARAM wparam, LPARAM lparam, DWORD *error )
{
    INT result = 0;

    switch (operation)
    {
    case 0: result = SendMessageCallbackW( hwnd, 0x60, wparam, lparam, NULL, 0 ); break;
    case 1: result = PostMessageW( hwnd, 0x60, wparam, lparam ); break;
    case 3: result = !!SetTimer( hwnd, wparam, lparam, NULL ); break;
    case 2:
        /* The retained lane returned success from a stub; that is not implementation evidence. */
        SetLastError( ERROR_NOT_SUPPORTED );
        break;
    default: SetLastError( ERROR_INVALID_PARAMETER ); break;
    }
    if (error) *error = result ? ERROR_SUCCESS : GetLastError();
    return result;
}
