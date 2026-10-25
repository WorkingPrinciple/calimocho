"""Port process-bound protocol records into a NEW copied cell009 Wine source."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def replace(root, relative, old, new):
    path = root / relative
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError("Unexpected activation seam: " + relative + ": " + old[:70])
    path.write_text(text.replace(old, new, 1))


def port(source):
    source = Path(source).resolve(strict=True)
    header = source / "include/wine/package.h"
    text = header.read_text()
    if "package_activation_record.h" in text:
        raise ValueError("Activation record port already applied")
    # Keep the common declarations inside the existing header guard.
    replace(source, "include/wine/package.h", "\n#ifndef __WINE_SERVER__",
            '\n#include "wine/package_activation_record.h"\n\n#ifndef __WINE_SERVER__')
    (source / "include/wine/package_activation_record.h").write_bytes(
        (REPO / "patches/wine/files/package_activation_record.h").read_bytes())
    replace(source, "include/Makefile.in", "\twine/package.h \\",
            "\twine/package.h \\\n\twine/package_activation_record.h \\")
    replace(source, "dlls/ntdll/unix/process.c",
            "ps_attr->Attributes[i].Size != sizeof(struct wine_package_identity)",
            "(ps_attr->Attributes[i].Size != sizeof(struct wine_package_identity)\n"
            "                    && ps_attr->Attributes[i].Size != sizeof(struct wine_package_activation))")
    replace(source, "server/process.h", "struct startup_info;",
            "struct startup_info;\nstruct wine_activation_record;")
    replace(source, "server/process.h",
            "struct startup_info *startup_info;    /* startup info while init is in progress */",
            "struct startup_info *startup_info;    /* startup info while init is in progress */\n"
            "    struct wine_activation_record *activation; /* immutable, no child inheritance */")
    replace(source, "server/process.c", "process->startup_info    = NULL;",
            "process->startup_info    = NULL;\n    process->activation      = NULL;")
    # The allocation is owned by the process, not its token or environment.
    replace(source, "server/process.c", "free( process->dir_cache );",
            "free( process->activation );\n    free( process->dir_cache );")
    replace(source, "server/process.c", "struct wine_package_identity admitted_package;",
            "struct wine_package_identity admitted_package;\n"
            "    const struct wine_activation_record *activation = NULL;")
    replace(source, "server/process.c",
            "req->package_size != sizeof(*package) || req->package_size > info->data_size",
            "(req->package_size != sizeof(*package)\n"
            "             && req->package_size != sizeof(struct wine_package_activation))\n"
            "            || req->package_size > info->data_size")
    replace(source, "server/process.c", "package = info_ptr;",
            "package = info_ptr;\n"
            "        if (req->package_size == sizeof(struct wine_package_activation))\n"
            "            activation = &((const struct wine_package_activation *)info_ptr)->activation;")
    replace(source, "server/process.c",
            "if (!token_set_package( process->token, package, req->package_size )) goto done;",
            """if (activation)
    {
        const struct wine_package_identity *caller = token_get_package_identity( current->process->token );
        unsigned int i;
        if (!package || !package->verified_gamingapp || !caller || !caller->verified_gamingapp
            || memcmp( caller->full_name, package->full_name, sizeof(caller->full_name) )
            || memcmp( caller->family_name, package->family_name, sizeof(caller->family_name) )
            || activation->version != 1 || activation->size != sizeof(*activation)
            || activation->kind != WINE_ACTIVATION_PROTOCOL
            || !activation->uri[0] || activation->uri[WINE_ACTIVATION_URI_CHARS - 1]
            || !activation->entrypoint[0] || activation->entrypoint[255])
        { set_error( STATUS_ACCESS_DENIED ); goto done; }
        for (i = 0; activation->uri[i]; ++i)
            if (activation->uri[i] < 0x20)
            { set_error( STATUS_INVALID_PARAMETER ); goto done; }
        if (!(process->activation = memdup( activation, sizeof(*activation) ))) goto done;
        memcpy( process->activation->caller_app_id, caller->app_id, sizeof(caller->app_id) );
    }
    if (!token_set_package( process->token, package, package ? sizeof(*package) : 0 )) goto done;""")
    replace(source, "server/security.h",
            "extern int token_set_package( struct token *token, const void *data, unsigned int size );",
            "struct wine_package_identity;\n"
            "extern const struct wine_package_identity *token_get_package_identity( struct token *token );\n"
            "extern int token_set_package( struct token *token, const void *data, unsigned int size );")
    replace(source, "server/token.c", "DECL_HANDLER(get_token_package)",
            """const struct wine_package_identity *token_get_package_identity( struct token *token )
{
    if (token->package_size != sizeof(struct wine_package_identity)) return NULL;
    return token->package_identity;
}

DECL_HANDLER(get_token_package)""")
    replace(source, "server/token.c", '#include "winternl.h"',
            '#include "winternl.h"\n#include "wine/package.h"')
    protocol = source / "server/protocol.def"
    protocol.write_text(protocol.read_text() + """

/* Current process only: never a caller-selected child or inherited environment. */
@REQ(get_process_activation)
@REPLY
    data_size_t size;
    VARARG(activation,bytes);
@END
""")
    process = source / "server/process.c"
    process.write_text(process.read_text() + """

DECL_HANDLER(get_process_activation)
{
    const struct wine_activation_record *activation = current->process->activation;
    if (!activation) { set_error( STATUS_NOT_FOUND ); return; }
    reply->size = sizeof(*activation);
    if (get_reply_max_size() < sizeof(*activation)) set_error( STATUS_BUFFER_TOO_SMALL );
    else set_reply_data( activation, sizeof(*activation) );
}
""")
    replace(source, "dlls/ntdll/unix/process.c",
            "switch (class)\n    {\n    UNIMPLEMENTED_INFO_CLASS(ProcessBasePriority);",
            """switch (class)
    {
    case ProcessWineActivation:
        if (handle != GetCurrentProcess()) return STATUS_ACCESS_DENIED;
        if (!info) return STATUS_INVALID_PARAMETER;
        SERVER_START_REQ( get_process_activation )
        {
            wine_server_set_reply( req, info, size );
            ret = wine_server_call( req );
            if (ret_len) *ret_len = reply->size;
        }
        SERVER_END_REQ;
        return ret;
    UNIMPLEMENTED_INFO_CLASS(ProcessBasePriority);
""")
    port_launcher(source)


def port_launcher(source):
    launcher = "dlls/windows.system.launcher/main.c"
    replace(source, launcher,
            "struct wine_package_identity requested = route->registration.identity, bound;",
            "struct wine_package_identity requested = route->registration.identity, bound;\n"
            "    struct wine_package_activation activation = {0};\n"
            '    BOOL uwp = wcscmp(route->entrypoint, L"Windows.FullTrustApplication") != 0;')
    replace(source, launcher, """    if (wcscmp(route->entrypoint, L"Windows.FullTrustApplication"))
    {
        TRACE("route scheme=%s app=%s pid=0 result=80004001 missing=uwp-protocol-activation\\n",
              debugstr_w(route->scheme), debugstr_w(requested.app_id));
        return E_NOTIMPL;
    }""", """    if (uwp)
    {
        if (!route->entrypoint[0] || wcslen(uri) >= WINE_ACTIVATION_URI_CHARS)
            return E_INVALIDARG;
        activation.identity = requested;
        activation.activation.version = 1;
        activation.activation.size = sizeof(activation.activation);
        activation.activation.kind = WINE_ACTIVATION_PROTOCOL;
        wcscpy(activation.activation.uri, uri);
        wcscpy(activation.activation.entrypoint, route->entrypoint);
    }""")
    replace(source, launcher,
            'swprintf(command_line, wcslen(image) + length + 8, L"\\"%s\\" \\"%s\\"", image + 4, uri);',
            'if (uwp) swprintf(command_line, wcslen(image) + length + 8, L"\\"%s\\"", image + 4);\n'
            '    else swprintf(command_line, wcslen(image) + length + 8, L"\\"%s\\" \\"%s\\"", image + 4, uri);')
    replace(source, launcher, "attributes.Attributes[1].Size = sizeof(requested);\n"
            "    attributes.Attributes[1].ValuePtr = &requested;",
            "attributes.Attributes[1].Size = uwp ? sizeof(activation) : sizeof(requested);\n"
            "    attributes.Attributes[1].ValuePtr = uwp ? (void *)&activation : (void *)&requested;")
