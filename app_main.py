#!/usr/bin/env python3
"""Single entry point for the bundled app.

Normally launches the Tkinter control panel. When relaunched with
CODESYNC_ROLE=login (the GUI does this to show the native WebKit login window),
it runs the login helper instead — a separate process avoids the
AppKit/Tkinter run-loop conflict.
"""
import os
import sys
import warnings

# charset_normalizer isn't importable from the py2app bundle (known quirk); requests
# falls back fine for our JSON/HTML, so silence its cosmetic startup warning.
warnings.filterwarnings("ignore", message="Unable to find acceptable character detection")


def main():
    role = os.environ.get("CODESYNC_ROLE")
    if role == "login":
        from app.login_helper import main as login_main
        login_main([
            "--out", os.environ.get("CODESYNC_OUT", ""),
            "--platforms", os.environ.get("CODESYNC_PLATFORMS", "leetcode"),
        ])
    elif role == "sync":
        # Headless scheduled run (launched by the LaunchAgent).
        from app.appsupport import load_config, STATE_DIR
        from app.sync_core import run_sync
        cfg = load_config()
        keep = os.environ.get("CODESYNC_KEEP_STREAK") == "1"
        limit = int(os.environ.get("CODESYNC_LIMIT", "0") or "0")
        print(f"[codesync] scheduled sync starting (keep_streak={keep}, limit={limit})")
        run_sync(cfg, STATE_DIR, stop_on_seen=True, limit=limit, keep_streak=keep, log=print)
    else:
        from app.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
