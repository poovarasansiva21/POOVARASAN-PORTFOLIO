/* Optional AI assistant. All answers come from the server's /api/chat endpoint (a real model call).
   If the backend or its API key is missing, the UI says so; nothing is simulated. */
(function () {
  const PF = window.PF, h = PF.h, MAX = 500;
  const launcher = h("button", { type: "button", class: "pf-launch pf-ai", id: "ai-open", "aria-haspopup": "dialog", "aria-label": "Open AI assistant" }, PF.icon("chat"), h("span", { class: "pf-launch-t", text: "Ask AI" }));
  const log = h("div", { class: "a-log", id: "ai-log", role: "log", "aria-live": "polite", "aria-label": "Conversation", tabindex: "0" });
  const note = h("p", { class: "a-note", text: "AI-generated answers based on this portfolio's verified information. It can still make mistakes." });
  const ta = h("textarea", { id: "ai-q", class: "a-input", rows: "2", maxlength: String(MAX), placeholder: "Ask about projects, skills or education", enterkeyhint: "send" });
  const send = h("button", { type: "submit", class: "a-send", "aria-label": "Send question" }, PF.icon("send", 20));
  const form = h("form", { class: "a-form" }, h("label", { for: "ai-q", class: "vh", text: "Your question" }), ta, send);
  const count = h("p", { class: "a-count", "aria-hidden": "true" });
  const chips = h("div", { class: "t-chips a-chips", role: "group", "aria-label": "Suggested questions" },
    ["What has he built?", "Which languages does he use?", "How can I contact him?"].map((q) => h("button", { type: "button", text: q, onclick: () => ask(q) })));
  const body = h("div", { class: "a-body" });
  const dlg = h("dialog", { id: "ai", class: "pf-dlg pf-ai-dlg", "aria-labelledby": "ai-title" },
    h("div", { class: "pf-bar" }, h("h2", { id: "ai-title", text: "Ask about Poovarasan" }), h("button", { type: "button", class: "pf-x", "aria-label": "Close assistant", onclick: () => dlg.close() }, PF.icon("close", 18))), body);
  PF.dock().append(launcher); document.body.append(dlg);
  const ctl = PF.dialog(dlg, launcher);

  const convo = []; let busy = false, mode = "checking";

  function showUnavailable(health) {
    mode = "unavailable";
    const why = health && health.reachable ? "The assistant isn't configured on this server." : "The assistant needs the portfolio's backend API, and it can't be reached from this page.";
    body.replaceChildren(h("div", { class: "a-off", role: "status" },
      h("h3", { text: "The AI assistant is unavailable right now" }), h("p", { text: why }),
      h("p", { text: "Everything on this site still works. Try the terminal or the contact form instead." }),
      h("div", { class: "a-off-actions" },
        h("button", { type: "button", text: "Open the terminal", onclick: () => { dlg.close(); PF.terminal && PF.terminal.open(); } }),
        h("a", { href: "#contact", text: "Go to contact form", onclick: () => dlg.close() }),
        h("button", { type: "button", text: "Check again", onclick: () => check(true) }))));
  }
  function showReady() {
    mode = "ready";
    body.replaceChildren(...[note, log, convo.length ? null : chips, form, count].filter(Boolean));
    if (!log.childNodes.length) bubble("assistant", "Hi! I can answer questions about Poovarasan's projects, skills, education and experience.");
    updateCount();
  }
  async function check(force) {
    mode = "checking"; body.replaceChildren(h("p", { class: "a-checking", role: "status", text: "Checking whether the assistant is available…" }));
    const hl = await PF.health(force);
    if (hl.assistant) showReady(); else showUnavailable(hl);
  }

  function bubble(role, text, extra) {
    const b = h("div", { class: "a-msg a-" + role },
      h("div", { class: "a-text", text }),
      role === "assistant" && !extra ? h("small", { text: "AI-generated, may contain mistakes" }) : null, extra || null);
    log.append(b); log.scrollTop = log.scrollHeight; return b;
  }
  const updateCount = () => { count.textContent = ta.value.length > MAX - 80 ? `${MAX - ta.value.length} characters left` : ""; };

  function errorText(status, retry, err) {
    if (err) return err.name === "TimeoutError" ? "The assistant took too long to answer. Try again." : navigator.onLine === false ? "You appear to be offline. Reconnect and try again." : "Couldn't reach the assistant. Try again.";
    if (status === 429) return `You're asking too quickly. Try again in ${retry || 60} seconds.`;
    if (status === 413 || status === 422) return `That question couldn't be sent. Keep it under ${MAX} characters.`;
    if (status === 503) return "The assistant is unavailable right now.";
    return "The AI service didn't respond properly. Try again in a moment.";
  }

  async function ask(text) {
    text = text.trim(); if (!text || busy || mode !== "ready") return;
    busy = true; send.disabled = true; chips.remove();
    bubble("user", text); ta.value = ""; updateCount();
    const wait = h("div", { class: "a-msg a-assistant a-wait", role: "status", text: "Thinking…" }); log.append(wait);
    let status = 0, retry = 0, err = null, reply = null;
    try {
      const r = await PF.fetchTimeout(PF.apiUrl("/api/chat"), { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ messages: [...convo, { role: "user", content: text }].slice(-8) }) }, 30000);
      status = r.status; retry = Number(r.headers.get("retry-after")) || 0;
      const j = await r.json().catch(() => null);
      if (r.ok && j && typeof j.reply === "string" && j.reply.trim()) reply = j.reply.trim();
    } catch (e) { err = e; }
    wait.remove();
    if (reply) { convo.push({ role: "user", content: text }, { role: "assistant", content: reply }); bubble("assistant", reply); }
    else {
      const retryBtn = h("button", { type: "button", class: "a-retry", text: "Try again", onclick: () => { b.remove(); ask(text); } });
      const b = bubble("error", errorText(status, retry, err), retryBtn); b.setAttribute("role", "alert");
      if (status === 503) PF.health(true).then((hl) => { if (!hl.assistant) showUnavailable(hl); });
    }
    busy = false; send.disabled = false; if (matchMedia("(pointer:fine)").matches) ta.focus();
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); ask(ta.value); });
  ta.addEventListener("input", updateCount);
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(ta.value); } });
  launcher.addEventListener("click", () => { ctl.open(); if (mode !== "ready") check(); else if (matchMedia("(pointer:fine)").matches) ta.focus(); });
})();
