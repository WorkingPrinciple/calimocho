/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#include <stdio.h>
#include <string.h>
#include <time.h>

#if !defined(__APPLE__) || !defined(__x86_64__)
#error This probe must run as Darwin x86_64.
#endif

int main(void)
{
    unsigned char mirrored_peb[512], expected[512];
    void *saved_slot;
    time_t value = 0;
    struct tm *result;
    int changed;

    memset(mirrored_peb, 0xa5, sizeof(mirrored_peb));
    memcpy(expected, mirrored_peb, sizeof(expected));
    __asm__ volatile ("movq %%gs:0x60,%0" : "=r" (saved_slot));
    __asm__ volatile ("movq %0,%%gs:0x60" :: "r" (mirrored_peb));
    result = localtime(&value);
    changed = memcmp(mirrored_peb, expected, sizeof(expected)) != 0;
    __asm__ volatile ("movq %0,%%gs:0x60" :: "r" (saved_slot));
    printf("localtime_nonnull=%d mirrored_peb_changed=%d\n", result != NULL, changed);
    return result && !changed ? 0 : 1;
}
