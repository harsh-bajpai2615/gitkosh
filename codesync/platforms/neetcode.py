"""NeetCode extractor.

NeetCode doesn't expose your stored code via an API, and its problems ARE LeetCode
problems. So this reuses your LeetCode session and keeps only the solves that are on
the NeetCode roadmap. It fetches the roadmap slug list live, with a small fallback.

Note: this overlaps with the `leetcode` platform. Enable both only if you want the
NeetCode subset mirrored under neetcode/ as well.
"""
from __future__ import annotations

from typing import Iterator, Set

import requests

from .base import Platform, Submission
from .leetcode import LeetCode

# Minimal fallback if the live roadmap fetch fails (NeetCode 150 core sample).
_FALLBACK = {
    "two-sum", "valid-anagram", "contains-duplicate", "group-anagrams",
    "top-k-frequent-elements", "product-of-array-except-self", "valid-sudoku",
    "longest-consecutive-sequence", "valid-palindrome", "two-sum-ii-input-array-is-sorted",
    "3sum", "container-with-most-water", "best-time-to-buy-and-sell-stock",
    "longest-substring-without-repeating-characters", "valid-parentheses",
    "merge-two-sorted-lists", "reverse-linked-list", "linked-list-cycle",
    "invert-binary-tree", "maximum-depth-of-binary-tree", "number-of-islands",
    "climbing-stairs", "coin-change", "longest-increasing-subsequence",
}

_SOURCES = [
    "https://neetcode.io/api/problems",
    "https://neetcode.io/api/problems/neetcode150",
]


def _roadmap_slugs() -> Set[str]:
    for url in _SOURCES:
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                continue
            data = r.json()
            items = data if isinstance(data, list) else data.get("problems", [])
            slugs = set()
            for it in items:
                link = it.get("link") or it.get("leetcode") or ""
                if "/problems/" in link:
                    slugs.add(link.rstrip("/").rsplit("/", 1)[-1])
                elif it.get("slug"):
                    slugs.add(it["slug"])
            if slugs:
                return slugs
        except Exception:  # noqa: BLE001
            continue
    return set(_FALLBACK)


class NeetCode(Platform):
    name = "neetcode"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self._lc = LeetCode(session, config, root_cfg)
        self._slugs = _roadmap_slugs()

    def _retag(self, sub: Submission) -> Submission:
        sub.platform = self.name
        if "neetcode" not in [t.lower() for t in sub.tags]:
            sub.tags = sub.tags + ["neetcode"]
        return sub

    def backfill(self) -> Iterator[Submission]:
        for sub in self._lc.backfill():
            if sub.slug in self._slugs:
                yield self._retag(sub)

    def recent(self) -> Iterator[Submission]:
        for sub in self._lc.recent():
            if sub.slug in self._slugs:
                yield self._retag(sub)
