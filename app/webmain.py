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

from . import (backfill, coach, companies, constants, gamify, github_auth,
               ollama_setup, patterns, posts, problems, roadmap, runner, site, srs,
               studyplan, voice)
from .appsupport import STATE_DIR, load_config, save_config
from .cards import render_png
from .contests import cf_rating, upcoming as cf_upcoming
from .github_api import GitHubAPI, slug_repo
from .insights import analytics, resume_bullets, topic_strength
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


def _solved_leetcode_slugs() -> set:
    """Slugs of LeetCode problems the user has actually solved (from synced history),
    used to mark progress against company question lists and study plans."""
    return studyplan.solved_slugs(_items())


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


def _wrap(prompt):
    return (prompt.rstrip() + "\n\nIMPORTANT: Do not repeat this prompt, the problem, or the user's code. "
            "Write ONLY your response, in GitHub-flavored Markdown, after the marker line.\n" + _SENTINEL + "\n")


def _ask(prompt):
    cfg = load_config()
    _ensure_ollama_ready(cfg)
    rg = ReadmeGenerator(cfg["readme"])
    out = rg.freeform(_wrap(prompt)) or ""
    if _SENTINEL in out:
        out = out.rsplit(_SENTINEL, 1)[-1]
    return out.strip()


def _emit_stream(stream_id, text):
    if not stream_id:
        return
    _js(f"window.gkStream && window.gkStream({json.dumps(stream_id)}, {json.dumps(text)})")


def _ask_stream(prompt, stream_id):
    """Stream an answer to the UI (keyed by stream_id) and return the full text.
    The UI receives the cumulative post-marker text on each chunk and just
    re-renders it, so it never has to reassemble deltas."""
    cfg = load_config()
    _ensure_ollama_ready(cfg)
    rg = ReadmeGenerator(cfg["readme"])
    buf = []

    def on_chunk(piece):
        buf.append(piece)
        text = "".join(buf)
        if _SENTINEL in text:  # only reveal what the model writes after the marker
            _emit_stream(stream_id, text.rsplit(_SENTINEL, 1)[-1].lstrip())

    out = rg.freeform_stream(_wrap(prompt), on_chunk) or ""
    if _SENTINEL in out:
        out = out.rsplit(_SENTINEL, 1)[-1]
    out = out.strip()
    _emit_stream(stream_id, out)  # final, clean render
    return out


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
                "topic_strength": topic_strength(items),
                "resume": resume_bullets(items), "quiz": quiz}

    def get_contests(self):
        handle = (load_config().get("platforms", {}).get("codeforces", {}) or {}).get("handle", "")
        up = []
        try:
            for c in cf_upcoming()[:12]:
                when = dt.datetime.fromtimestamp(c["start"]).strftime("%a %d %b · %H:%M") if c.get("start") else "—"
                up.append({"platform": c.get("platform", ""), "name": c.get("name", "Contest"), "when": when,
                           "dur": f"{round(c.get('duration', 0) / 3600, 1)}h", "url": c.get("url", "")})
        except Exception:  # noqa: BLE001 — a malformed/unreachable feed shouldn't blank the tab
            pass
        try:
            rating = [r for _, r in cf_rating(handle)]
        except Exception:  # noqa: BLE001
            rating = []
        return {"handle": handle, "upcoming": up, "rating": rating}

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

    def github_start(self):
        """Begin GitHub device-flow login. Returns the user_code to display BEFORE
        opening the browser (GitHub shows no code itself — the user must type ours)."""
        try:
            d = github_auth.start_device_flow(constants.GITHUB_CLIENT_ID)
            return {"ok": True, "user_code": d["user_code"],
                    "verification_uri": d.get("verification_uri", "https://github.com/login/device"),
                    "device_code": d["device_code"], "interval": d.get("interval", 5),
                    "expires_in": d.get("expires_in", 900)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def github_open(self, url=""):
        """Open the GitHub device-authorization page in the user's real browser."""
        import webbrowser
        if not (url or "").startswith("https://github.com/"):
            url = "https://github.com/login/device"
        webbrowser.open(url)
        return True

    def github_poll(self, device_code, interval=5, expires_in=900):
        """Wait for the user to approve, then store the token. {ok, login} or {ok, error}."""
        try:
            token = github_auth.poll_for_token(
                constants.GITHUB_CLIENT_ID, device_code,
                int(interval or 5), int(expires_in or 900))
            login = GitHubAPI(token, "").whoami()
            github_auth.save_token(STATE_DIR, token, login)
            return {"ok": True, "login": login}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

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

    # ---- backfill: import a local folder's real past work onto the graph ----
    def pick_folder(self):
        """Native folder chooser. Returns the chosen absolute path or ''."""
        try:
            if not WINDOW:
                return ""
            res = WINDOW.create_file_dialog(webview.FOLDER_DIALOG)
            if res:
                return res[0] if isinstance(res, (list, tuple)) else res
        except Exception:  # noqa: BLE001
            pass
        return ""

    def backfill_preview(self, path):
        if not path:
            return {"ok": False, "error": "Pick a folder first."}
        return backfill.summarize(backfill.scan(path))

    def backfill_run(self, path):
        gh_info = github_auth.load_github(STATE_DIR)
        if not gh_info:
            return {"ok": False, "error": "Connect GitHub first."}
        cfg = load_config()
        repo = (cfg.get("github") or {}).get("repo")
        if not repo:
            return {"ok": False, "error": "Set a destination repo in Setup first."}
        _prog("Scanning your folder…", 8)
        sc = backfill.scan(path)
        if not sc.get("ok"):
            return sc
        if not sc["total_files"]:
            return {"ok": False, "error": "No importable text files found in that folder."}
        commits = backfill.build_commits(sc)
        _prog(f"Importing {sc['total_files']} file(s) across {len(commits)} day(s)…", 30)
        gh = GitHubAPI(gh_info["token"], repo, private=cfg["github"].get("private", True))
        try:
            gh.ensure_repo()
            url = gh.push_commits(commits)  # layer onto history with the real dates
        except Exception as e:  # noqa: BLE001
            _prog(f"Import failed: {e}", 100)
            return {"ok": False, "error": str(e)}
        _prog(f"✓ Imported {sc['total_files']} file(s) in {len(commits)} dated commit(s).", 100)
        _js("window.gkRefresh && window.gkRefresh()")
        return {"ok": True, "files": sc["total_files"], "commits": len(commits), "url": url}

    def publish_site(self):
        cfg = load_config()
        gh_info = github_auth.load_github(STATE_DIR)
        if not gh_info or not (cfg.get("github") or {}).get("repo"):
            return None  # not connected / no repo — UI shows a hint
        gh = GitHubAPI(gh_info["token"], cfg["github"]["repo"],
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
    _TUTOR_SYSTEM = (
        "You are an expert, encouraging data-structures & algorithms tutor. Answer clearly and "
        "concisely with well-structured GitHub-flavored Markdown — use short headings, bullet lists "
        "and fenced code blocks where helpful. When asked for a hint, give a nudge; don't dump the "
        "full solution unless explicitly asked.\n\nConversation so far:\n")

    def _tutor_prompt(self, history):
        convo = "\n".join(f"{'Student' if m.get('role') == 'user' else 'Tutor'}: {m.get('content', '')}"
                          for m in (history or [])[-12:])
        return self._TUTOR_SYSTEM + convo

    def tutor_chat(self, history):
        return _ask(self._tutor_prompt(history)) or _ai_hint()

    def tutor_chat_stream(self, history, stream_id=""):
        out = _ask_stream(self._tutor_prompt(history), stream_id)
        return out or _ai_hint()

    # ---- mock interview ----
    _IV_SYSTEM = (
        "You are a senior software engineer conducting a real coding interview at a top tech company. "
        "Be professional, warm but rigorous. Drive the interview: ask the candidate to clarify assumptions, "
        "justify their approach, analyze time/space complexity, handle edge cases, and improve a brute-force "
        "answer. Probe with pointed follow-up questions. Give only a small nudge if they're truly stuck — "
        "NEVER write the solution for them. Ask ONE focused question per turn.\n"
        "Your replies are SPOKEN ALOUD to the candidate, so keep each turn very short — 1 to 3 sentences, "
        "conversational, no code blocks, no markdown headings, no bullet lists. Just talk like a real "
        "interviewer would out loud.")

    @staticmethod
    def _iv_convo(history):
        return "\n".join(
            f"{'Candidate' if m.get('role') == 'user' else 'Interviewer'}: {m.get('content', '')}"
            for m in (history or [])[-16:])

    def interview_problems(self):
        return problems.listing()

    def interview_start(self, pid=""):
        pool = problems.listing()
        if not pool:
            return {"ok": False, "error": "No problems available."}
        if not pid:
            import random
            pid = random.choice(pool)["id"]
        prob = problems.get(pid)
        if not prob:
            return {"ok": False, "error": "Unknown problem."}
        opener = (
            f"Hi! I'll be your interviewer today. Let's work on **{prob['title']}** "
            f"({prob['difficulty']} · {prob['topic']}).\n\n"
            "Take a moment to read it, then walk me through your initial thoughts — what's your first "
            "approach, and what's its time and space complexity? Ask me anything you'd like to clarify.")
        return {"ok": True, "pid": pid, "problem": prob, "opener": opener}

    def interview_reply(self, history, pid, code="", stream_id=""):
        prob = problems.get(pid) or {}
        prompt = (
            self._IV_SYSTEM
            + f"\n\n## Problem\n{prob.get('title', '')} ({prob.get('difficulty', '')})\n{prob.get('statement', '')}\n\n"
            + f"## Candidate's current code (may be incomplete)\n```python\n{code or '(nothing yet)'}\n```\n\n"
            + f"## Transcript so far\n{self._iv_convo(history)}\n\n"
            + "Respond as the interviewer for your next turn only.")
        return _ask_stream(prompt, stream_id) or _ai_hint()

    # ---- voice mock interview ----
    def voice_status(self):
        return voice.status()

    def voice_speak(self, text):
        return voice.speak(text or "")

    def voice_stop_speaking(self):
        return voice.stop_speaking()

    def voice_start(self):
        try:
            return voice.start_recording()
        except Exception as e:  # noqa: BLE001 — return, never throw, so the UI shows the cause
            import traceback; traceback.print_exc()
            return {"ok": False, "error": f"voice_start failed: {e}"}

    def voice_stop(self, hints=None):
        try:
            # Stored Groq key (any provider) is the preferred / fallback STT engine.
            llm = (load_config().get("readme", {}) or {}).get("llm", {}) or {}
            key = (llm.get("api_key") or "").strip()
            groq_key = key if key.startswith("gsk_") else ""
            return voice.stop_and_transcribe(groq_key, hints or [])
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            return {"ok": False, "error": f"voice_stop failed: {e}"}

    # ---- company-wise interview questions ----
    def list_companies(self):
        return companies.list_companies()

    @staticmethod
    def _decorate_questions(qs, company, name, period):
        """Tag each question with solved / in-app / bookmarked, plus aggregate
        totals and solved-by-difficulty — shared by company and saved-list views."""
        solved = _solved_leetcode_slugs()
        bm = set((load_config().get("bookmarks") or {}).keys())
        nsolved = 0
        diff = {"Easy": 0, "Medium": 0, "Hard": 0}
        solved_by_diff = {"Easy": 0, "Medium": 0, "Hard": 0}
        for q in qs:
            q["solved"] = q["slug"] in solved
            q["in_app"] = q["slug"] in problems.CATALOG  # solvable in the built-in IDE
            q["bookmarked"] = q["slug"] in bm
            q["topics"] = companies.topics_for(q["slug"])  # LeetCode topic/pattern tags
            d = q.get("difficulty", "")
            diff[d] = diff.get(d, 0) + 1
            if q["solved"]:
                nsolved += 1
                if d in solved_by_diff:
                    solved_by_diff[d] += 1
        return {
            "ok": True, "company": company, "name": name, "period": period,
            "questions": qs, "total": len(qs), "solved": nsolved,
            "difficulty": diff, "solved_by_diff": solved_by_diff,
        }

    def company_questions(self, company, period="all"):
        res = companies.fetch(company, period, STATE_DIR)
        if not res.get("ok"):
            return res
        cat = next((c for c in companies.list_companies()["companies"] if c["slug"] == company), None)
        return self._decorate_questions(res["questions"], company, (cat or {}).get("name", company), res["period"])

    # ---- personal saved/bookmark list (across companies) ----
    def get_bookmarks(self):
        return list((load_config().get("bookmarks") or {}).values())

    def toggle_bookmark(self, rec):
        rec = rec or {}
        slug = (rec.get("slug") or "").strip()
        if not slug:
            return {"ok": False}
        cfg = load_config()
        bm = cfg.setdefault("bookmarks", {})
        if slug in bm:
            del bm[slug]
            on = False
        else:
            bm[slug] = {
                "slug": slug, "title": rec.get("title", ""), "url": rec.get("url", ""),
                "difficulty": rec.get("difficulty", ""), "frequency": rec.get("frequency", 0) or 0,
                "acceptance": rec.get("acceptance", ""),
                "company": rec.get("company", ""), "company_name": rec.get("company_name", ""),
            }
            on = True
        save_config(cfg)
        return {"ok": True, "bookmarked": on}

    def saved_questions(self):
        qs = list((load_config().get("bookmarks") or {}).values())
        qs.sort(key=lambda x: x.get("frequency", 0) or 0, reverse=True)
        return self._decorate_questions(qs, "__saved", "My saved list", "saved")

    # ---- multi-company target sheet (placement shortlist) ----
    def get_targets(self):
        targets = load_config().get("targets") or []
        names = {c["slug"]: c["name"] for c in companies.list_companies()["companies"]}
        return [{"slug": s, "name": names.get(s, s)} for s in targets if s in names]

    def set_targets(self, slugs):
        valid = {c["slug"] for c in companies.list_companies()["companies"]}
        # de-dupe, keep order, validate, cap at 8 (a focused shortlist)
        seen, out = set(), []
        for s in (slugs or []):
            if s in valid and s not in seen:
                seen.add(s)
                out.append(s)
        out = out[:8]
        cfg = load_config()
        cfg["targets"] = out
        save_config(cfg)
        return {"ok": True, "targets": out}

    def target_questions(self, period="all"):
        targets = load_config().get("targets") or []
        if not targets:
            return {"ok": False, "error": "Pick some target companies first."}
        names = {c["slug"]: c["name"] for c in companies.list_companies()["companies"]}
        merged = {}  # slug -> merged question (with the set of asking companies)
        for slug in targets:
            res = companies.fetch(slug, period, STATE_DIR)
            if not res.get("ok"):
                continue
            cname = names.get(slug, slug)
            for q in res["questions"]:
                m = merged.get(q["slug"])
                if not m:
                    m = {"id": q.get("id", ""), "slug": q["slug"], "title": q.get("title", ""),
                         "difficulty": q.get("difficulty", ""), "url": q.get("url", ""),
                         "acceptance": q.get("acceptance", ""), "companies": [], "_freqs": []}
                    merged[q["slug"]] = m
                if cname not in m["companies"]:
                    m["companies"].append(cname)
                m["_freqs"].append(q.get("frequency", 0) or 0)
                if not m["difficulty"] and q.get("difficulty"):
                    m["difficulty"] = q["difficulty"]
        if not merged:  # every fetch failed (e.g. offline) — don't look "all solved"
            return {"ok": False, "error": "Couldn't load your target companies (check your connection)."}
        qs = []
        for m in merged.values():
            m["company_count"] = len(m["companies"])
            m["companies"] = sorted(m["companies"])
            m["frequency"] = max(m["_freqs"]) if m["_freqs"] else 0
            m.pop("_freqs", None)
            qs.append(m)
        # most-overlapping (asked by the most of your targets) first, then frequency
        qs.sort(key=lambda x: (x["company_count"], x["frequency"]), reverse=True)
        dec = self._decorate_questions(qs, "__targets",
                                       f"{len(targets)} target companies", "merged")
        dec["targets"] = [names.get(s, s) for s in targets]
        return dec

    # ---- auto study plan ----
    def _questions_for(self, source, period):
        if source == "__targets":
            return self.target_questions(period)
        if source == "__saved":
            return self.saved_questions()
        return self.company_questions(source, period)

    @staticmethod
    def _topic_weakness(questions):
        """Per-topic weakness over a view: 1 - solved/total. Returns
        (weights dict, weak_topics display list sorted weakest-first)."""
        tot, solv = {}, {}
        for q in questions:
            for t in q.get("topics", []):
                tot[t] = tot.get(t, 0) + 1
                if q.get("solved"):
                    solv[t] = solv.get(t, 0) + 1
        weights = {t: 1.0 - (solv.get(t, 0) / tot[t]) for t in tot}
        # Display the weakest reasonably-common topics (enough signal to matter).
        common = [t for t in tot if tot[t] >= 3]
        common.sort(key=lambda t: (weights[t], tot[t]), reverse=True)
        weak = [{"topic": t, "solved": solv.get(t, 0), "total": tot[t],
                 "pct": round(100 * solv.get(t, 0) / tot[t])} for t in common[:6]]
        return weights, weak

    def build_study_plan(self, source, period="all", weeks=4, per_day=3,
                         include_solved=False, topic_weighted=False):
        r = self._questions_for(source, period)
        if not r.get("ok"):
            return r
        weights, weak = (None, [])
        if topic_weighted:
            weights, weak = self._topic_weakness(r["questions"])
        plan = studyplan.build(r["questions"], weeks, per_day, include_solved, weights=weights)
        if not plan["total"]:
            return {"ok": False, "error": "Nothing to schedule — you've solved everything here, "
                    "or try including solved questions / a longer window."}
        plan.update({
            "source": source, "company": r.get("company", source),
            "name": r.get("name", source), "period": r.get("period", period),
            "topic_weighted": bool(topic_weighted), "weak_topics": weak,
            "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        })
        cfg = load_config()
        cfg["study_plan"] = plan
        save_config(cfg)
        # decorate() mutates; work on a copy so the stored plan stays free of
        # time-dependent fields.
        return studyplan.decorate(json.loads(json.dumps(plan)), _solved_leetcode_slugs())

    def get_study_plan(self):
        plan = load_config().get("study_plan")
        if not plan:
            return {"ok": False}
        return studyplan.decorate(json.loads(json.dumps(plan)), _solved_leetcode_slugs())

    def clear_study_plan(self):
        cfg = load_config()
        cfg.pop("study_plan", None)
        save_config(cfg)
        return {"ok": True}

    def interview_score(self, history, pid, code="", elapsed_sec=0):
        prob = problems.get(pid) or {}
        test_section = ""
        if code and code.strip() and pid in problems.TESTED:
            tr = problems.run_tests(code, pid)
            v = "ALL TESTS PASSED" if tr.get("ok") else f"{tr.get('passed', 0)}/{tr.get('total', 0)} passed"
            test_section = f"## Automated test results\n{v}\n\n"
        mins = max(0, int(elapsed_sec)) // 60
        prompt = (
            "You are a senior interviewer writing the post-interview scorecard. Be fair, specific and "
            "constructive — cite concrete moments from the transcript. Reply in GitHub-flavored Markdown "
            "with EXACTLY these sections:\n"
            "### 🎯 Overall — X/10\nOne-line verdict and a hire signal (Strong No / No / Lean No / Lean Yes / Yes / Strong Yes).\n"
            "### 🧠 Problem solving\n### 🗣 Communication\n### ⏱ Complexity analysis\n### 🧹 Code quality\n"
            "### ✅ Strengths\n### 📈 To improve\nKeep each section to 1–3 tight bullets.\n\n"
            f"## Problem\n{prob.get('title', '')} ({prob.get('difficulty', '')})\n{prob.get('statement', '')}\n\n"
            f"Time taken: ~{mins} min.\n\n{test_section}"
            f"## Candidate's final code\n```python\n{code or '(none)'}\n```\n\n"
            f"## Transcript\n{self._iv_convo(history)}")
        return _ask(prompt) or _ai_hint()

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

    def review_status(self):
        """Lightweight SRS counts for the launch review nudge."""
        return srs.stats(_items(), STATE_DIR)

    def get_gamify(self):
        return gamify.compute(_items(), STATE_DIR)

    def get_patterns(self):
        return patterns.listing()

    def pattern_problems(self, name):
        """In-app catalog problems matching a library pattern (for drilldown)."""
        topics = set(patterns.topics_for_pattern(name))
        if not topics:
            return {"ok": False, "error": "No problems mapped for this pattern."}
        solved = _solved_leetcode_slugs()
        order = {"Easy": 0, "Medium": 1, "Hard": 2}
        out = []
        for p in problems.listing():
            slug = p["id"]
            if topics & set(companies.topics_for(slug)):
                out.append({"slug": slug, "title": p["title"], "difficulty": p["difficulty"],
                            "tested": bool(p.get("tested")), "solved": slug in solved})
        out.sort(key=lambda x: (order.get(x["difficulty"], 9), x["title"]))
        return {"ok": True, "pattern": name, "topics": sorted(topics), "problems": out,
                "total": len(out), "solved": sum(1 for x in out if x["solved"])}

    def list_problems(self):
        return problems.listing()

    def get_problem(self, pid):
        return problems.get(pid)

    def run_code(self, code, stdin="", lang="python"):
        return runner.run(code or "", lang or "python", stdin or "")

    def lang_status(self):
        """Which languages can run on this machine (for the IDE language picker)."""
        return runner.available()

    def run_tests(self, code, pid):
        return problems.run_tests(code or "", pid)

    def _review_body(self, code, pid, attempt):
        """Build the AI-review prompt. Returns (body, None) or (None, message)."""
        prob = problems.get(pid)
        if not prob:
            return None, "Unknown problem."
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
        return body, None

    def ai_review(self, code, pid, attempt=1):
        body, msg = self._review_body(code, pid, attempt)
        if msg is not None:
            return msg
        return _ask(body) or _ai_hint()

    def ai_review_stream(self, code, pid, attempt=1, stream_id=""):
        body, msg = self._review_body(code, pid, attempt)
        if msg is not None:
            _emit_stream(stream_id, msg)
            return msg
        out = _ask_stream(body, stream_id)
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
