/*
 * trapbench: what a trapped instruction costs a Windows program under Calimocho (REQ-129).
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * Forza Horizon 6's copy protection runs a job about every 1.1 s that
 * executes about 2,000 instructions which trap on purpose, and its
 * vectored handler emulates each one (Highball, Apple FB25100017).
 * This program does the same round trip through Wine: ud2 or int3,
 * a vectored exception handler that steps over it, and NtContinue.
 * It also times a write into a 4 KB page holding code that already
 * ran. Compare with Highball's sigbench (the same trap without Wine)
 * to get Wine's share on our engine.
 *
 * Usage: trapbench.exe [count] [busy-threads]
 * Prints one line per test: name, count, microseconds per event.
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

static volatile LONG stop_busy;
static volatile LONG64 handled;

static LONG CALLBACK handler(EXCEPTION_POINTERS *info)
{
    DWORD code = info->ExceptionRecord->ExceptionCode;
    if (code == EXCEPTION_ILLEGAL_INSTRUCTION) { info->ContextRecord->Rip += 2; handled++; return EXCEPTION_CONTINUE_EXECUTION; }
    if (code == EXCEPTION_BREAKPOINT) { info->ContextRecord->Rip += 1; handled++; return EXCEPTION_CONTINUE_EXECUTION; }
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI busy(void *arg)
{
    volatile unsigned long long x = 0;
    (void)arg;
    while (!stop_busy) x += 1;
    return (DWORD)(x & 1);
}

static double now_us(void)
{
    static LARGE_INTEGER frequency;
    LARGE_INTEGER counter;
    if (!frequency.QuadPart) QueryPerformanceFrequency( &frequency );
    QueryPerformanceCounter( &counter );
    return (double)counter.QuadPart * 1e6 / (double)frequency.QuadPart;
}

static void report(const char *name, long count, double start, double end)
{
    printf( "%-22s %8ld  %9.2f us\n", name, count, (end - start) / count );
    fflush( stdout );
}

int main(int argc, char **argv)
{
    long count = argc > 1 ? atol( argv[1] ) : 20000, i;
    int threads = argc > 2 ? atoi( argv[2] ) : 0, t;
    HANDLE workers[64];
    unsigned char *code;
    DWORD old;
    double start;
    typedef int (*fn)(void);
    /* mov eax, 1; ret, followed by data in the same 4 KB page */
    static const unsigned char body[] = {0xb8, 0x01, 0x00, 0x00, 0x00, 0xc3};

    if (count <= 0 || threads < 0 || threads > 64) { fprintf( stderr, "usage: trapbench [count] [threads<=64]\n" ); return 2; }
    AddVectoredExceptionHandler( 1, handler );
    for (t = 0; t < threads; t++) workers[t] = CreateThread( NULL, 0, busy, NULL, 0, NULL );
    printf( "trapbench count=%ld busy_threads=%d\n", count, threads );

    start = now_us();
    for (i = 0; i < count; i++) __asm__ volatile ("ud2");
    report( "ud2 via VEH", count, start, now_us() );

    start = now_us();
    for (i = 0; i < count; i++) __asm__ volatile ("int3");
    report( "int3 via VEH", count, start, now_us() );

    code = VirtualAlloc( NULL, 0x2000, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE );
    if (!code) { fprintf( stderr, "VirtualAlloc failed\n" ); return 1; }
    memcpy( code, body, sizeof(body) );
    ((fn)code)();
    start = now_us();
    for (i = 0; i < count; i++) { code[0x800] = (unsigned char)i; ((fn)code)(); }
    report( "write same 4K + call", count, start, now_us() );
    start = now_us();
    for (i = 0; i < count; i++) { code[0x1800] = (unsigned char)i; ((fn)code)(); }
    report( "write other 4K + call", count, start, now_us() );
    VirtualProtect( code, 0x2000, PAGE_EXECUTE_READ, &old );

    stop_busy = 1;
    for (t = 0; t < threads; t++) { WaitForSingleObject( workers[t], INFINITE ); CloseHandle( workers[t] ); }
    printf( "handled=%lld expected=%ld\n", (long long)handled, 2 * count );
    return handled == 2 * count ? 0 : 1;
}
