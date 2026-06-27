#!/usr/bin/env bash
# Build CodeSync and publish it as a GitHub Release so installed copies can auto-update.
# Bump app/constants.py VERSION first, then run this.
set -euo pipefail
cd "$(dirname "$0")"

REPO="harsh-bajpai2615/codesync"
PY=".venv-app/bin/python"
[ -x "$PY" ] || PY="python3"
VERSION="$("$PY" -c 'from app.constants import VERSION; print(VERSION)')"
TAG="v$VERSION"
echo "==> Releasing CodeSync $TAG to $REPO"

# 1) build the app + dmg (also ad-hoc signs)
./build_app.sh

# 2) zip the .app for the in-app updater (ditto preserves the bundle)
cd dist
rm -f CodeSync.zip
ditto -c -k --sequesterRsrc --keepParent codesync.app CodeSync.zip
cd ..

# 3) ensure the releases repo exists (public, so unauthenticated update checks work)
gh repo view "$REPO" >/dev/null 2>&1 || \
  gh repo create "$REPO" --public -d "CodeSync — releases & auto-update feed"

# 4) publish the release with the zip (updater) + dmg (first-time installs)
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "Release $TAG already exists — uploading/overwriting assets."
  gh release upload "$TAG" dist/CodeSync.zip dist/codesync.dmg -R "$REPO" --clobber
else
  gh release create "$TAG" dist/CodeSync.zip dist/codesync.dmg \
    -R "$REPO" -t "CodeSync $TAG" -n "Automated release of CodeSync $TAG."
fi
echo "==> Done. Installed copies will offer the update on next launch."
