"""Build-time constants.

GITHUB_CLIENT_ID is the public client_id of the GitHub OAuth App registered for this
product (Device Flow enabled). It is safe to ship in the app. Fill it in once you've
registered the OAuth App; config `github.client_id` overrides it if set.
"""

GITHUB_CLIENT_ID = "Ov23li1zSZj6zdhurptk"  # codesync OAuth App (Device Flow), public/safe to ship

# App version + where the in-app updater looks for new releases.
VERSION = "0.2.0"
RELEASES_REPO = "harsh-bajpai2615/codesync"
