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

# --- version-bump discipline -------------------------------------------------
# Enforce a clean semver and refuse to re-ship an already-published version, so
# installed copies always see a strictly higher version (the updater compares
# numerically). Override the duplicate check with RELEASE_FORCE=1 if you really
# must re-upload assets for the same version.
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "✗ VERSION '$VERSION' in app/constants.py is not semver (X.Y.Z). Fix it first." >&2
  exit 1
fi
if [ "${RELEASE_FORCE:-0}" != "1" ] && gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "✗ $TAG is already released. Bump VERSION in app/constants.py (and add a" >&2
  echo "  CHANGELOG.md section) before releasing — or set RELEASE_FORCE=1 to re-upload." >&2
  exit 1
fi
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "⚠  Working tree has uncommitted changes — releasing anyway in 3s (Ctrl-C to stop)."
  sleep 3
fi
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
# Pull this version's CHANGELOG.md section into the notes (if present).
CHANGES="$("$PY" - "$VERSION" <<'PYEOF'
import sys, pathlib
ver = sys.argv[1]
p = pathlib.Path("CHANGELOG.md")
if not p.exists():
    sys.exit(0)
out, grab = [], False
for line in p.read_text(encoding="utf-8").splitlines():
    if line.startswith("## "):
        if grab:
            break
        grab = (line[3:].strip() == ver)
        continue
    if grab:
        out.append(line)
print("\n".join(out).strip())
PYEOF
)"
INSTALL="$(cat <<'EOF'
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
# Release notes = this version's changelog (if any) + install instructions.
if [ -n "$CHANGES" ]; then
  NOTES="## What's new in $TAG"$'\n\n'"$CHANGES"$'\n\n'"---"$'\n\n'"$INSTALL"
else
  NOTES="$INSTALL"
fi
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "Re-uploading assets for existing $TAG (RELEASE_FORCE)."
  gh release upload "$TAG" dist/GitKosh.zip dist/gitkosh.dmg -R "$REPO" --clobber
  gh release edit "$TAG" -R "$REPO" -t "GitKosh $TAG" -n "$NOTES"
else
  gh release create "$TAG" dist/GitKosh.zip dist/gitkosh.dmg \
    -R "$REPO" -t "GitKosh $TAG" -n "$NOTES"
fi
echo "==> Done. Installed copies will offer the update on next launch."
