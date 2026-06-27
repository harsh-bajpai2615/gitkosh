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
}

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

/* ---------- boot ---------- */
function boot() {
  renderSetup();
  const t = new URLSearchParams(location.search).get("tab");
  const item = (t && $(`.nav-item[data-tab="${t}"]`)) || $(".nav-item.active");
  if (item) { if (t) switchTab(t, item); else moveNavPill(item); }
}
if (window.pywebview) boot(); else window.addEventListener("DOMContentLoaded", boot);
window.addEventListener("pywebviewready", boot);
