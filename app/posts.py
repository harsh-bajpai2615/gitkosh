"""Generate shareable progress posts (dev.to / LinkedIn / X) from recent solves.

Uses the configured LLM for a polished draft when available, with a clean
template fallback so it always produces something. Returns both a long post and a
short (tweet-length) version.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .dashboard import LABELS


def _recent(items, days):
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    return [i for i in items if (i.get("timestamp") or 0) >= cutoff]


def _facts(items, days):
    recent = _recent(items, days)
    pool = recent if recent else items
    plats = sorted({LABELS.get(i.get("platform"), i.get("platform") or "?") for i in pool})
    topics = [t for t, _ in Counter(t for i in pool for t in (i.get("tags") or [])).most_common(5)]
    titles = [i.get("title", "") for i in sorted(pool, key=lambda x: x.get("timestamp", 0), reverse=True)][:5]
    return {"recent_n": len(recent), "total": len(items), "platforms": plats,
            "topics": topics, "titles": [t for t in titles if t]}


def _template(f, days, username):
    n = f["recent_n"]
    plats = ", ".join(f["platforms"]) or "my coding platforms"
    topics = ", ".join(f["topics"]) or "a mix of topics"
    if n:
        head = f"## This week in problem-solving 🚀\n\nSolved **{n}** problem(s) on {plats} over the last {days} days — now **{f['total']}** total."
    else:
        head = f"## Problem-solving update 🚀\n\n**{f['total']}** problems solved on {plats} and counting."
    body = f"\n\n**Focus areas:** {topics}."
    if f["titles"]:
        body += "\n\n**Recently:**\n" + "\n".join(f"- {t}" for t in f["titles"])
    body += "\n\n_Archived & documented automatically with [GitKosh](https://github.com/harsh-bajpai2615/gitkosh)._"
    return head + body


def _short(f, days):
    n = f["recent_n"] or f["total"]
    plats = "/".join(p for p in f["platforms"][:3]) or "coding"
    topics = " ".join("#" + t.replace(" ", "") for t in f["topics"][:3])
    when = f"this week" if f["recent_n"] else "so far"
    return f"Solved {n} problems {when} on {plats} 🚀 Focus: {', '.join(f['topics'][:3]) or 'DSA'}. {topics} #coding #leetcode"


def generate(items, rg=None, days=7, username="") -> dict:
    f = _facts(items, days)
    post = ""
    if rg is not None:
        prompt = (
            "Write a short, upbeat first-person social post (max ~120 words, Markdown, no hashtags) "
            "celebrating my recent competitive-programming progress. Be specific and humble, not salesy.\n"
            f"- problems solved in last {days} days: {f['recent_n']}\n"
            f"- total solved: {f['total']}\n"
            f"- platforms: {', '.join(f['platforms'])}\n"
            f"- top topics: {', '.join(f['topics'])}\n"
            f"- recent problems: {', '.join(f['titles'])}\n"
            "End with one short line crediting GitKosh."
        )
        try:
            post = rg.freeform(prompt)
        except Exception:  # noqa: BLE001
            post = ""
    if not post:
        post = _template(f, days, username)
    return {"post": post, "short": _short(f, days)}
