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

from . import (coach, constants, gamify, github_auth, ollama_setup, patterns,
               posts, problems, roadmap, runner, site, srs)
from .appsupport import STATE_DIR, load_config, save_config
from .cards import render_png
from .contests import cf_rating, upcoming as cf_upcoming
from .github_api import GitHubAPI, slug_repo
from .insights import analytics, resume_bullets
from .sync_core import CP, DOMAINS, LABELS, run_sync
from gitkosh.readme_gen import DEFAULT_MODELS, ReadmeGenerator
from gitkosh.store import Store

WINDOW = None


def _webui_index():
    """Path to webui/index.html — works in dev and inside the py2app bundle.

    py2app exposes bundled data files via the RESOURCEPATH env var
    (Contents/Resources); in dev we resolve relative to the repo root."""
    res = os.environ.get("RESOURCEPATH")
    if res and os.path.isdir(res):
        cand = os.path.join(res, "webui", "index.html")
        if os.path.exists(cand):
            return cand
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "webui", "index.html")


def _main_executable():
    """The bundle's main app binary. In a py2app .app, sys.executable points at the
    sibling 'python' helper, so relaunch the other executable in Contents/MacOS/."""
    macos = os.path.dirname(sys.executable)
    try:
        for f in os.listdir(macos):
            full = os.path.join(macos, f)
            if f != "python" and os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    except OSError:
        pass
    return sys.executable


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


# Some local models (e.g. Ollama) occasionally echo the prompt before answering.
# We append a sentinel and keep only what the model writes after the LAST one, so
# every response reads like it came from a polished assistant.
_SENTINEL = "===GITKOSH_REPLY_BELOW==="


def _ensure_ollama_ready(cfg):
    """If Ollama is the provider, auto-start the local server (when installed) and
    pin the request to a model that's actually pulled — so a fresh selection or a
    stale model name never silently fails. Mutates the in-memory cfg only."""
    llm = (cfg.get("readme", {}) or {}).get("llm", {}) or {}
    if llm.get("provider") != "ollama":
        return
    if not ollama_setup.server_up() and ollama_setup.app_installed():
        ollama_setup.ensure_running(wait=12)  # launch the installed app, brief wait
    avail = ollama_setup.models()
    if avail and llm.get("model") not in avail:
        llm["model"] = avail[0]  # never request a model that isn't downloaded


def _ai_hint():
    """A precise, actionable message for when the AI produced nothing — so the user
    knows exactly what to do instead of a vague 'pick an engine'."""
    llm = (load_config().get("readme", {}) or {}).get("llm", {}) or {}
    provider = llm.get("provider", "none")
    if provider in ("", "none"):
        return ("Turn on an AI engine in **Setup → AI engine** to use this — "
                "**Ollama** is free, private and runs on your Mac.")
    if provider == "ollama":
        state, _ = ollama_setup.status()
        if state == "not_installed":
            return ("Ollama isn't installed yet. Go to **Setup → AI engine**, click **Ollama**, "
                    "and it will install & start automatically (one-time, a couple of GB).")
        if state == "installed_not_running":
            return ("Ollama is installed but its server isn't running. Open **Setup → AI engine → Ollama** "
                    "to start it, then try again.")
        if state == "running_no_model":
            return ("Ollama is running but still downloading its model. Give it a minute "
                    "(re-open **Setup → AI engine → Ollama** to watch progress), then try again.")
        return "Ollama didn't respond. Make sure the Ollama app is running, then try again."
    if not llm.get("api_key"):
        return f"Add your {provider.title()} API key in **Setup → AI engine**, then try again."
    return (f"The {provider.title()} request failed — check your API key and internet connection "
            "in **Setup → AI engine**. (Tip: **Ollama** runs locally with no key.)")


def _ask(prompt):
    cfg = load_config()
    _ensure_ollama_ready(cfg)
    rg = ReadmeGenerator(cfg["readme"])
    full = (prompt.rstrip() + "\n\nIMPORTANT: Do not repeat this prompt, the problem, or the user's code. "
            "Write ONLY your response, in GitHub-flavored Markdown, after the marker line.\n" + _SENTINEL + "\n")
    out = rg.freeform(full) or ""
    if _SENTINEL in out:
        out = out.rsplit(_SENTINEL, 1)[-1]
    return out.strip()


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

    def ai_status(self):
        """Live status of the configured AI engine (drives the Setup UI)."""
        llm = (load_config().get("readme", {}) or {}).get("llm", {}) or {}
        provider = llm.get("provider", "none")
        out = {"provider": provider, "ready": False, "state": "", "models": [],
               "needs_setup": False, "message": ""}
        if provider == "ollama":
            state, ms = ollama_setup.status()
            out.update(state=state, models=ms, ready=(state == "ready"),
                       needs_setup=(state != "ready"))
        elif provider in ("gemini", "groq"):
            out["ready"] = bool(llm.get("api_key"))
            out["needs_setup"] = not out["ready"]
        return out

    def setup_ollama(self):
        """One-click local AI: install Ollama if missing, start its server, pull the
        model — all with live progress. Idempotent (cheap once already set up)."""
        cfg = load_config()
        llm = cfg.setdefault("readme", {}).setdefault("llm", {})
        llm["provider"] = "ollama"
        llm["model"] = DEFAULT_MODELS["ollama"]
        cfg["readme"]["mode"] = "llm"
        save_config(cfg)
        try:
            _prog("Setting up local AI (Ollama)…", 5)
            chosen = ollama_setup.setup(DEFAULT_MODELS["ollama"], progress=lambda m: _prog(m, 55))
            # Pin config to the model that's actually available, so requests never 404.
            avail = ollama_setup.models()
            if chosen and chosen not in avail and f"{chosen}:latest" not in avail and avail:
                chosen = avail[0]
            if chosen and chosen != llm.get("model"):
                llm["model"] = chosen
                save_config(cfg)
            _prog("Local AI ready.", 100)
            return {"ok": True, "model": llm["model"]}
        except Exception as e:  # noqa: BLE001
            _prog("", 0)
            return {"ok": False, "error": str(e)}

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
            if getattr(sys, "frozen", None):
                subprocess.run([_main_executable()], env=env, timeout=900)
            else:
                subprocess.run([sys.executable, "-m", "app.login_helper",
                                "--out", out, "--platforms", name], timeout=900)
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

    # ---- learn (AI tutor + in-app practice) ----
    def tutor_chat(self, history):
        convo = "\n".join(f"{'Student' if m.get('role') == 'user' else 'Tutor'}: {m.get('content', '')}"
                          for m in (history or [])[-12:])
        out = _ask(
            "You are an expert, encouraging data-structures & algorithms tutor. Answer clearly and "
            "concisely with well-structured GitHub-flavored Markdown — use short headings, bullet lists "
            "and fenced code blocks where helpful. When asked for a hint, give a nudge; don't dump the "
            "full solution unless explicitly asked.\n\nConversation so far:\n" + convo)
        return out or _ai_hint()

    def get_onboarded(self):
        return bool(load_config().get("onboarded"))

    def set_onboarded(self):
        cfg = load_config()
        cfg["onboarded"] = True
        save_config(cfg)
        return True

    def get_code(self, pid):
        """Return the user's saved in-progress code for a problem (or '' if none)."""
        return (load_config().get("solutions", {}) or {}).get(pid, "")

    def save_code(self, pid, code):
        """Persist the user's in-progress code so it survives problem switches & restarts."""
        if not pid or pid == "__scratch":
            return False
        cfg = load_config()
        sols = cfg.setdefault("solutions", {})
        if code and code.strip():
            sols[pid] = code
        else:
            sols.pop(pid, None)
        save_config(cfg)
        return True

    def reset_code(self, pid):
        """Forget saved code for a problem (used by the Reset button)."""
        cfg = load_config()
        if (cfg.get("solutions") or {}).pop(pid, None) is not None:
            save_config(cfg)
        return True

    def get_gamify(self):
        return gamify.compute(_items(), STATE_DIR)

    def get_patterns(self):
        return patterns.listing()

    def list_problems(self):
        return problems.listing()

    def get_problem(self, pid):
        return problems.get(pid)

    def run_code(self, code, stdin=""):
        return runner.run_python(code or "", stdin or "")

    def run_tests(self, code, pid):
        return problems.run_tests(code or "", pid)

    def ai_review(self, code, pid, attempt=1):
        prob = problems.get(pid)
        if not prob:
            return "Unknown problem."
        code = (code or "").strip()
        try:
            attempt = max(1, int(attempt))
        except Exception:  # noqa: BLE001
            attempt = 1
        stage = min(attempt, 5)
        starter = (prob.get("starter") or "").strip()
        stub = (not code) or code == starter or (code.replace("pass", "").strip() == starter.replace("pass", "").strip())

        # Decide correctness deterministically when we can, so the coaching never
        # mislabels a wrong/empty answer as correct (model-independent).
        correct = None            # True / False / None (unknown → let the model judge)
        test_section = ""
        if not stub and pid in problems.TESTED:
            tr = problems.run_tests(code, pid)
            correct = bool(tr.get("ok"))
            v = "ALL TESTS PASSED" if correct else f"{tr.get('passed', 0)}/{tr.get('total', 0)} TESTS PASSED"
            test_section = "## Automated test results\n" + v + "\n" + (tr.get("output", "") or "") + "\n\n"
        elif stub:
            correct = False

        header = (
            "You are an elite, supportive coding-interview coach. Be warm, precise and concrete, and never "
            "discourage the student. Reply in GitHub-flavored Markdown, starting directly with a heading.\n\n"
            f"## Problem: {prob['title']} ({prob['difficulty']} · {prob['topic']})\n{prob['statement']}\n\n"
            f"## Student's submission (attempt #{attempt})\n```python\n{code or '(empty stub)'}\n```\n\n"
            + test_section)

        review_branch = (
            "The student's solution is CORRECT. Celebrate, then review it with EXACTLY these sections:\n"
            "### ✅ Correct — great work!\nOne line on why it works.\n"
            "### ⏱ Complexity\nTime & space, each with a one-line justification.\n"
            "### 🧹 Code quality\nSpecific praise plus any naming / readability / edge-handling nits.\n"
            "### 🚀 Optimize\nCan it be faster, cleaner or use less memory? Give the key idea and a short improved "
            "snippet only if it materially helps; if it is already optimal, say so clearly.")

        ladder = (
            f"The student's solution is NOT correct yet{' (the automated tests above are failing)' if test_section else ''}. "
            "Stay encouraging and reveal ONLY the help for the current level — never anything more advanced. "
            f"This is attempt #{attempt}, so give level {stage}:\n"
            "- Level 1 → `### 💡 Hint`: one small conceptual nudge — what to think about. No code, no step list.\n"
            "- Level 2 → `### 💡 Bigger hint`: name the right pattern / data structure and the key insight. No full algorithm.\n"
            "- Level 3 → `### 🧭 Algorithm`: the approach as a clear plain-language bullet list. No code.\n"
            "- Level 4 → `### 📝 Pseudocode`: language-agnostic pseudocode of the full approach.\n"
            "- Level 5 → `### 🎯 Worked solution`: the complete, correct, idiomatic Python solution in a code block, "
            "a short explanation, and its time/space complexity.\n"
            "End (except at level 5) with one warm line inviting another attempt.")

        if correct is True:
            body = header + review_branch
        elif correct is False:
            body = header + ladder
        else:  # unknown: let the model judge, but give it both clearly-separated branches
            body = (header + "FIRST decide if the solution is correct and complete for all valid inputs "
                    "(treat an empty/stub body as incorrect).\n\nIf CORRECT:\n" + review_branch
                    + "\n\nIf NOT correct:\n" + ladder)

        out = _ask(body)
        return out or _ai_hint()

    def grade_answer(self, key, answer):
        appr = ""
        for it in _items():
            if srs.card_key(it) == key:
                appr = it.get("approach", "")
                break
        if not appr:
            return "No reference approach is stored for this problem — re-sync with an AI provider on."
        out = _ask(
            "You are a coding-interview coach. Grade my recalled approach against the reference. "
            "Reply in 3 short lines: a verdict (✅ solid / ⚠️ partial / ❌ off), what I got right, "
            "and what I missed.\n\nReference:\n" + appr + "\n\nMy answer:\n" + answer)
        return out or _ai_hint()


def main():
    global WINDOW
    index = _webui_index()
    tab = os.environ.get("GITKOSH_WEBTAB")
    url = "file://" + index + (f"?tab={tab}" if tab else "")
    WINDOW = webview.create_window("GitKosh", url=url, js_api=Api(), width=1080, height=780,
                                   min_size=(920, 660), background_color="#0b0d14")
    webview.start()


if __name__ == "__main__":
    main()
