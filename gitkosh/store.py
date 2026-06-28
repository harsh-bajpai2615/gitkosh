"""Tracks which submissions have already been processed, for dedup + incremental watch."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict


class Store:
    def __init__(self, state_dir: Path):
        state_dir = Path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "processed.json"
        self._data: Dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self._data = {}

    def seen(self, key: str) -> bool:
        return key in self._data

    def mark(self, key: str, meta: dict) -> None:
        self._data[key] = meta
        self.flush()

    def last_timestamp(self, platform: str) -> int:
        ts = [m.get("timestamp", 0) for m in self._data.values() if m.get("platform") == platform]
        return max(ts) if ts else 0

    def flush(self) -> None:
        # Write to a unique temp file in the same dir, then atomically replace —
        # a fixed temp name lets a concurrent run (GUI + scheduler) clobber the
        # temp mid-write and lose data or raise FileNotFoundError on replace.
        fd, tmp = tempfile.mkstemp(prefix="processed.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def count(self) -> int:
        return len(self._data)

    def all(self) -> list:
        return list(self._data.values())

    def clear(self, flush: bool = True) -> None:
        # flush=False clears only the in-memory view (so a reset re-discovers
        # everything) without persisting the wipe — callers can defer the on-disk
        # clear until a push succeeds, so a failed reset doesn't lose the record
        # and cause every problem to be re-pushed as a duplicate next run.
        self._data = {}
        if flush:
            self.flush()
