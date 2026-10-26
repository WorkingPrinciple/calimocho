/*
 * Calimocho NVAPI stub: driver version parsing (REQ-120)
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

#ifndef CALIMOCHO_NVAPI_VERSION_H
#define CALIMOCHO_NVAPI_VERSION_H

/* NVIDIA's Windows version a.b.c.d maps to the NVAPI number (c * 10000 + d) % 100000,
 * so 32.0.16.1656 is 61656 (616.56). Returns 0 when the string does not parse. */
static unsigned int calimocho_nvapi_version_from_string(const char *text)
{
    unsigned int parts[4] = {0, 0, 0, 0};
    unsigned int index = 0;
    int digit = 0;
    for (; *text; text++)
    {
        if (*text >= '0' && *text <= '9')
        {
            parts[index] = parts[index] * 10 + (unsigned int)(*text - '0');
            if (parts[index] > 99999) return 0;
            digit = 1;
        }
        else if (*text == '.' && digit && index < 3) { index++; digit = 0; }
        else return 0;
    }
    if (index != 3 || !digit) return 0;
    return (parts[2] * 10000 + parts[3]) % 100000;
}

#endif
