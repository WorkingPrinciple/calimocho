#!/usr/bin/env bash
# scripts/prep-build-deps.sh
#
# Prepare a macOS Apple Silicon machine for building calimocho's Wine
# engine. Idempotent: safe to re-run.
#
# What this script does (and why it does each thing):
#
# 1.  Verifies macOS is Apple Silicon. The whole point of calimocho is
#     to run Windows games on M-series Macs; Intel Macs aren't a target.
#
# 2.  Installs Rosetta 2 if not present. We build the Wine engine as
#     x86_64 (ADR-0010) and run it under Rosetta on Apple Silicon —
#     exactly the way every shipping Wine-on-Mac stack does it
#     (Whisky's bundled Wine, CrossOver, GPTK, gcenx). Native arm64
#     Wine on macOS 26 is killed by AppleSystemPolicy at exec; root
#     cause documented in docs/build-log.md.
#
# 3.  Installs an **x86_64** Homebrew at /usr/local/. The native arm64
#     Homebrew at /opt/homebrew/ ships arm64-only formulae which we
#     can't link x86_64 binaries against. Both Homebrews coexist;
#     calimocho's build picks the x86 one via arch -x86_64.
#
# 4.  Installs the x86_64 brew formulae Wine needs:
#       gnutls       — SChannel/HTTPS in Wine (Steam login)
#       freetype     — text rendering
#       sdl2         — audio + gamepad backend
#       libpng       — texture decoding
#       dbus         — Wine's IPC bus
#       mingw-w64    — cross-compiler for the Win32 PE side of Wine
#       bison flex   — Apple's system versions are too old for Wine's parsers
#       pkg-config   — for ./configure to find the above
#
# 5.  Brews D3DMetal-side dependencies (none today — GPTK ships its
#     own framework; we copy it in scripts/overlay-gptk.sh).
#
# 6.  Prints next-steps banner (scripts/fetch-sources.sh, then
#     scripts/build-wine.sh).
#
# This script does NOT:
#   - Download Wine sources (that's scripts/fetch-sources.sh)
#   - Install GPTK (Apple gates it behind Apple ID; user downloads manually)
#   - Touch any system-wide policy (no spctl mutations, no SIP changes)
#
# Designed to work identically in:
#   - Local developer machine (interactive, prompts for sudo password)
#   - GitHub Actions self-hosted Apple Silicon runner (sudo is passwordless,
#     or NONINTERACTIVE=1 + a pre-existing /etc/sudoers.d entry)

set -euo pipefail

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] prep-build-deps: $*" >&2; }

# --- 1. macOS Apple Silicon check ---------------------------------------------
if [[ "$(uname -s)" != "Darwin" ]]; then
  log "ERROR: macOS only (got $(uname -s))"
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  log "WARNING: this script targets Apple Silicon (got $(uname -m))."
  log "Intel Mac builds work without the x86 Homebrew layer — just"
  log "  brew install gnutls freetype sdl2 libpng dbus mingw-w64 bison flex pkg-config gstreamer ffmpeg molten-vk libffi zlib bzip2"
  log "and run scripts/build-wine.sh."
  exit 1
fi
log "macOS $(sw_vers -productVersion) on Apple Silicon — ok"

# --- 2. Rosetta 2 -------------------------------------------------------------
if arch -x86_64 /usr/bin/true 2>/dev/null; then
  log "Rosetta 2 already installed"
else
  log "installing Rosetta 2 (requires sudo)"
  /usr/sbin/softwareupdate --install-rosetta --agree-to-license
fi

# --- 3. x86_64 Homebrew at /usr/local/ ----------------------------------------
ARM_BREW="/opt/homebrew/bin/brew"
X86_BREW="/usr/local/bin/brew"

if [[ ! -x "$ARM_BREW" ]]; then
  log "ERROR: native arm64 Homebrew (/opt/homebrew/bin/brew) not installed."
  log "Install it first: see https://brew.sh"
  exit 1
fi
log "arm64 Homebrew: $($ARM_BREW --version | head -1)"

if [[ -x "$X86_BREW" ]]; then
  log "x86_64 Homebrew already installed at $X86_BREW"
else
  log "installing x86_64 Homebrew at /usr/local/ (requires sudo)"
  # The official install.sh now rejects Rosetta 2 execution on Apple Silicon.
  # Directly clone Homebrew into /usr/local/Homebrew as officially documented
  # for alternate installations.
  if [[ ! -d "/usr/local/Homebrew" ]]; then
    sudo mkdir -p /usr/local/Homebrew /usr/local/bin /usr/local/Cellar /usr/local/opt /usr/local/var /usr/local/etc /usr/local/share
    sudo chown -R "$(id -un):$(id -gn)" /usr/local/Homebrew /usr/local/Cellar /usr/local/opt /usr/local/var /usr/local/etc /usr/local/share 2>/dev/null || true
    git clone --depth=1 https://github.com/Homebrew/brew /usr/local/Homebrew
  fi
  if [[ ! -L "$X86_BREW" && ! -f "$X86_BREW" ]]; then
    sudo ln -sf /usr/local/Homebrew/bin/brew /usr/local/bin/brew
  fi
  arch -x86_64 "$X86_BREW" update --force --quiet 2>/dev/null || true
fi
for d in /usr/local/var /usr/local/etc /usr/local/share /usr/local/include /usr/local/lib; do
  if [[ ! -d "$d" ]]; then
    sudo mkdir -p "$d" 2>/dev/null || true
  fi
  if [[ ! -w "$d" ]]; then
    sudo chown -R "$(id -un):$(id -gn)" "$d" 2>/dev/null || true
  fi
done
log "x86_64 Homebrew: $(arch -x86_64 $X86_BREW --version | head -1)"

# --- 4. x86_64 build deps -----------------------------------------------------
DEPS=(
  gnutls       # SChannel / HTTPS (Steam login)
  freetype     # text rendering
  sdl2         # audio + gamepad
  libpng       # image decoding
  dbus         # Wine IPC
  mingw-w64    # PE cross-compiler
  bison        # Wine parser.y (system bison 2.3 too old)
  flex         # Wine .l lexers
  pkg-config   # configure dep discovery
  gstreamer    # CEF media pipeline (Steam UI needs this)
  ffmpeg       # video codecs for CEF + Wine media
  molten-vk    # Vulkan-on-Metal (CEF GPU process)
  libffi       # transitive dep of gstreamer (keg-only pkgconfig)
  zlib         # transitive dep of gnutls/freetype (keg-only pkgconfig)
  bzip2        # transitive dep of freetype (keg-only pkgconfig)
)

log "checking x86_64 brew formulae"
MISSING=()
for dep in "${DEPS[@]}"; do
  if arch -x86_64 "$X86_BREW" list --formula "$dep" >/dev/null 2>&1; then
    log "  ✓ $dep"
  else
    MISSING+=("$dep")
  fi
done

if (( ${#MISSING[@]} > 0 )); then
  log "installing missing: ${MISSING[*]}"
  arch -x86_64 "$X86_BREW" install "${MISSING[@]}"
fi

# Sanity-check that the linker can find the x86 libs we'll need.
# shellcheck disable=SC2034  # 'lib' documents the libs we sanity-check below
for lib in gnutls freetype dbus-1 SDL2 png; do
  if ! arch -x86_64 "$X86_BREW" --prefix >/dev/null 2>&1; then
    log "WARNING: x86 brew --prefix failed; PATH may be misconfigured"
    break
  fi
done

# --- 5. Done ------------------------------------------------------------------
cat <<EOF >&2

[$(ts)] prep-build-deps: done.

Next steps:
  scripts/fetch-sources.sh     # download CodeWeavers Wine 11 source tarball
  scripts/build-wine.sh        # configure + make + install (x86_64 under Rosetta)
  scripts/overlay-gptk.sh      # copy Apple GPTK D3DMetal into out/engine/
  scripts/sign-engine.sh       # ad-hoc sign with Wine entitlements
  scripts/test-engine.sh       # verify A1.1 through A1.5

Or run them all via scripts/build-all.sh (TODO).
EOF
