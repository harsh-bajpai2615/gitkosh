"""Headless sync core — shared by the GUI and the scheduled (LaunchAgent) run.

run_sync() discovers new accepted solutions, writes a README for each, and pushes
them to GitHub in one commit. If there are no new solves and keep_streak is on, it
makes a small dated commit to activity/streak.md so the GitHub contribution graph
stays green. Progress is reported via callbacks so the GUI can drive its bar while
the scheduler just logs.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from gitkosh.readme_gen import ReadmeGenerator
from gitkosh.store import Store
from gitkosh.platforms import REGISTRY

from . import github_auth
from .appsupport import save_config
from .dashboard import render as render_dashboard
from .detect import DETECTORS
from .github_api import GitHubAPI
from .native_session import NativeSession
from .site import render as render_site, badges_md
from .study import export_files as export_study


def _iso(ts):
    """Epoch seconds -> ISO-8601 UTC, for backdating commits. None when unknown (0)."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return None


def _index_readme(sub) -> str:
    """README for index-only entries (e.g. GeeksforGeeks) — no source code exists."""
    parts = [f"# {sub.title}", "", f"- **Platform:** {sub.platform}", f"- **Link:** {sub.url}"]
    if sub.difficulty:
        parts.append(f"- **Difficulty:** {sub.difficulty}")
    if sub.tags:
        parts.append(f"- **Tags:** {', '.join(sub.tags)}")
    if sub.statement:
        parts += ["", "## Problem", "", sub.statement]
    parts += ["", "_Solved on this platform. (Source code isn't exposed by the platform, "
              "so this is an index entry.)_",
              "", "<sub>synced by [GitKosh](https://github.com/harsh-bajpai2615/gitkosh)</sub>"]
    return "\n".join(parts) + "\n"


def _approach(md: str) -> str:
    """Pull the Algorithm / Approach / Key Insight sections from a README for study cards."""
    parts = []
    for header in ("Algorithm", "Approach", "Key Insight"):
        m = re.search(rf"^#+\s*{header}\s*$(.*?)(?=^#+\s|\Z)", md or "", re.M | re.S)
        if m and m.group(1).strip():
            parts.append(m.group(1).strip())
    return "\n".join(parts).strip()[:1500]

CP = ["leetcode", "codeforces", "codechef", "neetcode", "atcoder", "geeksforgeeks"]
DOMAINS = {"leetcode": "leetcode.com", "codeforces": "codeforces.com",
           "codechef": "codechef.com", "neetcode": "neetcode.io",
           "atcoder": "atcoder.jp", "geeksforgeeks": "geeksforgeeks.org"}
LABELS = {"leetcode": "LeetCode", "codeforces": "Codeforces",
          "codechef": "CodeChef", "neetcode": "NeetCode",
          "atcoder": "AtCoder", "geeksforgeeks": "GeeksforGeeks"}


def connected_platforms(state_dir) -> dict:
    p = Path(state_dir) / "storage_state.json"
    domains = set()
    if p.exists():
        try:
            for c in json.loads(p.read_text()).get("cookies", []):
                domains.add(c.get("domain", ""))
        except Exception:  # noqa: BLE001
            pass
    return {n: any(d in dom for dom in domains) for n, d in DOMAINS.items()}


def _noop(*a, **k):
    pass


def _write_last(state_dir, result):
    try:
        out = dict(result)
        out["at"] = datetime.now().isoformat(timespec="seconds")
        (Path(state_dir) / "last_run.json").write_text(json.dumps(out))
    except Exception:  # noqa: BLE001
        pass


def read_last_run(state_dir):
    p = Path(state_dir) / "last_run.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return None
    return None


def _keep_streak(gh: GitHubAPI, log) -> bool:
    today = date.today().isoformat()
    prev = gh.get_file_text("activity/streak.md")
    if today in prev:
        log(f"Streak already kept today ({today}).")
        return False
    line = f"- {today}: kept active (automatic)\n"
    content = (prev + line) if prev else ("# Activity\n\nDays this repo stayed active:\n\n" + line)
    gh.push({"activity/streak.md": content}, f"chore: keep streak {today}")
    log(f"No new solves — pushed a keep-streak commit for {today}.")
    return True


def run_sync(cfg, state_dir, *, stop_on_seen=True, limit=0, keep_streak=False, reset=False,
             log=print, progress=_noop, should_stop=lambda: False) -> dict:
    result = {"found": 0, "pushed": 0, "streak": False, "error": None, "url": None}
    if reset:
        stop_on_seen, limit = False, 0  # re-pull everything

    gh_info = github_auth.load_github(state_dir)
    if not gh_info:
        result["error"] = "not signed into GitHub"
        progress("done", text="Sign into GitHub first.", ok=False)
        _write_last(state_dir, result); return result
    session = NativeSession(state_dir)
    if not session.has_state():
        result["error"] = "no coding-platform login"
        progress("done", text="Log into a coding platform first.", ok=False)
        _write_last(state_dir, result); return result

    progress("busy", text="Preparing…")
    rg = ReadmeGenerator(cfg["readme"])
    ok, err = rg.self_test()
    if not ok:
        log(f"⚠️  Write-ups ({rg.provider}) not working: {err} — READMEs will be plain.")

    gh = GitHubAPI(gh_info["token"], cfg["github"]["repo"], private=cfg["github"].get("private", True))
    progress("busy", text="Preparing GitHub repo…")
    try:
        log(f"GitHub repo: {gh.ensure_repo()}")
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
        progress("done", text=f"GitHub error: {e}", ok=False)
        _write_last(state_dir, result); return result

    store = Store(state_dir)
    if reset:
        log("Reset: clearing local history and rebuilding the repo with real solve dates…")
        store.clear()
    logged = connected_platforms(state_dir)

    # discover
    progress("busy", text="Fetching your submissions…", sub="0 found")
    subs = []
    for name in CP:
        if not logged.get(name):
            continue
        if name == "neetcode" and not logged.get("leetcode"):
            log("[neetcode] needs LeetCode login too — skipping"); continue
        log(f"[{name}] fetching…")
        platcfg = dict(cfg.get("platforms", {}).get(name, {}))
        if name in DETECTORS and not platcfg.get("handle"):
            h = DETECTORS[name](session)
            if not h:
                log(f"  ! couldn't detect {name} handle — skipping"); continue
            platcfg["handle"] = h
            cfg.setdefault("platforms", {}).setdefault(name, {})["handle"] = h
            save_config(cfg)
        plat = REGISTRY[name](session, platcfg, None)
        try:
            it = plat.recent() if stop_on_seen else plat.backfill()
            for sub in it:
                if should_stop():
                    break
                if not sub.code.strip() and not sub.extra.get("list_only"):
                    continue
                if store.seen(sub.key):
                    if stop_on_seen:
                        break
                    continue
                subs.append((name, sub))
                progress("busy", text="Fetching your submissions…", sub=f"{len(subs)} found")
                if limit and len(subs) >= limit:
                    break
        except Exception as e:  # noqa: BLE001
            log(f"  ! {name} error: {e}")
        if limit and len(subs) >= limit:
            break
    result["found"] = len(subs)

    # generate READMEs + build one backdated commit per problem (real solve date)
    done, commits = [], []
    if subs:
        total = len(subs)
        log(f"Found {total} new problem(s).")
        for i, (name, sub) in enumerate(sorted(subs, key=lambda x: x[1].timestamp or 0), 1):
            if should_stop():
                break
            progress("step", i=i, n=total, text="Writing READMEs",
                     sub=f"{LABELS.get(name, name)}: {sub.title}")
            base = f"{name}/{sub.dirname}"
            if sub.code.strip():
                readme = rg.generate(sub)
                files = {f"{base}/solution.{sub.ext}": sub.code, f"{base}/README.md": readme}
            else:  # index-only entry (e.g. GeeksforGeeks — no source available)
                readme = _index_readme(sub)
                files = {f"{base}/README.md": readme}
            commits.append({
                "files": files,
                "message": f"{LABELS.get(name, name)}: {sub.title}" + (f" ({sub.lang})" if sub.lang else ""),
                "date": _iso(sub.timestamp),
            })
            done.append((name, sub, readme))
            log(f"  ✓ {base}")

    if done:
        progress("busy", text=f"Committing {len(done)} problem(s) (backdated to solve days)…")
        try:
            url = gh.push_commits(commits, orphan=reset, force=reset)
            for name, sub, readme in done:
                store.mark(sub.key, {
                    "platform": sub.platform, "title": sub.title,
                    "difficulty": sub.difficulty, "tags": sub.tags, "lang": sub.lang,
                    "url": sub.url, "dir": f"{name}/{sub.dirname}", "timestamp": sub.timestamp,
                    "approach": _approach(readme),
                })
            result["pushed"], result["url"] = len(done), url
            log(f"✓ Pushed {len(done)} problem(s), dated to the days you solved them. {url}")
            progress("busy", text="Updating dashboard, study exports & showcase…")
            try:
                allitems = store.all()
                owner, repo = gh._resolve()
                final = {"README.md": render_dashboard(allitems)}
                final.update(export_study(allitems))
                final["docs/index.html"] = render_site(allitems, owner, repo)
                final["docs/.nojekyll"] = ""
                final["profile/badges.md"] = badges_md(allitems, owner, repo)
                try:  # Pillow-rendered card (optional — only in the app bundle)
                    from .cards import render_png
                    final["profile/stats.png"] = render_png(allitems, username=owner)
                except Exception as e:  # noqa: BLE001
                    log(f"  (stats card skipped: {e})")
                gh.push_commits([{"files": final,
                                  "message": "GitKosh: update dashboard, study exports & showcase",
                                  "date": None}])
            except Exception as e:  # noqa: BLE001
                log(f"  (dashboard update skipped: {e})")
            progress("done", text=f"✓ Done — pushed {len(done)} problem(s).", ok=True)
        except Exception as e:  # noqa: BLE001
            result["error"] = str(e)
            log(f"Push failed: {e}")
            progress("done", text=f"Push failed: {e}", ok=False)
    else:
        if keep_streak:
            try:
                result["streak"] = _keep_streak(gh, log)
                progress("done", text="✓ No new solves — kept your streak alive.", ok=True)
            except Exception as e:  # noqa: BLE001
                result["error"] = str(e)
                log(f"Streak commit failed: {e}")
                progress("done", text=f"Streak commit failed: {e}", ok=False)
        else:
            log("Nothing new to sync.")
            progress("done", text="✓ Up to date — nothing new.", ok=True)

    _write_last(state_dir, result)
    return result
