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
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b === item));
  $$(".page").forEach((p) => p.classList.remove("active"));
  const page = $("#page-" + tab); page.classList.add("active");
  moveNavPill(item);
  if (tab === "insights") renderInsights();
  if (tab === "contests") renderContests();
  if (tab === "showcase") renderCard();
  if (tab === "practice") renderPractice();
  if (tab === "learn") renderLearn();
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
    } else {
      note.className = "provNote warn";
      note.innerHTML = "⚠ Cloud keys work, but replies can be <b>slower</b> and may hit <b>rate limits</b> under heavy use. " +
        "For the smoothest, private experience we recommend <b>Ollama</b> (free, local).";
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
function esc(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }

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

function startQuiz() {
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
  if (api()) reply = await act("tutor_chat", chat.filter((m) => !m.pending));
  else reply = "(Preview) Open GitKosh with an AI engine to chat. Tip: identify the pattern, find the invariant, then improve on brute force.";
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
  const pid = $("#probSelect").value;
  $("#runOut").textContent = ""; $("#runStatus").textContent = "";
  $("#reviewOut").classList.add("hidden"); $("#reviewOut").innerHTML = "";
  if (pid === "__scratch") {
    $("#stdinWrap").classList.remove("hidden"); $("#testBtn").style.display = "none"; $("#reviewBtn").style.display = "none";
    $("#probMeta").innerHTML = "";
    $("#probStatement").textContent = "Free Python scratchpad — read input() and print() output, then Run.";
    setEditor("# Scratchpad — write Python, add input below, then Run\nprint('Hello from GitKosh')\n");
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
function setEditor(v) { $("#editor").value = v; syncHL(); $("#editor").scrollTop = 0; }
let _saveTimer = null;
function saveCodeDebounced() {
  const pid = $("#probSelect").value;
  if (!api() || !pid || pid === "__scratch") return;
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => act("save_code", pid, $("#editor").value), 600);
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
  const r = await act("ai_review", $("#editor").value, pid, reviewAttempts[pid]);
  box.innerHTML = mdLite(r || "Couldn't review — check your AI engine in Setup.");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    <div style="margin-top:12px"><button class="btn sm btn-accent" id="askPat">Ask the tutor about this</button></div>`;
  $("#askPat").addEventListener("click", () => {
    $("#chat").scrollIntoView({ behavior: "smooth" });
    sendChat(`Explain the ${p.name} pattern with a simple example and when to use it.`);
  });
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
  const r = await act("run_code", $("#editor").value, $("#stdin") ? $("#stdin").value : "");
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
