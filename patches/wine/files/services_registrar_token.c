/* Scoped single-member registrar host. Other service groups are not admitted. */
static DWORD registrar_configuration( const struct service_entry *service )
{
    HKEY key;
    WCHAR members[64];
    DWORD type, size = sizeof(members), error;

    if (wcsicmp( service->name, L"CoreMessagingRegistrar" ) ||
        !service->config.lpServiceStartName ||
        wcsicmp( service->config.lpServiceStartName, L"NT AUTHORITY\\LocalService" ) ||
        service->sid_type != 3 ||
        service->config.dwServiceType != SERVICE_WIN32_SHARE_PROCESS ||
        !service->config.lpBinaryPathName ||
        wcsicmp( service->config.lpBinaryPathName,
                 L"C:\\windows\\system32\\svchost.exe -k LocalServiceNoNetwork -p" ))
        return ERROR_NOT_SUPPORTED;
    error = RegOpenKeyExW( HKEY_LOCAL_MACHINE,
                          L"Software\\Microsoft\\Windows NT\\CurrentVersion\\SvcHost", 0, KEY_QUERY_VALUE, &key );
    if (error) return error;
    error = RegQueryValueExW( key, L"LocalServiceNoNetwork", NULL, &type, (BYTE *)members, &size );
    RegCloseKey( key );
    if (error) return error;
    if (type != REG_MULTI_SZ || size != (wcslen(service->name) + 2) * sizeof(WCHAR) ||
        memcmp( members, service->name, (wcslen(service->name) + 1) * sizeof(WCHAR) ) ||
        members[wcslen(service->name) + 1])
        return ERROR_NOT_SUPPORTED;
    return ERROR_SUCCESS;
}

static DWORD registrar_privilege_scope( HANDLE *previous, HANDLE *scope )
{
    HANDLE process = NULL;
    TOKEN_PRIVILEGES privileges = {1, {{{7, 0}, SE_PRIVILEGE_ENABLED}}};
    DWORD error;

    *previous = *scope = NULL;
    if (!OpenThreadToken( GetCurrentThread(), TOKEN_IMPERSONATE | TOKEN_QUERY, TRUE, previous ) &&
        GetLastError() != ERROR_NO_TOKEN) return GetLastError();
    if (!OpenProcessToken( GetCurrentProcess(), TOKEN_DUPLICATE | TOKEN_QUERY, &process ))
    { error = GetLastError(); goto failed; }
    if (!DuplicateTokenEx( process, TOKEN_IMPERSONATE | TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                           NULL, SecurityImpersonation, TokenImpersonation, scope ))
    { error = GetLastError(); goto failed; }
    SetLastError( ERROR_SUCCESS );
    if (!AdjustTokenPrivileges( *scope, FALSE, &privileges, 0, NULL, NULL ))
    { error = GetLastError(); goto failed; }
    if ((error = GetLastError()) != ERROR_SUCCESS) goto failed;
    if (!SetThreadToken( NULL, *scope )) { error = GetLastError(); goto failed; }
    CloseHandle( process );
    return ERROR_SUCCESS;
failed:
    if (process) CloseHandle( process );
    if (*scope) CloseHandle( *scope );
    if (*previous) CloseHandle( *previous );
    *scope = *previous = NULL;
    return error;
}

static DWORD registrar_token_readback( HANDLE token, const TOKEN_USER *user, const TOKEN_SOURCE *source,
                                       const TOKEN_GROUPS *groups, const TOKEN_GROUPS *restricted,
                                       const TOKEN_PRIVILEGES *privileges, const ACL *dacl )
{
    BYTE buffer[4096];
    TOKEN_STATISTICS statistics;
    TOKEN_SOURCE actual_source;
    TOKEN_GROUPS *actual_groups = (TOKEN_GROUPS *)buffer;
    TOKEN_PRIVILEGES *actual_privileges = (TOKEN_PRIVILEGES *)buffer;
    DWORD size, value, i;
    TOKEN_INFORMATION_CLASS classes[] = {TokenUser, TokenOwner, TokenPrimaryGroup};

    for (i = 0; i < ARRAY_SIZE(classes); i++)
    {
        if (!GetTokenInformation( token, classes[i], buffer, sizeof(buffer), &size )) return GetLastError();
        if (!EqualSid( *(PSID *)buffer, user->User.Sid )) return ERROR_INVALID_DATA;
    }
    if (!GetTokenInformation( token, TokenStatistics, &statistics, sizeof(statistics), &size )) return GetLastError();
    if (statistics.TokenType != TokenPrimary || statistics.AuthenticationId.LowPart != 0x3e5 ||
        statistics.AuthenticationId.HighPart) return ERROR_INVALID_DATA;
    if (!GetTokenInformation( token, TokenSessionId, &value, sizeof(value), &size )) return GetLastError();
    if (value) return ERROR_INVALID_DATA;
    if (!GetTokenInformation( token, TokenSource, &actual_source, sizeof(actual_source), &size )) return GetLastError();
    if (memcmp( &actual_source, source, sizeof(*source) )) return ERROR_INVALID_DATA;
    if (!GetTokenInformation( token, TokenIntegrityLevel, buffer, sizeof(buffer), &size )) return GetLastError();
    if (!EqualSid( ((TOKEN_MANDATORY_LABEL *)buffer)->Label.Sid, groups->Groups[0].Sid ) ||
        ((TOKEN_MANDATORY_LABEL *)buffer)->Label.Attributes != 96) return ERROR_INVALID_DATA;
    for (i = 0; i < 2; i++)
    {
        const TOKEN_GROUPS *expected = i ? restricted : groups;
        DWORD j;
        if (!GetTokenInformation( token, i ? TokenRestrictedSids : TokenGroups,
                                  buffer, sizeof(buffer), &size )) return GetLastError();
        if (actual_groups->GroupCount != expected->GroupCount) return ERROR_INVALID_DATA;
        for (j = 0; j < expected->GroupCount; j++)
            if (actual_groups->Groups[j].Attributes != expected->Groups[j].Attributes ||
                !EqualSid( actual_groups->Groups[j].Sid, expected->Groups[j].Sid )) return ERROR_INVALID_DATA;
    }
    if (!GetTokenInformation( token, TokenIsRestricted, &value, sizeof(value), &size )) return GetLastError();
    if (!value) return ERROR_INVALID_DATA;
    if (!GetTokenInformation( token, TokenPrivileges, buffer, sizeof(buffer), &size )) return GetLastError();
    if (actual_privileges->PrivilegeCount != privileges->PrivilegeCount) return ERROR_INVALID_DATA;
    for (i = 0; i < privileges->PrivilegeCount; i++)
        if (memcmp( &actual_privileges->Privileges[i], &privileges->Privileges[i],
                    sizeof(LUID_AND_ATTRIBUTES) )) return ERROR_INVALID_DATA;
    if (!GetTokenInformation( token, TokenDefaultDacl, buffer, sizeof(buffer), &size )) return GetLastError();
    if (!((TOKEN_DEFAULT_DACL *)buffer)->DefaultDacl ||
        ((TOKEN_DEFAULT_DACL *)buffer)->DefaultDacl->AclSize != dacl->AclSize ||
        memcmp( ((TOKEN_DEFAULT_DACL *)buffer)->DefaultDacl, dacl, dacl->AclSize )) return ERROR_INVALID_DATA;
    return ERROR_SUCCESS;
}

static DWORD create_registrar_token( struct service_entry *service, HANDLE *result )
{
    static const DWORD privilege_ids[] = {3, 5, 12, 19, 21, 23, 25, 29, 30, 33, 34};
    static const char source_name[8] = {'A','d','v','a','p','i',' ',' '};
    BYTE sid_storage[10][SECURITY_MAX_SID_SIZE], service_sid[SECURITY_MAX_SID_SIZE];
    struct { DWORD count; SID_AND_ATTRIBUTES entries[11]; } groups;
    struct { DWORD count; SID_AND_ATTRIBUTES entries[4]; } restricted;
    struct { DWORD count; LUID_AND_ATTRIBUTES entries[11]; } privileges;
    SID_IDENTIFIER_AUTHORITY nt = {SECURITY_NT_AUTHORITY};
    SID_IDENTIFIER_AUTHORITY mandatory = {SECURITY_MANDATORY_LABEL_AUTHORITY};
    SID_IDENTIFIER_AUTHORITY world = {SECURITY_WORLD_SID_AUTHORITY};
    SID_IDENTIFIER_AUTHORITY local = {SECURITY_LOCAL_SID_AUTHORITY};
    SID_IDENTIFIER_AUTHORITY creator = {SECURITY_CREATOR_SID_AUTHORITY};
    BYTE write_sid[SECURITY_MAX_SID_SIZE], system_sid[SECURITY_MAX_SID_SIZE], owner_rights[SECURITY_MAX_SID_SIZE];
    DWORD session = 0, size = sizeof(service_sid), error, i, acl_size;
    HANDLE token = NULL, filtered = NULL, previous = NULL, scope = NULL;
    TOKEN_USER user;
    TOKEN_OWNER owner;
    TOKEN_PRIMARY_GROUP primary;
    TOKEN_DEFAULT_DACL dacl;
    TOKEN_SOURCE source;
    TOKEN_MANDATORY_LABEL label;
    UNICODE_STRING name;
    OBJECT_ATTRIBUTES attributes;
    LARGE_INTEGER expires;
    LUID authentication = {0x3e5, 0}, logon;
    NTSTATUS status;
    ACL *acl = NULL;
    HKEY key;
    WCHAR *required = NULL;

    *result = NULL;
    if ((error = registrar_configuration( service ))) return error;
    /* A nonempty privilege union needs separate qualification. */
    error = RegOpenKeyExW( service->db->root_key, service->name, 0, KEY_QUERY_VALUE, &key );
    if (error) return error;
    error = load_reg_multisz( key, L"RequiredPrivileges", FALSE, &required );
    RegCloseKey( key );
    if (error) return error;
    if (required && *required) { free( required ); return ERROR_NOT_SUPPORTED; }
    free( required );
    RtlInitUnicodeString( &name, service->name );
    if ((status = RtlCreateServiceSid( &name, service_sid, &size ))) return RtlNtStatusToDosError( status );
    if ((status = NtAllocateLocallyUniqueId( &logon ))) return RtlNtStatusToDosError( status );
    if ((status = NtAllocateLocallyUniqueId( &source.SourceIdentifier ))) return RtlNtStatusToDosError( status );
    memcpy( source.SourceName, source_name, sizeof(source_name) );

#define REGISTRAR_SID(index, authority, count, a, b, c) \
    do { \
        InitializeSid( sid_storage[index], &(authority), count ); \
        *GetSidSubAuthority( sid_storage[index], 0 ) = a; \
        if (count > 1) *GetSidSubAuthority( sid_storage[index], 1 ) = b; \
        if (count > 2) *GetSidSubAuthority( sid_storage[index], 2 ) = c; \
    } while (0)
    REGISTRAR_SID(0, nt, 1, SECURITY_LOCAL_SERVICE_RID, 0, 0);
    REGISTRAR_SID(1, mandatory, 1, SECURITY_MANDATORY_SYSTEM_RID, 0, 0);
    REGISTRAR_SID(2, world, 1, SECURITY_WORLD_RID, 0, 0);
    REGISTRAR_SID(3, nt, 2, SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_USERS, 0);
    REGISTRAR_SID(4, nt, 1, SECURITY_SERVICE_RID, 0, 0);
    REGISTRAR_SID(5, local, 1, 1, 0, 0);
    REGISTRAR_SID(6, nt, 1, SECURITY_AUTHENTICATED_USER_RID, 0, 0);
    REGISTRAR_SID(7, nt, 1, SECURITY_THIS_ORGANIZATION_RID, 0, 0);
    REGISTRAR_SID(8, nt, 3, SECURITY_LOGON_IDS_RID, logon.HighPart, logon.LowPart);
    REGISTRAR_SID(9, local, 1, SECURITY_LOCAL_RID, 0, 0);
#undef REGISTRAR_SID
    groups.count = 11;
    for (i = 0; i < 7; i++)
        groups.entries[i] = (SID_AND_ATTRIBUTES){sid_storage[i + 1], 7};
    groups.entries[0].Attributes = SE_GROUP_INTEGRITY | SE_GROUP_INTEGRITY_ENABLED;
    groups.entries[7] = (SID_AND_ATTRIBUTES){service_sid, 14};
    groups.entries[8] = (SID_AND_ATTRIBUTES){sid_storage[8], SE_GROUP_LOGON_ID | 15};
    groups.entries[9] = (SID_AND_ATTRIBUTES){sid_storage[9], 7};
    /* Write Restricted Code is well-known, not an imported VM group. */
    InitializeSid( write_sid, &nt, 1 ); *GetSidSubAuthority( write_sid, 0 ) = 33;
    InitializeSid( system_sid, &nt, 1 ); *GetSidSubAuthority( system_sid, 0 ) = SECURITY_LOCAL_SYSTEM_RID;
    InitializeSid( owner_rights, &creator, 1 ); *GetSidSubAuthority( owner_rights, 0 ) = 4;
    groups.entries[10] = (SID_AND_ATTRIBUTES){write_sid, 7};
    restricted.count = 4;
    restricted.entries[0] = (SID_AND_ATTRIBUTES){service_sid, 7};
    restricted.entries[1] = (SID_AND_ATTRIBUTES){sid_storage[2], 7};
    restricted.entries[2] = (SID_AND_ATTRIBUTES){sid_storage[8], 7};
    restricted.entries[3] = (SID_AND_ATTRIBUTES){write_sid, 7};
    privileges.count = ARRAY_SIZE(privilege_ids);
    for (i = 0; i < privileges.count; i++)
    {
        privileges.entries[i].Luid = (LUID){privilege_ids[i], 0};
        privileges.entries[i].Attributes = privilege_ids[i] == 23 || privilege_ids[i] == 29 ||
                                           privilege_ids[i] == 30 ? 3 : 0;
    }
    acl_size = sizeof(ACL) + 3 * (sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD)) +
               GetLengthSid( system_sid ) + GetLengthSid( owner_rights ) + GetLengthSid( service_sid );
    if (!(acl = malloc( acl_size ))) return ERROR_NOT_ENOUGH_MEMORY;
    if (!InitializeAcl( acl, acl_size, ACL_REVISION ) ||
        !AddAccessAllowedAce( acl, ACL_REVISION, GENERIC_ALL, system_sid ) ||
        !AddAccessAllowedAce( acl, ACL_REVISION, READ_CONTROL, owner_rights ) ||
        !AddAccessAllowedAce( acl, ACL_REVISION, GENERIC_ALL, service_sid ))
    { error = GetLastError(); goto done; }
    user.User = (SID_AND_ATTRIBUTES){sid_storage[0], 0};
    owner.Owner = primary.PrimaryGroup = sid_storage[0];
    dacl.DefaultDacl = acl;
    expires.QuadPart = MAXLONGLONG;
    InitializeObjectAttributes( &attributes, NULL, 0, NULL, NULL );
    if ((error = registrar_privilege_scope( &previous, &scope ))) goto done;
    status = NtCreateToken( &token, TOKEN_ALL_ACCESS, &attributes, TokenPrimary, &authentication,
                            &expires, &user, (TOKEN_GROUPS *)&groups, (TOKEN_PRIVILEGES *)&privileges,
                            &owner, &primary, &dacl, &source );
    if (!status) status = NtSetInformationToken( token, TokenSessionId, &session, sizeof(session) );
    label.Label = (SID_AND_ATTRIBUTES){sid_storage[1], SE_GROUP_INTEGRITY};
    if (!status) status = NtSetInformationToken( token, TokenIntegrityLevel, &label, sizeof(label) );
    if (!status) status = NtFilterToken( token, WRITE_RESTRICTED, NULL, NULL, (TOKEN_GROUPS *)&restricted, &filtered );
    error = RtlNtStatusToDosError( status );
    if (!error) error = registrar_token_readback( filtered, &user, &source, (TOKEN_GROUPS *)&groups,
                                                 (TOKEN_GROUPS *)&restricted, (TOKEN_PRIVILEGES *)&privileges, acl );
    if (!SetThreadToken( NULL, previous ))
    {
        /* Never launch while a privileged temporary impersonation remains installed. */
        WINE_ERR("cannot restore SCM thread token, error %lu\n", GetLastError());
        ExitProcess( ERROR_ACCESS_DENIED );
    }
    if (!error) { *result = filtered; filtered = NULL; }
done:
    if (scope) CloseHandle( scope );
    if (previous) CloseHandle( previous );
    if (filtered) CloseHandle( filtered );
    if (token) CloseHandle( token );
    free( acl );
    return error;
}
