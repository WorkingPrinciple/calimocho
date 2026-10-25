/* Included by completion.c. Server-owned, one-shot wait/IOCP associations.
 * LGPL-2.1-or-later
 */
static const WCHAR wait_packet_name[] = {'W','a','i','t','C','o','m','p','l','e','t','i','o','n','P','a','c','k','e','t'};

static struct type_descr wait_packet_type =
{
    { wait_packet_name, sizeof(wait_packet_name) },
    STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 1,
    { STANDARD_RIGHTS_READ | 1, STANDARD_RIGHTS_WRITE | 1,
      STANDARD_RIGHTS_EXECUTE | SYNCHRONIZE, STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 1 },
};

struct wait_packet
{
    struct object obj;
    struct wait_queue_entry wait;
    struct object *target;
    struct object *sync;
    struct completion *completion;
    struct comp_msg *msg;
    struct list port_entry;
    int queued;
};

static void wait_packet_dequeued(struct comp_msg *msg)
{
    struct wait_packet *packet = msg->packet;
    struct completion *completion;

    if (!packet) return;
    msg->packet = NULL;
    completion = packet->completion;
    list_remove(&packet->port_entry);
    packet->completion = NULL;
    packet->msg = NULL;
    packet->queued = 0;
    release_object(completion);
    release_object(packet);
}

static unsigned int cancel_wait_packet(struct wait_packet *packet, int remove_signaled)
{
    struct completion *completion = packet->completion;
    struct comp_msg *msg = packet->msg;

    if (!completion) return STATUS_CANCELLED;
    if (packet->queued)
    {
        if (!remove_signaled) return STATUS_PENDING;
        list_remove(&msg->queue_entry);
        if (!--completion->depth) reset_sync(completion->sync);
    }
    else
    {
        packet->sync->ops->remove_queue(packet->sync, &packet->wait);
        release_object(packet->sync);
        release_object(packet->target);
        packet->sync = packet->target = NULL;
    }
    wait_packet_dequeued(msg);
    free(msg);
    return STATUS_SUCCESS;
}

static void cancel_completion_packets(struct completion *completion)
{
    struct wait_packet *packet;

    while (!list_empty(&completion->packets))
    {
        packet = LIST_ENTRY(list_head(&completion->packets), struct wait_packet, port_entry);
        cancel_wait_packet(packet, 1);
    }
}

static int signal_wait_packet(struct wait_queue_entry *entry)
{
    struct wait_packet *packet = CONTAINING_RECORD(entry, struct wait_packet, wait);
    struct completion *completion = packet->completion;
    struct completion_wait *wait;

    if (!packet->sync->ops->signaled(packet->sync, entry)) return 0;
    if (packet->sync->ops->satisfied) packet->sync->ops->satisfied(packet->sync, entry);
    packet->sync->ops->remove_queue(packet->sync, entry);
    release_object(packet->sync);
    release_object(packet->target);
    packet->sync = packet->target = NULL;
    packet->queued = 1;
    list_add_tail(&completion->queue, &packet->msg->queue_entry);
    completion->depth++;

    /* A waiting receiver may consume the packet and release its port reference. */
    grab_object(completion);
    LIST_FOR_EACH_ENTRY(wait, &completion->wait_queue, struct completion_wait, wait_queue_entry)
    {
        wake_up(&wait->obj, 1);
        if (list_empty(&completion->queue)) break;
    }
    if (!list_empty(&completion->queue)) signal_sync(completion->sync);
    release_object(completion);
    return 1;
}

static void wait_packet_dump(struct object *obj, int verbose)
{
    struct wait_packet *packet = (struct wait_packet *)obj;
    fprintf(stderr, "Wait completion packet associated=%d queued=%d\n",
            !!packet->completion, packet->queued);
}

static int wait_packet_close(struct object *obj, struct process *process, obj_handle_t handle)
{
    if (obj->handle_count == 1) cancel_wait_packet((struct wait_packet *)obj, 1);
    return 1;
}

static void wait_packet_destroy(struct object *obj)
{
    struct wait_packet *packet = (struct wait_packet *)obj;
    assert(!packet->completion && !packet->target && !packet->sync && !packet->msg);
}

static bool wait_packet_init(struct object *obj, const void *data)
{
    struct wait_packet *packet = (struct wait_packet *)obj;
    packet->target = packet->sync = NULL;
    packet->completion = NULL;
    packet->msg = NULL;
    packet->queued = 0;
    return true;
}

static const struct object_ops wait_packet_ops =
{
    .size = sizeof(struct wait_packet),
    .type = &wait_packet_type,
    .dump = wait_packet_dump,
    .init = wait_packet_init,
    .close_handle = wait_packet_close,
    .destroy = wait_packet_destroy,
};

DECL_HANDLER(create_wait_completion_packet)
{
    struct object_params params = { .ops = &wait_packet_ops, .access = req->access };

    if (!get_req_object_attributes(&params)) return;
    reply->handle = create_named_obj_handle(current->process, &params);
    if (params.root) release_object(params.root);
}

DECL_HANDLER(associate_wait_completion_packet)
{
    struct wait_packet *packet;
    struct completion *completion = NULL;
    struct object *target = NULL, *sync = NULL;
    struct comp_msg *msg = NULL;

    if (!(packet = (struct wait_packet *)get_handle_obj(current->process, req->packet, 1,
                                                       &wait_packet_ops))) return;
    if (packet->completion)
    {
        set_error(STATUS_INVALID_PARAMETER);
        goto done;
    }
    if (!(completion = get_completion_obj(current->process, req->completion, IO_COMPLETION_MODIFY_STATE))) goto done;
    if (!(target = get_handle_obj(current->process, req->target, SYNCHRONIZE, NULL))) goto done;
    if (target->ops->type != &event_type && target->ops->type != &timer_type &&
        target->ops->type != &semaphore_type && target->ops->type != &thread_type &&
        target->ops->type != &process_type && target->ops->type != &alpc_port_type)
    {
        set_error(STATUS_OBJECT_TYPE_MISMATCH);
        goto done;
    }
    if (!(sync = get_obj_sync(target))) goto done;
    if (!sync->ops->add_queue || !sync->ops->remove_queue || !sync->ops->signaled)
    {
        set_error(STATUS_NOT_SUPPORTED);
        goto done;
    }
    if (!(msg = mem_alloc(sizeof(*msg)))) goto done;
    packet->wait.wait = NULL;
    packet->wait.obj = sync;
    packet->wait.wake_callback = signal_wait_packet;
    if (!sync->ops->add_queue(sync, &packet->wait)) goto done;
    msg->ckey = req->ckey;
    msg->cvalue = req->cvalue;
    msg->status = req->status;
    msg->information = req->information;
    msg->packet = packet;
    packet->msg = msg;
    packet->completion = completion;
    packet->target = target;
    packet->sync = sync;
    packet->queued = 0;
    list_add_tail(&completion->packets, &packet->port_entry);
    grab_object(packet);
    reply->already_signaled = signal_wait_packet(&packet->wait);
    completion = NULL;
    target = sync = NULL;
    msg = NULL;
done:
    free(msg);
    if (sync) release_object(sync);
    if (target) release_object(target);
    if (completion) release_object(completion);
    release_object(packet);
}

DECL_HANDLER(cancel_wait_completion_packet)
{
    struct wait_packet *packet;

    if (!(packet = (struct wait_packet *)get_handle_obj(current->process, req->packet, 1,
                                                       &wait_packet_ops))) return;
    set_error(cancel_wait_packet(packet, req->remove_signaled));
    release_object(packet);
}
