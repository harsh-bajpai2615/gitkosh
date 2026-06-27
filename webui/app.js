"use strict";
const api = () => (window.pywebview && window.pywebview.api) || null;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Sample data so the UI previews fully in a plain browser (no Python bridge).
const SAMPLE = {
  version: "v0.13.0",
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
async function getState() { const a = api(); return a ? await a.get_state() : SAMPLE; }
async function getInsights() { const a = api(); return a ? await a.get_insights() : SAMPLE.insights; }
async function getContests() { const a = api(); return a ? await a.get_contests() : SAMPLE.contests; }
async function getCard() { const a = api(); return a ? await a.get_card() : SAMPLE.card; }

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
}

function curProvider() { const o = $("#providerSeg button.on"); return o ? o.dataset.v : "ollama"; }
function updateKeyField(provider, key) {
  const show = provider === "gemini" || provider === "groq";
  $("#keyWrap").classList.toggle("hidden", !show);
  $("#keyHint").classList.toggle("hidden", !show);
  if (key !== undefined && $("#apiKey")) $("#apiKey").value = key || "";
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
  $("#topics").innerHTML = (d.topics || []).map((t) => `<span class="chip">${t}</span>`).join("");
  $("#resume").innerHTML = (d.resume || []).map((b) => `<li>${b.replace(/^[-•]\s*/, "")}</li>`).join("");
  const g = api() ? await act("get_gamify") : GAMIFY_SAMPLE;
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
  $("#contestList").innerHTML = (d.upcoming || []).map((c) =>
    `<div class="contest"><span class="cbadge ${c.platform === "codeforces" ? "cf" : "lc"}">${LABELS[c.platform] || c.platform}</span>
     <span class="nm">${c.name}</span><span class="when">${c.when} · ${c.dur}</span>
     <a href="${c.url}" target="_blank">open</a></div>`).join("") ||
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
$("#btnGithub").addEventListener("click", () => act("github_login").then(renderSetup));
$("#btnSync").addEventListener("click", () => { showProg(); act("run_sync", false); });
$("#btnReset").addEventListener("click", () => { showProg(); act("run_sync", true); });
$("#btnPublish").addEventListener("click", () => act("publish_site").then((u) => u && toast("Published: " + u)));
$("#btnPost").addEventListener("click", async () => { $("#postBox").value = "Generating…";
  const r = await act("generate_post"); if (r) $("#postBox").value = r.post; });
$("#btnCopyEmbed").addEventListener("click", async () => {
  const md = await act("get_embed"); navigator.clipboard?.writeText(md || ""); toast("Embed code copied"); });
$("#btnRefreshCard").addEventListener("click", renderCard);
$("#btnRefreshContests").addEventListener("click", renderContests);
$("#btnCopyResume").addEventListener("click", () => {
  navigator.clipboard?.writeText([...$$("#resume li")].map((l) => "- " + l.textContent).join("\n")); toast("Copied"); });
$$("#providerSeg button").forEach((b) => b.addEventListener("click", () => {
  $$("#providerSeg button").forEach((x) => x.classList.toggle("on", x === b));
  updateKeyField(b.dataset.v);
  act("set_provider", b.dataset.v); }));
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
async function getPractice() { const a = api(); return a ? await a.get_practice() : SAMPLE_PRACTICE; }

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

function mdLite(t) {
  let s = esc(t);
  s = s.replace(/```([\s\S]*?)```/g, (m, c) => `<pre>${c.trim()}</pre>`);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  return s;
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
  chat.push({ role: "bot", content: "…" }); renderChat();
  let reply;
  if (api()) reply = await act("tutor_chat", chat.filter((m) => m.content !== "…"));
  else reply = "(Preview) Open GitKosh with an AI provider to chat. Tip: identify the pattern, find the invariant, then improve on brute force.";
  chat[chat.length - 1] = { role: "bot", content: reply || "No reply." }; renderChat();
}
async function renderLearn() {
  if (!learnInit) {
    learnInit = true;
    if (!chat.length) { chat.push({ role: "bot", content: "Hi! I'm your DSA tutor 👋 Ask me to explain a concept, give a hint, or review your approach — or tap a chip below." }); renderChat(); }
    $("#probSelect").addEventListener("change", loadProblem);
    $("#chatSend").addEventListener("click", () => sendChat());
    $("#chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
    $$("#tutorChips .chip").forEach((c) => c.addEventListener("click", () => sendChat(c.dataset.q)));
    $("#runBtn").addEventListener("click", runCode);
    $("#testBtn").addEventListener("click", runTests);
    $("#editor").addEventListener("keydown", editorTab);
    $("#vizPlay").addEventListener("click", vizPlay);
    $("#vizShuffle").addEventListener("click", vizInit);
    vizInit();
  }
  if (!window._learnReal) {  // (re)load once the Python bridge is actually available
    const live = !!api();
    const probs = live ? await act("list_problems") : SAMPLE_PROBLEMS;
    $("#probSelect").innerHTML = `<option value="__scratch">Scratchpad (free Python)</option>` +
      (probs || []).map((p) => `<option value="${p.id}">${p.title} · ${p.difficulty}</option>`).join("");
    if (probs && probs.length) $("#probSelect").value = probs[0].id;
    renderPatterns(live ? await act("get_patterns") : PATTERNS_SAMPLE);
    if (live) window._learnReal = true;
    await loadProblem();
  }
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
let vizArr = [], vizBusy = false;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function vizInit() {
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
  vizBusy = true; $("#vizPlay").textContent = "Sorting…";
  const f = { bubble: bubbleSort, insertion: insertionSort, selection: selectionSort, quick: () => quickSort(0, vizArr.length - 1) };
  await f[$("#vizAlgo").value]();
  vizDraw(); vizBusy = false; $("#vizPlay").textContent = "▶ Play";
}
async function bubbleSort() { const a = vizArr, n = a.length; for (let i = 0; i < n; i++) for (let j = 0; j < n - i - 1; j++) { vizDraw([j, j + 1]); await sleep(6); if (a[j] > a[j + 1]) [a[j], a[j + 1]] = [a[j + 1], a[j]]; } }
async function insertionSort() { const a = vizArr, n = a.length; for (let i = 1; i < n; i++) { const k = a[i]; let j = i - 1; while (j >= 0 && a[j] > k) { a[j + 1] = a[j]; j--; vizDraw([j + 1, i]); await sleep(9); } a[j + 1] = k; } }
async function selectionSort() { const a = vizArr, n = a.length; for (let i = 0; i < n; i++) { let m = i; for (let j = i + 1; j < n; j++) { vizDraw([m, j]); await sleep(4); if (a[j] < a[m]) m = j; }[a[i], a[m]] = [a[m], a[i]]; } }
async function quickSort(lo, hi) { if (lo >= hi) return; const a = vizArr, p = a[hi]; let i = lo; for (let j = lo; j < hi; j++) { vizDraw([j, hi]); await sleep(9); if (a[j] < p) { [a[i], a[j]] = [a[j], a[i]]; i++; } }[a[i], a[hi]] = [a[hi], a[i]]; await quickSort(lo, i - 1); await quickSort(i + 1, hi); }
async function loadProblem() {
  const pid = $("#probSelect").value;
  $("#runOut").textContent = ""; $("#runStatus").textContent = "";
  if (pid === "__scratch") {
    $("#stdinWrap").classList.remove("hidden"); $("#testBtn").style.display = "none";
    $("#probStatement").textContent = "Free Python scratchpad — read input() and print() output, then Run.";
    $("#editor").value = "# Scratchpad — write Python, add input below, then Run\nprint('Hello from GitKosh')\n";
    return;
  }
  $("#stdinWrap").classList.add("hidden"); $("#testBtn").style.display = "";
  const p = api() ? await act("get_problem", pid) : { statement: "(preview) Solve in the app.", starter: "def solve():\n    pass\n" };
  $("#probStatement").textContent = p.statement || "";
  $("#editor").value = p.starter || "";
}
async function runCode() {
  const out = $("#runOut"); out.textContent = "Running…"; $("#runStatus").textContent = "";
  if (!api()) { toast("Run works inside the app."); out.textContent = ""; return; }
  const r = await act("run_code", $("#editor").value, $("#stdin") ? $("#stdin").value : "");
  out.textContent = (r.stdout || "") + (r.stderr ? "\n" + r.stderr : "");
  $("#runStatus").textContent = (r.ok ? "✓ ran" : "✗ error") + `  ${r.ms || 0}ms`;
  $("#runStatus").className = "runstatus " + (r.ok ? "ok" : "bad");
}
async function runTests() {
  const out = $("#runOut"); out.textContent = "Running tests…"; $("#runStatus").textContent = "";
  if (!api()) { toast("Tests run inside the app."); out.textContent = ""; return; }
  const r = await act("run_tests", $("#editor").value, $("#probSelect").value);
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
  }
}

/* ---------- boot ---------- */
function boot() {
  renderSetup();
  const t = new URLSearchParams(location.search).get("tab");
  const item = (t && $(`.nav-item[data-tab="${t}"]`)) || $(".nav-item.active");
  if (item) { if (t) switchTab(t, item); else moveNavPill(item); }
}
if (window.pywebview) boot(); else window.addEventListener("DOMContentLoaded", boot);
window.addEventListener("pywebviewready", boot);
