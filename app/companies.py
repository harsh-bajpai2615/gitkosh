"""Company-wise LeetCode interview questions.

A curated set of FAANG-tier + Indian-placement "dream/super-dream" companies is
featured, but all 657 companies from the source dataset are selectable. Each
company's question list (per recency window) is fetched on demand from the source's
raw CDN and cached locally; webmain then cross-references the user's synced LeetCode
solves and the in-app practice catalog.

Source: github.com/snehasishroy/leetcode-companywise-interview-questions
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path

import requests

_RAW = ("https://raw.githubusercontent.com/snehasishroy/"
        "leetcode-companywise-interview-questions/master")


def _data_path(name="companies.json") -> Path:
    """Locate a bundled data file in dev (next to this file under data/) or in the
    py2app bundle (Contents/Resources/data/), where DATA_FILES places it."""
    dev = Path(__file__).with_name("data") / name
    if dev.exists():
        return dev
    bundled = Path(sys.executable).resolve().parent.parent / "Resources" / "data" / name
    return bundled if bundled.exists() else dev


_topics = None


def topics_for(slug: str) -> list:
    """LeetCode topic tags for a problem slug (e.g. ['Array','Hash Table']), or []."""
    global _topics
    if _topics is None:
        try:
            _topics = json.loads(_data_path("leetcode_topics.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _topics = {}
    return _topics.get(slug, [])


_topic_totals = None


def topic_totals() -> dict:
    """How many LeetCode problems carry each topic tag, denominator for coverage."""
    global _topic_totals
    if _topic_totals is None:
        topics_for("")  # ensure the map is loaded
        counts = {}
        for tags in (_topics or {}).values():
            for t in tags:
                counts[t] = counts.get(t, 0) + 1
        _topic_totals = counts
    return _topic_totals

# Recency windows the dataset ships (smaller companies only have the longer ones;
# fetch() falls back to "all" when a requested window is missing for a company).
PERIODS = [
    {"key": "thirty-days", "label": "30 days"},
    {"key": "three-months", "label": "3 months"},
    {"key": "six-months", "label": "6 months"},
    {"key": "all", "label": "All time"},
]
_VALID_PERIODS = {p["key"] for p in PERIODS}
_CACHE_TTL = 7 * 86400  # re-fetch a company at most weekly

_catalog = None


def _load() -> dict:
    global _catalog
    if _catalog is None:
        _catalog = json.loads(_data_path().read_text(encoding="utf-8"))
    return _catalog


def list_companies() -> dict:
    c = _load()
    return {"featured": c["featured"], "companies": c["companies"], "periods": PERIODS}


def slug_from_url(url: str) -> str:
    """https://leetcode.com/problems/two-sum/ -> two-sum"""
    url = url or ""
    if "/problems/" not in url:
        return ""
    return url.split("/problems/", 1)[1].strip("/").split("/")[0]


def _num(s) -> float:
    try:
        return float((s or "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _cache_path(cache_dir, company, period) -> Path:
    return Path(cache_dir) / "company_cache" / f"{company}.{period}.json"


def _download(company, period):
    """Fetch+parse one CSV. Returns (rows, used_period) or (None, period) on failure."""
    try:
        r = requests.get(f"{_RAW}/{company}/{period}.csv", timeout=30)
    except requests.RequestException:
        return None, period
    if r.status_code != 200:
        return None, period
    rows = []
    for row in csv.DictReader(io.StringIO(r.text)):
        url = (row.get("URL") or "").strip()
        slug = slug_from_url(url)
        if not slug:
            continue
        rows.append({
            "id": (row.get("ID") or "").strip(),
            "slug": slug,
            "title": (row.get("Title") or "").strip(),
            "difficulty": (row.get("Difficulty") or "").strip(),
            "url": url,
            "acceptance": (row.get("Acceptance %") or "").strip(),
            "frequency": _num(row.get("Frequency %")),
        })
    rows.sort(key=lambda x: x["frequency"], reverse=True)
    return rows, period


def fetch(company, period, cache_dir) -> dict:
    """Return {ok, questions, period, error}. Uses a weekly local cache and falls
    back to 'all' when the requested window doesn't exist for this company."""
    company = (company or "").strip().lower()
    if period not in _VALID_PERIODS:
        period = "all"
    if company not in {c["slug"] for c in _load()["companies"]}:
        return {"ok": False, "error": "Unknown company."}

    cp = _cache_path(cache_dir, company, period)
    if cp.exists() and (time.time() - cp.stat().st_mtime) < _CACHE_TTL:
        try:
            return {"ok": True, **json.loads(cp.read_text(encoding="utf-8"))}
        except (OSError, ValueError):
            pass

    rows, used = _download(company, period)
    if rows is None and period != "all":  # window missing for this company
        rows, used = _download(company, "all")
    if rows is None:  # network failure: stale cache beats nothing
        if cp.exists():
            try:
                return {"ok": True, **json.loads(cp.read_text(encoding="utf-8"))}
            except (OSError, ValueError):
                pass
        return {"ok": False, "error": "Couldn't load this company's questions (check your connection)."}

    payload = {"questions": rows, "period": used}
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return {"ok": True, **payload}
