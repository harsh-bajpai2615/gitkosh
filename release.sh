#!/usr/bin/env bash
# Build GitKosh and publish it as a GitHub Release so installed copies can auto-update.
# Bump app/constants.py VERSION first, then run this.
set -euo pipefail
cd "$(dirname "$0")"

REPO="harsh-bajpai2615/gitkosh"
PY=".venv-app/bin/python"
[ -x "$PY" ] || PY="python3"
VERSION="$("$PY" -c 'from app.constants import VERSION; print(VERSION)')"
TAG="v$VERSION"
echo "==> Releasing GitKosh $TAG to $REPO"

# 1) build the app + dmg (also ad-hoc signs)
./build_app.sh

# 2) zip the .app for the in-app updater (ditto preserves the bundle)
cd dist
rm -f GitKosh.zip
ditto -c -k --sequesterRsrc --keepParent gitkosh.app GitKosh.zip
cd ..

# 3) ensure the releases repo exists (public, so unauthenticated update checks work)
gh repo view "$REPO" >/dev/null 2>&1 || \
  gh repo create "$REPO" --public -d "GitKosh — releases & auto-update feed"

# 4) publish the release with the zip (updater) + dmg (first-time installs)
NOTES="$(cat <<'EOF'
**Install**

1. Download **`gitkosh.dmg`** below, open it, and drag **GitKosh** into **Applications**.
2. **First launch.** GitKosh is open-source but not Apple-notarized (that needs a paid Apple Developer account), so macOS warns *"Apple could not verify GitKosh is free of malware."* — normal for any indie app. Unlock it once:
   - **macOS 15 Sequoia & newer:** click **Done**, then open **System Settings → Privacy & Security**, scroll to *"GitKosh was blocked…"* and click **Open Anyway**.
   - **macOS 14 & earlier:** **right-click the app → Open → Open**.
   - **Or, in Terminal (any version):** `xattr -dr com.apple.quarantine /Applications/GitKosh.app`

   After that it opens with a double-click and auto-updates.

**AI features (tutor, reviews, write-ups)**

Open **Setup → AI engine** and click **Ollama** — GitKosh installs & starts it for you (free, fully local, no key; one-time ~2 GB model download). Or paste a free Gemini/Groq key.
EOF
)"
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "Release $TAG already exists — uploading assets and refreshing notes."
  gh release upload "$TAG" dist/GitKosh.zip dist/gitkosh.dmg -R "$REPO" --clobber
  gh release edit "$TAG" -R "$REPO" -t "GitKosh $TAG" -n "$NOTES"
else
  gh release create "$TAG" dist/GitKosh.zip dist/gitkosh.dmg \
    -R "$REPO" -t "GitKosh $TAG" -n "$NOTES"
fi
echo "==> Done. Installed copies will offer the update on next launch."
