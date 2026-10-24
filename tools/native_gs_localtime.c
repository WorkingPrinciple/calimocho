/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#include <time.h>

#if !defined(__APPLE__) || !defined(__x86_64__)
#error This interposer is only for the isolated Darwin x86_64 native-GS port.
#endif

/* Darwin localtime's TSD slot overlaps the mirrored Windows PEB pointer. */
static __thread struct tm localtime_buffer;

static struct tm *native_gs_localtime(const time_t *value)
{
    return localtime_r(value, &localtime_buffer);
}

static const struct
{
    const void *replacement;
    const void *original;
} localtime_interpose __attribute__((used, section("__DATA,__interpose"))) =
{
    (const void *)native_gs_localtime, (const void *)localtime
};
