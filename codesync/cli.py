"""codesync command-line interface.

  codesync login [--platforms a,b]    # log into sites once in a browser
  codesync backfill [--platforms ...] # bulk-pull all past accepted solutions
  codesync watch [--platforms ...]    # poll for new accepted solves and push
"""
from __future__ import annotations

import argparse
import time

from .auth import Session
from .config import Config
from .github_sync import GitHubSync
from .readme_gen import ReadmeGenerator
from .store import Store
from .platforms import REGISTRY


def _select(config: Config, arg) -> list:
    enabled = config.enabled_platforms()
    if arg:
        want = [p.strip() for p in arg.split(",")]
        return [p for p in want if p in REGISTRY and (p in enabled or True)]
    return [p for p in enabled if p in REGISTRY]


def _make_platforms(names, session, config):
    out = []
    for name in names:
        cls = REGISTRY[name]
        out.append(cls(session, config.platforms.get(name, {}), config))
    return out


def cmd_login(args, config: Config):
    session = Session(config.profile_dir, config.state_dir)
    platforms = _select(config, args.platforms) or list(REGISTRY)
    session.login(platforms)


def _process(subs_iter, platform_name, store, gh, readme_gen, stop_on_seen: bool, limit=None):
    """Shared loop for backfill/watch. Returns count of newly pushed problems."""
    count = 0
    for sub in subs_iter:
        if not sub.code.strip():
            continue
        if store.seen(sub.key):
            if stop_on_seen:
                break          # watch mode: newest-first, so we've caught up
            continue           # backfill: just skip
        readme = readme_gen.generate(sub)
        gh.write_submission(sub, readme)
        gh.commit(f"{platform_name}: {sub.title} ({sub.lang})")
        store.mark(sub.key, {"platform": sub.platform, "timestamp": sub.timestamp, "title": sub.title})
        count += 1
        print(f"  + {sub.platform}/{sub.dirname}")
        if limit and count >= limit:
            break
    return count


def _run_once(config, args, stop_on_seen):
    session = Session(config.profile_dir, config.state_dir)
    if not session.has_state():
        print("No saved session. Run `codesync login` first.")
        return 0
    store = Store(config.state_dir)
    gh = GitHubSync(config.output_repo, config.github)
    gh.ensure_repo()
    readme_gen = ReadmeGenerator(config.readme)
    names = _select(config, args.platforms)
    limit = getattr(args, "limit", 0) or None
    total = 0
    for plat in _make_platforms(names, session, config):
        print(f"[{plat.name}]")
        try:
            it = plat.recent() if stop_on_seen else plat.backfill()
            total += _process(it, plat.name, store, gh, readme_gen, stop_on_seen, limit=limit)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {plat.name} error: {e}")
    if total:
        gh.push()
    session.close()
    print(f"Done. {total} new problem(s). State: {store.count()} tracked.")
    return total


def cmd_backfill(args, config: Config):
    _run_once(config, args, stop_on_seen=False)


def cmd_watch(args, config: Config):
    interval = int(config.watch.get("interval_minutes", 15)) * 60
    print(f"Watching every {interval // 60} min. Ctrl-C to stop.")
    while True:
        try:
            _run_once(config, args, stop_on_seen=True)
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        time.sleep(interval)


def main(argv=None):
    p = argparse.ArgumentParser(prog="codesync", description="Sync competitive-programming solutions to GitHub.")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn in (("login", cmd_login), ("backfill", cmd_backfill), ("watch", cmd_watch)):
        sp = sub.add_parser(name)
        sp.add_argument("--platforms", default="", help="comma list, e.g. leetcode,codeforces")
        if name == "backfill":
            sp.add_argument("--limit", type=int, default=0, help="max problems to pull (0 = all)")
        sp.set_defaults(func=fn)

    args = p.parse_args(argv)
    config = Config.load(args.config)
    args.func(args, config)


if __name__ == "__main__":
    main()
