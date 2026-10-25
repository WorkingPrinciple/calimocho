"""Preserve the measured service token's owner, group and source identity."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_token_identity.py", "patches/wine/files/server_token_identity.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned token identity source")
    paths = ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c",
             "server/token_identity.c")
    if (source / paths[-1]).exists():
        raise ValueError("Require fresh token identity source")
    token = (source / paths[0]).read_text()
    token = replace(token, "    struct sid    *user;",
        "    struct luid    authentication_id;\n    struct luid    source_id;\n"
        "    char           source_name[8];\n    struct sid    *user;")
    token = replace(token, "        token->restricted = 0;",
        "        token->authentication_id = (struct luid){0, 0};\n"
        "        token->source_id = (struct luid){0, 0};\n"
        "        memset( token->source_name, 0, sizeof(token->source_name) );\n"
        "        token->restricted = 0;")
    token = replace(token, "        /* copy groups */",
        "        token->owner = token->user;\n"
        "        token->primary_group = token->user;\n\n        /* copy groups */")
    token = replace(token, '#include "restricted_token.c"',
        '#include "restricted_token.c"\n#include "token_identity.c"')
    token = replace(token,
        "            if (!privilege_add( token, privs[i].luid, privs[i].attrs & SE_PRIVILEGE_ENABLED ))",
        "            struct privilege *privilege;\n"
        "            if (!(privilege = privilege_add( token, privs[i].luid, privs[i].attrs & SE_PRIVILEGE_ENABLED )))")
    token = replace(token,
        "                return NULL;\n            }\n        }\n\n        if (default_dacl)",
        "                return NULL;\n            }\n"
        "            privilege->def = !!(privs[i].attrs & SE_PRIVILEGE_ENABLED_BY_DEFAULT);\n"
        "        }\n\n        if (default_dacl)")
    token = replace(token, "    assert( token->primary_group );\n\n    /* copy privileges */",
        "    token_copy_identity( token, src_token );\n"
        "    assert( token->primary_group && token->owner );\n\n    /* copy privileges */")
    token = replace(token,
        "        if (filter_privilege( privilege, remove_privs, remove_priv_count )) continue;\n"
        "        if (!privilege_add( token, privilege->luid, privilege->enabled ))",
        "        struct privilege *newpriv;\n\n"
        "        if (filter_privilege( privilege, remove_privs, remove_priv_count )) continue;\n"
        "        if (!(newpriv = privilege_add( token, privilege->luid, privilege->enabled )))")
    start = token.index("    /* copy privileges */", token.index("struct token *token_duplicate("))
    end = token.index("\n    if (sd) default_set_sd(", start)
    section = token[start:end]
    section = replace(section, "            return NULL;\n        }\n    }",
        "            return NULL;\n        }\n        newpriv->def = privilege->def;\n    }")
    token = token[:start] + section + token[end:]
    start = token.index("DECL_HANDLER(create_token)")
    end = token.index("\n/* open a security token */", start)
    section = token[start:end]
    section = replace(section, "    struct sid *sid;", "    struct sid *sid;\n    const struct token_identity_data *identity;")
    section = replace(section,
        "    if (!user || !sid_valid_size( user, data_size ))",
        "    if (data_size < sizeof(*identity)) { set_error( STATUS_INVALID_PARAMETER ); return; }\n"
        "    identity = (const struct token_identity_data *)user;\n"
        "    data_size -= sizeof(*identity);\n    user = (struct sid *)(identity + 1);\n"
        "    fprintf( stderr, \"wineserver: create_token pid %04x data %u groups %d privs %d primary %d owner %d\\n\",\n"
        "             current->process->id, data_size, req->group_count, req->priv_count,\n"
        "             req->primary_group, identity->owner );\n"
        "    if (req->group_count < 0 || req->priv_count < 0 || identity->reserved ||\n"
        "        !sid_valid_size( user, data_size ))")
    section = replace(section,
        "    groups_size = req->group_count * sizeof( attrs[0] );",
        "    if (req->group_count > data_size / sizeof(attrs[0]))\n"
        "    { set_error( STATUS_INVALID_PARAMETER ); return; }\n"
        "    groups_size = req->group_count * sizeof( attrs[0] );")
    section = replace(section, "req->primary_group < 0", "req->primary_group < -1")
    section = replace(section,
        "    groups = mem_alloc( req->group_count * sizeof( groups[0] ) );",
        "    groups = mem_alloc( (req->group_count ? req->group_count : 1) * sizeof( groups[0] ) );")
    section = replace(section, "data_size < req->priv_count * sizeof( privs[0] )",
        "req->priv_count > data_size / sizeof(privs[0])")
    section = replace(section,
        "        reply->token = alloc_handle( current->process, token, req->access, params.attr );",
        "        if (token_apply_identity( token, &req->token_id, identity, req->primary_group ))\n"
        "            reply->token = alloc_handle( current->process, token, req->access, params.attr );")
    token = token[:start] + section + token[end:]
    token += """

DECL_HANDLER(get_token_identity)
{
    struct token *token;
    unsigned int access = req->source ? TOKEN_QUERY_SOURCE : TOKEN_QUERY;

    if (!(token = get_token_obj( current->process, req->handle, access ))) return;
    reply->authentication_id = token->authentication_id;
    reply->source_id = token->source_id;
    if (req->source)
    {
        if (get_reply_max_size() < sizeof(token->source_name)) set_error( STATUS_BUFFER_TOO_SMALL );
        else set_reply_data( token->source_name, sizeof(token->source_name) );
    }
    release_object( token );
}
"""
    protocol = (source / paths[1]).read_text()
    protocol = replace(protocol, "struct luid_attr\n",
        "struct token_identity_data\n{\n    struct luid source_id;\n"
        "    char source_name[8];\n    int owner;\n    unsigned int reserved;\n};\n\nstruct luid_attr\n")
    protocol = replace(protocol, "    /* VARARG(user,sid); */",
        "    /* VARARG(identity,token_identity_data); */\n    /* VARARG(user,sid); */")
    protocol += """

/* Query authentication and source identity, with distinct source query rights. */
@REQ(get_token_identity)
    obj_handle_t handle;
    int source;
@REPLY
    struct luid authentication_id;
    struct luid source_id;
    VARARG(source_name,bytes);
@END
"""
    client = (source / paths[2]).read_text()
    start = client.index("NTSTATUS WINAPI NtCreateToken(")
    end = client.index("\n\n/***********************************************************************", start)
    section = client[start:end]
    section = replace(section, "    int primary_group = -1;",
        "    int primary_group = -2;\n    struct token_identity_data identity = {0};\n"
        "    identity.owner = -2;")
    section = replace(section, "    if (attr->SecurityQualityOfService)",
        "    if (attr && attr->SecurityQualityOfService)")
    section = replace(section, "    groups_size = groups->GroupCount * sizeof( attrs[0] );",
        "    if (is_equal_sid( user->User.Sid, group->PrimaryGroup )) primary_group = -1;\n"
        "    if (!owner || !owner->Owner || is_equal_sid( user->User.Sid, owner->Owner )) identity.owner = -1;\n"
        "    identity.source_id.low_part = source->SourceIdentifier.LowPart;\n"
        "    identity.source_id.high_part = source->SourceIdentifier.HighPart;\n"
        "    memcpy( identity.source_name, source->SourceName, sizeof(identity.source_name) );\n"
        "    groups_size = groups->GroupCount * sizeof( attrs[0] );")
    section = replace(section, "        if (is_equal_sid( sid, group_sid ))",
        "        if (identity.owner == -2 && is_equal_sid( sid, owner->Owner )) identity.owner = i;\n"
        "        if (primary_group == -2 && is_equal_sid( sid, group_sid ))")
    section = replace(section, "    if (primary_group == -1)",
        "    if (identity.owner == -2)\n"
        "    { free( objattr ); return STATUS_INVALID_OWNER; }\n"
        "    if (primary_group == -2)")
    section = replace(section, "    groups_info = malloc( groups_size );",
        "    groups_info = malloc( groups_size ? groups_size : 1 );")
    # A request carries at most __SERVER_MAX_DATA (5) data chunks. Upstream already uses five here
    # (objattr, user, groups, privileges, DACL), so identity shares one buffer with the user SID:
    # the server reads the same byte stream. A sixth chunk overflowed __req.data (cell027-032).
    section = replace(section, "    BYTE *p;", "    BYTE *p, *head;\n    data_size_t head_size;")
    section = replace(section, "    SERVER_START_REQ( create_token )",
        "    sid = user->User.Sid;\n"
        "    head_size = sizeof(identity) + offsetof( SID, SubAuthority[sid->SubAuthorityCount] );\n"
        "    if (!(head = malloc( head_size )))\n"
        "    {\n        free( groups_info );\n        free( objattr );\n        return STATUS_NO_MEMORY;\n    }\n"
        "    memcpy( head, &identity, sizeof(identity) );\n"
        "    memcpy( head + sizeof(identity), sid, head_size - sizeof(identity) );\n\n"
        "    SERVER_START_REQ( create_token )")
    section = replace(section,
        "        sid = user->User.Sid;\n"
        "        wine_server_add_data( req, sid, offsetof( SID, SubAuthority[sid->SubAuthorityCount] ) );",
        "        wine_server_add_data( req, head, head_size );")
    section = replace(section, "    free( groups_info );\n    free( objattr );\n\n    return status;",
        "    free( head );\n    free( groups_info );\n    free( objattr );\n\n    return status;")
    client = client[:start] + section + client[end:]
    client = replace(client,
        "                statistics->AuthenticationId.LowPart  = 0; /* FIXME */\n"
        "                statistics->AuthenticationId.HighPart = 0; /* FIXME */",
        "                SERVER_START_REQ( get_token_identity )\n                {\n"
        "                    req->handle = wine_server_obj_handle( token );\n"
        "                    req->source = 0;\n                    status = wine_server_call( req );\n"
        "                    if (!status)\n                    {\n"
        "                        statistics->AuthenticationId.LowPart = reply->authentication_id.low_part;\n"
        "                        statistics->AuthenticationId.HighPart = reply->authentication_id.high_part;\n"
        "                    }\n                }\n                SERVER_END_REQ;")
    client = replace(client, "    case TokenStatistics:\n",
        "    case TokenSource:\n        SERVER_START_REQ( get_token_identity )\n        {\n"
        "            TOKEN_SOURCE *source = info;\n"
        "            req->handle = wine_server_obj_handle( token );\n            req->source = 1;\n"
        "            wine_server_set_reply( req, source->SourceName, sizeof(source->SourceName) );\n"
        "            if (!(status = wine_server_call( req )))\n            {\n"
        "                source->SourceIdentifier.LowPart = reply->source_id.low_part;\n"
        "                source->SourceIdentifier.HighPart = reply->source_id.high_part;\n"
        "            }\n        }\n        SERVER_END_REQ;\n        break;\n\n    case TokenStatistics:\n")
    for path, text in zip(paths, (token, protocol, client)):
        (source / path).write_text(text)
    (source / paths[-1]).write_bytes((REPO / SOURCES[-1]).read_bytes())
    return {"files": {p: sha256(source / p) for p in paths},
            "registrar_qualified": False,
            "identity": "user or owned group owner/primary group; caller-supplied authentication/source identity"}
