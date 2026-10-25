"""Accept the NtAlpcConnectPortEx client attributes and EffectiveOnly QoS CoreMessaging uses.

The client port object attributes are accepted only as an unnamed, unrooted
object whose optional security descriptor is applied at creation. Any other
client attribute field still returns STATUS_NOT_IMPLEMENTED with a FIXME.
Connection message attributes are not transported: a send buffer with valid
attributes is refused, and a receive buffer comes back with no valid
attributes. Every NOT_IMPLEMENTED path in the connect logs a fixed
"reason=<token>" FIXME with at most one numeric value, so a redacted
collector can still name the rejected check.
Static EffectiveOnly captures a client token without disabled privileges and
without disabled optional groups (deny-only and mandatory groups are kept).
"""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_connect_attrs.py",)
PATHS = ("server/alpc.c", "server/token.c", "server/security.h",
         "server/protocol.def", "dlls/ntdll/unix/alpc.c")

TOKEN_HELPER = """

/* static EffectiveOnly capture: drop disabled privileges and disabled optional groups */
struct token *token_duplicate_effective( struct token *src )
{
    struct luid_attr *disabled;
    struct privilege *privilege;
    struct group *group, *next;
    struct token *token;
    unsigned int count = 0;

    LIST_FOR_EACH_ENTRY( privilege, &src->privileges, struct privilege, entry )
        if (!privilege->enabled) count++;
    if (!(disabled = mem_alloc( (count ? count : 1) * sizeof(*disabled) ))) return NULL;
    count = 0;
    LIST_FOR_EACH_ENTRY( privilege, &src->privileges, struct privilege, entry )
        if (!privilege->enabled) disabled[count++].luid = privilege->luid;
    token = token_duplicate( src, 0, src->primary ? SecurityImpersonation : src->impersonation_level,
                             NULL, disabled, count, NULL, 0 );
    free( disabled );
    if (!token) return NULL;
    LIST_FOR_EACH_ENTRY_SAFE( group, next, &token->groups, struct group, entry )
    {
        if (group->attrs & (SE_GROUP_ENABLED | SE_GROUP_MANDATORY | SE_GROUP_USE_FOR_DENY_ONLY)) continue;
        if (&group->sid == token->owner || &group->sid == token->primary_group) continue;
        list_remove( &group->entry );
        free( group );
    }
    return token;
}
"""

CLIENT_ATTR_CHECK = """    if (client_attr)
    {
        TRACE( "client attr len %u root %p name %s attrs %#x sd %p qos %p\\n", (unsigned)client_attr->Length,
               client_attr->RootDirectory, debugstr_us( client_attr->ObjectName ),
               (unsigned)client_attr->Attributes, client_attr->SecurityDescriptor,
               client_attr->SecurityQualityOfService );
        if (client_attr->Length != sizeof(*client_attr)) return STATUS_INVALID_PARAMETER;
        /* FIXME reasons are fixed tokens and numeric masks only; the collector keeps nothing else. */
        if (client_attr->RootDirectory)
        {
            FIXME( "reason=client_attr_root\\n" );
            return STATUS_NOT_IMPLEMENTED;
        }
        if (client_attr->ObjectName)
        {
            FIXME( "reason=client_attr_name\\n" );
            return STATUS_NOT_IMPLEMENTED;
        }
        if (client_attr->Attributes & ~OBJ_CASE_INSENSITIVE)
        {
            FIXME( "reason=client_attr_attributes value=%#x\\n", (unsigned)client_attr->Attributes );
            return STATUS_NOT_IMPLEMENTED;
        }
        if (client_attr->SecurityQualityOfService)
        {
            FIXME( "reason=client_attr_qos\\n" );
            return STATUS_NOT_IMPLEMENTED;
        }
        if (client_attr->SecurityDescriptor)
        {
            InitializeObjectAttributes( &client_security, NULL, 0, NULL, client_attr->SecurityDescriptor );
            if ((status = wine_server_alloc_object_attributes( &client_security, &client_packed, &client_packed_size )))
                return status;
        }
    }
    if (out_attrs) TRACE( "send attributes allocated %#x valid %#x\\n",
                          (unsigned)out_attrs->AllocatedAttributes, (unsigned)out_attrs->ValidAttributes );
    if (in_attrs) TRACE( "receive attributes allocated %#x\\n", (unsigned)in_attrs->AllocatedAttributes );
    /* No connection message attribute is transported yet: sending one is refused, and a receive
     * buffer is returned with no valid attributes, which is what an attribute-free reply carries. */
    if (out_attrs && out_attrs->ValidAttributes)
    {
        FIXME( "reason=send_attributes value=%#x\\n", (unsigned)out_attrs->ValidAttributes );
        free( client_packed );
        return STATUS_NOT_IMPLEMENTED;
    }
"""


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC connect attribute source")
    server, token, security, protocol, client = ((source / p).read_text() for p in PATHS)
    if "token_duplicate_effective" in token or "DECL_HANDLER(alpc_impersonate_connection)" not in server:
        raise ValueError("Require ALPC impersonation source without connect attributes")

    protocol = replace(protocol,
        "    VARARG(identity,bytes,identity_size); /* required server identity */\n"
        "    VARARG(message,bytes);        /* connection message (after objattr and identity) */",
        "    VARARG(identity,bytes,identity_size); /* required server identity */\n"
        "    VARARG(client_sd,bytes,client_sd_size); /* client port security descriptor */\n"
        "    VARARG(message,bytes);        /* connection message (after objattr, identity, client_sd) */")
    protocol = replace(protocol,
        "    data_size_t   identity_size;  /* identity bytes before connection message */\n",
        "    data_size_t   identity_size;  /* identity bytes before connection message */\n"
        "    data_size_t   client_sd_size; /* client port security descriptor bytes after identity */\n"
        "    unsigned int  effective_only; /* static QoS EffectiveOnly */\n")

    start = server.index("DECL_HANDLER(alpc_connect_port)")
    end = server.index("\nDECL_HANDLER(", start + 1)
    section = server[start:end]
    section = replace(section,
        "    data = (const char *)data + req->identity_size;\n    len -= req->identity_size;\n",
        "    data = (const char *)data + req->identity_size;\n    len -= req->identity_size;\n"
        "    if (req->client_sd_size > len)\n"
        "    { release_object( conn ); set_error( STATUS_INVALID_PARAMETER ); return; }\n"
        "    if (req->client_sd_size)\n"
        "    {\n"
        "        client_sd = data;\n"
        "        if (!sd_is_valid( client_sd, req->client_sd_size ))\n"
        "        { release_object( conn ); set_error( STATUS_INVALID_SECURITY_DESCR ); return; }\n"
        "        if (client_sd->sacl_len)\n"
        "        {\n"
        "            fprintf( stderr, \"alpc: client port SACL is not implemented\\n\" );\n"
        "            release_object( conn ); set_error( STATUS_NOT_IMPLEMENTED ); return;\n"
        "        }\n"
        "        data = (const char *)data + req->client_sd_size;\n"
        "        len -= req->client_sd_size;\n"
        "    }\n")
    section = replace(section, "    const void *data;\n",
        "    const void *data;\n    const struct security_descriptor *client_sd = NULL;\n")
    section = replace(section,
        "    if ((client = create_port( NULL, &empty_unicode_str, 0, NULL, CLIENT_PORT )))\n    {\n",
        "    if ((client = create_port( NULL, &empty_unicode_str, 0, client_sd, CLIENT_PORT )) &&\n"
        "        req->effective_only)\n"
        "    {\n"
        "        struct token *effective = token_duplicate_effective( client->creator_token );\n"
        "        if (!effective) { release_object( client ); client = NULL; }\n"
        "        else\n"
        "        {\n"
        "            release_object( client->creator_token );\n"
        "            client->creator_token = effective;\n"
        "        }\n"
        "    }\n"
        "    if (client)\n    {\n")
    server = server[:start] + section + server[end:]

    token = token + TOKEN_HELPER
    security = replace(security, "extern int token_impersonate_alpc( struct token * );",
        "extern int token_impersonate_alpc( struct token * );\n"
        "extern struct token *token_duplicate_effective( struct token *src );")

    begin = client.index("static NTSTATUS connect_port(")
    finish = client.index("NTSTATUS WINAPI NtAlpcConnectPort(", begin)
    section = client[begin:finish]
    section = replace(section,
        "                              const void *identity, data_size_t identity_size, unsigned int identity_kind )",
        "                              const void *identity, data_size_t identity_size, unsigned int identity_kind,\n"
        "                              const void *client_sd, data_size_t client_sd_size )")
    section = replace(section,
        "        pa->SecurityQos.ContextTrackingMode != SECURITY_STATIC_TRACKING ||\n"
        "        pa->SecurityQos.EffectiveOnly)) return STATUS_NOT_IMPLEMENTED;",
        "        pa->SecurityQos.ContextTrackingMode != SECURITY_STATIC_TRACKING)) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa) TRACE( \"qos level %u tracking %u effective %u max %lu\\n\",\n"
        "                   (unsigned)pa->SecurityQos.ImpersonationLevel,\n"
        "                   (unsigned)pa->SecurityQos.ContextTrackingMode,\n"
        "                   (unsigned)pa->SecurityQos.EffectiveOnly, (unsigned long)pa->MaxMessageLength );")
    section = replace(section, "        req->identity_size = identity_size;\n",
        "        req->identity_size = identity_size;\n"
        "        req->client_sd_size = client_sd_size;\n"
        "        req->effective_only = pa && pa->SecurityQos.EffectiveOnly;\n")
    section = replace(section,
        "        if (identity_size) wine_server_add_data( req, identity, identity_size );\n",
        "        if (identity_size) wine_server_add_data( req, identity, identity_size );\n"
        "        if (client_sd_size) wine_server_add_data( req, client_sd, client_sd_size );\n")
    client = client[:begin] + section + client[finish:]
    client = replace(client, " : 0, sd ? 1 : 0 );", " : 0, sd ? 1 : 0, NULL, 0 );")

    begin = client.index("NTSTATUS WINAPI NtAlpcConnectPortEx(")
    finish = client.index("NTSTATUS WINAPI NtAlpcAcceptConnectPort(", begin)
    section = client[begin:finish]
    section = replace(section,
        "    OBJECT_ATTRIBUTES security_attr;\n    struct object_attributes *packed = NULL;\n"
        "    data_size_t packed_size;\n",
        "    OBJECT_ATTRIBUTES security_attr, client_security;\n"
        "    struct object_attributes *packed = NULL, *client_packed = NULL;\n"
        "    data_size_t packed_size, client_packed_size;\n")
    section = replace(section,
        "    if (client_attr || out_attrs || in_attrs) return STATUS_NOT_IMPLEMENTED;\n", CLIENT_ATTR_CHECK)
    section = replace(section,
        "        if ((status = wine_server_alloc_object_attributes( &security_attr, &packed, &packed_size ))) return status;\n",
        "        if ((status = wine_server_alloc_object_attributes( &security_attr, &packed, &packed_size )))\n"
        "        {\n            free( client_packed );\n            return status;\n        }\n")
    section = replace(section,
        "                           NULL, packed ? packed + 1 : NULL, packed ? packed->sd_len : 0, packed ? 2 : 0 );\n"
        "    free( packed );\n",
        "                           NULL, packed ? packed + 1 : NULL, packed ? packed->sd_len : 0, packed ? 2 : 0,\n"
        "                           client_packed ? client_packed + 1 : NULL, client_packed ? client_packed->sd_len : 0 );\n"
        "    free( packed );\n    free( client_packed );\n"
        "    if (!status && in_attrs) in_attrs->ValidAttributes = 0;\n")
    client = client[:begin] + section + client[finish:]

    begin = client.index("static NTSTATUS connect_port(")
    finish = client.index("NTSTATUS WINAPI NtAlpcConnectPort(", begin)
    section = client[begin:finish]
    section = replace(section,
        "    if (flags & ~ALPC_SYNC_CONNECTION) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa && pa->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa && (pa->SecurityQos.Length != sizeof(pa->SecurityQos) ||\n"
        "        pa->SecurityQos.ImpersonationLevel > SecurityImpersonation ||\n"
        "        pa->SecurityQos.ContextTrackingMode != SECURITY_STATIC_TRACKING)) return STATUS_NOT_IMPLEMENTED;\n",
        "    if (flags & ~ALPC_SYNC_CONNECTION)\n"
        "    {\n        FIXME( \"reason=connect_flags value=%#x\\n\", (unsigned)flags );\n"
        "        return STATUS_NOT_IMPLEMENTED;\n    }\n"
        "    if (pa && pa->MaxMessageLength > 0x8000)\n"
        "    {\n        FIXME( \"reason=max_message_length value=%#lx\\n\", (unsigned long)pa->MaxMessageLength );\n"
        "        return STATUS_NOT_IMPLEMENTED;\n    }\n"
        "    if (pa && (pa->SecurityQos.Length != sizeof(pa->SecurityQos) ||\n"
        "        pa->SecurityQos.ImpersonationLevel > SecurityImpersonation ||\n"
        "        pa->SecurityQos.ContextTrackingMode != SECURITY_STATIC_TRACKING))\n"
        "    {\n        FIXME( \"reason=connect_qos value=%#x\\n\", (unsigned)pa->SecurityQos.ImpersonationLevel |\n"
        "               ((unsigned)pa->SecurityQos.ContextTrackingMode << 8) |\n"
        "               ((pa->SecurityQos.Length == sizeof(pa->SecurityQos)) ? 0 : 0x10000) );\n"
        "        return STATUS_NOT_IMPLEMENTED;\n    }\n")
    client = client[:begin] + section + client[finish:]

    for path, text in zip(PATHS, (server, token, security, protocol, client)):
        (source / path).write_text(text)
    return {"files": {p: sha256(source / p) for p in PATHS},
            "client_attr": "unnamed unrooted client port; optional SD without SACL; other fields NOT_IMPLEMENTED",
            "message_attributes": "send attributes with ValidAttributes NOT_IMPLEMENTED; receive buffer returns ValidAttributes 0",
            "fixme_reasons": "each NOT_IMPLEMENTED path logs reason=<token> and at most one numeric value",
            "effective_only": "static capture drops disabled privileges and disabled optional groups",
            "identification_impersonation": "still STATUS_BAD_IMPERSONATION_LEVEL"}
