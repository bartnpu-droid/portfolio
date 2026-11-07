/* AI receptionist chat widget.
 *
 * Add to any website with one line:
 *   <script src="https://YOUR-SERVER/static/widget.js" data-title="BrightSmile Dental" defer></script>
 *
 * Options (data-attributes on the script tag):
 *   data-api          server URL (default: the server widget.js is loaded from)
 *   data-target       CSS selector of an element to also show the chat inline
 *   data-launcher     text of the floating button, or "none" to hide it
 *   data-accent       brand colour, e.g. "#2e7d64"
 *   data-theme        "light" (default) or "dark"
 *   data-suggestions  quick questions separated by "|"
 *
 * Any element with data-ask="Your question" opens the chat and asks it.
 * From JavaScript: window.AIChat.open("Your question")
 * All chat windows on a page show the same conversation, and it survives moving between pages.
 */
(function () {
  "use strict";
  const script = document.currentScript;
  const API = (script.dataset.api || new URL(script.src).origin).replace(/\/$/, "");
  const TITLE = script.dataset.title || "Virtual receptionist";
  const LAUNCHER = script.dataset.launcher || "Ask AI receptionist";
  const ACCENT = script.dataset.accent || "#2e7d64";
  const DARK = script.dataset.theme === "dark";
  const SUGGESTIONS = (script.dataset.suggestions ||
    "How much is a check-up?|Are you open on Saturday?|I'd like to book an appointment|I have toothache").split("|");
  const GREETING = `Hi! I'm the ${TITLE} assistant. I can answer questions about treatments, prices and opening hours, and request an appointment for you.`;
  const LOG_KEY = "bs_log", MAX_LOG = 40, MAX_LEN = 1000;

  const CSS = `
  .bs-chat,.bs-launch{--bs-ink:#132a2e;--bs-muted:#5a6d6f;--bs-line:#dbe3df;--bs-paper:#fff;--bs-tint:#f3f6f4;--bs-accent:${ACCENT};--bs-me:#e3efe9;
    --bs-on-accent:#fff;--bs-launch-bg:var(--bs-accent);--bs-launch-fg:#fff;
    font:15px/1.45 ${DARK ? '"Geist",' : ""}"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif;box-sizing:border-box}
  .bs-dark.bs-chat,.bs-dark.bs-launch{--bs-ink:#eef2f0;--bs-muted:#97a8a4;--bs-line:rgba(220,228,225,.13);--bs-paper:#142224;--bs-tint:#0f1a1c;
    --bs-me:#24383a;--bs-on-accent:#0d1618;--bs-launch-bg:#0d1618;--bs-launch-fg:#f4f1ea}
  .bs-dark .bs-dot{color:#0d1618}
  .bs-dark .bs-in{background:#0f1a1c}
  .bs-dark.bs-launch{box-shadow:0 0 0 1px rgba(200,164,106,.55),0 14px 34px rgba(0,0,0,.35)}
  .bs-dark.bs-launch svg{color:var(--bs-accent)}
  .bs-dark .bs-msg a{color:var(--bs-accent)}
  .bs-chat{color:var(--bs-ink);display:flex;flex-direction:column;background:var(--bs-paper);border:1px solid var(--bs-line);border-radius:20px;overflow:hidden}
  .bs-chat *,.bs-launch *{box-sizing:border-box}
  .bs-head{display:flex;align-items:center;gap:10px;padding:12px 10px 12px 16px;border-bottom:1px solid var(--bs-line)}
  .bs-dot{width:36px;height:36px;border-radius:50%;background:var(--bs-accent);color:var(--bs-on-accent);display:grid;place-items:center;font-weight:700;font-size:13px;flex:none}
  .bs-title{font-weight:600}.bs-sub{font-size:12px;color:var(--bs-muted);display:flex;align-items:center;gap:6px}
  .bs-sub:before{content:"";width:7px;height:7px;border-radius:50%;background:#3cb371}
  .bs-actions{margin-left:auto;display:flex}
  .bs-icon{border:0;background:none;color:var(--bs-muted);cursor:pointer;padding:8px;border-radius:10px;display:grid;place-items:center}
  .bs-icon:hover{color:var(--bs-ink);background:var(--bs-tint)}
  .bs-icon svg{width:18px;height:18px}
  .bs-log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:var(--bs-tint);overscroll-behavior:contain}
  .bs-msg{max-width:85%;padding:10px 13px;border-radius:16px;white-space:pre-wrap;overflow-wrap:anywhere}
  .bs-bot{background:var(--bs-paper);border:1px solid var(--bs-line);border-bottom-left-radius:5px;align-self:flex-start}
  .bs-me{background:var(--bs-me);border-bottom-right-radius:5px;align-self:flex-end}
  .bs-msg a{color:var(--bs-accent)}
  .bs-typing{display:inline-flex;gap:4px;padding:14px}
  .bs-typing i{width:6px;height:6px;border-radius:50%;background:var(--bs-muted);opacity:.4;animation:bs-b 1s infinite}
  .bs-typing i:nth-child(2){animation-delay:.15s}.bs-typing i:nth-child(3){animation-delay:.3s}
  @keyframes bs-b{50%{opacity:1;transform:translateY(-3px)}}
  .bs-sugs{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 12px;background:var(--bs-tint)}
  .bs-sugs[hidden]{display:none}
  .bs-sug{border:1px solid var(--bs-line);background:var(--bs-paper);border-radius:999px;padding:7px 12px;font:inherit;font-size:13px;color:var(--bs-ink);cursor:pointer}
  .bs-sug:hover{border-color:var(--bs-accent)}
  .bs-form{display:flex;gap:8px;padding:10px;border-top:1px solid var(--bs-line);background:var(--bs-paper)}
  .bs-in{flex:1;border:1px solid var(--bs-line);border-radius:12px;padding:11px 12px;font:inherit;font-size:16px;color:inherit;min-width:0;background:var(--bs-paper)}
  .bs-in:focus{outline:2px solid var(--bs-accent);outline-offset:-1px}
  .bs-send{border:0;border-radius:12px;background:var(--bs-accent);color:var(--bs-on-accent);padding:0 16px;font:inherit;font-weight:600;cursor:pointer}
  .bs-send:disabled{opacity:.5;cursor:default}
  .bs-note{font-size:11px;color:var(--bs-muted);text-align:center;padding:0 10px 8px;background:var(--bs-paper)}
  .bs-panel{position:fixed;right:20px;bottom:88px;width:min(390px,calc(100vw - 32px));height:min(620px,calc(100vh - 112px));z-index:2147483001;
    box-shadow:0 24px 60px rgba(19,42,46,.24);visibility:hidden;opacity:0;transform:translateY(12px) scale(.98);transform-origin:bottom right;
    transition:opacity .18s,transform .18s,visibility 0s .18s}
  .bs-panel.bs-open{visibility:visible;opacity:1;transform:none;transition:opacity .18s,transform .18s}
  .bs-launch{position:fixed;right:20px;bottom:20px;z-index:2147483000;display:flex;align-items:center;gap:10px;border:0;border-radius:999px;
    background:var(--bs-launch-bg);color:var(--bs-launch-fg);padding:13px 20px 13px 15px;font-weight:500;cursor:pointer;
    box-shadow:0 10px 28px rgba(19,42,46,.26);transition:opacity .2s,transform .2s}
  .bs-launch svg{width:22px;height:22px;flex:none}
  .bs-launch .bs-x{display:none}
  .bs-launch.bs-active{padding:13px}
  .bs-launch.bs-active span,.bs-launch.bs-active .bs-c{display:none}
  .bs-launch.bs-active .bs-x{display:block}
  .bs-launch.bs-away{opacity:0;transform:translateY(16px);pointer-events:none}
  .bs-launch:focus-visible,.bs-chat button:focus-visible{outline:3px solid var(--bs-ink);outline-offset:2px}
  @media (max-width:560px){
    .bs-launch{right:16px;bottom:16px;padding:15px}.bs-launch span{display:none}
    .bs-panel{left:8px;right:8px;bottom:80px;width:auto;height:calc(100vh - 96px);height:calc(100dvh - 96px)}
  }
  @media (prefers-reduced-motion:reduce){.bs-typing i{animation:none;opacity:.7}.bs-panel,.bs-panel.bs-open,.bs-launch{transition:none}}
  `;
  const ICON = {
    chat: '<svg class="bs-c" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" stroke-width="2.6"/></svg>',
    close: '<svg class="bs-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    restart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>',
  };

  // ---------- shared state: one conversation for every chat window on the page
  function newId() {
    return (window.crypto && crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now()).replace(/[^A-Za-z0-9-]/g, "");
  }
  let session;
  try {
    session = localStorage.getItem("bs_session");
    if (!session) { session = newId(); localStorage.setItem("bs_session", session); }
  } catch (_) { session = "s" + Date.now() + Math.floor(Math.random() * 1e6); }
  let log = [];
  try { log = JSON.parse(sessionStorage.getItem(LOG_KEY) || "[]"); if (!Array.isArray(log)) log = []; } catch (_) { log = []; }
  let busy = false;
  const views = [];
  function save() { try { sessionStorage.setItem(LOG_KEY, JSON.stringify(log.slice(-MAX_LOG))); } catch (_) {} }
  function push(who, text) { const m = { who, text }; log.push(m); save(); views.forEach((v) => v.add(m)); }
  function setBusy(b) { busy = b; views.forEach((v) => v.busy(b)); }

  async function ask(text) {
    text = String(text || "").trim().slice(0, MAX_LEN);
    if (!text || busy) return;
    push("me", text);
    setBusy(true);
    let reply;
    try {
      const r = await fetch(API + "/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session, message: text }),
      });
      const data = await r.json().catch(() => ({}));
      reply = data.reply || data.error || "The assistant is unavailable right now. Please try again in a minute or call the clinic.";
    } catch (_) {
      reply = "No connection. Check your internet and try again.";
    }
    setBusy(false);
    push("bot", reply);
  }

  function reset() {
    if (busy) return;
    log = []; save();
    session = newId();
    try { localStorage.setItem("bs_session", session); } catch (_) {}
    views.forEach((v) => v.render());
  }

  // ---------- UI
  const style = document.createElement("style"); style.textContent = CSS; document.head.appendChild(style);
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function linkify(node, text) {
    for (const p of String(text).split(/(https?:\/\/[^\s)]+)/g)) {
      if (/^https?:\/\//.test(p)) { const a = el("a", null, p); a.href = p; a.target = "_blank"; a.rel = "noopener"; node.append(a); }
      else node.append(document.createTextNode(p));
    }
  }
  function iconButton(svg, label) { const b = el("button", "bs-icon"); b.type = "button"; b.innerHTML = svg; b.setAttribute("aria-label", label); b.title = label; return b; }

  function makeView(kind) {
    const box = el("div", "bs-chat bs-" + kind + (DARK ? " bs-dark" : ""));
    const head = el("div", "bs-head");
    const meta = el("div"); meta.append(el("div", "bs-title", TITLE), el("div", "bs-sub", "Online, replies in seconds"));
    const actions = el("div", "bs-actions");
    const restart = iconButton(ICON.restart, "Start a new conversation"); restart.onclick = reset;
    actions.append(restart);
    head.append(el("div", "bs-dot", "AI"), meta, actions);
    const logEl = el("div", "bs-log"); logEl.setAttribute("role", "log"); logEl.setAttribute("aria-live", "polite");
    logEl.setAttribute("data-lenis-prevent", "");          // keep native scrolling inside the chat on smooth-scroll sites
    const sugs = el("div", "bs-sugs");
    for (const s of SUGGESTIONS) { const b = el("button", "bs-sug", s); b.type = "button"; b.onclick = () => ask(s); sugs.append(b); }
    const form = el("form", "bs-form");
    const input = el("input", "bs-in"); input.placeholder = "Ask about treatments, prices, booking…"; input.maxLength = MAX_LEN;
    input.setAttribute("aria-label", "Your message"); input.autocomplete = "off";
    const send = el("button", "bs-send", "Send"); send.type = "submit";
    form.append(input, send);
    box.append(head, logEl, sugs, form, el("div", "bs-note", "AI assistant, not medical advice. In an emergency call 999."));

    function bubble(m) { const n = el("div", "bs-msg " + (m.who === "me" ? "bs-me" : "bs-bot")); linkify(n, m.text); return n; }
    function scroll() { logEl.scrollTop = logEl.scrollHeight; }
    let typing = null;
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (busy || !input.value.trim()) return;
      const text = input.value; input.value = ""; ask(text);
    });
    const v = {
      box, head, input, actions,
      render() {
        typing = null;
        logEl.replaceChildren(bubble({ who: "bot", text: GREETING }), ...log.map(bubble));
        sugs.hidden = log.length > 0;
        if (busy) v.busy(true);
        scroll();
      },
      add(m) { if (typing) { typing.remove(); typing = null; } logEl.append(bubble(m)); sugs.hidden = true; if (busy) v.busy(true); scroll(); },
      busy(b) {
        send.disabled = b;
        if (b && !typing) { typing = el("div", "bs-msg bs-bot bs-typing"); typing.append(el("i"), el("i"), el("i")); typing.setAttribute("aria-label", "Typing"); logEl.append(typing); scroll(); }
        if (!b && typing) { typing.remove(); typing = null; }
      },
    };
    views.push(v);
    v.render();
    return v;
  }

  // inline chat (optional)
  const target = script.dataset.target ? document.querySelector(script.dataset.target) : null;
  let inline = null;
  if (target) { inline = makeView("inline"); inline.box.style.height = "100%"; target.append(inline.box); }

  // floating button + panel
  let launcher = null, panel = null, panelOpen = false, inlineVisible = false;
  function syncLauncher() {
    if (!launcher) return;
    launcher.classList.toggle("bs-active", panelOpen);
    launcher.classList.toggle("bs-away", inlineVisible && !panelOpen);
    launcher.setAttribute("aria-expanded", String(panelOpen));
    launcher.setAttribute("aria-label", panelOpen ? "Close chat" : LAUNCHER);
  }
  function openPanel() {
    if (!panel) {
      panel = makeView("panel");
      panel.box.classList.add("bs-panel"); panel.box.id = "bs-panel";
      panel.box.setAttribute("role", "dialog"); panel.box.setAttribute("aria-label", TITLE + " chat");
      const close = iconButton(ICON.close.replace('class="bs-x" ', ""), "Close chat"); close.onclick = closePanel;
      panel.actions.append(close);
      panel.box.addEventListener("keydown", (e) => { if (e.key === "Escape") closePanel(); });
      document.body.append(panel.box);
      panel.box.getBoundingClientRect();   // start the opening transition from the closed state
    }
    panelOpen = true; panel.box.classList.add("bs-open"); syncLauncher();
    panel.input.focus({ preventScroll: true });
  }
  function closePanel() {
    if (!panel) return;
    panelOpen = false; panel.box.classList.remove("bs-open"); syncLauncher();
    if (launcher) launcher.focus({ preventScroll: true });
  }
  if (LAUNCHER !== "none") {
    launcher = el("button", "bs-launch" + (DARK ? " bs-dark" : "")); launcher.type = "button";
    launcher.innerHTML = ICON.chat + ICON.close; launcher.append(el("span", null, LAUNCHER));
    launcher.setAttribute("aria-controls", "bs-panel");
    launcher.onclick = () => (panelOpen ? closePanel() : openPanel());
    document.body.append(launcher);
    syncLauncher();
  }
  if (inline && launcher && "IntersectionObserver" in window) {
    new IntersectionObserver(([en]) => { inlineVisible = en.isIntersecting; syncLauncher(); }, { threshold: 0.25 }).observe(inline.box);
  }

  function inView(node) { const r = node.getBoundingClientRect(); return r.top < innerHeight * 0.8 && r.bottom > innerHeight * 0.2; }
  function open(text) {
    if (inline && (inView(inline.box) || !launcher)) {
      if (!inView(inline.box)) inline.box.scrollIntoView({ block: "center" });
      inline.input.focus({ preventScroll: true });
    } else if (launcher) {
      openPanel();
    }
    if (text) ask(text);
  }
  document.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target.closest("[data-ask]") : null;
    if (!t) return;
    e.preventDefault();
    open(t.getAttribute("data-ask"));
  });

  window.AIChat = { open, ask, reset };
  document.dispatchEvent(new CustomEvent("aichat:ready"));
})();
