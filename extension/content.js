// Injects the page-context hook, then listens for "Accepted" submissions, fetches
// the full submission (code + problem metadata) via LeetCode's GraphQL, and hands
// it to the background worker to push to GitHub.
(function () {
  const s = document.createElement("script");
  s.src = chrome.runtime.getURL("injected.js");
  (document.head || document.documentElement).appendChild(s);
  s.remove();
})();

const recent = new Set();

window.addEventListener("message", async (e) => {
  if (e.source !== window || !e.data || e.data.source !== "gitkosh") return;
  const id = e.data.submissionId;
  if (recent.has(id)) return;
  recent.add(id);
  try {
    const payload = await fetchSubmission(id);
    if (payload && payload.code) {
      chrome.runtime.sendMessage({ type: "push", payload });
    }
  } catch (err) {
    console.warn("GitKosh:", err);
  }
});

async function fetchSubmission(id) {
  const query = `query d($id:Int!){submissionDetails(submissionId:$id){code lang{name} question{title titleSlug questionId difficulty topicTags{name}}}}`;
  const r = await fetch("https://leetcode.com/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ query, variables: { id: Number(id) } }),
  });
  const j = await r.json();
  const d = j && j.data && j.data.submissionDetails;
  if (!d || !d.question) return null;
  return {
    title: d.question.title,
    slug: d.question.titleSlug,
    qid: d.question.questionId,
    difficulty: d.question.difficulty,
    tags: (d.question.topicTags || []).map((t) => t.name),
    lang: (d.lang && d.lang.name) || "",
    code: d.code || "",
  };
}
