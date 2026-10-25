"""Add real restricting-SID state and access checking to the owned Wine source."""
from pathlib import Path
import hashlib
import subprocess

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_restricted_token.py", "patches/wine/files/server_restricted_token.c")
WRITE_MATRIX = {
    "repository": "/Users/dragoshont/xbox-install/xm",
    "commit": "c1ad52800417fa8be1c3783b733b3cacffcd59aa",
    "path": "scripts/macos/compatibility/xaml-startup/probe-outputs/native-write-overlap.txt",
    "sha256": "a6e3a715a14fe7131a87dc2f7bc1a7886792666b765b887ceb5067892c2f445d",
}


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned restricted-token source")
    paths = ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c",
             "server/restricted_token.c")
    if (source / "server/restricted_token.c").exists():
        raise ValueError("Use a fresh source tree for restricted-token port")
    data = subprocess.check_output([
        "git", "--no-replace-objects", "show", WRITE_MATRIX["commit"] + ":" + WRITE_MATRIX["path"],
    ], cwd=WRITE_MATRIX["repository"])
    if hashlib.sha256(data).hexdigest() != WRITE_MATRIX["sha256"]:
        raise ValueError("Native restricted-access matrix changed")
    token = (source / "server/token.c").read_text()
    start = token.index("static unsigned int get_sid_count(")
    end = token.index("\n/* checks whether all members", start)
    token = token[:start] + token[end:]
    token = replace(token,
        "    struct sid    *user;            /* SID of user this token represents */",
        "    struct list    restricted_sids;\n    unsigned int   restricted;\n"
        "    unsigned int   write_restricted;\n"
        "    struct sid    *user;            /* SID of user this token represents */")
    token = replace(token, "        list_init( &token->groups );",
        "        list_init( &token->groups );\n        list_init( &token->restricted_sids );\n"
        "        token->restricted = 0;\n        token->write_restricted = 0;")
    token = replace(token, "    free( token->default_dacl );\n    free( token->package_identity );",
        "    LIST_FOR_EACH_SAFE( cursor, cursor_next, &token->restricted_sids )\n"
        "    {\n        struct group *group = LIST_ENTRY( cursor, struct group, entry );\n"
        "        list_remove( &group->entry );\n        free( group );\n    }\n"
        "    free( token->default_dacl );\n    free( token->package_identity );")
    token = replace(token, "static int filter_group(",
                     '#include "restricted_token.c"\n\nstatic int filter_group(')
    token = replace(token, "    if (src_token->package_size)",
        "    token->restricted = src_token->restricted;\n"
        "    if (!token_copy_restrictions( token, src_token ))\n"
        "    {\n        release_object( token );\n        return NULL;\n    }\n"
        "    if (src_token->package_size)")
    # Keep original access-check behavior on unrestricted tokens; intersect its final grant.
    token = replace(token,
        "        if (desired_access == current_access)\n"
        "        {\n            *granted_access = current_access;\n"
        "            return *status = STATUS_SUCCESS;\n        }\n"
        "    }\n\n    /* 4:",
        "        if (desired_access == current_access && !token->restricted)\n"
        "        {\n            *granted_access = current_access;\n"
        "            return *status = STATUS_SUCCESS;\n        }\n"
        "    }\n\n    /* 4:")
    token = replace(token,
        "    *status = *granted_access ? STATUS_SUCCESS : STATUS_ACCESS_DENIED;",
        "    *granted_access = token_restricted_access( token, sd, mapping, *granted_access );\n"
        "    if (!(desired_access & MAXIMUM_ALLOWED) &&\n"
        "        (*granted_access & desired_access) != desired_access) *granted_access = 0;\n"
        "    *status = *granted_access ? STATUS_SUCCESS : STATUS_ACCESS_DENIED;")
    start = token.index("DECL_HANDLER(filter_token)")
    end = token.index("\n/* checks the specified privileges", start)
    token = token[:start] + """DECL_HANDLER(filter_token)
{
    struct token *source, *token;
    const struct luid_attr *privileges = get_req_data();
    const struct sid *disabled, *restricted, *sid;
    unsigned int size = get_req_data_size(), disabled_count = 0, restricted_count = 0, remaining;

    if (req->flags & ~8 || req->privileges_size > size ||
        req->privileges_size % sizeof(*privileges) ||
        req->disabled_size > size - req->privileges_size)
    { set_error( STATUS_INVALID_PARAMETER ); return; }
    disabled = (const struct sid *)((const char *)privileges + req->privileges_size);
    restricted = (const struct sid *)((const char *)disabled + req->disabled_size);
    sid = disabled;
    remaining = req->disabled_size;
    while (remaining)
    {
        if (!sid_valid_size( sid, remaining )) { set_error( STATUS_INVALID_SID ); return; }
        remaining -= sid_len( sid );
        sid = (const struct sid *)((const char *)sid + sid_len( sid ));
        disabled_count++;
    }
    sid = restricted;
    remaining = size - req->privileges_size - req->disabled_size;
    while (remaining)
    {
        if (!sid_valid_size( sid, remaining )) { set_error( STATUS_INVALID_SID ); return; }
        remaining -= sid_len( sid );
        sid = (const struct sid *)((const char *)sid + sid_len( sid ));
        restricted_count++;
    }
    if (!(source = (struct token *)get_handle_obj( current->process, req->handle,
                                                  TOKEN_DUPLICATE, &token_ops ))) return;
    token = token_duplicate( source, source->primary, source->impersonation_level, NULL,
                             privileges, req->privileges_size / sizeof(*privileges),
                             disabled, disabled_count );
    if (token)
    {
        int valid = 1;
        if (restricted_count)
        {
            struct group *group, *next;
            LIST_FOR_EACH_ENTRY_SAFE( group, next, &token->restricted_sids, struct group, entry )
            {
                list_remove( &group->entry );
                free( group );
            }
            valid = token_add_restrictions( token, source, restricted, restricted_count, req->flags );
        }
        if (valid)
        {
            unsigned int access = get_handle_access( current->process, req->handle );
            allocate_luid( &token->modified_id );
            reply->new_handle = alloc_handle_no_access_check( current->process, token, access, 0 );
        }
        release_object( token );
    }
    release_object( source );
}
""" + token[end:]
    # get_token_groups handles either the regular or the restricting group list.
    start = token.index("DECL_HANDLER(get_token_groups)")
    end = token.index("\nDECL_HANDLER(get_token_info)", start)
    group_handler = token[start:end]
    group_handler = replace(group_handler, "        const struct group *group;",
        "        const struct group *group;\n"
        "        const struct list *groups = req->restricted ? &token->restricted_sids : &token->groups;")
    group_handler = group_handler.replace("&token->groups, const struct group", "groups, const struct group")
    token = token[:start] + group_handler + token[end:]
    token = replace(token, "        reply->token_id = token->token_id;",
        "        reply->restricted = token->restricted;\n"
        "        reply->token_id = token->token_id;")

    protocol = (source / "server/protocol.def").read_text()
    protocol = replace(protocol,
        "    data_size_t   privileges_size; /* size of privileges */\n",
        "    data_size_t   privileges_size; /* size of privileges */\n"
        "    data_size_t   disabled_size;   /* size of disabled SID array */\n")
    protocol = replace(protocol,
        "    VARARG(disable_sids,sid);      /* array of groups to remove from new token */",
        "    VARARG(disable_sids,bytes,disabled_size); /* groups to disable */\n"
        "    VARARG(restrict_sids,sids);    /* restricting SID array */")
    protocol = replace(protocol,
        "    unsigned int    attr_mask;    /* mask for wanted attributes */",
        "    unsigned int    attr_mask;    /* mask for wanted attributes */\n"
        "    int             restricted;   /* select restricting SIDs */")
    protocol = replace(protocol,
        "    struct luid    token_id;      /* locally-unique identifier of the token */",
        "    int            restricted;    /* has a restricting SID filter */\n"
        "    struct luid    token_id;      /* locally-unique identifier of the token */")

    client = (source / "dlls/ntdll/unix/security.c").read_text()
    client = replace(client, "    case TokenGroups:\n    case TokenLogonSid:",
                     "    case TokenGroups:\n    case TokenRestrictedSids:\n    case TokenLogonSid:")
    client = replace(client, "            req->attr_mask = (class == TokenLogonSid) ? SE_GROUP_LOGON_ID : 0;",
        "            req->attr_mask = (class == TokenLogonSid) ? SE_GROUP_LOGON_ID : 0;\n"
        "            req->restricted = class == TokenRestrictedSids;")
    client = replace(client, "        TOKEN_GROUPS *groups = info;\n        ULONG i, count, needed_size;",
        "        TOKEN_GROUPS *groups = info;\n        ULONG i, count, needed_size;\n\n"
        "        if (!buffer && length) return STATUS_NO_MEMORY;")
    for label in ("TokenHasRestrictions", "TokenIsRestricted"):
        client = replace(client, "        0,    /* " + label + " */",
                         "        sizeof(DWORD), /* " + label + " */")
    client = replace(client, "    case TokenStatistics:\n",
        "    case TokenHasRestrictions:\n    case TokenIsRestricted:\n"
        "        SERVER_START_REQ( get_token_info )\n        {\n"
        "            req->handle = wine_server_obj_handle( token );\n"
        "            if (!(status = wine_server_call( req ))) *(DWORD *)info = reply->restricted;\n"
        "        }\n        SERVER_END_REQ;\n        break;\n\n    case TokenStatistics:\n")
    start = client.index("NTSTATUS WINAPI NtFilterToken(")
    end = client.index("\n\n\n/***********************************************************************", start)
    client = client[:start] + """static NTSTATUS pack_filter_sids( const TOKEN_GROUPS *groups, SID **output, data_size_t *length )
{
    unsigned int i;
    SIZE_T total = 0;
    BYTE *cursor;

    *output = NULL;
    *length = 0;
    if (!groups || !groups->GroupCount) return STATUS_SUCCESS;
    for (i = 0; i < groups->GroupCount; i++)
    {
        SID *sid = groups->Groups[i].Sid;
        SIZE_T size;
        if (!sid || sid->Revision != SID_REVISION || sid->SubAuthorityCount > SID_MAX_SUB_AUTHORITIES)
            return STATUS_INVALID_SID;
        size = offsetof( SID, SubAuthority[sid->SubAuthorityCount] );
        if (size > ~(data_size_t)0 - total) return STATUS_INVALID_PARAMETER;
        total += size;
    }
    if (!(*output = malloc( total ))) return STATUS_NO_MEMORY;
    cursor = (BYTE *)*output;
    for (i = 0; i < groups->GroupCount; i++)
    {
        SID *sid = groups->Groups[i].Sid;
        SIZE_T size = offsetof( SID, SubAuthority[sid->SubAuthorityCount] );
        memcpy( cursor, sid, size );
        cursor += size;
    }
    *length = total;
    return STATUS_SUCCESS;
}

NTSTATUS WINAPI NtFilterToken( HANDLE token, ULONG flags, TOKEN_GROUPS *disable_sids,
                               TOKEN_PRIVILEGES *privileges, TOKEN_GROUPS *restrict_sids, HANDLE *new_token )
{
    SID *disabled = NULL, *restricted = NULL;
    data_size_t disabled_size, restricted_size, privileges_size = 0;
    NTSTATUS status;

    TRACE( "%p %#x %p %p %p %p\\n", token, flags, disable_sids, privileges, restrict_sids, new_token );
    if (!new_token) return STATUS_ACCESS_VIOLATION;
    *new_token = NULL;
    if (flags & ~8) return STATUS_NOT_IMPLEMENTED;
    if (privileges)
    {
        if (privileges->PrivilegeCount > ~(data_size_t)0 / sizeof(LUID_AND_ATTRIBUTES))
            return STATUS_INVALID_PARAMETER;
        privileges_size = privileges->PrivilegeCount * sizeof(LUID_AND_ATTRIBUTES);
    }
    if ((status = pack_filter_sids( disable_sids, &disabled, &disabled_size ))) return status;
    if ((status = pack_filter_sids( restrict_sids, &restricted, &restricted_size )))
    {
        free( disabled );
        return status;
    }
    SERVER_START_REQ( filter_token )
    {
        req->handle = wine_server_obj_handle( token );
        req->flags = flags;
        req->privileges_size = privileges_size;
        req->disabled_size = disabled_size;
        if (privileges_size) wine_server_add_data( req, privileges->Privileges, privileges_size );
        wine_server_add_data( req, disabled, disabled_size );
        wine_server_add_data( req, restricted, restricted_size );
        status = wine_server_call( req );
        if (!status) *new_token = wine_server_ptr_handle( reply->new_handle );
    }
    SERVER_END_REQ;
    free( disabled );
    free( restricted );
    return status;
}""" + client[end:]
    (source / "server/token.c").write_text(token)
    (source / "server/protocol.def").write_text(protocol)
    (source / "dlls/ntdll/unix/security.c").write_text(client)
    (source / "server/restricted_token.c").write_bytes(
        (REPO / "patches/wine/files/server_restricted_token.c").read_bytes())
    return {"files": {p: sha256(source / p) for p in paths},
            "write_matrix": WRITE_MATRIX,
            "registrar_qualified": False,
            "unsupported_filter_flags": "all except WRITE_RESTRICTED"}
