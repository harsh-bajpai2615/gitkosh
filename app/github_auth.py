"""GitHub sign-in via OAuth Device Flow (no client secret, ideal for desktop apps).

Flow: request a device+user code -> user enters the user code at github.com/login/device
-> we poll until they approve -> we get an access token (repo scope) and store it.
The client_id is public and safe to ship; it comes from a GitHub OAuth App you register
once (Settings -> Developer settings -> OAuth Apps -> enable "Device Flow").
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

import requests

DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
SCOPE = "repo"
_HEADERS = {"Accept": "application/json", "User-Agent": "codesync"}


def start_device_flow(client_id: str) -> dict:
    """Returns dict with device_code, user_code, verification_uri, expires_in, interval."""
    r = requests.post(DEVICE_CODE_URL, headers=_HEADERS,
                      data={"client_id": client_id, "scope": SCOPE}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if "device_code" not in d:
        raise RuntimeError(f"GitHub device flow error: {d}")
    return d


def poll_for_token(client_id: str, device_code: str, interval: int = 5,
                   expires_in: int = 900, should_stop: Optional[Callable[[], bool]] = None) -> str:
    deadline = time.time() + expires_in
    wait = max(int(interval), 1)
    while time.time() < deadline:
        if should_stop and should_stop():
            raise RuntimeError("cancelled")
        time.sleep(wait)
        r = requests.post(TOKEN_URL, headers=_HEADERS, data={
            "client_id": client_id,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }, timeout=30)
        d = r.json()
        if d.get("access_token"):
            return d["access_token"]
        err = d.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            wait += 5
            continue
        raise RuntimeError(f"GitHub auth failed: {err or d}")
    raise TimeoutError("Login timed out — re-open the GitHub login.")


# ---------- token storage ----------
def _token_path(state_dir: Path) -> Path:
    return Path(state_dir) / "github.json"


def save_token(state_dir: Path, token: str, login: str) -> None:
    p = _token_path(state_dir)
    p.write_text(json.dumps({"token": token, "login": login}))
    p.chmod(0o600)


def load_github(state_dir: Path) -> Optional[dict]:
    p = _token_path(state_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def clear_token(state_dir: Path) -> None:
    p = _token_path(state_dir)
    if p.exists():
        p.unlink()
