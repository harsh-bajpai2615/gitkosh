"""CodeChef extractor (EXPERIMENTAL).

CodeChef has no stable public API and sits behind Cloudflare, so this is best-effort:
  - recent submissions:  /recent/user?user_handle=...&page=N   (returns HTML in JSON)
  - source code:         /viewsolution/{id}                     (browser fetch)
  - statement:           /api/contests/PRACTICE/problems/{code}
Expect occasional misses; re-run if Cloudflare blocks a fetch.
"""
from __future__ import annotations

import json
import re
import time
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from .base import Platform, Submission, slugify

BASE = "https://www.codechef.com"


class CodeChef(Platform):
    name = "codechef"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self.handle = (config or {}).get("handle", "")
        self.s = session.requests_session("codechef.com")
        self.s.headers.update({"Referer": BASE, "x-requested-with": "XMLHttpRequest"})

    def _recent_rows(self) -> Iterator[dict]:
        if not self.handle:
            raise RuntimeError("codechef.handle missing in config.")
        page = 0
        while True:
            r = self.s.get(f"{BASE}/recent/user",
                           params={"user_handle": self.handle, "page": page}, timeout=30)
            if r.status_code != 200:
                break
            try:
                payload = r.json()
            except json.JSONDecodeError:
                break
            html = payload.get("content", "")
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table tr")
            found = False
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 3:
                    continue
                # columns: time, problem, result(status), lang, [solution link]
                prob_link = tr.find("a", href=re.compile(r"/problems/"))
                sol_link = tr.find("a", href=re.compile(r"/viewsolution/"))
                status_img = tr.find("img") or tr.find(title=re.compile("accepted", re.I))
                is_ac = bool(status_img and "accepted" in (status_img.get("title", "") + status_img.get("src", "")).lower())
                if not (prob_link and sol_link):
                    continue
                found = True
                yield {
                    "code": prob_link["href"].rsplit("/", 1)[-1],
                    "name": prob_link.get_text(strip=True),
                    "solution_id": sol_link["href"].rsplit("/", 1)[-1],
                    "accepted": is_ac,
                }
            total = payload.get("max_page", page)
            if page >= total or not found:
                break
            page += 1
            time.sleep(1.0)

    def _source(self, solution_id: str) -> str:
        url = f"{BASE}/viewsolution/{solution_id}"
        html = self.session.browser_fetch(url, wait_selector="pre, .ace_content")
        soup = BeautifulSoup(html, "html.parser")
        # CodeChef renders code in an Ace editor; try a few shapes.
        for sel in ("#solution pre", "pre.code", ".ace_content", "pre"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text("\n")
        return ""

    def _statement(self, code: str) -> str:
        try:
            r = self.s.get(f"{BASE}/api/contests/PRACTICE/problems/{code}", timeout=30)
            if r.status_code == 200:
                return (r.json() or {}).get("body", "") or ""
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _build(self, row: dict) -> Optional[Submission]:
        code = self._source(row["solution_id"])
        time.sleep(1.0)
        if not code:
            print(f"  ! codechef {row['code']}: no source (Cloudflare/login?)")
            return None
        return Submission(
            platform=self.name,
            problem_id=row["code"],
            slug=slugify(row["name"] or row["code"]),
            title=row["name"] or row["code"],
            lang="",  # not reliably exposed in the recent table
            code=code,
            url=f"{BASE}/problems/{row['code']}",
            submission_id=row["solution_id"],
            timestamp=0,
            statement=self._statement(row["code"]),
        )

    def backfill(self) -> Iterator[Submission]:
        seen = set()
        for row in self._recent_rows():
            if not row["accepted"] or row["solution_id"] in seen:
                continue
            seen.add(row["solution_id"])
            try:
                s = self._build(row)
                if s:
                    yield s
            except Exception as e:  # noqa: BLE001
                print(f"  ! codechef {row.get('code')} failed: {e}")

    def recent(self) -> Iterator[Submission]:
        return self.backfill()
