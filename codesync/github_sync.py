"""Writes solutions into a local git repo and pushes to GitHub.

Uses the `git` and `gh` CLIs (both already on the system). Creates the repo with
`gh repo create` if it doesn't exist and create_if_missing is set.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .platforms.base import Submission


def _run(args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


class GitHubSync:
    def __init__(self, repo_path: Path, github_cfg: dict):
        self.repo = Path(repo_path)
        self.cfg = github_cfg or {}

    # ---------- repo setup ----------
    def ensure_repo(self) -> None:
        self.repo.mkdir(parents=True, exist_ok=True)
        if not (self.repo / ".git").exists():
            _run(["git", "init"], cwd=self.repo)
            _run(["git", "branch", "-M", "main"], cwd=self.repo)
        remote = self.cfg.get("repo", "")
        if not remote:
            return
        existing = _run(["git", "remote"], cwd=self.repo).stdout.split()
        if "origin" not in existing:
            self._ensure_github_remote(remote)

    def _ensure_github_remote(self, repo_slug: str) -> None:
        # Does the GitHub repo exist?
        exists = _run(["gh", "repo", "view", repo_slug], check=False).returncode == 0
        if not exists and self.cfg.get("create_if_missing"):
            vis = "--private" if self.cfg.get("visibility", "private") == "private" else "--public"
            print(f"Creating GitHub repo {repo_slug} ({vis})...")
            _run(["gh", "repo", "create", repo_slug, vis], check=False)
        url = f"https://github.com/{repo_slug}.git"
        _run(["git", "remote", "add", "origin", url], cwd=self.repo, check=False)

    # ---------- writing ----------
    def write_submission(self, sub: "Submission", readme: str) -> Path:
        d = self.repo / sub.platform / sub.dirname
        d.mkdir(parents=True, exist_ok=True)
        (d / f"solution.{sub.ext}").write_text(sub.code)
        (d / "README.md").write_text(readme)
        return d

    # ---------- git ----------
    def commit(self, message: str) -> bool:
        _run(["git", "add", "-A"], cwd=self.repo)
        status = _run(["git", "status", "--porcelain"], cwd=self.repo).stdout.strip()
        if not status:
            return False
        # Use a configured identity only if the repo has none, to avoid global prompts.
        if _run(["git", "config", "user.email"], cwd=self.repo, check=False).returncode != 0:
            _run(["git", "config", "user.email", "codesync@local"], cwd=self.repo)
            _run(["git", "config", "user.name", "codesync"], cwd=self.repo)
        _run(["git", "commit", "-m", message], cwd=self.repo)
        return True

    def push(self) -> None:
        if not self.cfg.get("push", True):
            return
        # -u sets upstream on first push; ignore failure so a missing remote doesn't crash.
        res = _run(["git", "push", "-u", "origin", "main"], cwd=self.repo, check=False)
        if res.returncode != 0:
            print(f"  ! push failed: {res.stderr.strip()}")
