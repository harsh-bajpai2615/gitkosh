#!/usr/bin/env bash
# Build codesync.app + codesync.dmg from a python.org framework Python (relocatable,
# distributable). Falls back to whatever python3 is on PATH with a warning.
set -euo pipefail
cd "$(dirname "$0")"

# Prefer a python.org framework Python (best for distributable py2app bundles).
PYORG=""
for v in 3.13 3.12 3.11; do
  cand="/Library/Frameworks/Python.framework/Versions/$v/bin/python3"
  [ -x "$cand" ] && { PYORG="$cand"; break; }
done
if [ -n "$PYORG" ]; then
  BASEPY="$PYORG"
  echo "==> Using python.org framework Python: $BASEPY"
else
  BASEPY="$(command -v python3)"
  echo "!! python.org framework Python not found in /Library/Frameworks."
  echo "!! Falling back to $BASEPY — bundle may be less portable across Macs."
fi

VENV=".venv-app"
echo "==> Creating build venv ($VENV) from $($BASEPY --version 2>&1)"
rm -rf "$VENV"
"$BASEPY" -m venv "$VENV"
PY="$VENV/bin/python"

echo "==> Installing build/runtime deps"
"$PY" -m pip install -q --upgrade pip "setuptools<81" wheel   # py2app needs pkg_resources
"$PY" -m pip install -q -r requirements-app.txt

echo "==> Building app (py2app)"
rm -rf build dist
"$PY" setup.py py2app

APP="dist/codesync.app"
[ -d "$APP" ] || { echo "Build failed: $APP not found"; exit 1; }
echo "==> Built $APP"

echo "==> Ad-hoc signing (free — makes it run reliably, esp. on Apple Silicon)"
# Not notarization: the app still needs a one-time right-click->Open on other Macs.
codesign --force --deep --sign - "$APP" && codesign --verify --deep "$APP" \
  && echo "  ad-hoc signature OK" || echo "  (ad-hoc signing skipped/failed; continuing)"

echo "==> Making DMG"
DMG="dist/codesync.dmg"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "codesync" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
echo "==> Done: $DMG"
echo
echo "Install: open the DMG, drag codesync.app to Applications."
echo "First launch on any Mac (unsigned): right-click the app -> Open -> Open."
