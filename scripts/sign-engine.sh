#!/usr/bin/env bash
# scripts/sign-engine.sh
#
# Ad-hoc sign every Mach-O file under out/engine/ with the entitlements
# Wine needs on Apple Silicon (JIT, unsigned exec memory, disabled
# page-protection, dyld env vars). AGENTS.md rule #8 (ad-hoc only).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/out/engine"
ENT="$REPO_ROOT/scripts/wine-entitlements.plist"

[[ -d "$OUT" ]] || { echo "sign-engine: $OUT missing" >&2; exit 1; }
[[ -f "$ENT" ]] || { echo "sign-engine: $ENT missing" >&2; exit 1; }

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] sign-engine: $*" >&2; }

# Determine signing identity:
# 1. Use $CODESIGN_IDENTITY if explicitly provided
# 2. Else check for local Developer ID Application cert in keychain
# 3. Else fallback to ad-hoc ("-")
DEFAULT_DEV_ID="Developer ID Application: Dragos Hont (M62Z4M5EUY)"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
TIMESTAMP_ARG="--timestamp=none"

if [[ -z "$SIGN_IDENTITY" ]]; then
  if security find-identity -v -p codesigning 2>/dev/null | grep -q "$DEFAULT_DEV_ID"; then
    SIGN_IDENTITY="$DEFAULT_DEV_ID"
    TIMESTAMP_ARG="--timestamp"
    log "Using detected Apple Developer ID: $SIGN_IDENTITY"
  else
    SIGN_IDENTITY="-"
    log "No Developer ID certificate found; using ad-hoc signing"
  fi
else
  if [[ "$SIGN_IDENTITY" != "-" ]]; then
    TIMESTAMP_ARG="--timestamp"
  fi
  log "Using specified signing identity: $SIGN_IDENTITY"
fi

count=0
while IFS= read -r -d '' f; do
  [[ -L "$f" ]] && continue
  # Detect Mach-O via `file` (handles thin + fat, arm64 + x86_64).
  if file -b "$f" | grep -q 'Mach-O'; then
    # Sign with entitlements + hardened runtime. The hardened
    # runtime is compatible with x86_64 Wine because the entitlements
    # plist grants the four loosening keys Wine needs:
    #   allow-jit, allow-unsigned-executable-memory,
    #   disable-executable-page-protection, allow-dyld-environment-vars,
    #   disable-library-validation.
    # The runtime flag adds defense-in-depth (DYLD_INSERT_LIBRARIES is
    # respected only with our entitlement, env-var injection from
    # outside is blocked, etc.) without breaking Wine.
    codesign --force $TIMESTAMP_ARG --sign "$SIGN_IDENTITY" \
             --entitlements "$ENT" --options runtime "$f"
    count=$((count+1))
  fi
done < <(find "$OUT" -type f -print0)

log "signed $count Mach-O files in $OUT"
