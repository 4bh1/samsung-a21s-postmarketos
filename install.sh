#!/usr/bin/env bash
set -euo pipefail

# Samsung Galaxy A21s pmaports installer
# Vibe coded with Google Antigravity

PMAPORTS_DIR="${1:-$HOME/.local/var/pmbootstrap/cache_git/pmaports}"

if [[ ! -d "$PMAPORTS_DIR" ]]; then
    echo "ERROR: pmaports directory not found at $PMAPORTS_DIR"
    echo "Usage: $0 [/path/to/pmaports]"
    exit 1
fi

DEST_DIR="$PMAPORTS_DIR/device/testing"
mkdir -p "$DEST_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing device-samsung-a21s to $DEST_DIR/device-samsung-a21s..."
rm -rf "$DEST_DIR/device-samsung-a21s"
cp -r "$SCRIPT_DIR/device-samsung-a21s" "$DEST_DIR/"

echo "==> Installing linux-postmarketos-exynos850 to $DEST_DIR/linux-postmarketos-exynos850..."
rm -rf "$DEST_DIR/linux-postmarketos-exynos850"
cp -r "$SCRIPT_DIR/linux-postmarketos-exynos850" "$DEST_DIR/"

echo "==> Done! You can now build with:"
echo "    pmbootstrap build device-samsung-a21s"
echo "    pmbootstrap build linux-postmarketos-exynos850"
