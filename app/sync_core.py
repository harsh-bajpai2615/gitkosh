"""Headless sync core — shared by the GUI and the scheduled (LaunchAgent) run.

run_sync() discovers new accepted solutions, writes a README for each, and pushes
them to GitHub in one commit. If there are no new solves and keep_streak is on, it
makes a small dated commit to activity/streak.md so the GitHub contribution graph
stays green. Progress is reported via callbacks so the GUI can drive its bar while
the scheduler just logs.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from codesync.readme_gen import ReadmeGenerator
from codesync.store import Store
from codesync.platforms import REGISTRY

from . import github_auth
from .appsupport import save_config
from .detect import DETECTORS
from .github_api import GitHubAPI
from .native_session import NativeSession

CP = ["leetcode", "codeforces", "codechef", "neetcode"]
DOMAINS = {"leetcode": "leetcode.com", "codeforces": "codeforces.com",
           "codechef": "codechef.com", "neetcode": "neetcode.io"}
LABELS = {"leetcode": "LeetCode", "codeforces": "Codeforces",
          "codechef": "CodeChef", "neetcode": "NeetCode"}


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


def run_sync(cfg, state_dir, *, stop_on_seen=True, limit=0, keep_streak=False,
             log=print, progress=_noop, should_stop=lambda: False) -> dict:
    result = {"found": 0, "pushed": 0, "streak": False, "error": None, "url": None}

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
                if not sub.code.strip():
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

    # write READMEs
    files, done = {}, []
    if subs:
        total = len(subs)
        log(f"Found {total} new problem(s).")
        for i, (name, sub) in enumerate(subs, 1):
            if should_stop():
                break
            progress("step", i=i, n=total, text="Writing READMEs",
                     sub=f"{LABELS.get(name, name)}: {sub.title}")
            base = f"{name}/{sub.dirname}"
            files[f"{base}/solution.{sub.ext}"] = sub.code
            files[f"{base}/README.md"] = rg.generate(sub)
            done.append(sub)
            log(f"  ✓ {base}")

    if files:
        progress("busy", text=f"Pushing {len(done)} problem(s) to GitHub…")
        try:
            url = gh.push(files, f"codesync: {len(done)} solution(s)")
            for sub in done:
                store.mark(sub.key, {"platform": sub.platform, "timestamp": sub.timestamp, "title": sub.title})
            result["pushed"], result["url"] = len(done), url
            log(f"✓ Pushed {len(done)} problem(s). {url}")
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
