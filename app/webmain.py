"""Prototype web-stack UI for GitKosh.

A native WebKit window (pywebview) renders webui/ (modern HTML/CSS/JS) and bridges
to the SAME Python backend the Tk app uses — no logic duplicated. Run with:
    .venv-app/bin/python -m app.webmain
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import subprocess
import sys
import threading

import webview

from . import coach, constants, github_auth, posts, roadmap, site, srs
from .appsupport import STATE_DIR, load_config, save_config
from .cards import render_png
from .contests import cf_rating, upcoming as cf_upcoming
from .github_api import GitHubAPI, slug_repo
from .insights import analytics, resume_bullets
from .sync_core import CP, DOMAINS, LABELS, run_sync
from gitkosh.readme_gen import DEFAULT_MODELS, ReadmeGenerator
from gitkosh.store import Store

WINDOW = None


def _items():
    try:
        return Store(STATE_DIR).all()
    except Exception:  # noqa: BLE001
        return []


def _connected():
    p = STATE_DIR / "storage_state.json"
    domains = set()
    if p.exists():
        try:
            for c in json.loads(p.read_text()).get("cookies", []):
                domains.add(c.get("domain", ""))
        except Exception:  # noqa: BLE001
            pass
    return {n: any(dom in d for d in domains) for n, dom in DOMAINS.items()}


def _js(code):
    try:
        if WINDOW:
            WINDOW.evaluate_js(code)
    except Exception:  # noqa: BLE001
        pass


def _prog(text, pct=8):
    _js(f"window.gkProgress && window.gkProgress({json.dumps(text or '')}, {pct})")


class Api:
    # ---- read ----
    def get_state(self):
        cfg = load_config()
        gh = github_auth.load_github(STATE_DIR)
        llm = cfg.get("readme", {}).get("llm", {}) or {}
        return {
            "version": f"v{constants.VERSION}",
            "github": (gh or {}).get("login"),
            "sites": {n: bool(v) for n, v in _connected().items()},
            "provider": llm.get("provider", "gemini"),
            "api_key": llm.get("api_key", ""),
        }

    def get_card(self):
        try:
            owner = (github_auth.load_github(STATE_DIR) or {}).get("login", "")
            return base64.b64encode(render_png(_items(), username=owner)).decode("ascii")
        except Exception:  # noqa: BLE001
            return ""

    def get_embed(self):
        owner = (github_auth.load_github(STATE_DIR) or {}).get("login", "")
        return site.badges_md(_items(), owner, slug_repo(load_config()["github"]["repo"]))

    def get_insights(self):
        items = _items()
        a = analytics(items)
        opt = f"{round(100 * a['optimal'] / a['coached'])}%" if a["coached"] else "—"
        tiles = [["This week", a["week"]], ["This month", a["month"]], ["Streak", f"{a['current_streak']}d"],
                 ["Longest", f"{a['longest_streak']}d"], ["Optimal", opt], ["Total", a["total"]]]
        quiz = [{"title": i.get("title", ""), "platform": LABELS.get(i.get("platform"), i.get("platform")),
                 "difficulty": i.get("difficulty", ""), "approach": i.get("approach", "")}
                for i in (a["revisit"] or items)[:30]]
        return {"tiles": tiles, "difficulty": dict(a["difficulty"]), "topics": a["strengths"],
                "resume": resume_bullets(items), "quiz": quiz}

    def get_contests(self):
        handle = (load_config().get("platforms", {}).get("codeforces", {}) or {}).get("handle", "")
        up = []
        for c in cf_upcoming()[:12]:
            when = dt.datetime.fromtimestamp(c["start"]).strftime("%a %d %b · %H:%M") if c.get("start") else "—"
            up.append({"platform": c["platform"], "name": c["name"], "when": when,
                       "dur": f"{round(c.get('duration', 0) / 3600, 1)}h", "url": c["url"]})
        return {"handle": handle, "upcoming": up, "rating": [r for _, r in cf_rating(handle)]}

    # ---- actions ----
    def set_provider(self, v):
        cfg = load_config()
        llm = cfg.setdefault("readme", {}).setdefault("llm", {})
        llm["provider"] = v
        llm["model"] = DEFAULT_MODELS.get(v, "")
        cfg["readme"]["mode"] = "minimal" if v == "none" else "llm"
        save_config(cfg)
        return True

    def save_ai(self, provider, key):
        cfg = load_config()
        llm = cfg.setdefault("readme", {}).setdefault("llm", {})
        llm["provider"] = provider
        llm["model"] = DEFAULT_MODELS.get(provider, "")
        llm["api_key"] = key or ""
        cfg["readme"]["mode"] = "minimal" if provider == "none" else "llm"
        save_config(cfg)
        return True

    def github_login(self):
        try:
            cid = constants.GITHUB_CLIENT_ID
            d = github_auth.start_device_flow(cid)
            import webbrowser
            webbrowser.open(d["verification_uri"])
            _prog(f"Enter code {d['user_code']} in your browser to authorize…", 30)
            token = github_auth.poll_for_token(cid, d["device_code"], d.get("interval", 5),
                                               d.get("expires_in", 900))
            login = GitHubAPI(token, "").whoami()
            github_auth.save_token(STATE_DIR, token, login)
            _prog("Connected to GitHub.", 100)
            return login
        except Exception as e:  # noqa: BLE001
            _prog(f"GitHub login failed: {e}", 0)
            return None

    def cp_login(self, name):
        try:
            out = str(STATE_DIR / "storage_state.json")
            env = dict(os.environ, GITKOSH_ROLE="login", GITKOSH_OUT=out, GITKOSH_PLATFORMS=name)
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            subprocess.run([sys.executable, os.path.join(root, "app_main.py")], env=env, timeout=900)
        except Exception:  # noqa: BLE001
            pass
        return True

    def run_sync(self, reset=False):
        cfg = load_config()

        def prog(kind, **k):
            if kind == "step":
                pct = int(100 * k.get("i", 0) / max(k.get("n", 1), 1))
            elif kind == "done":
                pct = 100
            else:
                pct = 12
            _prog(k.get("text", ""), pct)

        res = run_sync(cfg, STATE_DIR, reset=reset, keep_streak=True,
                       log=lambda m: _prog(m, 12), progress=prog)
        _js("window.gkRefresh && window.gkRefresh()")
        return res

    def publish_site(self):
        cfg = load_config()
        gh = GitHubAPI(github_auth.load_github(STATE_DIR)["token"], cfg["github"]["repo"],
                       private=cfg["github"].get("private", True))
        gh.ensure_repo()
        owner, repo = gh._resolve()
        items = _items()
        files = {"docs/index.html": site.render(items, owner, repo), "docs/.nojekyll": "",
                 "profile/badges.md": site.badges_md(items, owner, repo)}
        try:
            files["profile/stats.png"] = render_png(items, username=owner)
        except Exception:  # noqa: BLE001
            pass
        gh.push_commits([{"files": files, "message": "GitKosh: publish portfolio site", "date": None}])
        return gh.enable_pages("/docs")

    def generate_post(self):
        return posts.generate(_items(), rg=ReadmeGenerator(load_config()["readme"]), days=7,
                              username=(github_auth.load_github(STATE_DIR) or {}).get("login", ""))

    # ---- practice (quiz + coach + roadmaps) ----
    def get_practice(self):
        items = _items()
        return {
            "potd": coach.potd(items, STATE_DIR),
            "roadmaps": roadmap.progress(items),
            "srs": srs.stats(items, STATE_DIR),
            "queue": [{"key": srs.card_key(it), "title": it.get("title", ""),
                       "platform": LABELS.get(it.get("platform"), it.get("platform")),
                       "difficulty": it.get("difficulty", ""), "tags": it.get("tags") or [],
                       "approach": it.get("approach", ""), "url": it.get("url", "")}
                      for it in srs.due(items, STATE_DIR)[:40]],
        }

    def quiz_review(self, key, rating):
        srs.review(STATE_DIR, key, rating)
        return srs.stats(_items(), STATE_DIR)

    def grade_answer(self, key, answer):
        appr = ""
        for it in _items():
            if srs.card_key(it) == key:
                appr = it.get("approach", "")
                break
        if not appr:
            return "No reference approach is stored for this problem — re-sync with an AI provider on."
        out = ReadmeGenerator(load_config()["readme"]).freeform(
            "You are a coding-interview coach. Grade my recalled approach against the reference. "
            "Reply in 3 short lines: a verdict (✅ solid / ⚠️ partial / ❌ off), what I got right, "
            "and what I missed.\n\nReference:\n" + appr + "\n\nMy answer:\n" + answer)
        return out or "Couldn't grade — no AI provider configured (pick Ollama/Gemini in Setup)."


def main():
    global WINDOW
    index = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webui", "index.html")
    tab = os.environ.get("GITKOSH_WEBTAB")
    url = "file://" + index + (f"?tab={tab}" if tab else "")
    WINDOW = webview.create_window("GitKosh", url=url, js_api=Api(), width=1080, height=780,
                                   min_size=(920, 660), background_color="#0b0d14")
    webview.start()


if __name__ == "__main__":
    main()
