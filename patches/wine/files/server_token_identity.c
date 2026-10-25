/* Identity is token-owned; indices select copied groups, never caller memory. */
static struct sid *token_identity_sid( struct token *token, int index, int owner )
{
    struct group *group;

    if (index == -1) return token->user;
    if (index < -1) return NULL;
    LIST_FOR_EACH_ENTRY( group, &token->groups, struct group, entry )
    {
        if (!index--) return !owner || (group->attrs & SE_GROUP_OWNER) ? &group->sid : NULL;
    }
    return NULL;
}

static int token_apply_identity( struct token *token, const struct luid *authentication_id,
                                 const struct token_identity_data *identity, int primary_group )
{
    struct sid *owner = token_identity_sid( token, identity->owner, 1 );
    struct sid *primary = token_identity_sid( token, primary_group, 0 );

    if (!owner) { set_error( STATUS_INVALID_OWNER ); return 0; }
    if (!primary) { set_error( STATUS_INVALID_PRIMARY_GROUP ); return 0; }
    token->owner = owner;
    token->primary_group = primary;
    token->authentication_id = *authentication_id;
    token->source_id = identity->source_id;
    memcpy( token->source_name, identity->source_name, sizeof(token->source_name) );
    return 1;
}

static void token_copy_identity( struct token *token, const struct token *source )
{
    struct group *group, *copy;
    struct list *cursor = list_head( &token->groups );

    token->owner = source->owner == source->user ? token->user : NULL;
    token->primary_group = source->primary_group == source->user ? token->user : NULL;
    LIST_FOR_EACH_ENTRY( group, &source->groups, struct group, entry )
    {
        assert( cursor );
        copy = LIST_ENTRY( cursor, struct group, entry );
        if (source->owner == &group->sid) token->owner = &copy->sid;
        if (source->primary_group == &group->sid) token->primary_group = &copy->sid;
        cursor = list_next( &token->groups, cursor );
    }
    token->authentication_id = source->authentication_id;
    token->source_id = source->source_id;
    memcpy( token->source_name, source->source_name, sizeof(token->source_name) );
}
