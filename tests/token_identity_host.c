#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wine/list.h"
typedef unsigned data_size_t;
#define SE_GROUP_OWNER 8
#define TOKEN_QUERY 8
#define TOKEN_QUERY_SOURCE 16
#define STATUS_INVALID_OWNER 0xc000005au
#define STATUS_INVALID_PRIMARY_GROUP 0xc000005bu
#define STATUS_BUFFER_TOO_SMALL 0xc0000023u
#define STATUS_ACCESS_DENIED 0xc0000022u
#define STATUS_INVALID_PARAMETER 0xc000000du
struct sid { unsigned value; };
struct luid {unsigned low_part;int high_part;};
struct token_identity_data {struct luid source_id;char source_name[8];int owner;unsigned reserved;};
struct group {struct list entry;unsigned attrs;struct sid sid;};
struct token {
    struct list groups;
    struct sid *user,*owner,*primary_group;
    struct luid authentication_id,source_id;
    char source_name[8];
};
static unsigned error;
static void set_error(unsigned status) {error=status;}
#include "token_identity.c"
static struct token *input;
static unsigned rights,query_capacity;
static unsigned char output[8];
struct test_process {unsigned int id;};
static struct test_process test_process={0x20};
static struct {struct test_process *process;} current_value={&test_process},*current=&current_value;
static struct token *get_token_obj(void *process,unsigned handle,unsigned access) {
    if(handle!=1 || (rights&access)!=access) {set_error(STATUS_ACCESS_DENIED);return NULL;}
    return input;
}
static unsigned get_reply_max_size(void) {return query_capacity;}
static void set_reply_data(const void *data,unsigned size) {
    assert(size==sizeof(output));memcpy(output,data,size);
}
static void release_object(struct token *token) {}
struct request {
    unsigned handle,source,access,primary;
    int group_count,priv_count,primary_group,impersonation_level;
    struct luid token_id;
};
struct reply {struct luid authentication_id,source_id;unsigned token;};
#define DECL_HANDLER(name) static void name(const struct request *req,struct reply *reply)
#include "token_identity_query_under_test.c"
static void init(struct token *token,struct sid *user) {
    memset(token,0,sizeof(*token));list_init(&token->groups);token->user=user;
}
struct acl {unsigned size;};
struct luid_attr {struct luid luid;unsigned attrs;};
struct sid_attrs {const struct sid *sid;unsigned attrs;};
struct object_params {void *root;unsigned attr;};
static unsigned request_length;
static void *request_bytes;
static const unsigned default_session_id=1;
static const struct sid domain_users_sid={513};
static unsigned sid_len(const struct sid *sid) {return sizeof(*sid);}
static int sid_valid_size(const struct sid *sid,unsigned size) {return size>=sizeof(*sid);}
static int get_req_object_attributes(struct object_params *p) {memset(p,0,sizeof(*p));return 1;}
static void *get_req_data_after_objattr(struct object_params *p,unsigned *size) {
    *size=request_length;return request_bytes;
}
static void *mem_alloc(size_t size) {return malloc(size);}
static int acl_is_valid(const struct acl *acl,unsigned size) {return size>=sizeof(*acl)&&acl->size==size;}
static struct acl *create_default_dacl(const struct sid *sid) {
    struct acl *acl=malloc(sizeof(*acl));assert(acl);acl->size=sizeof(*acl);return acl;
}
static struct token *construct_token(unsigned primary,unsigned session,const struct sid *user,
                                  const struct sid_attrs *groups,unsigned count,const struct luid_attr *privs,
                                  unsigned priv_count,const struct acl *dacl,const struct luid *modified,
                                  unsigned primary_group,int level,int elevation) {
    static struct token created;
    static struct sid copied_user;
    static struct group copied_groups[2];
    assert(count<=2);copied_user=*user;init(&created,&copied_user);
    for(unsigned i=0;i<count;++i) {
        copied_groups[i].sid=*groups[i].sid;copied_groups[i].attrs=groups[i].attrs;
        list_add_tail(&created.groups,&copied_groups[i].entry);
    }
    input=&created;return &created;
}
static unsigned alloc_handle(void *process,struct token *token,unsigned access,unsigned attr) {return 9;}
#include "token_create_under_test.c"
int main(void) {
    struct sid user={19},copy_user={19};
    struct token source,copy;
    struct group groups[2]={{{0},0,{21}},{{0},8,{80}}},copies[2]={{{0},0,{21}},{{0},8,{80}}};
    struct token_identity_data identity={{0x4242,0},{'A','d','v','a','p','i',' ',' '},-1,0};
    struct luid authentication={0x3e5,0};
    init(&source,&user);init(&copy,&copy_user);
    for(unsigned i=0;i<2;++i) {
        list_add_tail(&source.groups,&groups[i].entry);
        list_add_tail(&copy.groups,&copies[i].entry);
    }
    assert(token_apply_identity(&source,&authentication,&identity,-1));
    assert(source.owner==source.user&&source.primary_group==source.user);
    token_copy_identity(&copy,&source);
    assert(copy.owner==&copy_user&&copy.primary_group==&copy_user);
    assert(copy.authentication_id.low_part==0x3e5&&copy.source_id.low_part==0x4242);
    assert(!memcmp(copy.source_name,"Advapi  ",8));
    identity.owner=1;
    assert(token_apply_identity(&source,&authentication,&identity,0));
    token_copy_identity(&copy,&source);
    assert(copy.owner==&copies[1].sid&&copy.primary_group==&copies[0].sid);
    groups[1].sid.value=999;source.source_name[0]='X';
    assert(copy.owner->value==80&&copy.source_name[0]=='A');
    identity.owner=0;error=0;
    assert(!token_apply_identity(&source,&authentication,&identity,-1)&&error==STATUS_INVALID_OWNER);
    identity.owner=-1;error=0;
    assert(!token_apply_identity(&source,&authentication,&identity,-2)&&error==STATUS_INVALID_PRIMARY_GROUP);
    identity.owner=2;error=0;
    assert(!token_apply_identity(&source,&authentication,&identity,0)&&error==STATUS_INVALID_OWNER);
    input=&copy;rights=TOKEN_QUERY;struct request req={.handle=1};struct reply reply={0};
    error=0;get_token_identity(&req,&reply);
    assert(!error&&reply.authentication_id.low_part==0x3e5);
    req.source=1;get_token_identity(&req,&reply);assert(error==STATUS_ACCESS_DENIED);
    error=0;rights=TOKEN_QUERY_SOURCE;query_capacity=7;
    get_token_identity(&req,&reply);assert(error==STATUS_BUFFER_TOO_SMALL);
    error=0;query_capacity=8;
    get_token_identity(&req,&reply);
    assert(!error&&!memcmp(output,"Advapi  ",8)&&reply.source_id.low_part==0x4242);
    req.source=0;get_token_identity(&req,&reply);assert(error==STATUS_ACCESS_DENIED);
    init(&source,&user);init(&copy,&copy_user);
    identity.owner=-1;
    assert(token_apply_identity(&source,&authentication,&identity,-1));
    token_copy_identity(&copy,&source);
    assert(copy.owner==copy.user&&copy.primary_group==copy.user);
    struct {
        struct token_identity_data identity;
        struct sid user;
        unsigned attrs[2];
        struct sid groups[2];
    } packed={{{0x5566,0},{'A','d','v','a','p','i',' ',' '},-1,0},{19},{0,8},{{21},{80}}};
    request_bytes=&packed;request_length=sizeof(packed);
    req=(struct request){.group_count=2,.primary_group=-1,.token_id={0x3e5,0}};
    reply=(struct reply){0};error=0;
    create_token(&req,&reply);
    assert(!error&&reply.token==9&&input->owner==input->user&&input->primary_group==input->user);
    assert(input->source_id.low_part==0x5566&&input->authentication_id.low_part==0x3e5);
    packed.identity.owner=1;req.primary_group=0;reply=(struct reply){0};
    create_token(&req,&reply);
    assert(!error&&reply.token==9&&input->owner->value==80&&input->primary_group->value==21);
    packed.identity.owner=0;reply=(struct reply){0};
    create_token(&req,&reply);assert(error==STATUS_INVALID_OWNER&&!reply.token);
    packed.identity.owner=-1;error=0;req.group_count=-1;
    create_token(&req,&reply);assert(error==STATUS_INVALID_PARAMETER&&!reply.token);
    error=0;req.group_count=0x7fffffff;
    create_token(&req,&reply);assert(error==STATUS_INVALID_PARAMETER&&!reply.token);
    error=0;req.group_count=2;request_length=sizeof(packed.identity)-1;
    create_token(&req,&reply);assert(error==STATUS_INVALID_PARAMETER&&!reply.token);
    return 0;
}
