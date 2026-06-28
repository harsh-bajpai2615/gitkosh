"use strict";
const api = () => (window.pywebview && window.pywebview.api) || null;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Sample data so the UI previews fully in a plain browser (no Python bridge).
const SAMPLE = {
  version: "v1.0.0",
  github: "harsh-bajpai2615",
  sites: { leetcode: true, codeforces: false, codechef: false, neetcode: false, atcoder: false, geeksforgeeks: false },
  provider: "ollama",
  card: "sample-card.png",
  insights: {
    tiles: [["This week", 0], ["This month", 0], ["Streak", "0d"], ["Longest", "4d"], ["Optimal", "—"], ["Total", 38]],
    difficulty: { Easy: 8, Medium: 21, Hard: 9 },
    topics: ["Array", "Hash Table", "Math", "Greedy", "Prefix Sum", "String", "Sorting", "Two Pointers"],
    topic_strength: {
      count: 8,
      topics: [
        { topic: "Array", solved: 18, easy: 7, med: 9, hard: 2, total: 2188, coverage: 1, strength: 100 },
        { topic: "Hash Table", solved: 9, easy: 4, med: 5, hard: 0, total: 822, coverage: 1, strength: 62 },
        { topic: "Dynamic Programming", solved: 4, easy: 0, med: 2, hard: 2, total: 661, coverage: 1, strength: 48 },
        { topic: "Two Pointers", solved: 5, easy: 2, med: 3, hard: 0, total: 253, coverage: 2, strength: 40 },
      ],
      underexplored: [{ topic: "Graph", total: 200, solved: 1 }, { topic: "Backtracking", total: 110, solved: 0 }],
    },
    resume: [
      "Solved 38+ data-structures & algorithms problems across 6 platforms.",
      "9 hard and 21 medium problems; strongest in Array, Hash Table, Math.",
      "Maintained consistent practice — 13 active days, longest streak 4 days.",
    ],
    quiz: [{ title: "Maximum Path Score in a Grid", platform: "LeetCode", difficulty: "Hard",
             approach: "1. DP over grid cells.\n2. Track best incoming path.\n3. Answer at bottom-right." }],
  },
  contests: {
    handle: "",
    upcoming: [
      { platform: "leetcode", name: "Weekly Contest 508", when: "Sun 28 Jun · 08:00", dur: "1.5h", url: "#" },
      { platform: "codeforces", name: "Codeforces Round 1106 (Div. 2)", when: "Sun 28 Jun · 20:05", dur: "2.0h", url: "#" },
      { platform: "codeforces", name: "Educational Codeforces Round 192", when: "Mon 06 Jul · 20:05", dur: "2.0h", url: "#" },
      { platform: "leetcode", name: "Biweekly Contest 186", when: "Sat 04 Jul · 20:00", dur: "1.5h", url: "#" },
    ],
    rating: [1200, 1280, 1350, 1320, 1410, 1480, 1530, 1505, 1590, 1640, 1710, 1690],
  },
};
const LABELS = { leetcode: "LeetCode", codeforces: "Codeforces", codechef: "CodeChef",
  neetcode: "NeetCode", atcoder: "AtCoder", geeksforgeeks: "GeeksforGeeks" };

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 2600);
}

/* ---------- navigation ---------- */
function moveNavPill(item) {
  const pill = $("#navPill");
  pill.style.height = item.offsetHeight + "px";
  pill.style.transform = `translateY(${item.offsetTop}px)`;
}
function switchTab(tab, item) {
  if (tab !== "interview") { try { ivStopAudio(); } catch (e) {} }  // don't keep talking/listening off-tab
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b === item));
  $$(".page").forEach((p) => p.classList.remove("active"));
  const page = $("#page-" + tab); page.classList.add("active");
  moveNavPill(item);
  if (tab === "insights") renderInsights();
  if (tab === "contests") renderContests();
  if (tab === "showcase") renderCard();
  if (tab === "practice") renderPractice();
  if (tab === "learn") renderLearn();
  if (tab === "interview") renderInterview();
  if (tab === "companies") renderCompanies();
  if (tab === "plan") renderPlan();
}
$$(".nav-item").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab, b)));

/* ---------- animations ---------- */
function countUp(el, target) {
  if (typeof target !== "number") { el.textContent = target; return; }
  const dur = 750, t0 = performance.now();
  (function step(now) {
    const k = Math.min((now - t0) / dur, 1);
    el.textContent = Math.round(target * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

/* ---------- data ---------- */
// These call the bridge directly (not through act), so guard each: a Python-side
// exception must not reject the awaiting render*() and leave the tab blank.
async function _safe(fn, fallback) {
  const a = api(); if (!a) return fallback;
  try { return await fn(a); } catch (e) { toast("Error: " + e); return fallback; }
}
async function getState() { return _safe((a) => a.get_state(), SAMPLE); }
async function getInsights() { return _safe((a) => a.get_insights(), SAMPLE.insights); }
async function getContests() { return _safe((a) => a.get_contests(), SAMPLE.contests); }
async function getCard() { return _safe((a) => a.get_card(), SAMPLE.card); }

/* ---------- setup ---------- */
async function renderSetup() {
  const s = await getState();
  $("#version").textContent = s.version;
  const gh = s.github;
  $("#ghBadge").textContent = gh || "not connected";
  $("#ghBadge").className = "badge " + (gh ? "ok" : "no");
  $("#ghStatus").textContent = gh || "Not connected";
  $("#ghDot").classList.toggle("on", !!gh);
  $("#btnGithub").textContent = gh ? "Connected ✓" : "Connect GitHub";
  const sites = $("#sites"); sites.innerHTML = "";
  for (const [k, on] of Object.entries(s.sites)) {
    const el = document.createElement("div"); el.className = "site";
    el.innerHTML = `<span class="nm">${LABELS[k] || k}</span>
      <span class="pill ${on ? "on" : "off"}">${on ? "Connected" : "Not connected"}</span>
      <button class="btn sm" data-cp="${k}">${on ? "Re-login" : "Log in"}</button>`;
    sites.appendChild(el);
  }
  $$("[data-cp]").forEach((b) => b.addEventListener("click", () => act("cp_login", b.dataset.cp)));
  $$("#providerSeg button").forEach((b) =>
    b.classList.toggle("on", b.dataset.v === (s.provider || "ollama")));
  updateKeyField(s.provider || "ollama", s.api_key);
  refreshProvNote();
}

function curProvider() { const o = $("#providerSeg button.on"); return o ? o.dataset.v : "ollama"; }
function updateKeyField(provider, key) {
  const show = provider === "gemini" || provider === "groq";
  $("#keyWrap").classList.toggle("hidden", !show);
  $("#keyHint").classList.toggle("hidden", !show);
  if (key !== undefined && $("#apiKey")) $("#apiKey").value = key || "";
  const note = $("#provNote");
  if (note) {
    if (provider === "ollama") {
      note.className = "provNote rec";
      note.innerHTML = "<b>Ollama — recommended.</b> Free, fully local & private — the best experience on a Mac. " +
        "The first reply downloads the model, so give it a few seconds.";
    } else if (provider === "none") {
      note.className = "provNote";
      note.innerHTML = "AI features (tutor, write-ups, quiz grading) are off. Pick <b>Ollama</b> to turn them on for free.";
    } else if (provider === "groq") {
      note.className = "provNote rec";
      note.innerHTML = "<b>Groq — best for the mock interview &amp; voice.</b> Free &amp; fast (Llama&nbsp;3.3&nbsp;70B), far sharper than the small local model. " +
        "Get a key in ~1 min:<br>1. Open <b>console.groq.com</b> → sign in (free).<br>2. <b>API Keys → Create API Key</b> → copy the <code>gsk_…</code> value.<br>3. Paste it below and <b>Save</b>.";
    } else {
      note.className = "provNote warn";
      note.innerHTML = "⚠ Gemini's free tier has a <b>low daily cap</b>. For a sharper interviewer and voice transcription, prefer <b>Groq</b> (free, fast) or <b>Ollama</b> (free, local).";
    }
  }
}

/* ---------- showcase ---------- */
async function renderCard() {
  const c = await getCard();
  if (c) $("#cardImg").src = c.startsWith("data:") || c.endsWith(".png") ? c : "data:image/png;base64," + c;
}

/* ---------- insights ---------- */
async function renderInsights() {
  const d = await getInsights();
  const tiles = $("#tiles"); tiles.innerHTML = "";
  d.tiles.forEach(([l, v]) => {
    const t = document.createElement("div"); t.className = "tile";
    t.innerHTML = `<div class="v">0</div><div class="l">${l}</div>`;
    tiles.appendChild(t); countUp(t.querySelector(".v"), v);
  });
  const tot = Object.values(d.difficulty).reduce((a, b) => a + b, 0) || 1;
  const colors = { Easy: "var(--easy)", Medium: "var(--med)", Hard: "var(--hard)" };
  const db = $("#diffBars"); db.innerHTML = "";
  ["Easy", "Medium", "Hard"].forEach((lvl) => {
    const n = d.difficulty[lvl] || 0;
    const row = document.createElement("div"); row.className = "drow";
    row.innerHTML = `<span class="lbl" style="color:${colors[lvl]}">${lvl}</span>
      <div class="bar-bg"><div class="bar-fill" style="background:${colors[lvl]}"></div></div><span class="n">${n}</span>`;
    db.appendChild(row);
    setTimeout(() => { row.querySelector(".bar-fill").style.width = (100 * n / tot) + "%"; }, 60);
  });
  $("#topics").innerHTML = (d.topics || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("");
  renderTopicStrength(d.topic_strength);
  $("#resume").innerHTML = (d.resume || []).map((b) => `<li>${esc(b.replace(/^[-•]\s*/, ""))}</li>`).join("");
  const g = (api() ? await act("get_gamify") : GAMIFY_SAMPLE) || GAMIFY_SAMPLE;
  $("#lvlBadge").textContent = "Lv " + g.level;
  $("#xpLabel").textContent = g.xp + " XP · " + g.earned + "/" + g.total_badges + " badges";
  $("#xpNext").textContent = g.into + "/" + g.need + " to Lv " + (g.level + 1);
  setTimeout(() => { $("#xpBar").style.width = g.pct + "%"; }, 60);
  $("#badges").innerHTML = g.badges.map((b) =>
    `<div class="bdg ${b.earned ? "earned" : "locked"}"><div class="ico">${b.earned ? "✓" : "·"}</div>
     <div><div class="bn">${b.name}</div><div class="bd">${b.desc}</div></div></div>`).join("");
}
function renderTopicStrength(ts) {
  const card = $("#topicStrengthCard");
  if (!ts || !ts.topics || !ts.topics.length) { if (card) card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  $("#topicMeta").textContent = `${ts.count} topics practiced`;
  const dcol = { easy: "var(--easy,#22c55e)", med: "var(--med,#f59e0b)", hard: "var(--hard,#ef4444)" };
  $("#topicStrength").innerHTML = ts.topics.map((t) => {
    const mix = [["easy", t.easy], ["med", t.med], ["hard", t.hard]]
      .filter(([, n]) => n).map(([k, n]) => `<span class="ts-pill ${k}">${n}</span>`).join("");
    const cov = t.coverage != null ? `<span class="ts-cov" title="${t.solved}/${t.total} of all LeetCode ${esc(t.topic)} problems">${t.coverage}%</span>` : "";
    return `<div class="ts-row">
      <span class="ts-name" title="${esc(t.topic)}">${esc(t.topic)}</span>
      <span class="ts-barbg"><span class="ts-barfill" style="width:0%" data-w="${t.strength}"></span></span>
      <span class="ts-n">${t.solved}</span>
      <span class="ts-mix">${mix}</span>
      ${cov}</div>`;
  }).join("");
  requestAnimationFrame(() => $$("#topicStrength .ts-barfill").forEach((b) => { b.style.width = (b.dataset.w || 0) + "%"; }));
  const under = ts.underexplored || [];
  $("#topicUnder").innerHTML = under.length
    ? `<div class="ts-under"><span class="muted">Underexplored (common, &lt;5% done):</span> ${under.map((u) =>
        `<span class="chip ts-underchip" title="${u.solved}/${u.total} solved">${esc(u.topic)}</span>`).join("")}</div>`
    : "";
}
const GAMIFY_SAMPLE = { level: 2, xp: 515, into: 15, need: 500, pct: 3, earned: 4, total_badges: 10,
  badges: [{ name: "First Steps", desc: "Sync your first solution", earned: true },
    { name: "Getting Going", desc: "Solve 10 problems", earned: true },
    { name: "Polyglot", desc: "Use 3+ languages", earned: true },
    { name: "Centurion", desc: "Solve 100 problems", earned: false }] };
const PATTERNS_SAMPLE = [
  { name: "Sliding Window", when: "Contiguous subarray with a constraint.", idea: "Grow right, shrink left.", examples: ["Max Profit", "Min Window Substring"] },
  { name: "Two Pointers", when: "Sorted array / pairs.", idea: "Move two indices to shrink the space.", examples: ["3Sum", "Valid Palindrome"] }];

/* ---------- contests ---------- */
async function renderContests() {
  const d = await getContests();
  $("#contestList").innerHTML = (d.upcoming || []).map((c) => {
    // Contest name/url come from external APIs — escape before injecting, and
    // only emit the link if it's a real http(s) URL.
    const safeUrl = /^https?:\/\//i.test(c.url || "") ? esc(c.url) : "";
    return `<div class="contest"><span class="cbadge ${c.platform === "codeforces" ? "cf" : "lc"}">${esc(LABELS[c.platform] || c.platform)}</span>
     <span class="nm">${esc(c.name)}</span><span class="when">${esc(c.when)} · ${esc(c.dur)}</span>
     ${safeUrl ? `<a href="${safeUrl}" target="_blank" rel="noopener">open</a>` : ""}</div>`;
  }).join("") ||
    `<div class="muted">Couldn't load contests.</div>`;
  drawRating(d.rating || [], d.handle);
}
function drawRating(vals, handle) {
  const svg = $("#ratingChart"); const W = 600, H = 140, p = 12;
  if (!vals.length) { svg.innerHTML = ""; $("#ratingMeta").textContent = handle ? "no rated contests" : "connect Codeforces"; return; }
  const mn = Math.min(...vals) - 50, mx = Math.max(...vals) + 50, rng = (mx - mn) || 1;
  const pts = vals.map((v, i) => [p + (W - 2 * p) * (i / Math.max(vals.length - 1, 1)),
    H - p - (H - 2 * p) * ((v - mn) / rng)]);
  const dpath = pts.map((q) => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ");
  svg.innerHTML = `<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#5b8cff"/>
    <stop offset="1" stop-color="#7c5cfc"/></linearGradient></defs>
    <polyline class="spark" points="${dpath}"/>
    <circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="4" fill="#7c5cfc"/>`;
  $("#ratingMeta").textContent = `current ${vals.at(-1)} · max ${Math.max(...vals)} · ${vals.length} contests`;
}

/* ---------- actions ---------- */
async function act(method, ...args) {
  const a = api();
  if (!a) { toast("Preview mode — run inside GitKosh to use this."); return null; }
  try { return await a[method](...args); } catch (e) { toast("Error: " + e); return null; }
}

/* ---------- streaming (token-by-token AI) ---------- */
// Python emits window.gkStream(id, cumulativeText) per chunk; we route it to the
// registered handler. streamAsk resolves with the final full text when done.
let _streamSeq = 0;
window._streams = window._streams || {};
window.gkStream = (id, text) => { const h = window._streams[id]; if (h) h(text); };
async function streamAsk(method, args, onChunk) {
  const a = api();
  if (!a) { toast("Preview mode — run inside GitKosh to use this."); return null; }
  const id = "s" + (++_streamSeq);
  window._streams[id] = onChunk;
  try { return await a[method](...args, id); }
  catch (e) { toast("Error: " + e); return null; }
  finally { delete window._streams[id]; }
}
$("#btnGithub").addEventListener("click", connectGithub);
async function connectGithub() {
  if (!api()) { toast("Open this inside GitKosh to connect GitHub."); return; }
  const btn = $("#btnGithub"); btn.disabled = true;
  const d = await act("github_start");
  btn.disabled = false;
  if (!d || !d.ok) { toast("Couldn't start GitHub login: " + ((d && d.error) || "check your connection")); return; }
  // Show the code BEFORE opening the browser — GitHub never shows it for you.
  $("#ghCode").textContent = d.user_code;
  try { await navigator.clipboard?.writeText(d.user_code); } catch (e) {}
  const status = $("#ghStatusMsg"); status.textContent = "Waiting for you to authorize on GitHub…";
  $("#ghCopy").onclick = async () => { try { await navigator.clipboard?.writeText(d.user_code); toast("Code copied"); } catch (e) {} };
  $("#ghOpen").onclick = () => act("github_open", d.verification_uri);
  let cancelled = false;
  $("#ghCancel").onclick = () => { cancelled = true; $("#ghAuth").classList.add("hidden"); };
  $("#ghAuth").classList.remove("hidden");
  const res = await act("github_poll", d.device_code, d.interval, d.expires_in);
  if (cancelled) return;
  if (res && res.ok) {
    $("#ghAuth").classList.add("hidden");
    toast("✓ Connected as " + res.login);
    renderSetup();
  } else {
    status.textContent = "Login didn't complete: " + ((res && res.error) || "timed out") + ". Close this and try again.";
  }
}
// Keep the final "done"/error state visible briefly, then clear the bar so it
// doesn't stay pinned at 100% until the next action.
async function runSyncFlow(reset) { showProg(); try { await act("run_sync", reset); } finally { setTimeout(() => $("#progWrap").classList.add("hidden"), 4000); } }
$("#btnSync").addEventListener("click", () => runSyncFlow(false));
$("#btnReset").addEventListener("click", () => runSyncFlow(true));
$("#btnPublish").addEventListener("click", () =>
  act("publish_site").then((u) => toast(u ? "Published: " + u : "Couldn't publish — connect GitHub and sync first.")));
$("#btnPost").addEventListener("click", async () => { $("#postBox").value = "Generating…";
  const r = await act("generate_post");
  $("#postBox").value = (r && r.post) || ""; if (!r || !r.post) toast("Couldn't generate a post — check your AI provider."); });
$("#btnCopyEmbed").addEventListener("click", async () => {
  const md = await act("get_embed"); navigator.clipboard?.writeText(md || ""); toast("Embed code copied"); });

/* ---------- backfill: import local past work (honest backdating) ---------- */
let _bfPath = "";
$("#btnPickFolder")?.addEventListener("click", async () => {
  if (!api()) { toast("Folder import works inside GitKosh."); return; }
  const p = await act("pick_folder");
  if (!p) return;
  _bfPath = p;
  $("#bfPath").textContent = p;
  const pv = $("#bfPreview"); pv.classList.remove("hidden");
  pv.innerHTML = `<div class="muted">Scanning…</div>`;
  $("#btnBackfill").classList.add("hidden");
  const s = await act("backfill_preview", p);
  if (!s || !s.ok || !s.total_files) {
    pv.innerHTML = `<div class="muted">${esc((s && s.error) || "No importable text files found there.")}</div>`;
    return;
  }
  const rows = (s.preview || []).map((r) => `<tr><td>${esc(r.date)}</td><td>${r.count}</td></tr>`).join("");
  pv.innerHTML = `
    <div class="bf-stat"><b>${s.total_files}</b> files · <b>${s.total_days}</b> day(s) · ${s.is_git ? "git dates" : "file dates"}${s.skipped ? " · " + s.skipped + " skipped" : ""}${s.capped ? " · capped" : ""}</div>
    <div class="muted">${esc(s.oldest || "")} → ${esc(s.newest || "")}</div>
    <table class="bf-table"><thead><tr><th>Day</th><th>Files → 1 commit</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="muted">Creates one backdated commit per day under <code>imports/${esc(s.name)}</code>.</div>`;
  $("#btnBackfill").classList.remove("hidden");
});
$("#btnBackfill")?.addEventListener("click", async () => {
  if (!_bfPath) return;
  showProg();
  try {
    const r = await act("backfill_run", _bfPath);
    if (r && r.ok) toast(`✓ Imported ${r.files} file(s) in ${r.commits} commit(s)`);
    else toast("Import failed: " + ((r && r.error) || "unknown"));
  } finally { setTimeout(() => $("#progWrap").classList.add("hidden"), 4000); }
});
$("#btnRefreshCard").addEventListener("click", renderCard);
$("#btnRefreshContests").addEventListener("click", renderContests);
$("#btnCopyResume").addEventListener("click", () => {
  navigator.clipboard?.writeText([...$$("#resume li")].map((l) => "- " + l.textContent).join("\n")); toast("Copied"); });
$$("#providerSeg button").forEach((b) => b.addEventListener("click", () => {
  $$("#providerSeg button").forEach((x) => x.classList.toggle("on", x === b));
  updateKeyField(b.dataset.v);
  act("set_provider", b.dataset.v);
  if (b.dataset.v === "ollama") ensureOllama(); }));

// Install / start Ollama + pull the model, with live progress. Idempotent, so it's
// safe to call whenever the user picks Ollama — it's near-instant once set up.
async function ensureOllama() {
  if (!api()) return;
  const st = await act("ai_status");
  if (st && st.ready) { refreshProvNote(); return; }
  showProg();
  window.gkProgress("Setting up local AI (Ollama)…", 5);
  const r = await act("setup_ollama");
  $("#progWrap").classList.add("hidden");
  if (r && r.ok) toast("✓ Local AI is ready");
  else toast("Ollama setup failed: " + ((r && r.error) || "unknown") + " — see ollama.com");
  refreshProvNote();
}

async function refreshProvNote() {
  if (!api()) return;
  const st = await act("ai_status");
  const note = $("#provNote");
  if (!note || !st) return;
  if (st.provider === "ollama") {
    if (st.ready) {
      note.className = "provNote rec";
      note.innerHTML = "<b>✓ Ollama ready.</b> Free, fully local & private — AI tutor, reviews and write-ups are on.";
    } else if (st.state === "running_no_model") {
      note.className = "provNote warn";
      note.innerHTML = "Ollama is running — finishing the one-time model download. Hang tight a moment.";
    } else {
      note.className = "provNote";
      note.innerHTML = "Click <b>Ollama</b> above to install & start it automatically (one-time, a couple of GB).";
    }
  }
}
$("#btnSaveKey").addEventListener("click", () =>
  act("save_ai", curProvider(), $("#apiKey").value).then(() => toast("AI settings saved")));
/* ---------- practice / quiz 2.0 ---------- */
const TOPICS = ["Array", "Hash Table", "Two Pointers", "Sliding Window", "Stack", "Binary Search",
  "Linked List", "Tree", "Heap", "Backtracking", "Graph", "Dynamic Programming", "Greedy",
  "Intervals", "Bit Manipulation", "Math", "Trie", "Sorting", "Recursion", "Matrix", "String", "Queue"];
const SAMPLE_PRACTICE = {
  potd: { due: 5, review_streak: 3, next: { title: "Two Sum", slug: "two-sum", sheet: "NeetCode 150", url: "#" },
          weak: ["Graphs", "Dynamic Programming", "Trie"] },
  srs: { due: 5, new: 33, reviewed_today: 2, review_streak: 3 },
  roadmaps: [{ name: "Blind 75", total: 75, done: 9, pct: 12 }, { name: "NeetCode 150", total: 150, done: 14, pct: 9 }],
  queue: [
    { key: "x", title: "Maximum Path Score in a Grid", platform: "LeetCode", difficulty: "Hard",
      tags: ["Dynamic Programming", "Matrix"], approach: "1. DP over grid cells.\n2. Track best incoming path.\n3. Answer at bottom-right.", url: "#" },
    { key: "y", title: "Count Stable Subarrays", platform: "LeetCode", difficulty: "Medium",
      tags: ["Array", "Prefix Sum"], approach: "Prefix sums + two pointers.", url: "#" }],
};
async function getPractice() { return _safe((a) => a.get_practice(), SAMPLE_PRACTICE); }

let Q = { queue: [], idx: 0, mode: "recall" };
// Escapes &<> via textContent AND quotes, so it's safe inside double/single-quoted
// HTML attributes (the value is interpolated into many attrs across this file).
function esc(s) {
  const d = document.createElement("div"); d.textContent = s == null ? "" : String(s);
  return d.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function renderPractice() {
  const d = await getPractice(); window._practice = d;
  const p = d.potd || {};
  $("#dueBadge").textContent = (p.due || 0) + " due";
  $("#revStreak").textContent = p.review_streak || 0;
  $("#revToday").textContent = (d.srs && d.srs.reviewed_today) || 0;
  let h = "";
  if (p.due) h += `<div class="big">🔁 ${p.due} problem(s) due for review.</div>
    <button class="btn btn-accent" id="potdReview" style="margin-top:8px">Start review</button>`;
  if (p.next) h += `<div class="big" style="margin-top:14px">Next to solve: <a href="${p.next.url}" target="_blank">${p.next.title}</a></div>
    <div class="muted">from ${p.next.sheet}</div>`;
  if (p.weak && p.weak.length) h += `<div class="weak">Focus areas: ${p.weak.join(" · ")}</div>`;
  $("#potd").innerHTML = h || `<div class="muted">All caught up 🎉</div>`;
  const pr = $("#potdReview"); if (pr) pr.addEventListener("click", startQuiz);
  $("#roadmaps").innerHTML = (d.roadmaps || []).map((r) =>
    `<div class="rmrow"><div class="top"><span>${r.name}</span><b>${r.done}/${r.total} · ${r.pct}%</b></div>
     <div class="bar-bg"><div class="bar-fill" style="width:0"></div></div></div>`).join("");
  setTimeout(() => $$("#roadmaps .bar-fill").forEach((b, i) => { b.style.width = d.roadmaps[i].pct + "%"; }), 60);
  $("#quizMeta").textContent = `${(d.srs && d.srs.due) || 0} due · ${(d.srs && d.srs.new) || 0} new`;
}

async function startQuiz() {
  // The launch banner can trigger this before renderPractice() has loaded data —
  // fetch it on demand rather than racing a timer.
  if (!window._practice) window._practice = await getPractice();
  const d = window._practice || {};
  Q.queue = (d.queue || []).slice(0, 20); Q.idx = 0;
  if (!Q.queue.length) { $("#quizCard").innerHTML = `<div class="muted">Nothing due — great job! Cards become reviewable as you solve & sync.</div>`; return; }
  $("#btnStartQuiz").textContent = "Restart"; showCard();
}
function rateRow() {
  return `<div class="rate"><button class="again" data-r="again">Again</button>
    <button class="hard" data-r="hard">Hard</button><button class="good" data-r="good">Good</button>
    <button class="easy" data-r="easy">Easy</button></div>`;
}
function bindRate(c) {
  $$(".rate button").forEach((b) => b.addEventListener("click", async () => {
    await act("quiz_review", c.key, b.dataset.r); Q.idx++; showCard();
  }));
}
function mcqOptions(correct, tags) {
  const pool = TOPICS.filter((t) => t !== correct && !tags.includes(t));
  const picks = [];
  while (picks.length < 3 && pool.length) picks.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
  const opts = [correct, ...picks];
  for (let i = opts.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [opts[i], opts[j]] = [opts[j], opts[i]]; }
  return opts;
}
function showCard() {
  const card = $("#quizCard");
  if (Q.idx >= Q.queue.length) {
    card.innerHTML = `<div class="qtitle">Session complete 🎉</div><div class="muted">${Q.queue.length} card(s) reviewed.</div>`;
    renderPractice(); $("#btnStartQuiz").textContent = "Start session"; return;
  }
  const c = Q.queue[Q.idx];
  const prog = `<div class="sessbar"><i style="width:${100 * Q.idx / Q.queue.length}%"></i></div>`;
  const head = `<div class="qtitle">${esc(c.title)}</div><div class="qmeta">${c.platform} · ${c.difficulty || ""} · ${(c.tags || []).slice(0, 3).join(", ")}</div>`;
  if (Q.mode === "recall") {
    card.innerHTML = prog + head + `<button class="btn" id="revealBtn">Reveal approach</button><div id="revealArea"></div>`;
    $("#revealBtn").addEventListener("click", () => {
      $("#revealArea").innerHTML = `<div class="reveal">${esc(c.approach) || "(no approach stored)"}</div>` + rateRow(); bindRate(c);
    });
  } else if (Q.mode === "type") {
    card.innerHTML = prog + head + `<textarea id="ans" rows="3" placeholder="Type your approach from memory…"></textarea>
      <button class="btn btn-accent" id="gradeBtn" style="margin-top:10px">Grade with AI</button><div id="revealArea"></div>`;
    $("#gradeBtn").addEventListener("click", async () => {
      $("#gradeBtn").textContent = "Grading…";
      const fb = await act("grade_answer", c.key, $("#ans").value);
      $("#revealArea").innerHTML = `<div class="feedback">${esc(fb || "")}</div><div class="reveal">${esc(c.approach)}</div>` + rateRow(); bindRate(c);
    });
  } else {
    const correct = (c.tags && c.tags[0]) || "Array";
    const opts = mcqOptions(correct, c.tags || []);
    card.innerHTML = prog + head + `<div class="muted">Which topic/pattern fits?</div>
      <div class="mcq" id="mcq">${opts.map((o) => `<button data-o="${o}">${o}</button>`).join("")}</div><div id="revealArea"></div>`;
    $$("#mcq button").forEach((b) => b.addEventListener("click", () => {
      $$("#mcq button").forEach((x) => { x.style.pointerEvents = "none";
        if (x.dataset.o === correct) x.classList.add("correct"); else if (x === b) x.classList.add("wrong"); });
      $("#revealArea").innerHTML = `<div class="reveal">${esc(c.approach)}</div>` + rateRow(); bindRate(c);
    }));
  }
}
$("#btnStartQuiz").addEventListener("click", startQuiz);
$$("#qmodes button").forEach((b) => b.addEventListener("click", () => {
  $$("#qmodes button").forEach((x) => x.classList.toggle("on", x === b));
  Q.mode = b.dataset.m;
  if (Q.queue.length && Q.idx < Q.queue.length) showCard();
}));

function showProg() { $("#progWrap").classList.remove("hidden"); window.gkProgress("Working…", 8); }
// called from Python via evaluate_js
window.gkProgress = (text, pct) => {
  $("#progWrap").classList.remove("hidden");
  $("#progText").textContent = text || "";
  $("#progBar").style.width = (pct || 0) + "%";
};
window.gkRefresh = () => { renderSetup(); };

/* ---------- learn (AI tutor + in-app solve) ---------- */
const SAMPLE_PROBLEMS = [
  { id: "contains-duplicate", title: "Contains Duplicate", difficulty: "Easy", topic: "Array / Hashing" },
  { id: "maximum-subarray", title: "Maximum Subarray", difficulty: "Medium", topic: "DP / Greedy" }];
let chat = [], learnInit = false;

// Full-ish Markdown → HTML (headings, lists, code blocks, inline, links, quotes).
function mdLite(src) {
  if (!src) return "";
  const blocks = [];
  src = String(src).replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) =>
    " " + (blocks.push(`<pre class="md-pre"><code>${esc(code.replace(/\n+$/, ""))}</code></pre>`) - 1) + " ");
  const inline = (s) => {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, (m, c) => `<code>${c}</code>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  };
  const out = [];
  let list = null, para = [];
  const closeList = () => { if (list) { out.push(`<${list.t}>` + list.items.map((x) => `<li>${x}</li>`).join("") + `</${list.t}>`); list = null; } };
  const closePara = () => { if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; } };
  for (const raw of src.split("\n")) {
    const line = raw.replace(/\s+$/, "");
    let m = line.match(/^ (\d+) $/);
    if (m) { closePara(); closeList(); out.push(blocks[+m[1]]); continue; }
    if (!line.trim()) { closePara(); closeList(); continue; }
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      closePara(); closeList();
      const lvl = Math.min(m[1].length + 2, 6);  // demote: chat ## shouldn't be page-title sized
      out.push(`<div class="md-h md-h${lvl}">${inline(m[2])}</div>`); continue;
    }
    if ((m = line.match(/^\s*[-*+]\s+(.*)$/))) {
      closePara(); if (!list || list.t !== "ul") { closeList(); list = { t: "ul", items: [] }; }
      list.items.push(inline(m[1])); continue;
    }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      closePara(); if (!list || list.t !== "ol") { closeList(); list = { t: "ol", items: [] }; }
      list.items.push(inline(m[1])); continue;
    }
    if ((m = line.match(/^\s*>\s?(.*)$/))) { closePara(); closeList(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
    para.push(line.trim());
  }
  closePara(); closeList();
  return out.join("");
}
function renderChat() {
  const c = $("#chat");
  c.innerHTML = chat.map((m) =>
    `<div class="msg ${m.role === "user" ? "user" : "bot"}${m.content === "…" ? " typing" : ""}">${m.role === "user" ? esc(m.content) : mdLite(m.content)}</div>`).join("");
  c.scrollTop = c.scrollHeight;
}
async function sendChat(text) {
  text = (text || $("#chatInput").value).trim(); if (!text) return;
  $("#chatInput").value = "";
  chat.push({ role: "user", content: text });
  const placeholder = { role: "bot", content: "…", pending: true };
  const idx = chat.push(placeholder) - 1; renderChat();
  if ($("#chatSend")) $("#chatSend").disabled = true;
  // Reassure the user while a local model warms up — it can take a few seconds.
  const warm = setTimeout(() => {
    if (chat[idx] && chat[idx].pending) {
      chat[idx].content = "Thinking… the local model is warming up — the first reply can take ~10s.";
      renderChat();
    }
  }, 9000);
  let reply;
  if (api()) {
    const hist = chat.filter((m) => !m.pending);
    reply = await streamAsk("tutor_chat_stream", [hist], (t) => {
      // Live-update the placeholder bubble as tokens arrive.
      chat[idx] = { role: "bot", content: t };
      renderChat();
    });
  } else reply = "(Preview) Open GitKosh with an AI engine to chat. Tip: identify the pattern, find the invariant, then improve on brute force.";
  clearTimeout(warm);
  chat[idx] = { role: "bot", content: reply || "No reply — check your AI engine in Setup (Ollama recommended)." };
  renderChat();
  if ($("#chatSend")) $("#chatSend").disabled = false;
}
async function renderLearn() {
  if (!learnInit) {
    learnInit = true;
    if (!chat.length) { chat.push({ role: "bot", content: "Hi! I'm your DSA tutor 👋 Ask me to explain a concept, give a hint, or review your approach — or tap a chip below." }); renderChat(); }
    $("#probSelect").addEventListener("change", loadProblem);
    $("#probSearch").addEventListener("input", () => buildProblemOptions($("#probSearch").value));
    $("#chatSend").addEventListener("click", () => sendChat());
    $("#chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
    $$("#tutorChips .chip").forEach((c) => c.addEventListener("click", () => sendChat(c.dataset.q)));
    $("#runBtn").addEventListener("click", runCode);
    $("#testBtn").addEventListener("click", runTests);
    $("#reviewBtn").addEventListener("click", aiReview);
    setupLangPicker();
    $("#resetBtn").addEventListener("click", async () => {
      const pid = $("#probSelect").value;
      if (api() && pid && pid !== "__scratch") await act("reset_code", pid);
      loadProblem(true);
    });
    $("#editor").addEventListener("keydown", editorTab);
    $("#editor").addEventListener("input", () => { syncHL(); saveCodeDebounced(); });
    $("#editor").addEventListener("scroll", () => { const hl = $("#editorHL"); hl.scrollTop = $("#editor").scrollTop; hl.scrollLeft = $("#editor").scrollLeft; });
    $("#vizPlay").addEventListener("click", vizPlay);
    $("#vizStop").addEventListener("click", vizHalt);
    $("#vizShuffle").addEventListener("click", vizInit);
    vizInit();
  }
  if (!window._learnReal) {  // (re)load once the Python bridge is actually available
    const live = !!api();
    PROBLEMS = live ? (await act("list_problems") || []) : SAMPLE_PROBLEMS;
    buildProblemOptions("");
    renderPatterns(live ? await act("get_patterns") : PATTERNS_SAMPLE);
    if (live) window._learnReal = true;
    const pq = new URLSearchParams(location.search).get("p");
    if (pq && [...$("#probSelect").options].some((o) => o.value === pq)) $("#probSelect").value = pq;
    await loadProblem();
  }
}

/* ---------- in-app IDE: full NeetCode 150 catalog ---------- */
let PROBLEMS = [];
const reviewAttempts = {};

// Multi-language Run support. Tests stay Python-only (the catalog harness is Python).
const LANG_LABELS = { python: "Python", cpp: "C++", java: "Java", javascript: "JavaScript" };
const LANG_TEMPLATES = {
  python: "# Scratchpad — write Python, add input below, then Run\nprint('Hello from GitKosh')\n",
  cpp: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    cout << \"Hello from GitKosh\" << endl;\n    return 0;\n}\n",
  java: "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello from GitKosh\");\n    }\n}\n",
  javascript: "// Scratchpad — write JavaScript, then Run\nconsole.log('Hello from GitKosh');\n",
};
let _editorBaseline = "";  // last value set programmatically — used to detect "untouched"
function curLang() { const s = $("#langSelect"); return (s && s.value) || "python"; }
async function setupLangPicker() {
  const sel = $("#langSelect");
  if (!sel || sel.dataset.ready) return;
  sel.dataset.ready = "1";
  const status = api() ? (await act("lang_status") || {}) : { python: true, cpp: true, java: true, javascript: true };
  sel.innerHTML = Object.keys(LANG_LABELS).map((k) =>
    `<option value="${k}">${LANG_LABELS[k]}${status[k] === false ? " ⚠ install needed" : ""}</option>`).join("");
  sel.addEventListener("change", onLangChange);
}
function onLangChange() {
  const lang = curLang();
  const tb = $("#testBtn");
  if (tb) { tb.disabled = lang !== "python"; tb.title = lang !== "python" ? "Automated tests are Python-only" : ""; }
  // In the scratchpad, swap to the language's template if the user hasn't edited it.
  if ($("#probSelect").value === "__scratch") {
    const ta = $("#editor");
    if (!ta.value.trim() || ta.value === _editorBaseline) setEditor(LANG_TEMPLATES[lang] || "");
  }
}
function buildProblemOptions(filter) {
  const sel = $("#probSelect");
  const prev = sel.value;
  const q = (filter || "").trim().toLowerCase();
  const matches = PROBLEMS.filter((p) => !q || p.title.toLowerCase().includes(q) || (p.topic || "").toLowerCase().includes(q));
  $("#probCount").textContent = q ? `(${matches.length})` : `· ${PROBLEMS.length} problems`;
  const groups = { Easy: [], Medium: [], Hard: [] };
  matches.forEach((p) => (groups[p.difficulty] || (groups[p.difficulty] = [])).push(p));
  const opt = (p) => `<option value="${p.id}">${p.tested ? "✓ " : ""}${esc(p.title)}${p.blind75 ? "  ·  B75" : ""}</option>`;
  let html = `<option value="__scratch">⌨︎ Scratchpad (free Python)</option>`;
  for (const lvl of ["Easy", "Medium", "Hard"]) {
    if (groups[lvl] && groups[lvl].length) html += `<optgroup label="${lvl} (${groups[lvl].length})">` + groups[lvl].map(opt).join("") + `</optgroup>`;
  }
  sel.innerHTML = html;
  if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  else if (q && matches.length) { sel.value = matches[0].id; loadProblem(); }
}

const DIFF_CLASS = { Easy: "easy", Medium: "med", Hard: "hard" };
let _loadSeq = 0;
async function loadProblem(forceReset) {
  const seq = ++_loadSeq;  // ignore stale responses if the user switches problems fast
  clearTimeout(_saveTimer);  // drop any pending debounced save for the previous problem
  const pid = $("#probSelect").value;
  $("#runOut").textContent = ""; $("#runStatus").textContent = "";
  $("#reviewOut").classList.add("hidden"); $("#reviewOut").innerHTML = "";
  if (pid === "__scratch") {
    $("#stdinWrap").classList.remove("hidden"); $("#testBtn").style.display = "none"; $("#reviewBtn").style.display = "none";
    $("#probMeta").innerHTML = "";
    const lang = curLang();
    $("#probStatement").textContent = `Free ${LANG_LABELS[lang] || "code"} scratchpad — read stdin and print output, then Run.`;
    setEditor(LANG_TEMPLATES[lang] || LANG_TEMPLATES.python);
    return;
  }
  $("#stdinWrap").classList.add("hidden"); $("#testBtn").style.display = ""; $("#reviewBtn").style.display = "";
  const p = api() ? await act("get_problem", pid) : (PROBLEMS.find((x) => x.id === pid) || { statement: "(preview) Solve in the app.", starter: "def solve():\n    pass\n" });
  if (seq !== _loadSeq) return;  // a newer loadProblem() superseded this one
  if (!p) return;
  if (forceReset) reviewAttempts[pid] = 0;
  const dc = DIFF_CLASS[p.difficulty] || "med";
  $("#probMeta").innerHTML =
    `<span class="dchip ${dc}">${esc(p.difficulty || "")}</span>` +
    (p.topic ? `<span class="tchip">${esc(p.topic)}</span>` : "") +
    (p.blind75 ? `<span class="tchip b75">Blind 75</span>` : "") +
    (p.tested ? `<span class="tchip tested">✓ auto-tested</span>` : `<span class="tchip">AI-reviewed</span>`) +
    (p.url ? `<a class="lc" href="${p.url}" target="_blank" rel="noopener">LeetCode ↗</a>` : "");
  $("#probStatement").textContent = p.statement || "";
  let code = p.starter || "";
  if (!forceReset && api()) {
    const saved = await act("get_code", pid);
    if (seq !== _loadSeq) return;  // stale — a newer problem was selected meanwhile
    if (saved && saved.trim()) code = saved;
  }
  setEditor(code);
}
function setEditor(v) { _editorBaseline = v; $("#editor").value = v; syncHL(); $("#editor").scrollTop = 0; }
let _saveTimer = null;
function saveCodeDebounced() {
  const pid = $("#probSelect").value;
  if (!api() || !pid || pid === "__scratch") return;
  // Capture pid + value NOW; if the user switches problems before the timer fires,
  // we must save A's code under A, not under whatever is selected at fire time.
  const code = $("#editor").value;
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => act("save_code", pid, code), 600);
}

/* lightweight Python syntax highlighting (offline, no deps) */
const PY_RE = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\b(\d+\.?\d*j?)\b|\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b|\b(print|len|range|int|str|list|dict|set|tuple|sum|min|max|abs|sorted|enumerate|zip|map|filter|float|bool|input|open|isinstance|type|reversed|any|all|round|ord|chr|format|repr|hash|self)\b/g;
function pyHighlight(src) {
  let s = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return s.replace(PY_RE, (m, com, str, num, kw, bi) => {
    if (com !== undefined) return `<span class="tok-com">${com}</span>`;
    if (str !== undefined) return `<span class="tok-str">${str}</span>`;
    if (num !== undefined) return `<span class="tok-num">${num}</span>`;
    if (kw !== undefined) return `<span class="tok-kw">${kw}</span>`;
    if (bi !== undefined) return `<span class="tok-bi">${bi}</span>`;
    return m;
  });
}
function syncHL() {
  const ta = $("#editor"), hl = $("#editorHL");
  if (!ta || !hl) return;
  hl.firstChild.innerHTML = pyHighlight(ta.value) + "\n";
  hl.scrollTop = ta.scrollTop; hl.scrollLeft = ta.scrollLeft;
}
async function aiReview() {
  const pid = $("#probSelect").value;
  if (pid === "__scratch") { toast("Pick a problem to get an AI review."); return; }
  if (!api()) { toast("AI Review runs inside the app with an AI engine on."); return; }
  const box = $("#reviewOut");
  box.classList.remove("hidden");
  reviewAttempts[pid] = (reviewAttempts[pid] || 0) + 1;
  box.innerHTML = `<div class="md-loading">✨ Reviewing your solution… <span class="muted">(local model may take a few seconds)</span></div>`;
  const r = await streamAsk("ai_review_stream", [$("#editor").value, pid, reviewAttempts[pid]],
    (t) => { box.innerHTML = mdLite(t); });
  box.innerHTML = mdLite(r || "Couldn't review — check your AI engine in Setup.");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- mock interview ---------- */
let IV = { init: false, pid: null, title: "", chat: [], t0: 0, timer: null, running: false };
async function renderInterview() {
  if (!IV.init) {
    IV.init = true;
    // Warm up system voices so a high-quality one is picked once they load.
    try { if (window.speechSynthesis) { window.speechSynthesis.getVoices(); window.speechSynthesis.onvoiceschanged = () => { VOICE.voice = null; }; } } catch (e) {}
    const sel = $("#ivProblem");
    const list = api() ? (await act("interview_problems") || []) : SAMPLE_PROBLEMS;
    sel.innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.title)} · ${esc(p.difficulty)}</option>`).join("");
    $("#ivRandom").addEventListener("click", () => {
      const opts = sel.options; if (opts.length) sel.selectedIndex = Math.floor(Math.random() * opts.length);
    });
    $("#ivStart").addEventListener("click", () => startInterview(sel.value));
    $("#ivSend").addEventListener("click", ivSend);
    $("#ivInput").addEventListener("keydown", (e) => { if (e.key === "Enter") ivSend(); });
    $("#ivScore").addEventListener("click", ivScore);
    $("#ivQuit").addEventListener("click", ivQuit);
    $("#ivMic").addEventListener("click", voiceToggleRec);
    $("#ivVoiceToggle").addEventListener("click", toggleVoice);
  }
}
function ivRenderChat() {
  const c = $("#ivChat");
  c.innerHTML = IV.chat.map((m) =>
    `<div class="msg ${m.role === "user" ? "user" : "bot"}${m.content === "…" ? " typing" : ""}">${m.role === "user" ? esc(m.content) : mdLite(m.content)}</div>`).join("");
  c.scrollTop = c.scrollHeight;
}
function ivTick() {
  const s = Math.floor((Date.now() - IV.t0) / 1000);
  const mm = String(Math.floor(s / 60)).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  $("#ivTimer").textContent = `${mm}:${ss}`;
}
async function startInterview(pid) {
  if (!api()) { toast("Mock interview runs inside GitKosh with an AI engine on."); return; }
  const r = await act("interview_start", pid);
  if (!r || !r.ok) { toast((r && r.error) || "Couldn't start the interview."); return; }
  IV.pid = r.pid; IV.title = r.problem.title || ""; IV.chat = [{ role: "bot", content: r.opener }]; IV.running = true;
  $("#ivSetup").classList.add("hidden"); $("#ivLive").classList.remove("hidden");
  $("#ivScorecard").classList.add("hidden"); $("#ivScorecard").innerHTML = "";
  $("#ivTitle").textContent = `${r.problem.title} · ${r.problem.difficulty}`;
  $("#ivStatement").textContent = r.problem.statement || "";
  $("#ivCode").value = r.problem.starter || "";
  ivRenderChat();
  IV.t0 = Date.now(); clearInterval(IV.timer); IV.timer = setInterval(ivTick, 1000); ivTick();
  ttsSpeak(r.opener, autoListen);  // voice-first: greet aloud, then auto-listen
  $("#ivInput").focus();
}
async function ivSend(text) {
  if (!IV.running) return;
  text = (text || $("#ivInput").value).trim(); if (!text) return;
  $("#ivInput").value = "";
  IV.chat.push({ role: "user", content: text });
  const idx = IV.chat.push({ role: "bot", content: "…", pending: true }) - 1;
  ivRenderChat();
  $("#ivSend").disabled = true;
  const hist = IV.chat.filter((m) => !m.pending);
  const reply = await streamAsk("interview_reply", [hist, IV.pid, $("#ivCode").value],
    (t) => { IV.chat[idx] = { role: "bot", content: t }; ivRenderChat(); });
  IV.chat[idx] = { role: "bot", content: reply || "Let's continue — what's your next step?" };
  ivRenderChat();
  $("#ivSend").disabled = false;
  ttsSpeak(IV.chat[idx].content, autoListen);  // ask aloud, then auto-listen for the answer
}

/* ---------- voice: TTS (interviewer speaks) + STT (you answer) ---------- */
const VOICE = { on: true, recording: false, busy: false, fails: 0, voice: null, utter: null, gen: 0 };
function stripForSpeech(md) {
  return String(md || "").replace(/```[\s\S]*?```/g, " — code — ")
    .replace(/`([^`]+)`/g, "$1").replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/[#*_>~|]/g, "").replace(/\s+/g, " ").trim();
}
function pickVoice() {
  try {
    const vs = (window.speechSynthesis && window.speechSynthesis.getVoices()) || [];
    if (!vs.length) return null;          // not ready yet — use default, retry next time
    if (VOICE.voice) return VOICE.voice;
    const pref = ["Samantha", "Google US English", "Microsoft Aria Online (Natural) - English (United States)", "Alex", "Karen", "Daniel"];
    let v = null;
    for (const n of pref) { v = vs.find((x) => x.name === n); if (v) break; }
    if (!v) v = vs.find((x) => /en[-_]US/i.test(x.lang)) || vs.find((x) => /^en/i.test(x.lang)) || null;
    VOICE.voice = v;
    return v;
  } catch (e) { return null; }
}
function markSpeaking(on) {
  const b = [...document.querySelectorAll("#ivChat .msg.bot")].pop();
  if (b) b.classList.toggle("speaking", on);
}
function ttsSpeak(text, onDone) {
  const say = VOICE.on ? stripForSpeech(text) : "";
  if (!say) { if (onDone) onDone(); return; }
  // Generation token: any newer speak() or stopSpeaking() invalidates this turn's
  // pending callbacks, so a stale safety-timer can't fire during the next question.
  const myGen = ++VOICE.gen;
  let fired = false;
  const fin = () => { if (fired || myGen !== VOICE.gen) return; fired = true; markSpeaking(false); if (onDone) onDone(); };
  try {
    if (window.speechSynthesis) {            // built-in, offline, cancelable
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(say);
      u.lang = "en-US"; u.rate = 1.02; u.pitch = 1.0;
      const v = pickVoice(); if (v) u.voice = v;
      u.onend = fin; u.onerror = fin;
      VOICE.utter = u; markSpeaking(true);
      window.speechSynthesis.speak(u);
      // safety net only — onend is primary; keep it generous so it never preempts real speech
      setTimeout(fin, Math.min(90000, 3500 + say.length * 75));
      return;
    }
  } catch (e) { /* fall through to native */ }
  markSpeaking(true);
  act("voice_speak", say);                    // native `say` fallback
  setTimeout(fin, Math.min(90000, 2500 + say.length * 70));
}
function stopSpeaking() {
  VOICE.gen++;  // invalidate any pending fin() from the current utterance
  try {
    if (VOICE.utter) { VOICE.utter.onend = null; VOICE.utter.onerror = null; VOICE.utter = null; }
    window.speechSynthesis && window.speechSynthesis.cancel();
  } catch (e) {}
  markSpeaking(false);
  act("voice_stop_speaking");
}
function toggleVoice() {
  VOICE.on = !VOICE.on;
  const b = $("#ivVoiceToggle");
  b.textContent = VOICE.on ? "🔊 Voice on" : "🔇 Voice off";
  b.classList.toggle("off", !VOICE.on);
  if (!VOICE.on) stopSpeaking();
}
function setMic(state) {  // "idle" | "recording" | "busy"
  const m = $("#ivMic"); if (!m) return;
  m.classList.toggle("recording", state === "recording");
  m.classList.toggle("busy", state === "busy");
  const lbl = state === "recording" ? "Listening… tap when done"
    : state === "busy" ? "Transcribing…" : "Tap to answer";
  m.innerHTML = (state === "recording" ? "⏺" : "🎤") + `<span class="lbl">${esc(lbl)}</span>`;
}
// Voice-first: auto-start listening once the interviewer finishes speaking.
function autoListen() {
  if (!IV.running || !VOICE.on || VOICE.recording || VOICE.busy) return;
  setTimeout(() => {
    if (IV.running && VOICE.on && !VOICE.recording && !VOICE.busy && isTab("interview")) voiceStartRec();
  }, 350);
}
function isTab(name) {
  const p = $("#page-" + name); return p && p.classList.contains("active");
}
async function voiceStartRec() {
  if (!api() || VOICE.recording || VOICE.busy) return;
  stopSpeaking();  // make sure the AI isn't talking into the mic
  const r = await act("voice_start");
  if (!r || !r.ok) { toast((r && r.error) || "Microphone unavailable — check permissions."); return; }
  VOICE.recording = true; setMic("recording");
}
async function voiceStopRec() {
  if (!VOICE.recording) return;
  VOICE.recording = false; VOICE.busy = true; setMic("busy");
  const r = await act("voice_stop", IV.title ? [IV.title] : []);  // bias toward this problem
  VOICE.busy = false; setMic("idle");
  if (r && r.ok && r.text) {
    VOICE.fails = 0;
    $("#ivInput").value = r.text; ivSend();
  } else {
    const err = (r && r.error) || "Couldn't hear that — tap the mic to try again, or type.";
    const transient = /didn'?t catch/i.test(err);  // silence/too-short → worth auto-retrying
    VOICE.fails = (VOICE.fails || 0) + 1;
    if (transient && VOICE.fails < 2 && IV.running && VOICE.on && isTab("interview")) {
      toast("Didn't catch that — listening again…"); autoListen();
    } else {
      VOICE.fails = 0;
      toast(err);  // show the real, actionable reason (permission/setup/etc.)
    }
  }
}
function voiceToggleRec() {
  if (!api()) { toast("Voice answers work inside GitKosh."); return; }
  if (VOICE.recording) voiceStopRec(); else voiceStartRec();
}
// Stop all audio when leaving the Interview tab (called from switchTab).
function ivStopAudio() {
  stopSpeaking();
  if (VOICE.recording) { VOICE.recording = false; act("voice_stop"); setMic("idle"); }
}
async function ivScore() {
  if (!IV.pid) return;
  const box = $("#ivScorecard"); box.classList.remove("hidden");
  box.innerHTML = `<div class="md-loading">📋 Scoring your interview…</div>`;
  const elapsed = Math.floor((Date.now() - IV.t0) / 1000);
  clearInterval(IV.timer); IV.running = false; ivStopAudio();
  const r = await act("interview_score", IV.chat.filter((m) => !m.pending), IV.pid, $("#ivCode").value, elapsed);
  box.innerHTML = mdLite(r || "Couldn't produce a scorecard — check your AI engine in Setup.");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function ivQuit() {
  clearInterval(IV.timer); IV.running = false; IV.pid = null; IV.chat = [];
  stopSpeaking(); if (VOICE.recording) { VOICE.recording = false; act("voice_stop"); setMic("idle"); }
  $("#ivLive").classList.add("hidden"); $("#ivSetup").classList.remove("hidden");
}

/* ---------- company prep ---------- */
const PERIOD_LABELS = { "thirty-days": "30 days", "three-months": "3 months", "six-months": "6 months", "all": "All time" };
const periodLabel = (k) => PERIOD_LABELS[k] || String(k || "").replace(/-/g, " ");
let CO = { init: false, slug: null, period: "all", name: "", companies: [], last: null,
  targets: [], byslug: {}, featured: [],
  filter: { diff: "all", unsolved: false, inapp: false, saved: false, topic: "all", q: "", sort: "freq" } };
async function renderCompanies() {
  if (CO.init) return;
  CO.init = true;
  if (!api()) { $("#coFeatured").innerHTML = '<span class="muted">Open GitKosh to load company question lists.</span>'; return; }
  const data = await act("list_companies");
  if (!data) { CO.init = false; return; }
  CO.companies = data.companies || [];
  CO.featured = data.featured || [];
  CO.byslug = Object.fromEntries(CO.companies.map((c) => [c.slug, c]));
  renderSingleFeatured();
  buildCompanyOptions("");
  $("#coSelect").addEventListener("change", () => selectCompany($("#coSelect").value));
  $("#coSearch").addEventListener("input", () => buildCompanyOptions($("#coSearch").value));
  $("#coSavedList").addEventListener("click", loadSaved);
  // ---- target sheet picker ----
  CO.targets = (await act("get_targets") || []).map((t) => t.slug);
  $("#coTargetAdd").innerHTML = `<option value="">+ add a company…</option>` +
    CO.companies.map((c) => `<option value="${esc(c.slug)}">${esc(c.name)}${c.featured ? " ★" : ""}</option>`).join("");
  $("#coTargetAdd").addEventListener("change", (e) => { if (e.target.value) { toggleTarget(e.target.value, true); e.target.value = ""; } });
  $("#coBuildTargets").addEventListener("click", buildTargets);
  renderTargetPicker();
  $("#coPeriod").innerHTML = (data.periods || []).map((p) =>
    `<button data-k="${esc(p.key)}" class="${p.key === "all" ? "on" : ""}">${esc(p.label)}</button>`).join("");
  $$("#coPeriod button").forEach((b) => b.addEventListener("click", () => {
    CO.period = b.dataset.k; $$("#coPeriod button").forEach((x) => x.classList.toggle("on", x === b));
    if (CO.slug === "__targets") buildTargets();
    else if (CO.slug && CO.slug !== "__saved") loadCompany();
  }));
  // ---- result toolbar (client-side filter/sort, no refetch) ----
  $$("#coDiff button").forEach((b) => b.addEventListener("click", () => {
    CO.filter.diff = b.dataset.d; $$("#coDiff button").forEach((x) => x.classList.toggle("on", x === b)); renderTable();
  }));
  $("#coUnsolved").addEventListener("change", (e) => { CO.filter.unsolved = e.target.checked; renderTable(); });
  $("#coInApp").addEventListener("change", (e) => { CO.filter.inapp = e.target.checked; renderTable(); });
  $("#coSavedOnly").addEventListener("change", (e) => { CO.filter.saved = e.target.checked; renderTable(); });
  $("#coTopic").addEventListener("change", (e) => { CO.filter.topic = e.target.value; renderTable(); });
  $("#coQ").addEventListener("input", (e) => { CO.filter.q = e.target.value; renderTable(); });
  $("#coSort").addEventListener("change", (e) => { CO.filter.sort = e.target.value; renderTable(); });
  $("#coPracticeNext").addEventListener("click", coPracticeNext);
  $("#coInterview").addEventListener("click", coInterview);
  $("#coCopy").addEventListener("click", coCopy);
  $("#coMakePlan").addEventListener("click", () => $("#coPlanBar").classList.toggle("hidden"));
  $("#planGenerate").addEventListener("click", coGeneratePlan);
}
async function coGeneratePlan() {
  if (!CO.last || !CO.slug) { toast("Pick a company first."); return; }
  const weeks = +$("#planWeeks").value, perDay = +$("#planPerDay").value;
  const incl = $("#planIncludeSolved").checked, weak = $("#planWeakTopics").checked;
  $("#planGenerate").disabled = true;
  const r = await act("build_study_plan", CO.slug, CO.period, weeks, perDay, incl, weak);
  $("#planGenerate").disabled = false;
  if (!r || !r.ok) { toast((r && r.error) || "Couldn't build the plan."); return; }
  $("#coPlanBar").classList.add("hidden");
  toast(`Plan ready — ${r.total} questions over ${r.days.length} days`);
  const navBtn = $$(".nav-item").find((b) => b.dataset.tab === "plan");
  if (navBtn) switchTab("plan", navBtn);
  renderPlan(r);
}
function buildCompanyOptions(filter) {
  const q = (filter || "").toLowerCase().trim();
  const sel = $("#coSelect");
  const list = q ? CO.companies.filter((c) => c.name.toLowerCase().includes(q) || c.slug.includes(q)) : CO.companies;
  sel.innerHTML = `<option value="">Select a company… (${CO.companies.length})</option>` +
    list.slice(0, 400).map((c) => `<option value="${esc(c.slug)}">${esc(c.name)}${c.featured ? " ★" : ""}</option>`).join("");
  if (CO.slug && [...sel.options].some((o) => o.value === CO.slug)) sel.value = CO.slug;
  else if (q && list.length === 1) selectCompany(list[0].slug);
}
let _coSeq = 0;
function selectCompany(slug) {
  if (!slug) return;
  CO.slug = slug;
  CO.filter.sort = "freq"; $("#coSort").value = "freq";  // overlap sort only applies to the target sheet
  $("#coSelect").value = slug;
  $$("#coFeatured .co-chip").forEach((b) => b.classList.toggle("on", b.dataset.slug === slug));
  loadCompany();
}
async function loadCompany() {
  const seq = ++_coSeq;
  $("#coResult").classList.remove("hidden");
  $("#coTableWrap").innerHTML = `<div class="muted">Loading questions…</div>`;
  $("#coSummary").innerHTML = ""; $("#coBars").innerHTML = ""; $("#coProgress").textContent = "";
  const r = await act("company_questions", CO.slug, CO.period);
  if (seq !== _coSeq) return;  // a newer selection superseded this load
  if (!r || !r.ok) { $("#coTableWrap").innerHTML = `<div class="muted">${esc((r && r.error) || "Couldn't load.")}</div>`; return; }
  CO.name = r.name; CO.last = r;
  renderCompanyResult(r);
}
async function loadSaved() {
  const seq = ++_coSeq;
  CO.slug = "__saved";
  $("#coSelect").value = ""; $$("#coFeatured .co-chip").forEach((b) => b.classList.remove("on"));
  $("#coResult").classList.remove("hidden");
  $("#coTableWrap").innerHTML = `<div class="muted">Loading your saved list…</div>`;
  $("#coSummary").innerHTML = ""; $("#coBars").innerHTML = ""; $("#coProgress").textContent = "";
  const r = await act("saved_questions");
  if (seq !== _coSeq) return;
  if (!r || !r.ok) { $("#coTableWrap").innerHTML = `<div class="muted">Couldn't load saved list.</div>`; return; }
  CO.name = r.name; CO.last = r;
  if (!r.total) { $("#coTableWrap").innerHTML = `<div class="co-empty">No saved questions yet. Tap the ☆ star on any question to build your personal interview-prep list across companies.</div>`;
    $("#coTitle").textContent = "My saved list"; $("#coProgress").textContent = "0 saved";
    $("#coPracticeNext").classList.add("hidden"); $("#coInterview").classList.add("hidden"); return; }
  renderCompanyResult(r);
}
// ---- target sheet (placement shortlist across companies) ----
// A short, uncluttered preview of featured companies with a "show all" expander.
const FEAT_PREVIEW = 12;
let _coFeatExpanded = false, _coTgtExpanded = false;
function _chipsHTML(selectedSet, expanded) {
  const list = expanded ? CO.featured : CO.featured.slice(0, FEAT_PREVIEW);
  let html = list.map((s) =>
    `<button class="co-chip ${selectedSet && selectedSet.has(s) ? "on" : ""}" data-slug="${esc(s)}">${esc((CO.byslug[s] || {}).name || s)}</button>`).join("");
  const extra = CO.featured.length - FEAT_PREVIEW;
  if (extra > 0) html += `<button class="co-chip co-more" data-more="1">${expanded ? "Show less" : "+ " + extra + " more"}</button>`;
  return html;
}
function renderSingleFeatured() {
  $("#coFeatured").innerHTML = _chipsHTML(null, _coFeatExpanded);
  $$("#coFeatured .co-chip[data-slug]").forEach((b) => b.addEventListener("click", () => selectCompany(b.dataset.slug)));
  const m = $("#coFeatured .co-more"); if (m) m.addEventListener("click", () => { _coFeatExpanded = !_coFeatExpanded; renderSingleFeatured(); });
}
function renderTargetPicker() {
  const chips = CO.targets.map((s) =>
    `<span class="co-tchip">${esc((CO.byslug[s] || {}).name || s)}<button data-slug="${esc(s)}" title="Remove">×</button></span>`).join("");
  $("#coTargetChips").innerHTML = chips;
  $$("#coTargetChips .co-tchip button").forEach((b) => b.addEventListener("click", () => toggleTarget(b.dataset.slug, false)));
  $("#coTargetCount").textContent = CO.targets.length ? `${CO.targets.length}/8 selected` : "";
  $("#coTargetFeatured").innerHTML = _chipsHTML(new Set(CO.targets), _coTgtExpanded);
  $$("#coTargetFeatured .co-chip[data-slug]").forEach((b) => b.addEventListener("click", () => toggleTarget(b.dataset.slug)));
  const m = $("#coTargetFeatured .co-more"); if (m) m.addEventListener("click", () => { _coTgtExpanded = !_coTgtExpanded; renderTargetPicker(); });
}
async function toggleTarget(slug, forceAdd) {
  if (!slug) return;
  const has = CO.targets.includes(slug);
  if (has && forceAdd) return;
  if (has) CO.targets = CO.targets.filter((s) => s !== slug);
  else {
    if (CO.targets.length >= 8) { toast("Up to 8 target companies — remove one first."); return; }
    CO.targets.push(slug);
  }
  const r = await act("set_targets", CO.targets);
  if (r && r.targets) CO.targets = r.targets;
  renderTargetPicker();
}
async function buildTargets() {
  if (!CO.targets.length) { toast("Add at least one target company."); return; }
  const seq = ++_coSeq;
  CO.slug = "__targets";
  $("#coSelect").value = ""; $$("#coFeatured .co-chip").forEach((b) => b.classList.remove("on"));
  CO.filter.sort = "companies"; $("#coSort").value = "companies";
  $("#coResult").classList.remove("hidden");
  $("#coTableWrap").innerHTML = `<div class="muted">Merging ${CO.targets.length} companies…</div>`;
  $("#coSummary").innerHTML = ""; $("#coBars").innerHTML = ""; $("#coProgress").textContent = "";
  const r = await act("target_questions", CO.period);
  if (seq !== _coSeq) return;
  if (!r || !r.ok) { $("#coTableWrap").innerHTML = `<div class="muted">${esc((r && r.error) || "Couldn't build the sheet.")}</div>`; return; }
  CO.name = r.name; CO.last = r;
  renderCompanyResult(r);
}
function _bar(lbl, cls, done, total) {
  const pct = total ? Math.round((100 * done) / total) : 0;
  return `<div class="co-bar ${cls}"><div class="co-bar-top"><span class="lbl">${lbl}</span><span>${done}/${total}</span></div>
    <div class="co-bar-bg"><div class="co-bar-fill" style="width:0%"></div></div></div>`;
}
function renderCompanyResult(r) {
  const saved = r.company === "__saved", targets = r.company === "__targets";
  $("#coTitle").textContent = saved ? "★ My saved list"
    : targets ? `🎯 Target sheet — ${(r.targets || []).length} companies`
    : `${r.name} — top questions`;
  const pct = r.total ? Math.round((100 * r.solved) / r.total) : 0;
  $("#coProgress").textContent = `${r.solved}/${r.total} solved (${pct}%)`;
  const inAppCount = r.questions.filter((q) => q.in_app).length;
  $("#coSummary").innerHTML =
    (targets ? `<span>Across: <b>${esc((r.targets || []).join(", "))}</b></span>`
             : saved ? `<span><b>Your bookmarked questions</b></span>`
             : `<span>Window: <b>${esc(periodLabel(r.period))}</b></span>`) +
    `<span><b>${r.total}</b> unique questions</span>` +
    `<span><b>${inAppCount}</b> solvable in-app</span>` +
    `<span><b>${r.questions.filter((q) => q.bookmarked).length}</b> saved</span>`;
  const sd = r.solved_by_diff || { Easy: 0, Medium: 0, Hard: 0 };
  $("#coBars").innerHTML =
    _bar("Overall", "tot", r.solved, r.total) +
    _bar("Easy", "easy", sd.Easy || 0, r.difficulty.Easy || 0) +
    _bar("Medium", "med", sd.Medium || 0, r.difficulty.Medium || 0) +
    _bar("Hard", "hard", sd.Hard || 0, r.difficulty.Hard || 0);
  // animate bar fills
  requestAnimationFrame(() => $$("#coBars .co-bar").forEach((bar) => {
    const top = bar.querySelector(".co-bar-top span:last-child").textContent.split("/");
    const tot = +top[1] || 0, done = +top[0] || 0;
    bar.querySelector(".co-bar-fill").style.width = (tot ? (100 * done / tot) : 0) + "%";
  }));
  buildTopicOptions(r);
  renderTable();
}
// Populate the topic filter from the current dataset (sorted by frequency, with counts).
function buildTopicOptions(r) {
  const counts = {};
  for (const q of r.questions) for (const t of (q.topics || [])) counts[t] = (counts[t] || 0) + 1;
  const topics = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
  if (!topics.includes(CO.filter.topic)) CO.filter.topic = "all";  // reset if no longer present
  const sel = $("#coTopic");
  sel.innerHTML = `<option value="all">All topics (${topics.length})</option>` +
    topics.map((t) => `<option value="${esc(t)}">${esc(t)} (${counts[t]})</option>`).join("");
  sel.value = CO.filter.topic;
}
function applyFilters() {
  const f = CO.filter, q = (f.q || "").toLowerCase().trim();
  let list = (CO.last.questions || []).slice();
  if (f.diff !== "all") list = list.filter((x) => x.difficulty === f.diff);
  if (f.unsolved) list = list.filter((x) => !x.solved);
  if (f.inapp) list = list.filter((x) => x.in_app);
  if (f.saved) list = list.filter((x) => x.bookmarked);
  if (f.topic !== "all") list = list.filter((x) => (x.topics || []).includes(f.topic));
  if (q) list = list.filter((x) => (x.title || "").toLowerCase().includes(q));
  const DORD = { Easy: 0, Medium: 1, Hard: 2 };
  if (f.sort === "diff") list.sort((a, b) => (DORD[a.difficulty] ?? 9) - (DORD[b.difficulty] ?? 9) || (b.frequency || 0) - (a.frequency || 0));
  else if (f.sort === "acc") list.sort((a, b) => (parseFloat(a.acceptance) || 0) - (parseFloat(b.acceptance) || 0));
  else if (f.sort === "title") list.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
  else if (f.sort === "companies") list.sort((a, b) => (b.company_count || 0) - (a.company_count || 0) || (b.frequency || 0) - (a.frequency || 0));
  else list.sort((a, b) => (b.frequency || 0) - (a.frequency || 0));
  return list;
}
function renderTable() {
  if (!CO.last) return;
  const r = CO.last, list = applyFilters();
  $("#coCount").textContent = `Showing ${list.length} of ${r.total}`;
  const next = r.questions.find((q) => q.in_app && !q.solved);
  $("#coPracticeNext").classList.toggle("hidden", !next);
  if (next) $("#coPracticeNext").dataset.pid = next.slug;
  $("#coInterview").classList.toggle("hidden", !r.questions.some((q) => q.in_app));
  if (!list.length) {
    $("#coTableWrap").innerHTML = `<div class="co-empty">No questions match these filters.<br><button class="btn sm" id="coClear" style="margin-top:10px">Clear filters</button></div>`;
    $("#coClear").addEventListener("click", coClearFilters);
    return;
  }
  const maxFreq = Math.max(1, ...list.map((q) => q.frequency || 0));
  const rows = list.map((q, i) => {
    const dc = q.difficulty === "Easy" ? "easy" : q.difficulty === "Hard" ? "hard" : "med";
    const bar = Math.max(3, Math.round((46 * (q.frequency || 0)) / maxFreq));
    const status = q.solved ? `<span class="solved">✓ Solved</span>`
      : q.in_app ? `<a href="#" class="co-open" data-pid="${esc(q.slug)}">Solve in app</a>`
      : `<a href="${esc(q.url)}" target="_blank" rel="noopener">LeetCode ↗</a>`;
    return `<tr class="${q.solved ? "done" : ""}">
      <td>${i + 1}</td>
      <td><button class="co-star ${q.bookmarked ? "on" : ""}" data-slug="${esc(q.slug)}" title="Save to my list">${q.bookmarked ? "★" : "☆"}</button></td>
      <td><a href="${esc(q.url)}" target="_blank" rel="noopener">${esc(q.title)}</a>${q.in_app ? ' <span class="co-dchip" style="background:rgba(124,92,252,.16);color:#b9a7ff">in-app</span>' : ""} ${q.companies && q.companies.length ? `<span class="co-cocount" title="${esc(q.companies.join(', '))}">${q.company_count} cos</span>` : ""}${q.companies && q.companies.length ? `<span class="co-askedat">${esc(q.companies.join(", "))}</span>` : ""}${q.topics && q.topics.length ? `<span class="co-topics">${q.topics.map((t) => `<span class="co-topic ${t === CO.filter.topic ? "on" : ""}" data-topic="${esc(t)}">${esc(t)}</span>`).join("")}</span>` : ""}</td>
      <td><span class="co-dchip ${dc}">${esc(q.difficulty || "")}</span></td>
      <td class="freq">${(q.frequency || 0).toFixed(0)}%<span class="co-freqbar" style="width:${bar}px"></span></td>
      <td class="acc">${esc(q.acceptance || "")}</td>
      <td class="co-status">${status}</td></tr>`;
  }).join("");
  $("#coTableWrap").innerHTML = `<div class="co-tablewrap"><table class="co-table">
    <thead><tr><th>#</th><th></th><th>Problem</th><th>Diff</th><th>Freq</th><th>Acc</th><th>Status</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
  $$("#coTableWrap .co-open").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); openInApp(a.dataset.pid); }));
  $$("#coTableWrap .co-star").forEach((s) => s.addEventListener("click", () => coToggleStar(s.dataset.slug)));
  // click a topic chip to filter by it (toggle off if already active)
  $$("#coTableWrap .co-topic").forEach((c) => c.addEventListener("click", () => {
    CO.filter.topic = (CO.filter.topic === c.dataset.topic) ? "all" : c.dataset.topic;
    $("#coTopic").value = CO.filter.topic;
    renderTable();
  }));
}
async function coToggleStar(slug) {
  const q = (CO.last.questions || []).find((x) => x.slug === slug);
  if (!q) return;
  const special = CO.slug === "__saved" || CO.slug === "__targets";
  const res = await act("toggle_bookmark", {
    slug: q.slug, title: q.title, url: q.url, difficulty: q.difficulty,
    frequency: q.frequency, acceptance: q.acceptance,
    company: special ? (q.company || "") : CO.slug,
    company_name: special ? (q.company_name || (q.companies || []).join(", ")) : CO.name,
  });
  if (!res) return;
  q.bookmarked = !!res.bookmarked;
  // If we're viewing the saved list and just un-saved one, drop it from the view.
  if (CO.slug === "__saved" && !q.bookmarked) {
    CO.last.questions = CO.last.questions.filter((x) => x.slug !== slug);
    CO.last.total = CO.last.questions.length;
  }
  renderTable();
  // refresh the "saved" count chip (last span in the summary row)
  const savedCount = CO.last.questions.filter((x) => x.bookmarked).length;
  const spans = $("#coSummary").querySelectorAll("span");
  const chip = spans[spans.length - 1];
  if (chip) chip.innerHTML = `<b>${savedCount}</b> saved`;
}
function coClearFilters() {
  CO.filter = { diff: "all", unsolved: false, inapp: false, saved: false, topic: "all", q: "", sort: "freq" };
  $$("#coDiff button").forEach((b) => b.classList.toggle("on", b.dataset.d === "all"));
  $("#coUnsolved").checked = false; $("#coInApp").checked = false; $("#coSavedOnly").checked = false;
  $("#coQ").value = ""; $("#coSort").value = "freq"; $("#coTopic").value = "all";
  renderTable();
}
function coCopy() {
  const list = applyFilters();
  if (!list.length) { toast("Nothing to copy with these filters."); return; }
  const title = CO.slug === "__saved" ? "My saved list"
    : CO.slug === "__targets" ? `Target sheet — ${((CO.last && CO.last.targets) || []).join(", ")}`
    : `${CO.name} — interview prep`;
  const lines = [`# ${title}`, ""];
  for (const q of list) {
    const box = q.solved ? "[x]" : "[ ]";
    const at = q.companies && q.companies.length ? ` · asked at: ${q.companies.join(", ")}` : "";
    lines.push(`- ${box} [${q.title}](${q.url}) — ${q.difficulty || "?"} · ${(q.frequency || 0).toFixed(0)}% freq${at}`);
  }
  navigator.clipboard?.writeText(lines.join("\n"));
  toast(`Copied ${list.length} questions as a checklist`);
}
// Switch to the Learn tab and load a problem by slug (polls until options are ready).
function openInApp(slug) {
  const navBtn = $$(".nav-item").find((b) => b.dataset.tab === "learn");
  if (navBtn) switchTab("learn", navBtn);
  let tries = 0;
  const t = setInterval(() => {
    const sel = $("#probSelect");
    if (sel && [...sel.options].some((o) => o.value === slug)) { sel.value = slug; loadProblem(); clearInterval(t); }
    else if (++tries > 30) clearInterval(t);
  }, 100);
}
function coPracticeNext() { const pid = $("#coPracticeNext").dataset.pid; if (pid) openInApp(pid); }
function coInterview() {
  const inApp = ((CO.last && CO.last.questions) || []).filter((q) => q.in_app);
  if (!inApp.length) return;
  const pick = (inApp.find((q) => !q.solved) || inApp[0]).slug;
  const navBtn = $$(".nav-item").find((b) => b.dataset.tab === "interview");
  if (navBtn) switchTab("interview", navBtn);
  let tries = 0;
  const t = setInterval(() => {
    if (IV.init) {
      clearInterval(t);
      const sel = $("#ivProblem");
      if (sel && [...sel.options].some((o) => o.value === pick)) sel.value = pick;
      startInterview(pick);
    } else if (++tries > 30) clearInterval(t);
  }, 100);
}

/* ---------- auto study plan ---------- */
let _planWired = false;
async function renderPlan(planArg) {
  if (!_planWired) {
    _planWired = true;
    $("#planCopy").addEventListener("click", planCopy);
    $("#planDelete").addEventListener("click", planDelete);
  }
  const plan = planArg || (api() ? await act("get_study_plan") : null);
  if (!plan || !plan.ok) {
    $("#planEmpty").classList.remove("hidden"); $("#planView").classList.add("hidden");
    return;
  }
  window._plan = plan;
  $("#planEmpty").classList.add("hidden"); $("#planView").classList.remove("hidden");
  const pr = plan.progress || { done: 0, total: 0, pct: 0 };
  $("#planName").textContent = `${plan.name} — study plan`;
  $("#planProgress").textContent = `${pr.done}/${pr.total} done (${pr.pct}%)`;
  $("#planMeta").innerHTML =
    `<span><b>${plan.weeks}</b> weeks · <b>${plan.per_day}</b>/day</span>` +
    `<span>Window: <b>${esc(periodLabel(plan.period))}</b></span>` +
    `<span>Started <b>${esc((plan.created || "").slice(0, 10))}</b></span>` +
    (plan.include_solved ? `<span>incl. solved</span>` : "") +
    (plan.topic_weighted ? `<span>⚡ weak-topic focus</span>` : "");
  if (plan.topic_weighted && (plan.weak_topics || []).length) {
    $("#planMeta").innerHTML +=
      `<span style="flex-basis:100%">Emphasizing: ${plan.weak_topics.map((t) =>
        `<span class="co-topic">${esc(t.topic)} <b>${t.pct}%</b></span>`).join(" ")}</span>`;
  }
  requestAnimationFrame(() => { $("#planBar").style.width = pr.pct + "%"; });
  // today's focus
  const today = plan.days.find((d) => d.is_today);
  $("#planTodayCard").classList.remove("hidden");
  if (today) {
    $("#planTodayBadge").textContent = `${today.done}/${today.total} done`;
    $("#planToday").innerHTML = today.items.length
      ? today.items.map(planItemRow).join("") : `<div class="muted">Rest day — nothing scheduled 🎉</div>`;
  } else {
    const upcoming = plan.days.find((d) => !d.is_past);
    $("#planTodayBadge").textContent = "";
    $("#planToday").innerHTML = upcoming
      ? `<div class="muted">Nothing due today. Next study day: <b>${esc(upcoming.date)}</b>.</div>`
      : `<div class="muted">Plan complete — nice work! 🎉</div>`;
  }
  // full schedule grouped into weeks of 7
  const weeks = [];
  for (let i = 0; i < plan.days.length; i += 7) weeks.push(plan.days.slice(i, i + 7));
  $("#planSchedule").innerHTML = weeks.map((wk, wi) =>
    `<div class="plan-week"><div class="plan-week-h">Week ${wi + 1} · ${esc(wk[0].date)} – ${esc(wk[wk.length - 1].date)}</div>${wk.map(planDayBlock).join("")}</div>`).join("");
  $$("#page-plan .co-open").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); openInApp(a.dataset.pid); }));
}
function planItemRow(it) {
  const dc = it.difficulty === "Easy" ? "easy" : it.difficulty === "Hard" ? "hard" : "med";
  const action = (!it.solved && it.in_app) ? `<a href="#" class="co-open act" data-pid="${esc(it.slug)}">Solve in app</a>` : "";
  return `<div class="plan-item ${it.solved ? "solved" : ""}">
    <span class="chk">${it.solved ? "✓" : "○"}</span>
    <span class="co-dchip ${dc}">${esc(it.difficulty || "")}</span>
    <span class="t"><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a></span>
    <span class="act">${action}</span></div>`;
}
function planDayBlock(d) {
  const complete = d.total > 0 && d.done === d.total;
  const cls = `plan-day ${d.is_today ? "today" : ""} ${d.is_past && !complete ? "past incomplete" : ""} ${complete ? "done-day" : ""}`;
  return `<div class="${cls}">
    <div class="plan-day-h"><span class="date">${esc(d.weekday)} ${esc(d.date.slice(5))}</span>${d.is_today ? '<span class="tag">Today</span>' : ""}<span class="cnt">${d.done}/${d.total}</span></div>
    ${d.items.map(planItemRow).join("")}</div>`;
}
function planCopy() {
  const plan = window._plan; if (!plan) return;
  const lines = [`# ${plan.name} — study plan (${plan.weeks} weeks, ${plan.per_day}/day)`, ""];
  for (const d of plan.days) {
    lines.push(`## ${d.weekday} ${d.date}`);
    for (const it of d.items) lines.push(`- ${it.solved ? "[x]" : "[ ]"} [${it.title}](${it.url}) — ${it.difficulty || "?"}`);
    lines.push("");
  }
  navigator.clipboard?.writeText(lines.join("\n"));
  toast("Copied study plan as a checklist");
}
async function planDelete() {
  await act("clear_study_plan");
  window._plan = null;
  toast("Study plan deleted");
  renderPlan();
}

function renderPatterns(pats) {
  window._pats = pats || [];
  $("#patterns").innerHTML = window._pats.map((p, i) =>
    `<div class="pat" data-i="${i}"><div class="pn">${esc(p.name)}</div><div class="pw">${esc(p.when)}</div></div>`).join("");
  $$("#patterns .pat").forEach((el) => el.addEventListener("click", () => showPattern(+el.dataset.i)));
}
function showPattern(i) {
  const p = window._pats[i]; const d = $("#patternDetail");
  d.classList.remove("hidden");
  d.innerHTML = `<h3>${esc(p.name)}</h3><div><b>When:</b> ${esc(p.when)}</div>
    <div style="margin-top:6px"><b>Idea:</b> ${esc(p.idea)}</div>
    <div class="ex">${(p.examples || []).map((e) => `<span class="chip">${esc(e)}</span>`).join("")}</div>
    <div class="row" style="margin-top:12px">
      <button class="btn sm btn-accent" id="drillPat">🧩 Practice this pattern</button>
      <button class="btn sm" id="askPat">Ask the tutor about this</button>
    </div>
    <div id="patDrill"></div>`;
  $("#askPat").addEventListener("click", () => {
    $("#chat").scrollIntoView({ behavior: "smooth" });
    sendChat(`Explain the ${p.name} pattern with a simple example and when to use it.`);
  });
  $("#drillPat").addEventListener("click", () => drillPattern(p.name));
}
async function drillPattern(name) {
  const box = $("#patDrill");
  if (!api()) { toast("Pattern practice runs inside GitKosh."); return; }
  box.innerHTML = `<div class="muted" style="margin-top:10px">Finding problems…</div>`;
  const r = await act("pattern_problems", name);
  if (!r || !r.ok || !r.total) { box.innerHTML = `<div class="muted" style="margin-top:10px">${esc((r && r.error) || "No in-app problems for this pattern yet.")}</div>`; return; }
  const rows = r.problems.map((q) => {
    const dc = q.difficulty === "Easy" ? "easy" : q.difficulty === "Hard" ? "hard" : "med";
    const status = q.solved ? `<span class="solved">✓</span>` : "";
    return `<div class="drill-item">
      <span class="co-dchip ${dc}">${esc(q.difficulty || "")}</span>
      <a href="#" class="drill-open" data-pid="${esc(q.slug)}">${esc(q.title)}</a>
      ${q.tested ? '<span class="co-dchip" style="background:rgba(124,92,252,.16);color:#b9a7ff">auto-tested</span>' : ""}
      <span class="drill-status">${status}</span></div>`;
  }).join("");
  box.innerHTML = `<div class="drill-head">${r.solved}/${r.total} solved · all open in the in-app editor</div>
    <div class="drill-list">${rows}</div>`;
  $$("#patDrill .drill-open").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); openInApp(a.dataset.pid); }));
}

/* sorting visualizer */
let vizArr = [], vizBusy = false, vizStop = false;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
class VizStopped extends Error {}
async function vizTick(hi) { vizDraw(hi); await sleep(VIZ_DELAY); if (vizStop) throw new VizStopped(); }
let VIZ_DELAY = 7;
function vizInit() {
  if (vizBusy) return;  // don't reshuffle mid-sort
  vizArr = Array.from({ length: 46 }, () => 0.08 + Math.random() * 0.9);
  vizDraw();
}
function vizDraw(hi = []) {
  const c = $("#vizCanvas"); if (!c) return;
  const W = c.width = c.clientWidth || 800, H = c.height = 230;
  const ctx = c.getContext("2d"); ctx.clearRect(0, 0, W, H);
  const n = vizArr.length, bw = W / n;
  vizArr.forEach((v, i) => {
    const h = v * (H - 16) + 6;
    ctx.fillStyle = hi.includes(i) ? "#fbbf24" : "#7c5cfc";
    ctx.fillRect(i * bw + 1, H - h, Math.max(bw - 2, 1), h);
  });
}
async function vizPlay() {
  if (vizBusy) return;
  vizBusy = true; vizStop = false;
  $("#vizPlay").textContent = "Sorting…"; $("#vizPlay").disabled = true;
  $("#vizStop").disabled = false; $("#vizShuffle").disabled = true; $("#vizAlgo").disabled = true;
  const f = { bubble: bubbleSort, insertion: insertionSort, selection: selectionSort, quick: () => quickSort(0, vizArr.length - 1) };
  try { await f[$("#vizAlgo").value](); } catch (e) { if (!(e instanceof VizStopped)) throw e; }
  vizDraw(); vizBusy = false;
  $("#vizPlay").textContent = "▶ Play"; $("#vizPlay").disabled = false;
  $("#vizStop").disabled = true; $("#vizShuffle").disabled = false; $("#vizAlgo").disabled = false;
}
function vizHalt() { vizStop = true; }
async function bubbleSort() { const a = vizArr, n = a.length; for (let i = 0; i < n; i++) for (let j = 0; j < n - i - 1; j++) { await vizTick([j, j + 1]); if (a[j] > a[j + 1]) [a[j], a[j + 1]] = [a[j + 1], a[j]]; } }
async function insertionSort() { const a = vizArr, n = a.length; for (let i = 1; i < n; i++) { const k = a[i]; let j = i - 1; while (j >= 0 && a[j] > k) { a[j + 1] = a[j]; j--; await vizTick([j + 1, i]); } a[j + 1] = k; } }
async function selectionSort() { const a = vizArr, n = a.length; for (let i = 0; i < n; i++) { let m = i; for (let j = i + 1; j < n; j++) { await vizTick([m, j]); if (a[j] < a[m]) m = j; }[a[i], a[m]] = [a[m], a[i]]; } }
async function quickSort(lo, hi) { if (lo >= hi) return; const a = vizArr, p = a[hi]; let i = lo; for (let j = lo; j < hi; j++) { await vizTick([j, hi]); if (a[j] < p) { [a[i], a[j]] = [a[j], a[i]]; i++; } }[a[i], a[hi]] = [a[hi], a[i]]; await quickSort(lo, i - 1); await quickSort(i + 1, hi); }
async function runCode() {
  $("#reviewOut").classList.add("hidden");
  const out = $("#runOut"); out.textContent = "Running…"; $("#runStatus").textContent = "";
  if (!api()) { toast("Run works inside the app."); out.textContent = ""; return; }
  const r = await act("run_code", $("#editor").value, $("#stdin") ? $("#stdin").value : "", curLang());
  if (!r) { out.textContent = ""; toast("Run failed — try again."); return; }
  out.textContent = (r.stdout || "") + (r.stderr ? "\n" + r.stderr : "");
  $("#runStatus").textContent = (r.ok ? "✓ ran" : "✗ error") + `  ${r.ms || 0}ms`;
  $("#runStatus").className = "runstatus " + (r.ok ? "ok" : "bad");
}
async function runTests() {
  $("#reviewOut").classList.add("hidden");
  const out = $("#runOut"); out.textContent = "Running tests…"; $("#runStatus").textContent = "";
  if (!api()) { toast("Tests run inside the app."); out.textContent = ""; return; }
  const r = await act("run_tests", $("#editor").value, $("#probSelect").value);
  if (!r) { out.textContent = ""; toast("Couldn't run tests — try again."); return; }
  out.textContent = r.output || "";
  $("#runStatus").textContent = `${r.passed}/${r.total} passed`;
  $("#runStatus").className = "runstatus " + (r.ok ? "ok" : "bad");
}
function editorTab(e) {
  if (e.key === "Tab") {
    e.preventDefault();
    const t = e.target, s = t.selectionStart, en = t.selectionEnd;
    t.value = t.value.slice(0, s) + "    " + t.value.slice(en);
    t.selectionStart = t.selectionEnd = s + 4;
    syncHL();
  }
}

/* ---------- first-run welcome ---------- */
let welcomeHandled = false;
async function maybeWelcome() {
  if (welcomeHandled) return;          // boot() can fire twice (DOMContentLoaded + pywebviewready)
  welcomeHandled = true;
  // Durable flag lives in the Python config (WKWebView file:// localStorage isn't
  // persisted, which made the prompt reappear every launch).
  let seen = false;
  if (api()) { try { seen = await act("get_onboarded"); } catch (e) {} }
  else { try { seen = !!localStorage.getItem("gk_welcomed"); } catch (e) { seen = true; } }
  if (seen) return;
  const m = $("#welcome"); if (!m) return;
  m.classList.remove("hidden");
  const close = (provider) => {
    if (api()) act("set_onboarded"); else { try { localStorage.setItem("gk_welcomed", "1"); } catch (e) {} }
    m.classList.add("hidden");
    const btn = $(`#providerSeg button[data-v="${provider}"]`);
    if (btn) {
      $$("#providerSeg button").forEach((x) => x.classList.toggle("on", x === btn));
      updateKeyField(provider);
      act("set_provider", provider);
    }
    switchTabByName("setup");
    if (provider === "ollama") ensureOllama();
  };
  $("#welcomeGotIt").addEventListener("click", () => close("ollama"));
  $("#welcomeSkip").addEventListener("click", () => close("gemini"));
}
function switchTabByName(name) {
  const item = $(`.nav-item[data-tab="${name}"]`);
  if (item) switchTab(name, item);
}

/* ---------- boot ---------- */
function boot() {
  renderSetup();
  const t = new URLSearchParams(location.search).get("tab");
  const item = (t && $(`.nav-item[data-tab="${t}"]`)) || $(".nav-item.active");
  if (item) { if (t) switchTab(t, item); else moveNavPill(item); }
  maybeWelcome();
  reviewNudge();
}
// On launch, nudge the user if spaced-repetition reviews are due.
let _reviewNudged = false;
async function reviewNudge() {
  if (_reviewNudged || !api()) return;
  _reviewNudged = true;
  const st = await act("review_status");
  const b = $("#reviewBanner");
  if (!st || !st.due || !b) return;
  $("#reviewBannerText").textContent =
    `🔁 ${st.due} problem${st.due > 1 ? "s" : ""} due for review` +
    (st.review_streak ? ` · keep your ${st.review_streak}-day review streak alive` : "");
  b.classList.remove("hidden");
  $("#reviewBannerGo").onclick = () => {
    b.classList.add("hidden");
    const nav = $$(".nav-item").find((x) => x.dataset.tab === "practice");
    if (nav) switchTab("practice", nav);
    startQuiz();  // self-fetches practice data if needed (no timer race)
  };
  $("#reviewBannerX").onclick = () => b.classList.add("hidden");
}
// Always boot once the DOM is parsed — pywebview can inject its bridge before the
// document finishes loading, so guarding on `window.pywebview` alone can run boot()
// too early (nav not built yet → ?tab deep-link silently ignored). readyState is the
// reliable signal. pywebviewready re-runs boot to refresh data once the bridge is live.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
window.addEventListener("pywebviewready", boot);
