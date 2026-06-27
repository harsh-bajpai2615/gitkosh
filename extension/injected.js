// Runs in the PAGE context (not the isolated content-script world) so it can wrap
// the page's own fetch. When LeetCode's submission "check" reports Accepted, it
// forwards the submission id to the content script via postMessage.
(function () {
  const orig = window.fetch;
  window.fetch = async function (...args) {
    const res = await orig.apply(this, args);
    try {
      const req = args[0];
      const url = (req && req.url) || (typeof req === "string" ? req : "");
      if (typeof url === "string" && url.includes("/check/")) {
        res.clone().json().then((d) => {
          if (d && d.status_msg === "Accepted" && d.submission_id) {
            window.postMessage({ source: "gitkosh", submissionId: d.submission_id }, "*");
          }
        }).catch(() => {});
      }
    } catch (e) { /* ignore */ }
    return res;
  };
})();
