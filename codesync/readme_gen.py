"""Per-problem README generation.

Full-LLM mode: the model writes the whole write-up (summary, approach, complexity,
insights), grounded on the scraped statement/tags so it doesn't hallucinate. The
LLM provider is pluggable — Gemini, Groq, or a local Ollama model via their HTTP APIs.
"""
from __future__ import annotations

import os
import textwrap
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .platforms.base import Submission

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",  # 2.0-flash has no free-tier quota; 2.5-flash does
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1",
}


def _prompt(sub: "Submission") -> str:
    statement = sub.statement[:6000] if sub.statement else "(statement not captured — infer from the code and title)"
    return textwrap.dedent(f"""\
        You are documenting a competitive-programming solution for a GitHub repo.
        Write a README.md in GitHub-flavored Markdown for ONE problem.

        Platform: {sub.platform}
        Problem: {sub.title}
        Difficulty/Rating: {sub.difficulty or "unknown"}
        Tags: {", ".join(sub.tags) or "none"}
        Link: {sub.url}
        Language: {sub.lang}

        Official statement (may be truncated):
        ---
        {statement}
        ---

        My accepted solution:
        ```{sub.ext}
        {sub.code[:8000]}
        ```

        FORMAT RULES (strict):
        - Use ONLY Markdown headings and bullet/numbered lists. NO plain paragraphs anywhere.
        - Every piece of information must be a bullet (-) or a numbered step.
        - The Algorithm must be NUMBERED steps describing what MY code above actually does,
          in order — concrete and specific to my solution, not a generic textbook method.
        - Be accurate; do not invent constraints. Do not paste the source code.

        Produce EXACTLY this structure:

        # {sub.title}

        ## Problem
        - (3-6 bullets: what's given, what's asked, key constraints)

        ## Algorithm
        1. (first concrete step my code takes)
        2. (next step)
        3. (... 5-12 numbered steps total, following my code's actual logic)

        ## Complexity
        - **Time:** O(...) — bullet reason
        - **Space:** O(...) — bullet reason

        ## Key Insight
        - (1-3 bullets: the trick/observation that makes the solution work)

        ## Tags
        - {", ".join(sub.tags) if sub.tags else "(none)"}
        """)


# ---------- providers ----------
def _gen_gemini(prompt: str, model: str, api_key: str, base_url: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(3):
        r = requests.post(
            url, params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=120,
        )
        if r.status_code == 429 and attempt < 2:  # rate limited — back off and retry
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        cand = r.json()["candidates"][0]
        return "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
    r.raise_for_status()  # exhausted retries
    return ""


def _gen_openai_compatible(prompt: str, model: str, api_key: str, base_url: str) -> str:
    """Works for Groq and local Ollama (both expose the OpenAI chat-completions shape)."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(3):
        r = requests.post(f"{base_url.rstrip('/')}/chat/completions",
                          headers=headers, json=payload, timeout=180)
        if r.status_code == 429 and attempt < 2:
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    r.raise_for_status()
    return ""


_PROVIDERS = {
    "gemini": _gen_gemini,
    "groq": _gen_openai_compatible,
    "ollama": _gen_openai_compatible,
}

_DEFAULT_BASE = {
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
}


def _minimal(sub: "Submission") -> str:
    parts = [f"# {sub.title}", "", f"- **Platform:** {sub.platform}", f"- **Link:** {sub.url}"]
    if sub.difficulty:
        parts.append(f"- **Difficulty/Rating:** {sub.difficulty}")
    if sub.tags:
        parts.append(f"- **Tags:** {', '.join(sub.tags)}")
    if sub.runtime or sub.memory:
        parts.append(f"- **Result:** {sub.runtime} {sub.memory}".strip())
    if sub.statement:
        parts += ["", "## Problem", "", sub.statement]
    parts += ["", f"See `solution.{sub.ext}` for my accepted solution."]
    return "\n".join(parts) + "\n"


class ReadmeGenerator:
    def __init__(self, readme_cfg: dict):
        self.mode = (readme_cfg or {}).get("mode", "minimal")
        llm = (readme_cfg or {}).get("llm", {}) or {}
        self.provider = llm.get("provider", "gemini")
        self.model = llm.get("model") or DEFAULT_MODELS.get(self.provider, "")
        # Key precedence: explicit api_key in config (the app stores it here) > env var.
        self.api_key = llm.get("api_key") or (
            os.environ.get(llm.get("api_key_env", ""), "") if llm.get("api_key_env") else ""
        )
        self.base_url = llm.get("base_url") or _DEFAULT_BASE.get(self.provider, "")

    def self_test(self):
        """Quick check that the configured LLM works. Returns (ok, error_message)."""
        if self.mode != "llm":
            return True, ""
        fn = _PROVIDERS.get(self.provider)
        if not fn:
            return False, f"unknown provider '{self.provider}'"
        try:
            fn("Reply with the single word: ok", self.model, self.api_key, self.base_url)
            return True, ""
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "401" in msg or "API_KEY_INVALID" in msg or "UNAUTHENTICATED" in msg:
                msg = "invalid API key (Gemini keys start with 'AIza' — get one at aistudio.google.com/apikey)"
            return False, msg

    def generate(self, sub: "Submission") -> str:
        if self.mode != "llm":
            return _minimal(sub)
        fn = _PROVIDERS.get(self.provider)
        if not fn:
            print(f"  ! unknown LLM provider '{self.provider}', writing minimal README")
            return _minimal(sub)
        try:
            body = fn(_prompt(sub), self.model, self.api_key, self.base_url)
            if body:
                return body.rstrip() + "\n"
        except Exception as e:  # noqa: BLE001
            print(f"  ! LLM README failed for {sub.slug} ({self.provider}): {e}; falling back to minimal")
        return _minimal(sub)
