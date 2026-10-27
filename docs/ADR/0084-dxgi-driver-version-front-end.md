# ADR-0084: DXGI front-end for the driver version

Status: Rejected for FH6 (REQ-120); see Result.
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

## Result (2026-10-27): not effective for FH302

An A/B on two fresh clones of the same FH6 prefix, with no automatic
dismissal and the dialog detected by window title, settled it. The
control showed "Forza Horizon 6 Compatibility Warning". The clone with
both the NVAPI stub and the DXGI front-end showed it too. FH6 called
the NVAPI stub (driver 616.56) but never called
`IDXGIAdapter::CheckInterfaceSupport`. FH302 comes from another query,
perhaps SetupAPI, WMI or D3DKMT. The components stay in the source tree
as tested, reusable shims, but the FH6 profile doesn't install them.

A trace of the query FH6 actually uses was not possible. The Ode CLI
accepts FH6 only with its reviewed title recipe, which pins
`WINEDEBUG=-all`, and the executable is encrypted at rest, so it can't
be started outside the CLI. The CLI's popup record of the A/B run also
shows the FH302 dialog closing by itself after a few seconds with no
button pressed. The title screen follows either way, so the warning is
cosmetic. REQ-120 is parked with this evidence.

L12's diagnostic trace (2026-10-27, run `25ef635a`, channels including
`+setupapi,+wbemprox,+d3dkmt,+plugplay`) gives negative evidence. Between
the executable starting and the FH302 dialog, FH6 made no WMI query, no
SetupAPI device-property call and no D3DKMT driver-version query. The
only D3DKMT calls came from Streamline: `KMTQAITYPE_WDDM_2_7_CAPS` (70,
not handled by Wine) and two NGX registry lookups. Two paths were not
traced: registry reads (`+reg`) and version resources. The run asked for
`+version`, but Wine's channel is `ver`. The remaining lead is the
classic one: the display Class key has no `UserModeDriverName`, so a
game that reads the version resource of the user-mode driver DLL finds
none.

A second trace (L12, run `e5cb3b80`, with `+reg,+ver`) found what FH6
reads just before the dialog. It opens `HKLM\SOFTWARE\Microsoft\DirectX`,
enumerates the first adapter subkey and reads its `AdapterLuid` and
`DriverVersion` (both as QWORD). A probe in an FH6 prefix with the FH6
environment found everything consistent:

- DXGI adapter LUID `0x3f7`;
- D3D12 device `GetAdapterLuid` `0x3f7`;
- registry `AdapterLuid` `0x3f7`, `DriverVersion` 32.0.16.1656,
  `VendorId` `10de`, `DeviceId` `2786`.

So a LUID mismatch is ruled out too. The trace doesn't show the data
FH6 got back, so the next step would be a relay trace of `RegGetValueW`
in the game process. REQ-120 stays parked.
