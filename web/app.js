/* PaperScroll front end: one file, no build step. Runs in a browser (served by the PC) or inside the Android APK. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const Cap = window.Capacitor;
  const native = !!(Cap && Cap.isNativePlatform && Cap.isNativePlatform());
  const plug = (n) => (Cap && Cap.Plugins && Cap.Plugins[n]) || null;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------------------------------------------------------------- storage helpers
  const ls = {
    get(k, d) { try { const v = localStorage.getItem("ps." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("ps." + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };
  const DEFAULT_SERVER = "http://127.0.0.1:8765";   // only used by an APK that bundles the UI; normal builds load it from the server
  const bundled = location.hostname === "localhost";   // old APKs ship the UI inside; new ones load it from the PC
  const server = () => (native && bundled ? ls.get("server", DEFAULT_SERVER) : "").replace(/\/$/, "");
  const abs = (p) => (p && p.startsWith("/") ? server() + p : p);

  async function api(path, opts = {}) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), opts.timeout || 25000);
    try {
      const r = await fetch(server() + path, {
        method: opts.method || "GET",
        headers: opts.body ? { "Content-Type": "application/json" } : {},
        body: opts.body ? JSON.stringify(opts.body) : undefined,
        signal: ctl.signal,
      });
      if (!r.ok) {
        let d = ""; try { d = (await r.json()).detail || ""; } catch { /* not JSON */ }
        throw new Error(d || `HTTP ${r.status}`);
      }
      return opts.raw ? r : r.json();
    } finally { clearTimeout(t); }
  }

  function toast(msg, ms = 1800) {
    const el = $("#toast");
    el.textContent = msg; el.classList.remove("hidden");
    el.style.animation = "none"; void el.offsetWidth; el.style.animation = "";
    clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.add("hidden"), ms);
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function haptic(kind = "LIGHT") {
    try { if (plug("Haptics")) plug("Haptics").impact({ style: kind }); else navigator.vibrate?.(12); } catch { /* no haptics */ }
  }

  // ---------------------------------------------------------------- theme + reading settings
  const reading = { density: ls.get("density", "std"), font: ls.get("font", 16), theme: ls.get("theme", "auto") };
  // Android WebView multiplies text by the system font scale (Huawei "large text"), which the card layout
  // cannot absorb. New APKs switch that off natively; for older ones, measure it and zoom the page back.
  (function undoTextZoom() {
    try {
      const p = document.createElement("span");
      p.style.cssText = "position:absolute;left:-999px;top:0;visibility:hidden;display:inline-block;font:100px/1 serif";
      p.textContent = "X"; document.body.appendChild(p);
      const z = p.getBoundingClientRect().height / 100; p.remove();
      if (z > 1.04 && z < 3) document.documentElement.style.zoom = (1 / z).toFixed(4);
    } catch { /* optional */ }
  })();
  function applyReading() {
    const root = document.documentElement;
    root.style.setProperty("--fs", reading.font + "px");
    root.dataset.density = reading.density;
    if (reading.theme === "auto") root.removeAttribute("data-theme"); else root.dataset.theme = reading.theme;
    const night = reading.theme === "night" || (reading.theme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
    try {
      plug("StatusBar")?.setStyle({ style: night ? "DARK" : "LIGHT" });
      plug("StatusBar")?.setBackgroundColor({ color: night ? "#15130F" : "#F3EEE4" });
    } catch { /* optional */ }
    $$("#s-density button").forEach((b) => b.classList.toggle("on", b.dataset.v === reading.density));
    $$("#s-theme button").forEach((b) => b.classList.toggle("on", b.dataset.v === reading.theme));
    $("#s-font").value = reading.font;
  }

  // ---------------------------------------------------------------- prefs UI
  const PREFS = [
    ["recency", "时间 · RECENCY", [["newest", "只看最新"], ["fresh", "偏新"], ["any", "不在乎新旧"]]],
    ["fit", "主题贴合 · FIT", [["strict", "严格"], ["balanced", "适中"], ["broad", "发散"]]],
    ["quality", "论文成色 · QUALITY", [["all", "都看"], ["accepted", "优先中稿"], ["cited", "优先高引"], ["classic", "经典回顾"]]],
    ["novelty", "新鲜感 · NOVELTY", [["stable", "稳定"], ["balanced", "适中"], ["surprise", "多点惊喜"]]],
  ];
  function renderPrefs(host, prefs) {
    host.innerHTML = PREFS.map(([k, name, opts]) => `
      <div class="pref"><span class="name">${name}</span>
        <div class="seg" data-pref="${k}">${opts.map(([v, l]) => `<button data-v="${v}" class="${prefs[k] === v ? "on" : ""}">${l}</button>`).join("")}</div>
      </div>`).join("");
    $$(".seg", host).forEach((seg) => seg.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      $$("button", seg).forEach((x) => x.classList.toggle("on", x === b));
    }));
  }
  const readPrefs = (host) => Object.fromEntries($$(".seg[data-pref]", host).map((s) => [s.dataset.pref, ($("button.on", s) || {}).dataset?.v]));

  // ---------------------------------------------------------------- icons (stroked line set, drawn for this app)
  const IC = {
    like: '<svg viewBox="0 0 24 24"><path d="M12 20.3s-7.6-4.6-9.4-9.3C1.4 7.7 3.5 4.5 6.9 4.5c2.1 0 3.6 1.2 5.1 3 1.5-1.8 3-3 5.1-3 3.4 0 5.5 3.2 4.3 6.5-1.8 4.7-9.4 9.3-9.4 9.3z"/></svg>',
    save: '<svg viewBox="0 0 24 24"><path d="M6.5 3.5h11v17l-5.5-4-5.5 4z"/></svg>',
    note: '<svg viewBox="0 0 24 24"><path d="M15.5 4.5l4 4L9 19H5v-4z"/><path d="M13 7l4 4"/></svg>',
    hide: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M6 18L18 6"/></svg>',
    share: '<svg viewBox="0 0 24 24"><path d="M12 15V3.5M7.5 8L12 3.5 16.5 8"/><path d="M5 12.5V20h14v-7.5"/></svg>',
    read: '<svg viewBox="0 0 24 24"><path d="M3 5.5c3-1 6-.8 9 1 3-1.8 6-2 9-1V19c-3-1-6-.8-9 1-3-1.8-6-2-9-1z"/><path d="M12 6.5V20"/></svg>',
    pdf: '<svg viewBox="0 0 24 24"><path d="M6 3h8.5L19 7.5V21H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/></svg>',
    heart: '<svg viewBox="0 0 24 24"><path d="M12 21s-8.2-5-10.1-10.1C.6 7.3 2.9 3.8 6.6 3.8c2.3 0 3.9 1.3 5.4 3.2 1.5-1.9 3.1-3.2 5.4-3.2 3.7 0 6 3.5 4.7 7.1C20.2 16 12 21 12 21z"/></svg>',
  };

  // ---------------------------------------------------------------- today's reading counter
  const today = () => new Date().toISOString().slice(0, 10);
  const counter = ls.get("readcount", { d: today(), ids: [] });
  function renderCount(bump) {
    if (counter.d !== today()) { counter.d = today(); counter.ids = []; }
    const el = $("#read-count");
    $("b", el).textContent = counter.ids.length;
    if (bump && !reduceMotion) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
  }
  function countRead(id) {
    if (counter.d !== today()) { counter.d = today(); counter.ids = []; }
    if (counter.ids.includes(id)) return;
    counter.ids.push(id); ls.set("readcount", counter); renderCount(true);
  }

  // ---------------------------------------------------------------- feed
  const feedEl = $("#feed");
  const state = { cards: [], loading: false, offline: false, current: null, enterTs: 0, pin: null, serial: ls.get("serial", 0) };

  // numbers and SOTA claims are what the eye should land on
  // Soft hyphens from TeX patterns: justified English then breaks inside long words instead of
  // stretching the spaces (the phone's WebView cannot hyphenate on its own).
  let hyph = (s) => s;
  try { if (window.createHyphenator && window.hyphenationPatternsEnUs) hyph = window.createHyphenator(window.hyphenationPatternsEnUs, { hyphenChar: "\u00AD", minWordLength: 6 }); } catch { /* optional */ }
  const hi = (s) => esc(hyph(s || "")).replace(/(?:(?:&gt;|[+~≈])?\d+(?:\.\d+)?\s?(?:%|×|x\b|-fold|\s?pp\b|\s?(?:percentage )?points\b))|\bstate-of-the-art\b|\bSOTA\b/gi, (m) => `<b class="num">${m}</b>`);
  const pct = (t) => (t < 1 ? "&lt;1%" : Math.round(t) + "%");
  function whyHTML(c) {
    if (c.explore) return `<span class="w-ex">邻近领域</span>换换口味，离你常看的方向不远`;
    const w = c.why || {}, bits = [];
    if (w.reason === "interest" && w.label) bits.push(`你常看 <i>${esc(w.label)}</i>`);
    else if (w.reason === "session") bits.push(w.label ? `接着刚才的 <i>${esc(w.label)}</i>` : "接着你刚才在看的");
    else if (w.reason === "author" && w.label) bits.push(`你喜欢过 <i>${esc(w.label)}</i> 的论文`);
    if (w.top != null && !bits.length) bits.push(`相关度 前 ${pct(w.top)}`);
    if (w.hits && w.hits.length) bits.push(`提到 ${w.hits.map((h) => `<i>${esc(h)}</i>`).join("、")}`);
    return bits.length ? `<span class="w-lb">为何推荐</span>${bits.join(" · ")}` : "";
  }
  function tierText(c) {
    const t = c.tier || {}, b = [];
    if (t.ccf) b.push("CCF-" + esc(t.ccf));
    if (t.core) b.push("CORE " + esc(t.core));
    return b.join(" · ");
  }
  function factsHTML(c) {
    const g = c.glance || {}, f = [];
    for (const u of g.code || []) f.push(`<button class="fact link" data-u="${esc(u)}">代码 ↗</button>`);
    for (const u of g.project || []) f.push(`<button class="fact link" data-u="${esc(u)}">项目页 ↗</button>`);
    if (g.code_soon) f.push(`<span class="fact">代码待公开</span>`);
    if (g.pages) f.push(`<span class="fact">${g.pages} 页${g.figures ? ` · ${g.figures} 图` : ""}</span>`);
    if (c.citations) f.push(`<span class="fact">${c.citations} 引用</span>`);
    return f.join("");
  }

  function cardHTML(c, idx) {
    const d = reading.density;
    const g = c.glance || {};
    const authors = c.n_authors > 2
      ? `${esc(c.first_author)} <i>…</i> ${esc(c.last_author)} <i>· ${c.n_authors} 人</i>`
      : c.authors.map(esc).join(" <i>&amp;</i> ");
    const venue = c.venue || (c.accepted ? "Accepted" : "");
    const tier = tierText(c);
    const seal = venue ? `<div class="seal${c.fig ? "" : " inline"}">${esc(venue)}${tier ? `<small>${tier}</small>` : ""}</div>` : "";
    let i = 0;
    const r = () => `data-r style="--i:${i++}"`;
    const plate = c.fig ? `
      <figure class="plate loading" ${r()}>
        ${seal}
        <div class="plate-frame" data-act="zoom"><img alt="Key figure" decoding="async" src="${esc(abs(c.fig))}"
          onload="this.classList.add('ok');this.closest('.plate').classList.remove('loading');window.psFit(this.closest('.card'))"
          onerror="const k=this.closest('.card'),p=this.closest('.plate'),s=p.querySelector('.seal');if(s){s.classList.add('inline');p.after(s)}p.remove();window.psFit(k)"></div>
      </figure>` : (seal ? `<div ${r()}>${seal}</div>` : "");
    const rows = [["问题", g.problem, "p"], ["方法", g.method, "m"], ["结果", g.result, "r"]]
      .filter(([, t, k]) => t && (d !== "min" || k === "m"));
    const glance = rows.length
      ? `<div class="glance" data-act="detail" ${r()}>${rows.map(([l, t, k]) => `<p class="g-row g-${k}" lang="en"><span class="rh">${l}</span>${hi(t)}</p>`).join("")}</div>`
      : `<p class="tldr" lang="en" data-act="detail" ${r()}>${hi(c.tldr)}</p>`;
    const used = new Set(Object.values(c.roles || {}));
    const rest = rows.length && d !== "min" ? (c.sents || []).filter((_, k) => !used.has(k)).join(" ") : "";
    const kinds = (g.kinds || []).map((k) => `<span class="kind">${esc(k)}</span>`).join("");
    const why = whyHTML(c);
    const facts = factsHTML(c);
    return `
      <div class="card-body">
        <div class="folio" ${r()}><span class="no">No.${String(idx).padStart(4, "0")}</span><span>${esc(c.primary)}</span>
          <span class="grow"></span><span>${esc(c.published)}</span><button class="tr-btn" data-act="translate" aria-label="翻译这篇">译</button></div>
        ${g.name || kinds ? `<div class="kick" ${r()}>${g.name ? `<span class="name">${esc(g.name)}</span>` : ""}${kinds}</div>` : ""}
        <h2 lang="en" ${r()}>${esc(c.title)}</h2>
        ${why ? `<div class="why" ${r()}>${why}</div>` : ""}
        ${plate}
        ${glance}
        ${rest ? `<p class="rest" lang="en" data-act="detail"><span class="lbl">摘要其余</span>${hi(rest)}</p>` : ""}
        <div class="meta" ${r()}>
          ${d !== "min" ? `<div class="byline">${authors}${c.affiliations.length ? `<span class="affs"> · ${c.affiliations.slice(0, 2).map(esc).join(" · ")}</span>` : ""}</div>` : ""}
          ${facts ? `<div class="facts">${facts}</div>` : ""}
        </div>
      </div>
      <div class="actions">
        <button data-act="like" class="like ${c.liked ? "on" : ""}" aria-label="喜欢">${IC.like}<span>喜欢</span></button>
        <button data-act="save" class="save ${c.saved ? "on" : ""}" aria-label="收藏">${IC.save}<span>收藏</span></button>
        <button data-act="note" class="note ${c.note ? "on" : ""}" aria-label="笔记">${IC.note}<span>笔记</span></button>
        <button data-act="detail" aria-label="精读">${IC.read}<span>精读</span></button>
        <button data-act="pdf" aria-label="打开 PDF">${IC.pdf}<span>PDF</span></button>
        <button data-act="share" aria-label="分享">${IC.share}<span>分享</span></button>
        <button data-act="hide" aria-label="不感兴趣">${IC.hide}<span>不想看</span></button>
      </div>`;
  }

  function skeletonHTML() {
    return `<article class="card skeleton">
      <div class="folio"><span class="no">No.····</span><span class="grow"></span></div>
      <div class="sk" style="height:34%;margin-top:4px"></div>
      <div class="sk" style="height:30px;width:92%"></div><div class="sk" style="height:30px;width:70%"></div>
      <div class="sk" style="height:15px;width:96%;margin-top:6px"></div><div class="sk" style="height:15px;width:88%"></div>
      <div class="sk" style="height:15px;width:60%"></div></article>`;
  }

  // ---------------------------------------------------------------- fit figure and text to the card
  // Fixed rules, no hiding:
  //  * the figure always spans the full text width (no side margins). Its box is the image's natural
  //    height at that width, capped at 42% of the card; a taller image is cropped from the top
  //    (tap shows the whole figure), so it is never shrunk into a thumbnail.
  //  * the three paragraphs get the rest. They are clamped (… then 精读 shows everything); only if even
  //    2 lines each do not fit does the figure give back height, down to 24% of the card.
  const CLAMPS = [2, 3, 4, 5, 6, 8, 12, 40];
  let scrolling = false, scrollT = 0;
  const fitQueue = new Set();
  feedEl.addEventListener("scroll", () => {
    scrolling = true; clearTimeout(scrollT);
    scrollT = setTimeout(() => { scrolling = false; const q = [...fitQueue]; fitQueue.clear(); q.forEach(fitCard); }, 220);
  }, { passive: true });
  function fits(body) {   // offsets ignore the reveal transform, unlike scrollHeight
    const last = body.lastElementChild;
    return !last || last.offsetTop + last.offsetHeight <= body.offsetTop + body.clientHeight + 1;
  }
  function fitCard(el) {
    if (!el || !el.isConnected) return;
    if (scrolling) { fitQueue.add(el); return; }       // changing layout mid-swipe makes scroll-snap jump back
    const body = $(".card-body", el); if (!body || !body.clientHeight) return;   // hidden view: refit later
    if (document.fonts && document.fonts.status !== "loaded" && !el._fontWait) {
      el._fontWait = true;
      document.fonts.ready.then(() => { el._fontWait = false; requestAnimationFrame(() => fitCard(el)); });
    }
    const paras = $$(".g-row, .tldr", el);
    const set = (n) => paras.forEach((d) => { d.style.webkitLineClamp = String(d.classList.contains("g-m") ? n + 1 : d.classList.contains("tldr") ? n * 2 : n); });
    const rest = $(".rest", el); if (rest) rest.style.display = "none";
    const facts = $(".facts", el), why = $(".why", el), h2 = $("h2", el);
    if (facts) facts.style.display = ""; if (why) why.style.display = ""; if (h2) h2.style.webkitLineClamp = "";
    if ($(".plate", el)) $(".plate", el).style.display = "";
    const H = body.clientHeight;
    const plate = $(".plate", el), img = plate && $("img", plate);
    let fig = 0, figMin = 0;
    if (plate) {
      const W = plate.clientWidth;
      const natural = img && img.naturalWidth ? (W - 14) * img.naturalHeight / img.naturalWidth + 14 : H * 0.34;  // loading: placeholder
      fig = Math.min(natural, H * 0.4);
      figMin = Math.min(natural, H * 0.24);
      plate.style.height = fig + "px";
      plate.classList.toggle("crop", natural > fig + 2);
    }
    // largest clamp that fits with the full figure
    let n = CLAMPS.length - 1;
    for (; n > 0; n--) { set(CLAMPS[n]); if (fits(body)) break; }
    set(CLAMPS[n]);
    // still overflowing at 2 lines: let the figure give back height (cropped from the top)
    while (plate && !fits(body) && fig > figMin) {
      fig = Math.max(figMin, fig - 12);
      plate.style.height = fig + "px";
      plate.classList.add("crop");
    }
    // still too much: drop the least useful bits in order, then shrink the figure further, then hide it
    for (const step of [() => facts && (facts.style.display = "none"), () => why && (why.style.display = "none"),
                        () => h2 && (h2.style.webkitLineClamp = "2")]) {
      if (fits(body)) break;
      step();
    }
    while (plate && !fits(body) && fig > H * 0.14) { fig -= 12; plate.style.height = fig + "px"; plate.classList.add("crop"); }
    if (plate && !fits(body)) plate.style.display = "none";
    // then give spare lines one at a time: method first, then result, then problem
    const order = [".g-m", ".g-r", ".g-p", ".tldr"].map((k) => $(k, el)).filter(Boolean);
    const cur = new Map(order.map((d) => [d, parseInt(d.style.webkitLineClamp, 10) || 3]));
    for (let grew = true; grew;) {
      grew = false;
      for (const d of order) {
        const v = cur.get(d); if (v >= 40) continue;
        d.style.webkitLineClamp = String(v + 1);
        if (fits(body) && d.scrollHeight > d.clientHeight + 1) { cur.set(d, v + 1); grew = true; }
        else if (fits(body)) { cur.set(d, 40); d.style.webkitLineClamp = "40"; }   // already shows everything
        else d.style.webkitLineClamp = String(v);
      }
    }
    if (plate && img && img.naturalWidth) {        // re-check crop against the final box
      const natural = (plate.clientWidth - 14) * img.naturalHeight / img.naturalWidth + 14;
      plate.classList.toggle("crop", natural > fig + 2);
    }
    // space left over: show the rest of the abstract
    if (rest && fits(body)) {
      rest.style.display = "-webkit-box";
      let lines = 30; rest.style.webkitLineClamp = "30";
      while (lines >= 2 && !fits(body)) { lines -= 1; rest.style.webkitLineClamp = String(lines); }
      if (lines < 2) rest.style.display = "none";
    }
  }
  window.psFit = fitCard;
  const refitAll = () => $$(".card:not(.skeleton)", feedEl).forEach(fitCard);
  const refitSoon = () => { clearTimeout(refitAll._t); refitAll._t = setTimeout(refitAll, 120); };
  window.addEventListener("resize", refitSoon);
  // the feed's height can change without a window resize (WebView bars, first layout): watch it directly
  if (window.ResizeObserver) {
    let lastH = 0;
    new ResizeObserver((es) => { const h = Math.round(es[0].contentRect.height); if (h && h !== lastH) { lastH = h; refitSoon(); } }).observe(feedEl);
  }
  // web fonts change line lengths: refit once they arrive (otherwise fallback-font metrics leave gaps)
  if (document.fonts) {
    document.fonts.ready.then(() => requestAnimationFrame(refitAll));
    document.fonts.addEventListener("loadingdone", () => requestAnimationFrame(refitAll));
  }

  function appendCards(cards) {
    $$(".card.skeleton", feedEl).forEach((x) => x.remove());
    const frag = document.createDocumentFragment();
    for (const c of cards) {
      if (state.cards.some((x) => x.id === c.id)) continue;
      state.cards.push(c);
      c._no = ++state.serial;
      const el = document.createElement("article");
      el.className = "card"; el.dataset.id = c.id;
      el.innerHTML = cardHTML(c, c._no);
      frag.appendChild(el);
      io.observe(el);
    }
    ls.set("serial", state.serial);
    feedEl.appendChild(frag);
    requestAnimationFrame(refitAll);
    if (!state.offline) ls.set("cache", state.cards.slice(-40));
    const first = $(".card", feedEl);
    if (first && state.cards.length <= cards.length) {
      first.classList.add("in");
      if (!ls.get("hinted", false)) {
        const h = document.createElement("div");
        h.className = "swipe-hint"; h.innerHTML = "↑<span>上滑看下一篇 · 双击喜欢</span>";
        first.appendChild(h); ls.set("hinted", true);
        setTimeout(() => h.remove(), 4500);
      }
    }
  }

  function rerenderCards() {
    $$(".card:not(.skeleton)", feedEl).forEach((el) => {
      const c = state.cards.find((x) => x.id === el.dataset.id);
      if (c) el.innerHTML = cardHTML(c, c._no);
    });
    requestAnimationFrame(refitAll);
  }

  function showMsg(html) {
    const m = $("#feed-msg");
    if (!html) { m.classList.add("hidden"); return; }
    m.innerHTML = html; m.classList.remove("hidden");
  }

  async function loadMore() {
    if (state.loading) return;
    state.loading = true;
    if (!state.cards.length) feedEl.innerHTML = skeletonHTML();
    else if (!$(".card.skeleton", feedEl)) feedEl.insertAdjacentHTML("beforeend", skeletonHTML());   // visible "loading next" page at the end
    try {
      const r = await api("/api/feed", { method: "POST", body: { n: 6, pin: state.pin }, timeout: 40000 });
      state.pin = null;
      if (state.offline) { state.offline = false; $(".offline-bar")?.remove(); }
      if (!r.cards.length && !state.cards.length) {
        feedEl.innerHTML = "";
        const j = r.job || {};
        showMsg(r.indexed === 0
          ? `<div class="big">正在印刷第一期…</div><div class="small">${esc(j.step || "")} ${esc(j.ingest || "")} ${esc(j.embed || "")}<br>首次建库约 10–30 分钟</div><button class="btn ghost" id="retry">再试一次</button>`
          : `<div class="big">这一期读完了</div><div class="small">在设置里放宽「时间」或「主题贴合」，或者重置已看记录</div><button class="btn ghost" id="retry">再试一次</button>`);
        $("#retry")?.addEventListener("click", () => { showMsg(""); loadMore(); });
      } else {
        showMsg("");
        appendCards(r.cards);
      }
    } catch (e) {
      $$(".card.skeleton", feedEl).forEach((x) => x.remove());
      if (!state.cards.length) {
        const cache = ls.get("cache", []);
        if (cache.length) {
          state.offline = true;
          appendCards(cache);
          const bar = document.createElement("div");
          bar.className = "offline-bar"; bar.textContent = "OFFLINE · 连不上电脑，显示缓存";
          $("#view-feed").appendChild(bar);
        } else {
          showMsg(`<div class="big">连不上电脑</div><div class="small">${esc(server() || location.origin)}<br>确认手机 Tailscale 已连接、电脑开机</div><button class="btn ghost" id="retry">重试</button>`);
          $("#retry")?.addEventListener("click", () => { showMsg(""); loadMore(); });
        }
      } else {
        toast("加载失败：" + e.message);
      }
    } finally { state.loading = false; }
  }

  // dwell tracking → view / skip events; reveal animation; prefetch when near the end
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      const id = en.target.dataset.id;
      if (en.isIntersecting && en.intersectionRatio > 0.6) {
        leaveCurrent();
        state.current = id; state.enterTs = Date.now();
        en.target.classList.add("in");
        const idx = state.cards.findIndex((c) => c.id === id);
        if (idx >= state.cards.length - 3 && !state.offline) loadMore();
      } else if (!en.isIntersecting) {
        en.target.classList.remove("in");   // replay the reveal next time it comes into view
      }
    }
  }, { root: feedEl, threshold: [0, 0.6] });
  function leaveCurrent() {
    if (!state.current || state.offline) return;
    const dwell = (Date.now() - state.enterTs) / 1000;
    if (dwell >= 1.5) countRead(state.current);
    sendEvent(state.current, dwell < 1.5 ? "skip" : "view", { dwell });
    state.current = null;
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) leaveCurrent();
    else { if (state.current == null) state.enterTs = Date.now(); checkUpdate(); }
  });

  // ---------------------------------------------------------------- UI updates without reinstalling
  let webVersion = null;
  async function checkUpdate() {
    if (bundled && native) return;   // an old APK with the UI baked in cannot reload a newer one
    try {
      const st = await api("/api/status", { timeout: 8000 });
      if (!st.web_version) return;
      if (webVersion == null) { webVersion = st.web_version; return; }
      if (st.web_version !== webVersion && !$(".update-bar")) {
        const bar = document.createElement("button");
        bar.className = "update-bar"; bar.textContent = "界面有更新 · 点此载入";
        bar.onclick = () => location.reload();
        $("#app").appendChild(bar);
      }
    } catch { /* offline: try next time */ }
  }

  // strong implicit signals for the recommender (figure, close reading, links, share), once per card and kind
  const engaged = new Set();
  function engage(c, kind) {
    if (!c || state.offline) return;
    const k = c.id + "|" + kind;
    if (engaged.has(k)) return;
    engaged.add(k); sendEvent(c.id, kind);
  }

  const pending = ls.get("pending", []);
  async function sendEvent(id, kind, extra = {}) {
    // eid lets the server drop a resend of an event it already stored (a timed-out request may have arrived)
    const ev = { id, kind, eid: Date.now().toString(36) + Math.random().toString(36).slice(2, 8), ...extra };
    try { await api("/api/event", { method: "POST", body: ev, timeout: 8000 }); }
    catch { pending.push(ev); ls.set("pending", pending.slice(-200)); }
  }
  let flushing = false;
  async function flushPending() {
    if (flushing) return;   // two overlapping flushes would send the same event twice
    flushing = true;
    try {
      while (pending.length) {
        try { await api("/api/event", { method: "POST", body: pending[0], timeout: 8000 }); pending.shift(); ls.set("pending", pending); }
        catch { return; }
      }
    } finally { flushing = false; }
  }

  // taps: buttons, plus double-tap anywhere else on the card = like
  let lastTap = { t: 0, x: 0, y: 0 };
  feedEl.addEventListener("click", (e) => {
    const el = e.target.closest(".card"); if (!el || el.classList.contains("skeleton")) return;
    const c = state.cards.find((x) => x.id === el.dataset.id);
    const b = e.target.closest("[data-act]");
    const now = Date.now();
    const dbl = now - lastTap.t < 320 && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 40;
    lastTap = { t: now, x: e.clientX, y: e.clientY };
    if (dbl && !(b && b.closest(".actions"))) {
      clearTimeout(feedEl._zoomT);
      burst(el, e.clientX, e.clientY);
      if (!c.liked) act("like", c, $(".actions .like", el), el);
      else haptic("LIGHT");
      return;
    }
    const link = e.target.closest("[data-u]");
    if (link) { engage(c, "link"); openUrl(link.dataset.u); return; }
    if (!b) return;
    if (b.dataset.act === "zoom" || (b.dataset.act === "detail" && !b.closest(".actions"))) {   // wait: may become a double tap
      clearTimeout(feedEl._zoomT);
      const k = b.dataset.act;
      feedEl._zoomT = setTimeout(() => { engage(c, k === "zoom" ? "fig" : "read"); k === "zoom" ? openViewer(abs(c.fig)) : openDetail(c); }, 330);
      return;
    }
    act(b.dataset.act, c, b, el);
  });

  function burst(cardEl, x, y) {
    const r = cardEl.getBoundingClientRect();
    const h = document.createElement("div");
    h.className = "burst"; h.innerHTML = IC.heart;
    h.style.left = (x - r.left) + "px"; h.style.top = (y - r.top) + "px";
    cardEl.appendChild(h);
    setTimeout(() => h.remove(), 850);
  }

  function popBtn(btn) { if (!btn || reduceMotion) return; btn.classList.remove("pop"); void btn.offsetWidth; btn.classList.add("pop"); }

  function act(kind, c, btn, cardEl) {
    if (kind === "like" || kind === "save") {
      const key = kind === "like" ? "liked" : "saved";
      c[key] = !c[key];
      btn?.classList.toggle("on", c[key]);
      if (c[key]) { popBtn(btn); haptic(kind === "like" ? "MEDIUM" : "LIGHT"); }
      sendEvent(c.id, c[key] ? kind : "un" + kind);
      toast(c[key] ? (kind === "like" ? "喜欢 · 会推荐更多类似的" : "已收进书房") : "已取消");
    } else if (kind === "hide") {
      c.hidden = true;
      sendEvent(c.id, "hide");
      haptic("LIGHT");
      toast("少推这类");
      const next = cardEl?.nextElementSibling;
      if (next) next.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    } else if (kind === "note") {
      openNote(c, btn);
    } else if (kind === "share") {
      engage(c, "share"); share(c);
    } else if (kind === "pdf") {
      engage(c, "link"); openUrl(c.pdf_url);
    } else if (kind === "detail") {
      engage(c, "read"); openDetail(c);
    } else if (kind === "translate") {
      translateCard(c, cardEl, btn);
    }
  }

  // ---------------------------------------------------------------- refresh: button + pull-down on the first card
  async function refreshFeed(fromPull) {
    checkUpdate();
    const btn = $("#btn-refresh");
    btn.classList.add("spin");
    haptic("LIGHT");
    leaveCurrent();
    state.cards = []; state.offline = false; $(".offline-bar")?.remove();
    io.disconnect();
    feedEl.scrollTop = 0;
    feedEl.innerHTML = "";
    await loadMore();
    btn.classList.remove("spin");
    if (!fromPull && state.cards.length) toast("换了一批");
  }
  $("#btn-refresh").addEventListener("click", () => refreshFeed(false));

  const ptr = $("#ptr");
  let pull = null;
  feedEl.addEventListener("touchstart", (e) => {
    pull = feedEl.scrollTop <= 0 && !state.loading ? { y: e.touches[0].clientY, d: 0 } : null;
  }, { passive: true });
  feedEl.addEventListener("touchmove", (e) => {
    if (!pull) return;
    pull.d = Math.max(0, e.touches[0].clientY - pull.y);
    if (feedEl.scrollTop > 0) { pull = null; ptr.style.opacity = 0; return; }
    const d = Math.min(pull.d, 140);
    ptr.style.opacity = Math.min(1, d / 60);
    ptr.style.transform = `translate(-50%, ${-60 + d * 0.75}px)`;
    const ready = d > 90;
    if (ready && !ptr.classList.contains("ready")) haptic("LIGHT");
    ptr.classList.toggle("ready", ready);
    $(".ptr-text", ptr).textContent = ready ? "松手换一批" : "下拉换一批";
    $(".ptr-seal svg", ptr).style.transform = `rotate(${d * 2.6}deg)`;
  }, { passive: true });
  feedEl.addEventListener("touchend", async () => {
    if (!pull) return;
    const go = pull.d > 90 && ptr.classList.contains("ready");
    pull = null;
    if (go) {
      ptr.classList.add("loading"); $(".ptr-text", ptr).textContent = "正在排新的一期…";
      await refreshFeed(true);
      ptr.classList.remove("loading");
    }
    ptr.classList.remove("ready");
    ptr.style.transition = "transform .3s, opacity .3s";
    ptr.style.opacity = 0; ptr.style.transform = "translate(-50%, -60px)";
    setTimeout(() => (ptr.style.transition = ""), 320);
  });

  // ---------------------------------------------------------------- translation (only on request)
  // A tap on 译 translates this paper's title and abstract sentences (DeepL on the computer, cached there);
  // a second tap shows the original again. Selecting any text offers to translate just the selection.
  const LANG_ATTR = { "ZH-HANS": "zh-Hans", "ZH-HANT": "zh-Hant", "EN-US": "en", "PT-BR": "pt" };
  const langAttr = (l) => LANG_ATTR[l] || (l || "zh").toLowerCase();
  async function getTranslation(c) {
    if (c._tr) return c._tr;
    c._tr = await api("/api/translate", { method: "POST", body: { id: c.id }, timeout: 45000 });
    return c._tr;
  }
  function trError(e) {
    const m = e.message || "";
    toast(/no DeepL/.test(m) ? "先在设置里填 DeepL key" : /quota/.test(m) ? "DeepL 本月额度用完了" : "翻译失败：" + m, 2600);
  }
  async function translateCard(c, el, btn) {
    if (!el) return;
    if (el._orig) {   // back to the original
      for (const [node, html, lang] of el._orig) { node.innerHTML = html; node.setAttribute("lang", lang); }
      el._orig = null; el.classList.remove("translated"); btn?.classList.remove("on"); if (btn) btn.textContent = "译";
      fitCard(el); return;
    }
    btn?.classList.add("busy");
    let tr;
    try { tr = await getTranslation(c); } catch (e) { trError(e); return; } finally { btn?.classList.remove("busy"); }
    const L = langAttr(tr.lang), roles = c.roles || {}, S = tr.sents || [];
    const orig = [];
    const swap = (node, html) => { if (!node) return; orig.push([node, node.innerHTML, node.getAttribute("lang") || "en"]); node.innerHTML = html; node.setAttribute("lang", L); };
    swap($("h2", el), esc(tr.title));
    const lbl = { p: "问题", m: "方法", r: "结果" }, key = { p: "problem", m: "method", r: "result" };
    for (const k of ["p", "m", "r"]) {
      const row = $(".g-" + k, el), i = roles[key[k]];
      if (row && i != null && S[i]) swap(row, `<span class="rh">${lbl[k]}</span>${hi(S[i])}`);
    }
    const used = new Set(Object.values(roles));
    const rest = $(".rest", el);
    const sep = /^(zh|ja)/.test(L) ? "" : " ";   // no space between CJK sentences
    if (rest) swap(rest, `<span class="lbl">摘要其余</span>${hi(S.filter((_, k) => !used.has(k)).join(sep))}`);
    const tldr = $(".tldr", el);
    if (tldr) swap(tldr, hi(S.slice(0, 2).join(sep)));
    el._orig = orig; el.classList.add("translated");
    if (btn) { btn.classList.add("on"); btn.textContent = "原文"; }
    fitCard(el);
  }
  async function translateSheet(c, btn) {
    const box = $("#sheet-content");
    if (box._orig) {
      for (const [node, html, lang] of box._orig) { node.innerHTML = html; node.setAttribute("lang", lang); }
      box._orig = null; btn.classList.remove("on"); btn.textContent = "译"; return;
    }
    btn.classList.add("busy");
    let tr;
    try { tr = await getTranslation(c); } catch (e) { trError(e); return; } finally { btn.classList.remove("busy"); }
    const L = langAttr(tr.lang), orig = [];
    const swap = (node, html) => { if (!node) return; orig.push([node, node.innerHTML, node.getAttribute("lang") || "en"]); node.innerHTML = html; node.setAttribute("lang", L); };
    swap($("h3", box), esc(tr.title));
    const abs = $(".abs", box);
    if (abs) {
      const sep = /^(zh|ja)/.test(L) ? "" : " ";
      swap(abs, $$(":scope > span", abs).map((sp, i) => `<span class="${sp.className}">${tr.sents[i] != null ? hi(tr.sents[i]) : sp.innerHTML}</span>`).join(sep));
    }
    box._orig = orig; btn.classList.add("on"); btn.textContent = "原文";
  }

  // translate a selection: a small 译 button appears under the selected text
  const selBtn = document.createElement("button");
  selBtn.className = "sel-tr hidden"; selBtn.textContent = "译 选中内容";
  const selPop = document.createElement("div");
  selPop.className = "tr-pop hidden";
  document.addEventListener("DOMContentLoaded", () => { $("#app").append(selBtn, selPop); });
  if (document.readyState !== "loading") $("#app")?.append(selBtn, selPop);
  let selText = "", selT = 0;
  document.addEventListener("selectionchange", () => {
    clearTimeout(selT);
    selT = setTimeout(() => {
      const sel = document.getSelection();
      let t = "";
      if (sel && !sel.isCollapsed && sel.rangeCount) {   // without our own labels (问题 / 方法 / 结果 …)
        const frag = sel.getRangeAt(0).cloneContents();
        for (const x of frag.querySelectorAll(".rh, .lbl, .w-lb, .tr-btn")) x.textContent = "";
        t = frag.textContent.replace(/­/g, "").replace(/\s+/g, " ").trim();
      }
      const node = sel && sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
      if (t.length < 2 || t.length > 4000 || !node || !node.closest("#feed, #sheet, #library")) { selBtn.classList.add("hidden"); return; }
      selText = t;
      const r = sel.getRangeAt(0).getBoundingClientRect(), app = $("#app").getBoundingClientRect();
      const top = Math.min(r.bottom - app.top + 10, app.height - 120);
      selBtn.style.top = Math.max(8, top) + "px";
      selBtn.style.left = Math.min(Math.max(8, r.left - app.left + r.width / 2 - 56), app.width - 128) + "px";
      selBtn.classList.remove("hidden");
    }, 350);
  });
  selBtn.addEventListener("pointerdown", (e) => e.preventDefault());   // keep the selection while tapping
  selBtn.addEventListener("click", async () => {
    const text = selText; selBtn.classList.add("hidden");
    selPop.innerHTML = `<div class="tp-src">${esc(text.length > 160 ? text.slice(0, 160) + "…" : text)}</div><div class="tp-out">翻译中…</div>`;
    selPop.classList.remove("hidden");
    try {
      const r = await api("/api/translate", { method: "POST", body: { texts: [text] }, timeout: 45000 });
      $(".tp-out", selPop).textContent = r.texts[0];
      $(".tp-out", selPop).setAttribute("lang", langAttr(r.lang));
    } catch (e) { selPop.classList.add("hidden"); trError(e); }
  });
  document.addEventListener("pointerdown", (e) => { if (!selPop.contains(e.target) && e.target !== selBtn) selPop.classList.add("hidden"); }, true);

  // ---------------------------------------------------------------- sheet / viewer
  function openSheet(html) {
    $("#sheet-content").innerHTML = html;
    $("#sheet").classList.remove("hidden");
  }
  const closeSheet = () => $("#sheet").classList.add("hidden");
  $(".sheet-backdrop").addEventListener("click", closeSheet);

  function openDetail(c) {
    const roles = c.roles || {}, tag = {};
    for (const [k, v] of Object.entries(roles)) tag[v] = k[0];
    const sents = c.sents && c.sents.length ? c.sents : [c.abstract];
    const g = c.glance || {};
    const facts = factsHTML(c);
    openSheet(`
      <div class="kicker">${esc(c.primary)} · ${esc(c.published)}${c.venue ? " · " + esc(c.venue) : ""}${tierText(c) ? " · " + tierText(c) : ""}</div>
      <button class="tr-btn sheet-tr" aria-label="翻译这篇">译</button>
      <h3 lang="en">${esc(c.title)}</h3>
      ${c.fig ? `<figure class="sheet-fig" data-zoom="${esc(abs(c.fig))}"><img alt="Key figure" src="${esc(abs(c.fig))}" onerror="this.parentNode.remove()"></figure>` : ""}
      ${g.name || (g.kinds || []).length ? `<div class="kick">${g.name ? `<span class="name">${esc(g.name)}</span>` : ""}${(g.kinds || []).map((k) => `<span class="kind">${esc(k)}</span>`).join("")}</div>` : ""}
      ${Object.keys(roles).length ? `<div class="legend"><span class="lg-p">问题</span><span class="lg-m">方法</span><span class="lg-r">结果</span><em>原文摘要，按句子作用着色</em></div>` : ""}
      <p class="abs" lang="en">${sents.map((t, i) => `<span class="${tag[i] ? "s-" + tag[i] : ""}">${hi(t)}</span>`).join(" ")}</p>
      ${facts ? `<div class="facts">${facts}</div>` : ""}
      <p class="authors-all">${c.authors.map(esc).join(", ")}</p>
      ${c.affiliations.length ? `<p class="meta-line">${c.affiliations.map(esc).join(" · ")}</p>` : ""}
      ${c.comment ? `<p class="meta-line">COMMENT · ${esc(c.comment)}</p>` : ""}
      <p class="meta-line">arXiv:${esc(c.id)} · ${esc(c.categories.join(" "))}</p>
      <div class="links">
        <button class="primary" data-u="${esc(c.pdf_url)}">PDF</button>
        <button data-u="${esc(c.html_url)}">HTML 全文</button>
        <button data-u="${esc(c.arxiv_url)}">arXiv 页面</button>
        ${c.doi ? `<button data-u="https://doi.org/${esc(c.doi)}">DOI</button>` : ""}
      </div>`);
    $$("#sheet-content [data-u]").forEach((b) => b.addEventListener("click", () => openUrl(b.dataset.u)));
    $("#sheet-content .sheet-fig")?.addEventListener("click", (e) => openViewer(e.currentTarget.dataset.zoom));
    $("#sheet-content")._orig = null;
    $("#sheet-content .sheet-tr").addEventListener("click", (e) => translateSheet(c, e.currentTarget));
  }

  function openNote(c, btn) {
    openSheet(`<div class="kicker">Marginalia · 笔记</div><h3>${esc(c.title)}</h3>
      <textarea id="note-text" rows="5" placeholder="写点想法，会出现在书房和导出里">${esc(c.note)}</textarea>
      <div class="btn-row" style="margin-top:12px"><button class="btn" id="note-save">保存</button><button class="btn ghost" id="note-cancel">取消</button></div>`);
    $("#note-cancel").onclick = closeSheet;
    $("#note-save").onclick = () => {
      c.note = $("#note-text").value.trim();
      sendEvent(c.id, "comment", { text: c.note });
      btn?.classList.toggle("on", !!c.note);
      closeSheet(); toast("笔记已保存");
    };
  }

  const viewer = $("#viewer");
  function openViewer(src) {
    if (!src) return;
    $("img", viewer).src = src;
    viewer.classList.remove("hidden", "zoom");
  }
  viewer.addEventListener("click", (e) => {
    if (e.target.tagName === "IMG") viewer.classList.toggle("zoom");
    else viewer.classList.add("hidden");
  });

  async function share(c) {
    try {
      if (plug("Share")) return await plug("Share").share({ title: c.title, text: c.title, url: c.arxiv_url, dialogTitle: "分享论文" });
      if (navigator.share) return await navigator.share({ title: c.title, url: c.arxiv_url });
      await navigator.clipboard.writeText(`${c.title}\n${c.arxiv_url}`); toast("链接已复制");
    } catch { /* user cancelled */ }
  }

  function openUrl(u) {
    if (plug("Browser")) plug("Browser").open({ url: u });
    else window.open(u, "_blank", "noopener");
  }

  // ---------------------------------------------------------------- library
  let libKind = "like";
  async function loadLibrary() {
    const list = $("#lib-list");
    list.innerHTML = '<div class="empty">翻书中…</div>';
    try {
      const r = await api(`/api/library?kind=${libKind}`);
      ls.set("lib." + libKind, r.cards);
      renderLibrary(r.cards);
    } catch {
      renderLibrary(ls.get("lib." + libKind, []), true);
    }
  }
  function renderLibrary(cards, offline) {
    const list = $("#lib-list");
    if (!cards.length) {
      list.innerHTML = `<div class="empty">${offline ? "连不上电脑，也没有缓存" : { like: "还没有喜欢的论文。<br>刷论文时双击卡片试试。", save: "书架还空着。", note: "还没写过笔记。", hidden: "没有被标为不感兴趣的论文。" }[libKind]}</div>`;
      return;
    }
    list.innerHTML = cards.map((c, i) => `
      <div class="lib-item" data-i="${i}">
        <div class="t"><span class="marks">${c.liked ? "♥" : ""}${c.saved ? "❘" : ""}</span>${esc(c.title)}</div>
        <div class="s">${esc(c.first_author)}${c.n_authors > 1 ? " et al." : ""} · ${esc(c.published)}${c.venue ? " · " + esc(c.venue) : ""} · ${esc(c.id)}</div>
        ${c.note ? `<div class="n">${esc(c.note)}</div>` : ""}
      </div>`).join("");
    $$(".lib-item", list).forEach((el) => el.addEventListener("click", () => {
      const c = cards[+el.dataset.i];
      openDetail(c);
      const links = $("#sheet-content .links");
      const mk = (label, fn) => { const b = document.createElement("button"); b.textContent = label; b.onclick = fn; links.appendChild(b); };
      if (libKind === "hidden") mk("恢复推荐", () => { sendEvent(c.id, "unhide"); closeSheet(); setTimeout(loadLibrary, 300); });
      else {
        mk(c.liked ? "取消喜欢" : "喜欢", () => { sendEvent(c.id, c.liked ? "unlike" : "like"); closeSheet(); setTimeout(loadLibrary, 300); });
        mk(c.saved ? "取消收藏" : "收藏", () => { sendEvent(c.id, c.saved ? "unsave" : "save"); closeSheet(); setTimeout(loadLibrary, 300); });
        mk("笔记", () => openNote(c));
      }
    }));
  }
  $("#lib-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    libKind = b.dataset.k;
    $$("#lib-tabs button").forEach((x) => x.classList.toggle("on", x === b));
    loadLibrary();
  });
  $("#exp-go").addEventListener("click", async () => {
    const kind = $("#exp-kind").value, fmt = $("#exp-fmt").value;
    try {
      const r = await api(`/api/export?kind=${kind}&fmt=${fmt}`, { raw: true });
      const text = await r.text();
      const ext = { bibtex: "bib", md: "md", csv: "csv", json: "json" }[fmt];
      const name = `paperscroll-${kind}-${today()}.${ext}`;
      if (native && plug("Filesystem") && plug("Share")) {
        const w = await plug("Filesystem").writeFile({ path: name, data: text, directory: "CACHE", encoding: "utf8" });
        await plug("Share").share({ title: name, files: [w.uri], dialogTitle: "导出到…" });
      } else {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
        a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      }
    } catch (e) { if (!/cancel/i.test(String(e))) toast("导出失败：" + (e.message || e)); }
  });

  // ---------------------------------------------------------------- settings
  let cats = [];
  async function loadSettings() {
    try {
      const [p, s] = await Promise.all([api("/api/profile"), api("/api/status")]);
      $("#s-topic").value = p.topic; $("#s-keywords").value = p.keywords;
      renderPrefs($("#prefs"), p.prefs);
      cats = s.categories.slice(); renderCats();
      $("#s-window").value = String(s.window_days);
      renderStatus(s);
      api("/api/recsys").then(renderRecsys).catch(() => { $("#s-recsys").textContent = "—"; });
      api("/api/translate/info").then(renderTranslate).catch(() => { $("#s-tr-usage").textContent = "—"; });
    } catch { $("#s-status").textContent = "连不上电脑端"; }
    $("#s-server").value = server() || (native ? location.origin : DEFAULT_SERVER);
    $("#server-section").classList.toggle("hidden", !native);
  }
  function renderStatus(s) {
    const j = s.job || {};
    const st = j.state === "running" ? "同步中 · " + esc(j.step) + " " + esc(j.ingest || "") + " " + esc(j.step === "embedding" ? j.embed : j.step === "Semantic Scholar" ? j.s2 : j.step === "OpenAlex" ? j.openalex : "")
      : j.state === "error" ? "出错 " + esc(j.last_error) : "空闲";
    $("#s-status").innerHTML = `论文 ${s.papers.toLocaleString()} 篇 · 索引 ${s.indexed.toLocaleString()}<br>
      引用/出处补全：OpenAlex ${(s.oa_enriched || 0).toLocaleString()} · S2 ${s.s2_enriched.toLocaleString()}${j.openalex ? `<br>OpenAlex：${esc(j.openalex)}` : ""}<br>
      最新 ${esc((s.newest || "—").slice(0, 10))} · 上次同步 ${esc(j.last_sync || "—")}<br>
      每天 ${esc(s.sync_times.join(" / "))} 自动更新 · 状态 ${st}
      ${s.has_openalex_key ? "" : "<br>未设 OpenAlex key：用共享免费额度，每天补约 2 万篇"}`;
  }
  function renderTranslate(t) {
    $("#s-tr-lang").innerHTML = Object.entries(t.langs).map(([k, v]) => `<option value="${esc(k)}" ${k === t.lang ? "selected" : ""}>${esc(v)}</option>`).join("");
    const u = t.usage;
    $("#s-tr-usage").textContent = !t.has_key ? "未设置 DeepL key：翻译不可用"
      : u && u.limit ? `DeepL 本月已用 ${u.used.toLocaleString()} / ${u.limit.toLocaleString()} 字符（每篇约 1,500）`
      : "DeepL key 已设置";
  }
  $("#s-tr-save").addEventListener("click", async () => {
    const body = { translate_lang: $("#s-tr-lang").value };
    const k = $("#s-deepl").value.trim(); if (k) body.deepl_api_key = k;
    try {
      await api("/api/config", { method: "PUT", body }); $("#s-deepl").value = "";
      state.cards.forEach((c) => { c._tr = null; });
      toast("已保存"); renderTranslate(await api("/api/translate/info"));
    } catch (e) { toast("保存失败：" + e.message); }
  });
    function renderRecsys(r) {
    if (r.version === "v1") { $("#s-recsys").textContent = "当前使用旧版推荐（只用课题和喜欢）"; return; }
    const ints = r.interests || [];
    $("#s-recsys").innerHTML = (ints.length
      ? ints.map((x) => `· ${esc(x.label || "未命名")} <span class="muted">${x.papers} 篇</span>`).join("<br>")
      : "还在了解你：多刷几篇，看得久的、点开图或精读的会被记住") +
      `<br>你平时每篇看 ${esc(String(r.median_dwell))} 秒；快速划过的会少推`;
  }
    function renderCats() {
    $("#s-cats").innerHTML = cats.map((c, i) => `<span class="chip">${esc(c)}<button data-i="${i}" aria-label="删除 ${esc(c)}">×</button></span>`).join("");
  }
  $("#s-cats").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { cats.splice(+b.dataset.i, 1); renderCats(); } });
  $("#s-cat-add").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const v = e.target.value.trim(); if (v && !cats.includes(v)) cats.push(v);
    e.target.value = ""; renderCats();
  });
  $("#s-save-profile").addEventListener("click", async () => {
    await api("/api/profile", { method: "PUT", body: { topic: $("#s-topic").value, keywords: $("#s-keywords").value, prefs: readPrefs($("#prefs")) } });
    toast("已更新");
    refreshFeed(true); showView("feed");
  });
  $("#s-save-lib").addEventListener("click", async () => {
    const body = { categories: cats, window_days: +$("#s-window").value };
    const key = $("#s-s2key").value.trim(); if (key) body.s2_api_key = key;
    const oak = $("#s-oakey").value.trim(); if (oak) body.openalex_api_key = oak;
    try { const s = await api("/api/config", { method: "PUT", body }); $("#s-s2key").value = ""; $("#s-oakey").value = ""; renderStatus(s); toast("已保存，后台开始同步"); }
    catch (e) { toast("保存失败：" + e.message); }
  });
  $("#s-sync").addEventListener("click", async () => { const r = await api("/api/sync", { method: "POST" }); toast(r.started ? "已开始同步" : "已经在同步了"); setTimeout(loadSettings, 800); });
  $("#s-reset-seen").addEventListener("click", async () => { await api("/api/reset_seen", { method: "POST" }); toast("已重置"); refreshFeed(true); });
  $("#s-save-server").addEventListener("click", () => {
    const v = ($("#s-server").value.trim() || DEFAULT_SERVER).replace(/\/$/, "");
    ls.set("server", v);
    if (!bundled && v !== location.origin) { location.href = v + "/"; return; }   // the UI lives on the PC: go there
    toast("已保存"); refreshFeed(true); loadSettings();
  });
  $("#s-density").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; reading.density = b.dataset.v; ls.set("density", reading.density); applyReading(); rerenderCards(); });
  $("#s-theme").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; reading.theme = b.dataset.v; ls.set("theme", reading.theme); applyReading(); });
  $("#s-font").addEventListener("input", (e) => { reading.font = +e.target.value; ls.set("font", reading.font); applyReading(); requestAnimationFrame(refitAll); });

  // ---------------------------------------------------------------- navigation
  function showView(v) {
    $$(".view").forEach((x) => x.classList.toggle("active", x.id === "view-" + v));
    $$(".tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
    if (v !== "feed") leaveCurrent(); else requestAnimationFrame(refitAll);
    if (v === "library") loadLibrary();
    if (v === "settings") loadSettings();
  }
  $(".tabbar").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) showView(b.dataset.view); });
  if (plug("App")) plug("App").addListener("backButton", () => {
    if (!viewer.classList.contains("hidden")) viewer.classList.add("hidden");
    else if (!$("#sheet").classList.contains("hidden")) closeSheet();
    else if (!$("#view-feed").classList.contains("active")) showView("feed");
    else plug("App").minimizeApp();
  });

  // ---------------------------------------------------------------- boot
  const EXAMPLES = ["bimanual manipulation, diffusion policy", "vision-language-action models", "video generation, controllability",
    "LLM reasoning with reinforcement learning", "sim-to-real robot learning", "3D gaussian splatting"];
  async function boot() {
    applyReading();
    renderCount(false);
    state.pin = new URLSearchParams(location.search).get("p");
    let profile = null;
    try { profile = await api("/api/profile", { timeout: 10000 }); } catch { /* offline: fall through to cached feed */ }
    if (profile && !profile.topic) {
      renderPrefs($("#o-prefs"), profile.prefs);
      $("#ob-examples").innerHTML = EXAMPLES.map((x) => `<button>${esc(x)}</button>`).join("");
      $("#ob-examples").onclick = (e) => {
        const b = e.target.closest("button"); if (!b) return;
        const t = $("#o-topic"); t.value = t.value.trim() ? t.value.trim() + "; " + b.textContent : b.textContent;
      };
      $("#onboard").classList.remove("hidden");
      $("#o-go").onclick = async () => {
        const topic = $("#o-topic").value.trim();
        if (!topic) { toast("先写一句你的研究方向"); return; }
        await api("/api/profile", { method: "PUT", body: { topic, keywords: $("#o-keywords").value, prefs: readPrefs($("#o-prefs")) } });
        $("#onboard").classList.add("hidden");
        loadMore();
      };
      return;
    }
    loadMore();
    checkUpdate();
    flushPending();
    setInterval(flushPending, 60000);
  }
  boot();
})();
