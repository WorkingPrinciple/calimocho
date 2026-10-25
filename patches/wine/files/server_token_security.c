static const struct sid *token_integrity_sid( const struct token *token )
{
    static const struct sid medium = { SID_REVISION, 1, SECURITY_MANDATORY_LABEL_AUTHORITY,
                                      { SECURITY_MANDATORY_MEDIUM_RID } };
    const struct acl *sacl;
    const struct ace *ace;
    unsigned int i;
    int present;

    if (!token->obj.sd) return &medium;
    sacl = sd_get_sacl( token->obj.sd, &present );
    if (present && sacl)
        for (i = 0, ace = ace_first( sacl ); i < sacl->count; i++, ace = ace_next( ace ))
            if (ace->type == SYSTEM_MANDATORY_LABEL_ACE_TYPE) return (const struct sid *)(ace + 1);
    return &medium;
}

DECL_HANDLER(get_token_integrity)
{
    struct token *token;
    const struct sid *sid;

    if (!(token = get_token_obj( current->process, req->handle, TOKEN_QUERY ))) return;
    sid = token_integrity_sid( token );
    reply->sid_len = sid_len( sid );
    if (get_reply_max_size() < reply->sid_len) set_error( STATUS_BUFFER_TOO_SMALL );
    else set_reply_data( sid, reply->sid_len );
    release_object( token );
}

DECL_HANDLER(set_token_security)
{
    static const SID_IDENTIFIER_AUTHORITY mandatory = SECURITY_MANDATORY_LABEL_AUTHORITY;
    struct token *token;
    const struct sid *label = get_req_data();
    unsigned int size = get_req_data_size();

    if (req->which != TokenSessionId && req->which != TokenIntegrityLevel)
    { set_error( STATUS_INVALID_INFO_CLASS ); return; }
    if ((req->which == TokenSessionId && size) ||
        (req->which == TokenIntegrityLevel &&
         (!sid_valid_size( label, size ) || sid_len( label ) != size ||
          label->revision != SID_REVISION || label->sub_count != 1 ||
          memcmp( &label->id_auth, &mandatory, sizeof(mandatory) ))))
    { set_error( STATUS_INVALID_PARAMETER ); return; }
    if (!(token = get_token_obj( current->process, req->handle,
                                 req->which == TokenSessionId ? TOKEN_ADJUST_SESSIONID : TOKEN_ADJUST_DEFAULT )))
        return;
    /* Only the privileged setter is qualified for this source candidate. */
    if (!thread_single_check_privilege( current, SeTcbPrivilege ))
        set_error( STATUS_PRIVILEGE_NOT_HELD );
    else if (req->which == TokenSessionId)
    {
        token->session_id = req->session_id;
        allocate_luid( &token->modified_id );
    }
    else if (token_assign_label( token, label ))
    {
        struct group *group;
        LIST_FOR_EACH_ENTRY( group, &token->groups, struct group, entry )
            if ((group->attrs & SE_GROUP_INTEGRITY) && group->sid.sub_count == 1)
                copy_sid( &group->sid, label );
        allocate_luid( &token->modified_id );
    }
    else if (!get_error()) set_error( STATUS_UNSUCCESSFUL );
    release_object( token );
}
