"""AtCoder extractor.

Submission list via the public AtCoder Problems API (kenkoooo, v3 — paginated by
from_second, ≥1s between calls). Source code is scraped from each submission page
(`#submission-code`) using your logged-in session. Statement best-effort from the
task page. Needs your AtCoder handle (auto-detected from the session).
"""
from __future__ import annotations

import time
from typing import Iterator

from bs4 import BeautifulSoup
import html2text

from .base import Platform, Submission, slugify

BASE = "https://atcoder.jp"
KEN = "https://kenkoooo.com/atcoder/atcoder-api"

_LANG = [
    ("c++", "cpp"), ("pypy", "python3"), ("python", "python3"), ("rust", "rust"),
    ("java", "java"), ("kotlin", "kotlin"), ("c#", "csharp"), (".net", "csharp"),
    ("go", "go"), ("javascript", "javascript"), ("typescript", "typescript"),
    ("ruby", "ruby"), ("swift", "swift"), ("scala", "scala"), ("php", "php"),
]


def _norm_lang(s: str) -> str:
    t = (s or "").lower()
    for needle, lang in _LANG:
        if needle in t:
            return lang
    if t.startswith("c ") or t.startswith("c("):
        return "c"
    return s


def _md(node) -> str:
    if node is None:
        return ""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = True
    return h.handle(str(node)).strip()


class AtCoder(Platform):
    name = "atcoder"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self.handle = (config or {}).get("handle", "")
        self.s = session.requests_session("atcoder.jp")
        self.s.headers.update({"Referer": BASE})

    def _submissions(self):
        if not self.handle:
            raise RuntimeError("atcoder.handle missing in config.")
        out, frm = [], 0
        while True:
            r = self.s.get(f"{KEN}/v3/user/submissions",
                           params={"user": self.handle, "from_second": frm}, timeout=60)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 500:
                break
            frm = max(s["epoch_second"] for s in batch) + 1
            time.sleep(1.1)
        return out

    def _source(self, contest_id, sub_id) -> str:
        url = f"{BASE}/contests/{contest_id}/submissions/{sub_id}"
        try:
            r = self.s.get(url, timeout=30)
            if r.status_code != 200:
                return ""
            pre = BeautifulSoup(r.text, "html.parser").select_one("#submission-code")
            return pre.get_text() if pre else ""
        except Exception:  # noqa: BLE001
            return ""

    def _statement(self, contest_id, task_id) -> str:
        try:
            r = self.s.get(f"{BASE}/contests/{contest_id}/tasks/{task_id}", timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")
            node = soup.select_one("#task-statement span.lang-en") or soup.select_one("#task-statement")
            return _md(node)[:6000]
        except Exception:  # noqa: BLE001
            return ""

    def backfill(self) -> Iterator[Submission]:
        ac = [s for s in self._submissions() if s.get("result") == "AC"]
        ac.sort(key=lambda s: s.get("epoch_second", 0), reverse=True)
        seen = set()
        for s in ac:
            pid, cid, sid = s.get("problem_id"), s.get("contest_id"), s.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            code = self._source(cid, sid)
            time.sleep(1.1)
            if not code:
                print(f"  ! atcoder {pid}: no source (private?)")
                continue
            yield Submission(
                platform=self.name, problem_id=pid, slug=slugify(pid), title=pid,
                lang=_norm_lang(s.get("language", "")), code=code,
                url=f"{BASE}/contests/{cid}/tasks/{pid}",
                submission_id=str(sid), timestamp=int(s.get("epoch_second", 0)),
                difficulty="", tags=[], statement=self._statement(cid, pid),
            )

    def recent(self) -> Iterator[Submission]:
        return self.backfill()
