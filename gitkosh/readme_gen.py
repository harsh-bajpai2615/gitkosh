"""Per-problem README generation.

Full-LLM mode: the model writes the whole write-up (summary, approach, complexity,
insights), grounded on the scraped statement/tags so it doesn't hallucinate. The
LLM provider is pluggable — Gemini, Groq, or a local Ollama model via their HTTP APIs.
"""
from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .platforms.base import Submission

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",  # 2.0-flash has no free-tier quota; 2.5-flash does
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.2",  # matches app/ollama_setup.py's auto-pulled model
}


def _prompt(sub: "Submission") -> str:
    statement = sub.statement[:6000] if sub.statement else "(statement not captured — infer from the code and title)"
    # NOTE: this f-string is intentionally flush-left (no source indentation).
    # textwrap.dedent() over an *interpolated* string is unsafe — the embedded
    # source code carries its own indentation and skews the common-whitespace
    # calculation, corrupting both the code block and the surrounding Markdown.
    tags = ", ".join(sub.tags) if sub.tags else "(none)"
    return f"""\
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

## Optimization
- (Honestly assess MY solution: is it optimal in time & space for this problem?)
- (If it is optimal, say so in one bullet.)
- (If it can be improved, give the better approach + its complexity in 1-3 bullets.)

## Tags
- {tags}

After the Tags section, on the VERY LAST line, output exactly one HTML comment verdict:
`<!-- gitkosh:optimal=yes -->` if my solution is already optimal, otherwise
`<!-- gitkosh:optimal=no -->`. Output nothing after that comment.
"""


def parse_optimal(readme: str):
    """Extract the AI coach's verdict from a generated README. True/False/None."""
    import re
    m = re.search(r"gitkosh:optimal\s*=\s*(yes|no)", readme or "", re.I)
    if not m:
        return None
    return m.group(1).lower() == "yes"


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


# ---------- streaming providers ----------
# Each yields incremental text via on_chunk(delta) and returns the full text, so
# the UI can render an answer token-by-token instead of after a long wait.
def _stream_openai_compatible(prompt, model, api_key, base_url, on_chunk):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}
    full = []
    with requests.post(f"{base_url.rstrip('/')}/chat/completions",
                       headers=headers, json=payload, timeout=180, stream=True) as r:
        r.raise_for_status()
        r.encoding = "utf-8"  # SSE has no charset; requests would default to latin-1 → mojibake
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                break
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            delta = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                full.append(delta)
                on_chunk(delta)
    return "".join(full)


def _stream_gemini(prompt, model, api_key, base_url, on_chunk):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
    full = []
    with requests.post(url, params={"key": api_key, "alt": "sse"},
                       json={"contents": [{"parts": [{"text": prompt}]}]},
                       timeout=180, stream=True) as r:
        r.raise_for_status()
        r.encoding = "utf-8"  # SSE has no charset; avoid latin-1 mojibake on multibyte text
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            for cand in obj.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    t = part.get("text")
                    if t:
                        full.append(t)
                        on_chunk(t)
    return "".join(full)


_STREAM_PROVIDERS = {
    "gemini": _stream_gemini,
    "groq": _stream_openai_compatible,
    "ollama": _stream_openai_compatible,
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
        self.footer = (readme_cfg or {}).get("footer", True)

    @staticmethod
    def _footer(sub: "Submission") -> str:
        link = f"[{sub.platform} problem]({sub.url})" if sub.url else sub.platform
        return ("\n\n---\n<sub>" + link +
                " · synced & documented by "
                "[GitKosh](https://github.com/harsh-bajpai2615/gitkosh)</sub>\n")

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

    def freeform(self, prompt: str) -> str:
        """Run an arbitrary prompt through the configured provider (for social posts).
        Returns '' if no working LLM is configured."""
        if self.mode != "llm":
            return ""
        fn = _PROVIDERS.get(self.provider)
        if not fn:
            return ""
        try:
            return (fn(prompt, self.model, self.api_key, self.base_url) or "").strip()
        except Exception as e:  # noqa: BLE001
            print(f"  ! freeform LLM failed ({self.provider}): {e}")
            return ""

    def freeform_stream(self, prompt: str, on_chunk) -> str:
        """Like freeform(), but streams the answer via on_chunk(delta) as it arrives.
        Falls back to a single-shot call (emitting the whole result once) if the
        provider can't stream or the stream errors. Returns the full text."""
        if self.mode != "llm":
            return ""
        fn = _STREAM_PROVIDERS.get(self.provider)
        if fn:
            try:
                return (fn(prompt, self.model, self.api_key, self.base_url, on_chunk) or "").strip()
            except Exception as e:  # noqa: BLE001
                print(f"  ! streaming failed ({self.provider}): {e}; falling back")
        out = self.freeform(prompt)
        if out:
            on_chunk(out)
        return out

    def generate(self, sub: "Submission") -> str:
        out = None
        if self.mode == "llm":
            fn = _PROVIDERS.get(self.provider)
            if not fn:
                print(f"  ! unknown LLM provider '{self.provider}', writing minimal README")
            else:
                try:
                    body = fn(_prompt(sub), self.model, self.api_key, self.base_url)
                    if body:
                        out = body.rstrip() + "\n"
                except Exception as e:  # noqa: BLE001
                    print(f"  ! LLM README failed for {sub.slug} ({self.provider}): {e}; falling back to minimal")
        if out is None:
            out = _minimal(sub)
        if self.footer:
            out = out.rstrip() + self._footer(sub)
        return out
