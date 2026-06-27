"""Codeforces extractor.

Official API gives the submission *list* (verdict, problem, tags, rating) but not
source. We pull the list via API, then scrape each accepted submission page for the
actual code, and the problem page for the statement.
"""
from __future__ import annotations

import time
from typing import Iterator, Optional

from bs4 import BeautifulSoup
import html2text

from .base import Platform, Submission, slugify

BASE = "https://codeforces.com"


def _md(node) -> str:
    if node is None:
        return ""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    return h.handle(str(node)).strip()


class Codeforces(Platform):
    name = "codeforces"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self.handle = (config or {}).get("handle", "")
        self.s = session.requests_session("codeforces.com")
        self.s.headers.update({"Referer": BASE})

    def _api_status(self):
        if not self.handle:
            raise RuntimeError("codeforces.handle missing in config.")
        r = self.s.get(f"{BASE}/api/user.status",
                       params={"handle": self.handle, "from": 1, "count": 10000}, timeout=30)
        r.raise_for_status()
        j = r.json()
        if j.get("status") != "OK":
            raise RuntimeError(f"Codeforces API: {j.get('comment')}")
        return j["result"]

    def _fetch_html(self, url: str, wait_selector: str = "") -> str:
        try:
            r = self.s.get(url, timeout=30)
        except Exception:  # noqa: BLE001
            return self.session.browser_fetch(url, wait_selector)
        looks_blocked = r.status_code != 200 or "Just a moment" in r.text or "cf-browser-verification" in r.text
        if looks_blocked:
            # Cloudflare challenge — retry through the real logged-in browser.
            return self.session.browser_fetch(url, wait_selector)
        return r.text

    def _source(self, contest_id, submission_id) -> str:
        url = f"{BASE}/contest/{contest_id}/submission/{submission_id}"
        html = self._fetch_html(url, wait_selector="#program-source-text")
        soup = BeautifulSoup(html, "html.parser")
        pre = soup.select_one("#program-source-text")
        return pre.get_text() if pre else ""

    def _statement(self, contest_id, index) -> str:
        url = f"{BASE}/contest/{contest_id}/problem/{index}"
        try:
            html = self._fetch_html(url, wait_selector=".problem-statement")
            soup = BeautifulSoup(html, "html.parser")
            return _md(soup.select_one(".problem-statement"))
        except Exception:  # noqa: BLE001
            return ""

    def _build(self, sub: dict) -> Optional[Submission]:
        prob = sub.get("problem", {})
        contest_id = prob.get("contestId")
        index = prob.get("index", "")
        sid = str(sub["id"])
        if contest_id is None:
            return None
        code = self._source(contest_id, sid)
        time.sleep(1.0)
        if not code:
            print(f"  ! codeforces {contest_id}{index}: no source (private/contest gym?)")
            return None
        pid = f"{contest_id}{index}"
        return Submission(
            platform=self.name,
            problem_id=pid,
            slug=slugify(prob.get("name", pid)),
            title=f"{pid} - {prob.get('name', '')}",
            lang=sub.get("programmingLanguage", ""),
            code=code,
            url=f"{BASE}/contest/{contest_id}/problem/{index}",
            submission_id=sid,
            verdict="Accepted",
            timestamp=int(sub.get("creationTimeSeconds", 0)),
            difficulty=str(prob.get("rating", "")),
            tags=prob.get("tags", []),
            statement=self._statement(contest_id, index),
        )

    def backfill(self) -> Iterator[Submission]:
        seen = set()
        for sub in self._api_status():
            if sub.get("verdict") != "OK":
                continue
            prob = sub.get("problem", {})
            tag = (prob.get("contestId"), prob.get("index"), sub.get("programmingLanguage"))
            if tag in seen:
                continue
            seen.add(tag)
            try:
                s = self._build(sub)
                if s:
                    yield s
            except Exception as e:  # noqa: BLE001
                print(f"  ! codeforces {sub.get('id')} failed: {e}")

    def recent(self) -> Iterator[Submission]:
        return self.backfill()
