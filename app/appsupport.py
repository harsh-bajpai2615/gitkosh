"""Per-user application paths and config bootstrap.

Everything lives under ~/Library/Application Support/GitKosh. The app is a
mediator: it holds session cookies (CP sites) + a GitHub token, and pushes via
the GitHub API — there is no local git repo.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

APP_DIR = Path(os.path.expanduser("~/Library/Application Support/GitKosh"))
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
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("config root is not a mapping")
    except Exception as e:  # noqa: BLE001
        # A corrupt config must NEVER brick the app — back it up and reset to
        # defaults. (Logins/token live in separate files and are unaffected.)
        try:
            backup = CONFIG_PATH.with_name("config.corrupt.yaml")
            CONFIG_PATH.replace(backup)
            print(f"[GitKosh] config.yaml was unreadable ({e}); backed up to {backup}, using defaults.")
        except OSError:
            pass
        save_config(DEFAULT_CONFIG)
        return _deep_merge(DEFAULT_CONFIG, {})
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(cfg: dict) -> None:
    """Write config atomically (temp file + os.replace) so concurrent saves from
    the UI bridge / scheduler can never interleave into a corrupt file."""
    ensure_dirs()
    text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    fd, tmp = tempfile.mkstemp(dir=str(APP_DIR), prefix="config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
