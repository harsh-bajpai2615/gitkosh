"""Build-time constants.

GITHUB_CLIENT_ID is the public client_id of the GitHub OAuth App registered for this
product (Device Flow enabled). It is safe to ship in the app. Fill it in once you've
registered the OAuth App; config `github.client_id` overrides it if set.
"""

GITHUB_CLIENT_ID = "Ov23li1zSZj6zdhurptk"  # gitkosh OAuth App (Device Flow), public/safe to ship

# App version + where the in-app updater looks for new releases.
# Bump this (semver) for every release — release.sh refuses to re-ship a version
# that's already published, so installed copies always see a higher version. Keep
# CHANGELOG.md in sync; release.sh pulls this version's section into the notes.
VERSION = "1.1.0"
RELEASES_REPO = "harsh-bajpai2615/gitkosh"
