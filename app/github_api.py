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
            "User-Agent": "gitkosh",
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
            "description": "Competitive-programming solutions, synced by GitKosh.",
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
            "message": "Initialize repository (GitKosh)",
            "content": base64.b64encode(
                "# Competitive Programming\n\nSolutions synced automatically by GitKosh.\n".encode()
            ).decode("ascii"),
            "branch": self.branch,
        }
        r = self.s.put(f"{API}/repos/{owner}/{repo}/contents/README.md", json=body, timeout=30)
        r.raise_for_status()

    def _blob(self, owner, repo, content) -> str:
        raw = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8")
        b64 = base64.b64encode(raw).decode("ascii")
        r = self.s.post(f"{API}/repos/{owner}/{repo}/git/blobs",
                        json={"content": b64, "encoding": "base64"}, timeout=60)
        r.raise_for_status()
        return r.json()["sha"]

    def enable_pages(self, path: str = "/docs") -> str:
        """Enable GitHub Pages (branch=main, given path) and return the site URL.
        Idempotent — returns the URL whether it was just created or already on."""
        owner, repo = self._resolve()
        self.s.post(f"{API}/repos/{owner}/{repo}/pages",
                    json={"source": {"branch": self.branch, "path": path}}, timeout=30)
        g = self.s.get(f"{API}/repos/{owner}/{repo}/pages", timeout=30)
        if g.status_code == 200:
            return g.json().get("html_url") or f"https://{owner}.github.io/{repo}/"
        raise RuntimeError("couldn't enable GitHub Pages (token may lack permission). "
                           "Enable it once under repo Settings → Pages → Branch: main /docs.")

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

    def _author(self) -> dict:
        """Author identity for backdated commits. Uses the account's noreply email so
        backdated commits still count toward the contribution graph."""
        if getattr(self, "_author_cache", None):
            return self._author_cache
        d = self.s.get(f"{API}/user", timeout=30).json()
        login, uid = d.get("login", "user"), d.get("id", "")
        email = d.get("email") or f"{uid}+{login}@users.noreply.github.com"
        self._author_cache = {"name": d.get("name") or login, "email": email}
        return self._author_cache

    def push_commits(self, commits: list, orphan: bool = False, force: bool = False) -> str:
        """Create a chain of commits, one per entry, each backdated to its own date.

        commits: [{"files": {path: text}, "message": str, "date": iso8601 | None}]
        Each commit builds on the previous; the branch moves once at the end — so a big
        backfill becomes many commits dated to the real solve days (fills the contribution
        graph historically). With orphan=True the chain starts from no parent (fresh
        history); force=True replaces the branch (used by reset & re-backfill).
        Returns the last commit's URL.
        """
        commits = [c for c in commits if c.get("files")]
        if not commits:
            return ""
        owner, repo = self._resolve()
        if orphan:
            parent, tree_base = None, None
        else:
            base_commit, base_tree = self._get_base(owner, repo)
            if base_commit is None:
                self._seed_initial(owner, repo)
                base_commit, base_tree = self._get_base(owner, repo)
            parent, tree_base = base_commit, base_tree
        author = self._author()
        last_url = ""
        for c in commits:
            tree = [{"path": p, "mode": "100644", "type": "blob",
                     "sha": self._blob(owner, repo, txt)} for p, txt in c["files"].items()]
            body = {"tree": tree}
            if tree_base:
                body["base_tree"] = tree_base
            tr = self.s.post(f"{API}/repos/{owner}/{repo}/git/trees", json=body, timeout=60)
            tr.raise_for_status()
            tree_sha = tr.json()["sha"]
            cbody = {"message": c["message"], "tree": tree_sha,
                     "parents": [parent] if parent else []}
            if c.get("date"):
                who = {"name": author["name"], "email": author["email"], "date": c["date"]}
                cbody["author"], cbody["committer"] = who, who
            cm = self.s.post(f"{API}/repos/{owner}/{repo}/git/commits", json=cbody, timeout=60)
            cm.raise_for_status()
            j = cm.json()
            parent, tree_base, last_url = j["sha"], tree_sha, j.get("html_url", j["sha"])
        up = self.s.patch(f"{API}/repos/{owner}/{repo}/git/refs/heads/{self.branch}",
                          json={"sha": parent, "force": bool(force or orphan)}, timeout=30)
        if up.status_code == 422:  # ref doesn't exist yet — create it
            self.s.post(f"{API}/repos/{owner}/{repo}/git/refs",
                        json={"ref": f"refs/heads/{self.branch}", "sha": parent}, timeout=30).raise_for_status()
        else:
            up.raise_for_status()
        return last_url
