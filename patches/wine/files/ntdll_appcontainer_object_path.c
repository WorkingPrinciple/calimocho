/*
 * AppContainer namespace query, included by coremessaging_ntdll_stubs.c.
 * Package activation metadata alone is not a lowbox token or an AppContainer SID.
 * LGPL-2.1-or-later
 */
static NTSTATUS object_path_error( const char *reason, NTSTATUS status )
{
    WARN( "appcontainer_object_path reason=%s status=%08lx.\n", reason, status );
    return status;
}

static NTSTATUS object_path_parent_sid( const SID *sid )
{
    static const SID_IDENTIFIER_AUTHORITY authority = SECURITY_APP_PACKAGE_AUTHORITY;

    if (!RtlValidSid( (PSID)sid ) ||
        memcmp( &sid->IdentifierAuthority, &authority, sizeof(authority) ) ||
        sid->SubAuthorityCount < 1 || sid->SubAuthority[0] != SECURITY_APP_PACKAGE_BASE_RID)
        return STATUS_INVALID_SID;
    if (sid->SubAuthorityCount == 12) return STATUS_NOT_SUPPORTED;
    return sid->SubAuthorityCount == 8 ? STATUS_SUCCESS : STATUS_INVALID_SID;
}

NTSTATUS WINAPI RtlGetAppContainerNamedObjectPath( HANDLE token, PSID sid, BOOLEAN relative,
                                                 UNICODE_STRING *path )
{
    static const WCHAR root[] = L"\\Sessions\\";
    static const WCHAR name[] = L"AppContainerNamedObjects\\";
    union
    {
        TOKEN_APPCONTAINER_INFORMATION container;
        BYTE bytes[sizeof(TOKEN_APPCONTAINER_INFORMATION) + SECURITY_MAX_SID_SIZE];
    } info;
    TOKEN_STATISTICS statistics;
    UNICODE_STRING sid_string = {0}, session_string;
    HANDLE opened = NULL;
    WCHAR session_buffer[11];
    ULONG length, is_container, session, private_namespace;
    SIZE_T bytes;
    NTSTATUS status;

    if (!path) return object_path_error( "null_output", STATUS_INVALID_PARAMETER );
    memset( path, 0, sizeof(*path) );
    if (token && sid) return object_path_error( "token_and_sid", STATUS_INVALID_PARAMETER_MIX );
    if (sid)
        token = (HANDLE)(LONG_PTR)-4; /* Explicit SID uses the current process session. */
    else if (!token)
    {
        status = NtOpenThreadToken( (HANDLE)(LONG_PTR)-2, TOKEN_QUERY, TRUE, &opened );
        if (status == STATUS_NO_TOKEN)
            status = NtOpenProcessToken( (HANDLE)(LONG_PTR)-1, TOKEN_QUERY, &opened );
        if (status) return object_path_error( "effective_token", status );
        token = opened;
    }
    /* Wine's AppContainer queries do not validate handles themselves. */
    status = NtQueryInformationToken( token, TokenStatistics, &statistics, sizeof(statistics), &length );
    if (status) goto done;
    if (!sid)
    {
        status = NtQueryInformationToken( token, TokenIsAppContainer, &is_container,
                                         sizeof(is_container), &length );
        if (status) goto done;
        if (!is_container)
        {
            /* Current native ntdll's non-lowbox output contract is not established. */
            status = STATUS_NOT_SUPPORTED;
            goto done;
        }
        status = NtQueryInformationToken( token, TokenAppContainerSid, &info, sizeof(info), &length );
        if (status) goto done;
        if (!(sid = info.container.TokenAppContainer))
        {
            status = STATUS_INVALID_SID;
            goto done;
        }
    }
    if ((status = object_path_parent_sid( sid ))) goto done;
    if (!relative)
    {
        /* Private namespaces additionally include a user SID. Do not silently omit it.
         * Wine has no private-namespace tokens, and its query is currently unsupported. */
        status = NtQueryInformationToken( token, TokenPrivateNameSpace, &private_namespace,
                                         sizeof(private_namespace), &length );
        if (status) goto done;
        if (private_namespace)
        {
            status = STATUS_NOT_SUPPORTED;
            goto done;
        }
        status = NtQueryInformationToken( token, TokenSessionId, &session, sizeof(session), &length );
        if (status) goto done;
        session_string.Buffer = session_buffer;
        session_string.Length = 0;
        session_string.MaximumLength = sizeof(session_buffer);
        if ((status = RtlIntegerToUnicodeString( session, 10, &session_string ))) goto done;
    }
    if ((status = RtlConvertSidToUnicodeString( &sid_string, sid, TRUE ))) goto done;
    bytes = sizeof(name) + sid_string.Length;
    if (!relative) bytes += sizeof(root) - sizeof(WCHAR) + session_string.Length + sizeof(WCHAR);
    if (bytes > 0xfffe)
    {
        status = STATUS_NAME_TOO_LONG;
        goto done;
    }
    path->Buffer = RtlAllocateHeap( NtCurrentTeb()->Peb->ProcessHeap, 0, bytes );
    if (!path->Buffer)
    {
        status = STATUS_NO_MEMORY;
        goto done;
    }
    path->MaximumLength = bytes;
    path->Buffer[0] = 0;
    if (!relative)
    {
        if ((status = RtlAppendUnicodeToString( path, root )) ||
            (status = RtlAppendUnicodeStringToString( path, &session_string )) ||
            (status = RtlAppendUnicodeToString( path, L"\\" ))) goto done;
    }
    if (!(status = RtlAppendUnicodeToString( path, name )))
        status = RtlAppendUnicodeStringToString( path, &sid_string );
done:
    RtlFreeUnicodeString( &sid_string );
    if (opened) NtClose( opened );
    if (status)
    {
        RtlFreeUnicodeString( path );
        return object_path_error( "resolution", status );
    }
    TRACE( "appcontainer_object_path result=success relative=%u bytes=%u.\n", relative, path->Length );
    return STATUS_SUCCESS;
}
