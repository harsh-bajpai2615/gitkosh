"""Session backed by cookies captured by the native WebKit login window.

Implements the same surface the extractors call (requests_session / cookie /
browser_fetch / close), reading the same storage_state.json the Playwright
Session writes — so the platform extractors are reused unchanged. There is no
real browser here, so browser_fetch degrades to a plain requests GET (good
enough for Codeforces source pages; CodeChef's Cloudflare pages may miss).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class NativeSession:
    def __init__(self, state_dir: Path):
        self.state_path = Path(state_dir) / "storage_state.json"

    def has_state(self) -> bool:
        return self.state_path.exists()

    def _cookies(self) -> List[dict]:
        if not self.state_path.exists():
            raise RuntimeError("Not logged in yet.")
        return json.loads(self.state_path.read_text()).get("cookies", [])

    def cookie(self, name: str, domain_contains: str = "") -> Optional[str]:
        for c in self._cookies():
            if c["name"] == name and domain_contains in c.get("domain", ""):
                return c["value"]
        return None

    def requests_session(self, domain_contains: str = "") -> requests.Session:
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        for c in self._cookies():
            dom = c.get("domain", "")
            if domain_contains and domain_contains not in dom:
                continue
            try:
                s.cookies.set(c["name"], c["value"], domain=dom.lstrip("."), path=c.get("path", "/"))
            except Exception:  # noqa: BLE001
                pass
        return s

    def browser_fetch(self, url: str, wait_selector: str = "", timeout_ms: int = 30000) -> str:
        # No headless browser in the app build; best-effort plain GET with cookies.
        s = self.requests_session()
        s.headers["Referer"] = url
        r = s.get(url, timeout=timeout_ms / 1000)
        r.raise_for_status()
        return r.text

    def close(self) -> None:
        pass
