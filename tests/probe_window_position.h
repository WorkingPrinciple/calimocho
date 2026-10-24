/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

static int probe_window_position(int *x, int *y)
{
    const char *values[] = {getenv("CALIMOCHO_PROBE_X"), getenv("CALIMOCHO_PROBE_Y")};
    int *outputs[] = {x, y};
    *x = *y = 80;
    if (!values[0] && !values[1]) return 1;
    if (!values[0] || !values[1])
    {
        printf("ERROR both probe coordinates are required\n");
        return 0;
    }
    for (int i = 0; i < 2; ++i)
    {
        char *end;
        long value;
        errno = 0;
        value = strtol(values[i], &end, 10);
        if (errno || !*values[i] || *end || value < -32768 || value > 32767)
        {
            printf("ERROR invalid probe coordinate\n");
            return 0;
        }
        *outputs[i] = (int)value;
    }
    printf("placement x=%d y=%d\n", *x, *y);
    return 1;
}
