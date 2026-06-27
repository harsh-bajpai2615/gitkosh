"""Push files to GitHub via the REST API using an OAuth token — no git/gh needed.

Accumulate files for a sync run, then commit them all at once with the Git Data API
(blobs -> tree -> commit -> ref update). Handles brand-new empty repos too.
"""
from __future__ import annotations

import base64
import re
from typing import Dict, Optional, Tuple

import requests

API = "https://api.github.com"


def slug_repo(name: str) -> str:
    """GitHub repo names allow only [A-Za-z0-9._-]; turn anything else into '-'."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-") or "solutions"


class GitHubAPI:
    def __init__(self, token: str, repo_slug: str, private: bool = True, branch: str = "main"):
        self.token = token
        self.repo_slug = repo_slug.strip()
        self.private = private
        self.branch = branch
        self._owner = None
        self._repo = None
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "codesync",
        })

    # ---------- identity / repo ----------
    def whoami(self) -> str:
        r = self.s.get(f"{API}/user", timeout=30)
        r.raise_for_status()
        return r.json()["login"]

    def _resolve(self) -> Tuple[str, str]:
        if self._owner:
            return self._owner, self._repo
        if "/" in self.repo_slug:
            owner, repo = self.repo_slug.split("/", 1)
            self._owner, self._repo = owner.strip(), slug_repo(repo)
        else:
            self._owner, self._repo = self.whoami(), slug_repo(self.repo_slug)
        return self._owner, self._repo

    def ensure_repo(self) -> str:
        owner, repo = self._resolve()
        r = self.s.get(f"{API}/repos/{owner}/{repo}", timeout=30)
        if r.status_code == 200:
            return f"{owner}/{repo}"
        if r.status_code != 404:
            r.raise_for_status()
        # Create under the authenticated user (org repos must pre-exist).
        login = self.whoami()
        if owner != login:
            raise RuntimeError(f"Repo {owner}/{repo} not found and can't auto-create under '{owner}'. "
                               f"Create it on GitHub first, or use '{login}/{repo}'.")
        cr = self.s.post(f"{API}/user/repos", json={
            "name": repo, "private": self.private, "auto_init": False,
            "description": "Competitive-programming solutions, synced by codesync.",
        }, timeout=30)
        cr.raise_for_status()
        return f"{owner}/{repo}"

    # ---------- commit ----------
    def _get_base(self, owner, repo) -> Tuple[Optional[str], Optional[str]]:
        """Return (base_commit_sha, base_tree_sha) or (None, None) for an empty repo."""
        r = self.s.get(f"{API}/repos/{owner}/{repo}/git/ref/heads/{self.branch}", timeout=30)
        if r.status_code in (404, 409):  # 404 = no such ref, 409 = empty repo (no commits yet)
            return None, None
        r.raise_for_status()
        commit_sha = r.json()["object"]["sha"]
        c = self.s.get(f"{API}/repos/{owner}/{repo}/git/commits/{commit_sha}", timeout=30)
        c.raise_for_status()
        return commit_sha, c.json()["tree"]["sha"]

    def _seed_initial(self, owner, repo) -> None:
        """Empty repos reject the Git Data API; create a first commit via Contents API."""
        body = {
            "message": "Initialize repository (CodeSync)",
            "content": base64.b64encode(
                "# Competitive Programming\n\nSolutions synced automatically by CodeSync.\n".encode()
            ).decode("ascii"),
            "branch": self.branch,
        }
        r = self.s.put(f"{API}/repos/{owner}/{repo}/contents/README.md", json=body, timeout=30)
        r.raise_for_status()

    def _blob(self, owner, repo, content: str) -> str:
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        r = self.s.post(f"{API}/repos/{owner}/{repo}/git/blobs",
                        json={"content": b64, "encoding": "base64"}, timeout=60)
        r.raise_for_status()
        return r.json()["sha"]

    def get_file_text(self, path: str) -> str:
        """Current text of a file on the default branch, or '' if absent."""
        owner, repo = self._resolve()
        r = self.s.get(f"{API}/repos/{owner}/{repo}/contents/{path}",
                       params={"ref": self.branch}, timeout=30)
        if r.status_code == 200 and r.json().get("content"):
            return base64.b64decode(r.json()["content"]).decode("utf-8", "replace")
        return ""

    def push(self, files: Dict[str, str], message: str) -> str:
        """Commit a {path: text} mapping in one commit. Returns the commit URL."""
        if not files:
            return ""
        owner, repo = self._resolve()
        base_commit, base_tree = self._get_base(owner, repo)
        if base_commit is None:  # brand-new empty repo — seed an initial commit first
            self._seed_initial(owner, repo)
            base_commit, base_tree = self._get_base(owner, repo)

        tree = [{"path": path, "mode": "100644", "type": "blob",
                 "sha": self._blob(owner, repo, content)} for path, content in files.items()]
        tree_body = {"tree": tree}
        if base_tree:
            tree_body["base_tree"] = base_tree
        tr = self.s.post(f"{API}/repos/{owner}/{repo}/git/trees", json=tree_body, timeout=60)
        tr.raise_for_status()
        tree_sha = tr.json()["sha"]

        commit_body = {"message": message, "tree": tree_sha}
        if base_commit:
            commit_body["parents"] = [base_commit]
        cm = self.s.post(f"{API}/repos/{owner}/{repo}/git/commits", json=commit_body, timeout=60)
        cm.raise_for_status()
        commit_sha = cm.json()["sha"]

        ref = f"refs/heads/{self.branch}"
        if base_commit:
            up = self.s.patch(f"{API}/repos/{owner}/{repo}/git/refs/heads/{self.branch}",
                              json={"sha": commit_sha, "force": False}, timeout=30)
        else:
            up = self.s.post(f"{API}/repos/{owner}/{repo}/git/refs",
                             json={"ref": ref, "sha": commit_sha}, timeout=30)
        up.raise_for_status()
        return cm.json().get("html_url", commit_sha)
