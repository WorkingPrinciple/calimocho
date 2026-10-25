#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "wine/list.h"
#define SID_REVISION 1
#define SECURITY_MANDATORY_LABEL_AUTHORITY {0,0,0,0,0,16}
#define SECURITY_MANDATORY_MEDIUM_RID 8192
#define SE_GROUP_INTEGRITY 0x20
#define SYSTEM_MANDATORY_LABEL_ACE_TYPE 17
#define TOKEN_QUERY 8
#define TOKEN_ADJUST_DEFAULT 0x80
#define TOKEN_ADJUST_SESSIONID 0x100
#define TokenSessionId 12
#define TokenIntegrityLevel 25
#define STATUS_BUFFER_TOO_SMALL 0xc0000023u
#define STATUS_ACCESS_DENIED 0xc0000022u
#define STATUS_PRIVILEGE_NOT_HELD 0xc0000061u
#define STATUS_INVALID_PARAMETER 0xc000000du
#define STATUS_INVALID_INFO_CLASS 0xc0000003u
#define STATUS_UNSUCCESSFUL 0xc0000001u
typedef unsigned char SID_IDENTIFIER_AUTHORITY[6];
struct sid {unsigned char revision,sub_count;SID_IDENTIFIER_AUTHORITY id_auth;unsigned sub_auth[1];};
struct ace {unsigned type;};
struct entry {struct ace ace;struct sid sid;};
struct acl {unsigned count;struct entry entries[1];};
struct security_descriptor {struct acl sacl;};
struct object {struct security_descriptor *sd;};
struct group {struct list entry;unsigned attrs;struct sid sid;};
struct token {struct object obj;struct list groups;unsigned session_id,modified_id;};
static struct token target;
static struct security_descriptor stored_sd;
static unsigned error,rights,capacity,privileged,fail_label;
static const unsigned SeTcbPrivilege=7;
static struct {void *process;} current_value,*current=&current_value;
static void set_error(unsigned status) {error=status;}
static unsigned get_error(void) {return error;}
static struct token *get_token_obj(void *p,unsigned handle,unsigned access) {
    if(handle!=1||(rights&access)!=access) {set_error(STATUS_ACCESS_DENIED);return NULL;}
    return &target;
}
static const struct acl *sd_get_sacl(const struct security_descriptor *sd,int *present) {*present=1;return &sd->sacl;}
static const struct ace *ace_first(const struct acl *acl) {return &acl->entries[0].ace;}
static const struct ace *ace_next(const struct ace *ace) {return (const struct ace *)((const struct entry *)ace+1);}
static unsigned sid_len(const struct sid *sid) {return offsetof(struct sid,sub_auth[sid->sub_count]);}
static int sid_valid_size(const struct sid *sid,unsigned size) {return size>=8&&size>=sid_len(sid);}
static void copy_sid(struct sid *out,const struct sid *in) {memcpy(out,in,sid_len(in));}
static int thread_single_check_privilege(void *thread,unsigned privilege) {assert(privilege==7);return privileged;}
static int token_assign_label(struct token *token,const struct sid *label) {
    if(fail_label)return 0;
    stored_sd.sacl.count=1;stored_sd.sacl.entries[0].ace.type=SYSTEM_MANDATORY_LABEL_ACE_TYPE;
    stored_sd.sacl.entries[0].sid=*label;token->obj.sd=&stored_sd;return 1;
}
static void allocate_luid(unsigned *id) {++*id;}
static void release_object(struct token *token) {}
static unsigned get_reply_max_size(void) {return capacity;}
static struct sid output,input;
static const void *get_req_data(void) {return &input;}
static unsigned data_size;
static unsigned get_req_data_size(void) {return data_size;}
static void set_reply_data(const void *data,unsigned size) {assert(size==sizeof(output));memcpy(&output,data,size);}
struct request {unsigned handle,which,session_id;};
struct reply {unsigned sid_len;};
#define DECL_HANDLER(name) static void name(const struct request *req,struct reply *reply)
#include "token_security.c"
int main(void) {
    list_init(&target.groups);target.session_id=1;
    struct request req={.handle=1,.which=TokenSessionId,.session_id=0};
    struct reply reply={0};
    set_token_security(&req,&reply);assert(error==STATUS_ACCESS_DENIED&&target.session_id==1);
    rights=TOKEN_ADJUST_SESSIONID;error=0;
    set_token_security(&req,&reply);assert(error==STATUS_PRIVILEGE_NOT_HELD&&target.session_id==1);
    privileged=1;error=0;
    set_token_security(&req,&reply);assert(!error&&!target.session_id&&target.modified_id==1);
    req.which=TokenIntegrityLevel;rights=TOKEN_ADJUST_DEFAULT;error=0;data_size=sizeof(input)-1;
    set_token_security(&req,&reply);assert(error==STATUS_INVALID_PARAMETER&&!target.obj.sd);
    input=(struct sid){1,1,SECURITY_MANDATORY_LABEL_AUTHORITY,{16384}};data_size=sizeof(input);
    struct group group={.attrs=SE_GROUP_INTEGRITY,.sid={1,1,SECURITY_MANDATORY_LABEL_AUTHORITY,{8192}}};
    list_add_tail(&target.groups,&group.entry);
    error=0;privileged=0;
    set_token_security(&req,&reply);assert(error==STATUS_PRIVILEGE_NOT_HELD&&!target.obj.sd);
    privileged=1;error=0;fail_label=1;
    set_token_security(&req,&reply);assert(error==STATUS_UNSUCCESSFUL&&!target.obj.sd);
    fail_label=0;error=0;
    set_token_security(&req,&reply);
    assert(!error&&target.modified_id==2&&group.sid.sub_auth[0]==16384);
    rights=TOKEN_QUERY;capacity=sizeof(output);get_token_integrity(&req,&reply);
    assert(!error&&reply.sid_len==sizeof(output)&&output.sub_auth[0]==16384);
    capacity=0;get_token_integrity(&req,&reply);assert(error==STATUS_BUFFER_TOO_SMALL);
    capacity=sizeof(output);error=0;target.obj.sd=NULL;
    get_token_integrity(&req,&reply);assert(!error&&output.sub_auth[0]==8192);
    rights=0;get_token_integrity(&req,&reply);assert(error==STATUS_ACCESS_DENIED);
    rights=TOKEN_ADJUST_DEFAULT;error=0;input.id_auth[5]=5;
    set_token_security(&req,&reply);assert(error==STATUS_INVALID_PARAMETER);
    error=0;req.which=999;
    set_token_security(&req,&reply);assert(error==STATUS_INVALID_INFO_CLASS);
    return 0;
}
