"""Import a local folder's REAL past work onto your GitHub contribution graph.

Honest backdating only: every commit is dated to when the work actually happened —
the file's real modification time, or (for a git repo) the real author date of the
commit that last touched it. This surfaces work you genuinely did but never pushed.
It is NOT a fabricated-history generator: dates come from your filesystem/git, are
clamped to never be in the future, and nothing is invented.

Foundation: GitHubAPI.push_commits() turns a list of {files, message, date} into a
chain of backdated commits, so one day of work becomes one dated commit.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Directories that are never the user's own authored work.
IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "dist", "build", "out",
    "__pycache__", ".idea", ".vscode", ".next", ".nuxt", ".cache", "target",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "vendor", ".gradle", "Pods",
    "DerivedData", ".terraform", "bin", "obj", "coverage", ".parcel-cache",
}
MAX_FILE_BYTES = 1_000_000   # skip files larger than ~1 MB (build artifacts, data dumps)
MAX_FILES = 5000             # safety cap on a single import
_TEXT_SAMPLE = 4096


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _iso(ts) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def _day(ts) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-") or "project"


def _is_probably_text(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(_TEXT_SAMPLE)
    except OSError:
        return False
    return b"\x00" not in chunk  # NUL byte ⇒ binary


def _git_file_dates(root: Path) -> dict:
    """Map each tracked file (posix relpath) -> the author unix-time of the most
    recent commit touching it. Empty dict if not a git repo / git unavailable."""
    out: dict = {}
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "log", "--no-merges", "--pretty=format:%at", "--name-only"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return out
    if res.returncode != 0:
        return out
    # Output per commit: a %at timestamp line, then its changed files, then a blank
    # separator. Track position (the first line after a blank is the timestamp) rather
    # than guessing by isdigit() — a file literally named "123456789" must not be read
    # as a timestamp.
    cur_ts = None
    expect_ts = True
    for line in res.stdout.splitlines():
        if not line.strip():
            expect_ts = True
            continue
        if expect_ts:
            try:
                cur_ts = int(line.strip())
            except ValueError:
                cur_ts = None
            expect_ts = False
        elif cur_ts is not None and line not in out:  # newest wins (log is newest-first)
            out[line] = cur_ts
    return out


def scan(path: str) -> dict:
    """Walk `path`, grouping authored text files by the UTC day they were last worked
    on. Returns {ok, name, root, buckets, total_files, total_days, skipped, oldest,
    newest, capped} — buckets maps day -> [{rel, abs, ts, size}]."""
    root = Path(path).expanduser()
    try:
        root = root.resolve()
    except OSError:
        return {"ok": False, "error": "Couldn't read that folder."}
    if not root.is_dir():
        return {"ok": False, "error": "That isn't a folder."}

    git_dates = _git_file_dates(root) if (root / ".git").exists() else {}
    is_git = bool(git_dates)
    buckets = defaultdict(list)
    total = skipped = 0
    capped = False
    now = _now_ts()

    for dirpath, dirs, files in os.walk(root):
        # prune ignored + hidden directories in place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                skipped += 1
                continue
            ap = Path(dirpath) / fn
            try:
                st = ap.stat()
            except OSError:
                skipped += 1
                continue
            if st.st_size == 0 or st.st_size > MAX_FILE_BYTES:
                skipped += 1
                continue
            rel = ap.relative_to(root).as_posix()
            ts = git_dates.get(rel, st.st_mtime)
            ts = min(int(ts), now)  # never date a commit in the future
            if not _is_probably_text(ap):
                skipped += 1
                continue
            if total >= MAX_FILES:
                capped = True
                break
            buckets[_day(ts)].append({"rel": rel, "abs": str(ap), "ts": ts, "size": st.st_size})
            total += 1
        if capped:
            break

    days = sorted(buckets)
    return {
        "ok": True,
        "name": root.name,
        "root": str(root),
        "is_git": is_git,
        "buckets": dict(buckets),
        "total_files": total,
        "total_days": len(days),
        "skipped": skipped,
        "capped": capped,
        "oldest": days[0] if days else None,
        "newest": days[-1] if days else None,
    }


def summarize(scan_result: dict, sample: int = 12) -> dict:
    """A lightweight, JSON-friendly preview for the UI (no file contents)."""
    if not scan_result.get("ok"):
        return scan_result
    buckets = scan_result["buckets"]
    days = sorted(buckets)
    rows = [{"date": d, "count": len(buckets[d])} for d in days]
    # Show the most recent `sample` days in the preview table.
    preview = rows[-sample:][::-1]
    return {
        "ok": True,
        "name": scan_result["name"],
        "root": scan_result["root"],
        "is_git": scan_result["is_git"],
        "total_files": scan_result["total_files"],
        "total_days": scan_result["total_days"],
        "skipped": scan_result["skipped"],
        "capped": scan_result["capped"],
        "oldest": scan_result["oldest"],
        "newest": scan_result["newest"],
        "preview": preview,
    }


def build_commits(scan_result: dict, dest_prefix: str = None) -> list:
    """Turn a scan into push_commits() input — one backdated commit per day."""
    if not scan_result.get("ok"):
        return []
    name = scan_result["name"]
    prefix = (dest_prefix or f"imports/{_slug(name)}").rstrip("/")
    buckets = scan_result["buckets"]
    commits = []
    for day in sorted(buckets):
        files = {}
        latest = 0
        for f in buckets[day]:
            try:
                txt = Path(f["abs"]).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files[f"{prefix}/{f['rel']}"] = txt
            latest = max(latest, f["ts"])
        if files:
            n = len(files)
            commits.append({
                "files": files,
                "message": f"import: {name} — {day} ({n} file{'s' if n != 1 else ''})",
                "date": _iso(latest),
            })
    return commits
