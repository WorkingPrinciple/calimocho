"""Add read-only opcode diagnostics to an isolated Wine source tree (REQ-108)."""

import argparse
from pathlib import Path


ANCHOR = """    save_context( data, &context, sigcontext );

    switch(TRAP_sig(sigcontext))
    {
    case TRAP_x86_OFLOW:"""
DIAGNOSTIC = """    save_context( data, &context, sigcontext );

    if (TRAP_sig(sigcontext) == TRAP_x86_PRIVINFLT && TRACE_ON(seh))
    {
        BYTE bytes[16];
        char hex[sizeof(bytes) * 3 + 1];
        SIZE_T count, i;

        count = virtual_uninterrupted_read_memory( (const void *)context.c.Rip, bytes, sizeof(bytes) );
        hex[0] = 0;
        for (i = 0; i < count; i++) snprintf( hex + i * 3, sizeof(hex) - i * 3, "%02x ", bytes[i] );
        TRACE_(seh)( "FH6_DIAG fault rip=%#lx bytes_read=%lu bytes=%s cs=%04x rsp=%#lx\\n",
                     (long)context.c.Rip, (unsigned long)count, hex,
                     context.c.SegCs, (long)context.c.Rsp );
    }

    switch(TRAP_sig(sigcontext))
    {
    case TRAP_x86_OFLOW:"""


def instrument(text):
    if "FH6_DIAG" in text:
        raise ValueError("Source already contains FH6 diagnostics")
    if text.count(ANCHOR) != 1:
        raise ValueError("Expected exactly one invalid-opcode handler anchor")
    return text.replace(ANCHOR, DIAGNOSTIC)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    target = args.source / "dlls/ntdll/unix/signal_x86_64.c"
    target.write_text(instrument(target.read_text()))
