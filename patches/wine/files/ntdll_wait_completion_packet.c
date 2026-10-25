/* Server-backed wait completion packets. LGPL-2.1-or-later */
NTSTATUS WINAPI NtCreateWaitCompletionPacket(HANDLE *handle, ACCESS_MASK access,
                                             OBJECT_ATTRIBUTES *attributes)
{
    struct object_attributes *object;
    data_size_t size;
    NTSTATUS status;

    if (!handle) return STATUS_ACCESS_VIOLATION;
    *handle = NULL;
    if ((status = wine_server_alloc_object_attributes(attributes, &object, &size))) return status;
    SERVER_START_REQ(create_wait_completion_packet)
    {
        req->access = access;
        wine_server_add_data(req, object, size);
        status = wine_server_call(req);
        if (!status) *handle = wine_server_ptr_handle(reply->handle);
    }
    SERVER_END_REQ;
    free(object);
    return status;
}

NTSTATUS WINAPI NtAssociateWaitCompletionPacket(HANDLE packet, HANDLE completion, HANDLE target,
                                                void *key, void *value, NTSTATUS io_status,
                                                ULONG_PTR information, BOOLEAN *already_signaled)
{
    NTSTATUS status;

    SERVER_START_REQ(associate_wait_completion_packet)
    {
        req->packet = wine_server_obj_handle(packet);
        req->completion = wine_server_obj_handle(completion);
        req->target = wine_server_obj_handle(target);
        req->ckey = (ULONG_PTR)key;
        req->cvalue = (ULONG_PTR)value;
        req->status = io_status;
        req->information = information;
        status = wine_server_call(req);
        if (!status && already_signaled) *already_signaled = reply->already_signaled;
    }
    SERVER_END_REQ;
    return status;
}

NTSTATUS WINAPI NtCancelWaitCompletionPacket(HANDLE packet, BOOLEAN remove_signaled)
{
    NTSTATUS status;

    SERVER_START_REQ(cancel_wait_completion_packet)
    {
        req->packet = wine_server_obj_handle(packet);
        req->remove_signaled = remove_signaled;
        status = wine_server_call(req);
    }
    SERVER_END_REQ;
    return status;
}
