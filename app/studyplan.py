"""Auto study plan — turn a company / target / saved question list into a dated schedule.

Distributes the highest-priority unsolved questions across N weeks with a balanced
mix of difficulties each day, so a student gets a concrete daily target instead of a
wall of problems. The plan is stored in config and tracked against synced solves.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import companies

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_ROTATION = ["Easy", "Medium", "Hard"]


def _today():
    return datetime.now(timezone.utc).date()


def solved_slugs(items) -> set:
    """LeetCode slugs the user has actually solved (from synced history)."""
    out = set()
    for it in items or []:
        if it.get("platform") != "leetcode":
            continue
        slug = companies.slug_from_url(it.get("url") or "")
        if not slug:
            base = (it.get("dir") or "").split("/")[-1]
            slug = re.sub(r"^\d+-", "", base)
        if slug:
            out.add(slug)
    return out


def _item(q) -> dict:
    it = {
        "slug": q.get("slug", ""), "title": q.get("title", ""), "url": q.get("url", ""),
        "difficulty": q.get("difficulty", ""), "frequency": q.get("frequency", 0) or 0,
        "in_app": bool(q.get("in_app")),
    }
    if q.get("companies"):
        it["companies"] = q["companies"]
    return it


def build(questions, weeks=4, per_day=3, include_solved=False, weights=None, start=None) -> dict:
    """Schedule `questions` (already priority-ordered) into a dated plan.

    Each day gets up to per_day items with a balanced Easy/Medium/Hard mix, while
    high-frequency/high-overlap problems still land early.

    If `weights` is given (topic -> weakness in 0..1), questions touching weak
    topics are boosted so the plan emphasizes the patterns you're weakest at.
    """
    weeks = max(1, min(int(weeks or 4), 26))
    per_day = max(1, min(int(per_day or 3), 15))
    start = start or _today()
    pool = [q for q in questions if include_solved or not q.get("solved")]
    if weights and pool:
        # Blend topic weakness with (normalized) frequency so weak patterns are
        # genuinely emphasized while still-important common problems stay in play.
        maxf = max((q.get("frequency", 0) or 0 for q in pool), default=1) or 1
        def _score(q):
            w = max((weights.get(t, 0.0) for t in (q.get("topics") or [])), default=0.0)
            fn = (q.get("frequency", 0) or 0) / maxf
            return 0.55 * w + 0.45 * fn
        pool = sorted(pool, key=_score, reverse=True)
    selected = pool[:weeks * 7 * per_day]

    # Interleave difficulties (priority preserved within each) for balanced days.
    buckets = {"Easy": [], "Medium": [], "Hard": []}
    other = []
    for q in selected:
        d = q.get("difficulty")
        (buckets[d] if d in buckets else other).append(q)
    order = []
    while any(buckets[d] for d in _ROTATION) or other:
        for d in _ROTATION:
            if buckets[d]:
                order.append(buckets[d].pop(0))
        if other:
            order.append(other.pop(0))

    days = []
    for i in range(0, len(order), per_day):
        di = i // per_day
        date = start + timedelta(days=di)
        days.append({
            "date": date.isoformat(),
            "weekday": WEEKDAYS[date.weekday()],
            "items": [_item(q) for q in order[i:i + per_day]],
        })
    return {"weeks": weeks, "per_day": per_day, "include_solved": bool(include_solved),
            "days": days, "total": len(order)}


def decorate(plan: dict, solved: set) -> dict:
    """Annotate a stored plan with solved status + progress (non-persistent)."""
    today = _today().isoformat()
    done = tot = 0
    today_pending = today_total = 0
    for day in plan.get("days", []):
        d_done = 0
        for it in day["items"]:
            it["solved"] = it["slug"] in solved
            tot += 1
            if it["solved"]:
                done += 1
                d_done += 1
        day["done"] = d_done
        day["total"] = len(day["items"])
        day["is_today"] = day["date"] == today
        day["is_past"] = day["date"] < today
        if day["is_today"]:
            today_total = day["total"]
            today_pending = day["total"] - d_done
    plan["ok"] = True
    plan["progress"] = {
        "done": done, "total": tot,
        "pct": round(100 * done / tot) if tot else 0,
        "today_pending": today_pending, "today_total": today_total,
    }
    return plan
