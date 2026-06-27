const t = document.getElementById("token");
const r = document.getElementById("repo");
const s = document.getElementById("status");

chrome.storage.sync.get(["token", "repo"], (d) => {
  if (d.token) t.value = d.token;
  if (d.repo) r.value = d.repo;
});

document.getElementById("save").onclick = () => {
  chrome.storage.sync.set({ token: t.value.trim(), repo: r.value.trim() }, () => {
    s.textContent = "✓ Saved — solve something on LeetCode!";
    setTimeout(() => (s.textContent = ""), 2500);
  });
};
