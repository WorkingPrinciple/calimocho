/* Actual restricting-SID helper and access-check body, with deterministic token/ACL data. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "wine/list.h"
#define TRUE 1
#define FALSE 0
#define GENERIC_READ 0x80000000u
#define GENERIC_WRITE 0x40000000u
#define GENERIC_EXECUTE 0x20000000u
#define GENERIC_ALL 0x10000000u
#define MAXIMUM_ALLOWED 0x02000000u
#define ACCESS_SYSTEM_SECURITY 0x01000000u
#define DELETE 0x10000
#define READ_CONTROL 0x20000
#define WRITE_DAC 0x40000
#define WRITE_OWNER 0x80000
#define SYNCHRONIZE 0x100000
#define STANDARD_RIGHTS_REQUIRED 0xf0000
#define SE_GROUP_MANDATORY 1
#define SE_GROUP_ENABLED_BY_DEFAULT 2
#define SE_GROUP_ENABLED 4
#define SE_GROUP_USE_FOR_DENY_ONLY 16
#define INHERIT_ONLY_ACE 8
#define ACCESS_ALLOWED_ACE_TYPE 0
#define ACCESS_DENIED_ACE_TYPE 1
#define STATUS_SUCCESS 0
#define STATUS_GENERIC_NOT_MAPPED 0xc00000e6u
#define STATUS_INVALID_SECURITY_DESCR 0xc0000079u
#define STATUS_BUFFER_TOO_SMALL 0xc0000023u
#define STATUS_PRIVILEGE_NOT_HELD 0xc0000061u
#define STATUS_ACCESS_DENIED 0xc0000022u
#define STATUS_INVALID_PARAMETER 0xc000000du
#define STATUS_INVALID_SID 0xc0000078u
#define TOKEN_DUPLICATE 2
#define TOKEN_QUERY 8
#define SeSecurityPrivilege 8
typedef unsigned long ULONG;
struct sid { unsigned sub_count,sub_auth[1]; };
struct group { struct list entry;unsigned attrs;struct sid sid; };
struct token {
    struct list groups,restricted_sids;
    unsigned restricted,write_restricted;
    struct sid *user;
    unsigned primary,impersonation_level,modified_id;
};
struct luid_attr {unsigned luid,attrs;};
struct generic_map {unsigned read,write,exec,all;};
struct ace {unsigned type,flags,mask;};
struct entry {struct ace ace;struct sid sid;};
struct acl {unsigned count;struct entry entries[8];};
struct security_descriptor {struct sid *owner,*group;struct acl *dacl;int present;};
static int fail_allocation;
static void *mem_alloc(size_t size) {if(fail_allocation)return NULL;return malloc(size);}
static int equal_sid(const struct sid *a,const struct sid *b) {
    return a->sub_count==b->sub_count&&!memcmp(a->sub_auth,b->sub_auth,a->sub_count*sizeof(unsigned));
}
static unsigned sid_len(const struct sid *sid) {return offsetof(struct sid,sub_auth[sid->sub_count]);}
static void copy_sid(struct sid *out,const struct sid *in) {memcpy(out,in,sid_len(in));}
static const struct acl *sd_get_dacl(const struct security_descriptor *sd,int *present) {
    *present=sd->present;return sd->dacl;
}
static const struct sid *sd_get_owner(const struct security_descriptor *sd) {return sd->owner;}
static const struct sid *sd_get_group(const struct security_descriptor *sd) {return sd->group;}
static const struct ace *ace_first(const struct acl *acl) {return &acl->entries[0].ace;}
static const struct ace *ace_next(const struct ace *ace) {return (const struct ace *)((const struct entry *)ace+1);}
static unsigned map_access(unsigned access,const struct generic_map *map) {
    if(access&GENERIC_READ)access|=map->read;
    if(access&GENERIC_WRITE)access|=map->write;
    if(access&GENERIC_EXECUTE)access|=map->exec;
    if(access&GENERIC_ALL)access|=map->all;
    return access&~(GENERIC_READ|GENERIC_WRITE|GENERIC_EXECUTE|GENERIC_ALL);
}
static int token_check_privileges(struct token *t,int all,const struct luid_attr *p,unsigned n,struct luid_attr *out) {
    return 0;
}
static int token_sid_present(struct token *t,const struct sid *sid,int deny) {
    struct group *g;
    if(equal_sid(t->user,sid))return 1;
    LIST_FOR_EACH_ENTRY(g,&t->groups,struct group,entry)
        if((g->attrs&SE_GROUP_ENABLED)&&(!(!deny&&(g->attrs&SE_GROUP_USE_FOR_DENY_ONLY)))&&equal_sid(&g->sid,sid))return 1;
    return 0;
}
#include "server_restricted_token.c"
#include "token_access_under_test.c"
static void init(struct token *t,struct sid *user) {
    memset(t,0,sizeof(*t));t->user=user;list_init(&t->groups);list_init(&t->restricted_sids);
}
static void cleanup(struct token *t) {
    struct group *g,*next;
    LIST_FOR_EACH_ENTRY_SAFE(g,next,&t->restricted_sids,struct group,entry) {list_remove(&g->entry);free(g);}
}
static struct token *input_token,*output_token;
static const int token_ops=0;
static unsigned handler_error,request_size,reply_capacity;
static const void *request_bytes;
static unsigned char query_buffer[128];
static void set_error(unsigned error) {handler_error=error;}
static const void *get_req_data(void) {return request_bytes;}
static unsigned get_req_data_size(void) {return request_size;}
static unsigned get_reply_max_size(void) {return reply_capacity;}
static void *set_reply_data_size(unsigned size) {assert(size<=sizeof(query_buffer));return query_buffer;}
static struct {void *process;} current_value,*current=&current_value;
static void *get_handle_obj(void *process,unsigned handle,unsigned access,const void *ops) {
    if(handle!=1) {set_error(0xc0000008u);return NULL;}
    return input_token;
}
static unsigned get_handle_access(void *p,unsigned handle) {return 0xffff;}
static void allocate_luid(unsigned *id) {++*id;}
static unsigned alloc_handle_no_access_check(void *p,struct token *t,unsigned access,unsigned attr) {
    output_token=t;return 2;
}
static void release_object(struct token *t) { /* Harness retains output until explicit cleanup. */ }
static int sid_valid_size(const struct sid *sid,unsigned size) {
    return size>=sizeof(unsigned)&&sid->sub_count<=1&&size>=sid_len(sid);
}
static struct sid *copy_sid_result(struct sid *out,const struct sid *in) {
    copy_sid(out,in);return (struct sid *)((char *)out+sid_len(in));
}
static struct token *token_duplicate(struct token *src,unsigned primary,unsigned level,const void *sd,
                                     const struct luid_attr *priv,unsigned count,const struct sid *disabled,unsigned n) {
    struct token *t=malloc(sizeof(*t));assert(t);init(t,src->user);
    t->primary=primary;t->impersonation_level=level;t->restricted=src->restricted;
    assert(token_copy_restrictions(t,src));return t;
}
struct request {unsigned flags,privileges_size,disabled_size,handle,restricted,attr_mask;};
struct reply {unsigned new_handle,attr_len,sid_len;};
#define DECL_HANDLER(name) static void name(const struct request *req,struct reply *reply)
#define copy_sid copy_sid_result
#include "token_handlers_under_test.c"
#undef copy_sid
static void entry(struct acl *acl,unsigned type,struct sid sid,unsigned mask) {
    unsigned i=acl->count++;acl->entries[i]=(struct entry){{type,0,mask},sid};
}
static unsigned check(struct token *t,struct security_descriptor *sd,struct generic_map *map,unsigned desired) {
    unsigned granted=0xdeadbeef,status=0xbeef;
    assert(!token_access_check(t,sd,desired,NULL,NULL,map,&granted,&status));
    assert(status==(granted?STATUS_SUCCESS:STATUS_ACCESS_DENIED));
    return granted;
}
int main(void) {
    struct sid user={1,{1}},restrictor={1,{2}},other={1,{3}},owner={1,{4}};
    struct token source,full,write,copy,intersection;
    struct acl acl={0};
    struct security_descriptor sd={&owner,&owner,&acl,1};
    struct generic_map map={0x120089,0x120116,0x1200a0,0x1f01ff};
    init(&source,&user);init(&full,&user);init(&write,&user);init(&copy,&user);init(&intersection,&user);
    assert(token_add_restrictions(&full,&source,&restrictor,1,0));
    assert(token_add_restrictions(&write,&source,&restrictor,1,8));
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,user,GENERIC_ALL);
    assert(check(&source,&sd,&map,1)==1);
    assert(!check(&full,&sd,&map,1));
    assert(check(&write,&sd,&map,1)==1);
    assert(!check(&write,&sd,&map,2));
    assert(check(&write,&sd,&map,SYNCHRONIZE|READ_CONTROL)==(SYNCHRONIZE|READ_CONTROL));
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,restrictor,2);
    assert(check(&full,&sd,&map,2)==2);
    assert(check(&write,&sd,&map,2)==2);
    assert(!check(&full,&sd,&map,3));
    assert(check(&full,&sd,&map,MAXIMUM_ALLOWED)==2);
    assert(check(&write,&sd,&map,MAXIMUM_ALLOWED)==((map.all&~((map.write&~(map.read|map.exec))|DELETE|WRITE_DAC|WRITE_OWNER))|2));
    /* Owner rights in the first pass cannot bypass restricting SIDs. */
    sd.owner=&user;
    assert(!check(&full,&sd,&map,WRITE_DAC));
    sd.owner=&owner;
    acl.count=0;
    entry(&acl,ACCESS_DENIED_ACE_TYPE,restrictor,2);
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,user,GENERIC_ALL);
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,restrictor,GENERIC_ALL);
    assert(!check(&full,&sd,&map,2));
    assert(check(&full,&sd,&map,1)==1);
    /* An allow before a deny retains its already granted rights, as in the normal pass. */
    acl.count=0;
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,restrictor,2);
    entry(&acl,ACCESS_DENIED_ACE_TYPE,restrictor,2);
    entry(&acl,ACCESS_ALLOWED_ACE_TYPE,user,GENERIC_ALL);
    assert(check(&full,&sd,&map,2)==2);
    sd.dacl=NULL;
    assert(check(&full,&sd,&map,2)==2);
    sd.dacl=&acl;acl.count=0;
    assert(!check(&full,&sd,&map,2));
    assert(token_copy_restrictions(&copy,&full));
    assert(token_restricted_sid_present(&copy,&restrictor));
    assert(token_add_restrictions(&intersection,&full,&other,1,8));
    assert(intersection.restricted&&!intersection.write_restricted&&list_empty(&intersection.restricted_sids));
    cleanup(&full);
    init(&full,&user);
    assert(token_add_restrictions(&full,&intersection,&restrictor,1,0));
    assert(full.restricted&&list_empty(&full.restricted_sids)); /* Empty intersections stay restrictive. */
    fail_allocation=1;
    assert(!token_copy_restrictions(&full,&copy));
    fail_allocation=0;
    input_token=&source;request_bytes=&restrictor;request_size=sizeof(restrictor);
    struct request req={.flags=8,.handle=1};
    struct reply reply={0};
    filter_token(&req,&reply);
    assert(!handler_error&&reply.new_handle==2&&output_token->restricted&&output_token->write_restricted);
    assert(token_restricted_sid_present(output_token,&restrictor));
    input_token=output_token;req.restricted=1;reply_capacity=0;reply=(struct reply){0};
    get_token_groups(&req,&reply);
    assert(handler_error==STATUS_BUFFER_TOO_SMALL&&reply.attr_len==4&&reply.sid_len==sizeof(restrictor));
    handler_error=0;reply_capacity=sizeof(query_buffer);reply=(struct reply){0};
    get_token_groups(&req,&reply);
    assert(!handler_error&&reply.attr_len==4&&reply.sid_len==sizeof(restrictor));
    assert(*(unsigned *)query_buffer==7&&equal_sid((struct sid *)(query_buffer+4),&restrictor));
    cleanup(output_token);free(output_token);output_token=NULL;input_token=&source;
    req.flags=1;handler_error=0;reply=(struct reply){0};filter_token(&req,&reply);
    assert(handler_error==STATUS_INVALID_PARAMETER&&!reply.new_handle);
    req.flags=0;request_size=sizeof(restrictor)-1;handler_error=0;
    filter_token(&req,&reply);assert(handler_error==STATUS_INVALID_SID&&!reply.new_handle);
    request_size=sizeof(restrictor);req.disabled_size=request_size+1;handler_error=0;
    filter_token(&req,&reply);assert(handler_error==STATUS_INVALID_PARAMETER&&!reply.new_handle);
    /* Exact mappings/rights from the retained native 60-row overlap probe. */
    struct { const char *name;struct generic_map map; } cases[]={
        {"FILE",{0x120089,0x120116,0x1200a0,0x1f01ff}},
        {"KEY",{0x020019,0x020006,0x020019,0x0f003f}},
        {"WX_RW",{0x020001,0x120002,0x100004,0x1f0007}},
        {"SPLIT",{0x000005,0x000007,0x000003,0x1f0007}}
    };
    unsigned rights[]={SYNCHRONIZE,READ_CONTROL,READ_CONTROL|SYNCHRONIZE,0x100020,0x120089,
                       0x20019,GENERIC_READ,GENERIC_EXECUTE,1,2,4,0x120116,0x20006,GENERIC_WRITE,MAXIMUM_ALLOWED};
    sd.owner=&owner;sd.dacl=&acl;acl.count=0;
    for(unsigned i=0;i<4;++i) {
        acl.count=0;entry(&acl,ACCESS_ALLOWED_ACE_TYPE,user,cases[i].map.all);
        for(unsigned j=0;j<15;++j) {
            unsigned granted=0,status=0,ret;
            ret=token_access_check(&write,&sd,rights[j],NULL,NULL,&cases[i].map,&granted,&status);
            printf("OVERLAP map=%s desired=%08x api=%u allowed=%u granted=%08x error=%u\n",
                   cases[i].name,rights[j],!ret,!ret&&!status,granted,ret?1360:0);
        }
    }
    cleanup(&full);cleanup(&write);cleanup(&copy);cleanup(&intersection);
    return 0;
}
