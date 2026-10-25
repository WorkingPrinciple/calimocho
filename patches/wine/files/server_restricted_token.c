/* Restricting-SID ownership and the second access-check pass. LGPL-2.1-or-later */
static int token_restricted_sid_present( const struct token *token, const struct sid *sid )
{
    const struct group *group;

    LIST_FOR_EACH_ENTRY( group, &token->restricted_sids, const struct group, entry )
        if (equal_sid( &group->sid, sid )) return 1;
    return 0;
}

static int token_copy_restrictions( struct token *token, const struct token *source )
{
    const struct group *group;

    token->write_restricted = source->write_restricted;
    LIST_FOR_EACH_ENTRY( group, &source->restricted_sids, const struct group, entry )
    {
        struct group *copy;
        size_t size = offsetof( struct group, sid.sub_auth[group->sid.sub_count] );

        if (!(copy = mem_alloc( size ))) return 0;
        memcpy( copy, group, size );
        list_add_tail( &token->restricted_sids, &copy->entry );
    }
    return 1;
}

static int token_add_restrictions( struct token *token, const struct token *source,
                                   const struct sid *sids, unsigned int count, unsigned int flags )
{
    unsigned int i;

    /* Filtering an already restricted token takes an intersection, never a union. */
    for (i = 0; i < count; i++)
    {
        struct group *group;
        size_t size = offsetof( struct group, sid.sub_auth[sids->sub_count] );

        if ((source->restricted && !token_restricted_sid_present( source, sids )) ||
            token_restricted_sid_present( token, sids ))
        {
            sids = (const struct sid *)((const char *)sids + sid_len( sids ));
            continue;
        }
        if (!(group = mem_alloc( size ))) return 0;
        group->attrs = SE_GROUP_MANDATORY | SE_GROUP_ENABLED_BY_DEFAULT | SE_GROUP_ENABLED;
        copy_sid( &group->sid, sids );
        list_add_tail( &token->restricted_sids, &group->entry );
        sids = (const struct sid *)((const char *)sids + sid_len( sids ));
    }
    token->restricted = 1;
    /* A second filter must never weaken an existing full restriction. */
    token->write_restricted = !!(flags & 8) && (!source->restricted || source->write_restricted);
    return 1;
}

static unsigned int token_restricted_access( const struct token *token,
                                             const struct security_descriptor *sd,
                                             const struct generic_map *mapping,
                                             unsigned int normal_access )
{
    const struct acl *dacl;
    const struct ace *ace;
    unsigned int i, allowed = 0, denied = 0;
    unsigned int restricted_access = normal_access;
    int present;

    if (!token->restricted) return normal_access;
    if (token->write_restricted)
        restricted_access &= (mapping->write & ~(mapping->read | mapping->exec)) |
                             DELETE | WRITE_DAC | WRITE_OWNER;
    if (!restricted_access) return normal_access;
    dacl = sd_get_dacl( sd, &present );
    if (!present || !dacl) return normal_access;
    for (i = 0, ace = ace_first( dacl ); i < dacl->count; i++, ace = ace_next( ace ))
    {
        const struct sid *sid = (const struct sid *)(ace + 1);
        unsigned int mask;

        if (ace->flags & INHERIT_ONLY_ACE || !token_restricted_sid_present( token, sid )) continue;
        mask = map_access( ace->mask, mapping ) & restricted_access;
        if (ace->type == ACCESS_DENIED_ACE_TYPE) denied |= mask & ~allowed;
        else if (ace->type == ACCESS_ALLOWED_ACE_TYPE) allowed |= mask & ~denied;
    }
    return (normal_access & ~restricted_access) | (allowed & restricted_access);
}
