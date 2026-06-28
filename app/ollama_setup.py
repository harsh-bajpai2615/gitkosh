"""One-click local-AI setup via Ollama — no terminal, no key.

Detects Ollama, and if missing: downloads the official macOS app into ~/Applications,
launches it (starts the local server), then pulls a small model via the HTTP API.
We only use the HTTP API at localhost:11434, so the Ollama CLI is never required.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
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


def _server_binary() -> Optional[str]:
    """The headless `ollama` server binary inside an installed bundle."""
    for app in APP_LOCATIONS:
        for sub in ("Contents/Resources/ollama", "Contents/MacOS/ollama"):
            p = os.path.join(app, sub)
            if os.path.exists(p):
                return p
    return None


def _make_executable(path: str) -> None:
    try:
        st = os.stat(path).st_mode
        os.chmod(path, st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _repair_perms() -> None:
    """Python's zipfile drops the +x bit on extract, leaving every bundled binary
    (ollama, llama-server, helpers…) un-launchable -> the server starts but fails
    to spawn its workers. Restore execute on all regular files in the bundle; the
    bit is meaningless on data files (png/plist) so this is safe and instant."""
    for app in APP_LOCATIONS:
        if not os.path.isdir(app):
            continue
        for root, _dirs, files in os.walk(app):
            for name in files:
                _make_executable(os.path.join(root, name))


def ensure_running(progress: Progress = None, wait: int = 90) -> bool:
    if server_up():
        return True
    _repair_perms()
    started = False
    # Preferred: launch the headless server binary directly. This starts the HTTP
    # API on :11434 without Ollama's first-run GUI wizard (which otherwise needs a
    # manual click + admin password and is why "open" alone could hang/fail).
    binp = _server_binary()
    if binp:
        _make_executable(binp)
        try:
            _log(progress, "Starting Ollama server…")
            subprocess.Popen([binp, "serve"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            started = True
        except Exception:  # noqa: BLE001
            started = False
    if not started:  # fall back to launching the .app via LaunchServices
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
    fd, tmp = tempfile.mkstemp(suffix=".zip", prefix="ollama-")
    got, last = 0, 0
    with os.fdopen(fd, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
            got += len(chunk)
            if got - last >= (20 << 20):
                last = got
                mb = f"{got // (1 << 20)}" + (f" / {total // (1 << 20)}" if total else "")
                _log(progress, f"  downloaded {mb} MB")
    _log(progress, "Installing into ~/Applications…")
    app = os.path.join(dest, "Ollama.app")
    shutil.rmtree(app, ignore_errors=True)
    # ditto preserves executable bits AND symlinks; Python's zipfile loses both,
    # which produced a non-executable Ollama.app that never started.
    rc = subprocess.run(["ditto", "-x", "-k", tmp, dest],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    if rc != 0 or not os.path.exists(app):
        # Fallback: zipfile, restoring the unix mode stored in each entry.
        with zipfile.ZipFile(tmp) as z:
            for info in z.infolist():
                out = z.extract(info, dest)
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode:
                    try:
                        os.chmod(out, mode)
                    except OSError:
                        pass
    try:
        os.remove(tmp)
    except OSError:
        pass
    if not os.path.exists(app):
        raise RuntimeError("Ollama.app not found after unzip.")
    _repair_perms()


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


def setup(model: str = DEFAULT_MODEL, progress: Progress = None) -> str:
    """Full flow: install (if needed) -> run -> ensure a usable model.
    Returns the model name to use. Reuses an already-pulled model instead of
    forcing a redundant multi-GB download."""
    if not app_installed() and not server_up():
        install_app(progress)
    if not ensure_running(progress):
        raise RuntimeError("Ollama didn't start. Open the Ollama app once, then retry.")
    have = models()
    if model in have or f"{model}:latest" in have:
        chosen = model
    elif have:
        chosen = have[0]  # already downloaded — no need to pull another model
    else:
        pull_model(model, progress)
        chosen = model
    _log(progress, "Local AI ready.")
    return chosen
