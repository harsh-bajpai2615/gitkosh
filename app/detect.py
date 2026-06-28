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
        # Prefer the logged-in user's own link in the header/account menu — a bare
        # `a[href^="/users/"]` would also match "top users"/ranking widgets on the
        # homepage and detect the wrong handle.
        a = soup.select_one(
            'header a[href^="/users/"], nav a[href^="/users/"], '
            '.user-name-box a[href^="/users/"], .m-nav__user a[href^="/users/"]'
        ) or soup.select_one('a[href^="/users/"]')
        if a:
            return a["href"].rstrip("/").rsplit("/", 1)[-1]
    except Exception:  # noqa: BLE001
        pass
    return ""


def detect_atcoder(session) -> str:
    try:
        s = session.requests_session("atcoder.jp")
        html = s.get("https://atcoder.jp/", timeout=30).text
        import re
        m = re.search(r'userScreenName\s*=\s*"([^"]+)"', html)
        if m:
            return m.group(1)
        soup = BeautifulSoup(html, "html.parser")
        # Scope to the navbar so we don't pick up a ranking/standings user link.
        a = (soup.select_one('.navbar a[href^="/users/"], nav a[href^="/users/"]')
             or soup.select_one('a[href^="/users/"]'))
        if a:
            return a["href"].rstrip("/").rsplit("/", 1)[-1]
    except Exception:  # noqa: BLE001
        pass
    return ""


def detect_geeksforgeeks(session) -> str:
    try:
        s = session.requests_session("geeksforgeeks.org")
        # GFG stores the handle in a cookie on most logged-in sessions.
        for n in ("gfguserName", "user_name", "userName"):
            v = session.cookie(n, "geeksforgeeks.org")
            if v:
                return v
        import re
        html = s.get("https://www.geeksforgeeks.org/", timeout=30).text
        m = re.search(r'"user_name"\s*:\s*"([^"]+)"', html) or re.search(r'/user/([^/"]+)/', html)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return ""


DETECTORS = {
    "codeforces": detect_codeforces,
    "codechef": detect_codechef,
    "atcoder": detect_atcoder,
    "geeksforgeeks": detect_geeksforgeeks,
}
