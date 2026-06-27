"""Generate the repo's top-level README dashboard from the solved-problem store.

Renders an at-a-glance portfolio: totals, per-platform + difficulty + language
breakdowns, top tags, solving streak, and a per-platform index of every problem.
Degrades gracefully when older entries lack some fields.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

LABELS = {"leetcode": "LeetCode", "codeforces": "Codeforces",
          "codechef": "CodeChef", "neetcode": "NeetCode",
          "atcoder": "AtCoder", "geeksforgeeks": "GeeksforGeeks"}


def _d(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    except Exception:  # noqa: BLE001
        return None


def _streaks(days):
    """(current_streak, longest_streak) over a set of date objects."""
    if not days:
        return 0, 0
    s = sorted(set(days))
    longest = run = 1
    for a, b in zip(s, s[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        longest = max(longest, run)
    # current streak: consecutive days ending today or yesterday
    today = datetime.now(timezone.utc).date()
    if s[-1] < today - timedelta(days=1):
        return 0, longest
    cur, d = 1, s[-1]
    sset = set(s)
    while d - timedelta(days=1) in sset:
        cur += 1
        d -= timedelta(days=1)
    return cur, longest


def _bar(n, total, width=20):
    if not total:
        return ""
    filled = round(width * n / total)
    return "█" * filled + "░" * (width - filled)


def render(items: list, repo_slug: str = "") -> str:
    total = len(items)
    if total == 0:
        return "# Competitive Programming\n\n_Solutions will appear here after your first GitKosh sync._\n"

    plat = Counter(i.get("platform", "?") for i in items)
    langs = Counter((i.get("lang") or "").strip() for i in items if (i.get("lang") or "").strip())
    diff = Counter(i.get("difficulty", "") for i in items if i.get("difficulty") in ("Easy", "Medium", "Hard"))
    tags = Counter(t for i in items for t in (i.get("tags") or []))
    days = [d for d in (_d(i.get("timestamp")) for i in items) if d]
    cur, longest = _streaks(days)
    last = max(days) if days else None

    out = []
    out.append("# 🧩 Competitive Programming\n")
    out.append(f"> **{total}** solutions, auto-synced from "
               f"{', '.join(LABELS.get(p, p) for p in plat)} by "
               f"[GitKosh](https://github.com/harsh-bajpai2615/gitkosh).\n")

    # headline stats
    out.append("| Solved | Current streak | Longest streak | Active days | Last solved |")
    out.append("|:--:|:--:|:--:|:--:|:--:|")
    out.append(f"| **{total}** | 🔥 {cur} day{'s' if cur != 1 else ''} | {longest} day{'s' if longest != 1 else ''} "
               f"| {len(set(days))} | {last.isoformat() if last else '—'} |\n")

    # by platform
    out.append("### By platform\n")
    out.append("| Platform | Solved |")
    out.append("|:--|:--:|")
    for p, n in plat.most_common():
        out.append(f"| {LABELS.get(p, p)} | {n} |")
    out.append("")

    # by difficulty
    if diff:
        out.append("### By difficulty\n")
        for level in ("Easy", "Medium", "Hard"):
            n = diff.get(level, 0)
            out.append(f"- **{level}** `{_bar(n, sum(diff.values()))}` {n}")
        out.append("")

    # languages
    if langs:
        out.append("### Languages\n")
        out.append(" · ".join(f"{l} ({n})" for l, n in langs.most_common()))
        out.append("")

    # top tags
    if tags:
        out.append("### Top topics\n")
        out.append(" · ".join(f"`{t}` {n}" for t, n in tags.most_common(15)))
        out.append("")

    # browse by topic — the interview-prep "patterns" view
    if tags:
        out.append("## Browse by topic\n")
        for t, n in tags.most_common(20):
            rows = sorted((i for i in items if t in (i.get("tags") or [])),
                          key=lambda i: i.get("timestamp", 0), reverse=True)
            out.append(f"<details><summary><b>{t}</b> ({n})</summary>\n")
            for i in rows:
                d = i.get("dir")
                title = i.get("title", "—")
                out.append(f"- [{title}](./{d})" if d else f"- {title}")
            out.append("\n</details>\n")

    # index per platform
    out.append("## All solutions\n")
    for p, _ in plat.most_common():
        rows = [i for i in items if i.get("platform") == p]
        rows.sort(key=lambda i: i.get("timestamp", 0), reverse=True)
        out.append(f"<details><summary><b>{LABELS.get(p, p)}</b> ({len(rows)})</summary>\n")
        out.append("| Problem | Difficulty | Language | Solved |")
        out.append("|:--|:--:|:--:|:--:|")
        for i in rows:
            title = i.get("title", "—")
            d = i.get("dir")
            name = f"[{title}](./{d})" if d else title
            dt = _d(i.get("timestamp"))
            out.append(f"| {name} | {i.get('difficulty', '') or '—'} | {i.get('lang', '') or '—'} "
                       f"| {dt.isoformat() if dt else '—'} |")
        out.append("\n</details>\n")

    out.append("---")
    out.append("<sub>Synced & documented automatically with "
               "[GitKosh](https://github.com/harsh-bajpai2615/gitkosh).</sub>")
    return "\n".join(out) + "\n"
