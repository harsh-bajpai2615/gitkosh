"""Upcoming contests + Codeforces rating history (public APIs, no auth).

Feeds the in-app Contests tab. All network calls are best-effort and isolated, so
one platform being down never breaks the others.
"""
from __future__ import annotations

import requests

UA = {"User-Agent": "gitkosh"}


def codeforces_upcoming() -> list:
    r = requests.get("https://codeforces.com/api/contest.list", headers=UA, timeout=30)
    r.raise_for_status()
    out = []
    for c in r.json().get("result", []):
        if c.get("phase") == "BEFORE":
            out.append({"platform": "codeforces", "name": c["name"],
                        "start": c.get("startTimeSeconds", 0), "duration": c.get("durationSeconds", 0),
                        "url": f"https://codeforces.com/contests/{c['id']}"})
    return out


def leetcode_upcoming() -> list:
    r = requests.post("https://leetcode.com/graphql",
                      json={"query": "{ upcomingContests { title titleSlug startTime duration } }"},
                      headers={**UA, "Referer": "https://leetcode.com", "Content-Type": "application/json"},
                      timeout=30)
    data = (r.json().get("data") or {}).get("upcomingContests") or []
    return [{"platform": "leetcode", "name": c["title"], "start": c.get("startTime", 0),
             "duration": c.get("duration", 0),
             "url": f"https://leetcode.com/contest/{c['titleSlug']}"} for c in data]


def upcoming() -> list:
    out = []
    for fn in (codeforces_upcoming, leetcode_upcoming):
        try:
            out += fn()
        except Exception:  # noqa: BLE001
            pass
    out.sort(key=lambda x: x.get("start", 0))
    return out


def cf_rating(handle: str) -> list:
    """[(epoch_seconds, rating), …] for a Codeforces handle, or []."""
    if not handle:
        return []
    try:
        r = requests.get("https://codeforces.com/api/user.rating",
                         params={"handle": handle}, headers=UA, timeout=30)
        return [(x["ratingUpdateTimeSeconds"], x["newRating"]) for x in r.json().get("result", [])]
    except Exception:  # noqa: BLE001
        return []
