#!/usr/bin/env bash
# Build Claude Ticker as a macOS .app bundle
set -euo pipefail

echo "==> Installing Python dependencies…"
pip3 install -r requirements.txt

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building .app…"
python3 setup.py py2app 2>&1

APP="dist/ClaudeTicker.app"

echo "==> Ad-hoc signing (allows first-run without Gatekeeper prompt)…"
codesign --force --deep --sign - "$APP" 2>/dev/null || true

echo ""
echo "✓ Built: $APP"
echo ""
echo "To install system-wide:"
echo "  cp -r $APP /Applications/"
echo ""
echo "First run: right-click → Open  (required for unsigned apps on macOS 15)"
echo "Or drag to Login Items in System Settings → General → Login Items"
