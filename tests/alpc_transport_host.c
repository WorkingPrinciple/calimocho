/* Exercise the generated server handlers, without starting Wine or a prefix. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wine/list.h"

#define STATUS_NO_MEMORY 0xc0000017u
#define STATUS_OBJECT_NAME_EXISTS 0x40000000u
#define STATUS_OBJECT_NAME_COLLISION 0xc0000035u
#define STATUS_OBJECT_TYPE_MISMATCH 0xc0000024u
#define STATUS_INVALID_HANDLE 0xc0000008u
#define STATUS_INVALID_PORT_HANDLE 0xc0000042u
#define STATUS_PENDING 0x103u
#define STATUS_INVALID_CID 0xc000000bu
#define STATUS_REPLY_MESSAGE_MISMATCH 0xc000021fu
#define STATUS_PORT_DISCONNECTED 0xc0000037u
#define STATUS_PORT_CONNECTION_REFUSED 0xc0000041u
#define STATUS_UNSUCCESSFUL 0xc0000001u
#define STATUS_BUFFER_TOO_SMALL 0xc0000023u
#define STATUS_BUFFER_OVERFLOW 0x80000005u
#define STATUS_PORT_MESSAGE_TOO_LONG 0xc000002fu
#define STATUS_ACCESS_DENIED 0xc0000022u
#define STATUS_INVALID_PARAMETER 0xc000000du
#define STATUS_INVALID_SID 0xc0000078u
#define STATUS_INVALID_SECURITY_DESCR 0xc0000079u
#define STATUS_SERVER_SID_MISMATCH 0xc00002a0u
#define STATUS_BAD_IMPERSONATION_LEVEL 0xc00000a5u
#define STATUS_PRIVILEGE_NOT_HELD 0xc0000061u
#define STANDARD_RIGHTS_READ 0x20000
#define STANDARD_RIGHTS_WRITE 0x20000
#define STANDARD_RIGHTS_EXECUTE 0x20000
#define SYNCHRONIZE 0x100000
#define ALPC_SYNC_CONNECTION 0x20000
#define ALPC_MSGFLG_REPLY_MESSAGE 0x10000
#define ALPC_PORTFLG_NON_BLOCKING_RECEIVE 0x40000
typedef uint16_t WCHAR;
typedef unsigned obj_handle_t, process_id_t, thread_id_t, data_size_t;
typedef uint64_t client_ptr_t;
typedef struct { unsigned char data[40]; } ALPC_PORT_MESSAGE;
struct object;
struct wait_queue_entry { int unused; };
struct process { unsigned id; };
struct security_descriptor { unsigned unused; };
struct unicode_str { const WCHAR *str; unsigned len; };
struct type_descr {
    struct unicode_str name;
    unsigned access;
    struct { unsigned read, write, execute, all; } mapping;
};
struct object_ops {
    size_t size;
    struct type_descr *type;
    void (*dump)(struct object *,int);
    int (*add_queue)(struct object *,struct wait_queue_entry *);
    void (*remove_queue)(struct object *,struct wait_queue_entry *);
    int (*signaled)(struct object *,struct wait_queue_entry *);
    struct object *(*get_sync)(struct object *);
    unsigned (*map_access)(struct object *,unsigned);
    int (*set_sd)(struct object *,const struct security_descriptor *,unsigned);
    WCHAR *(*get_full_name)(struct object *,unsigned,unsigned *);
    int (*close_handle)(struct object *,struct process *,unsigned);
    void (*destroy)(struct object *);
};
struct object { const struct object_ops *ops; unsigned refcount,handle_count,signals,wakes; };
struct object_attributes { unsigned attributes; };
struct object_params {
    const struct object_ops *ops;
    struct object *root;
    struct unicode_str name;
    unsigned attr,access;
    const struct security_descriptor *sd;
    const struct object_attributes *objattr;
};
static struct process process={0x123};
static struct { struct process *process; unsigned id; struct token *token; } thread={&process,0x456,NULL}, *current=&thread;
static struct object *handles[64],*named;
static unsigned access_masks[64];
static unsigned error,objects,request_size,reply_capacity,reply_size;
static const void *request_data;
static char reply_data[256];
static bool fail_handle;
static const struct object_attributes attributes={0};
static const WCHAR name[]={'t','e','s','t'};
static void set_error(unsigned status) { error=status; }
static unsigned get_error(void) { return error; }
static void *grab_object(void *pointer) {
    struct object *obj=pointer;assert(obj&&obj->refcount);++obj->refcount;return obj;
}
static void release_object(void *pointer) {
    struct object *obj=pointer;assert(obj&&obj->refcount);
    if(!--obj->refcount) {
        assert(!obj->handle_count);
        if(obj==named)named=NULL;
        if(obj->ops&&obj->ops->destroy)obj->ops->destroy(obj);
        --objects;free(obj);
    }
}
static void *create_named_object(struct object_params *params) {
    struct object *obj=calloc(1,params->ops->size);assert(obj);
    obj->ops=params->ops;obj->refcount=1;++objects;
    if(params->name.len) { assert(!named);named=obj; }
    return obj;
}
static void *open_named_object(struct object_params *params) {
    assert(params->access==1);assert(named);return grab_object(named);
}
static unsigned alloc_handle(struct process *process,void *pointer,unsigned access,unsigned attrs) {
    struct object *obj=pointer;
    if(fail_handle) { fail_handle=false;set_error(STATUS_NO_MEMORY);return 0; }
    for(unsigned i=1;i<64;++i)if(!handles[i]) {
        handles[i]=grab_object(obj);access_masks[i]=access;++obj->handle_count;return i;
    }
    abort();
}
static unsigned alloc_handle_no_access_check(struct process *p,void *obj,unsigned access,unsigned attr) {
    return alloc_handle(p,obj,access,attr);
}
static void close_handle(unsigned handle) {
    struct object *obj=handles[handle];assert(obj);
    if(obj->ops&&obj->ops->close_handle)obj->ops->close_handle(obj,&process,handle);
    handles[handle]=NULL;--obj->handle_count;release_object(obj);
}
static void *get_handle_obj(struct process *p,unsigned h,unsigned a,const struct object_ops *ops) {
    struct object *obj=h<64?handles[h]:NULL;
    if(!obj) {set_error(STATUS_INVALID_HANDLE);return NULL;}
    if((access_masks[h]&a)!=a) {set_error(STATUS_ACCESS_DENIED);return NULL;}
    assert(obj->ops==ops);return grab_object(obj);
}
static struct object *create_internal_sync(int manual,int initial) {
    struct object *obj=calloc(1,sizeof(*obj));assert(obj);
    obj->refcount=1;obj->signals=initial;++objects;return obj;
}
static void signal_sync(struct object *obj) {obj->signals=1;}
static void reset_sync(struct object *obj) {obj->signals=0;}
static void wake_up(struct object *obj,int maximum) {++obj->wakes;}
static int add_queue(struct object *obj,struct wait_queue_entry *e) {return 1;}
static void remove_queue(struct object *obj,struct wait_queue_entry *e) {}
static unsigned default_map_access(struct object *obj,unsigned a) {return a;}
static int default_set_sd(struct object *obj,const struct security_descriptor *sd,unsigned flags) {return 1;}
static WCHAR *default_get_full_name(struct object *obj,unsigned max,unsigned *len) {return NULL;}
static unsigned get_process_id(struct process *p) {return p->id;}
static unsigned get_thread_id(void *t) {return current->id;}
static bool get_req_object_attributes(struct object_params *params) {
    params->objattr=&attributes;params->name=(struct unicode_str){name,sizeof(name)};return true;
}
static const void *get_req_data_after_objattr(struct object_params *params,unsigned *len) {
    *len=request_size;return request_data;
}
static unsigned get_reply_max_size(void) {return reply_capacity;}
static const void *get_req_data(void) {return request_data;}
static unsigned get_req_data_size(void) {return request_size;}
static void set_reply_data(const void *data,unsigned len) {
    assert(len<=reply_capacity&&len<=sizeof(reply_data));reply_size=len;memcpy(reply_data,data,len);
}
#ifdef ALPC_IDENTITY_TEST
#define SecurityImpersonation 2
#define SecurityAnonymous 0
struct sid {unsigned value;};
struct token {struct object obj;unsigned identity;};
static unsigned current_identity=0x1234;
static struct token *thread_get_impersonation_token(void *thread) {return NULL;}
static struct token *token_duplicate(struct token *src,unsigned primary,unsigned level,const void *sd,
                                    const void *priv,unsigned count,const void *sids,unsigned n) {
    struct token *token=calloc(1,sizeof(*token));assert(token);
    token->obj.refcount=1;token->identity=src?src->identity:current_identity;++objects;return token;
}
static int sid_valid_size(const struct sid *sid,unsigned size) {return size==sizeof(*sid);}
static unsigned sid_len(const struct sid *sid) {return sizeof(*sid);}
static int sd_is_valid(const struct security_descriptor *sd,unsigned size) {return size==sizeof(*sd);}
static int token_alpc_identity(struct token *t,const struct sid *sid,const struct security_descriptor *sd,const void *map) {
    return t->identity==(sid?sid->value:sd->unused);
}
#ifdef ALPC_IMPERSONATION_TEST
static unsigned impersonate_privilege=1;
static const unsigned SeImpersonatePrivilege=29;
static int thread_single_check_privilege(void *t,unsigned p) {assert(p==29);return impersonate_privilege;}
#include "token_impersonation_under_test.c"
#endif
#endif
struct request {
    unsigned handle,flags,max_msg_len,connect_flags,msg_id,accept,callback_id,request,match_id;
    unsigned identity_kind,identity_size;
    unsigned impersonation_level,pid,tid;
    uint64_t context,msg_context;
};
struct reply {
    unsigned handle,state,pid,tid,msg_id,size,type,callback_id,sequence,kind,flags,max_msg_len,owner_pid;
    uint64_t msg_context,port_context,context;
};
#define DECL_HANDLER(name) static void name(const struct request *req,struct reply *reply)
#include "alpc_server_under_test.c"

static struct reply call(void (*handler)(const struct request *,struct reply *),struct request req) {
    struct reply reply={0};error=0;reply_size=0;handler(&req,&reply);return reply;
}
static unsigned connect_client(unsigned connection_flags) {
    struct request req={.connect_flags=connection_flags};
#ifdef ALPC_IMPERSONATION_TEST
    req.impersonation_level=SecurityImpersonation;
#endif
    struct reply reply=call(alpc_connect_port,req);
    assert(!error&&reply.handle);return reply.handle;
}
static unsigned receive_id(unsigned port) {
    struct reply reply=call(alpc_receive_message,(struct request){.handle=port});
    assert(!error&&reply.pid==process.id&&reply.tid==current->id);return reply.msg_id;
}
int main(void) {
    struct reply reply;
    unsigned conn,client,server,id;
    reply_capacity=sizeof(reply_data);
    reply=call(alpc_create_port,(struct request){0});conn=reply.handle;assert(!error&&conn);
#ifdef ALPC_IDENTITY_TEST
    current_identity=0x5678; /* A later caller's identity must not replace the creator snapshot. */
    struct sid expected={0x1234};
    request_data=&expected;request_size=sizeof(expected);
    reply=call(alpc_connect_port,(struct request){.identity_kind=1,.identity_size=sizeof(expected)});
    assert(!error&&reply.handle);close_handle(reply.handle);
    expected.value=0x5678;
    reply=call(alpc_connect_port,(struct request){.identity_kind=1,.identity_size=sizeof(expected)});
    assert(error==STATUS_SERVER_SID_MISMATCH&&!reply.handle);
    expected.value=0x1234;
    reply=call(alpc_connect_port,(struct request){.identity_kind=2,.identity_size=sizeof(expected)});
    assert(!error&&reply.handle);close_handle(reply.handle);
    expected.value=0;
    reply=call(alpc_connect_port,(struct request){.identity_kind=2,.identity_size=sizeof(expected)});
    assert(error==STATUS_SERVER_SID_MISMATCH&&!reply.handle);
    reply=call(alpc_connect_port,(struct request){.identity_kind=1,.identity_size=1});
    assert(error==STATUS_INVALID_SID&&!reply.handle);
    reply=call(alpc_connect_port,(struct request){.identity_kind=2,.identity_size=1});
    assert(error==STATUS_INVALID_SECURITY_DESCR&&!reply.handle);
    request_size=0;
#endif
    client=connect_client(0);
    assert(!alpc_port_signaled(handles[client],NULL));
#ifdef ALPC_IMPERSONATION_TEST
    call(alpc_impersonate_connection,(struct request){.handle=conn});
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH&&!current->token);
#endif
    id=receive_id(conn);
    assert(!list_empty(&((struct alpc_port *)handles[conn])->pending));
#ifdef ALPC_IMPERSONATION_TEST
    struct request identity_req={.handle=conn,.msg_id=id,.pid=process.id,.tid=current->id};
    current_identity=0x9876;
    call(alpc_impersonate_connection,(struct request){.handle=client,.msg_id=id,.pid=process.id,.tid=current->id});
    assert(error==STATUS_INVALID_PORT_HANDLE&&!current->token);
    identity_req.pid++;
    call(alpc_impersonate_connection,identity_req);
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH&&!current->token);
    identity_req.pid--;identity_req.tid++;
    call(alpc_impersonate_connection,identity_req);
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH&&!current->token);
    identity_req.tid--;impersonate_privilege=0;
    call(alpc_impersonate_connection,identity_req);
    assert(error==STATUS_PRIVILEGE_NOT_HELD&&!current->token);
    impersonate_privilege=1;
    ((struct alpc_port *)handles[client])->impersonation_level=1;
    call(alpc_impersonate_connection,identity_req);
    assert(error==STATUS_BAD_IMPERSONATION_LEVEL&&!current->token);
    ((struct alpc_port *)handles[client])->impersonation_level=2;
    call(alpc_impersonate_connection,identity_req);
    assert(!error&&current->token&&current->token->identity==0x5678);
#endif
    reply=call(alpc_accept_connect_port,(struct request){.handle=conn,.msg_id=id,.accept=1,.context=0x7788});
    server=reply.handle;assert(!error&&server);
#ifdef ALPC_IMPERSONATION_TEST
    call(alpc_impersonate_connection,identity_req);
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH&&current->token->identity==0x5678);
    release_object(current->token);current->token=NULL;
#endif
    assert(alpc_port_signaled(handles[client],NULL));
    reply=call(alpc_receive_message,(struct request){.handle=client});
    assert(!error&&reply.type==LPC_CONNECTION_REPLY&&reply.msg_id==id);
    assert(!alpc_port_signaled(handles[client],NULL));
    request_data="payload";request_size=7;
    reply=call(alpc_send_message,(struct request){.handle=client,.request=1});
    id=reply.msg_id;assert(!error);
    reply_capacity=2;
    call(alpc_receive_message,(struct request){.handle=conn});
    assert(error==STATUS_BUFFER_TOO_SMALL);
    assert(alpc_port_signaled(handles[conn],NULL));
    reply_capacity=sizeof(reply_data);
    reply=call(alpc_receive_message,(struct request){.handle=conn});
    assert(!error&&reply.msg_id==id&&reply.port_context==0x7788);
    assert(reply_size==7&&!memcmp(reply_data,"payload",7));
    call(alpc_send_message,(struct request){.handle=conn,.flags=ALPC_MSGFLG_REPLY_MESSAGE,.msg_id=id+100});
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH);
    call(alpc_send_message,(struct request){.handle=conn,.flags=ALPC_MSGFLG_REPLY_MESSAGE,.msg_id=id});
    assert(!error);
    call(alpc_send_message,(struct request){.handle=conn,.flags=ALPC_MSGFLG_REPLY_MESSAGE,.msg_id=id});
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH);
    close_handle(server); /* A queued reply must not retain a weak sender pointer. */
    reply=call(alpc_receive_message,(struct request){.handle=client});
    assert(!error&&reply.msg_id==id);
    close_handle(client);
    request_size=0;
    client=connect_client(ALPC_SYNC_CONNECTION);
    id=receive_id(conn);
    reply=call(alpc_accept_connect_port,(struct request){.handle=conn,.msg_id=id,.accept=1});
    server=reply.handle;assert(!error);
    assert(alpc_port_signaled(handles[client],NULL));
    reply=call(alpc_connect_result,(struct request){.handle=client});
    assert(!error&&reply.state==ALPC_CONNECTED);
    assert(!alpc_port_signaled(handles[client],NULL));
    call(alpc_send_message,(struct request){.handle=server,.flags=ALPC_MSGFLG_REPLY_MESSAGE,.msg_id=id+99});
    assert(error==STATUS_REPLY_MESSAGE_MISMATCH);
    close_handle(client);close_handle(server);
    client=connect_client(0);
    close_handle(client); /* Cancel a queued connect without an ownership cycle. */
    assert(list_empty(&((struct alpc_port *)handles[conn])->queue));
    assert(!alpc_port_signaled(handles[conn],NULL));
    client=connect_client(0);
    id=receive_id(conn);close_handle(client);
    call(alpc_accept_connect_port,(struct request){.handle=conn,.msg_id=id,.accept=1});
    assert(error==STATUS_INVALID_CID);
    request_data="wake";request_size=4;
    call(alpc_send_message,(struct request){.handle=conn});
    assert(!error);reply=call(alpc_receive_message,(struct request){.handle=conn});
    assert(!error&&reply.type==LPC_DATAGRAM&&reply_size==4);
    ((struct alpc_port *)handles[conn])->max_msg_len=2;
    call(alpc_send_message,(struct request){.handle=conn});
    assert(error==STATUS_PORT_MESSAGE_TOO_LONG);
    ((struct alpc_port *)handles[conn])->max_msg_len=0x8000;
    request_size=0;
    fail_handle=true;call(alpc_connect_port,(struct request){0});assert(error==STATUS_NO_MEMORY);
    assert(list_empty(&((struct alpc_port *)handles[conn])->queue));
    client=connect_client(0);
    id=receive_id(conn);fail_handle=true;
    call(alpc_accept_connect_port,(struct request){.handle=conn,.msg_id=id,.accept=1});
    assert(error==STATUS_NO_MEMORY&&((struct alpc_port *)handles[client])->state==ALPC_REFUSED);
    close_handle(client);
    client=connect_client(0);
    id=receive_id(conn);
    reply=call(alpc_accept_connect_port,(struct request){.handle=conn,.msg_id=id,.accept=1});
    server=reply.handle;assert(!error&&server);
    unsigned duplicate=alloc_handle(&process,handles[server],0,0);
    call(alpc_send_message,(struct request){.handle=duplicate});
    assert(error==STATUS_ACCESS_DENIED);
    call(alpc_disconnect_port,(struct request){.handle=server});
    assert(!error&&((struct alpc_port *)handles[client])->state==ALPC_CLOSED);
    close_handle(server);close_handle(duplicate);close_handle(client);
    client=connect_client(0);
    close_handle(conn);close_handle(client);
    {
        /* Registrar shape: waitable connection port (0x70000), a wait packet on its
           sync object, and a synchronous 0x18-byte connect from the client. */
        reply=call(alpc_create_port,(struct request){.flags=0x70000});
        unsigned waitable=reply.handle;assert(!error&&waitable);
        struct alpc_port *port=(struct alpc_port *)handles[waitable];
        struct object *sync=port->obj.ops->get_sync(&port->obj);
        assert(sync==port->sync);release_object(sync);
        call(alpc_receive_message,(struct request){.handle=waitable});
        assert(error==STATUS_UNSUCCESSFUL&&!port->sync->signals);
        unsigned char connect_msg[0x18];
        for(unsigned i=0;i<sizeof(connect_msg);++i)connect_msg[i]=(unsigned char)(0xa0+i);
        unsigned wakes=port->obj.wakes;
        request_data=connect_msg;request_size=sizeof(connect_msg);
        client=connect_client(ALPC_SYNC_CONNECTION);
        request_size=0;
        assert(port->sync->signals&&port->obj.wakes>wakes);
        assert(port->obj.ops->signaled(&port->obj,NULL));
        reply=call(alpc_receive_message,(struct request){.handle=waitable});
        assert(!error&&reply.type==LPC_CONNECTION_REQUEST);
        assert(reply_size==sizeof(connect_msg)&&!memcmp(reply_data,connect_msg,sizeof(connect_msg)));
        id=reply.msg_id;
        assert(!port->sync->signals);
        reply=call(alpc_accept_connect_port,(struct request){.handle=waitable,.msg_id=id,.accept=1});
        server=reply.handle;assert(!error&&server);
        reply=call(alpc_connect_result,(struct request){.handle=client});
        assert(!error&&reply.state==ALPC_CONNECTED);
        close_handle(server);close_handle(client);close_handle(waitable);
    }
    assert(!objects&&!named);
    return 0;
}
