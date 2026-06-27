<div align="center">

<img src="docs/logo.png" width="120" alt="CodeSync logo" />

# CodeSync

**Automatically sync your competitive-programming solutions from LeetCode, Codeforces, CodeChef & NeetCode to GitHub — each with an AI-written explanation, on a daily schedule that even keeps your contribution streak alive.**

![platform](https://img.shields.io/badge/platform-macOS%2012%2B-000?logo=apple)
![python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)
![release](https://img.shields.io/github/v/release/harsh-bajpai2615/codesync?color=5B5BD6)
![license](https://img.shields.io/badge/license-MIT-16A34A)

[**⬇ Download for macOS**](https://github.com/harsh-bajpai2615/codesync/releases/latest) · [Features](#-features) · [How it works](#%EF%B8%8F-how-it-works) · [Build from source](#%EF%B8%8F-build-from-source)

<br/>

<img src="docs/screenshot.png" width="540" alt="CodeSync app" />

</div>

---

## What is CodeSync?

CodeSync is a tiny macOS app that turns your scattered competitive-programming solves into a clean, organized, **documented** GitHub repository — automatically. Log into your accounts once; CodeSync pulls every accepted submission, writes a per-problem README (problem summary → a numbered algorithm of *your* solution → complexity → key insight), and pushes it all to GitHub. Put it on a daily schedule and it keeps running — even keeping your contribution graph green.

> It's a **mediator**, not an editor. Keep solving on the platforms you love; CodeSync archives and documents the work for you. Your passwords are never stored — it logs in through the system's WebKit cookie store.

## ✨ Features

- **5 logins — that's the whole UI.** LeetCode, Codeforces, CodeChef, NeetCode + GitHub. A guided 3-step flow makes the order obvious.
- **AI write-ups for every problem.** Problem summary → **numbered algorithm of your actual code** → time/space complexity → key insight, in clean Markdown.
- **Bring-your-own AI — including free & local.** Google Gemini, Groq, or **one-click local Ollama** (no key, no limits, fully private).
- **Daily auto-sync.** A background scheduler runs even when the app is closed — no reminders, no clicking.
- **Streak keeper.** On days with no new solves, it makes a small dated commit so your GitHub streak stays alive.
- **In-app auto-update.** New versions install themselves with one click.
- **Nothing to install on your Mac.** No `git`, no terminal, no Python — it talks to GitHub over the API and ships its own runtime.
- **Live progress.** A real progress bar: *Fetching → Writing READMEs i/N → Pushing → Done.*

## 📥 Install

1. Download the latest **`codesync.dmg`** from [**Releases**](https://github.com/harsh-bajpai2615/codesync/releases/latest).
2. Open it and drag **CodeSync** into **Applications**.
3. First launch (the app isn't notarized yet): **right-click → Open → Open** — once. After that it opens normally and updates itself.

## 🚀 Usage

1. **Connect GitHub** — one-tap "Login with GitHub" (OAuth device flow).
2. **Connect your coding sites** — log in; handles are detected automatically.
3. **Choose write-ups** — paste a free Gemini/Groq key, or set up **Ollama** in one click (free, local).
4. **Sync** — or flip on **daily auto-sync** and forget about it.

Your solutions land in your repo like this:

```
leetcode/0001-two-sum/
├── solution.py
└── README.md      # problem · algorithm · complexity · key insight
```

## 🤖 Write-up providers

| Provider | Cost | Setup | Daily limit |
|---|---|---|---|
| **Ollama** (local) | Free | One-click install, in-app | None |
| **Groq** | Free tier | Paste an API key | High |
| **Gemini** | Free tier | Paste an API key | Low |
| **None** | Free | Nothing | No AI — statement + code only |

## ⏰ Automation & streak keeping

Turn on **“Sync automatically every day”** and CodeSync installs a macOS LaunchAgent that runs a sync daily — even with the app closed. With **“Keep my GitHub streak alive”** on, days with no new solves still get a small dated commit to `activity/streak.md`, so your contribution graph stays green.

## 🏗️ How it works

- **Login** — a native WebKit window captures your session cookie (no passwords stored); GitHub uses OAuth **Device Flow** (no client secret shipped).
- **Fetch** — one extractor per platform (LeetCode GraphQL, Codeforces API + page scrape, CodeChef scrape, NeetCode via LeetCode).
- **Document** — a pluggable LLM layer writes each README from your code + the official statement.
- **Push** — the GitHub **REST API** (Git Data API) commits everything; no `git`/`gh` needed on your machine.
- **Schedule** — a LaunchAgent runs the same headless sync on a daily cron.
- **Update** — the app checks GitHub Releases on launch and self-replaces.

```
LeetCode ─┐
Codeforces┤   WebKit login (cookies)         Gemini / Groq / Ollama (write-ups)
CodeChef ─┼─▶ extractors ─▶ submissions ─▶  README generator ─▶ GitHub API ─▶ your repo
NeetCode ─┘   GitHub Device Flow (token)     scheduler (daily) + streak keeper
```

## 🛠️ Build from source

Requires macOS and a [python.org](https://www.python.org/downloads/macos/) framework Python (3.13 recommended).

```bash
git clone https://github.com/harsh-bajpai2615/codesync
cd codesync
./build_app.sh          # → dist/codesync.app + dist/codesync.dmg
```

Cut a release that installed copies will auto-update to:

```bash
# bump VERSION in app/constants.py, then:
./release.sh
```

## 📂 Project structure

```
app/            macOS app — GUI, WebKit login, sync core, scheduler, updater, Ollama setup
codesync/       platform extractors, README generator, GitHub helpers
setup.py        py2app bundle config           build_app.sh   build .app + .dmg
release.sh      build + publish a release       tools/         app-icon generator
```

## ⚠️ Notes & limitations

- **macOS only** (uses native WebKit + LaunchAgents).
- **Not notarized yet** — first launch needs right-click→Open; updates after that are seamless.
- **CodeChef** is best-effort (Cloudflare, no public API).
- Free **Gemini** has a low daily cap — use **Ollama** (local) or **Groq** for large backfills.
- Your data (logins, settings, history) lives in `~/Library/Application Support/codesync/` and survives updates.

## License

[MIT](LICENSE) © Harsh Bajpai

<div align="center"><sub>Made for people who solve a lot and document too little.</sub></div>
