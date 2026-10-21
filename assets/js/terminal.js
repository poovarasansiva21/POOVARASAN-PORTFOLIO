/* Interactive developer terminal.
   Security model: input is looked up in a fixed Map of command handlers. It is never evaluated,
   never passed to a shell, never inserted as HTML. Unknown input only produces an error line. */
(function () {
  const PF = window.PF, h = PF.h, D = PF_DATA;
  const HIST_KEY = "pf.term.hist";
  const line = (text, cls) => h("div", { class: "t-line" + (cls ? " t-" + cls : ""), text });
  const link = (text, href) => h("a", { href, target: "_blank", rel: "noopener", text });
  const trunc = (s, n) => (s.length > n ? s.slice(0, n) + "…" : s);

  const commands = new Map();
  const def = (name, desc, run) => commands.set(name, { desc, run });

  def("help", "List the supported commands", () => [
    line("Supported commands:"),
    ...[...commands].map(([n, c]) => h("div", { class: "t-line" }, h("span", { class: "t-k", text: n.padEnd(9) }), c.desc)),
    line("Tip: ↑ ↓ browse history, Tab completes, Ctrl+L clears, Esc closes.", "dim")
  ]);
  def("about", "Who I am", () => [
    line(`${D.name}, ${D.role}, ${D.location}`, "hi"), line(D.summary),
    line(`${D.education.degree}, ${D.education.institution} (${D.education.years}, CGPA ${D.education.cgpa}).`),
    ...D.experience.map((e) => line(`${e.title}, ${e.org} (${e.duration}).`))
  ]);
  def("skills", "Languages, fundamentals, web and ML tools", () =>
    Object.entries(D.skills).map(([k, v]) => h("div", { class: "t-line" }, h("span", { class: "t-k", text: k + ": " }), v.join(", "))));
  def("projects", "Projects with their repositories", () => [
    ...D.projects.flatMap((p, i) => [h("div", { class: "t-line" }, h("span", { class: "t-k", text: String(i + 1).padStart(2, "0") + " " }), p.title, h("span", { class: "t-dim", text: "  [" + p.tech.join(", ") + "]" })),
      h("div", { class: "t-line t-indent" }, link(p.repo, p.repo))]),
    line("Open the Projects section for filters, search and details.", "dim")
  ]);
  def("github", "Live GitHub stats (falls back to portfolio data)", async () => {
    const gh = PF.github; await gh.load();
    const s = gh.state, lbl = gh.statusLabel(), out = [line(lbl.text, lbl.tone === "warn" ? "warn" : "dim")];
    if (gh.hasLive() || s.profile) {
      const t = gh.totals();
      out.push(line(`${s.profile.publicRepos} public repos, ${s.profile.followers} followers, ${t.stars} stars, ${t.forks} forks.`));
      s.repos.filter((r) => !r.fork).slice(0, 3).forEach((r) => out.push(h("div", { class: "t-line" }, h("span", { class: "t-k", text: "recent " }), `${r.name} (${r.language || "n/a"}, pushed ${PF.ago(r.pushedAt)})`)));
      s.events.slice(0, 3).forEach((e) => out.push(line("• " + gh.describeEvent(e) + ", " + PF.ago(e.at), "dim")));
    } else out.push(line(`${D.github.fallbackPublicRepos} public repositories (${D.github.fallbackNote})`));
    out.push(h("div", { class: "t-line" }, link(D.contact.github, D.contact.github)));
    return out;
  });
  def("contact", "How to reach me", () => [
    h("div", { class: "t-line" }, h("span", { class: "t-k", text: "email    " }), link(D.contact.email, "mailto:" + D.contact.email)),
    h("div", { class: "t-line" }, h("span", { class: "t-k", text: "phone    " }), link(D.contact.phone, "tel:" + D.contact.phone.replace(/\s/g, ""))),
    h("div", { class: "t-line" }, h("span", { class: "t-k", text: "linkedin " }), link(D.contact.linkedin, D.contact.linkedin)),
    h("div", { class: "t-line" }, h("span", { class: "t-k", text: "github   " }), link(D.contact.github, D.contact.github)),
    line("Or use the contact form at the bottom of the page.", "dim")
  ]);
  def("clear", "Clear the screen", () => "CLEAR");
  def("date", "Current date and time", () => [line(new Date().toLocaleString(undefined, { dateStyle: "full", timeStyle: "long" }))]);

  /* ---------- UI ---------- */
  const launcher = h("button", { type: "button", class: "pf-launch", id: "term-open", "aria-haspopup": "dialog", "aria-label": "Open developer terminal" }, PF.icon("terminal"), h("span", { class: "pf-launch-t", text: "Terminal" }));
  const out = h("div", { class: "t-out", id: "term-out", role: "log", "aria-live": "polite", "aria-label": "Terminal output", tabindex: "0" });
  const input = h("input", { id: "term-cmd", class: "t-input", type: "text", autocomplete: "off", autocapitalize: "off", autocorrect: "off", spellcheck: "false", enterkeyhint: "send", maxlength: "80", "aria-describedby": "term-hint" });
  const chips = h("div", { class: "t-chips", role: "group", "aria-label": "Quick commands" }, [...commands.keys()].map((n) => h("button", { type: "button", text: n, onclick: () => { exec(n); if (matchMedia("(pointer:fine)").matches) input.focus(); } })));
  const form = h("form", { class: "t-form", autocomplete: "off" },
    h("label", { for: "term-cmd" }, h("span", { "aria-hidden": "true", text: "$" }), h("span", { class: "vh", text: "Command" })), input,
    h("button", { type: "submit", class: "t-run", text: "Run" }));
  const dlg = h("dialog", { id: "term", class: "pf-dlg pf-term", "aria-labelledby": "term-title" },
    h("div", { class: "pf-bar" }, h("h2", { id: "term-title", text: "poovarasan@portfolio: ~" }), h("button", { type: "button", class: "pf-x", "aria-label": "Close terminal", onclick: () => dlg.close() }, PF.icon("close", 18))),
    out, chips, form, h("p", { id: "term-hint", class: "vh", text: "Type help for commands. Only the listed commands run; nothing else is executed." }));
  PF.dock().append(launcher); document.body.append(dlg);
  const ctl = PF.dialog(dlg, launcher);

  let hist = (() => { try { return JSON.parse(sessionStorage.getItem(HIST_KEY)) || []; } catch { return []; } })();
  let pos = hist.length, draft = "";
  const saveHist = () => { try { sessionStorage.setItem(HIST_KEY, JSON.stringify(hist.slice(-50))); } catch { /* ignore */ } };
  const print = (nodes) => { out.append(...[].concat(nodes)); out.scrollTop = out.scrollHeight; };
  let greeted = false;

  function exec(raw) {
    const text = raw.trim(); if (!text) return;
    if (hist[hist.length - 1] !== text) hist.push(text);
    hist = hist.slice(-50); pos = hist.length; saveHist();
    print(h("div", { class: "t-line t-echo" }, h("span", { class: "t-prompt", text: "$ " }), trunc(text, 80)));
    const [cmd, ...args] = text.split(/\s+/), name = cmd.toLowerCase(), c = commands.get(name);
    if (!c) { print(line(`command not found: ${trunc(cmd, 40)}. Type "help" to see the supported commands.`, "err")); return; }
    if (args.length) print(line(`${name} takes no arguments; ignoring them.`, "dim"));
    Promise.resolve(c.run()).then((res) => { if (res === "CLEAR") out.replaceChildren(); else print(res); })
      .catch(() => print(line(`${name} failed unexpectedly. Try again.`, "err")));
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); const v = input.value; input.value = ""; exec(v); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp") { e.preventDefault(); if (pos === hist.length) draft = input.value; if (pos > 0) input.value = hist[--pos]; }
    else if (e.key === "ArrowDown") { e.preventDefault(); if (pos < hist.length) { pos++; input.value = pos === hist.length ? draft : hist[pos]; } }
    else if (e.key === "Tab" && input.value && !/\s/.test(input.value)) {
      e.preventDefault(); const m = [...commands.keys()].filter((n) => n.startsWith(input.value.toLowerCase()));
      if (m.length === 1) input.value = m[0]; else if (m.length > 1) print(line(m.join("   "), "dim"));
    } else if (e.key === "l" && e.ctrlKey) { e.preventDefault(); out.replaceChildren(); }
  });

  launcher.addEventListener("click", () => {
    ctl.open();
    if (!greeted) { greeted = true; print([line("Poovarasan's portfolio terminal", "hi"), line('Type "help" to see the supported commands. Only those run: no shell, no JavaScript.', "dim")]); }
    if (matchMedia("(pointer:fine)").matches) input.focus();
  });
  PF.terminal = { exec, open: () => launcher.click() };
})();
