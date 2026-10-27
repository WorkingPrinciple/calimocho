# monodump (diagnostic only)

Takes a managed-stack snapshot of a running Unity Mono game under Wine
(REQ-132, [ADR-0086](../../docs/ADR/0086-dredge-and-rv-there-yet-root-causes.md)).
It is never part of an engine build, a release recipe or a title profile.

```bash
x86_64-w64-mingw32-gcc -shared -O2 -Wall -Wextra -Werror -o monodump.dll monodump_dll.c
x86_64-w64-mingw32-gcc -municode -O2 -Wall -Wextra -Werror -o monodump.exe monodump_exe.c
# copy both into the prefix's C:\, then, with the same WINEPREFIX:
wine 'C:\monodump.exe' GAME.exe 'C:\monodump.dll'
# report: C:\monodump.txt (or %MONODUMP_OUT%)
```

Each thread is suspended only long enough to copy its registers and up
to 64 KiB of stack. Addresses are resolved after the thread resumes,
with the game's own `mono_jit_info_table_find` and
`mono_method_full_name`. Stack slots that resolve to JIT code are
candidate frames, not an exact unwind. The report can contain game
data, so treat it as local evidence.
