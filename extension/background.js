// Pushes a captured solution to GitHub via the REST/Git Data API (blobs -> tree ->
// commit -> ref), using a Personal Access Token + repo stored in the popup.
const API = "https://api.github.com";
const EXT = {
  python3: "py", python: "py", cpp: "cpp", "c++": "cpp", java: "java", c: "c",
  javascript: "js", typescript: "ts", rust: "rs", golang: "go", go: "go",
  kotlin: "kt", swift: "swift", "c#": "cs", csharp: "cs", ruby: "rb", scala: "scala",
  php: "php", mysql: "sql", dart: "dart", elixir: "ex", erlang: "erl", racket: "rkt",
};

const extFor = (lang) => EXT[(lang || "").toLowerCase()] || "txt";
const dirFor = (qid, slug) => `leetcode/${String(qid).padStart(4, "0")}-${slug}`;
const utf8b64 = (s) => btoa(unescape(encodeURIComponent(s)));

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "push") {
    pushSolution(msg.payload)
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true; // async
  }
});

function getCfg() {
  return new Promise((res) => chrome.storage.sync.get(["token", "repo"], res));
}

async function gh(token, method, path, body) {
  const r = await fetch(API + path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok && r.status !== 404 && r.status !== 409) {
    throw new Error(`${method} ${path} -> ${r.status}`);
  }
  return r;
}

async function me(token) {
  return (await (await gh(token, "GET", "/user")).json()).login;
}

function readme(p) {
  return `# ${p.title}\n\n- **Platform:** LeetCode\n- **Difficulty:** ${p.difficulty}\n` +
    `- **Tags:** ${(p.tags || []).join(", ") || "—"}\n- **Language:** ${p.lang}\n` +
    `- **Link:** https://leetcode.com/problems/${p.slug}/\n\n` +
    `_Synced in real time by [GitKosh](https://github.com/harsh-bajpai2615/gitkosh)._\n`;
}

async function base(token, owner, repo) {
  let r = await gh(token, "GET", `/repos/${owner}/${repo}/git/ref/heads/main`);
  if (r.status === 404 || r.status === 409) {
    await gh(token, "PUT", `/repos/${owner}/${repo}/contents/README.md`, {
      message: "Initialize repository (GitKosh)",
      content: utf8b64("# Competitive Programming\n\nSynced by GitKosh.\n"),
    });
    r = await gh(token, "GET", `/repos/${owner}/${repo}/git/ref/heads/main`);
  }
  const commitSha = (await r.json()).object.sha;
  const c = await (await gh(token, "GET", `/repos/${owner}/${repo}/git/commits/${commitSha}`)).json();
  return { commitSha, treeSha: c.tree.sha };
}

async function pushSolution(p) {
  const { token, repo } = await getCfg();
  if (!token || !repo) throw new Error("Set your GitHub token and repo in the GitKosh popup.");
  let owner, name;
  if (repo.includes("/")) { [owner, name] = repo.split("/"); }
  else { owner = await me(token); name = repo; }

  const dir = dirFor(p.qid, p.slug);
  const files = {};
  files[`${dir}/solution.${extFor(p.lang)}`] = p.code;
  files[`${dir}/README.md`] = readme(p);

  const { commitSha, treeSha } = await base(token, owner, name);
  const tree = [];
  for (const [path, content] of Object.entries(files)) {
    const b = await (await gh(token, "POST", `/repos/${owner}/${name}/git/blobs`,
      { content: utf8b64(content), encoding: "base64" })).json();
    tree.push({ path, mode: "100644", type: "blob", sha: b.sha });
  }
  const tr = await (await gh(token, "POST", `/repos/${owner}/${name}/git/trees`,
    { tree, base_tree: treeSha })).json();
  const cm = await (await gh(token, "POST", `/repos/${owner}/${name}/git/commits`,
    { message: `LeetCode: ${p.title} (${p.lang})`, tree: tr.sha, parents: [commitSha] })).json();
  await gh(token, "PATCH", `/repos/${owner}/${name}/git/refs/heads/main`,
    { sha: cm.sha, force: false });

  chrome.action.setBadgeText({ text: "✓" });
  chrome.action.setBadgeBackgroundColor({ color: "#16A34A" });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
  return { ok: true, url: cm.html_url };
}
