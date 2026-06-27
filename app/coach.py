"""Problem-of-the-Day / coaching recommendations.

Surfaces what to do next: review cards that are due, the next unsolved problem from
the NeetCode 150 path, and your weakest topics.
"""
from __future__ import annotations

from . import srs
from .insights import analytics
from .roadmap import NEETCODE150, _title, solved_slugs


def potd(items, state_dir):
    st = srs.stats(items, state_dir)
    solved = solved_slugs(items)
    nxt = None
    for s in NEETCODE150:
        if s not in solved:
            nxt = {"title": _title(s), "slug": s, "sheet": "NeetCode 150",
                   "url": f"https://leetcode.com/problems/{s}/"}
            break
    a = analytics(items)
    return {"due": st["due"], "review_streak": st["review_streak"],
            "next": nxt, "weak": (a.get("growth") or [])[:3]}
