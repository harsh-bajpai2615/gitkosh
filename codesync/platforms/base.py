"""Shared data model + Platform interface."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

# Map platform language names -> file extension.
LANG_EXT = {
    "python": "py", "python3": "py", "pypy": "py", "pypy3": "py", "pythonml": "py",
    "cpp": "cpp", "c++": "cpp", "gnu c++17": "cpp", "gnu c++20": "cpp", "c++17": "cpp",
    "c": "c", "gnu c11": "c",
    "java": "java",
    "javascript": "js", "node.js": "js",
    "typescript": "ts",
    "go": "go", "golang": "go",
    "rust": "rs",
    "kotlin": "kt",
    "swift": "swift",
    "csharp": "cs", "c#": "cs", ".net": "cs",
    "ruby": "rb",
    "scala": "scala",
    "php": "php",
    "mysql": "sql", "mssql": "sql", "oraclesql": "sql", "postgresql": "sql",
}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-") or "problem"


@dataclass
class Submission:
    platform: str          # "leetcode"
    problem_id: str        # "1"  (platform-native id; may be non-numeric)
    slug: str              # "two-sum"
    title: str             # "Two Sum"
    lang: str              # "python3"
    code: str              # the actual source
    url: str               # link to the problem
    submission_id: str = ""
    verdict: str = "Accepted"
    timestamp: int = 0     # epoch seconds of submission
    difficulty: str = ""   # Easy | Medium | Hard | rating number
    tags: List[str] = field(default_factory=list)
    statement: str = ""    # problem statement (markdown/plain), if available
    runtime: str = ""
    memory: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def ext(self) -> str:
        return LANG_EXT.get(self.lang.lower().strip(), "txt")

    @property
    def key(self) -> str:
        """Dedup key. Keyed by submission id when present, else slug+lang."""
        sid = self.submission_id or self.slug
        return f"{self.platform}:{sid}:{self.lang}"

    @property
    def dirname(self) -> str:
        pid = str(self.problem_id)
        if pid.isdigit():
            return f"{int(pid):04d}-{self.slug}"
        return f"{pid}-{self.slug}" if pid else self.slug


class Platform:
    """Subclass per site. `session` is a codesync.auth.Session."""
    name = "base"

    def __init__(self, session, config: dict, root_cfg=None):
        self.session = session
        self.config = config or {}
        self.root_cfg = root_cfg

    def backfill(self) -> Iterator[Submission]:
        """Yield all past accepted submissions (newest first is fine)."""
        raise NotImplementedError

    def recent(self) -> Iterator[Submission]:
        """Yield the most recent accepted submissions (for watch mode).
        Default: delegate to backfill but callers should cap via the store."""
        return self.backfill()
