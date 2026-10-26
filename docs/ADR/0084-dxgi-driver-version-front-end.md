# ADR-0084: DXGI front-end for the driver version

Status: Proposed (REQ-120). Needs live proof and review.
Date: 2026-10-26

## Context

[ADR-0083](0083-opt-in-nvapi-stub.md) added an NVAPI stub for Forza
Horizon 6. An A/B on a prefix that still shows FH302 proved that the stub
alone is not enough. FH6 called the stub and got 616.56, but the dialog
"Unable to detect graphics driver version (Code: FH302)" still appeared.

A small probe in the same prefix (2026-10-26) showed where the version is
missing:

- The registry is right: `DriverVersion` 32.0.16.1656, `ProviderName`
  NVIDIA, `MatchingDeviceId` `pci\ven_10de&dev_2786` (patch 0012).
- Apple's `dxgi.dll` returns `S_OK` from
  `IDXGIAdapter::CheckInterfaceSupport`, with the user-mode driver (UMD)
  version 65535.65535.65535.65535. That is the classic Direct3D way to
  read the driver version, and the value means "unknown".

`CheckInterfaceSupport` is implemented inside `D3DMetal.framework`
(`DXGIAdapter::CheckInterfaceSupport`). D3DMetal has no setting for the
UMD version (its `D3DM_*` variables were checked). AGENTS rule 1 and the
GPTK licence say Apple's files ship unmodified.

## Decision

1. `tools/dxgi_umd/` is our own LGPL-2.1+ source for a `dxgi.dll`
   front-end, built like the NVAPI stub (mingw-w64, no C runtime,
   kernel32 and advapi32 only, reproducible).
2. It loads Apple's `dxgi.dll` unchanged by path:
   `CALIMOCHO_DXGI_REAL` when set, otherwise the `dxgi.dll` next to
   `HB_D3D12_REAL`, which the FH6 profile already sets to the engine's
   `lib\wine\x86_64-windows\d3d12.dll`. Wine does not pass
   `WINELOADER` into the Windows environment. Its export name is
   `dxgi_calimocho.dll`, because Wine 11 matches modules by export name
   and wouldn't load Apple's `dxgi.dll` next to another `dxgi.dll`. It
   forwards all seven of Apple's exports.
3. For every factory it creates, and every adapter such a factory
   returns, it makes a private copy of that object's vtable and points the
   object at the copy. In the copy, `CheckInterfaceSupport` and the
   factory calls that return adapters (`EnumAdapters`, `EnumAdapters1`,
   `EnumAdapterByLuid`, `EnumAdapterByGpuPreference`) point to the
   front-end. Every other entry, and the entry before slot 0 (RTTI), stays
   Apple's. The front-end calls Apple's `CheckInterfaceSupport` first,
   keeps its result code and replaces only the version with the registry
   `DriverVersion`. Apple's files, code pages and vtables are never
   written; only the instance's own vtable pointer changes.
4. Unless `D3DM_VENDOR_ID` is set, it changes nothing.
5. It installs at `lib/calimocho/x86_64-windows/dxgi.dll`. Only the FH6
   profile copies it to `system32\dxgi.dll` and sets
   `dxgi=native,builtin` in the prefix's DllOverrides.

## Consequences

- Live, 2026-10-26: in an FH6 prefix with the opt-in identity, a probe
  got `S_OK` and 32.0.16.1656 from `CheckInterfaceSupport` through the
  front-end (Apple alone: 65535.65535.65535.65535). One FH6 run with the
  front-end reached the title screen without FH302 and without input.
  That run is not proof: the same prefix also showed no FH302 without
  the front-end afterwards, and the trace showed FH6 never called
  `CheckInterfaceSupport` there. A clean A/B on a fresh prefix is still
  needed.

- If D3DMetal ever checks an object's vtable pointer, the front-end could
  break that title. The live FH6 run is the check.
- Adapters reached another way (for example `IDXGIDevice::GetAdapter`
  from a D3D11 device) keep Apple's answer. FH6 is a D3D12 title.
- Runtime interposition on Apple objects is a design choice for review,
  even though no Apple bytes are changed. If review rejects it, FH302
  stays (the owner can still choose "Don't show again").
