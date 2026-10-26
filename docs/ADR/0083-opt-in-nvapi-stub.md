# ADR-0083: Opt-in NVAPI stub for the NVIDIA identity

Status: Accepted (REQ-120). Not sufficient on its own; see
[ADR-0084](0084-dxgi-driver-version-front-end.md).
Date: 2026-10-26

## Context

Forza Horizon 6 runs on Calimocho with an opt-in NVIDIA GPU identity
(`D3DM_VENDOR_ID=0x10de`, [ADR-0079](0079-forza-opt-ins-in-the-general-engine.md)).
With the AMD default, D3DMetal crashes it. On start it shows a
"Compatibility Warning" dialog with code FH302:
"Unable to detect graphics driver version. You can continue, but may
experience suboptimal performance or instability."

FH302 is a detection failure, not an old driver. The age check is a
separate code, FH301, whose documented minimum is NVIDIA 596.36.
Patch 0012 already reports driver 32.0.16.1656 (616.56) through the
display Class key and D3DKMT. FH302 stayed.

The executable is encrypted at rest, so we can't read its checks
statically. The DLLs it ships next to it can be read. NVIDIA Streamline
(`sl.interposer.dll`, `sl.common.dll`) logs "Failed to get driver
version from NvAPI!", and Aftermath also loads NVAPI. On an NVIDIA
adapter, the driver version comes from `nvapi64.dll`, which Windows
installs with the NVIDIA driver. Neither Calimocho nor CrossOver ships
one.

The FOSS option is dxvk-nvapi (MIT). It can't work here: during adapter
setup it requires DXVK's `IDXGIVkInteropAdapter`, and Apple's
`dxgi.dll` doesn't have it (`src/nvapi/nvapi_adapter.cpp`, commit
`a90187ff`). Highball's NVAPI stub (GPL-3.0) is 32-bit only and doesn't
report a driver version. So there is no FOSS path, and
[ADR-0017](0017-follow-when-foss-exists-lead-when-only-paid-exists.md)
lets us write the smallest piece that unblocks one.

## Decision

1. `tools/nvapi_stub/` is our own LGPL-2.1+ source for a 64-bit
   `nvapi64.dll`. It is built with mingw-w64, links only kernel32 and
   advapi32 and doesn't use the C runtime. It is reproducible
   (TimeDateStamp 0, the same bytes from any build directory).
2. It answers only identity queries: Initialize, Unload,
   GetErrorMessage, GetInterfaceVersionString,
   SYS_GetDriverAndBranchVersion, GetDisplayDriverVersion,
   EnumPhysicalGPUs, GPU_GetFullName, GPU_GetPCIIdentifiers,
   GPU_GetArchInfo (Ada, AD104), GPU_GetGPUType and
   GetLogicalGPUFromPhysicalGPU. DRS_CreateSession explicitly returns
   `NVAPI_NO_IMPLEMENTATION`, because there is no driver settings
   database. It reads the
   version from the same display Class key `DriverVersion` that patch
   0012 writes, so every query shows one driver. Every other function
   returns `NVAPI_NO_IMPLEMENTATION`, so Reflex, DLSS and Aftermath
   turn themselves off.
3. Unless `D3DM_VENDOR_ID` is `0x10de`, Initialize returns
   `NVAPI_NVIDIA_DEVICE_NOT_FOUND`.
4. It is installed at `lib/calimocho/x86_64-windows/nvapi64.dll`,
   outside `lib/wine`, so wineboot never copies it into a prefix. Only
   the FH6 profile step copies it to `system32\nvapi64.dll`. Wine has
   no builtin `nvapi64`, so that copy loads as a native DLL. Every
   other title is unchanged.
5. For evidence runs it can log each query, either to the Windows path
   in `CALIMOCHO_NVAPI_LOG` or to `C:\calimocho-nvapi.log` when that
   file already exists. Otherwise it writes nothing.

## Consequences

- One run with the stub on the -06 engine (2026-10-26, no rebuild)
  showed which queries FH6 makes: Initialize,
  SYS_GetDriverAndBranchVersion (answered 616.56), EnumPhysicalGPUs
  and GPU_GetArchInfo. It reached the signed-in title screen and quit
  normally. The same run also showed that this prefix carries the
  owner's "Don't show again" for FH302, so it didn't prove anything
  about the dialog. The A/B on a prefix that still shows FH302 settled
  it: FH302 appeared both with and without the stub. FH6 also needs the
  DXGI driver version (ADR-0084).
- FH6's DLSS and Reflex menus stay off, as they are without the stub.
- If a game starts needing more NVAPI, it gets
  `NVAPI_NO_IMPLEMENTATION`, never made-up data.
- `nvapi64.dll` and NVAPI are NVIDIA names, used here only for
  identification. The function IDs and structure layouts come from
  NVIDIA's public MIT-licensed SDK headers. No NVIDIA code is used.
