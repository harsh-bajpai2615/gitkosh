"""GeeksforGeeks extractor (EXPERIMENTAL · index-only).

GeeksforGeeks exposes NO API for your submitted *source code* — only the list of
solved problems is fetchable. So GitKosh records your GFG-solved problems as a
documented index (title + link + difficulty), without source files. Best-effort;
the solved-list endpoint is unofficial and may change. Needs your GFG handle
(auto-detected from the session).
"""
from __future__ import annotations

from typing import Iterator

from .base import Platform, Submission, slugify

SOLVED_API = "https://authapi.geeksforgeeks.org/api-get/problems-solved/"


class GeeksforGeeks(Platform):
    name = "geeksforgeeks"

    def __init__(self, session, config, root_cfg=None):
        super().__init__(session, config, root_cfg)
        self.handle = (config or {}).get("handle", "")
        self.s = session.requests_session("geeksforgeeks.org")
        self.s.headers.update({"Referer": "https://www.geeksforgeeks.org/"})

    def _solved(self):
        if not self.handle:
            raise RuntimeError("geeksforgeeks.handle missing in config.")
        r = self.s.get(SOLVED_API, params={"handle": self.handle}, timeout=30)
        r.raise_for_status()
        result = r.json().get("result", r.json())
        items = []
        if isinstance(result, dict):
            for diff, lst in result.items():
                if isinstance(lst, list):
                    for p in lst:
                        if isinstance(p, dict):
                            items.append((diff, p))
        return items

    def backfill(self) -> Iterator[Submission]:
        try:
            solved = self._solved()
        except Exception as e:  # noqa: BLE001
            print(f"  ! geeksforgeeks: couldn't fetch solved list ({e}). GFG exposes no source-code API.")
            return
        if not solved:
            print("  ! geeksforgeeks: no solved problems found (GFG exposes no source-code API).")
            return
        for diff, p in solved:
            name = p.get("question") or p.get("problem_name") or p.get("name") or ""
            if not name:
                continue
            slug = p.get("slug") or slugify(name)
            url = p.get("question_url") or p.get("url") or f"https://www.geeksforgeeks.org/problems/{slug}/1"
            yield Submission(
                platform=self.name, problem_id=slug, slug=slugify(name),
                title=name, lang="", code="", url=url,
                submission_id=slug, timestamp=0,
                difficulty=(str(diff).capitalize() if diff else ""), tags=[],
                statement="", extra={"list_only": True},
            )

    def recent(self) -> Iterator[Submission]:
        return self.backfill()
