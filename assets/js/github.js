/* Live GitHub data via the public REST API. No tokens: anonymous requests only (60/hour per IP),
   so responses are cached in localStorage and the UI degrades to a clearly labelled fallback.
   status: idle | loading | live | cached | stale | fallback */
(function () {
  const PF = window.PF, API = "https://api.github.com", KEY = "pf.gh.v1";
  const user = PF_DATA.github.username;
  const state = { status: "idle", reason: null, resetAt: null, profile: null, repos: [], events: [], fetchedAt: null, partial: false };
  const subs = new Set();
  const emit = () => subs.forEach((f) => f(state));
  let inflight = null;

  class GhError extends Error { constructor(kind, extra) { super(kind); this.kind = kind; Object.assign(this, extra); } }

  async function get(path) {
    let r;
    try { r = await PF.fetchTimeout(API + path, { headers: { Accept: "application/vnd.github+json" } }, 10000); }
    catch (e) { throw new GhError(navigator.onLine === false ? "offline" : e.name === "TimeoutError" ? "timeout" : "network"); }
    if (r.ok) return r.json();
    const remaining = r.headers.get("x-ratelimit-remaining"), reset = r.headers.get("x-ratelimit-reset"), retry = r.headers.get("retry-after");
    if (r.status === 429 || (r.status === 403 && (remaining === "0" || retry))) {
      throw new GhError("rate_limit", { resetAt: reset ? Number(reset) * 1000 : retry ? Date.now() + Number(retry) * 1000 : null });
    }
    if (r.status === 404) throw new GhError("not_found");
    throw new GhError("http", { status: r.status });
  }

  const slimRepo = (r) => ({ name: r.name, url: r.html_url, description: r.description, language: r.language, stars: r.stargazers_count | 0, forks: r.forks_count | 0, pushedAt: r.pushed_at, fork: !!r.fork, archived: !!r.archived });
  const slimEvent = (e) => ({ type: e.type, repo: (e.repo && e.repo.name || "").split("/").pop(), at: e.created_at, action: e.payload && e.payload.action, refType: e.payload && e.payload.ref_type });
  const slimProfile = (p) => ({ login: p.login, name: p.name, publicRepos: p.public_repos | 0, followers: p.followers | 0, url: p.html_url });

  function apply(data, status, reason, resetAt) {
    Object.assign(state, { status, reason: reason || null, resetAt: resetAt || null, profile: data ? data.profile : null, repos: data ? data.repos : [], events: data ? data.events : [], fetchedAt: data ? data.at : null, partial: !!(data && data.profile && data.profile.publicRepos > data.repos.length) });
    emit();
  }

  async function fetchFresh() {
    const [p, r, e] = await Promise.allSettled([get(`/users/${user}`), get(`/users/${user}/repos?per_page=100&sort=pushed`), get(`/users/${user}/events/public?per_page=30`)]);
    const failed = [p, r].find((x) => x.status === "rejected");
    if (failed) throw failed.reason;
    if (!Array.isArray(r.value)) throw new GhError("http", { status: 0 });
    return { at: Date.now(), profile: slimProfile(p.value), repos: r.value.map(slimRepo), events: e.status === "fulfilled" && Array.isArray(e.value) ? e.value.map(slimEvent) : [] };
  }

  async function load(force) {
    if (inflight) return inflight;
    const cached = PF.store.get(KEY), ttl = (window.PF_CONFIG && PF_CONFIG.githubCacheMs) || 900000;
    if (!force && cached && Date.now() - cached.at < ttl) { apply(cached, "cached"); return state; }
    state.status = "loading"; emit();
    inflight = fetchFresh().then(
      (data) => { PF.store.set(KEY, data); apply(data, "live"); },
      (err) => {
        const kind = err.kind || "network";
        if (cached) apply(cached, "stale", kind, err.resetAt); else apply(null, "fallback", kind, err.resetAt);
      }
    ).then(() => { inflight = null; return state; });
    return inflight;
  }

  const reasonText = (s) => ({
    offline: "you appear to be offline",
    rate_limit: "GitHub's anonymous rate limit was reached" + (s.resetAt ? ` (resets around ${new Date(s.resetAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })})` : ""),
    timeout: "GitHub took too long to respond",
    network: "GitHub could not be reached",
    not_found: `no GitHub user named ${user} was found`,
    http: "GitHub returned an error"
  }[s.reason] || "GitHub could not be reached");

  function statusLabel() {
    const s = state, when = s.fetchedAt ? PF.ago(new Date(s.fetchedAt).toISOString()) : "";
    switch (s.status) {
      case "loading": return { tone: "info", text: "Loading live data from GitHub…" };
      case "live": return { tone: "ok", text: "Live data from the GitHub API, fetched " + when + "." };
      case "cached": return { tone: "ok", text: "Live GitHub data, cached " + when + "." };
      case "stale": return { tone: "warn", text: `Showing GitHub data cached ${when}. Live refresh failed: ${reasonText(s)}.` };
      case "fallback": return { tone: "warn", text: `Live GitHub data unavailable: ${reasonText(s)}. Showing portfolio data instead.` };
      default: return { tone: "info", text: "" };
    }
  }

  const verbs = { PushEvent: "Pushed to", WatchEvent: "Starred", ForkEvent: "Forked", IssueCommentEvent: "Commented on", PullRequestEvent: "Pull request in", PullRequestReviewEvent: "Reviewed a pull request in", ReleaseEvent: "Released in", PublicEvent: "Made public:" };
  function describeEvent(ev) {
    if (ev.type === "CreateEvent") return `Created ${ev.refType || "something"} in ${ev.repo}`;
    if (ev.type === "IssuesEvent") return `${ev.action === "closed" ? "Closed" : "Opened"} an issue in ${ev.repo}`;
    return `${verbs[ev.type] || ev.type.replace(/Event$/, "")} ${ev.repo}`.trim();
  }

  const repoFor = (url) => { const n = (url || "").split("/").pop().toLowerCase(); return state.repos.find((r) => r.name.toLowerCase() === n) || null; };
  const hasLive = () => ["live", "cached", "stale"].includes(state.status) && state.repos.length > 0;
  const totals = () => { const own = state.repos.filter((r) => !r.fork); return { stars: own.reduce((a, r) => a + r.stars, 0), forks: own.reduce((a, r) => a + r.forks, 0) }; };

  PF.github = { state, load, statusLabel, describeEvent, repoFor, hasLive, totals, reasonText,
    subscribe(fn) { subs.add(fn); fn(state); return () => subs.delete(fn); } };
})();
