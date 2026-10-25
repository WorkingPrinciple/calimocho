/*
 * Explicit verified local package graph, not Store trust or capabilities.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#ifndef __WINE_PACKAGE_GRAPH_H
#define __WINE_PACKAGE_GRAPH_H
#include "wine/package.h"

#define WINE_GRAPH_MAGIC 0x47505743
#define WINE_GRAPH_MAX 17
struct wine_graph_entry
{
    WCHAR full_name[256];
    WCHAR family_name[256];
    WCHAR path[1024];
};
struct wine_package_graph
{
    ULONG magic, version, count;
    struct wine_graph_entry entries[WINE_GRAPH_MAX];
};

static BOOL wine_graph_terminated(const WCHAR *text, unsigned int capacity)
{
    unsigned int i;
    for (i = 0; i < capacity; ++i) if (!text[i]) return TRUE;
    return FALSE;
}

static NTSTATUS wine_load_package_graph(struct wine_package_graph **result)
{
    struct wine_package_identity identity;
    struct wine_package_graph *graph;
    UNICODE_STRING name = RTL_CONSTANT_STRING(L"CALIMOCHO_PACKAGE_GRAPH"), value, filename;
    WCHAR path[1024];
    OBJECT_ATTRIBUTES attributes;
    IO_STATUS_BLOCK io;
    HANDLE file;
    NTSTATUS status;
    unsigned int i;
    ULONG size;
    *result = NULL;
    status = wine_query_package_identity((HANDLE)(LONG_PTR)-4, &identity);
    if (status) return status;
    if (!identity.verified_gamingapp) return STATUS_NOT_FOUND;
    value.Buffer = path;
    value.Length = 0;
    value.MaximumLength = sizeof(path) - sizeof(WCHAR);
    status = RtlQueryEnvironmentVariable_U(NULL, &name, &value);
    if (status == STATUS_VARIABLE_NOT_FOUND) return STATUS_NOT_FOUND;
    if (status) return status;
    path[value.Length / sizeof(WCHAR)] = 0;
    if ((status = RtlDosPathNameToNtPathName_U_WithStatus(path, &filename, NULL, NULL))) return status;
    InitializeObjectAttributes(&attributes, &filename, OBJ_CASE_INSENSITIVE, NULL, NULL);
    status = NtOpenFile(&file, GENERIC_READ | SYNCHRONIZE, &attributes, &io,
                        FILE_SHARE_READ, FILE_SYNCHRONOUS_IO_NONALERT | FILE_NON_DIRECTORY_FILE);
    RtlFreeUnicodeString(&filename);
    if (status) return status;
    graph = RtlAllocateHeap(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(*graph) + 1);
    if (!graph)
    {
        NtClose(file);
        return STATUS_NO_MEMORY;
    }
    status = NtReadFile(file, NULL, NULL, NULL, &io, graph, sizeof(*graph) + 1, NULL, NULL);
    NtClose(file);
    if (status) goto failed;
    size = offsetof(struct wine_package_graph, entries);
    if (io.Information < size || graph->magic != WINE_GRAPH_MAGIC || graph->version != 1
        || !graph->count || graph->count > WINE_GRAPH_MAX
        || io.Information != size + graph->count * sizeof(graph->entries[0]))
    {
        status = STATUS_INVALID_PARAMETER;
        goto failed;
    }
    for (i = 0; i < graph->count; ++i)
    {
        struct wine_graph_entry *entry = &graph->entries[i];
        if (!entry->full_name[0] || !wine_graph_terminated(entry->full_name, 256)
            || !entry->family_name[0] || !wine_graph_terminated(entry->family_name, 256)
            || !wine_graph_terminated(entry->path, 1024)
            || entry->path[0] != 'Z' || entry->path[1] != ':' || entry->path[2] != '\\'
            || wcschr(entry->path, ';'))
        {
            status = STATUS_INVALID_PARAMETER;
            goto failed;
        }
    }
    if (wcscmp(identity.full_name, graph->entries[0].full_name)
        || wcscmp(identity.family_name, graph->entries[0].family_name))
    {
        status = STATUS_ACCESS_DENIED;
        goto failed;
    }
    *result = graph;
    return STATUS_SUCCESS;
failed:
    RtlFreeHeap(GetProcessHeap(), 0, graph);
    return status;
}
#endif
