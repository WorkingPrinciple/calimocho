# ADR-0076: Provide the eight-byte theme color preference pair

## Context

Cell042 ran once and completed the registrar RELEASE response. The app
entered FrameworkView.Initialize, then exited with `0x80000100`, without
a window. Its complete capture contains Wine's DelayLoadFailureHook
fingerprint and two exception parameters naming the uxtheme API set and
`GetUserColorPreference`. Those parameters are strings, not XAML code.
The filter entry alone is not proof of termination cause. The matching
Wine loader failure, missing PE export and exact target exit identify
the missing runtime behavior.

The exact XAML input has SHA-256
`16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899`.
Its helper initializes an eight-byte local, calls GetUserColorPreference
with forceReload=0, then calls GetColorFromPreference without checking
the first HRESULT. The second call uses ignoreHighContrast=0 and
cacheMode=1. Callers request accent shades 1 through 7 and application
background 0xd2. Native code was read for understanding only.

The public references resolve the ABI and numeric roles:

- [m417z's header and implementation][preference] at commit
  `61020ff19d42467253620251279cd35409e0d08f` declare two COLORREFs,
  an HRESULT return, and use the second color as the accent.
- [Pete Batard's measured color table][roles] at commit
  `969017691b91982be986ae040f90dd2ec62166b4` distinguishes the
  named-color enumeration index from the numeric color type. It reports
  application text=0, accent light3/light2/light1=1/2/3, accent=4,
  accent dark1/dark2/dark3=5/6/7, application background=0xd2,
  light/dark background=0xd3/0xd4 and light/dark text=0xd5/0xd6.
  These values match the XAML caller arguments.
- [The public preference example][flags] names high-contrast modes
  0 (cached value) and 1 (refresh). Its three-DWORD preference declaration
  conflicts with the exact caller and the two-COLORREF reference, so
  that declaration is not used.

These references are not proof of the entire native output or failure
contract. No native Windows differential is available.

## Decision

Add only the named GetUserColorPreference and GetColorFromPreference
exports to source-built Wine uxtheme. Leave existing immersive APIs and
theme rendering unchanged. Use the already present Wine mechanisms:
Explorer's AccentPalette, the same default palette as
windows.ui/uisettings.c, ShouldAppsUseDarkMode and system colors.

GetUserColorPreference initializes exactly eight bytes before querying
the palette. color2 is the current accent. color1 is Wine's desktop
background system color; the native derivation of that field is not
measured. A missing palette uses Wine's existing default, without writing
the registry. Other registry failures return an HRESULT and leave both
output fields initialized to system colors.

GetColorFromPreference returns opaque ABGR, matching the caller's
red/blue conversion and COLORREF representation. It implements the
measured text/background roles and the current palette's accent shades.
Accent itself uses the supplied preference. Shades for a preference
that does not match the current palette fail explicitly; there is no
invented native accent-generation algorithm. High contrast uses current
system window, text and highlight colors unless the caller asks to
ignore it. Both admitted cache modes query current settings. There is
no persistent preference or high-contrast cache.

Null input, unsupported role/cache mode, malformed palette, failed
high-contrast query and unsupported custom shades report errors.
Color-returning failures use CLR_INVALID, SetLastError and a fixed
diagnostic reason. These failure conventions are a scoped Wine policy,
not measured native parity.

Build uxtheme explicitly and stage that exact PE. Bind its source,
export specification, original implementation payload, built/staged
hashes and direct AMD64 named exports into cell043. Preserve all
existing owner, observer, registrar, setup and fresh-prefix boundaries.
No native XAML patch or runtime replay is part of this source slice.

## Consequences

Host tests cover the exact eight-byte write with guard words, all
admitted roles, opaque byte order, force reload, palette changes,
high-contrast flags/cache modes and explicit failure paths. PE
qualification rejects missing/forwarded exports and a stale staged DLL.
This establishes a source candidate, not native theme fidelity, a
rendered window or successful Xbox activation.

The coordinator must validate the new receipt and admit a single fresh
cell043 run. Cell042 remains sealed and the FH6 baseline is unchanged.

[preference]: https://github.com/m417z/Windows-10-Color-Control/blob/61020ff19d42467253620251279cd35409e0d08f/WindowsThemeColorApi.cpp
[roles]: https://raw.githubusercontent.com/pbatard/list-immersive-colors/969017691b91982be986ae040f90dd2ec62166b4/list-immersive-colors.txt
[flags]: https://gist.github.com/smourier/d9de36c49e19aa9923d5143965057405
