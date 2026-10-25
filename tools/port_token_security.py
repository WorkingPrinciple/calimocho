"""Replace successful session/integrity token setter stubs with guarded state."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_token_security.py", "patches/wine/files/server_token_security.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned token security source")
    paths = ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c",
             "server/token_security.c")
    if (source / paths[-1]).exists():
        raise ValueError("Require fresh token security source")
    token = (source / paths[0]).read_text() + '\n#include "token_security.c"\n'
    protocol = (source / paths[1]).read_text() + """

/* Stored token integrity, not a fixed synthetic high label. */
@REQ(get_token_integrity)
    obj_handle_t handle;
@REPLY
    data_size_t sid_len;
    VARARG(sid,sid);
@END

/* Privileged session/integrity mutation. */
@REQ(set_token_security)
    obj_handle_t handle;
    int which;
    unsigned int session_id;
    VARARG(label,sid);
@END
"""
    client = (source / paths[2]).read_text()
    start = client.index("    case TokenIntegrityLevel:\n")
    end = client.index("\n    case TokenUIAccess:", start)
    client = client[:start] + """    case TokenIntegrityLevel:
        SERVER_START_REQ( get_token_integrity )
        {
            TOKEN_MANDATORY_LABEL *label = info;
            ULONG space = length < sizeof(*label) ? 0 : length - sizeof(*label);
            req->handle = wine_server_obj_handle( token );
            wine_server_set_reply( req, label + 1, space );
            status = wine_server_call( req );
            if (retlen) *retlen = sizeof(*label) + reply->sid_len;
            if (!status)
            {
                label->Label.Sid = label + 1;
                label->Label.Attributes = SE_GROUP_INTEGRITY | SE_GROUP_INTEGRITY_ENABLED;
            }
        }
        SERVER_END_REQ;
        break;
""" + client[end:]
    client = replace(client,
        '        FIXME("TokenSessionId stub!\\n");\n        ret = STATUS_SUCCESS;',
        "        SERVER_START_REQ( set_token_security )\n        {\n"
        "            req->handle = wine_server_obj_handle( token );\n"
        "            req->which = TokenSessionId;\n"
        "            req->session_id = *(const DWORD *)info;\n"
        "            ret = wine_server_call( req );\n        }\n        SERVER_END_REQ;")
    client = replace(client,
        '        FIXME( "TokenIntegrityLevel stub!\\n" );\n        ret = STATUS_SUCCESS;',
        """        {
            const TOKEN_MANDATORY_LABEL *label = info;
            const SID *sid;
            if (length < sizeof(*label)) { ret = STATUS_INFO_LENGTH_MISMATCH; break; }
            if (!label) { ret = STATUS_ACCESS_VIOLATION; break; }
            sid = label->Label.Sid;
            if (!sid || sid->Revision != SID_REVISION || sid->SubAuthorityCount != 1 ||
                !(label->Label.Attributes & SE_GROUP_INTEGRITY))
            { ret = STATUS_INVALID_PARAMETER; break; }
            SERVER_START_REQ( set_token_security )
            {
                req->handle = wine_server_obj_handle( token );
                req->which = TokenIntegrityLevel;
                wine_server_add_data( req, sid, offsetof(SID, SubAuthority[1]) );
                ret = wine_server_call( req );
            }
            SERVER_END_REQ;
        }""")
    for path, text in zip(paths, (token, protocol, client)):
        (source / path).write_text(text)
    (source / paths[-1]).write_bytes((REPO / SOURCES[-1]).read_bytes())
    return {"files": {p: sha256(source / p) for p in paths}, "registrar_qualified": False,
            "scope": "privileged session/integrity setters; unprivileged integrity mutation not admitted"}
