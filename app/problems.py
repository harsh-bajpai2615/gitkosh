"""In-app practice problems.

The full NeetCode 150 (which includes Blind 75) catalog lives in
`problem_catalog.py` — every problem is selectable, solvable in the editor, and
reviewed by the AI tutor. A curated subset also ships with automated test cases
(instant pass/fail via a generated harness); the rest are graded by AI review.
"""
from __future__ import annotations

import re

from .problem_catalog import CATALOG, ORDER
from .runner import run_python

# Problems that ship with deterministic automated tests (Run tests → instant pass/fail).
# Function names match the catalog starters so the harness binds correctly.
TESTED = {
    "contains-duplicate": {"func": "containsDuplicate",
        "cases": [[[[1, 2, 3, 1]], True], [[[1, 2, 3, 4]], False],
                  [[[1, 1, 1, 3, 3, 4, 3, 2, 4, 2]], True]]},
    "valid-anagram": {"func": "isAnagram",
        "cases": [[["anagram", "nagaram"], True], [["rat", "car"], False], [["a", "a"], True]]},
    "best-time-to-buy-and-sell-stock": {"func": "maxProfit",
        "cases": [[[[7, 1, 5, 3, 6, 4]], 5], [[[7, 6, 4, 3, 1]], 0], [[[1, 2]], 1]]},
    "maximum-subarray": {"func": "maxSubArray",
        "cases": [[[[-2, 1, -3, 4, -1, 2, 1, -5, 4]], 6], [[[1]], 1], [[[5, 4, -1, 7, 8]], 23]]},
    "climbing-stairs": {"func": "climbStairs",
        "cases": [[[2], 2], [[3], 3], [[5], 8]]},
    "binary-search": {"func": "search",
        "cases": [[[[-1, 0, 3, 5, 9, 12], 9], 4], [[[-1, 0, 3, 5, 9, 12], 2], -1], [[[5], 5], 0]]},
    "two-sum": {"func": "twoSum", "unordered": True,
        "cases": [[[[2, 7, 11, 15], 9], [0, 1]], [[[3, 2, 4], 6], [1, 2]], [[[3, 3], 6], [0, 1]]]},
    "valid-palindrome": {"func": "isPalindrome",
        "cases": [[["A man, a plan, a canal: Panama"], True], [["race a car"], False], [[" "], True]]},
    "valid-parentheses": {"func": "isValid",
        "cases": [[["()"], True], [["()[]{}"], True], [["(]"], False], [["([)]"], False]]},
    "maximum-depth-of-binary-tree": None,  # tree input — AI review only (placeholder removed below)
}
# drop any None placeholders (kept above only for documentation clarity)
TESTED = {k: v for k, v in TESTED.items() if v}


def listing():
    out = []
    for s in ORDER:
        c = CATALOG[s]
        out.append({"id": s, "title": c["title"], "difficulty": c["difficulty"],
                    "topic": c["topic"], "tested": s in TESTED, "blind75": c.get("blind75", False)})
    return out


def get(pid):
    c = CATALOG.get(pid)
    if not c:
        return None
    return {"id": pid, "title": c["title"], "difficulty": c["difficulty"], "topic": c["topic"],
            "statement": c["statement"], "starter": c["starter"], "url": c.get("url", ""),
            "tested": pid in TESTED, "blind75": c.get("blind75", False)}


def _harness(code, func, cases, unordered=False):
    # unordered: accept the answer in any order (e.g. two-sum index pairs), to
    # match what the judge actually accepts.
    cmp = "(sorted(_g) == sorted(_e))" if unordered else "(_g == _e)"
    return (code + "\n\n"
            + f"_C = {cases!r}\n_p = 0\n"
            + "for _i, (_a, _e) in enumerate(_C):\n"
            + "    try:\n"
            + f"        _g = {func}(*_a)\n"
            + f"        _ok = {cmp}\n"
            + "        print(('PASS' if _ok else 'FAIL') + f' #{_i+1}  input={_a}  ->  {_g}'"
            + " + ('' if _ok else f'   (expected {_e})'))\n"
            + "        _p += 1 if _ok else 0\n"
            + "    except Exception as _ex:\n"
            + "        print(f'ERROR #{_i+1}: {_ex!r}')\n"
            + "print(f'__RESULT__ {_p} {len(_C)}')\n")


def run_tests(code, pid):
    t = TESTED.get(pid)
    if not t:
        return {"ok": False, "passed": 0, "total": 0,
                "output": "No automated tests for this problem — use “AI Review” to check your solution."}
    res = run_python(_harness(code or "", t["func"], t["cases"], t.get("unordered", False)))
    out = res["stdout"]
    passed = total = 0
    lines = []
    for ln in out.splitlines():
        # Only honor a strictly-formatted sentinel (so user code that happens to
        # print "__RESULT__ ..." can't crash the parser or fake a pass); the last
        # match wins — that's the one the harness emits.
        m = re.fullmatch(r"__RESULT__ (\d+) (\d+)", ln)
        if m:
            passed, total = int(m.group(1)), int(m.group(2))
        else:
            lines.append(ln)
    if res["stderr"]:
        lines.append(res["stderr"])
    return {"ok": total > 0 and passed == total, "passed": passed, "total": total,
            "output": "\n".join(lines).strip(), "ms": res["ms"]}
