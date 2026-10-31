#!/usr/bin/env bash
# scripts/build-app.sh — Build Calimocho.app from Swift sources
#
# Phase 2: Creates the .app bundle, compiles Swift sources, bundles
# the Wine engine, and ad-hoc signs everything.
#
# Usage:
#   ./scripts/build-app.sh [--clean]
#
# Output:
#   out/Calimocho.app

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUT_APP="$REPO_ROOT/out/Calimocho.app"
ENGINE_SRC="$REPO_ROOT/out/engine"
SWIFT_SRC="$REPO_ROOT/Calimocho/Sources"
INFO_PLIST="$REPO_ROOT/Calimocho/Info.plist"
ENTITLEMENTS="$REPO_ROOT/Calimocho/Calimocho.entitlements"

# Parse args
CLEAN=false
if [[ "${1:-}" == "--clean" ]]; then
    CLEAN=true
fi

echo "[build-app] Starting Calimocho.app build..."

# Clean if requested
if [[ "$CLEAN" == "true" ]]; then
    echo "[build-app] Cleaning old build..."
    rm -rf "$OUT_APP"
fi

# Verify engine exists
if [[ ! -d "$ENGINE_SRC" ]]; then
    echo "ERROR: Engine not found at $ENGINE_SRC"
    echo "Run ./scripts/build-wine.sh first"
    exit 3
fi

# Create .app bundle structure
echo "[build-app] Creating .app bundle structure..."
mkdir -p "$OUT_APP/Contents/"{MacOS,Resources/Engine,Frameworks}

# Compile Swift sources
echo "[build-app] Compiling Swift sources..."
SWIFT_FILES=(
    "$SWIFT_SRC/CalimochoApp.swift"
    "$SWIFT_SRC/BottleManager.swift"
    "$SWIFT_SRC/SteamLauncher.swift"
    "$SWIFT_SRC/FirstRunWizardWindow.swift"
)

# Use swiftc to compile for macOS 15+, targeting arm64 only for the Swift binary
# (Wine engine itself is x86_64 and runs under Rosetta)
swiftc \
    -target arm64-apple-macos15.0 \
    -O \
    -framework SwiftUI \
    -framework AppKit \
    -framework Foundation \
    "${SWIFT_FILES[@]}" \
    -o "$OUT_APP/Contents/MacOS/Calimocho"

echo "[build-app] Swift binary compiled successfully"

# Copy Info.plist
cp "$INFO_PLIST" "$OUT_APP/Contents/Info.plist"

# Bundle engine (per ARCHITECTURE.md: Contents/Resources/Engine/)
echo "[build-app] Bundling Wine engine..."
rsync -a --delete "$ENGINE_SRC/" "$OUT_APP/Contents/Resources/Engine/"

# Sign the app bundle (Developer ID if present, otherwise ad-hoc)
echo "[build-app] Signing Calimocho.app..."
DEFAULT_DEV_ID="Developer ID Application: Dragos Hont (M62Z4M5EUY)"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
TIMESTAMP_ARG="--timestamp=none"

if [[ -z "$SIGN_IDENTITY" ]]; then
    if security find-identity -v -p codesigning 2>/dev/null | grep -q "$DEFAULT_DEV_ID"; then
        SIGN_IDENTITY="$DEFAULT_DEV_ID"
        TIMESTAMP_ARG="--timestamp"
        echo "[build-app] Signing with detected Apple Developer ID: $SIGN_IDENTITY"
    else
        SIGN_IDENTITY="-"
        echo "[build-app] Signing ad-hoc (-)"
    fi
else
    if [[ "$SIGN_IDENTITY" != "-" ]]; then
        TIMESTAMP_ARG="--timestamp"
    fi
    echo "[build-app] Signing with specified identity: $SIGN_IDENTITY"
fi

codesign \
    --force \
    --deep \
    --sign "$SIGN_IDENTITY" \
    $TIMESTAMP_ARG \
    --options runtime \
    --entitlements "$ENTITLEMENTS" \
    "$OUT_APP"

# Verify signature
codesign --verify "$OUT_APP" 2>&1 | grep -q "valid on disk" || {
    echo "WARNING: Code signature verification had issues"
    codesign --verify --verbose "$OUT_APP" || true
}

echo ""
echo "✓ Calimocho.app built successfully at:"
echo "  $OUT_APP"
echo ""
echo "To test:"
echo "  open $OUT_APP"
echo ""
echo "To install:"
echo "  cp -R $OUT_APP /Applications/"
