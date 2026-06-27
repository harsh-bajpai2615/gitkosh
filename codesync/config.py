"""Config loading + path helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p))).resolve()


class Config:
    def __init__(self, data: Dict[str, Any], path: Path):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: str) -> "Config":
        p = _expand(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Config not found at {p}. Copy config.example.yaml to config.yaml and edit it."
            )
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(data, p)

    # -- convenience accessors --
    @property
    def output_repo(self) -> Path:
        return _expand(self.data["output_repo"])

    @property
    def github(self) -> Dict[str, Any]:
        return self.data.get("github", {})

    @property
    def platforms(self) -> Dict[str, Any]:
        return self.data.get("platforms", {})

    @property
    def readme(self) -> Dict[str, Any]:
        return self.data.get("readme", {"mode": "minimal"})

    @property
    def watch(self) -> Dict[str, Any]:
        return self.data.get("watch", {"interval_minutes": 15})

    @property
    def profile_dir(self) -> Path:
        d = _expand(self.data.get("paths", {}).get("profile_dir", "~/.codesync/browser-profile"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def state_dir(self) -> Path:
        d = _expand(self.data.get("paths", {}).get("state_dir", "~/.codesync/state"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def enabled_platforms(self) -> list:
        return [name for name, cfg in self.platforms.items() if cfg and cfg.get("enabled")]
