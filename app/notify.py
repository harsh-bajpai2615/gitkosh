"""macOS notification helper (used by the scheduled daily run for review reminders)."""
from __future__ import annotations

import json
import subprocess


def notify(title: str, text: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e", f"display notification {json.dumps(text)} with title {json.dumps(title)}"],
            timeout=10, check=False)
    except Exception:  # noqa: BLE001
        pass
