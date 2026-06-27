"""Gamification — XP, levels, and achievement badges derived from your activity.
Keeps students motivated. All computed from existing data (no extra storage)."""
from __future__ import annotations

from collections import Counter

from . import roadmap, srs

# id, name, description, predicate(stats)
_BADGES = [
    ("first", "First Steps", "Sync your first solution", lambda c: c["n"] >= 1),
    ("ten", "Getting Going", "Solve 10 problems", lambda c: c["n"] >= 10),
    ("fifty", "Half Century", "Solve 50 problems", lambda c: c["n"] >= 50),
    ("century", "Centurion", "Solve 100 problems", lambda c: c["n"] >= 100),
    ("hard", "Hard Hitter", "Solve 10 Hard problems", lambda c: c["hard"] >= 10),
    ("poly", "Polyglot", "Use 3+ languages", lambda c: c["langs"] >= 3),
    ("explorer", "Pattern Explorer", "Cover 8+ topics", lambda c: c["topics"] >= 8),
    ("streak7", "On Fire", "7-day review streak", lambda c: c["rstreak"] >= 7),
    ("blind10", "Blind 75 Initiate", "Clear 10 of Blind 75", lambda c: c["blind"] >= 10),
    ("blind40", "Blind 75 Adept", "Clear 40 of Blind 75", lambda c: c["blind"] >= 40),
]
LEVEL_XP = 500


def compute(items, state_dir):
    diff = Counter(i.get("difficulty") for i in items)
    c = {
        "n": len(items),
        "hard": diff.get("Hard", 0),
        "langs": len({(i.get("lang") or "").strip() for i in items if (i.get("lang") or "").strip()}),
        "topics": len({t for i in items for t in (i.get("tags") or [])}),
        "rstreak": srs.stats(items, state_dir)["review_streak"],
        "blind": next((r["done"] for r in roadmap.progress(items) if r["name"] == "Blind 75"), 0),
    }
    xp = c["n"] * 10 + c["hard"] * 15 + c["blind"] * 15 + c["rstreak"] * 20
    level = 1 + xp // LEVEL_XP
    into = xp % LEVEL_XP
    badges = [{"id": b[0], "name": b[1], "desc": b[2], "earned": bool(b[3](c))} for b in _BADGES]
    return {"xp": xp, "level": level, "into": into, "need": LEVEL_XP,
            "pct": round(100 * into / LEVEL_XP), "earned": sum(1 for b in badges if b["earned"]),
            "total_badges": len(badges), "badges": badges}
