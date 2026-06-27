"""codesync — mediator between LeetCode/Codeforces/CodeChef/NeetCode and GitHub.

Guided, themed UI: log into your 5 accounts (GitHub first), then sync. No coding
happens here; a platform's web view is only its login screen.
"""
from __future__ import annotations

import contextlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from codesync.readme_gen import ReadmeGenerator
from codesync.store import Store
from codesync.platforms import REGISTRY

from . import constants, github_auth, ollama_setup, scheduler, updater
from .appsupport import STATE_DIR, load_config, save_config
from .github_api import GitHubAPI
from .native_session import NativeSession
from .detect import DETECTORS
from .sync_core import run_sync, read_last_run

try:
    from .logo_data import LOGO_PNG_B64
except Exception:  # noqa: BLE001
    LOGO_PNG_B64 = ""

CP = ["leetcode", "codeforces", "codechef", "neetcode", "atcoder", "geeksforgeeks"]
DOMAINS = {"leetcode": "leetcode.com", "codeforces": "codeforces.com",
           "codechef": "codechef.com", "neetcode": "neetcode.io",
           "atcoder": "atcoder.jp", "geeksforgeeks": "geeksforgeeks.org"}
LABELS = {"leetcode": "LeetCode", "codeforces": "Codeforces",
          "codechef": "CodeChef", "neetcode": "NeetCode",
          "atcoder": "AtCoder", "geeksforgeeks": "GeeksforGeeks"}
PROVIDERS = ["gemini", "groq", "ollama", "none"]
PROVIDER_MODEL = {"gemini": "gemini-2.5-flash", "groq": "llama-3.3-70b-versatile",
                  "ollama": "llama3.1", "none": ""}

# palette
BG = "#EEF0F6"; CARD = "#FFFFFF"; INK = "#1F2433"; MUTED = "#6B7280"
ACCENT = "#5B5BD6"; ACCENT_DK = "#4F46E5"; BORDER = "#E3E6EF"
OK_FG = "#0F7B3B"; OK_BG = "#DCFCE7"; NO_FG = "#B42318"; NO_BG = "#FDECEA"
LOCK_FG = "#9AA1B2"; LOCK_BG = "#F1F3F8"
FONT = "Helvetica Neue"; MONO = "Menlo"


def cp_status() -> dict:
    p = STATE_DIR / "storage_state.json"
    domains = set()
    if p.exists():
        try:
            for c in json.loads(p.read_text()).get("cookies", []):
                domains.add(c.get("domain", ""))
        except Exception:  # noqa: BLE001
            pass
    return {name: any(dom in d for d in domains) for name, dom in DOMAINS.items()}


def _main_executable() -> str:
    """The bundle's main app binary. In a py2app .app, sys.executable points at the
    sibling 'python' helper, so relaunch the other executable in Contents/MacOS/."""
    macos = os.path.dirname(sys.executable)
    try:
        for f in os.listdir(macos):
            full = os.path.join(macos, f)
            if f != "python" and os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    except OSError:
        pass
    return sys.executable


class QueueWriter:
    def __init__(self, q): self.q = q
    def write(self, s):
        if s: self.q.put(s)
    def flush(self): pass


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.logq = queue.Queue()
        self.worker = None
        self.stop_evt = threading.Event()
        self.pills = {}

        root.title("GitKosh")
        root.configure(bg=BG)
        root.geometry("760x780")
        root.minsize(560, 520)
        self.logo_img = None
        if LOGO_PNG_B64:
            try:
                self.logo_img = tk.PhotoImage(data=LOGO_PNG_B64)
                root.iconphoto(True, self.logo_img)
            except Exception:  # noqa: BLE001
                self.logo_img = None

        self._styles()
        self._build()
        self.refresh_status()
        self.root.after(100, self._drain_log)
        self._refresh_ollama()
        self._refresh_schedule()
        self.update_info = None
        self._check_updates()

    # ---------------- styling ----------------
    def _styles(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=INK, font=(FONT, 12))
        s.configure("Card.TFrame", background=CARD)
        s.configure("Card.TLabel", background=CARD, foreground=INK, font=(FONT, 12))
        s.configure("CardName.TLabel", background=CARD, foreground=INK, font=(FONT, 13, "bold"))
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=(FONT, 11))
        s.configure("Section.TLabel", background=BG, foreground=MUTED, font=(FONT, 11, "bold"))
        s.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF",
                    font=(FONT, 12, "bold"), padding=(16, 9), borderwidth=0, focuscolor=ACCENT)
        s.map("Accent.TButton", background=[("active", ACCENT_DK), ("disabled", "#C7CAD6")])
        s.configure("Ghost.TButton", background="#F3F4FB", foreground=ACCENT_DK,
                    font=(FONT, 11, "bold"), padding=(12, 6), borderwidth=0)
        s.map("Ghost.TButton", background=[("active", "#E6E8FF"), ("disabled", "#F1F3F8")])
        s.configure("TCombobox", fieldbackground=CARD, background=CARD)
        s.configure("TCheckbutton", background=CARD, foreground=INK)
        s.configure("CS.Horizontal.TProgressbar", troughcolor=BORDER, background=ACCENT,
                    borderwidth=0, thickness=12)

    def _card(self, parent):
        f = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, bd=0)
        f.pack(fill="x", padx=16, pady=(0, 12))
        return f

    def _pill(self, parent, text, fg, bg):
        return tk.Label(parent, text=text, fg=fg, bg=bg, font=(FONT, 10, "bold"), padx=10, pady=3)

    def _entry(self, parent, var, width, show=None):
        e = tk.Entry(parent, textvariable=var, width=width, relief="flat", bd=0,
                     highlightbackground=BORDER, highlightcolor=ACCENT, highlightthickness=1,
                     bg="#FFFFFF", fg=INK, font=(FONT, 12), insertbackground=INK)
        if show:
            e.config(show=show)
        return e

    # ---------------- layout ----------------
    def _build(self):
        # scrollable, centered content column (so Activity is reachable at any window size)
        outer = tk.Frame(self.root, bg=BG); outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="n")
        maxw = 700

        def _fit(e):
            w = min(e.width, maxw)
            self.canvas.itemconfig(self._win, width=w)
            self.canvas.coords(self._win, (e.width - w) / 2, 0)
        self.canvas.bind("<Configure>", _fit)
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * e.delta), "units"))

        b = self.body

        # header
        head = tk.Frame(b, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        head.pack(fill="x", padx=16, pady=16)
        self.header = head
        if self.logo_img:
            tk.Label(head, image=self.logo_img, bg=CARD).pack(side="left", padx=(14, 12), pady=12)
        txt = tk.Frame(head, bg=CARD); txt.pack(side="left", pady=12)
        tk.Label(txt, text="GitKosh", bg=CARD, fg=INK, font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(txt, text=f"Sync your coding-platform solutions to GitHub  ·  v{constants.VERSION}",
                 bg=CARD, fg=MUTED, font=(FONT, 12)).pack(anchor="w")

        # update banner (hidden unless a newer release exists)
        self.update_bar = tk.Frame(b, bg="#FFF7E6", highlightbackground="#F0D58C", highlightthickness=1)
        self.update_lbl = tk.Label(self.update_bar, text="", bg="#FFF7E6", fg="#7A5B00", font=(FONT, 11, "bold"))
        self.update_lbl.pack(side="left", padx=12, pady=8)
        ttk.Button(self.update_bar, text="Update now", style="Ghost.TButton",
                   command=self.do_update).pack(side="right", padx=10, pady=6)

        # steps strip
        steps = tk.Frame(b, bg=BG); steps.pack(fill="x", padx=16)
        self.step_chips = {}
        for i, (key, label) in enumerate([("1", "Connect GitHub"), ("2", "Connect a coding site"),
                                          ("3", "Sync to GitHub")]):
            chip = self._pill(steps, f"{key}  {label}", LOCK_FG, LOCK_BG)
            chip.pack(side="left", padx=(0, 8), pady=(0, 12))
            self.step_chips[key] = chip

        # Step 1 — GitHub
        ttk.Label(b, text="STEP 1 — CONNECT GITHUB  (do this first)",
                  style="Section.TLabel").pack(anchor="w", padx=18, pady=(2, 4))
        gh = self._card(b)
        row = tk.Frame(gh, bg=CARD); row.pack(fill="x", padx=14, pady=12)
        ttk.Label(row, text="GitHub", style="CardName.TLabel", width=12).pack(side="left")
        self.pills["github"] = self._pill(row, "…", LOCK_FG, LOCK_BG); self.pills["github"].pack(side="left")
        self.gh_btn = ttk.Button(row, text="Log in", style="Ghost.TButton", command=self.github_login)
        self.gh_btn.pack(side="right")

        # Step 2 — coding sites
        ttk.Label(b, text="STEP 2 — CONNECT YOUR CODING SITES",
                  style="Section.TLabel").pack(anchor="w", padx=18, pady=(4, 4))
        sites = self._card(b)
        for name in CP:
            row = tk.Frame(sites, bg=CARD); row.pack(fill="x", padx=14, pady=8)
            ttk.Label(row, text=LABELS[name], style="CardName.TLabel", width=12).pack(side="left")
            self.pills[name] = self._pill(row, "…", LOCK_FG, LOCK_BG); self.pills[name].pack(side="left")
            ttk.Button(row, text="Log in", style="Ghost.TButton",
                       command=lambda n=name: self.cp_login(n)).pack(side="right")
        tk.Label(sites, text="Tip: NeetCode mirrors your LeetCode solves — connect LeetCode too.",
                 bg=CARD, fg=MUTED, font=(FONT, 10)).pack(anchor="w", padx=14, pady=(0, 10))

        # Setup
        ttk.Label(b, text="SETUP  (set once)", style="Section.TLabel").pack(anchor="w", padx=18, pady=(4, 4))
        setup = self._card(b)
        g = tk.Frame(setup, bg=CARD); g.pack(fill="x", padx=14, pady=12)
        ttk.Label(g, text="Repo name", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.repo_var = tk.StringVar(value=self.cfg["github"].get("repo", "competitive-programming"))
        self._entry(g, self.repo_var, 26).grid(row=0, column=1, sticky="w", padx=8, ipady=4)
        self.private_var = tk.BooleanVar(value=self.cfg["github"].get("private", True))
        tk.Checkbutton(g, text="private", variable=self.private_var, bg=CARD, fg=INK,
                       activebackground=CARD, highlightthickness=0, font=(FONT, 11)).grid(row=0, column=2, padx=8)
        llm = self.cfg["readme"].get("llm", {})
        ttk.Label(g, text="Write-ups", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.provider_var = tk.StringVar(value=llm.get("provider", "gemini"))
        cb = ttk.Combobox(g, textvariable=self.provider_var, values=PROVIDERS, width=10, state="readonly")
        cb.grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self.model_var.set(PROVIDER_MODEL.get(self.provider_var.get(), "")))
        self.model_var = tk.StringVar(value=llm.get("model", "gemini-2.5-flash"))
        ttk.Label(g, text="API key", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.key_var = tk.StringVar(value=llm.get("api_key", ""))
        self._entry(g, self.key_var, 34, show="•").grid(row=2, column=1, columnspan=2, sticky="we", padx=8, pady=(8, 0), ipady=4)
        tk.Label(g, text="free keys: aistudio.google.com/apikey · console.groq.com  ·  or pick 'ollama' (local, no key)",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).grid(row=3, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Button(g, text="Save", style="Ghost.TButton", command=self.save_settings).grid(row=0, column=3, rowspan=2, padx=10)

        # One-click free local AI (Ollama) — no key, no terminal, unlimited
        orow = tk.Frame(g, bg=CARD); orow.grid(row=4, column=0, columnspan=4, sticky="w", pady=(12, 0))
        tk.Label(orow, text="Free local AI (Ollama):", bg=CARD, fg=MUTED, font=(FONT, 11)).pack(side="left")
        self.ollama_pill = self._pill(orow, "checking…", LOCK_FG, LOCK_BG); self.ollama_pill.pack(side="left", padx=8)
        self.ollama_btn = ttk.Button(orow, text="Set up", style="Ghost.TButton", command=self.setup_ollama)
        self.ollama_btn.pack(side="left")
        tk.Label(g, text="One click: installs Ollama + a model so write-ups are unlimited & free (no key needed).",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).grid(row=5, column=0, columnspan=4, sticky="w", padx=2, pady=(2, 2))

        # Automation
        ttk.Label(b, text="AUTOMATION — hands-free & streak-keeping", style="Section.TLabel").pack(anchor="w", padx=18, pady=(4, 4))
        auto = self._card(b)
        a = tk.Frame(auto, bg=CARD); a.pack(fill="x", padx=14, pady=12)
        self.sched_var = tk.BooleanVar(value=False)
        tk.Checkbutton(a, text="Sync automatically every day at", variable=self.sched_var, bg=CARD, fg=INK,
                       activebackground=CARD, highlightthickness=0, font=(FONT, 12)).grid(row=0, column=0, sticky="w")
        self.time_var = tk.StringVar(value="09:00")
        self._entry(a, self.time_var, 6).grid(row=0, column=1, sticky="w", padx=8, ipady=3)
        ttk.Button(a, text="Apply", style="Ghost.TButton", command=self.apply_schedule).grid(row=0, column=2, padx=6)
        self.streak_var = tk.BooleanVar(value=True)
        tk.Checkbutton(a, text="Keep my GitHub streak alive (commit at least once a day, even with no new solves)",
                       variable=self.streak_var, bg=CARD, fg=INK, activebackground=CARD,
                       highlightthickness=0, font=(FONT, 11)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.sched_status = tk.Label(a, text="", bg=CARD, fg=MUTED, font=(FONT, 10), anchor="w")
        self.sched_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # Step 3 — sync
        ttk.Label(b, text="STEP 3 — SYNC", style="Section.TLabel").pack(anchor="w", padx=18, pady=(4, 4))
        bar = tk.Frame(b, bg=BG); bar.pack(fill="x", padx=16, pady=(0, 8))
        self.sync_btn = ttk.Button(bar, text="Sync now", style="Accent.TButton", command=self.do_backfill)
        self.sync_btn.pack(side="left")
        self.watch_btn = ttk.Button(bar, text="Auto-sync: off", style="Ghost.TButton", command=self.toggle_watch)
        self.watch_btn.pack(side="left", padx=8)
        self.reset_btn = ttk.Button(bar, text="Reset & re-backfill", style="Ghost.TButton", command=self.do_reset)
        self.reset_btn.pack(side="left", padx=(0, 8))
        tk.Label(bar, text="limit", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.limit_var = tk.StringVar(value="0")
        self._entry(bar, self.limit_var, 4).pack(side="left", padx=4, ipady=3)
        self.hint = tk.Label(bar, text="", bg=BG, fg=MUTED, font=(FONT, 10)); self.hint.pack(side="left", padx=8)
        self.summary = tk.Label(bar, text="", bg=BG, fg=OK_FG, font=(FONT, 11, "bold")); self.summary.pack(side="right")

        # progress (live during sync)
        prog = self._card(b)
        inner = tk.Frame(prog, bg=CARD); inner.pack(fill="x", padx=14, pady=10)
        self.prog_label = tk.Label(inner, text="Idle — connect accounts, then Sync.", bg=CARD,
                                   fg=INK, font=(FONT, 12, "bold"), anchor="w")
        self.prog_label.pack(fill="x")
        self.prog = ttk.Progressbar(inner, style="CS.Horizontal.TProgressbar",
                                    mode="determinate", maximum=100, value=0)
        self.prog.pack(fill="x", pady=(6, 2))
        self.prog_sub = tk.Label(inner, text="", bg=CARD, fg=MUTED, font=(FONT, 10), anchor="w")
        self.prog_sub.pack(fill="x")

        # status portal
        portal = self._card(b)
        tk.Label(portal, text="Activity", bg=CARD, fg=MUTED, font=(FONT, 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        self.log = scrolledtext.ScrolledText(portal, height=9, font=(MONO, 10), bg="#FBFBFE",
                                             fg="#374151", relief="flat", borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    # ---------------- status ----------------
    def refresh_status(self):
        st = cp_status()
        for name in CP:
            ok = st.get(name)
            self.pills[name].config(text="Connected" if ok else "Not connected",
                                    fg=OK_FG if ok else NO_FG, bg=OK_BG if ok else NO_BG)
        gh = github_auth.load_github(STATE_DIR)
        gh_ok = bool(gh)
        if gh_ok:
            self.pills["github"].config(text=gh.get("login", "Connected"), fg=OK_FG, bg=OK_BG)
            self.gh_btn.config(text="Log out", command=self.github_logout)
        else:
            self.pills["github"].config(text="Not connected", fg=NO_FG, bg=NO_BG)
            self.gh_btn.config(text="Log in", command=self.github_login)

        any_cp = any(st.values())
        self._set_chip("1", gh_ok)
        self._set_chip("2", any_cp)
        self._set_chip("3", gh_ok and any_cp)

        ready = gh_ok and any_cp
        self.sync_btn.config(state="normal" if ready else "disabled")
        self.watch_btn.config(state="normal" if ready else "disabled")
        self.reset_btn.config(state="normal" if ready else "disabled")
        if ready:
            self.hint.config(text="")
        elif not gh_ok:
            self.hint.config(text="← connect GitHub first")
        else:
            self.hint.config(text="← connect a coding site")

    def _set_chip(self, key, done):
        label = {"1": "Connect GitHub", "2": "Connect a coding site", "3": "Sync to GitHub"}[key]
        if done:
            self.step_chips[key].config(text=f"✓  {label}", fg=OK_FG, bg=OK_BG)
        else:
            self.step_chips[key].config(text=f"{key}  {label}", fg=LOCK_FG, bg=LOCK_BG)

    def _drain_log(self):
        try:
            while True:
                self.log.insert("end", self.logq.get_nowait())
                self.log.see("end")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    # ---------------- CP login ----------------
    def cp_login(self, name):
        out = str(STATE_DIR / "storage_state.json")
        self.logq.put(f"Opening {LABELS[name]} login…\n")

        def run():
            try:
                if getattr(sys, "frozen", None):
                    env = dict(os.environ, CODESYNC_ROLE="login", CODESYNC_OUT=out, CODESYNC_PLATFORMS=name)
                    subprocess.run([_main_executable()], env=env, check=False)
                else:
                    subprocess.run([sys.executable, "-m", "app.login_helper", "--out", out, "--platforms", name], check=False)
            except Exception as e:  # noqa: BLE001
                self.logq.put(f"login error: {e}\n")
            self.root.after(0, self.refresh_status)

        threading.Thread(target=run, daemon=True).start()

    # ---------------- GitHub login ----------------
    def _client_id(self):
        return self.cfg["github"].get("client_id") or constants.GITHUB_CLIENT_ID

    def github_login(self):
        cid = self._client_id()
        if not cid:
            messagebox.showerror("GitHub login not configured",
                                 "No GitHub client_id set. Register a GitHub OAuth App (Device Flow) "
                                 "and put its client_id in app/constants.py.")
            return
        self.gh_btn.config(state="disabled")
        self.logq.put("Starting GitHub login…\n")

        def run():
            try:
                d = github_auth.start_device_flow(cid)
                self.root.after(0, lambda: self._show_code(d))
                token = github_auth.poll_for_token(cid, d["device_code"], d.get("interval", 5), d.get("expires_in", 900))
                login = GitHubAPI(token, "x").whoami()
                github_auth.save_token(STATE_DIR, token, login)
                self.logq.put(f"✓ GitHub connected as {login}\n")
            except Exception as e:  # noqa: BLE001
                self.logq.put(f"GitHub login failed: {e}\n")
            self.root.after(0, lambda: (self.gh_btn.config(state="normal"), self.refresh_status()))

        threading.Thread(target=run, daemon=True).start()

    def _show_code(self, d):
        code = d["user_code"]
        uri = d.get("verification_uri", "https://github.com/login/device")
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(code)
        except Exception:  # noqa: BLE001
            pass
        webbrowser.open(uri)
        messagebox.showinfo("Authorize on GitHub",
                            f"Your browser opened {uri}\n\n"
                            f"Enter this code (already copied to your clipboard):\n\n        {code}\n\n"
                            f"Approve access, then come back here.")

    def github_logout(self):
        github_auth.clear_token(STATE_DIR)
        self.refresh_status()
        self.logq.put("GitHub disconnected.\n")

    # ---------------- Ollama (free local AI) ----------------
    def _refresh_ollama(self):
        def run():
            st, ms = ollama_setup.status()
            def ui():
                if st == "ready":
                    self.ollama_pill.config(text=f"ready ({ms[0]})", fg=OK_FG, bg=OK_BG)
                    self.ollama_btn.config(text="Re-pull model", state="normal")
                elif st == "running_no_model":
                    self.ollama_pill.config(text="no model yet", fg=NO_FG, bg=NO_BG)
                    self.ollama_btn.config(text="Download model", state="normal")
                elif st == "installed_not_running":
                    self.ollama_pill.config(text="installed, not running", fg=NO_FG, bg=NO_BG)
                    self.ollama_btn.config(text="Start & set up", state="normal")
                else:
                    self.ollama_pill.config(text="not installed", fg=LOCK_FG, bg=LOCK_BG)
                    self.ollama_btn.config(text="Set up free local AI", state="normal")
            self.root.after(0, ui)
        threading.Thread(target=run, daemon=True).start()

    def setup_ollama(self):
        self.ollama_btn.config(state="disabled", text="Setting up…")
        model = self.model_var.get().strip() if self.provider_var.get() == "ollama" else ""
        model = model or ollama_setup.DEFAULT_MODEL
        self.logq.put(f"Setting up free local AI (Ollama, model '{model}')…\n")

        def run():
            try:
                ollama_setup.setup(model, progress=lambda m: self.logq.put(m + "\n"))
                self.provider_var.set("ollama")
                self.model_var.set(model)
                self.save_settings()
                self.logq.put("✓ Local AI ready — Write-ups switched to Ollama (free, unlimited).\n")
            except Exception as e:  # noqa: BLE001
                self.logq.put(f"Ollama setup failed: {e}\n")
            self.root.after(0, self._refresh_ollama)

        threading.Thread(target=run, daemon=True).start()

    # ---------------- auto-update ----------------
    def _check_updates(self):
        def run():
            info = updater.check()
            if info:
                self.update_info = info
                self.root.after(0, lambda: self._show_update_bar(info))
        threading.Thread(target=run, daemon=True).start()

    def _show_update_bar(self, info):
        self.update_lbl.config(text=f"Update available — v{info['version']} is out (you have v{constants.VERSION})")
        self.update_bar.pack(fill="x", padx=16, pady=(0, 8), after=self.header)

    def do_update(self):
        info = self.update_info
        if not info:
            return
        if not messagebox.askyesno("Update GitKosh",
                                   f"Download and install v{info['version']}? "
                                   "GitKosh will relaunch. Your logins and settings are kept."):
            return
        self.update_lbl.config(text=f"Updating to v{info['version']}…")
        self.logq.put(f"Updating to v{info['version']}…\n")

        def run():
            try:
                ok = updater.download_and_apply(info["url"], log=lambda m: self.logq.put(m + "\n"))
                if ok:
                    self.root.after(800, lambda: os._exit(0))
                else:
                    self.root.after(0, lambda: self.update_lbl.config(text="Update couldn't be applied."))
            except Exception as e:  # noqa: BLE001
                self.logq.put(f"Update failed: {e}\n")
                self.root.after(0, lambda: self.update_lbl.config(text=f"Update failed: {e}"))
        threading.Thread(target=run, daemon=True).start()

    # ---------------- scheduler ----------------
    def _program_args(self):
        if getattr(sys, "frozen", None):
            return [_main_executable()]
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return [sys.executable, os.path.join(root_dir, "app_main.py")]

    def apply_schedule(self):
        self.save_settings()
        if not self.sched_var.get():
            scheduler.disable()
            self.logq.put("Daily auto-sync turned off.\n")
            self._refresh_schedule(); return
        try:
            h, m = (int(x) for x in self.time_var.get().strip().split(":"))
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError
        except Exception:  # noqa: BLE001
            messagebox.showerror("Time format", "Enter the time as HH:MM, e.g. 09:00")
            return
        scheduler.enable(self._program_args(), h, m, bool(self.streak_var.get()))
        self.logq.put(f"✓ Daily auto-sync scheduled at {h:02d}:{m:02d}"
                      + (" — will keep your streak alive." if self.streak_var.get() else ".") + "\n")
        self._refresh_schedule()

    def _refresh_schedule(self):
        en = scheduler.is_enabled()
        self.sched_var.set(en)
        sch = scheduler.read_schedule()
        if sch:
            h, m, ks = sch
            self.time_var.set(f"{h:02d}:{m:02d}")
            self.streak_var.set(ks)
        lr = read_last_run(STATE_DIR)
        parts = [f"⏰ Scheduled daily at {self.time_var.get()}" if en
                 else "Not scheduled — runs only when you click Sync."]
        if lr:
            when = lr.get("at", "")[:16].replace("T", " ")
            if lr.get("error"):
                parts.append(f"last run {when}: error")
            elif lr.get("pushed"):
                parts.append(f"last run {when}: +{lr['pushed']} pushed")
            elif lr.get("streak"):
                parts.append(f"last run {when}: streak kept")
            else:
                parts.append(f"last run {when}: nothing new")
        self.sched_status.config(text="   ·   ".join(parts))

    # ---------------- settings ----------------
    def save_settings(self):
        self.cfg["github"]["repo"] = self.repo_var.get().strip()
        self.cfg["github"]["private"] = bool(self.private_var.get())
        prov = self.provider_var.get()
        self.cfg["readme"]["mode"] = "minimal" if prov == "none" else "llm"
        self.cfg["readme"]["llm"] = {"provider": prov, "model": self.model_var.get().strip(),
                                     "api_key": self.key_var.get().strip()}
        save_config(self.cfg)
        self.logq.put("Settings saved.\n")

    # ---------------- sync ----------------
    def do_backfill(self):
        if self.worker and self.worker.is_alive():
            return
        self.save_settings()
        try:
            limit = int(self.limit_var.get() or "0")
        except ValueError:
            limit = 0
        self.sync_btn.config(state="disabled")
        self.worker = threading.Thread(target=self._run, args=(False, limit), daemon=True)
        self.worker.start()

    def do_reset(self):
        if self.worker and self.worker.is_alive():
            return
        if not messagebox.askyesno(
            "Reset & re-backfill",
            "This clears GitKosh's local sync history and rebuilds your repo from scratch — "
            "one commit per problem, backdated to the day you actually solved it, so your "
            "contribution graph reflects your real history.\n\n"
            "Your existing commit history in the repo will be REPLACED. Continue?"):
            return
        self.save_settings()
        self.sync_btn.config(state="disabled")
        self.worker = threading.Thread(target=self._run, args=(False, 0, True), daemon=True)
        self.worker.start()

    def toggle_watch(self):
        if self.worker and self.worker.is_alive() and not self.stop_evt.is_set():
            self.stop_evt.set()
            self.watch_btn.config(text="Auto-sync: stopping…")
            return
        self.save_settings()
        self.stop_evt.clear()
        self.watch_btn.config(text="Auto-sync: on")
        self.worker = threading.Thread(target=self._watch_loop, daemon=True)
        self.worker.start()

    def _watch_loop(self):
        interval = int(self.cfg.get("watch", {}).get("interval_minutes", 15)) * 60
        while not self.stop_evt.is_set():
            self._run(True, 0)
            for _ in range(interval):
                if self.stop_evt.is_set():
                    break
                time.sleep(1)
        self.root.after(0, lambda: self.watch_btn.config(text="Auto-sync: off"))

    def _run(self, stop_on_seen, limit, reset=False):
        with contextlib.redirect_stdout(QueueWriter(self.logq)):
            try:
                self._do_sync(stop_on_seen, limit, reset)
            except Exception as e:  # noqa: BLE001
                print(f"ERROR: {e}")
        self.root.after(0, self.refresh_status)

    # ---------- progress display (thread-safe via root.after) ----------
    def _prog_busy(self, text, sub=""):
        def ui():
            self.prog_label.config(text=text, fg=INK)
            self.prog_sub.config(text=sub)
            self.prog.config(mode="indeterminate", maximum=100)
            try:
                self.prog.start(14)
            except tk.TclError:
                pass
        self.root.after(0, ui)

    def _prog_subtext(self, sub):
        self.root.after(0, lambda: self.prog_sub.config(text=sub))

    def _prog_step(self, i, n, text, sub=""):
        def ui():
            try:
                self.prog.stop()
            except tk.TclError:
                pass
            self.prog.config(mode="determinate", maximum=max(n, 1), value=i)
            self.prog_label.config(text=text, fg=INK)
            self.prog_sub.config(text=sub)
        self.root.after(0, ui)

    def _prog_done(self, text, ok=True):
        def ui():
            try:
                self.prog.stop()
            except tk.TclError:
                pass
            self.prog.config(mode="determinate", maximum=100, value=100 if ok else 0)
            self.prog_label.config(text=text, fg=OK_FG if ok else NO_FG)
            self.prog_sub.config(text="")
        self.root.after(0, ui)

    def _progress_cb(self, stage, i=0, n=0, text="", sub="", ok=True):
        """Adapter so sync_core drives the progress bar (thread-safe via _prog_*)."""
        if stage == "busy":
            self._prog_busy(text, sub)
        elif stage == "step":
            self._prog_step(i, n, f"{text}…  {i} / {n}", sub)
        elif stage == "done":
            self._prog_done(text, ok)

    def _do_sync(self, stop_on_seen, limit, reset=False):
        res = run_sync(
            self.cfg, STATE_DIR,
            stop_on_seen=stop_on_seen, limit=limit, reset=reset,
            keep_streak=bool(self.streak_var.get()),
            log=print,                       # redirected to the Activity log by _run
            progress=self._progress_cb,
            should_stop=self.stop_evt.is_set,
        )
        if res.get("pushed"):
            self.root.after(0, lambda: self.summary.config(text=f"+{res['pushed']} pushed"))
        self.root.after(0, self._refresh_schedule)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
