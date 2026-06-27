"""LeetCode extractor.

Uses the logged-in session cookie with two undocumented-but-stable endpoints:
  - GET /api/submissions/?offset=&limit=   -> paginated submission list (no code)
  - POST /graphql submissionDetails(id)    -> code + question statement + tags
"""
from __future__ import annotations

import time
from typing import Iterator

from bs4 import BeautifulSoup
import html2text

from .base import Platform, Submission

BASE = "https://leetcode.com"

_DETAILS_QUERY = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    code
    runtimeDisplay
    memoryDisplay
    lang { name }
    question {
      questionId
      questionFrontendId
      titleSlug
      title
      difficulty
      content
      topicTags { name }
    }
  }
}
"""


def _md(html: str) -> str:
    if not html:
        return ""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    return h.handle(html).strip()


class LeetCode(Platform):
    name = "leetcode"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self.s = session.requests_session("leetcode.com")
        csrf = session.cookie("csrftoken", "leetcode.com") or ""
        self.s.headers.update({
            "Referer": BASE,
            "Origin": BASE,
            "x-csrftoken": csrf,
            "Content-Type": "application/json",
        })

    def _details(self, submission_id: str) -> dict:
        r = self.s.post(
            f"{BASE}/graphql",
            json={"query": _DETAILS_QUERY, "variables": {"submissionId": int(submission_id)}},
            timeout=30,
        )
        r.raise_for_status()
        return (r.json().get("data") or {}).get("submissionDetails") or {}

    def _iter_list(self) -> Iterator[dict]:
        """Yield accepted submission summaries, newest first, across all pages."""
        offset = 0
        limit = 20
        while True:
            r = self.s.get(
                f"{BASE}/api/submissions/",
                params={"offset": offset, "limit": limit},
                timeout=30,
            )
            if r.status_code == 403:
                raise RuntimeError("LeetCode returned 403 — session expired? Re-run `codesync login`.")
            r.raise_for_status()
            data = r.json()
            dump = data.get("submissions_dump", [])
            if not dump:
                break
            for sub in dump:
                if sub.get("status_display") == "Accepted":
                    yield sub
            if not data.get("has_next"):
                break
            offset += limit
            time.sleep(0.7)  # be polite

    def _to_submission(self, summary: dict) -> Submission:
        sid = str(summary["id"])
        det = self._details(sid)
        q = det.get("question", {}) or {}
        code = det.get("code", "") or ""
        statement = _md(q.get("content", ""))
        slug = q.get("titleSlug") or summary.get("title_slug", "")
        time.sleep(0.5)
        return Submission(
            platform=self.name,
            problem_id=str(q.get("questionFrontendId") or q.get("questionId") or ""),
            slug=slug,
            title=q.get("title") or summary.get("title", ""),
            lang=(det.get("lang") or {}).get("name") or summary.get("lang", ""),
            code=code,
            url=f"{BASE}/problems/{slug}/",
            submission_id=sid,
            verdict="Accepted",
            timestamp=int(summary.get("timestamp", 0)),
            difficulty=q.get("difficulty", ""),
            tags=[t["name"] for t in q.get("topicTags", []) or []],
            statement=statement,
            runtime=det.get("runtimeDisplay", ""),
            memory=det.get("memoryDisplay", ""),
        )

    def backfill(self) -> Iterator[Submission]:
        seen_best = set()  # (slug, lang) -> keep only newest accepted
        for summary in self._iter_list():
            tag = (summary.get("title_slug"), summary.get("lang"))
            if tag in seen_best:
                continue
            seen_best.add(tag)
            try:
                yield self._to_submission(summary)
            except Exception as e:  # noqa: BLE001
                print(f"  ! leetcode {summary.get('title_slug')} failed: {e}")

    def recent(self) -> Iterator[Submission]:
        # Newest-first already; the runner stops once it hits known keys.
        for summary in self._iter_list():
            try:
                yield self._to_submission(summary)
            except Exception as e:  # noqa: BLE001
                print(f"  ! leetcode {summary.get('title_slug')} failed: {e}")
