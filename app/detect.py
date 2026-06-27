"""Auto-detect Codeforces / CodeChef handles from the logged-in session,
so the UI needs no handle fields. Best-effort; returns "" if it can't tell.
"""
from __future__ import annotations

from bs4 import BeautifulSoup


def detect_codeforces(session) -> str:
    try:
        s = session.requests_session("codeforces.com")
        html = s.get("https://codeforces.com/", timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        # When logged in, the personal sidebar links to the user's own profile.
        sidebar = soup.select_one(".personal-sidebar") or soup
        a = sidebar.select_one('a[href^="/profile/"]')
        if a:
            return a.get_text(strip=True) or a["href"].rstrip("/").rsplit("/", 1)[-1]
    except Exception:  # noqa: BLE001
        pass
    return ""


def detect_codechef(session) -> str:
    try:
        s = session.requests_session("codechef.com")
        html = s.get("https://www.codechef.com/", timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        a = soup.select_one('a[href^="/users/"]')
        if a:
            return a["href"].rstrip("/").rsplit("/", 1)[-1]
    except Exception:  # noqa: BLE001
        pass
    return ""


DETECTORS = {"codeforces": detect_codeforces, "codechef": detect_codechef}
