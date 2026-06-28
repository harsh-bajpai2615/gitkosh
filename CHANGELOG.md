# Changelog

All notable changes to GitKosh. This project follows [semantic versioning](https://semver.org).
`release.sh` reads the top-most version's section here for the GitHub Release notes.

## 1.1.0

**Practice & learning**
- **Multi-language IDE** — run C++, Java and JavaScript in the in-app editor, not just Python (uses local toolchains with clear "install X" hints).
- **Streaming AI** — the tutor and AI review now stream token-by-token.
- **Mock interview mode** — a timed problem with an AI interviewer that probes your reasoning, then a structured scorecard.
- **Pattern → problem drilldowns** — jump from the pattern library straight into matching in-app problems.
- **Launch review nudge** — a banner on startup when spaced-repetition reviews are due.

**Company interview prep**
- **Company prep tab** — the most-asked LeetCode questions for 657 companies (FAANG + placement favourites featured), matched against your synced solves.
- **Rich filtering** — difficulty, unsolved-only, in-app-only, saved-only, **topic/pattern**, title search and sorting, with per-difficulty progress.
- **Saved list & bookmarks** across companies.
- **Multi-company target sheet** — one merged, de-duplicated sheet across your shortlist, ranked by overlap.
- **Auto study plan** — a dated N-week schedule with balanced difficulty, an optional **weak-topic emphasis**, a Plan tab, and daily reminders.
- **Per-topic strength** in Insights.

**Archiving**
- **Backfill from my machine** — import a local folder's real past work onto your contribution graph using honest file/git dates.
- **Polished portfolio site** — gradient hero plus difficulty/language/platform/topic breakdowns.

**Fixes**
- Corrected README generation (a `dedent` bug had been corrupting every AI write-up), reset/re-backfill duplicate commits, the in-app updater's version compare and self-replace, handle detection, two-sum grading, the browser extension's default-branch/retry handling, plus encoding, race-condition and webui robustness issues.

## 1.0.0

- Initial release: sync accepted solutions from LeetCode, Codeforces, CodeChef, NeetCode, AtCoder & GeeksforGeeks to GitHub with AI write-ups; in-app NeetCode 150 + Blind 75 editor with progressive AI review; spaced-repetition Quiz Me; Insights, Contests, Showcase; daily auto-sync, streak keeper and in-app auto-update.
