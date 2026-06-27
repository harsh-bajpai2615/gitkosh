#!/usr/bin/env python3
"""Single entry point for the bundled app.

Normally launches the Tkinter control panel. When relaunched with
GITKOSH_ROLE=login (the GUI does this to show the native WebKit login window),
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
    role = os.environ.get("GITKOSH_ROLE")
    if role == "login":
        from app.login_helper import main as login_main
        login_main([
            "--out", os.environ.get("GITKOSH_OUT", ""),
            "--platforms", os.environ.get("GITKOSH_PLATFORMS", "leetcode"),
        ])
    elif role == "sync":
        # Headless scheduled run (launched by the LaunchAgent).
        from app.appsupport import load_config, STATE_DIR
        from app.sync_core import run_sync
        cfg = load_config()
        keep = os.environ.get("GITKOSH_KEEP_STREAK") == "1"
        limit = int(os.environ.get("GITKOSH_LIMIT", "0") or "0")
        print(f"[GitKosh] scheduled sync starting (keep_streak={keep}, limit={limit})")
        res = run_sync(cfg, STATE_DIR, stop_on_seen=True, limit=limit, keep_streak=keep, log=print)
        # Daily review reminder (spaced repetition)
        try:
            from app import srs, notify
            from gitkosh.store import Store
            st = srs.stats(Store(STATE_DIR).all(), STATE_DIR)
            pushed = res.get("pushed", 0)
            bits = []
            if pushed:
                bits.append(f"Synced {pushed} new solution(s)")
            if st["due"]:
                bits.append(f"{st['due']} problem(s) due for review")
            if bits:
                notify.notify("GitKosh", " · ".join(bits))
        except Exception as e:  # noqa: BLE001
            print(f"[GitKosh] reminder skipped: {e}")
    else:
        from app.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
