/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <windows.h>
#include <windowsx.h>
#include <stdio.h>
#include <string.h>

static unsigned int relative_packets, nonzero_packets, absolute_packets, mouse_moves, errors;
static BOOL running, aborted;
static HWND probe_window;

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    if (message == WM_INPUT && running)
    {
        RAWINPUT input;
        UINT size = sizeof(input);
        UINT read = GetRawInputData((HRAWINPUT)lparam, RID_INPUT, &input, &size,
                                   sizeof(RAWINPUTHEADER));
        if (read == (UINT)-1 || read < sizeof(RAWINPUTHEADER))
        {
            printf("ERROR GetRawInputData win32=%lu size=%u\n", GetLastError(), read);
            ++errors;
        }
        else if (input.header.dwType == RIM_TYPEMOUSE)
        {
            if (read < sizeof(RAWINPUTHEADER) + sizeof(RAWMOUSE))
            {
                printf("ERROR truncated RAWMOUSE size=%u\n", read);
                ++errors;
            }
            else
            {
                const RAWMOUSE *mouse = &input.data.mouse;
                if (mouse->usFlags & MOUSE_MOVE_ABSOLUTE) ++absolute_packets;
                else
                {
                    ++relative_packets;
                    if (mouse->lLastX || mouse->lLastY) ++nonzero_packets;
                }
                printf("RAW flags=%u dx=%ld dy=%ld foreground=%d\n", mouse->usFlags,
                       mouse->lLastX, mouse->lLastY, GetForegroundWindow() == window);
            }
        }
        /* Foreground WM_INPUT requires DefWindowProc cleanup. */
    }
    else if (message == WM_MOUSEMOVE && running)
    {
        POINT cursor;
        ++mouse_moves;
        if (!GetCursorPos(&cursor))
        {
            printf("ERROR GetCursorPos win32=%lu\n", GetLastError());
            ++errors;
        }
        else
            printf("MOVE client_x=%d client_y=%d screen_x=%ld screen_y=%ld\n",
                   GET_X_LPARAM(lparam), GET_Y_LPARAM(lparam), cursor.x, cursor.y);
    }
    else if ((message == WM_KILLFOCUS || message == WM_CLOSE) && running)
    {
        aborted = TRUE;
        running = FALSE;
        return 0;
    }
    return DefWindowProcA(window, message, wparam, lparam);
}

int main(int argc, char **argv)
{
    WNDCLASSA cls = {0};
    RAWINPUTDEVICE device = {1, 2, 0, NULL};
    CURSORINFO cursor_info = {sizeof(CURSORINFO), 0, NULL, {0, 0}};
    RECT clip, previous_clip;
    MSG message;
    ULONGLONG started = 0, elapsed = 0;
    unsigned int hidden_calls = 0;
    UINT registrations = 0;
    BOOL saved_clip = FALSE, clipped = FALSE, registered = FALSE, unclipped = FALSE;
    BOOL clip_restored = TRUE, raw_removed = TRUE;
    unsigned int restored_calls = 0;
    int result = 1;

    if (argc != 2 || (strcmp(argv[1], "--run") && strcmp(argv[1], "--unclipped")))
    {
        fprintf(stderr, "Usage: raw-mouse-probe.exe --run|--unclipped\n"
                "Requires exclusive desktop input lease; foreground window for 5 seconds.\n");
        return 2;
    }
    unclipped = !strcmp(argv[1], "--unclipped");
    setvbuf(stdout, NULL, _IONBF, 0);
    cls.lpfnWndProc = window_proc;
    cls.hInstance = GetModuleHandleA(NULL);
    cls.lpszClassName = "CalimochoRawMouseProbe";
    if (!RegisterClassA(&cls)) goto win32_error;
    probe_window = CreateWindowExA(0, cls.lpszClassName, "Calimocho Raw Mouse Probe",
                                  WS_OVERLAPPEDWINDOW, 80, 80, 400, 300,
                                  NULL, NULL, cls.hInstance, NULL);
    if (!probe_window) goto win32_error;
    ShowWindow(probe_window, SW_SHOW);
    if (!SetForegroundWindow(probe_window)) goto win32_error;
    SetFocus(probe_window);
    while (PeekMessageA(&message, NULL, 0, 0, PM_REMOVE))
    {
        TranslateMessage(&message);
        DispatchMessageA(&message);
    }
    if (GetForegroundWindow() != probe_window || GetFocus() != probe_window)
    {
        printf("ERROR probe did not acquire foreground/focus\n");
        goto cleanup;
    }
    if (!GetClientRect(probe_window, &clip) ||
        !ClientToScreen(probe_window, (POINT *)&clip.left) ||
        !ClientToScreen(probe_window, (POINT *)&clip.right)) goto win32_error;
    if (!GetCursorInfo(&cursor_info) ||
        GetRegisteredRawInputDevices(NULL, &registrations, sizeof(device)) == (UINT)-1)
        goto win32_error;
    if (registrations)
    {
        printf("ERROR unexpected existing raw registrations=%u\n", registrations);
        goto cleanup;
    }
    printf("ORIGINAL cursor_flags=%lu registrations=%u\n", cursor_info.flags, registrations);
    device.hwndTarget = probe_window;
    if (!RegisterRawInputDevices(&device, 1, sizeof(device))) goto win32_error;
    registered = TRUE;
    if (!unclipped)
    {
        if (!GetClipCursor(&previous_clip)) goto win32_error;
        saved_clip = TRUE;
        printf("ORIGINAL_CLIP left=%ld top=%ld right=%ld bottom=%ld\n",
               previous_clip.left, previous_clip.top, previous_clip.right, previous_clip.bottom);
        if (!ClipCursor(&clip)) goto win32_error;
        clipped = TRUE;
    }
    do
    {
        if (hidden_calls == 32)
        {
            printf("ERROR cursor display counter did not become hidden\n");
            ++errors;
            goto cleanup;
        }
        ++hidden_calls;
    } while (ShowCursor(FALSE) >= 0);
    running = TRUE;
    started = GetTickCount64();
    printf("READY pid=%lu hwnd=%p clip=%d left=%ld top=%ld right=%ld bottom=%ld duration_ms=5000\n",
           GetCurrentProcessId(), probe_window, !unclipped,
           clip.left, clip.top, clip.right, clip.bottom);
    while (running && (elapsed = GetTickCount64() - started) < 5000)
    {
        if (GetForegroundWindow() != probe_window)
        {
            aborted = TRUE;
            break;
        }
        if (MsgWaitForMultipleObjects(0, NULL, FALSE, 20, QS_ALLINPUT) == WAIT_FAILED)
            goto win32_error;
        while (running && GetTickCount64() - started < 5000 &&
               PeekMessageA(&message, NULL, 0, 0, PM_REMOVE))
        {
            if (message.message == WM_QUIT)
            {
                aborted = TRUE;
                running = FALSE;
                break;
            }
            TranslateMessage(&message);
            DispatchMessageA(&message);
        }
    }
    elapsed = GetTickCount64() - started;
    result = aborted ? 3 : (errors || !nonzero_packets ? 1 : 0);
    goto cleanup;

win32_error:
    printf("ERROR Win32 setup/wait win32=%lu\n", GetLastError());
    ++errors;
cleanup:
    running = FALSE;
    while (hidden_calls)
    {
        ShowCursor(TRUE);
        --hidden_calls;
        ++restored_calls;
    }
    if (clipped && saved_clip && !ClipCursor(&previous_clip))
    {
        printf("ERROR restoring ClipCursor win32=%lu\n", GetLastError());
        clip_restored = FALSE;
        ++errors;
    }
    if (registered)
    {
        device.dwFlags = RIDEV_REMOVE;
        device.hwndTarget = NULL;
        if (!RegisterRawInputDevices(&device, 1, sizeof(device)))
        {
            printf("ERROR removing raw registration win32=%lu\n", GetLastError());
            raw_removed = FALSE;
            ++errors;
        }
    }
    if (probe_window && !DestroyWindow(probe_window))
    {
        printf("ERROR destroying window win32=%lu\n", GetLastError());
        ++errors;
    }
    if (errors) result = 1;
    printf("CLEANUP clip_restored=%d raw_removed=%d cursor_show_calls=%u\n",
           clip_restored, raw_removed, restored_calls);
    printf("SUMMARY relative=%u nonzero=%u absolute=%u moves=%u elapsed_ms=%llu aborted=%d errors=%u\n",
           relative_packets, nonzero_packets, absolute_packets, mouse_moves,
           (unsigned long long)elapsed, aborted, errors);
    return result;
}
