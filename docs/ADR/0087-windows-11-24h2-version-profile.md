# ADR-0087: A Windows 11 24H2 version profile for new title prefixes

Status: Proposed (source and unit tests done; game A/B pending).
Requirement: REQ-155 (owner decision COR-324).

## Context

Wine 11.20 knows two Windows 11 era versions in its tables: `win10`
(build 19045, the default) and `win11` (build 22000, the first Windows 11
release). A new prefix reports Windows 10 19045. Some current games and
their launchers ask for a newer Windows, and the owner asked: "why dont we
use w 11 26100 for all games ?" and then approved it ("its ok").

Wine keeps the Windows version in two places that must agree:

1. ntdll's version table. It is used when a prefix names a version
   (`HKCU\Software\Wine` `Version`, or a per-app `AppDefaults` key).
   Otherwise ntdll reads the version from the registry below.
2. The registry under `HKLM\Software\Microsoft\Windows NT\CurrentVersion`
   (`CurrentBuild`, `CurrentBuildNumber`, `UBR`, `ProductName` and so on).
   `wine.inf` writes Windows 10 values there when a prefix is created, and
   `winecfg /v <version>` rewrites them from winecfg's own table.

Writing a few registry values after the fact would leave these two out of
step, so a game could get 26100 from one API and 19045 from another.

## Decision

Calimocho patch 0019 adds a `win11-24h2` profile to both tables:

- ntdll: Windows 10.0 build 26100, workstation, no service pack. This
  table is only used when a prefix or program names the version (the
  `Version` value or an `AppDefaults` entry). With the `winecfg /v` route
  below, ntdll reads the version from the registry values instead, so
  both routes report 10.0.26100 from `RtlGetVersion` and the PEB.
- winecfg: the same version, plus the registry values real Windows 11
  24H2 has: `CurrentBuild` and `CurrentBuildNumber` "26100", `UBR` 4652,
  `DisplayVersion` "24H2", `ReleaseId` "2009", and `ProductName`
  "Windows 10 Pro". Real Windows 11 keeps that Windows 10 product name;
  programs tell Windows 11 apart by build number 22000 or later. When a
  prefix switches to another profile, winecfg removes `DisplayVersion` and
  `ReleaseId` again.

The engine default does not change. `wine.inf` still writes Windows 10, so
existing prefixes stay as they are, even after an engine update. A new
per-title prefix gets the profile by running Wine's own tool once after
`wineboot`:

```bash
wine winecfg /v win11-24h2
```

On an engine without the profile, this exits with status 1 and changes
nothing, so the caller can refuse instead of silently getting 19045. The
CLI (COR-318, backend lane) uses this route and checks
`CurrentBuildNumber` and `DisplayVersion` afterwards.

`tests/wine/test_windows_version_profile.py` compiles the real ntdll and
winecfg tables and winecfg's registry writer from a Wine source tree. It
fails on unpatched Wine 11.20 and passes with the series applied.

As on Windows, `GetVersionEx` gives a program without a Windows 10/11
compatibility manifest version 6.2 build 9200. That is expected, not a
defect, and the A/B does not count it as one. The A/B evidence uses a
small probe that calls `RtlGetVersion` inside the test prefix.

This follows AGENTS rule 4 ("we follow when a FOSS path exists"): it uses
Wine's existing version-profile mechanism and adds a newer Windows build
to it, by owner decision COR-324. It adds no CrossOver-only behaviour.

The profile only changes values under `Windows NT\CurrentVersion`. It
never writes `ProgramFilesDir`, `CommonFilesDir` or the `W6432` values
under `Windows\CurrentVersion`; `wine.inf` writes those as `REG_SZ`. A
prefix where they showed up as `REG_EXPAND_SZ` `%SystemDrive%\...` (REQ-140
evidence) was one whose 64-bit `wine.inf` install had not finished. Its
native `Windows\CurrentVersion` key held only shell32's lazy defaults
(4 of 9 values), while four prefixes the CLI created with this profile
have the normal `REG_SZ` values. The unit test asserts the profile writer
does not touch them.

## Consequences

- Before this becomes the default for new title prefixes, it is A/B
  tested on copies of the FH6, No Man's Sky and Witcher prefixes (never
  the real save prefixes), and smoke tested on the REQ-145 game set.
- A per-game choice (REQ-156) can pick `win10`, `win11` or `win11-24h2`
  through the same `winecfg /v` call.
- If a game breaks on 26100, its prefix can go back with
  `winecfg /v win10`; no data in the prefix depends on the version.
- UBR 4652 is a fixed update level. It is not kept in step with
  Microsoft's monthly updates.
