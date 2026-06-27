"""Per-user application paths and config bootstrap.

Everything lives under ~/Library/Application Support/codesync. The app is a
mediator: it holds session cookies (CP sites) + a GitHub token, and pushes via
the GitHub API — there is no local git repo.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

APP_DIR = Path(os.path.expanduser("~/Library/Application Support/codesync"))
CONFIG_PATH = APP_DIR / "config.yaml"
STATE_DIR = APP_DIR / "state"

DEFAULT_CONFIG = {
    "github": {"repo": "competitive-programming", "private": True, "client_id": ""},
    # Handles are auto-detected from the logged-in session; cached here.
    "platforms": {
        "codeforces": {"handle": ""},
        "codechef": {"handle": ""},
    },
    "readme": {
        "mode": "llm",
        "llm": {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": ""},
    },
    "watch": {"interval_minutes": 15},
    "paths": {"state_dir": str(STATE_DIR)},
}


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return _deep_merge(DEFAULT_CONFIG, {})
    data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(cfg: dict) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
