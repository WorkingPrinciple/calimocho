/* Compile the actual server packet handlers with a deterministic host object adapter. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wine/list.h"

#define CONTAINING_RECORD(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define STATUS_SUCCESS 0u
#define STATUS_PENDING 0x103u
#define STATUS_CANCELLED 0xc0000120u
#define STATUS_INVALID_PARAMETER 0xc000000du
#define STATUS_OBJECT_TYPE_MISMATCH 0xc0000024u
#define STATUS_NOT_SUPPORTED 0xc00000bbu
#define STATUS_INVALID_HANDLE 0xc0000008u
#define STATUS_ACCESS_DENIED 0xc0000022u
#define STATUS_NO_MEMORY 0xc0000017u
#define STANDARD_RIGHTS_REQUIRED 0xf0000
#define STANDARD_RIGHTS_READ 0x20000
#define STANDARD_RIGHTS_WRITE 0x20000
#define STANDARD_RIGHTS_EXECUTE 0x20000
#define SYNCHRONIZE 0x100000
#define IO_COMPLETION_MODIFY_STATE 2
typedef uint16_t WCHAR;
typedef unsigned obj_handle_t;
typedef uint64_t apc_param_t;
struct object;
struct wait_queue_entry;
struct process { int unused; };
struct type_descr {
    struct { const WCHAR *str; unsigned size; } name;
    unsigned access;
    struct { unsigned read, write, execute, all; } mapping;
};
struct object_ops {
    size_t size;
    struct type_descr *type;
    void (*dump)(struct object *,int);
    bool (*init)(struct object *,const void *);
    int (*close_handle)(struct object *,struct process *,obj_handle_t);
    void (*destroy)(struct object *);
    int (*add_queue)(struct object *,struct wait_queue_entry *);
    void (*remove_queue)(struct object *,struct wait_queue_entry *);
    int (*signaled)(struct object *,struct wait_queue_entry *);
    void (*satisfied)(struct object *,struct wait_queue_entry *);
};
struct object {
    const struct object_ops *ops;
    unsigned refcount, handle_count;
    struct list wait_queue;
    struct object *sync;
    int signals;
    bool manual;
};
struct wait_queue_entry {
    struct list entry;
    struct object *obj;
    void *wait;
    int (*wake_callback)(struct wait_queue_entry *);
};
struct wait_packet;
struct comp_msg {
    struct list queue_entry;
    struct wait_packet *packet;
    apc_param_t ckey,cvalue,information;
    unsigned status;
};
struct completion {
    struct object obj;
    struct object *sync;
    struct list queue,wait_queue,packets;
    unsigned depth;
};
struct completion_wait { struct object obj; struct list wait_queue_entry; };
static struct { struct process *process; } current_value, *current = &current_value;
static struct type_descr event_type,timer_type,semaphore_type,thread_type,process_type;
static struct object *handles[32];
static unsigned access_masks[32], error, objects;
static bool fail_alloc;
static void set_error(unsigned value) { error = value; }
static void *mem_alloc(size_t size) {
    if (fail_alloc) { fail_alloc=false; set_error(STATUS_NO_MEMORY); return NULL; }
    return malloc(size);
}
static void *grab_object(void *pointer) {
    struct object *obj=pointer; assert(obj && obj->refcount); ++obj->refcount; return obj;
}
static void release_object(void *pointer) {
    struct object *obj=pointer; assert(obj && obj->refcount);
    if (!--obj->refcount) {
        if(obj->ops->destroy) obj->ops->destroy(obj);
        assert(list_empty(&obj->wait_queue)); --objects; free(obj);
    }
}
static void *allocate(const struct object_ops *ops) {
    struct object *obj=calloc(1,ops->size); assert(obj);
    obj->ops=ops;obj->refcount=1;list_init(&obj->wait_queue);++objects;
    if(ops->init) assert(ops->init(obj,NULL));
    return obj;
}
static unsigned add_handle(void *pointer,unsigned access) {
    struct object *obj=pointer;
    for(unsigned i=1;i<32;++i) if(!handles[i]) {
        handles[i]=obj;access_masks[i]=access;++obj->handle_count;return i;
    }
    abort();
}
static void close_handle(unsigned handle) {
    struct object *obj=handles[handle]; assert(obj);
    if(obj->ops->close_handle) obj->ops->close_handle(obj,NULL,handle);
    --obj->handle_count;handles[handle]=NULL;release_object(obj);
}
static void *get_handle_obj(struct process *p,unsigned handle,unsigned access,const struct object_ops *ops) {
    struct object *obj = handle<32?handles[handle]:NULL;
    if(!obj) {set_error(STATUS_INVALID_HANDLE);return NULL;}
    if(ops && obj->ops!=ops) {set_error(STATUS_OBJECT_TYPE_MISMATCH);return NULL;}
    if((access_masks[handle]&access)!=access) {set_error(STATUS_ACCESS_DENIED);return NULL;}
    return grab_object(obj);
}
static const struct object_ops port_ops;
static struct completion *get_completion_obj(struct process *p,unsigned h,unsigned a) {
    return get_handle_obj(p,h,a,&port_ops);
}
static struct object *get_obj_sync(struct object *obj) { return grab_object(obj->sync); }
static int add_queue(struct object *obj,struct wait_queue_entry *entry) {
    list_add_tail(&obj->wait_queue,&entry->entry);return 1;
}
static void remove_queue(struct object *obj,struct wait_queue_entry *entry) {list_remove(&entry->entry);}
static int signaled(struct object *obj,struct wait_queue_entry *entry) {return obj->signals!=0;}
static void satisfied(struct object *obj,struct wait_queue_entry *entry) {
    assert(obj->signals); if(!obj->manual)--obj->signals;
}
static void signal_sync(struct object *obj) {obj->signals=1;}
static void reset_sync(struct object *obj) {obj->signals=0;}
static void wake_up(struct object *obj,int max) {abort();} /* No mocked receiver is installed. */
struct request {unsigned access,packet,completion,target,remove_signaled,status;apc_param_t ckey,cvalue,information;};
struct reply {unsigned handle;int already_signaled;};
#define DECL_HANDLER(name) static void name(const struct request *req,struct reply *reply)
struct object_params {const struct object_ops *ops;unsigned access;struct object *root;};
static bool get_req_object_attributes(struct object_params *params) {return true;}
static unsigned create_named_obj_handle(struct process *p,struct object_params *params) {
    return add_handle(allocate(params->ops),params->access);
}

#include "server_wait_completion_packet.c"

static const struct object_ops sync_ops = {
    .size=sizeof(struct object),.type=&event_type,.add_queue=add_queue,.remove_queue=remove_queue,
    .signaled=signaled,.satisfied=satisfied
};
static const struct object_ops target_ops = {.size=sizeof(struct object),.type=&event_type};
static const struct object_ops port_ops = {.size=sizeof(struct completion)};
static void signal_target(struct object *sync) {
    sync->signals=1;
    while(!list_empty(&sync->wait_queue)) {
        struct wait_queue_entry *e=LIST_ENTRY(list_head(&sync->wait_queue),struct wait_queue_entry,entry);
        if(!e->wake_callback(e))break;
    }
}
static void associate(struct request *req,struct reply *reply) {
    error=0;reply->already_signaled=0x55;associate_wait_completion_packet(req,reply);
}
static void cancel(struct request *req) {struct reply reply;error=0;cancel_wait_completion_packet(req,&reply);}
int main(void) {
    struct completion *port=allocate(&port_ops);
    struct object *sync=allocate(&sync_ops),*target=allocate(&target_ops);
    struct reply reply={0};
    struct request req={.access=1};
    struct comp_msg *msg;
    unsigned packet;
    port->sync=allocate(&sync_ops);list_init(&port->queue);list_init(&port->wait_queue);list_init(&port->packets);
    target->sync=sync;
    create_wait_completion_packet(&req,&reply);packet=reply.handle;assert(packet&&objects==5);
    req.packet=packet;req.completion=add_handle(port,IO_COMPLETION_MODIFY_STATE);
    req.target=add_handle(target,SYNCHRONIZE);
    req.ckey=0x1122334455667788ULL;req.cvalue=0xaabbccddeeff0011ULL;
    req.status=0xc0001234;req.information=0x8877665544332211ULL;
    cancel(&req);assert(error==STATUS_CANCELLED);
    fail_alloc=true;associate(&req,&reply);assert(error==STATUS_NO_MEMORY&&reply.already_signaled==0x55);
    associate(&req,&reply);assert(!error&&!reply.already_signaled&&!port->depth);
    associate(&req,&reply);assert(error==STATUS_INVALID_PARAMETER);
    signal_target(sync);assert(port->depth==1&&list_empty(&sync->wait_queue)&&!sync->signals);
    msg=LIST_ENTRY(list_head(&port->queue),struct comp_msg,queue_entry);
    assert(msg->ckey==req.ckey&&msg->cvalue==req.cvalue&&msg->status==req.status&&msg->information==req.information);
    signal_target(sync);assert(port->depth==1);
    req.remove_signaled=0;cancel(&req);assert(error==STATUS_PENDING&&port->depth==1);
    associate(&req,&reply);assert(error==STATUS_INVALID_PARAMETER);
    req.remove_signaled=1;cancel(&req);assert(!error&&!port->depth&&!port->sync->signals);
    cancel(&req);assert(error==STATUS_CANCELLED);
    associate(&req,&reply);assert(!error&&reply.already_signaled&&port->depth==1&&!sync->signals);
    msg=LIST_ENTRY(list_head(&port->queue),struct comp_msg,queue_entry);
    list_remove(&msg->queue_entry);--port->depth;wait_packet_dequeued(msg);free(msg);
    cancel(&req);assert(error==STATUS_CANCELLED);
    associate(&req,&reply);assert(!error&&!reply.already_signaled);
    req.remove_signaled=0;cancel(&req);assert(!error&&list_empty(&sync->wait_queue));
    sync->manual=true;signal_target(sync);
    associate(&req,&reply);assert(!error&&reply.already_signaled&&sync->signals);
    cancel_completion_packets(port);assert(!port->depth&&list_empty(&port->packets));
    sync->signals=0;associate(&req,&reply);assert(!error&&!reply.already_signaled);
    close_handle(packet);assert(list_empty(&sync->wait_queue)&&list_empty(&port->packets));
    close_handle(req.target);release_object(sync);
    release_object(port->sync);close_handle(req.completion);
    assert(!objects);
    return 0;
}
