#!/usr/bin/env bash
# ==============================================================================
# Samsung Galaxy A21s (SM-A217F) — pmaports & Device Setup
# Vibe coded with Google Antigravity
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--device" ]]; then
    TARGET_IP="${2:-172.16.42.1}"
    exec "$SCRIPT_DIR/deploy-to-device.sh" "$TARGET_IP"
fi

PMAPORTS_DIR="${1:-$HOME/.local/var/pmbootstrap/cache_git/pmaports}"

if [[ ! -d "$PMAPORTS_DIR" ]]; then
    echo "ERROR: pmaports directory not found at $PMAPORTS_DIR"
    echo ""
    echo "Usage:"
    echo "  $0 [/path/to/pmaports]     # Copy packages into pmaports"
    echo "  $0 --device [device-ip]    # Deploy fixes directly to phone via SSH"
    exit 1
fi

DEST_DIR="$PMAPORTS_DIR/device/testing"
mkdir -p "$DEST_DIR"

echo "==> Installing device-samsung-a21s to $DEST_DIR/device-samsung-a21s..."
rm -rf "$DEST_DIR/device-samsung-a21s"
cp -r "$SCRIPT_DIR/device-samsung-a21s" "$DEST_DIR/"

if [[ -d "$SCRIPT_DIR/linux-samsung-a21s" ]]; then
    echo "==> Installing linux-samsung-a21s to $DEST_DIR/linux-samsung-a21s..."
    rm -rf "$DEST_DIR/linux-samsung-a21s"
    cp -r "$SCRIPT_DIR/linux-samsung-a21s" "$DEST_DIR/"
fi

if [[ -d "$SCRIPT_DIR/linux-postmarketos-exynos850" ]]; then
    echo "==> Installing linux-postmarketos-exynos850 to $DEST_DIR/linux-postmarketos-exynos850..."
    rm -rf "$DEST_DIR/linux-postmarketos-exynos850"
    cp -r "$SCRIPT_DIR/linux-postmarketos-exynos850" "$DEST_DIR/"
fi

echo "==> Done! You can now build with:"
echo "    pmbootstrap build device-samsung-a21s"
echo "    pmbootstrap build linux-samsung-a21s"
