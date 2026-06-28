"""Tiny local code runner for in-app practice.

Runs the user's Python in a subprocess with a timeout and captures output. It's
their own code on their own machine (like a local IDE), so no sandbox — but we cap
time and never touch the network.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time


def run_python(code: str, stdin: str = "", timeout: int = 6) -> dict:
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        t0 = time.time()
        p = subprocess.run([sys.executable, path], input=stdin, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"ok": p.returncode == 0, "stdout": p.stdout, "stderr": p.stderr,
                "ms": round((time.time() - t0) * 1000)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"⏱ Time limit exceeded ({timeout}s)", "ms": timeout * 1000}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stdout": "", "stderr": str(e), "ms": 0}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
