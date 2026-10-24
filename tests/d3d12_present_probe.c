/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define COBJMACROS
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <stdio.h>
#include "probe_window_position.h"
#include <string.h>

#define WIDTH 320
#define HEIGHT 240
#define FRAMES 120
#define CHECK(name, call) do { \
    hr = (call); \
    printf("%s HRESULT=0x%08lx\n", name, (unsigned long)hr); \
    if (FAILED(hr)) goto cleanup; \
} while (0)
#define RELEASE(object, type) do { if (object) type##_Release(object); } while (0)

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    return DefWindowProcA(window, message, wparam, lparam);
}

static int wait_queue(ID3D12CommandQueue *queue, ID3D12Fence *fence,
                      HANDLE event, UINT64 value)
{
    HRESULT hr = ID3D12CommandQueue_Signal(queue, fence, value);
    if (FAILED(hr))
    {
        printf("Signal HRESULT=0x%08lx\n", (unsigned long)hr);
        return 0;
    }
    if (ID3D12Fence_GetCompletedValue(fence) < value)
    {
        hr = ID3D12Fence_SetEventOnCompletion(fence, value, event);
        if (FAILED(hr))
        {
            printf("SetEventOnCompletion HRESULT=0x%08lx\n", (unsigned long)hr);
            return 0;
        }
        if (WaitForSingleObject(event, 10000) != WAIT_OBJECT_0)
        {
            printf("ERROR fence wait failed or timed out win32=%lu\n", GetLastError());
            return 0;
        }
    }
    return 1;
}

int main(void)
{
    const float colour[4] = {0.2f, 0.4f, 0.8f, 1.0f};
    WNDCLASSA window_class = {0};
    RECT rect = {0, 0, WIDTH, HEIGHT};
    HWND window = NULL;
    HANDLE event = NULL;
    ID3D12Device *device = NULL;
    ID3D12CommandQueue *queue = NULL;
    ID3D12CommandAllocator *allocator = NULL;
    ID3D12GraphicsCommandList *list = NULL;
    ID3D12Fence *fence = NULL;
    ID3D12DescriptorHeap *heap = NULL;
    ID3D12Resource *buffers[2] = {NULL, NULL}, *readback = NULL;
    IDXGIFactory4 *factory = NULL;
    IDXGISwapChain1 *swapchain1 = NULL;
    IDXGISwapChain3 *swapchain = NULL;
    D3D12_COMMAND_QUEUE_DESC queue_desc = {0};
    DXGI_SWAP_CHAIN_DESC1 swap_desc = {0};
    D3D12_DESCRIPTOR_HEAP_DESC heap_desc = {0};
    D3D12_CPU_DESCRIPTOR_HANDLE handles[2];
    D3D12_HEAP_PROPERTIES properties = {0};
    D3D12_RESOURCE_DESC readback_desc = {0}, texture_desc;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint;
    D3D12_RANGE range;
    UINT64 bytes, fence_value = 0;
    UINT increment, frame, presented = 0;
    unsigned char *mapped = NULL;
    HRESULT hr = E_FAIL;
    int result = 1;
    int window_x, window_y;
    MSG message;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (!probe_window_position(&window_x, &window_y)) return 1;
    window_class.lpfnWndProc = window_proc;
    window_class.hInstance = GetModuleHandleA(NULL);
    window_class.lpszClassName = "CalimochoPresentProbe";
    if (!RegisterClassA(&window_class))
    {
        printf("ERROR RegisterClass win32=%lu\n", GetLastError());
        goto cleanup;
    }
    if (!AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE))
    {
        printf("ERROR AdjustWindowRect win32=%lu\n", GetLastError());
        goto cleanup;
    }
    window = CreateWindowExA(WS_EX_NOACTIVATE, window_class.lpszClassName,
                             "Calimocho D3D12 Present Probe", WS_OVERLAPPEDWINDOW,
                             window_x, window_y, rect.right - rect.left, rect.bottom - rect.top,
                             NULL, NULL, window_class.hInstance, NULL);
    if (!window)
    {
        printf("ERROR CreateWindow win32=%lu\n", GetLastError());
        goto cleanup;
    }
    ShowWindow(window, SW_SHOWNOACTIVATE);
    printf("window hwnd=%p size=%dx%d no_activate=1\n", window, WIDTH, HEIGHT);
    CHECK("CreateDXGIFactory", CreateDXGIFactory2(0, &IID_IDXGIFactory4, (void **)&factory));
    CHECK("D3D12CreateDevice", D3D12CreateDevice(NULL, D3D_FEATURE_LEVEL_11_0,
                                               &IID_ID3D12Device, (void **)&device));
    queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    CHECK("CreateCommandQueue", ID3D12Device_CreateCommandQueue(
        device, &queue_desc, &IID_ID3D12CommandQueue, (void **)&queue));
    swap_desc.Width = WIDTH;
    swap_desc.Height = HEIGHT;
    swap_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    swap_desc.SampleDesc.Count = 1;
    swap_desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    swap_desc.BufferCount = 2;
    swap_desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    CHECK("CreateSwapChainForHwnd", IDXGIFactory4_CreateSwapChainForHwnd(
        factory, (IUnknown *)queue, window, &swap_desc, NULL, NULL, &swapchain1));
    CHECK("SwapChain3", IDXGISwapChain1_QueryInterface(
        swapchain1, &IID_IDXGISwapChain3, (void **)&swapchain));
    CHECK("CreateAllocator", ID3D12Device_CreateCommandAllocator(
        device, D3D12_COMMAND_LIST_TYPE_DIRECT, &IID_ID3D12CommandAllocator, (void **)&allocator));
    CHECK("CreateCommandList", ID3D12Device_CreateCommandList(
        device, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator, NULL,
        &IID_ID3D12GraphicsCommandList, (void **)&list));
    CHECK("InitialClose", ID3D12GraphicsCommandList_Close(list));
    CHECK("CreateFence", ID3D12Device_CreateFence(
        device, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void **)&fence));
    event = CreateEventA(NULL, FALSE, FALSE, NULL);
    if (!event)
    {
        printf("ERROR CreateEvent win32=%lu\n", GetLastError());
        goto cleanup;
    }
    heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    heap_desc.NumDescriptors = 2;
    CHECK("CreateRTVHeap", ID3D12Device_CreateDescriptorHeap(
        device, &heap_desc, &IID_ID3D12DescriptorHeap, (void **)&heap));
    /* MinGW's C header exposes this structure-return method through its vtable. */
    heap->lpVtbl->GetCPUDescriptorHandleForHeapStart(heap, &handles[0]);
    increment = ID3D12Device_GetDescriptorHandleIncrementSize(device, D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
    handles[1].ptr = handles[0].ptr + increment;
    for (frame = 0; frame < 2; ++frame)
    {
        CHECK("GetBuffer", IDXGISwapChain3_GetBuffer(
            swapchain, frame, &IID_ID3D12Resource, (void **)&buffers[frame]));
        ID3D12Device_CreateRenderTargetView(device, buffers[frame], NULL, handles[frame]);
    }
    buffers[0]->lpVtbl->GetDesc(buffers[0], &texture_desc);
    ID3D12Device_GetCopyableFootprints(device, &texture_desc, 0, 1, 0, &footprint, NULL, NULL, &bytes);
    properties.Type = D3D12_HEAP_TYPE_READBACK;
    readback_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    readback_desc.Width = bytes;
    readback_desc.Height = readback_desc.DepthOrArraySize = readback_desc.MipLevels = 1;
    readback_desc.SampleDesc.Count = 1;
    readback_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    CHECK("CreateReadback", ID3D12Device_CreateCommittedResource(
        device, &properties, D3D12_HEAP_FLAG_NONE, &readback_desc,
        D3D12_RESOURCE_STATE_COPY_DEST, NULL, &IID_ID3D12Resource, (void **)&readback));

    for (frame = 0; frame < FRAMES; ++frame)
    {
        UINT index = IDXGISwapChain3_GetCurrentBackBufferIndex(swapchain);
        D3D12_RESOURCE_BARRIER barrier = {0};
        D3D12_TEXTURE_COPY_LOCATION src = {0}, dst = {0};
        ID3D12CommandList *submitted = (ID3D12CommandList *)list;
        while (PeekMessageA(&message, NULL, 0, 0, PM_REMOVE))
        {
            TranslateMessage(&message);
            DispatchMessageA(&message);
        }
        CHECK("ResetAllocator", ID3D12CommandAllocator_Reset(allocator));
        CHECK("ResetList", ID3D12GraphicsCommandList_Reset(list, allocator, NULL));
        barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        barrier.Transition.pResource = buffers[index];
        barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT;
        barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_RENDER_TARGET;
        ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
        ID3D12GraphicsCommandList_ClearRenderTargetView(list, handles[index], colour, 0, NULL);
        barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
        if (frame == FRAMES - 1)
        {
            barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
            ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
            src.pResource = buffers[index];
            src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
            dst.pResource = readback;
            dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
            dst.PlacedFootprint = footprint;
            ID3D12GraphicsCommandList_CopyTextureRegion(list, &dst, 0, 0, 0, &src, NULL);
            barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE;
        }
        barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PRESENT;
        ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
        CHECK("CloseList", ID3D12GraphicsCommandList_Close(list));
        ID3D12CommandQueue_ExecuteCommandLists(queue, 1, &submitted);
        if (!wait_queue(queue, fence, event, ++fence_value)) goto cleanup;
        hr = IDXGISwapChain3_Present(swapchain, 1, 0);
        if (hr != S_OK)
        {
            printf("Present frame=%u HRESULT=0x%08lx\n", frame, (unsigned long)hr);
            goto cleanup;
        }
        if (!frame || frame == FRAMES - 1)
            printf("Present frame=%u HRESULT=0x%08lx\n", frame, (unsigned long)hr);
        ++presented;
        if (presented == 60)
        {
            printf("capture_ready presents=60 colour_rgba=51,102,204,255\n");
            Sleep(4000);
        }
        Sleep(16);
    }
    range.Begin = 0;
    range.End = (SIZE_T)bytes;
    CHECK("ReadbackMap", ID3D12Resource_Map(readback, 0, &range, (void **)&mapped));
    {
        const unsigned char *pixel = mapped + footprint.Offset +
            (HEIGHT / 2) * footprint.Footprint.RowPitch + (WIDTH / 2) * 4;
        int matched = pixel[0] == 51 && pixel[1] == 102 && pixel[2] == 204 && pixel[3] == 255;
        printf("readback_pixel rgba=%u,%u,%u,%u expected=51,102,204,255 matched=%d\n",
               pixel[0], pixel[1], pixel[2], pixel[3], matched);
        result = matched ? 0 : 1;
    }
    range.Begin = range.End = 0;
    ID3D12Resource_Unmap(readback, 0, &range);
    mapped = NULL;

cleanup:
    if (queue && fence && event && !wait_queue(queue, fence, event, ++fence_value)) result = 1;
    printf("Present count=%u target=%u last_HRESULT=0x%08lx result=%d\n",
           presented, FRAMES, (unsigned long)hr, result);
    RELEASE(readback, ID3D12Resource);
    RELEASE(buffers[0], ID3D12Resource);
    RELEASE(buffers[1], ID3D12Resource);
    RELEASE(heap, ID3D12DescriptorHeap);
    RELEASE(list, ID3D12GraphicsCommandList);
    RELEASE(allocator, ID3D12CommandAllocator);
    RELEASE(swapchain, IDXGISwapChain3);
    RELEASE(swapchain1, IDXGISwapChain1);
    RELEASE(factory, IDXGIFactory4);
    RELEASE(fence, ID3D12Fence);
    RELEASE(queue, ID3D12CommandQueue);
    RELEASE(device, ID3D12Device);
    if (event) CloseHandle(event);
    if (window) DestroyWindow(window);
    return result;
}
