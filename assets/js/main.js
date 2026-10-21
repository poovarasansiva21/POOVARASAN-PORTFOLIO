/* Original portfolio behaviour (previously an inline <script>), with fixes:
   - preloader can never trap the page; skipped for reduced motion and repeat visits in a session
   - mobile menu has aria-expanded, closes on Esc, and is not tabbable while hidden (see features.css)
   - the expertise path animation only runs while visible and stops once it settles
   - count-ups and parallax respect prefers-reduced-motion
   - scroll listeners are passive; getTotalLength() is guarded */
(function () {
  const $ = (s) => document.querySelector(s), nav = $("#nav");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let seen = false;
  try { seen = sessionStorage.getItem("pf.seen") === "1"; } catch { /* storage blocked */ }
  const quick = reduce || seen;

  const pre = $("#pre");
  if (pre) {
    if (quick) pre.remove();
    else {
      setTimeout(() => {
        pre.classList.add("go");
        try { sessionStorage.setItem("pf.seen", "1"); } catch { /* ignore */ }
      }, 2200);
      setTimeout(() => pre.remove(), 3800);
    }
  }

  const yr = new Date().getFullYear();
  $("#yr").textContent = yr;
  $(".y").textContent = yr;
  $("#code").textContent = Array(2).fill("def predict(model, X):\n    X = preprocess(X)\n    return model.fit(X).predict(X)\nwhile traffic.live():\n    count = detect(frame)\n    signal.adjust(count)\nclass Recommender:\n    def similar(self, book): ...\nSELECT * FROM students WHERE cgpa > 7;\nfor i in range(n): dp[i] = max(dp[i-1], a[i])\n".repeat(6)).join("\n");

  const sc = () => nav.classList.toggle("s", scrollY > 40);
  addEventListener("scroll", sc, { passive: true }); sc();

  /* mobile menu */
  const bg = $("#bg"), bi = $("#bi");
  const setMenu = (open) => {
    nav.classList.toggle("o", open);
    bg.setAttribute("aria-expanded", String(open));
    bi.innerHTML = open ? '<path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/>' : '<path stroke-linecap="round" d="M4 6h16M4 12h16M4 18h16"/>';
  };
  bg.addEventListener("click", () => setMenu(!nav.classList.contains("o")));
  document.querySelectorAll(".mm a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
  addEventListener("keydown", (e) => { if (e.key === "Escape" && nav.classList.contains("o")) { setMenu(false); bg.focus(); } });

  /* reveal on scroll */
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.15 });
  document.querySelectorAll(".rv,.drop").forEach((e) => io.observe(e));
  setTimeout(() => document.querySelectorAll("#home .rv").forEach((e) => e.classList.add("in")), quick ? 0 : 2000);

  /* expertise: dashed path draws with scroll; cards turn red when the line reaches them */
  const ex = $("#ex"), ml = $("#ml"), pp = $("#pp"), cards = [...document.querySelectorAll(".tc")];
  let L = 0; try { L = pp.getTotalLength(); } catch { /* not measurable when hidden */ }
  pp.style.strokeDasharray = L || 0;
  let cur = 0, running = false, visible = false;
  function step() {
    const r = ex.getBoundingClientRect(), t = Math.min(1, Math.max(0, (innerHeight / 2 - r.top) / r.height));
    cur += (t - cur) * (reduce ? 1 : 0.12);
    pp.style.strokeDashoffset = L * (1 - cur);
    ml.firstChild.style.height = cur * 100 + "%";
    const tip = cur * r.height;
    cards.forEach((c) => c.classList.toggle("on", tip >= c.getBoundingClientRect().top - r.top + 50));
    if (visible && Math.abs(t - cur) > 0.001) requestAnimationFrame(step); else running = false;
  }
  const kick = () => { if (visible && !running) { running = true; requestAnimationFrame(step); } };
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }, { rootMargin: "200px 0px" }).observe(ex);
  addEventListener("scroll", kick, { passive: true }); addEventListener("resize", kick);

  /* contact background parallax */
  const cs = $("#contact"), cb = $("#cbg");
  if (!reduce) addEventListener("scroll", () => {
    const r = cs.getBoundingClientRect(), p = Math.min(1, Math.max(0, (innerHeight - r.top) / (innerHeight + r.height)));
    cb.style.transform = `translateY(${-20 + p * 50}%)`;
  }, { passive: true });

  /* count-up numbers */
  if (!reduce) {
    const cu = (el) => {
      const m = el.textContent.trim().match(/^([\d.]+)(\D*)$/); if (!m) return;
      const e = parseFloat(m[1]), d = (m[1].split(".")[1] || "").length, x = m[2], t0 = performance.now();
      const f = (n) => { const p = Math.min(1, (n - t0) / 1300), v = e * (1 - Math.pow(1 - p, 3)); el.textContent = v.toFixed(d) + x; if (p < 1) requestAnimationFrame(f); };
      f(t0);
    };
    const io2 = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { io2.unobserve(e.target); setTimeout(() => cu(e.target), e.target.closest("#home") && !quick ? 2300 : 0); } }), { threshold: 0.6 });
    document.querySelectorAll(".st strong,.chip b").forEach((e) => io2.observe(e));
  }
})();
