"""Tiny local code runner for in-app practice.

Runs the user's code in a subprocess with a timeout and captures output. It's
their own code on their own machine (like a local IDE), so no sandbox — but we
cap time and never touch the network.

Python runs out of the box (it ships with the app). C++, Java and JavaScript use
the toolchains already on the user's machine (g++/clang++, javac+java, node); if
one isn't installed we return a clear, actionable install hint instead of a crash.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

# Display metadata + source extension per supported language.
LANGS = {
    "python":     {"label": "Python", "ext": "py"},
    "cpp":        {"label": "C++",    "ext": "cpp"},
    "java":       {"label": "Java",   "ext": "java"},
    "javascript": {"label": "JavaScript", "ext": "js"},
}

# What to tell the user when a language's toolchain isn't on PATH.
_INSTALL_HINT = {
    "cpp": "C++ needs a compiler. Install the Xcode Command Line Tools: run "
           "`xcode-select --install` in Terminal, then try again.",
    "java": "Java isn't installed. Install a JDK (e.g. `brew install openjdk`), "
            "then try again.",
    "javascript": "Node.js isn't installed. Get it from nodejs.org "
                  "(or `brew install node`), then try again.",
}

_COMPILE_TIMEOUT = 20  # seconds for the compile step (separate from the run timeout)


def _result(ok, stdout="", stderr="", ms=0):
    return {"ok": ok, "stdout": stdout, "stderr": stderr, "ms": ms}


def _cpp_compiler():
    return shutil.which("g++") or shutil.which("clang++")


def _java_classname(code: str) -> str:
    """Java requires the file to match the public class; derive it from the source."""
    m = re.search(r"public\s+class\s+(\w+)", code)
    if m:
        return m.group(1)
    m = re.search(r"\bclass\s+(\w+)", code)
    return m.group(1) if m else "Main"


def run(code: str, lang: str = "python", stdin: str = "", timeout: int = 6) -> dict:
    """Run `code` in `lang`, returning {ok, stdout, stderr, ms}."""
    lang = (lang or "python").lower()
    if lang not in LANGS:
        return _result(False, stderr=f"Unsupported language: {lang}")
    if lang == "python":
        return run_python(code, stdin, timeout)
    if lang == "javascript":
        return _run_node(code, stdin, timeout)
    if lang == "cpp":
        return _run_cpp(code, stdin, timeout)
    if lang == "java":
        return _run_java(code, stdin, timeout)
    return _result(False, stderr=f"Unsupported language: {lang}")


def run_python(code: str, stdin: str = "", timeout: int = 6) -> dict:
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        t0 = time.time()
        p = subprocess.run([sys.executable, path], input=stdin, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return _result(p.returncode == 0, p.stdout, p.stderr, round((time.time() - t0) * 1000))
    except subprocess.TimeoutExpired:
        return _result(False, stderr=f"⏱ Time limit exceeded ({timeout}s)", ms=timeout * 1000)
    except Exception as e:  # noqa: BLE001
        return _result(False, stderr=str(e))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _exec(argv, stdin, timeout, cwd=None):
    """Run an already-built program, mapping timeouts/missing-binary to a result."""
    t0 = time.time()
    try:
        p = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
        return _result(p.returncode == 0, p.stdout, p.stderr, round((time.time() - t0) * 1000))
    except subprocess.TimeoutExpired:
        return _result(False, stderr=f"⏱ Time limit exceeded ({timeout}s)", ms=timeout * 1000)
    except Exception as e:  # noqa: BLE001 — never let a launch failure reach the bridge as null
        return _result(False, stderr=str(e))


def _run_node(code, stdin, timeout):
    node = shutil.which("node")
    if not node:
        return _result(False, stderr=_INSTALL_HINT["javascript"])
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "main.js")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        return _exec([node, src], stdin, timeout)


def _run_cpp(code, stdin, timeout):
    cc = _cpp_compiler()
    if not cc:
        return _result(False, stderr=_INSTALL_HINT["cpp"])
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "main.cpp")
        exe = os.path.join(d, "main.out")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            c = subprocess.run([cc, "-std=c++17", "-O2", "-o", exe, src],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=_COMPILE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return _result(False, stderr=f"⏱ Compilation timed out ({_COMPILE_TIMEOUT}s)")
        if c.returncode != 0:
            return _result(False, stderr="Compilation failed:\n" + (c.stderr or c.stdout))
        return _exec([exe], stdin, timeout)


def _run_java(code, stdin, timeout):
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java:
        return _result(False, stderr=_INSTALL_HINT["java"])
    cls = _java_classname(code)
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, f"{cls}.java")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            c = subprocess.run([javac, src], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=_COMPILE_TIMEOUT, cwd=d)
        except subprocess.TimeoutExpired:
            return _result(False, stderr=f"⏱ Compilation timed out ({_COMPILE_TIMEOUT}s)")
        if c.returncode != 0:
            return _result(False, stderr="Compilation failed:\n" + (c.stderr or c.stdout))
        return _exec([java, "-cp", d, cls], stdin, timeout, cwd=d)


def available() -> dict:
    """Map each language -> whether its toolchain is runnable now (for UI hints)."""
    return {
        "python": True,
        "javascript": bool(shutil.which("node")),
        "cpp": bool(_cpp_compiler()),
        "java": bool(shutil.which("javac") and shutil.which("java")),
    }
