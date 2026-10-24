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

int main(int argc, char **argv)
{
    unsigned char mirrored_peb[512], expected[512];
    void *saved_slot, *observed_slot;
    time_t value = 0;
    struct tm calendar, returned;
    char buffer[128];
    const char *function = argc == 2 ? argv[1] : "localtime";
    int changed, slot_changed, succeeded = 0;

    if (!localtime_r(&value, &calendar)) return 2;

    memset(mirrored_peb, 0xa5, sizeof(mirrored_peb));
    memcpy(expected, mirrored_peb, sizeof(expected));
    __asm__ volatile ("movq %%gs:0x60,%0" : "=r" (saved_slot));
    __asm__ volatile ("movq %0,%%gs:0x60" :: "r" (mirrored_peb));
    if (!strcmp(function, "localtime")) succeeded = localtime(&value) != NULL;
    else if (!strcmp(function, "ctime")) succeeded = ctime(&value) != NULL;
    else if (!strcmp(function, "gmtime")) succeeded = gmtime(&value) != NULL;
    else if (!strcmp(function, "localtime_r")) succeeded = localtime_r(&value, &returned) != NULL;
    else if (!strcmp(function, "gmtime_r")) succeeded = gmtime_r(&value, &returned) != NULL;
    else if (!strcmp(function, "ctime_r")) succeeded = ctime_r(&value, buffer) != NULL;
    else if (!strcmp(function, "asctime")) succeeded = asctime(&calendar) != NULL;
    else if (!strcmp(function, "asctime_r")) succeeded = asctime_r(&calendar, buffer) != NULL;
    else if (!strcmp(function, "mktime")) succeeded = mktime(&calendar) == value;
    else if (!strcmp(function, "timegm"))
    {
        gmtime_r(&value, &calendar);
        succeeded = timegm(&calendar) == value;
    }
    else if (!strcmp(function, "strftime"))
        succeeded = strftime(buffer, sizeof(buffer), "%c %s %Z %z", &calendar) != 0;
    changed = memcmp(mirrored_peb, expected, sizeof(expected)) != 0;
    __asm__ volatile ("movq %%gs:0x60,%0" : "=r" (observed_slot));
    slot_changed = observed_slot != mirrored_peb;
    __asm__ volatile ("movq %0,%%gs:0x60" :: "r" (saved_slot));
    printf("function=%s succeeded=%d mirrored_peb_changed=%d slot_changed=%d\n",
           function, succeeded, changed, slot_changed);
    return succeeded && !changed && !slot_changed ? 0 : 1;
}
