/*
 * Calimocho DXGI front-end: driver version parsing (REQ-120)
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * Plain C with no Windows types, so tests can compile it on the host.
 */

#ifndef CALIMOCHO_UMD_VERSION_H
#define CALIMOCHO_UMD_VERSION_H

/* Parse a Windows driver version "a.b.c.d" (each 0..65535). Returns 1 on success. */
static int calimocho_parse_driver_version(const char *text, unsigned int parts[4])
{
    unsigned int index = 0;
    int digit = 0;
    parts[0] = parts[1] = parts[2] = parts[3] = 0;
    for (; *text; text++)
    {
        if (*text >= '0' && *text <= '9')
        {
            parts[index] = parts[index] * 10 + (unsigned int)(*text - '0');
            if (parts[index] > 65535) return 0;
            digit = 1;
        }
        else if (*text == '.' && digit && index < 3) { index++; digit = 0; }
        else return 0;
    }
    return index == 3 && digit;
}

#endif
