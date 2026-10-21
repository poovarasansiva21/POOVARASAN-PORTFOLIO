/* Contact form: client validation (mirrors the server), POST to /api/contact, honest states.
   "Sent" is only ever shown after the server answers 200 {ok:true}. */
(function () {
  const PF = window.PF, h = PF.h, form = PF.$("#form");
  if (!form) return;
  const T0 = { v: performance.now() };
  const fields = { first_name: PF.$("#fn"), last_name: PF.$("#ln"), email: PF.$("#em"), message: PF.$("#ms"), consent: PF.$("#pe") };
  const status = PF.$("#form-status"), btn = form.querySelector(".send"), btnLabel = btn.firstChild;
  const val = (k) => (fields[k].type === "checkbox" ? fields[k].checked : fields[k].value.trim());

  function rules() {
    const e = {}, name = (k, label) => { const v = val(k); if (!v) e[k] = `Enter your ${label}.`; else if (v.length > 60) e[k] = `Keep your ${label} under 60 characters.`; };
    name("first_name", "first name"); name("last_name", "last name");
    const em = val("email");
    if (!em) e.email = "Enter your email address."; else if (em.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em)) e.email = "Enter a valid email address, like name@example.com.";
    const m = val("message");
    if (m.length < 10) e.message = "Write at least 10 characters so I know how to help."; else if (m.length > 2000) e.message = `Shorten your message by ${m.length - 2000} characters (2000 maximum).`;
    if (!val("consent")) e.consent = "Please confirm you're happy to be contacted at this email address.";
    return e;
  }
  const errEl = (k) => {
    let el = PF.$("#err-" + k); if (el) return el;
    el = h("p", { class: "ferr", id: "err-" + k }); const f = fields[k];
    (f.type === "checkbox" ? f.closest(".pm") : f).insertAdjacentElement("afterend", el);
    f.setAttribute("aria-describedby", ((f.getAttribute("aria-describedby") || "") + " err-" + k).trim()); return el;
  };
  function showErrors(errs) {
    for (const k of Object.keys(fields)) { const el = errEl(k); el.textContent = errs[k] || ""; fields[k].setAttribute("aria-invalid", errs[k] ? "true" : "false"); }
    const first = Object.keys(fields).find((k) => errs[k]); if (first) fields[first].focus();
  }
  fields.message.addEventListener("input", () => { const n = fields.message.value.length; PF.$("#ms-count").textContent = n > 1800 ? `${2000 - n} characters left` : ""; });

  function setStatus(kind, text, extra) { status.className = "fstatus f-" + kind; status.replaceChildren(...[h("span", { text }), extra].filter(Boolean)); }
  const setBusy = (b) => { btn.disabled = b; form.setAttribute("aria-busy", String(b)); btnLabel.textContent = b ? "Sending… " : "Send "; };
  const mailto = () => "mailto:" + PF_DATA.contact.email + "?subject=" + encodeURIComponent("Portfolio message from " + val("first_name")) +
    "&body=" + encodeURIComponent(`Hi Poovarasan,\n\n${val("message")}\n\n${val("first_name")} ${val("last_name")}\n${val("email")}`);
  const mailBtn = () => h("a", { class: "f-mail", href: mailto(), text: "Open my email app with this message" });

  PF.health().then((hl) => { if (!hl.contact) setStatus("warn", "The contact service is offline right now. You can still write your message here and open it in your email app, or email me directly."); });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault(); if (btn.disabled) return;
    const errs = rules(); showErrors(errs);
    if (Object.keys(errs).length) { setStatus("err", `Please fix ${Object.keys(errs).length === 1 ? "1 field" : Object.keys(errs).length + " fields"} and send again.`); return; }
    const hl = await PF.health();
    if (!hl.contact) { setStatus("warn", "The contact service is unavailable, so nothing was sent from this page.", mailBtn()); return; }
    setBusy(true); setStatus("info", "Sending your message…");
    try {
      const r = await PF.fetchTimeout(PF.apiUrl("/api/contact"), { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ first_name: val("first_name"), last_name: val("last_name"), email: val("email"), message: val("message"), consent: true, website: (form.elements.website || {}).value || "", elapsed_ms: Math.round(performance.now() - T0.v) }) }, 15000);
      const j = await r.json().catch(() => null);
      if (r.ok && j && j.ok === true) {
        setStatus("ok", `Message sent. Thank you, ${val("first_name")}.`);
        form.reset(); showErrors({}); T0.v = performance.now();
      } else if (r.status === 422 && j && j.fields) { showErrors(j.fields); setStatus("err", "The server couldn't accept the message. Check the highlighted fields."); }
      else if (r.status === 429) { const m = Math.max(1, Math.ceil((Number(r.headers.get("retry-after")) || 600) / 60)); setStatus("err", `Too many messages from your network. Your message was not sent. Try again in about ${m} minute${m === 1 ? "" : "s"}.`, mailBtn()); }
      else if (r.status === 400 && j && j.error === "too_fast") setStatus("err", "That was submitted too quickly. Wait a moment and press Send again.");
      else setStatus("err", r.status === 503 ? "The contact service is unavailable, so your message was not sent." : "Something went wrong on the server, so your message was not sent.", mailBtn());
    } catch (e) {
      setStatus("err", e.name === "TimeoutError" ? "The server took too long to respond. Your message may not have been sent." : navigator.onLine === false ? "You appear to be offline. Your message was not sent." : "Couldn't reach the server. Your message was not sent.", mailBtn());
    } finally { setBusy(false); }
  });
})();
