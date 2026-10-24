/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <stdio.h>
#include "probe_window_position.h"

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

int main(void)
{
    const float colour[4] = {0.2f, 0.4f, 0.8f, 1.0f};
    const D3D_FEATURE_LEVEL requested[] = {D3D_FEATURE_LEVEL_11_0};
    D3D_FEATURE_LEVEL level = 0;
    WNDCLASSA cls = {0};
    RECT rect = {0, 0, WIDTH, HEIGHT};
    HWND window = NULL;
    ID3D11Device *device = NULL;
    ID3D11DeviceContext *context = NULL;
    IDXGIFactory2 *factory = NULL;
    IDXGISwapChain1 *swapchain = NULL;
    ID3D11Texture2D *backbuffer = NULL, *staging = NULL;
    ID3D11RenderTargetView *view = NULL;
    DXGI_SWAP_CHAIN_DESC1 swap_desc = {0};
    D3D11_TEXTURE2D_DESC desc;
    D3D11_MAPPED_SUBRESOURCE mapped;
    UINT frame, presented = 0;
    HRESULT hr = E_FAIL;
    int result = 1;
    int window_x, window_y;
    MSG message;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (!probe_window_position(&window_x, &window_y)) return 1;
    cls.lpfnWndProc = window_proc;
    cls.hInstance = GetModuleHandleA(NULL);
    cls.lpszClassName = "CalimochoD3D11PresentProbe";
    if (!RegisterClassA(&cls) || !AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE))
    {
        printf("ERROR window setup win32=%lu\n", GetLastError());
        goto cleanup;
    }
    window = CreateWindowExA(WS_EX_NOACTIVATE, cls.lpszClassName,
        "Calimocho D3D11 Present Probe", WS_OVERLAPPEDWINDOW,
        window_x, window_y, rect.right - rect.left, rect.bottom - rect.top,
        NULL, NULL, cls.hInstance, NULL);
    if (!window)
    {
        printf("ERROR CreateWindow win32=%lu\n", GetLastError());
        goto cleanup;
    }
    ShowWindow(window, SW_SHOWNOACTIVATE);
    printf("window hwnd=%p size=%dx%d no_activate=1\n", window, WIDTH, HEIGHT);
    CHECK("D3D11CreateDevice", D3D11CreateDevice(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL,
        0, requested, 1, D3D11_SDK_VERSION, &device, &level, &context));
    printf("feature_level=0x%x\n", level);
    CHECK("CreateDXGIFactory", CreateDXGIFactory1(&IID_IDXGIFactory2, (void **)&factory));
    swap_desc.Width = WIDTH;
    swap_desc.Height = HEIGHT;
    swap_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    swap_desc.SampleDesc.Count = 1;
    swap_desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    swap_desc.BufferCount = 2;
    swap_desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    CHECK("CreateSwapChainForHwnd", IDXGIFactory2_CreateSwapChainForHwnd(
        factory, (IUnknown *)device, window, &swap_desc, NULL, NULL, &swapchain));
    CHECK("GetBuffer", IDXGISwapChain1_GetBuffer(
        swapchain, 0, &IID_ID3D11Texture2D, (void **)&backbuffer));
    CHECK("CreateRenderTargetView", ID3D11Device_CreateRenderTargetView(
        device, (ID3D11Resource *)backbuffer, NULL, &view));
    ID3D11Texture2D_GetDesc(backbuffer, &desc);
    desc.Usage = D3D11_USAGE_STAGING;
    desc.BindFlags = 0;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    desc.MiscFlags = 0;
    CHECK("CreateStagingTexture", ID3D11Device_CreateTexture2D(device, &desc, NULL, &staging));
    for (frame = 0; frame < FRAMES; ++frame)
    {
        while (PeekMessageA(&message, NULL, 0, 0, PM_REMOVE))
        {
            TranslateMessage(&message);
            DispatchMessageA(&message);
        }
        ID3D11DeviceContext_ClearRenderTargetView(context, view, colour);
        if (frame == FRAMES - 1)
            ID3D11DeviceContext_CopyResource(context, (ID3D11Resource *)staging,
                                             (ID3D11Resource *)backbuffer);
        hr = IDXGISwapChain1_Present(swapchain, 1, 0);
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
    CHECK("StagingMap", ID3D11DeviceContext_Map(context, (ID3D11Resource *)staging,
        0, D3D11_MAP_READ, 0, &mapped));
    {
        const unsigned char *pixel = (const unsigned char *)mapped.pData +
            (HEIGHT / 2) * mapped.RowPitch + (WIDTH / 2) * 4;
        int matched = pixel[0] == 51 && pixel[1] == 102 && pixel[2] == 204 && pixel[3] == 255;
        printf("readback_pixel rgba=%u,%u,%u,%u expected=51,102,204,255 matched=%d\n",
            pixel[0], pixel[1], pixel[2], pixel[3], matched);
        result = matched ? 0 : 1;
    }
    ID3D11DeviceContext_Unmap(context, (ID3D11Resource *)staging, 0);
cleanup:
    printf("Present count=%u target=%u last_HRESULT=0x%08lx result=%d\n",
        presented, FRAMES, (unsigned long)hr, result);
    if (context)
    {
        ID3D11DeviceContext_ClearState(context);
        ID3D11DeviceContext_Flush(context);
    }
    RELEASE(staging, ID3D11Texture2D);
    RELEASE(view, ID3D11RenderTargetView);
    RELEASE(backbuffer, ID3D11Texture2D);
    RELEASE(swapchain, IDXGISwapChain1);
    RELEASE(factory, IDXGIFactory2);
    RELEASE(context, ID3D11DeviceContext);
    RELEASE(device, ID3D11Device);
    if (window) DestroyWindow(window);
    return result;
}
