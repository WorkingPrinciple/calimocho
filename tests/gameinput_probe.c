/* Windowless no-device GameInput contract. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <windows.h>
#include <initguid.h>
#include "gameinput.h"

static unsigned int failures, notifications;
#define check(test) do { if (!(test)) { \
    fprintf(stderr, "FAIL line %u: %s\n", __LINE__, #test); ++failures; } } while (0)

static void WINAPI device_callback(GameInputCallbackToken token, void *context, v0_IGameInputDevice *device,
                                   uint64_t timestamp, GameInputDeviceStatus current, GameInputDeviceStatus previous)
{
    ++notifications;
}

#define EXTRA_CALLBACKS(ver) \
static void WINAPI ver##_system_callback(GameInputCallbackToken token, void *context, ver##_IGameInputDevice *device, uint64_t time, GameInputSystemButtons current, GameInputSystemButtons previous) \
{ ++notifications; } \
static void WINAPI ver##_keyboard_callback(GameInputCallbackToken token, void *context, ver##_IGameInputDevice *device, uint64_t time, uint32_t current, uint32_t previous) \
{ ++notifications; }
EXTRA_CALLBACKS(v0)
EXTRA_CALLBACKS(v1)
EXTRA_CALLBACKS(v2)

#define NEW_VERSION_CHECK(ver) \
static void WINAPI ver##_device_callback(GameInputCallbackToken token, void *context, ver##_IGameInputDevice *device, uint64_t time, GameInputDeviceStatus current, GameInputDeviceStatus previous) \
{ ++notifications; } \
static void WINAPI ver##_reading_callback(GameInputCallbackToken token, void *context, ver##_IGameInputReading *reading) \
{ ++notifications; } \
static void check_##ver(ver##_IGameInput *input) \
{ \
    ver##_IGameInputReading *reading = (void *)1; \
    ver##_IGameInputDevice *device = (void *)1; \
    APP_LOCAL_DEVICE_ID id = {{0}}; \
    GameInputCallbackToken token = 0; \
    check(ver##_IGameInput_GetCurrentReading(input, GameInputKindGamepad, NULL, &reading) == (HRESULT)GAMEINPUT_E_READING_NOT_FOUND && !reading); \
    check(ver##_IGameInput_GetNextReading(input, NULL, GameInputKindGamepad, NULL, &reading) == (HRESULT)GAMEINPUT_E_READING_NOT_FOUND && !reading); \
    check(ver##_IGameInput_GetPreviousReading(input, NULL, GameInputKindGamepad, NULL, &reading) == (HRESULT)GAMEINPUT_E_READING_NOT_FOUND && !reading); \
    check(ver##_IGameInput_FindDeviceFromId(input, &id, &device) == (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND && !device); \
    check(ver##_IGameInput_RegisterReadingCallback(input, NULL, GameInputKindGamepad, NULL, ver##_reading_callback, &token) == S_OK && token); \
    ver##_IGameInput_StopCallback(input, token); \
    check(ver##_IGameInput_UnregisterCallback(input, token)); \
    check(ver##_IGameInput_RegisterDeviceCallback(input, NULL, GameInputKindGamepad, ver##_GameInputDeviceAnyStatus, GameInputBlockingEnumeration, NULL, ver##_device_callback, &token) == S_OK && token); \
    check(ver##_IGameInput_UnregisterCallback(input, token)); \
    check(ver##_IGameInput_RegisterSystemButtonCallback(input, NULL, GameInputSystemButtonNone, NULL, ver##_system_callback, &token) == S_OK && token); \
    check(ver##_IGameInput_UnregisterCallback(input, token)); \
    check(ver##_IGameInput_RegisterKeyboardLayoutCallback(input, NULL, NULL, ver##_keyboard_callback, &token) == S_OK && token); \
    check(ver##_IGameInput_UnregisterCallback(input, token)); \
    token = 123; \
    check(ver##_IGameInput_RegisterDeviceCallback(input, NULL, GameInputKindGamepad, ver##_GameInputDeviceAnyStatus, GameInputBlockingEnumeration, NULL, NULL, &token) == E_INVALIDARG && token == 0); \
    ver##_IGameInput_SetFocusPolicy(input, GameInputDefaultFocusPolicy); \
}
NEW_VERSION_CHECK(v1)
NEW_VERSION_CHECK(v2)

int main(void)
{
    HRESULT (WINAPI *initialize)(REFIID, void **);
    HRESULT (WINAPI *create)(v0_IGameInput **);
    HRESULT (WINAPI *can_unload)(void);
    HMODULE module = LoadLibraryW(L"gameinput.dll");
    WCHAR module_path[MAX_PATH], expected_path[MAX_PATH];
    v0_IGameInput *input = NULL;
    v1_IGameInput *v1 = NULL;
    v2_IGameInput *v2 = NULL;
    IUnknown *identity0 = NULL, *identity2 = NULL;
    v0_IGameInputReading *reading = (void *)1;
    v0_IGameInputDevice *device = (void *)1;
    IGameInputDispatcher *dispatcher = NULL;
    GameInputCallbackToken first = 0, second = 0;
    LARGE_INTEGER before, after, frequency;
    uint64_t timestamp;
    HANDLE wait;
    HRESULT hr;
    GUID unknown = {0x12345678, 0x1234, 0x1234, {1,2,3,4,5,6,7,8}};
    void *out = (void *)1;

    check(module != NULL);
    if (!module) return 1;
    check(GetModuleFileNameW(module, module_path, MAX_PATH) > 0);
    check(GetSystemDirectoryW(expected_path, MAX_PATH) > 0);
    lstrcatW(expected_path, L"\\gameinput.dll");
    check(!lstrcmpiW(module_path, expected_path));
    initialize = (void *)GetProcAddress(module, "GameInputInitialize");
    create = (void *)GetProcAddress(module, "GameInputCreate");
    can_unload = (void *)GetProcAddress(module, "DllCanUnloadNow");
    check(create != NULL);
    hr = create ? create(&input) : E_NOTIMPL;
    printf("GameInputCreate HRESULT=%08lx Initialize_export=%u\n", hr, !!initialize);
    check(hr == S_OK && input != NULL);
    check(initialize != NULL);
    if (!input || !initialize || !can_unload) { FreeLibrary(module); return 1; }
    check(create(NULL) == E_POINTER);
    check(initialize(&unknown, &out) == E_NOINTERFACE && out == NULL);
    check(initialize(NULL, &out) == E_INVALIDARG);
    check(initialize(&IID_v0_IGameInput, NULL) == E_POINTER);
    check(can_unload && can_unload() == S_FALSE);
    check(v0_IGameInput_QueryInterface(input, &IID_v1_IGameInput, (void **)&v1) == S_OK);
    check(v0_IGameInput_QueryInterface(input, &IID_v2_IGameInput, (void **)&v2) == S_OK);
    if (!v1 || !v2) return 1;
    check(v0_IGameInput_QueryInterface(input, &IID_IUnknown, (void **)&identity0) == S_OK);
    check(v2_IGameInput_QueryInterface(v2, &IID_IUnknown, (void **)&identity2) == S_OK);
    check(identity0 == identity2);
    IUnknown_Release(identity0);
    IUnknown_Release(identity2);
    check_v1(v1);
    check_v2(v2);

    check(v0_IGameInput_GetCurrentReading(input, GameInputKindGamepad, NULL, &reading)
          == (HRESULT)GAMEINPUT_E_READING_NOT_FOUND && reading == NULL);
    check(v0_IGameInput_GetCurrentReading(input, GameInputKindGamepad, NULL, NULL) == E_POINTER);
    reading = (void *)1;
    check(v0_IGameInput_GetTemporalReading(input, 0, NULL, &reading)
          == (HRESULT)GAMEINPUT_E_READING_NOT_FOUND && reading == NULL);
    check(v0_IGameInput_FindDeviceFromPlatformString(input, L"not-a-device", &device)
          == (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND && device == NULL);
    check(v0_IGameInput_CreateAggregateDevice(input, GameInputKindGamepad, &device)
          == (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND && device == NULL);
    check(v0_IGameInput_RegisterDeviceCallback(input, NULL, GameInputKindGamepad, v0_GameInputDeviceAnyStatus,
          GameInputBlockingEnumeration, NULL, device_callback, &first) == S_OK && first != 0);
    check(v0_IGameInput_RegisterDeviceCallback(input, NULL, GameInputKindGamepad, v0_GameInputDeviceAnyStatus,
          GameInputBlockingEnumeration, NULL, device_callback, &second) == S_OK && second != first && second != 0);
    check(notifications == 0);
    v0_IGameInput_StopCallback(input, first);
    check(v0_IGameInput_UnregisterCallback(input, first, 0));
    check(!v0_IGameInput_UnregisterCallback(input, first, 0));
    check(v0_IGameInput_UnregisterCallback(input, second, 0));
    check(v0_IGameInput_RegisterSystemButtonCallback(input, NULL, GameInputSystemButtonNone,
          NULL, v0_system_callback, &first) == S_OK && first);
    check(v0_IGameInput_UnregisterCallback(input, first, 0));
    check(v0_IGameInput_RegisterKeyboardLayoutCallback(input, NULL, NULL,
          v0_keyboard_callback, &first) == S_OK && first);
    check(v0_IGameInput_UnregisterCallback(input, first, 0));
    first = 123;
    check(v0_IGameInput_RegisterDeviceCallback(input, NULL, GameInputKindGamepad, v0_GameInputDeviceAnyStatus,
          GameInputBlockingEnumeration, NULL, NULL, &first) == E_INVALIDARG && first == 0);
    check(v0_IGameInput_CreateDispatcher(input, &dispatcher) == S_OK && dispatcher != NULL);
    if (dispatcher)
    {
        check(!IGameInputDispatcher_Dispatch(dispatcher, 0));
        check(IGameInputDispatcher_OpenWaitHandle(dispatcher, &wait) == S_OK);
        check(WaitForSingleObject(wait, 0) == WAIT_TIMEOUT);
        CloseHandle(wait);
        IGameInputDispatcher_Release(dispatcher);
    }
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&before);
    timestamp = v2_IGameInput_GetCurrentTimestamp(v2);
    QueryPerformanceCounter(&after);
    check(timestamp >= (uint64_t)before.QuadPart / frequency.QuadPart * 1000000 +
                       (uint64_t)(before.QuadPart % frequency.QuadPart) * 1000000 / frequency.QuadPart);
    check(timestamp <= (uint64_t)after.QuadPart / frequency.QuadPart * 1000000 +
                       (uint64_t)(after.QuadPart % frequency.QuadPart) * 1000000 / frequency.QuadPart);
    v1_IGameInput_Release(v1);
    v2_IGameInput_Release(v2);
    check(v0_IGameInput_Release(input) == 0);
    out = NULL;
    check(initialize(&IID_v0_IGameInput, &out) == S_OK && out != NULL);
    if (out) v0_IGameInput_Release((v0_IGameInput *)out);
    out = NULL;
    check(initialize(&IID_v1_IGameInput, &out) == S_OK && out != NULL);
    if (out) v1_IGameInput_Release((v1_IGameInput *)out);
    out = NULL;
    check(initialize(&IID_v2_IGameInput, &out) == S_OK && out != NULL);
    if (out) v2_IGameInput_Release((v2_IGameInput *)out);
    check(can_unload() == S_OK);
    printf("no-device callbacks=%u failures=%u\n", notifications, failures);
    FreeLibrary(module);
    return failures ? 1 : 0;
}
