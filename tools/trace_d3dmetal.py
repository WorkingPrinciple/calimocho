"""Instrument the Wine-owned D3DMetal boundary without touching Apple code."""

import argparse
from pathlib import Path
import re

from port_d3dmetal import replace_once


def trace_callbacks(text, expected=24):
    pattern = re.compile(
        r"^(static [^\n]+?\b(my_\w+)\([^\n]*\)\n\{\n)(.*?)(^\})",
        re.MULTILINE | re.DOTALL,
    )
    names = []

    def instrument(match):
        header, name, body, end = match.groups()
        names.append(name)
        if "boundary enter" in body:
            raise ValueError(f"Already instrumented: {name}")
        body = replace_once(
            body, '    TRACE("',
            f'    TRACE("boundary enter {name}\\n");\n    TRACE("',
        ) if body.count('    TRACE("') == 1 else body
        if f"boundary enter {name}" not in body:
            raise ValueError(f"Missing unique entry trace: {name}")
        is_void = header.startswith("static void ")

        def returned(result):
            expression = result.group(1).strip()
            if is_void:
                call = f"{expression}; " if expression else ""
                return (
                    f'{{ {call}TRACE("boundary leave {name} void\\n"); return; }}'
                )
            if not expression:
                raise ValueError(f"Missing return value: {name}")
            return (
                f"{{ __typeof__({expression}) boundary_result = ({expression}); "
                f'TRACE("boundary leave {name} result=%#lx\\n", '
                "(unsigned long)(UINT_PTR)boundary_result); return boundary_result; }"
            )

        body, returns = re.subn(r"\breturn\b\s*([^;]*);", returned, body)
        if is_void:
            body += f'    TRACE("boundary leave {name} void\\n");\n'
        elif not returns:
            raise ValueError(f"No return in callback: {name}")
        return header + body + end

    traced = pattern.sub(instrument, text)
    if len(names) != expected or len(set(names)) != expected:
        raise ValueError(f"Expected {expected} unique callbacks, found {names}")
    return traced


def trace_thread_start(text):
    text = replace_once(
        text,
        "WINE_DECLARE_DEBUG_CHANNEL(seh);\n",
        "WINE_DECLARE_DEBUG_CHANNEL(seh);\nWINE_DECLARE_DEBUG_CHANNEL(macdrv_d3dmtl);\n",
    )
    text = replace_once(
        text,
        "    assert( thread_data->frame_size == frame_size );",
        '    TRACE_(macdrv_d3dmtl)("boundary enter signal_start_thread/init_syscall_frame '
        'entry=%p arg=%p teb=%p data=%p frame=%p pthread_teb=%#lx\\n",\n'
        "                            entry, arg, teb, data, frame, "
        "(unsigned long)thread_data->pthread_teb);\n"
        "    assert( thread_data->frame_size == frame_size );",
    )
    return replace_once(
        text,
        "    pthread_sigmask( SIG_UNBLOCK, &server_block_set, NULL );\n}\n\n\n"
        "/***********************************************************************\n"
        " *           signal_start_thread",
        '    TRACE_(macdrv_d3dmtl)("boundary handoff signal_start_thread '
        'entry=%p arg=%p teb=%p pthread_teb=%#lx frame=%p rip=%#lx rcx=%#lx rsp=%#lx\\n",\n'
        "                            entry, arg, teb, (unsigned long)thread_data->pthread_teb,\n"
        "                            frame, (unsigned long)frame->rip, "
        "(unsigned long)frame->rcx, (unsigned long)frame->rsp);\n"
        "    pthread_sigmask( SIG_UNBLOCK, &server_block_set, NULL );\n}\n\n\n"
        "/***********************************************************************\n"
        " *           signal_start_thread",
    )


def instrument(source):
    driver = source / "dlls/winemac.drv/d3dmetal.c"
    thread = source / "dlls/ntdll/unix/signal_x86_64.c"
    changes = {
        driver: trace_callbacks(driver.read_text()),
        thread: trace_thread_start(thread.read_text()),
    }
    for path, content in changes.items():
        path.write_text(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    instrument(parser.parse_args().source)
