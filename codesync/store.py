"""Tracks which submissions have already been processed, for dedup + incremental watch."""
from __future__ import annotations

import json
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
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)

    def count(self) -> int:
        return len(self._data)
