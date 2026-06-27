"""Daily background scheduling via a macOS LaunchAgent.

Writes ~/Library/LaunchAgents/<LABEL>.plist that launchd runs every day at a set
time — even when CodeSync isn't open, no human prompt. The agent launches the app
binary with CODESYNC_ROLE=sync (handled in app_main.py) to run a headless sync.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

LABEL = "com.harshbajpai.codesync.sync"
PLIST_PATH = Path(os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist"))
LOG_PATH = os.path.expanduser("~/Library/Application Support/codesync/scheduler.log")


def is_enabled() -> bool:
    return PLIST_PATH.exists()


def read_schedule() -> Optional[Tuple[int, int, bool]]:
    """Returns (hour, minute, keep_streak) or None."""
    if not PLIST_PATH.exists():
        return None
    try:
        d = plistlib.loads(PLIST_PATH.read_bytes())
        ci = d.get("StartCalendarInterval", {}) or {}
        ks = (d.get("EnvironmentVariables", {}) or {}).get("CODESYNC_KEEP_STREAK") == "1"
        return int(ci.get("Hour", 9)), int(ci.get("Minute", 0)), ks
    except Exception:  # noqa: BLE001
        return None


def enable(program_args: List[str], hour: int, minute: int, keep_streak: bool) -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": program_args,
        "EnvironmentVariables": {
            "CODESYNC_ROLE": "sync",
            "CODESYNC_KEEP_STREAK": "1" if keep_streak else "0",
        },
        "StartCalendarInterval": {"Hour": int(hour), "Minute": int(minute)},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": LOG_PATH,
        "StandardErrorPath": LOG_PATH,
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    # reload so launchd picks up changes
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)], capture_output=True)


def disable() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink()


def run_now() -> None:
    """Kick the agent immediately (for a manual test of the scheduled path)."""
    subprocess.run(["launchctl", "start", LABEL], capture_output=True)
