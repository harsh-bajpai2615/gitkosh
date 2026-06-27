"""Authentication via a real browser you log into once.

You log into each site in a Playwright-controlled browser; cookies persist in a
local profile dir and a saved storage_state.json. We never see your passwords.
Extractors then reuse those cookies through a plain `requests` session, and can
fall back to a real browser fetch for Cloudflare-protected pages.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Where each platform wants you to land for login, and a URL we can poll to
# confirm you're authenticated.
LOGIN_URLS = {
    "leetcode": "https://leetcode.com/accounts/login/",
    "codeforces": "https://codeforces.com/enter",
    "codechef": "https://www.codechef.com/login",
    "neetcode": "https://leetcode.com/accounts/login/",  # neetcode rides leetcode
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Cookie that proves you're logged in, per platform (for auto-detecting login).
# neetcode rides leetcode's session. codeforces/codechef have no reliable marker.
AUTH_COOKIES = {
    "leetcode": ("LEETCODE_SESSION", "leetcode.com"),
    "neetcode": ("LEETCODE_SESSION", "leetcode.com"),
}


class Session:
    def __init__(self, profile_dir: Path, state_dir: Path):
        self.profile_dir = Path(profile_dir)
        self.state_path = Path(state_dir) / "storage_state.json"
        self._pw = None
        self._browser_ctx = None

    # ---------------- login ----------------
    def login(self, platforms: List[str], timeout: int = 600) -> None:
        """Open a browser, let the user log into each platform, then save cookies.

        For platforms with a known auth-cookie marker (leetcode/neetcode) login is
        auto-detected by polling — no terminal Enter needed, so this works when
        launched via `!`. For the others we ask for an Enter press when a TTY exists.
        """
        from playwright.sync_api import sync_playwright

        urls = []
        for p in platforms:
            u = LOGIN_URLS.get(p)
            if u and u not in urls:
                urls.append(u)
        markered = [p for p in platforms if p in AUTH_COOKIES]
        unmarkered = [p for p in platforms if p not in AUTH_COOKIES]

        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                user_agent=UA,
                args=["--disable-blink-features=AutomationControlled"],
            )
            for i, u in enumerate(urls):
                page = ctx.pages[0] if i == 0 and ctx.pages else ctx.new_page()
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:  # noqa: BLE001
                    print(f"  (could not open {u}: {e})")

            print("\n" + "=" * 64)
            print("A browser window is open. Log into:", ", ".join(platforms))
            print("=" * 64)

            if markered:
                self._wait_for_login(ctx, markered, timeout)
            if unmarkered:
                print(f"Can't auto-detect login for: {', '.join(unmarkered)}.")
                try:
                    input("Log into them, then press ENTER here to save... ")
                except (EOFError, OSError):
                    print("(no terminal input; waiting 60s for you to finish logging in)")
                    self._sleep(60)

            state = ctx.storage_state()
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state, indent=2))
            ctx.close()
        print(f"Saved {len(state.get('cookies', []))} cookies to {self.state_path}")

    @staticmethod
    def _sleep(seconds: float) -> None:
        import time
        time.sleep(seconds)

    def _wait_for_login(self, ctx, platforms: List[str], timeout: int) -> None:
        """Poll until each platform's auth cookie appears (or timeout)."""
        import time
        wanted = {p: AUTH_COOKIES[p] for p in platforms}
        print(f"Waiting for login on: {', '.join(platforms)} (auto-detects, up to {timeout}s)...")
        deadline = time.time() + timeout
        done = set()
        while time.time() < deadline and len(done) < len(wanted):
            cookies = ctx.cookies()
            for p, (name, dom) in wanted.items():
                if p in done:
                    continue
                if any(c["name"] == name and dom in c.get("domain", "") and c.get("value") for c in cookies):
                    done.add(p)
                    print(f"  ✓ {p} logged in")
            time.sleep(2)
        missing = [p for p in wanted if p not in done]
        if missing:
            print(f"  ! timed out waiting for: {', '.join(missing)} (saving anyway)")

    def has_state(self) -> bool:
        return self.state_path.exists()

    def _cookies(self) -> List[dict]:
        if not self.state_path.exists():
            raise RuntimeError("No saved session. Run `codesync login` first.")
        return json.loads(self.state_path.read_text()).get("cookies", [])

    def cookie(self, name: str, domain_contains: str = "") -> Optional[str]:
        for c in self._cookies():
            if c["name"] == name and domain_contains in c.get("domain", ""):
                return c["value"]
        return None

    # ---------------- requests session ----------------
    def requests_session(self, domain_contains: str = "") -> requests.Session:
        """A requests.Session preloaded with the saved cookies (optionally filtered)."""
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

    # ---------------- browser fetch (Cloudflare fallback) ----------------
    def browser_fetch(self, url: str, wait_selector: str = "", timeout_ms: int = 30000) -> str:
        """Fetch a URL with the real (persistent) browser. Returns page HTML."""
        from playwright.sync_api import sync_playwright

        if self._pw is None:
            self._pw = sync_playwright().start()
            self._browser_ctx = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir), headless=True, user_agent=UA,
            )
        page = self._browser_ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass
            return page.content()
        finally:
            page.close()

    def close(self) -> None:
        if self._browser_ctx:
            self._browser_ctx.close()
        if self._pw:
            self._pw.stop()
        self._browser_ctx = None
        self._pw = None
