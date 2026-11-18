"""Analytics & insights derived from the solved-problem store.

Powers the in-app Insights tab and a committed insights.md: topic strengths,
difficulty mastery, solving pace/trend, optimality (from the AI coach), a
"revisit" list, and résumé-ready bullets. Pure-Python; degrades gracefully when
older entries lack difficulty/tags/optimal.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from . import companies
from .dashboard import _d, _streaks, LABELS

DIFFS = ("Easy", "Medium", "Hard")


def topic_strength(items: list, top: int = 14) -> dict:
    """Per-topic strength from solved problems: count, difficulty mix, a relative
    strength score (difficulty-weighted, 0..100 vs your strongest topic), and
    coverage vs all LeetCode problems in that topic. Plus 'underexplored': common
    topics you've barely touched."""
    by = {}
    for i in items:
        d = i.get("difficulty")
        for t in (i.get("tags") or []):
            e = by.setdefault(t, {"solved": 0, "Easy": 0, "Medium": 0, "Hard": 0})
            e["solved"] += 1
            if d in DIFFS:
                e[d] += 1
    totals = companies.topic_totals()
    rows, max_pts = [], 1
    for t, e in by.items():
        pts = e["Easy"] + 2 * e["Medium"] + 3 * e["Hard"]
        max_pts = max(max_pts, pts)
        rows.append({"topic": t, "solved": e["solved"], "easy": e["Easy"], "med": e["Medium"],
                     "hard": e["Hard"], "total": totals.get(t, 0), "_pts": pts})
    for r in rows:
        r["strength"] = round(100 * r["_pts"] / max_pts)
        r["coverage"] = round(100 * r["solved"] / r["total"]) if r["total"] else None
        r.pop("_pts")
    rows.sort(key=lambda r: (r["solved"], r["strength"]), reverse=True)

    # Underexplored: common topics you've barely touched, but don't flag ones
    # you're already strong in (a huge denominator can make a top topic look thin).
    strong = {r["topic"] for r in rows if r["strength"] >= 50}
    under = []
    for t, tot in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        if tot < 40 or t in strong:  # only common, interview-relevant topics
            continue
        s = by.get(t, {}).get("solved", 0)
        if s / tot < 0.05:  # under 5% of that topic touched
            under.append({"topic": t, "total": tot, "solved": s})
        if len(under) >= 6:
            break
    return {"topics": rows[:top], "underexplored": under, "count": len(rows)}


def _recent(items, days):
    cut = datetime.now(timezone.utc).timestamp() - days * 86400
    return [i for i in items if (i.get("timestamp") or 0) >= cut]


def analytics(items: list) -> dict:
    total = len(items)
    plat = Counter(i.get("platform", "?") for i in items)
    langs = Counter((i.get("lang") or "").strip() for i in items if (i.get("lang") or "").strip())
    diff = Counter(i.get("difficulty") for i in items if i.get("difficulty") in DIFFS)
    tags = Counter(t for i in items for t in (i.get("tags") or []))
    days = [x for x in (_d(i.get("timestamp")) for i in items) if x]
    cur, longest = _streaks(days)

    # pace / trend
    wk, prev_wk = len(_recent(items, 7)), len(_recent(items, 14)) - len(_recent(items, 7))
    mo = len(_recent(items, 30))
    trend = "up" if wk > prev_wk else ("down" if wk < prev_wk else "flat")

    # optimality from the AI coach (optimal: True/False/None)
    coached = [i for i in items if i.get("optimal") is not None]
    optimal = sum(1 for i in coached if i.get("optimal"))
    revisit = [i for i in items if i.get("optimal") is False]

    return {
        "total": total, "platforms": plat, "languages": langs, "difficulty": diff,
        "tags": tags, "current_streak": cur, "longest_streak": longest,
        "active_days": len(set(days)), "week": wk, "prev_week": prev_wk, "month": mo,
        "trend": trend, "coached": len(coached), "optimal": optimal, "revisit": revisit,
        "strengths": [t for t, _ in tags.most_common(6)],
        "growth": [t for t, _ in sorted(tags.items(), key=lambda x: x[1])[:6]] if len(tags) > 6 else [],
    }


def resume_bullets(items: list, rg=None) -> list:
    a = analytics(items)
    if not a["total"]:
        return ["Solve a few problems and sync, your résumé bullets will appear here."]
    plats = ", ".join(LABELS.get(p, p) for p in a["platforms"])
    facts = (f"total={a['total']}, platforms=[{plats}], hard={a['difficulty'].get('Hard',0)}, "
             f"medium={a['difficulty'].get('Medium',0)}, top_topics={', '.join(a['strengths'])}, "
             f"longest_streak={a['longest_streak']}d, languages={', '.join(list(a['languages'])[:4])}")
    if rg is not None:
        out = rg.freeform(
            "Write 3 concise, strong résumé bullet points (one line each, action-oriented, "
            "no fluff, start with '- ') summarizing this competitive-programming activity. "
            "Use only these facts, don't invent numbers:\n" + facts)
        lines = [l.strip() for l in (out or "").splitlines() if l.strip().startswith("-")]
        if lines:
            return lines
    bullets = [
        f"- Solved {a['total']}+ data-structures & algorithms problems across "
        f"{len(a['platforms'])} platforms ({plats}).",
        f"- {a['difficulty'].get('Hard',0)} hard and {a['difficulty'].get('Medium',0)} medium "
        f"problems; strongest in {', '.join(a['strengths'][:3]) or 'core DSA'}.",
        f"- Maintained consistent practice: {a['active_days']} active days, "
        f"longest streak {a['longest_streak']} days.",
    ]
    return bullets


def _bar(n, total, width=18):
    if not total:
        return ""
    return "█" * round(width * n / total) + "░" * (width - round(width * n / total))


def render_md(items: list) -> str:
    a = analytics(items)
    if not a["total"]:
        return "# Insights\n\n_Sync some solutions to see your analytics._\n"
    out = ["# Insights\n", f"_Auto-generated by GitKosh from {a['total']} solutions._\n"]
    out += ["## Pace", "",
            f"- This week: **{a['week']}** (prev week {a['prev_week']}): trend {a['trend']}",
            f"- This month: **{a['month']}**",
            f"- Current streak **{a['current_streak']}d** · longest **{a['longest_streak']}d** · "
            f"active days **{a['active_days']}**", ""]
    if sum(a["difficulty"].values()):
        out += ["## Difficulty", ""]
        tot = sum(a["difficulty"].values())
        for lvl in DIFFS:
            n = a["difficulty"].get(lvl, 0)
            out.append(f"- **{lvl}** `{_bar(n, tot)}` {n}")
        out.append("")
    if a["strengths"]:
        out += ["## Strongest topics", "", " · ".join(f"`{t}`" for t in a["strengths"]), ""]
    if a["coached"]:
        pct = round(100 * a["optimal"] / a["coached"])
        out += ["## Solution quality (AI coach)", "",
                f"- **{pct}%** of coached solutions look optimal ({a['optimal']}/{a['coached']}).", ""]
        if a["revisit"]:
            out += ["**Worth revisiting:**"]
            for i in a["revisit"][:15]:
                d = i.get("dir")
                t = i.get("title", "-")
                out.append(f"- {f'[{t}](./{d})' if d else t}")
            out.append("")
    out += ["## Résumé bullets", ""] + resume_bullets(items) + [""]
    out += ["<sub>Generated by [GitKosh](https://github.com/harsh-bajpai2615/gitkosh).</sub>"]
    return "\n".join(out) + "\n"
