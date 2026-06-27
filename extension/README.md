# GitKosh Sync — browser extension (beta)

A lightweight companion to the [GitKosh](https://github.com/harsh-bajpai2615/gitkosh)
macOS app that captures your **accepted LeetCode submissions in real time** and pushes
them straight to GitHub — so it also works on **Windows & Linux**, with no app needed.

> The macOS app does much more (6 platforms, AI write-ups, dashboard, insights, contests).
> This extension is the lightweight, cross-platform, real-time capture path for LeetCode.

## Install (unpacked)

1. Open `chrome://extensions` (Chrome/Edge/Brave) and turn on **Developer mode**.
2. Click **Load unpacked** and select this `extension/` folder.
3. Click the GitKosh icon → paste a **GitHub token** and your **repo** (`owner/name` or just `name`).
   - Create a fine-grained token with **Contents: Read and write** on that repo at
     [github.com/settings/tokens](https://github.com/settings/tokens).
4. Solve a problem on LeetCode. On **Accepted**, it commits `leetcode/<id>-<slug>/solution.<ext>`
   and a small `README.md`. A green ✓ badge confirms the push.

## How it works

- `injected.js` wraps the page's `fetch` to detect an **Accepted** submission.
- `content.js` then pulls the code + problem metadata via LeetCode's GraphQL and forwards it.
- `background.js` commits the files via the GitHub Git Data API (blobs → tree → commit → ref).

No passwords are stored; only your token + repo, in `chrome.storage`. Nothing is sent anywhere
except GitHub.

## Status

Beta. LeetCode occasionally changes its internal endpoints; if a solve doesn't push, open the
extension's service-worker console from `chrome://extensions` and file an issue.
