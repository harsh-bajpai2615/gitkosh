"""In-app auto-updater.

Checks GitHub Releases (constants.RELEASES_REPO) for a newer version, and if found,
downloads the new .app zip, swaps it in place (stripping the download-quarantine flag
so there's no Gatekeeper prompt), and relaunches — no terminal. Uses the public,
unauthenticated GitHub API so it works on any recipient's machine.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

from . import constants

API = "https://api.github.com"


def _ver(v: str):
    # Pad to a fixed width so comparisons across "1.2" vs "1.2.0" are correct
    # (an unequal-length tuple compare would call 1.2.0 "newer" than 1.2,
    # causing a re-download loop, and miss 1.2 -> 1.2.0 updates).
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in (nums + ["0", "0", "0"])[:3])


def check(current: Optional[str] = None) -> Optional[dict]:
    """Return {version, url, notes} if a newer release exists, else None."""
    cur = current or constants.VERSION
    try:
        r = requests.get(f"{API}/repos/{constants.RELEASES_REPO}/releases/latest",
                         headers={"Accept": "application/vnd.github+json"}, timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        tag = d.get("tag_name", "")
        if _ver(tag) <= _ver(cur):
            return None
        url = next((a["browser_download_url"] for a in d.get("assets", [])
                    if a.get("name", "").endswith(".zip")), None)
        if not url:
            return None
        return {"version": tag.lstrip("v"), "url": url, "notes": d.get("body", "") or ""}
    except Exception:  # noqa: BLE001
        return None


def _bundle_path() -> Optional[Path]:
    p = Path(sys.executable).resolve()
    for anc in [p] + list(p.parents):
        if anc.suffix == ".app":
            return anc
    return None


def download_and_apply(url: str, log: Callable[[str], None] = lambda m: None) -> bool:
    """Download the new .app, swap it in, relaunch. Returns True if the swap was launched.
    Caller should quit the app shortly after this returns True."""
    bundle = _bundle_path()
    if not bundle:
        log("Updates only apply to the installed app (not in dev mode).")
        return False
    log("Downloading update…")
    r = requests.get(url, stream=True, timeout=180)
    r.raise_for_status()
    buf = io.BytesIO()
    for chunk in r.iter_content(1 << 20):
        buf.write(chunk)
    tmp = Path(tempfile.mkdtemp(prefix="gitkosh-update-"))
    log("Extracting…")
    with zipfile.ZipFile(buf) as z:
        z.extractall(tmp)
    new_app = next((p for p in [*tmp.iterdir(), *tmp.rglob("*.app")] if p.suffix == ".app"), None)
    if not new_app:
        log("Update package had no .app inside.")
        return False
    script = tmp / "swap.sh"
    # Swap without ever leaving the user with no app: stage the old bundle aside,
    # move the new one in, and only then delete the backup. If the move fails for
    # any reason (disk full, interrupted, permissions), roll the original back.
    script.write_text(
        "#!/bin/sh\n"
        f"PID={os.getpid()}\n"
        'while kill -0 "$PID" 2>/dev/null; do sleep 0.4; done\n'
        f'BAK="{bundle}.bak"\n'
        'rm -rf "$BAK"\n'
        f'if mv "{bundle}" "$BAK" && mv "{new_app}" "{bundle}"; then\n'
        '  rm -rf "$BAK"\n'
        'else\n'
        f'  [ -d "$BAK" ] && [ ! -d "{bundle}" ] && mv "$BAK" "{bundle}"\n'
        'fi\n'
        f'xattr -dr com.apple.quarantine "{bundle}" 2>/dev/null\n'
        f'open "{bundle}"\n'
        f'rm -rf "{tmp}"\n'
    )
    script.chmod(0o755)
    log("Installing update and relaunching…")
    subprocess.Popen(["/bin/sh", str(script)], start_new_session=True)
    return True
