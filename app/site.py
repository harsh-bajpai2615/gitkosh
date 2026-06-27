"""Generate a self-contained portfolio website (docs/index.html) for GitHub Pages.

One HTML file, inline CSS + a little vanilla JS (search + topic filter). Pulls from
the solved-problem store; links resolve to absolute GitHub URLs so it works at the
Pages URL regardless of relative paths. Themed to match the GitKosh stats card.
"""
from __future__ import annotations

import html
from collections import Counter

from .dashboard import _d, _streaks, LABELS

DIFF_COLOR = {"Easy": "#2cbb5d", "Medium": "#e3a008", "Hard": "#e5484d"}


def _esc(s) -> str:
    return html.escape(str(s or ""))


def badges_md(items: list, owner: str, repo: str, pages_url: str = "") -> str:
    """A copy-paste snippet for the user's GitHub *profile* README."""
    total = len(items)
    plat = Counter(i.get("platform", "?") for i in items)
    days = [x for x in (_d(i.get("timestamp")) for i in items) if x]
    cur, _ = _streaks(days)
    card = f"https://raw.githubusercontent.com/{owner}/{repo}/main/profile/stats.png"
    repo_url = f"https://github.com/{owner}/{repo}"
    lines = [
        f"[![Competitive Programming]({card})]({pages_url or repo_url})",
        "",
        f"![Solved](https://img.shields.io/badge/Solved-{total}-5B5BD6) "
        f"![Streak](https://img.shields.io/badge/Streak-{cur}d-E3A008) "
        f"![Platforms](https://img.shields.io/badge/Platforms-{len(plat)}-16A34A)",
    ]
    if pages_url:
        lines += ["", f"🔗 **[My portfolio site]({pages_url})**"]
    return "\n".join(lines) + "\n"


def render(items: list, owner: str = "", repo: str = "") -> str:
    base = f"https://github.com/{owner}/{repo}/tree/main" if owner and repo else ""
    card = f"https://raw.githubusercontent.com/{owner}/{repo}/main/profile/stats.png" if owner and repo else ""

    total = len(items)
    plat = Counter(i.get("platform", "?") for i in items)
    langs = Counter((i.get("lang") or "").strip() for i in items if (i.get("lang") or "").strip())
    diff = Counter(i.get("difficulty") for i in items if i.get("difficulty") in DIFF_COLOR)
    tags = Counter(t for i in items for t in (i.get("tags") or []))
    days = [x for x in (_d(i.get("timestamp")) for i in items) if x]
    cur, longest = _streaks(days)
    last = max(days) if days else None

    tiles = [("Solved", total), ("Current streak", f"{cur}d"), ("Longest", f"{longest}d"),
             ("Active days", len(set(days))), ("Languages", len(langs)), ("Platforms", len(plat))]
    tiles_html = "".join(
        f'<div class="tile"><div class="tv">{_esc(v)}</div><div class="tl">{_esc(l)}</div></div>'
        for l, v in tiles)

    dtot = sum(diff.values()) or 1
    diff_html = "".join(
        f'<div class="drow"><span style="color:{c}">{lvl}</span>'
        f'<div class="dbar"><i style="width:{int(100*diff.get(lvl,0)/dtot)}%;background:{c}"></i></div>'
        f'<span class="dn">{diff.get(lvl,0)}</span></div>'
        for lvl, c in DIFF_COLOR.items())

    chips_html = "".join(
        f'<button class="chip" data-topic="{_esc(t)}">{_esc(t)} <b>{n}</b></button>'
        for t, n in tags.most_common(24))

    rows = sorted(items, key=lambda i: i.get("timestamp", 0), reverse=True)
    rows_html = []
    for i in rows:
        d = i.get("dir")
        title = _esc(i.get("title", "—"))
        link = f"{base}/{d}" if (base and d) else (i.get("url") or "#")
        dt = _d(i.get("timestamp"))
        topics = " ".join(i.get("tags") or [])
        dc = DIFF_COLOR.get(i.get("difficulty"), "#8a90a6")
        rows_html.append(
            f'<tr data-text="{title.lower()} {_esc(i.get("platform"))}" data-topics="{_esc(topics).lower()}">'
            f'<td><a href="{_esc(link)}" target="_blank" rel="noopener">{title}</a></td>'
            f'<td>{_esc(LABELS.get(i.get("platform"), i.get("platform")))}</td>'
            f'<td style="color:{dc};font-weight:600">{_esc(i.get("difficulty") or "—")}</td>'
            f'<td>{_esc(i.get("lang") or "—")}</td>'
            f'<td class="muted">{dt.isoformat() if dt else "—"}</td></tr>')

    card_img = (f'<img class="card-img" src="{card}" alt="stats" '
                'onerror="this.style.display=\'none\'">') if card else ""

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(owner or "My")} — Competitive Programming</title>
<style>
  :root{{--bg:#0f1117;--card:#171a24;--bd:#262b3b;--ink:#f0f2f8;--mut:#8a90a6;--acc:#7b7af6}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
  .wrap{{max-width:960px;margin:0 auto;padding:40px 20px 80px}}
  header{{display:flex;align-items:center;gap:16px;margin-bottom:28px}}
  .logo{{width:54px;height:54px;border-radius:14px;background:var(--acc);display:grid;
    place-items:center;font-weight:800;font-size:22px;color:#fff}}
  h1{{margin:0;font-size:26px}} .sub{{color:var(--mut);font-size:14px}}
  .card-img{{width:100%;border-radius:18px;border:1px solid var(--bd);margin:8px 0 26px;display:block}}
  .tiles{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:26px}}
  @media(max-width:680px){{.tiles{{grid-template-columns:repeat(3,1fr)}}}}
  .tile{{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px}}
  .tv{{font-size:24px;font-weight:800}} .tl{{color:var(--mut);font-size:12px;margin-top:2px}}
  h2{{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:26px 0 12px}}
  .drow{{display:flex;align-items:center;gap:12px;margin:8px 0;font-weight:600;font-size:13px}}
  .dbar{{flex:1;height:8px;background:#2e3344;border-radius:5px;overflow:hidden}}
  .dbar i{{display:block;height:100%}} .dn{{color:var(--mut);width:28px;text-align:right}}
  .chips{{display:flex;flex-wrap:wrap;gap:8px}}
  .chip{{background:var(--card);border:1px solid var(--bd);color:#b9c0d4;border-radius:16px;
    padding:6px 12px;font-size:13px;cursor:pointer}} .chip b{{color:var(--acc)}}
  .chip.active{{border-color:var(--acc);color:#fff}}
  input{{width:100%;padding:11px 14px;margin:14px 0;background:var(--card);border:1px solid var(--bd);
    border-radius:12px;color:var(--ink);font-size:14px}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid var(--bd)}}
  th{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
  a{{color:#aab2ff;text-decoration:none}} a:hover{{text-decoration:underline}} .muted{{color:var(--mut)}}
  footer{{margin-top:40px;color:var(--mut);font-size:13px;text-align:center}}
  footer a{{color:var(--acc)}}
</style></head>
<body><div class="wrap">
  <header>
    <div class="logo">GK</div>
    <div><h1>{_esc(owner or "My profile")}</h1>
    <div class="sub">Competitive Programming · last solved {last.isoformat() if last else "—"}</div></div>
  </header>
  {card_img}
  <div class="tiles">{tiles_html}</div>
  <h2>Difficulty</h2>{diff_html}
  <h2>Topics</h2><div class="chips"><button class="chip active" data-topic="">All</button>{chips_html}</div>
  <input id="q" placeholder="Search {total} problems…">
  <table><thead><tr><th>Problem</th><th>Platform</th><th>Difficulty</th><th>Lang</th><th>Solved</th></tr></thead>
  <tbody id="tb">{''.join(rows_html)}</tbody></table>
  <footer>Auto-generated &amp; updated by <a href="https://github.com/harsh-bajpai2615/gitkosh" target="_blank">GitKosh</a>.</footer>
</div>
<script>
  const q=document.getElementById('q'),rows=[...document.querySelectorAll('#tb tr')];
  let topic='';
  function apply(){{const s=q.value.toLowerCase();rows.forEach(r=>{{
    const okT=!topic||r.dataset.topics.includes(topic.toLowerCase());
    const okS=!s||r.dataset.text.includes(s);r.style.display=okT&&okS?'':'none';}});}}
  q.addEventListener('input',apply);
  document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{{
    document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));
    c.classList.add('active');topic=c.dataset.topic;apply();}}));
</script></body></html>
"""
