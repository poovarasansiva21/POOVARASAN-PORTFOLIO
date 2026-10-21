/* Shared helpers. No innerHTML with dynamic data anywhere in the feature modules. */
(function () {
  const PF = (window.PF = window.PF || {});
  PF.$ = (s, r = document) => r.querySelector(s);
  PF.reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* h("a", {class:"x", href:"..", onclick:fn}, "text", childNode) */
  PF.h = function (tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "text") el.textContent = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return el;
  };

  PF.store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage blocked or full */ } },
    remove(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } }
  };

  PF.ago = function (iso) {
    const t = new Date(iso).getTime();
    if (!t) return "";
    const s = Math.round((t - Date.now()) / 1000), a = Math.abs(s);
    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    if (a < 60) return rtf.format(Math.round(s), "second");
    if (a < 3600) return rtf.format(Math.round(s / 60), "minute");
    if (a < 86400) return rtf.format(Math.round(s / 3600), "hour");
    if (a < 86400 * 60) return rtf.format(Math.round(s / 86400), "day");
    return rtf.format(Math.round(s / (86400 * 30)), "month");
  };

  PF.apiUrl = (p) => ((window.PF_CONFIG && PF_CONFIG.apiBase) || "").replace(/\/$/, "") + p;

  /* fetch with timeout; rejects with {name:"TimeoutError"} on timeout */
  PF.fetchTimeout = async function (url, opts = {}, ms = 10000) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), ms);
    try { return await fetch(url, { ...opts, signal: ctl.signal }); }
    catch (e) { if (e.name === "AbortError") { const t = new Error("timeout"); t.name = "TimeoutError"; throw t; } throw e; }
    finally { clearTimeout(timer); }
  };

  /* Which backend features are available? Cached briefly. Never throws. */
  let hp = null, hpAt = 0;
  PF.health = function (force) {
    const ttl = hp && hp.__ok ? 60000 : 8000;
    if (!force && hp && Date.now() - hpAt < ttl) return hp.p;
    const p = PF.fetchTimeout(PF.apiUrl("/api/health"), { headers: { Accept: "application/json" } }, 4000)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("bad status"))))
      .then((j) => ({ reachable: true, assistant: !!j.assistant, contact: !!j.contact }))
      .catch(() => ({ reachable: false, assistant: false, contact: false }));
    hp = { p, __ok: false }; hpAt = Date.now();
    p.then((v) => { hp.__ok = v.reachable; });
    return p;
  };

  /* Native <dialog> wrapper: Esc + focus trap come from the browser; we restore focus on close
     and close on backdrop click. */
  PF.dialog = function (dlg, opener) {
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("close", () => { document.documentElement.classList.remove("pf-lock"); if (opener) opener.focus(); });
    return { open() { if (!dlg.open) dlg.showModal(); document.documentElement.classList.add("pf-lock"); }, close() { dlg.close(); } };
  };

  const icons = {
    terminal: '<path stroke-linecap="round" stroke-linejoin="round" d="M5 8l4 4-4 4M12 16h7"/>',
    chat: '<path stroke-linecap="round" stroke-linejoin="round" d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z"/>',
    close: '<path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/>',
    send: '<path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14m0 0l-6-6m6 6l-6 6"/>'
  };
  /* icons are static strings defined above, never user data */
  PF.icon = (name, size = 22) => {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("width", size); s.setAttribute("height", size); s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "2");
    s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false");
    s.innerHTML = icons[name];
    return s;
  };

  /* Floating launcher dock shared by the terminal and the assistant. */
  PF.dock = function () {
    let d = document.getElementById("pf-dock");
    if (!d) { d = PF.h("div", { id: "pf-dock", class: "pf-dock" }); document.body.append(d); }
    return d;
  };
})();
