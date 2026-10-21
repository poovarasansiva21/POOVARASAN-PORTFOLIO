/* Technical project explorer: filters, search, sorting, expandable details, and the live GitHub panel.
   Content comes from PF_DATA.projects. Optional detail fields are rendered only when present. */
(function () {
  const PF = window.PF, h = PF.h, projects = PF_DATA.projects;
  const grid = PF.$("#pg"), tools = PF.$("#pj-tools"), panel = PF.$("#gh-panel");
  if (!grid || !tools || !panel) return;

  const cats = [["all", "All"], ["ml", "ML & Vision"], ["web", "Web"], ["dsa", "DSA"]];
  const st = { q: "", cat: "all", tech: "", sort: "featured" };
  const open = new Set();
  const techs = [...new Set(projects.flatMap((p) => p.tech))].sort((a, b) => a.localeCompare(b));
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

  /* ---------- GitHub panel ---------- */
  function stat(value, label, note) {
    return h("div", { class: "gh-stat" }, h("strong", { text: value }), h("span", { text: label }), note ? h("small", { text: note }) : null);
  }
  function renderPanel(s) {
    const lbl = PF.github.statusLabel(), live = PF.github.hasLive() || (s.status === "live" || s.status === "cached");
    const fb = PF_DATA.github, t = PF.github.totals();
    const stats = live && s.profile
      ? [stat(s.profile.publicRepos, "Public repositories", s.partial ? "stars and forks count the 100 most recently pushed" : ""), stat(s.profile.followers, "Followers"), stat(t.stars, "Stars received"), stat(t.forks, "Forks")]
      : [stat(fb.fallbackPublicRepos, "Public repositories", fb.fallbackNote), stat("n/a", "Stars received"), stat("n/a", "Forks")];
    const events = live ? s.events.slice(0, 5) : [];
    const body = [
      h("div", { class: "gh-head" },
        h("h3", { id: "gh-title" }, "GitHub activity for ", h("a", { href: PF_DATA.contact.github, target: "_blank", rel: "noopener", text: fb.username })),
        h("button", { type: "button", class: "gh-refresh", disabled: s.status === "loading", onclick: () => PF.github.load(true), text: s.status === "loading" ? "Loading…" : "Refresh" })),
      h("p", { class: "gh-status gh-" + lbl.tone, role: "status", text: lbl.text }),
      h("div", { class: "gh-stats" }, stats)
    ];
    if (live && s.repos.length === 0) body.push(h("p", { class: "gh-empty", text: "GitHub returned no public repositories for this account yet." }));
    if (events.length) body.push(h("ul", { class: "gh-events", "aria-label": "Recent public activity" }, events.map((e) => h("li", {}, h("span", { text: PF.github.describeEvent(e) }), h("time", { datetime: e.at, text: PF.ago(e.at) })))));
    else if (live && s.repos.length) body.push(h("p", { class: "gh-empty", text: "No recent public activity was returned by GitHub." }));
    panel.setAttribute("aria-busy", String(s.status === "loading"));
    panel.replaceChildren(...body);
  }

  /* ---------- project cards ---------- */
  function liveLine(p) {
    const gh = PF.github, repo = gh.repoFor(p.repo);
    if (repo) {
      const bits = [plural(repo.stars, "star"), plural(repo.forks, "fork")];
      if (repo.language) bits.push(repo.language);
      if (repo.pushedAt) bits.push("pushed " + PF.ago(repo.pushedAt));
      return h("p", { class: "pj-live" }, h("b", { text: "Confirmed on GitHub" }), " · " + bits.join(" · "));
    }
    if (gh.hasLive() && !gh.state.partial) return h("p", { class: "pj-live pj-warn", text: "Not found in live GitHub data (the repository may be renamed or private)." });
    return null;
  }
  function details(p) {
    const rows = [["Problem", p.problem], ["Architecture", p.architecture], ["Implementation", p.implementation]];
    if (p.results && p.results.length) rows.push(["Verified results", p.results.join("; ")]);
    const dl = h("dl", { class: "pj-dl" });
    rows.forEach(([k, v]) => { if (v) dl.append(h("dt", { text: k }), h("dd", { text: v })); });
    if (p.demo) dl.append(h("dt", { text: "Live demo" }), h("dd", {}, h("a", { href: p.demo, target: "_blank", rel: "noopener", text: p.demo })));
    const repo = PF.github.repoFor(p.repo);
    if (repo && repo.description) dl.append(h("dt", { text: "GitHub description" }), h("dd", { text: repo.description }));
    return dl;
  }
  function card(p) {
    const idx = projects.indexOf(p), id = "pd-" + p.id, isOpen = open.has(p.id);
    const panelEl = h("div", { class: "pd", id, hidden: !isOpen }, details(p));
    const btn = h("button", { type: "button", class: "more", "aria-expanded": String(isOpen), "aria-controls": id, "aria-label": `${isOpen ? "Hide" : "Show"} details for ${p.title}`, text: isOpen ? "Hide details" : "Details" });
    btn.addEventListener("click", () => {
      const now = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", String(now)); btn.textContent = now ? "Hide details" : "Details";
      btn.setAttribute("aria-label", `${now ? "Hide" : "Show"} details for ${p.title}`);
      panelEl.hidden = !now; now ? open.add(p.id) : open.delete(p.id);
    });
    return h("article", { class: "pj", "data-c": p.category },
      h("div", { class: "i" },
        h("span", { class: "n", text: String(idx + 1).padStart(2, "0") }),
        h("h3", { text: p.title }), h("p", { text: p.summary }), liveLine(p),
        h("ul", { "aria-label": "Technologies" }, p.tech.map((t) => h("li", { text: t }))),
        h("div", { class: "pj-actions" }, btn, h("a", { class: "lk", target: "_blank", rel: "noopener", href: p.repo, text: "View on GitHub" })),
        panelEl));
  }

  /* ---------- filtering and sorting ---------- */
  function visible() {
    const q = st.q.trim().toLowerCase();
    let list = projects.filter((p) => (st.cat === "all" || p.category === st.cat) && (!st.tech || p.tech.includes(st.tech)) &&
      (!q || [p.title, p.summary, p.problem, p.architecture, p.implementation, p.tech.join(" ")].filter(Boolean).join(" ").toLowerCase().includes(q)));
    const live = (p) => PF.github.repoFor(p.repo);
    const by = {
      featured: () => 0,
      name: (a, b) => a.title.localeCompare(b.title),
      stars: (a, b) => (live(b) ? live(b).stars : -1) - (live(a) ? live(a).stars : -1),
      updated: (a, b) => new Date(live(b) ? live(b).pushedAt : 0) - new Date(live(a) ? live(a).pushedAt : 0)
    }[st.sort];
    return list.map((p, i) => [p, i]).sort((x, y) => by(x[0], y[0]) || projects.indexOf(x[0]) - projects.indexOf(y[0])).map((x) => x[0]);
  }
  const count = h("p", { class: "pj-count", role: "status", "aria-live": "polite" });
  function render() {
    const list = visible(), filtered = st.q || st.cat !== "all" || st.tech;
    grid.replaceChildren(...(list.length ? list.map(card) : [h("div", { class: "pj-empty" }, h("p", { text: "No projects match these filters." }), h("button", { type: "button", class: "more", onclick: reset, text: "Clear filters" }))]));
    count.textContent = filtered ? `Showing ${list.length} of ${projects.length} projects` : `${projects.length} projects`;
  }
  function reset() { Object.assign(st, { q: "", cat: "all", tech: "", sort: "featured" }); search.value = ""; techSel.value = ""; sortSel.value = "featured"; syncCats(); render(); }

  /* ---------- toolbar ---------- */
  const search = h("input", { type: "search", id: "pj-q", placeholder: "Search by name, tech or keyword", autocomplete: "off", maxlength: "60" });
  let timer; search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = search.value; render(); }, 120); });
  const techSel = h("select", { id: "pj-tech" }, h("option", { value: "", text: "All technologies" }), techs.map((t) => h("option", { value: t, text: t })));
  techSel.addEventListener("change", () => { st.tech = techSel.value; render(); });
  const sortOpts = [["featured", "Featured order"], ["name", "Name (A to Z)"], ["stars", "Most stars"], ["updated", "Recently updated"]];
  const sortSel = h("select", { id: "pj-sort" }, sortOpts.map(([v, t]) => h("option", { value: v, text: t })));
  sortSel.addEventListener("change", () => { st.sort = sortSel.value; render(); });
  const catBtns = cats.map(([v, t]) => h("button", { type: "button", "data-f": v, text: t, onclick: () => { st.cat = v; syncCats(); render(); } }));
  function syncCats() { catBtns.forEach((b) => { const on = b.dataset.f === st.cat; b.classList.toggle("a", on); b.setAttribute("aria-pressed", String(on)); }); }
  function syncSortAvailability() {
    const live = PF.github.hasLive();
    [...sortSel.options].forEach((o) => { if (o.value === "stars" || o.value === "updated") { o.disabled = !live; o.text = (o.value === "stars" ? "Most stars" : "Recently updated") + (live ? "" : " (needs live GitHub data)"); } });
    if (!live && (st.sort === "stars" || st.sort === "updated")) { st.sort = "featured"; sortSel.value = "featured"; }
  }
  tools.replaceChildren(
    h("div", { class: "pj-row" },
      h("div", { class: "pj-field pj-grow" }, h("label", { for: "pj-q", text: "Search projects" }), search),
      h("div", { class: "pj-field" }, h("label", { for: "pj-tech", text: "Technology" }), techSel),
      h("div", { class: "pj-field" }, h("label", { for: "pj-sort", text: "Sort by" }), sortSel)),
    h("div", { class: "fl", role: "group", "aria-label": "Filter by category" }, catBtns, h("button", { type: "button", class: "pj-clear", onclick: reset, text: "Clear filters" })),
    count);

  /* ---------- wiring ---------- */
  syncCats(); syncSortAvailability(); render(); renderPanel(PF.github.state);
  PF.github.subscribe((s) => { renderPanel(s); syncSortAvailability(); if (s.status !== "loading") render(); });

  const section = PF.$("#projects");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); PF.github.load(); } }, { rootMargin: "400px 0px" });
    io.observe(section);
  } else PF.github.load();
})();
