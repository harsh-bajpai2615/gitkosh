"""Spaced-repetition engine for Quiz Me (SM-2-flavored).

Per-problem review state + a daily review log live in <state>/review.json, keyed by
the problem's repo dir (stable, unique). New (never-reviewed) cards count as due.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

DAY = 86400
RATINGS = ("again", "hard", "good", "easy")


def _path(state_dir):
    return Path(state_dir) / "review.json"


def _load(state_dir):
    p = _path(state_dir)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            d.setdefault("cards", {})
            d.setdefault("log", {})
            return d
        except Exception:  # noqa: BLE001
            pass
    return {"cards": {}, "log": {}}


def _save(state_dir, d):
    _path(state_dir).write_text(json.dumps(d, indent=2))


def card_key(item):
    return item.get("dir") or item.get("url") or item.get("title") or ""


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def due(items, state_dir, now=None):
    """Items due for review (overdue first, then never-seen)."""
    now = now or time.time()
    d = _load(state_dir)
    cards = d["cards"]
    seen, fresh = [], []
    for it in items:
        k = card_key(it)
        if not k:
            continue
        c = cards.get(k)
        if c is None:
            fresh.append(it)
        elif c.get("due", 0) <= now:
            seen.append((c.get("due", 0), it))
    seen.sort(key=lambda x: x[0])
    return [it for _, it in seen] + fresh


def review(state_dir, key, rating, now=None):
    """Apply a rating (again/hard/good/easy) and schedule the next review."""
    now = now or time.time()
    d = _load(state_dir)
    c = d["cards"].get(key, {"ease": 2.4, "interval": 0, "reps": 0})
    ease = c.get("ease", 2.4)
    interval = c.get("interval", 0)
    reps = c.get("reps", 0)
    if rating == "again":
        reps, interval, ease = 0, 0, max(1.3, ease - 0.2)
        nxt = now + 600  # ~10 min
    elif rating == "hard":
        interval = max(1, round((interval or 1) * 1.2))
        ease = max(1.3, ease - 0.15)
        reps += 1
        nxt = now + interval * DAY
    elif rating == "easy":
        interval = max(2, round((interval or 1) * ease * 1.3))
        ease = min(3.0, ease + 0.15)
        reps += 1
        nxt = now + interval * DAY
    else:  # good
        interval = 1 if reps == 0 else max(1, round(interval * ease))
        reps += 1
        nxt = now + interval * DAY
    d["cards"][key] = {"ease": round(ease, 2), "interval": interval, "reps": reps,
                       "due": nxt, "last": now}
    d["log"][_today()] = d["log"].get(_today(), 0) + 1
    _save(state_dir, d)
    return d["cards"][key]


def stats(items, state_dir, now=None):
    now = now or time.time()
    d = _load(state_dir)
    days = sorted(d["log"].keys())
    # review streak: consecutive days ending today/yesterday with >=1 review
    from datetime import date, timedelta
    today = datetime.now(timezone.utc).date()
    have = set(days)
    streak = 0
    cur = today
    if today.isoformat() not in have and (today - timedelta(days=1)).isoformat() not in have:
        streak = 0
    else:
        if today.isoformat() not in have:
            cur = today - timedelta(days=1)
        while cur.isoformat() in have:
            streak += 1
            cur = cur - timedelta(days=1)
    duec = len(due(items, state_dir, now))
    new = sum(1 for it in items if card_key(it) not in d["cards"])
    return {"due": duec, "new": new, "reviewed_today": d["log"].get(today.isoformat(), 0),
            "review_streak": streak}
