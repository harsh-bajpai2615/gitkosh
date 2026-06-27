"""One-click local-AI setup via Ollama — no terminal, no key.

Detects Ollama, and if missing: downloads the official macOS app into ~/Applications,
launches it (starts the local server), then pulls a small model via the HTTP API.
We only use the HTTP API at localhost:11434, so the Ollama CLI is never required.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import time
import zipfile
from typing import Callable, List, Optional, Tuple

import requests

OLLAMA_URL = "http://localhost:11434"
DOWNLOAD_URL = "https://ollama.com/download/Ollama-darwin.zip"
DEFAULT_MODEL = "llama3.2"  # ~2GB, fast; good enough for the write-ups
APP_LOCATIONS = ["/Applications/Ollama.app", os.path.expanduser("~/Applications/Ollama.app")]

Progress = Optional[Callable[[str], None]]


def _log(progress: Progress, msg: str) -> None:
    if progress:
        progress(msg)


def server_up(timeout: float = 2) -> bool:
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


def models() -> List[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def app_installed() -> bool:
    return any(os.path.exists(p) for p in APP_LOCATIONS)


def status() -> Tuple[str, List[str]]:
    """-> (state, models). state in: ready | running_no_model | installed_not_running | not_installed"""
    if server_up():
        ms = models()
        return ("ready", ms) if ms else ("running_no_model", [])
    return ("installed_not_running", []) if app_installed() else ("not_installed", [])


def ensure_running(progress: Progress = None, wait: int = 90) -> bool:
    if server_up():
        return True
    for p in APP_LOCATIONS:
        if os.path.exists(p):
            _log(progress, "Starting Ollama…")
            subprocess.run(["open", p], check=False)
            break
    deadline = time.time() + wait
    while time.time() < deadline:
        if server_up():
            return True
        time.sleep(2)
    return server_up()


def install_app(progress: Progress = None) -> None:
    dest = os.path.expanduser("~/Applications")
    os.makedirs(dest, exist_ok=True)
    _log(progress, "Downloading Ollama…")
    r = requests.get(DOWNLOAD_URL, stream=True, timeout=60)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    buf, got, last = io.BytesIO(), 0, 0
    for chunk in r.iter_content(1 << 20):
        buf.write(chunk)
        got += len(chunk)
        if got - last >= (20 << 20):
            last = got
            mb = f"{got // (1 << 20)}" + (f" / {total // (1 << 20)}" if total else "")
            _log(progress, f"  downloaded {mb} MB")
    _log(progress, "Installing into ~/Applications…")
    with zipfile.ZipFile(buf) as z:
        z.extractall(dest)
    app = os.path.join(dest, "Ollama.app")
    if not os.path.exists(app):
        raise RuntimeError("Ollama.app not found after unzip.")
    subprocess.run(["open", app], check=False)


def pull_model(model: str, progress: Progress = None) -> None:
    _log(progress, f"Downloading model '{model}' (one-time, a couple GB)…")
    with requests.post(f"{OLLAMA_URL}/api/pull", json={"name": model}, stream=True, timeout=None) as r:
        r.raise_for_status()
        last_pct = -1
        for line in r.iter_lines():
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("error"):
                raise RuntimeError(d["error"])
            tot, comp = d.get("total"), d.get("completed")
            if tot and comp:
                pct = int(comp * 100 / tot)
                if pct >= last_pct + 5:
                    last_pct = pct
                    _log(progress, f"  {d.get('status', 'pulling')}: {pct}%")
    _log(progress, f"Model '{model}' ready.")


def setup(model: str = DEFAULT_MODEL, progress: Progress = None) -> None:
    """Full flow: install (if needed) -> run -> pull model."""
    if not app_installed() and not server_up():
        install_app(progress)
    if not ensure_running(progress):
        raise RuntimeError("Ollama didn't start. Open the Ollama app once, then retry.")
    if model not in models():
        pull_model(model, progress)
    _log(progress, "Local AI ready.")
