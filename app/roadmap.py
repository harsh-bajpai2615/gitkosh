"""Roadmap / study-sheet progress — overlays your solved LeetCode problems onto
the canonical Blind 75 and NeetCode 150 lists. Matching is by LeetCode slug
(derived from each solved item's repo dir + title).
"""
from __future__ import annotations

import re

BLIND75 = [
    "two-sum", "contains-duplicate", "valid-anagram", "group-anagrams",
    "top-k-frequent-elements", "product-of-array-except-self", "encode-and-decode-strings",
    "longest-consecutive-sequence", "valid-palindrome", "3sum", "container-with-most-water",
    "best-time-to-buy-and-sell-stock", "longest-substring-without-repeating-characters",
    "longest-repeating-character-replacement", "minimum-window-substring", "valid-parentheses",
    "find-minimum-in-rotated-sorted-array", "search-in-rotated-sorted-array", "reverse-linked-list",
    "merge-two-sorted-lists", "reorder-list", "remove-nth-node-from-end-of-list", "linked-list-cycle",
    "merge-k-sorted-lists", "invert-binary-tree", "maximum-depth-of-binary-tree", "same-tree",
    "subtree-of-another-tree", "lowest-common-ancestor-of-a-binary-search-tree",
    "binary-tree-level-order-traversal", "validate-binary-search-tree", "kth-smallest-element-in-a-bst",
    "construct-binary-tree-from-preorder-and-inorder-traversal", "binary-tree-maximum-path-sum",
    "serialize-and-deserialize-binary-tree", "implement-trie-prefix-tree",
    "design-add-and-search-words-data-structure", "word-search-ii", "find-median-from-data-stream",
    "combination-sum", "word-search", "number-of-islands", "clone-graph", "pacific-atlantic-water-flow",
    "course-schedule", "graph-valid-tree", "number-of-connected-components-in-an-undirected-graph",
    "alien-dictionary", "climbing-stairs", "house-robber", "house-robber-ii",
    "longest-palindromic-substring", "palindromic-substrings", "decode-ways", "coin-change",
    "maximum-product-subarray", "word-break", "longest-increasing-subsequence", "unique-paths",
    "longest-common-subsequence", "maximum-subarray", "jump-game", "insert-interval", "merge-intervals",
    "non-overlapping-intervals", "meeting-rooms", "meeting-rooms-ii", "rotate-image", "spiral-matrix",
    "set-matrix-zeroes", "number-of-1-bits", "counting-bits", "reverse-bits", "missing-number",
    "sum-of-two-integers",
]

_NC_EXTRA = [
    "valid-sudoku", "two-sum-ii-input-array-is-sorted", "trapping-rain-water", "permutation-in-string",
    "sliding-window-maximum", "min-stack", "evaluate-reverse-polish-notation", "generate-parentheses",
    "daily-temperatures", "car-fleet", "largest-rectangle-in-histogram", "binary-search",
    "search-a-2d-matrix", "koko-eating-bananas", "time-based-key-value-store",
    "median-of-two-sorted-arrays", "add-two-numbers", "copy-list-with-random-pointer",
    "find-the-duplicate-number", "lru-cache", "balanced-binary-tree", "diameter-of-binary-tree",
    "count-good-nodes-in-binary-tree", "kth-largest-element-in-a-stream", "last-stone-weight",
    "k-closest-points-to-origin", "kth-largest-element-in-an-array", "task-scheduler", "design-twitter",
    "subsets", "combination-sum-ii", "permutations", "subsets-ii", "palindrome-partitioning",
    "letter-combinations-of-a-phone-number", "n-queens", "rotting-oranges", "walls-and-gates",
    "surrounded-regions", "course-schedule-ii", "redundant-connection", "word-ladder",
    "reconstruct-itinerary", "min-cost-to-connect-all-points", "network-delay-time",
    "swim-in-rising-water", "cheapest-flights-within-k-stops", "partition-equal-subset-sum",
    "best-time-to-buy-and-sell-stock-with-cooldown", "coin-change-ii", "target-sum",
    "interleaving-string", "longest-increasing-path-in-a-matrix", "distinct-subsequences",
    "edit-distance", "burst-balloons", "regular-expression-matching", "jump-game-ii", "gas-station",
    "hand-of-straights", "merge-triplets-to-form-target-triplet", "partition-labels",
    "valid-parenthesis-string", "minimum-interval-to-include-each-query", "happy-number", "plus-one",
    "powx-n", "multiply-strings", "detect-squares",
]
NEETCODE150 = BLIND75 + _NC_EXTRA
SHEETS = {"Blind 75": BLIND75, "NeetCode 150": NEETCODE150}


def _slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def solved_slugs(items):
    out = set()
    for it in items:
        if it.get("platform") != "leetcode":
            continue
        d = it.get("dir") or ""
        if d:
            out.add(re.sub(r"^\d+[-_]", "", d.split("/")[-1]))
        if it.get("title"):
            out.add(_slugify(it["title"]))
    return out


def _title(slug):
    return slug.replace("-", " ").title()


def progress(items):
    solved = solved_slugs(items)
    res = []
    for name, lst in SHEETS.items():
        done = [s for s in lst if s in solved]
        missing = [s for s in lst if s not in solved]
        res.append({"name": name, "total": len(lst), "done": len(done),
                    "pct": round(100 * len(done) / len(lst)),
                    "missing": [{"slug": s, "title": _title(s),
                                 "url": f"https://leetcode.com/problems/{s}/"} for s in missing]})
    return res
