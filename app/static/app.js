/* Deutsch Lernen — interfaz (JavaScript sin dependencias) */
"use strict";

// ====================================================================== utilidades
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const gcls = (art) => ({ der: "g-der", die: "g-die", das: "g-das", pl: "g-pl" }[art] || "g-none");
const LEVELS = ["A1", "A2", "B1", "B2"];
const SKILL_ICON = { vocab: "🧠", gram: "🧩", listen: "🎧", read: "📖", write: "✍️", speak: "🗣️" };
const SKILL_NAME = { vocab: "Vocabulario", gram: "Gramática", listen: "Escucha", read: "Lectura", write: "Escritura", speak: "Pronunciación" };

const api = {
  async get(p) { const r = await fetch(p); if (!r.ok) throw new Error(await r.text()); return r.json(); },
  async post(p, d) {
    const r = await fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d || {}) });
    return r.json();
  },
};

function toast(msg, ms = 2600) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

function wordHTML(c) {
  // artículo coloreado + palabra
  if (c.art === "der" || c.art === "die" || c.art === "das") return `<span class="a">${c.art}</span> ${esc(c.de)}`;
  if (c.art === "pl") return `<span class="a">die</span> ${esc(c.de)}`;
  return esc(c.de);
}

function colorArticles(text) {
  // colorea der/die/das al principio de una opción (para opciones en alemán)
  const m = /^(der|die|das) (.+)$/.exec(text);
  return m ? `<span class="${m[1]}">${m[1]}</span> ${esc(m[2])}` : esc(text);
}

function norm(s) {
  return String(s).trim().toLowerCase().replace(/ß/g, "ss").replace(/[.,!?¿¡;:«»"“”„]/g, "").replace(/\s+/g, " ");
}
function lev(a, b) {
  const m = a.length, n = b.length;
  if (Math.abs(m - n) > 2) return 9;
  const d = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)]);
  for (let j = 1; j <= n; j++) d[0][j] = j;
  for (let i = 1; i <= m; i++) for (let j = 1; j <= n; j++)
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[m][n];
}

// ====================================================================== estado
const S = { settings: {}, lib: null, voices: [] };

function applyTheme() {
  document.documentElement.setAttribute("data-theme", S.settings.theme === "dark" ? "dark" : "light");
}

// ====================================================================== voz
const TTS = {
  warned: false,
  init() {
    if (!("speechSynthesis" in window)) return;
    const load = () => { S.voices = speechSynthesis.getVoices().filter((v) => v.lang && v.lang.toLowerCase().startsWith("de")); };
    load();
    speechSynthesis.onvoiceschanged = load;
  },
  systemVoice(swiss) {
    const vs = S.voices;
    if (!vs.length) return null;
    if (swiss) { const ch = vs.find((v) => /de[-_]CH/i.test(v.lang)); if (ch) return ch; }
    const chosen = vs.find((v) => v.name === S.settings.system_voice);
    if (chosen) return chosen;
    const pref = ["Anna", "Petra", "Helena", "Markus", "Yannick", "Martin"];
    for (const p of pref) { const v = vs.find((x) => x.name.startsWith(p) && /de[-_]DE/i.test(x.lang)); if (v) return v; }
    return vs.find((v) => /de[-_]DE/i.test(v.lang)) || vs[0];
  },
  current: null,
  url(text, opts) {
    const rate = (Number(S.settings.rate) || 0.95) * (opts.slow ? 0.7 : 1);
    const voice = opts.swiss ? S.settings.azure_voice_ch : S.settings.azure_voice;
    return `/api/tts?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(voice)}&rate=${rate.toFixed(2)}`;
  },
  preload(text, opts = {}) { fetch(this.url(text, opts)).catch(() => {}); },
  async speak(text, opts = {}) {
    if (!text) return;
    const rate = (Number(S.settings.rate) || 0.95) * (opts.slow ? 0.7 : 1);
    if (this.current) { this.current.pause(); this.current = null; }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    if (S.settings.voice_engine === "azure" && S.settings.azure_key_set) {
      try {
        const r = await fetch(this.url(text, opts));
        if (r.ok) {
          const url = URL.createObjectURL(await r.blob());
          const a = new Audio(url);
          this.current = a;
          await a.play();
          return;
        }
        if (!this.warned) { toast("No se pudo usar la voz de Azure; uso la voz del Mac."); this.warned = true; }
      } catch (e) { /* sin conexión: voz del sistema */ }
    }
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    const v = this.systemVoice(opts.swiss);
    if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = "de-DE"; }
    u.rate = rate;
    speechSynthesis.speak(u);
  },
};

// ====================================================================== estructura
function shell(active, content) {
  const nav = [["hoy", "☀️", "Hoy"], ["ruta", "🧭", "Ruta"], ["apuntes", "📚", "Apuntes"], ["progreso", "📈", "Progreso"]];
  return `<div class="app">
    <nav class="rail" aria-label="Secciones">
      <a class="brand" href="#/hoy" aria-label="Inicio"><span class="b1"></span><span class="b2"></span><span class="b3"></span></a>
      ${nav.map(([id, ic, label]) => `<button class="nav ${active === id ? "on" : ""}" data-go="#/${id}"><span class="ic">${ic}</span>${label}</button>`).join("")}
      <div class="spacer"></div>
      <button class="nav ${active === "ajustes" ? "on" : ""}" data-go="#/ajustes"><span class="ic">⚙️</span>Ajustes</button>
    </nav>
    <main class="main" id="main">${content}</main>
  </div>`;
}

function mount(active, html) {
  $("#root").innerHTML = shell(active, html);
  $$("[data-go]").forEach((b) => b.addEventListener("click", () => { location.hash = b.dataset.go; }));
  window.scrollTo(0, 0);
}

// ====================================================================== router
async function route() {
  const parts = (location.hash || "#/hoy").slice(2).split("/").map(decodeURIComponent);
  const [view, a, b] = parts;
  try {
    if (!S.settings.placement_done && view !== "test" && view !== "bienvenida") { location.hash = "#/bienvenida"; return; }
    if (view === "bienvenida") return viewWelcome();
    if (view === "test") return viewPlacement();
    if (view === "ruta") return viewRoute();
    if (view === "apuntes") return viewLibrary(a || "vocab", b);
    if (view === "progreso") return viewProgress();
    if (view === "ajustes") return viewSettings();
    return viewHome();
  } catch (e) {
    console.error(e);
    mount("", `<div class="card"><h2>Algo no ha cargado</h2><p class="muted">${esc(e.message)}</p><button class="btn" onclick="location.reload()">Volver a cargar</button></div>`);
  }
}

// ====================================================================== bienvenida y test
function viewWelcome() {
  let minutes = 30;
  $("#root").innerHTML = `<div class="onboard"><div class="card">
    <div class="brand" style="margin:0 0 20px"><span class="b1"></span><span class="b2"></span><span class="b3"></span></div>
    <h1>Hallo! Empecemos.</h1>
    <p class="muted">Cada día tendrás una sesión corta, dividida en bloques pequeños. Los colores te ayudan a recordar el género: <span class="art g-der">der</span> <span class="art g-die">die</span> <span class="art g-das">das</span>.</p>
    <label class="field" for="nm">¿Cómo te llamas? <span class="muted small">(opcional)</span></label>
    <input id="nm" type="text" placeholder="Tu nombre" value="${esc(S.settings.name || "")}">
    <p class="field" style="margin-top:20px">¿Cuánto tiempo al día?</p>
    <div class="choices">${[15, 20, 30, 45].map((m) => `<button class="chip ${m === 30 ? "on" : ""}" data-m="${m}">${m} min</button>`).join("")}</div>
    <div class="row">
      <button class="btn primary big" id="go-test">Hacer el test de nivel · 5 min</button>
      <button class="btn ghost" id="go-a1">Empezar desde A1</button>
    </div>
  </div></div>`;
  $$("[data-m]").forEach((b) => b.addEventListener("click", () => {
    minutes = Number(b.dataset.m);
    $$("[data-m]").forEach((x) => x.classList.toggle("on", x === b));
  }));
  const save = async (extra) => {
    const name = $("#nm").value.trim();
    await api.post("/api/settings", { name, minutes, ...extra });
    Object.assign(S.settings, { name, minutes, ...extra });
  };
  $("#go-test").addEventListener("click", async () => { await save({}); location.hash = "#/test"; });
  $("#go-a1").addEventListener("click", async () => {
    await save({ level: "A1", placement_done: true });
    location.hash = "#/hoy";
  });
}

async function viewPlacement() {
  const qs = await api.get("/api/placement");
  let i = 0;
  const scores = { A1: 0, A2: 0, B1: 0, B2: 0 };
  const seen = { A1: 0, A2: 0, B1: 0, B2: 0 };
  const draw = () => {
    if (i >= qs.length) return done();
    const q = qs[i];
    $("#root").innerHTML = `<div class="onboard"><div class="card">
      <div class="row" style="justify-content:space-between"><span class="lv">${q.level}</span><span class="muted small">${i + 1} / ${qs.length}</span></div>
      <div class="bar" style="margin:14px 0 26px"><i style="width:${(i / qs.length) * 100}%"></i></div>
      <p class="de" style="font-size:1.6rem;margin:0 0 18px">${esc(q.q)}</p>
      <div class="options">${q.options.map((o, k) => `<button class="opt de-opt" data-k="${k}"><span class="n">${k + 1}</span>${esc(o)}</button>`).join("")}</div>
      <p class="muted small" style="margin-top:18px">Si no lo sabes, elige «no lo sé». No pasa nada: así el test acierta mejor.</p>
      <button class="btn ghost" id="dunno">No lo sé</button>
    </div></div>`;
    const pick = (k) => {
      seen[q.level] += 1;
      if (k === q.answer) scores[q.level] += 1;
      i += 1;
      // si un nivel queda claramente por debajo, terminamos antes
      if (seen[q.level] === 6 && scores[q.level] <= 2) return done();
      draw();
    };
    $$(".opt").forEach((b) => b.addEventListener("click", () => pick(Number(b.dataset.k))));
    $("#dunno").addEventListener("click", () => pick(-1));
    document.onkeydown = (e) => { const n = Number(e.key); if (n >= 1 && n <= q.options.length) pick(n - 1); };
  };
  const done = async () => {
    document.onkeydown = null;
    const r = await api.post("/api/placement", { scores });
    S.settings.level = r.level;
    S.settings.placement_done = true;
    const desc = { A1: "Empezamos por la base: saludos, compras, transporte y el género de las palabras.", A2: "Ya tienes la base. Toca el pasado, el dativo y la vida diaria.", B1: "Vamos a por el alemán de trabajo: clientes, diseño y entrevistas.", B2: "Pulimos registro formal, argumentación y vocabulario técnico." }[r.level];
    $("#root").innerHTML = `<div class="onboard"><div class="card" style="text-align:center">
      <div class="level current" style="display:block"><div class="badge" style="margin:0 auto 18px;width:96px;height:96px;font-size:2rem">${r.level}</div></div>
      <h1>Empiezas en ${r.level}</h1>
      <p class="muted">${desc}</p>
      <p class="small muted">${LEVELS.map((l) => `${l}: ${scores[l]}/6`).join(" · ")}</p>
      <button class="btn primary big" id="start">Ir a mi primer día</button>
    </div></div>`;
    $("#start").addEventListener("click", () => { location.hash = "#/hoy"; });
  };
  draw();
}

// ====================================================================== inicio
async function viewHome() {
  const h = await api.get("/api/home");
  const greet = h.name ? `Hallo, ${esc(h.name)}` : "Hallo";
  const plan = [
    `<span class="chip">⏱ ${h.minutes} min</span>`,
    h.due ? `<span class="chip">🔁 ${h.due} repasos</span>` : "",
    h.new ? `<span class="chip">✨ ${h.new} nuevas</span>` : "",
    ...h.unit.grammar.map((g) => `<span class="chip">🧩 ${esc(g.title)}</span>`),
    `<span class="chip"><span class="swissflag">+</span> suizo del día</span>`,
  ].join("");
  mount("hoy", `
    <div class="today">
      <section class="card hero">
        <div class="stripe" aria-hidden="true"></div>
        <p class="muted" style="margin:0">${greet} · nivel ${h.level}</p>
        <h1>${h.done_today ? "Sesión de hoy hecha" : "Tu sesión de hoy"}</h1>
        <p class="muted" style="margin:0">${h.done_today ? "Si te apetece, puedes hacer otra o practicar un tema suelto." : "Bloques cortos con una pausa entre ellos. Puedes parar cuando quieras."}</p>
        <div class="plan">${plan}</div>
        <button class="btn primary big" id="start">${h.done_today ? "Hacer otra sesión" : "Empezar"} <span class="kbd">Enter</span></button>
      </section>
      <section class="card streak">
        <div>
          <p class="muted" style="margin:0">Racha</p>
          <div class="num">${h.streak}<span style="font-size:1.4rem"> ${h.streak === 1 ? "día" : "días"}</span></div>
          <p class="small muted" style="margin:6px 0 0">Un día de descanso por semana no la rompe.</p>
        </div>
        <div class="week">${h.week.map((d, k) => `<div class="d ${d.n >= 10 ? "on" : ""} ${k === 6 ? "today" : ""}"><i></i>${d.label}</div>`).join("")}</div>
      </section>
    </div>
    ${S.settings.voice_engine === "azure" && S.settings.azure_key_set ? "" : `<section class="card voice-banner"><div><b>🎙️ Activa la voz natural (gratis)</b><br><span class="muted small">Ahora suena la voz del Mac, que es artificial. Con Azure oirás voces casi humanas, también suizas.</span></div><a class="btn primary" href="#/ajustes">Configurar · 5 min</a></section>`}
    <section class="card unitcard" style="margin-top:16px">
      <div class="big-ic">${h.unit.vocab[0] ? h.unit.vocab[0].icon : "🧩"}</div>
      <div>
        <p class="muted small" style="margin:0">Ahora en tu ruta · ${h.unit.level}</p>
        <h2 style="margin:2px 0 6px">${esc(h.unit.title)}</h2>
        <div class="row">${h.unit.vocab.map((v) => `<a class="chip" href="#/apuntes/vocab/${v.id}">${v.icon} ${esc(v.title)}</a>`).join("")}
        ${h.unit.grammar.map((g) => `<a class="chip" href="#/apuntes/gram/${g.id}">🧩 ${esc(g.title)}</a>`).join("")}</div>
      </div>
      <a class="btn" href="#/ruta">Ver ruta</a>
    </section>
    <h3 style="margin:28px 0 12px">Práctica rápida</h3>
    <div class="shortcuts">
      <button class="shortcut" data-practice="weak"><span class="ic">🎯</span><span><b>Puntos débiles</b><br><span class="muted small">Lo que más te cuesta</span></span></button>
      <button class="shortcut" data-practice="verbs"><span class="ic">🔁</span><span><b>Verbos</b><br><span class="muted small">Conjugación salteada</span></span></button>
      <button class="shortcut" data-practice="swiss"><span class="ic"><span class="swissflag">+</span></span><span><b>Suizo-alemán</b><br><span class="muted small">Para la calle en Basilea</span></span></button>
    </div>`);
  $("#start").addEventListener("click", () => startSession("/api/session"));
  $$("[data-practice]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=${b.dataset.practice}`)));
  document.onkeydown = (e) => { if (e.key === "Enter" && document.activeElement === document.body) startSession("/api/session"); };
}

// ====================================================================== sesión (modo foco)
async function startSession(url) {
  document.onkeydown = null;
  const data = await api.get(url);
  if (!data.exercises.length) {
    toast(url.includes("weak") ? "Aún no hay puntos débiles: ¡sigue practicando!" : "No hay nada que practicar aquí ahora mismo.");
    return;
  }
  new Session(data).open();
}

class Session {
  constructor(data) {
    this.data = data;
    this.list = data.exercises;
    this.i = 0;
    this.block = data.block_size || 8;
    this.done = 0;          // ejercicios respondidos (sin contar presentaciones)
    this.ok = 0;
    this.blockOk = 0; this.blockN = 0;
    this.t0 = Date.now();
    this.requeued = new Set();
    this.answered = false;
    this.sinceBreak = 0;
  }

  open() {
    this.el = document.createElement("div");
    this.el.className = "focus";
    this.el.setAttribute("role", "dialog");
    this.el.innerHTML = `
      <header class="ftop">
        <button class="icon-btn" id="quit" title="Salir (Esc)" aria-label="Salir">✕</button>
        <div class="segments" id="segs"></div>
        <div class="timer ${S.settings.show_timer === false ? "hidden" : ""}"><span id="clock">0:00</span><span class="tbar"><i id="tbar" style="width:0%"></i></span></div>
      </header>
      <div class="stage" id="stage"></div>
      <footer class="fb idle" id="fb"></footer>`;
    document.body.appendChild(this.el);
    document.body.style.overflow = "hidden";
    $("#quit", this.el).addEventListener("click", () => this.quit());
    this.keyh = (e) => this.onKey(e);
    document.addEventListener("keydown", this.keyh);
    this.tick = setInterval(() => this.clock(), 1000);
    this.render();
  }

  close() {
    clearInterval(this.tick);
    document.removeEventListener("keydown", this.keyh);
    document.body.style.overflow = "";
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    this.el.remove();
  }

  quit() {
    if (this.done === 0) { this.close(); return; }
    this.finish(false);
  }

  clock() {
    const s = Math.round((Date.now() - this.t0) / 1000);
    $("#clock", this.el).textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    const target = (Number(S.settings.minutes) || 30) * 60;
    $("#tbar", this.el).style.width = `${Math.min(100, (s / target) * 100)}%`;
  }

  segments() {
    const n = Math.max(1, Math.ceil(this.list.length / this.block));
    let html = "";
    for (let b = 0; b < n; b++) {
      const start = b * this.block, end = Math.min(this.list.length, start + this.block);
      const fill = Math.max(0, Math.min(1, (this.i - start) / (end - start)));
      html += `<div class="seg"><i style="width:${fill * 100}%"></i></div>`;
    }
    $("#segs", this.el).innerHTML = html;
  }

  render() {
    this.segments();
    this.answered = false;
    this.started = Date.now();
    const fb = $("#fb", this.el);
    fb.className = "fb idle";
    fb.innerHTML = "";
    if (this.i >= this.list.length) return this.finish(true);
    const ex = this.list[this.i];
    this.ex = ex;
    const stage = $("#stage", this.el);
    stage.innerHTML = `<div class="ex">${this.kicker(ex)}${this.body(ex)}</div>`;
    stage.scrollTop = 0;
    this.bind(ex);
    this.prefetch();
  }

  kicker(ex) {
    const left = ex.type === "intro" ? "✨ Nueva" : `${SKILL_ICON[ex.skill] || ""} ${SKILL_NAME[ex.skill] || ""}${ex.requeue ? " · otra vez" : ""}`;
    return `<div class="ex-kicker"><span class="skill">${left}</span><span class="lv">${ex.level}</span></div>`;
  }

  body(ex) {
    const c = ex.card || {};
    const p = ex.prompt || {};
    const g = gcls(c.art);
    switch (ex.type) {
      case "intro": return this.introHTML(ex);
      case "article":
        return `<div class="prompt"><div class="emoji">${c.emoji || ""}</div><div class="word de">${esc(p.text)}</div><div class="sub">${esc(p.hint)}</div></div>
          <div class="options three">${ex.options.map((o, k) => `<button class="opt art-opt g-${o}" data-k="${k}"><span class="n">${k + 1}</span><span class="${o}">${o}</span></button>`).join("")}</div>`;
      case "meaning": case "verb_meaning": case "phrase_meaning":
        return `<div class="prompt ${c.art ? "gband " + g : ""}"><div class="word de ${this.sizeCls(p.text)}">${ex.type === "meaning" ? wordHTML(c).replace('class="a"', `class="${c.art === "pl" ? "pl" : c.art}"`) : esc(p.text)}</div>
          <div class="audio-row"><button class="icon-btn" data-say>🔊</button></div></div>
          <p class="muted" style="text-align:center;margin:14px 0 0">¿Qué significa?</p>${this.optsHTML(ex)}`;
      case "reverse":
        return `<div class="prompt"><div class="emoji">${c.emoji || ""}</div><div class="word ${this.sizeCls(p.text)}">${esc(p.text)}</div><div class="sub">¿Cómo se dice en alemán?</div></div>${this.optsHTML(ex)}`;
      case "listen":
        return `<div class="prompt"><div class="sub">Escucha y elige lo que has oído</div><div class="audio-row" style="margin-top:18px"><button class="play" data-say aria-label="Escuchar">▶</button><button class="icon-btn" data-slow title="Más despacio">🐢</button></div></div>${this.optsHTML(ex)}`;
      case "plural":
        return `<div class="prompt gband ${g}"><div class="word de">${wordHTML(c).replace('class="a"', `class="${c.art}"`)}</div><div class="sub">¿Cuál es el plural?</div></div>${this.optsHTML(ex)}`;
      case "cloze":
        return `<div class="prompt"><div class="q">${esc(p.text).replace("___", '<span style="border-bottom:3px solid var(--focus);padding:0 .8em">&nbsp;</span>')}</div><div class="sub" style="margin-top:10px">${esc(p.hint)}</div></div>${this.optsHTML(ex)}`;
      case "type": case "dictation": case "verb_type":
        return `<div class="prompt">${p.listen ? `<div class="sub">Escucha y escribe</div><div class="audio-row" style="margin-top:14px"><button class="play" data-say aria-label="Escuchar">▶</button><button class="icon-btn" data-slow title="Más despacio">🐢</button></div>`
          : `<div class="emoji">${c.emoji || ""}</div><div class="word ${this.sizeCls(p.text)}">${esc(p.text)}</div><div class="sub">Escríbelo en alemán${p.needs_article ? ", con su artículo" : ""}</div>`}</div>
          <div class="typebox"><input type="text" id="typed" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${p.needs_article ? "der / die / das …" : "…"}"><button class="btn primary" id="check">Comprobar</button></div>
          <div class="umlauts">${["ä", "ö", "ü", "ß"].map((u) => `<button data-u="${u}" tabindex="-1">${u}</button>`).join("")}</div>`;
      case "order":
        return `<div class="prompt"><div class="sub">Ordena la frase</div><div class="q" style="font-size:1.25rem;margin-top:6px">${esc(p.hint)}</div></div>
          <div class="order-line" id="line"></div>
          <div class="tokens" id="toks">${ex.tokens.map((t, k) => `<button class="tok" data-t="${k}">${esc(t)}</button>`).join("")}</div>
          <div class="row" style="justify-content:center;margin-top:16px"><button class="btn" id="reset">Borrar</button><button class="btn primary" id="check" disabled>Comprobar</button></div>`;
      case "conj":
        return `<div class="prompt"><div class="sub">${esc(p.es)}</div><div class="word de">${esc(p.text)}</div>
          <div class="tense"><span class="chip">${esc(p.tense)}</span></div>
          <div class="q" style="margin-top:16px"><b>${esc(p.pronoun)}</b> <span style="border-bottom:3px solid var(--focus);padding:0 1.2em">&nbsp;</span></div></div>${this.optsHTML(ex)}`;
      case "gram":
        return `<div class="prompt"><div class="sub">🧩 ${esc(p.topic)}</div><div class="q" style="margin-top:8px">${esc(p.text).replace(/___/g, '<span style="border-bottom:3px solid var(--focus);padding:0 .8em">&nbsp;</span>')}</div></div>${this.optsHTML(ex)}`;
      case "swiss_std": case "swiss_es":
        return `<div class="prompt"><div class="sub"><span class="swissflag">+</span> ${p.kind === "dialecto" ? "Dialecto" : "Helvetismo"} · lo oirás en Basilea</div><div class="word de ${this.sizeCls(p.text)}">${esc(p.text)}</div>
          <div class="audio-row"><button class="icon-btn" data-say>🔊</button></div>
          <div class="sub">${ex.type === "swiss_std" ? "¿Cómo se dice en alemán estándar?" : "¿Qué significa?"}</div></div>${this.optsHTML(ex)}`;
      default: return `<p>Ejercicio desconocido</p>`;
    }
  }

  prefetch() {
    if (S.settings.voice_engine !== "azure" || !S.settings.azure_key_set) return;
    for (const nx of this.list.slice(this.i + 1, this.i + 3)) {
      [nx.audio, nx.sentence && nx.sentence.de].filter(Boolean).forEach((t) => TTS.preload(t, { swiss: nx.swiss || (nx.card && nx.card.kind === "swiss") }));
    }
  }

  sizeCls(t) { const n = String(t || "").length; return n > 26 ? "long" : n > 14 ? "mid" : ""; }

  optsHTML(ex) {
    const de = ex.options_de;
    return `<div class="options">${ex.options.map((o, k) => `<button class="opt ${de ? "de-opt" : ""}" data-k="${k}"><span class="n">${k + 1}</span><span>${de && ex.type !== "plural" ? colorArticles(o).replace(/class="(der|die|das)"/, "") : esc(o)}</span></button>`).join("")}</div>`;
  }

  introHTML(ex) {
    const c = ex.card;
    if (c.kind === "vocab") {
      const g = gcls(c.art);
      return `<div class="prompt intro ${g}">
        <div class="side">${c.emoji || "🔤"}</div>
        <div class="body">
          <div class="head">${c.art ? `<span class="art">${c.art === "pl" ? "die · plural" : c.art}</span>` : ""}<span class="muted small">${esc(c.theme)}</span></div>
          <p class="word de">${esc(c.de)}</p>
          ${c.art && c.art !== "pl" && c.pl ? `<div class="plural">Plural: <span class="de pl">${c.pl === "—" ? "sin plural" : "die " + esc(c.pl)}</span></div>` : ""}
          <div class="meaning">${esc(c.es)}</div>
          <div class="row"><button class="icon-btn" data-say aria-label="Escuchar">🔊</button><button class="icon-btn" data-slow title="Más despacio">🐢</button></div>
          <div class="example"><button class="icon-btn" data-say-ex aria-label="Escuchar ejemplo">🔊</button><div><div class="de">${esc(c.ex)}</div><div class="muted small">${esc(c.exs)}</div></div></div>
          <div class="extras">${c.ch ? `<span class="chip"><span class="swissflag">+</span> En Suiza: <b class="de">${esc(c.ch)}</b></span>` : ""}${c.note ? `<span class="chip">💡 ${esc(c.note)}</span>` : ""}</div>
        </div></div>
        <div class="row" style="justify-content:center;margin-top:20px"><button class="btn primary big" id="gotit">Lo tengo <span class="kbd">Enter</span></button></div>`;
    }
    if (c.kind === "verb") {
      const pr = ["ich", "du", "er/sie", "wir", "ihr", "sie/Sie"];
      return `<div class="prompt intro g-none"><div class="side">🔁</div><div class="body">
        <div class="head"><span class="chip">${c.tags.map(esc).join(" · ")}</span></div>
        <p class="word de">${esc(c.de)}</p><div class="meaning">${esc(c.es)}${c.prep ? ` · <b>${esc(c.prep)}</b>` : ""}</div>
        <div class="row"><button class="icon-btn" data-say>🔊</button></div>
        <div class="conj-mini de">${[0, 3, 1, 4, 2, 5].map((k) => `<span class="p">${pr[k]}</span><span>${esc(c.prs[k])}</span>`).join("")}</div>
        <p class="small muted" style="margin:10px 0 0">Perfekt: <span class="de">${c.aux === "sein" ? "ist" : "hat"} ${esc(c.part)}</span></p>
        <div class="example"><button class="icon-btn" data-say-ex>🔊</button><div><div class="de">${esc(c.ex)}</div><div class="muted small">${esc(c.exs)}</div></div></div>
        ${c.note ? `<div class="extras"><span class="chip">💡 ${esc(c.note)}</span></div>` : ""}
      </div></div><div class="row" style="justify-content:center;margin-top:20px"><button class="btn primary big" id="gotit">Lo tengo <span class="kbd">Enter</span></button></div>`;
    }
    if (c.kind === "swiss") {
      return `<div class="prompt intro g-none"><div class="side" style="background:#D52B1E1a;border-color:#D52B1E"><span class="swissflag" style="font-size:2.4rem;width:1.4em;height:1.4em">+</span></div><div class="body">
        <div class="head"><span class="swiss-type ${c.type}">${c.type}</span><span class="muted small">Suizo-alemán para reconocer</span></div>
        <p class="word de">${esc(c.de)}</p>
        <div class="meaning">${esc(c.es)}</div>
        <div class="row"><button class="icon-btn" data-say>🔊</button><span class="muted">Alemán estándar: <b class="de">${esc(c.std)}</b></span></div>
        ${c.note ? `<div class="extras"><span class="chip">💡 ${esc(c.note)}</span></div>` : ""}
      </div></div><div class="row" style="justify-content:center;margin-top:20px"><button class="btn primary big" id="gotit">Lo tengo <span class="kbd">Enter</span></button></div>`;
    }
    // frase
    return `<div class="prompt intro g-none"><div class="side">💬</div><div class="body">
      <div class="head"><span class="muted small">Expresión</span></div>
      <p class="word de" style="font-size:2rem">${esc(c.de)}</p><div class="meaning">${esc(c.es)}</div>
      <div class="row"><button class="icon-btn" data-say>🔊</button><button class="icon-btn" data-slow>🐢</button></div>
      ${c.note ? `<div class="extras"><span class="chip">💡 ${esc(c.note)}</span></div>` : ""}
    </div></div><div class="row" style="justify-content:center;margin-top:20px"><button class="btn primary big" id="gotit">Lo tengo <span class="kbd">Enter</span></button></div>`;
  }

  say(slow) { TTS.speak(this.ex.audio, { swiss: this.ex.swiss || (this.ex.card && this.ex.card.kind === "swiss"), slow }); }

  bind(ex) {
    const st = $("#stage", this.el);
    $$("[data-say]", st).forEach((b) => b.addEventListener("click", () => this.say(false)));
    $$("[data-slow]", st).forEach((b) => b.addEventListener("click", () => this.say(true)));
    $$("[data-say-ex]", st).forEach((b) => b.addEventListener("click", () => TTS.speak(ex.card.ex)));
    if (ex.type === "intro") {
      api.post("/api/introduce", { item: ex.item });
      setTimeout(() => this.say(false), 250);
      $("#gotit", st).addEventListener("click", () => this.next());
      $("#gotit", st).focus();
      return;
    }
    if (["listen", "dictation"].includes(ex.type) || (ex.type === "type" && ex.prompt.listen)) setTimeout(() => this.say(false), 300);
    if (["meaning", "swiss_std", "swiss_es", "phrase_meaning", "verb_meaning"].includes(ex.type)) setTimeout(() => this.say(false), 250);
    $$(".opt", st).forEach((b) => b.addEventListener("click", () => this.choose(Number(b.dataset.k))));
    if (["type", "dictation", "verb_type"].includes(ex.type)) {
      const inp = $("#typed", st);
      inp.focus();
      $$("[data-u]", st).forEach((b) => b.addEventListener("click", () => {
        const s = inp.selectionStart, e = inp.selectionEnd;
        inp.value = inp.value.slice(0, s) + b.dataset.u + inp.value.slice(e);
        inp.focus(); inp.setSelectionRange(s + 1, s + 1);
      }));
      $("#check", st).addEventListener("click", () => this.checkTyped());
    }
    if (ex.type === "order") {
      this.picked = [];
      const line = $("#line", st);
      const drawLine = () => {
        line.innerHTML = this.picked.map((k, pos) => `<button class="tok" data-pos="${pos}">${esc(ex.tokens[k])}</button>`).join("") || `<span class="muted">Toca las palabras en orden</span>`;
        $$(".tok[data-t]", st).forEach((b) => b.classList.toggle("used", this.picked.includes(Number(b.dataset.t))));
        $$("[data-pos]", line).forEach((b) => b.addEventListener("click", () => { if (this.answered) return; this.picked.splice(Number(b.dataset.pos), 1); drawLine(); }));
        $("#check", st).disabled = this.picked.length !== ex.tokens.length;
      };
      $$(".tok[data-t]", st).forEach((b) => b.addEventListener("click", () => { if (this.answered) return; this.picked.push(Number(b.dataset.t)); drawLine(); }));
      $("#reset", st).addEventListener("click", () => { if (this.answered) return; this.picked = []; drawLine(); });
      $("#check", st).addEventListener("click", () => this.checkOrder());
      drawLine();
    }
  }

  onKey(e) {
    if (e.key === "Escape") { this.quit(); return; }
    const typing = document.activeElement && document.activeElement.tagName === "INPUT";
    if (e.key === "Enter") {
      e.preventDefault();
      if (this.mode === "break") { $("#cont", this.el)?.click(); return; }
      if (this.mode === "end") { $("#home", this.el)?.click(); return; }
      if (this.ex.type === "intro") return this.next();
      if (this.answered) return this.next();
      if (typing) return this.checkTyped();
      if (this.ex.type === "order" && !$("#check", this.el).disabled) return this.checkOrder();
      return;
    }
    if (typing || this.answered) return;
    const n = Number(e.key);
    if (n >= 1 && this.ex.options && n <= this.ex.options.length) this.choose(n - 1);
    if (e.key === " " && this.ex.audio) { e.preventDefault(); this.say(false); }
  }

  choose(k) {
    if (this.answered) return;
    const ex = this.ex;
    const right = k === ex.answer;
    $$(".opt", this.el).forEach((b, idx) => {
      b.disabled = true;
      if (idx === ex.answer) b.classList.add("is-right");
      if (idx === k && !right) b.classList.add("is-wrong");
    });
    this.result(right, right ? null : ex.options[ex.answer]);
  }

  checkTyped() {
    if (this.answered) return;
    const ex = this.ex;
    const inp = $("#typed", this.el);
    const v = norm(inp.value);
    if (!v) return;
    let right = ex.accept.includes(v);
    let note = "";
    const target = norm(ex.answer_text);
    if (!right && lev(v, target) === 1 && target.length >= 5) { right = true; note = `Casi perfecto: se escribe <b class="de">${esc(ex.answer_text)}</b>.`; }
    if (!right && ex.prompt.needs_article) {
      const word = target.split(" ").slice(1).join(" ");
      if (v === word) note = "Falta el artículo: en alemán, el artículo forma parte de la palabra.";
      else if (v.split(" ").slice(1).join(" ") === word) note = `La palabra está bien, pero el artículo es <b class="${ex.card.art}">${ex.card.art}</b>.`;
    }
    if (right && !note && inp.value.trim() !== ex.answer_text && inp.value.trim().toLowerCase() === ex.answer_text.toLowerCase() && ex.card && ex.card.art) {
      note = "Recuerda: los sustantivos alemanes van siempre con mayúscula.";
    }
    inp.classList.add(right ? "ok" : "no");
    inp.disabled = true;
    this.result(right, right ? null : ex.answer_text, note, !right);
  }

  checkOrder() {
    if (this.answered) return;
    const ex = this.ex;
    const built = this.picked.map((k) => ex.tokens[k]).join(" ");
    const target = ex.answer_tokens.join(" ");
    const right = norm(built) === norm(target);
    $("#line", this.el).classList.add(right ? "ok" : "no");
    this.result(right, right ? null : target, "", !right);
  }

  result(right, correctText, note = "", allowOverride = false) {
    this.answered = true;
    const ex = this.ex;
    const ms = Date.now() - this.started;
    this.done += 1; this.blockN += 1; this.sinceBreak += 1;
    if (right) { this.ok += 1; this.blockOk += 1; }
    api.post("/api/answer", { item: ex.item, type: ex.type, skill: ex.skill, correct: right, ms, requeue: !!ex.requeue });
    if (!right && !this.requeued.has(ex.item)) {
      this.requeued.add(ex.item);
      const copy = Object.assign({}, ex, { requeue: true });
      this.list.splice(Math.min(this.list.length, this.i + 4), 0, copy);
    }
    if (ex.audio && ex.type !== "listen") setTimeout(() => TTS.speak(ex.type === "order" || ex.type === "cloze" ? ex.audio : ex.audio, { swiss: ex.swiss }), 150);
    const c = ex.card || {};
    let detail = "";
    const vocabLine = ["article", "plural", "listen", "reverse", "type", "dictation"].includes(ex.type) && c.kind === "vocab";
    if (!right && correctText && !vocabLine) detail += `Respuesta: <b class="de">${colorArticles(correctText)}</b>. `;
    if (ex.type === "gram" && ex.explain) detail += esc(ex.explain);
    else if (ex.explain && !right) detail += esc(ex.explain);
    const colored = wordHTML(c).replace('class="a"', `class="${c.art === "pl" ? "pl" : c.art}"`);
    if (vocabLine && ex.type === "plural") detail += ` <b class="de">${colored}</b> → <b class="de"><span class="pl">die</span> ${esc(c.pl)}</b>`;
    else if (vocabLine) detail += ` <b class="de">${colored}</b> = ${esc(c.es)}`;
    if (note) detail = note + " " + detail;
    const praise = ["¡Bien!", "¡Genau!", "¡Perfecto!", "¡Eso es!", "¡Sehr gut!", "¡Super!"];
    const sn = ex.sentence;
    const sentHTML = sn ? `<div class="sent"><button class="icon-btn" id="say-sent" aria-label="Escuchar la frase">🔊</button><div><div class="de">${esc(sn.de)}</div><div class="es">${esc(sn.es)}</div></div></div>` : "";
    const fb = $("#fb", this.el);
    fb.className = `fb ${right ? "right" : "wrong"}`;
    fb.innerHTML = `<div class="fb-inner">
      <div class="msg"><div class="badge">${right ? "✓" : "↻"}</div><div><div class="title">${right ? praise[Math.floor(Math.random() * praise.length)] : "Casi. Lo repetimos en un momento."}</div><div class="detail">${detail}</div>${sentHTML}</div></div>
      <div class="row">${allowOverride ? `<button class="btn ghost small" id="override" title="Si tu respuesta también es correcta">Mi respuesta también vale</button>` : ""}
      ${ex.sheet ? `<button class="btn ghost" id="sheet">Ver ficha</button>` : ""}
      <button class="btn primary" id="next">Seguir <span class="kbd">Enter</span></button></div></div>`;
    $("#next", fb).addEventListener("click", () => this.next());
    $("#next", fb).focus();
    if (sn) $("#say-sent", fb).addEventListener("click", () => TTS.speak(sn.de, { swiss: sn.swiss }));
    if (ex.sheet) $("#sheet", fb).addEventListener("click", () => this.showSheet(ex.sheet));
    if (allowOverride) $("#override", fb).addEventListener("click", () => {
      api.post("/api/answer", { item: ex.item, type: ex.type, skill: ex.skill, correct: true, ms, requeue: true });
      this.ok += 1; this.blockOk += 1;
      this.list = this.list.filter((x, idx) => !(idx > this.i && x.item === ex.item && x.requeue));
      this.next();
    });
  }

  async showSheet(id) {
    if (!S.lib) S.lib = await api.get("/api/library");
    const sh = S.lib.sheets.find((s) => s.id === id);
    if (!sh) return;
    const st = $("#stage", this.el);
    const keep = st.innerHTML;
    st.innerHTML = `<div class="ex"><div class="card sheet"><h2>${sh.icon} ${esc(sh.title)}</h2>${sh.html}<div class="row" style="margin-top:18px"><button class="btn primary" id="back">Volver al ejercicio</button></div></div></div>`;
    $("#back", st).addEventListener("click", () => { st.innerHTML = keep; $$(".opt", st).forEach((b) => (b.disabled = true)); });
  }

  next() {
    if (this.ex && this.ex.type === "intro") { /* no cuenta como respuesta */ }
    this.i += 1;
    this.mode = null;
    const atBreak = this.i < this.list.length && this.i % this.block === 0 && this.sinceBreak >= 4;
    if (atBreak) return this.breakScreen();
    this.render();
  }

  breakScreen() {
    this.mode = "break";
    this.segments();
    const blocks = Math.ceil(this.list.length / this.block);
    const cur = Math.floor(this.i / this.block);
    const pct = this.blockN ? this.blockOk / this.blockN : 1;
    const C = 2 * Math.PI * 76;
    $("#fb", this.el).className = "fb idle";
    $("#stage", this.el).innerHTML = `<div class="ex breaker">
      <svg class="ring" viewBox="0 0 180 180" aria-hidden="true"><defs><linearGradient id="ringgrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F5D04A"/><stop offset="1" stop-color="#D0271D"/></linearGradient></defs><circle class="track" cx="90" cy="90" r="76"/><circle class="val" cx="90" cy="90" r="76" stroke-dasharray="${C}" stroke-dashoffset="${C}"/><text x="90" y="104" text-anchor="middle">${this.blockOk}/${this.blockN}</text></svg>
      <h2>Bloque ${cur} de ${blocks} hecho</h2>
      <p class="muted">${pct >= 0.85 ? "Vas muy bien. Respira un momento." : pct >= 0.6 ? "Buen ritmo. Lo que has fallado volverá pronto." : "Los fallos se quedan guardados para repasarlos. Sigue así."}</p>
      <div class="breath" aria-hidden="true"></div>
      <div class="row" style="justify-content:center"><button class="btn ghost" id="stop">Terminar por hoy</button><button class="btn primary big" id="cont">Seguir <span class="kbd">Enter</span></button></div>
    </div>`;
    requestAnimationFrame(() => { const v = $(".ring .val", this.el); if (v) v.style.strokeDashoffset = C * (1 - pct); });
    this.blockOk = 0; this.blockN = 0; this.sinceBreak = 0;
    $("#cont", this.el).addEventListener("click", () => { this.mode = null; this.render(); });
    $("#cont", this.el).focus();
    $("#stop", this.el).addEventListener("click", () => this.finish(false));
  }

  async finish(complete) {
    this.mode = "end";
    clearInterval(this.tick);
    const seconds = Math.round((Date.now() - this.t0) / 1000);
    const r = await api.post("/api/finish", { total: this.done, correct: this.ok, seconds, complete, kind: this.data.kind });
    const pct = this.done ? Math.round((this.ok / this.done) * 100) : 0;
    $("#segs", this.el).innerHTML = "";
    $("#fb", this.el).className = "fb idle";
    $("#stage", this.el).innerHTML = `<div class="ex breaker">
      <div style="font-size:4rem">${complete ? "🎉" : "👏"}</div>
      <h1>${complete ? "¡Sesión completada!" : "Buen trabajo"}</h1>
      ${r.level_up ? `<div class="tip" style="text-align:left">🚀 <b>¡Subes a ${r.level_up}!</b> Has visto casi todo tu nivel con buenos resultados. Las próximas sesiones traen contenido de ${r.level_up}.</div>` : ""}
      <div class="grid g3" style="margin:24px 0">
        <div class="card stat"><div class="v">${this.ok}/${this.done}</div><div class="l">aciertos · ${pct} %</div></div>
        <div class="card stat"><div class="v">+${r.xp}</div><div class="l">puntos</div></div>
        <div class="card stat"><div class="v">${r.streak}</div><div class="l">${r.streak === 1 ? "día" : "días"} de racha</div></div>
      </div>
      <p class="muted">${Math.floor(seconds / 60)} min ${seconds % 60} s. Lo que has fallado volverá en las próximas sesiones.</p>
      <button class="btn primary big" id="home">Volver al inicio <span class="kbd">Enter</span></button>
    </div>`;
    $("#home", this.el).addEventListener("click", () => { this.close(); route(); });
    $("#home", this.el).focus();
  }
}

// ====================================================================== apuntes
async function viewLibrary(tab, ref) {
  if (!S.lib) S.lib = await api.get("/api/library");
  const L = S.lib;
  const tabs = [["vocab", "🧠 Vocabulario"], ["gram", "🧩 Gramática"], ["verbos", "🔁 Verbos"], ["frases", "💬 Expresiones"], ["suizo", "🇨🇭 Suizo"], ["notas", "📝 Mis apuntes"]];
  const tabsHTML = `<div class="tabs no-print">${tabs.map(([id, label]) => `<button class="tab ${tab === id ? "on" : ""}" data-go="#/apuntes/${id}">${label}</button>`).join("")}</div>`;
  let body = "";
  if (tab === "vocab") body = ref ? themeDetail(L.themes.find((t) => t.id === ref)) : themeGrid(L.themes);
  else if (tab === "gram") body = ref ? sheetDetail(L.sheets.find((s) => s.id === ref)) : sheetList(L.sheets);
  else if (tab === "verbos") body = ref ? verbDetail(L.verbs.find((v) => v.id === ref), L.pronouns) : verbList(L.verbs);
  else if (tab === "frases") body = phrasesView(L.phrases);
  else if (tab === "suizo") body = swissView(L.swiss);
  else if (tab === "notas") body = `<div id="notes"></div>`;
  mount("apuntes", `<div class="view-head no-print"><div><h1>Apuntes</h1><p class="muted">Todo se puede escuchar, practicar y guardar como PDF.</p></div></div>${tabsHTML}${body}`);
  bindLibrary(tab, ref);
}

function genderBar(items) {
  const n = { der: 0, die: 0, das: 0, pl: 0 };
  items.forEach((i) => { if (n[i.art] !== undefined) n[i.art] += 1; });
  const tot = Object.values(n).reduce((a, b) => a + b, 0);
  if (!tot) return `<div class="genderbar"><i style="width:100%;background:var(--line)"></i></div>`;
  return `<div class="genderbar" title="der ${n.der} · die ${n.die} · das ${n.das}">${["der", "die", "das", "pl"].map((g) => `<i style="width:${(n[g] / tot) * 100}%;background:var(--${g})"></i>`).join("")}</div>`;
}

function themeGrid(themes) {
  return LEVELS.map((lv) => {
    const ts = themes.filter((t) => t.level === lv);
    if (!ts.length) return "";
    return `<h3 style="margin:20px 0 10px"><span class="lv">${lv}</span></h3><div class="grid g3">${ts.map((t) => {
      const known = t.items.filter((i) => i.status === "known").length;
      const seen = t.items.filter((i) => i.status !== "new").length;
      return `<button class="tile" data-go="#/apuntes/vocab/${t.id}"><span class="ic">${t.icon}</span><span class="t">${esc(t.title)}</span>${genderBar(t.items)}
        <span class="meta"><span>${t.items.length} palabras</span><span>${seen ? `${known}/${t.items.length} sabidas` : "sin empezar"}</span></span></button>`;
    }).join("")}</div>`;
  }).join("");
}

function wordCard(i, hideEs) {
  return `<div class="wcard ${gcls(i.art)}" data-art="${i.art || "x"}">
    <div class="e">${i.emoji || ""}</div>
    <div><div class="w">${wordHTML(i)}</div>
      ${i.art && i.art !== "pl" && i.pl ? `<div class="pl-f">Pl.: ${i.pl === "—" ? "—" : "die " + esc(i.pl)}</div>` : ""}
      <div class="m ${hideEs ? "es-hide" : ""}">${esc(i.es)}</div>
      <div class="x"><span class="de">${esc(i.ex)}</span><br>${esc(i.exs)}</div>
      ${(i.ch || i.note) ? `<div class="flags">${i.ch ? `<span class="chip small"><span class="swissflag">+</span> ${esc(i.ch)}</span>` : ""}${i.note ? `<span class="chip small">💡 ${esc(i.note)}</span>` : ""}</div>` : ""}
    </div>
    <div class="col" style="display:flex;flex-direction:column;gap:8px;align-items:center"><button class="icon-btn" data-speak="${esc(i.display)}" aria-label="Escuchar">🔊</button><span class="status-dot ${i.status}" title="${{ new: "Nueva", learning: "Aprendiendo", known: "Sabida" }[i.status]}"></span></div>
  </div>`;
}

function themeDetail(t) {
  if (!t) return `<p>Tema no encontrado.</p>`;
  const hasNouns = t.items.some((i) => i.art);
  return `<div class="view-head"><div><a class="muted small no-print" href="#/apuntes/vocab">← Vocabulario</a><h2 style="margin-top:6px">${t.icon} ${esc(t.title)} <span class="lv">${t.level}</span></h2></div>
    <div class="row no-print"><button class="btn primary" data-practice-theme="${t.id}">Practicar este tema</button><button class="btn" onclick="window.print()">Guardar PDF</button></div></div>
    <div class="filterbar">${hasNouns ? `<span class="muted small">Ver:</span><button class="chip on" data-filter="all">Todas</button><button class="chip" data-filter="der"><span class="der">●</span> der</button><button class="chip" data-filter="die"><span class="die">●</span> die</button><button class="chip" data-filter="das"><span class="das">●</span> das</button>` : ""}
      <button class="chip" id="hide-es">🙈 Ocultar traducción</button></div>
    <div class="words">${t.items.map((i) => wordCard(i)).join("")}</div>`;
}

function sheetList(sheets) {
  return LEVELS.map((lv) => {
    const ss = sheets.filter((s) => s.level === lv);
    return `<h3 style="margin:20px 0 10px"><span class="lv">${lv}</span></h3><div class="grid g3">${ss.map((s) => `<button class="tile" data-go="#/apuntes/gram/${s.id}"><span class="ic">${s.icon}</span><span class="t">${esc(s.title)}</span><span class="muted small">${esc(s.summary)}</span></button>`).join("")}</div>`;
  }).join("");
}

function sheetDetail(s) {
  if (!s) return `<p>Ficha no encontrada.</p>`;
  return `<div class="view-head"><div><a class="muted small no-print" href="#/apuntes/gram">← Gramática</a><h2 style="margin-top:6px">${s.icon} ${esc(s.title)} <span class="lv">${s.level}</span></h2><p class="muted">${esc(s.summary)}</p></div>
    <div class="row no-print"><button class="btn primary" data-practice-sheet="${s.id}">Practicar</button><button class="btn" onclick="window.print()">Guardar PDF</button></div></div>
    <div class="card sheet">${s.html}</div>`;
}

function verbList(verbs) {
  const tags = ["regular", "irregular", "separable", "inseparable", "modal", "reflexivo", "preposición", "dativo", "movimiento"];
  return `<div class="filterbar"><input type="search" id="vsearch" placeholder="Buscar verbo o significado…" style="max-width:320px">
    ${tags.map((t) => `<button class="chip" data-tag="${t}">${t}</button>`).join("")}</div>
    <div class="card list-rows" id="vlist">${verbs.map((v) => `<div class="r" data-tags="${v.tags.join(" ")}" data-q="${esc((v.inf + " " + v.es).toLowerCase())}">
      <a class="de" href="#/apuntes/verbos/${v.id}"><b>${esc(v.inf)}</b> <span class="muted small">${esc(v.prep || "")}</span></a>
      <span>${esc(v.es)}</span><span class="row"><span class="lv">${v.level}</span><span class="status-dot ${v.status}"></span></span></div>`).join("")}</div>`;
}

function conjTable(title, forms, pr) {
  return `<div class="vt"><h4>${title}</h4><table>${forms.map((f, k) => `<tr><td>${pr[k]}</td><td class="f">${esc(f)}</td></tr>`).join("")}</table></div>`;
}

function verbDetail(v, pr) {
  if (!v) return `<p>Verbo no encontrado.</p>`;
  const imp = v.imp ? `<div class="vt"><h4>Imperativ</h4><table><tr><td>du</td><td class="f">${esc(v.imp[0])}!</td></tr><tr><td>ihr</td><td class="f">${esc(v.imp[1])}!</td></tr><tr><td>Sie</td><td class="f">${esc(v.imp[2])}!</td></tr></table></div>` : `<div class="vt"><h4>Imperativ</h4><p class="muted small">No se usa en imperativo.</p></div>`;
  return `<div class="view-head"><div><a class="muted small no-print" href="#/apuntes/verbos">← Verbos</a>
    <h2 class="de" style="margin-top:6px">${esc(v.inf)} <button class="icon-btn no-print" data-speak="${esc(v.inf)}">🔊</button></h2>
    <p style="margin:0">${esc(v.es)} ${v.prep ? `· <b>${esc(v.prep)}</b>` : ""}</p>
    <div class="taglist" style="margin-top:8px">${v.tags.map((t) => `<span class="chip small">${t}</span>`).join("")}<span class="lv">${v.level}</span></div></div>
    <div class="row no-print"><button class="btn primary" data-practice-verbs>Practicar verbos</button><button class="btn" onclick="window.print()">Guardar PDF</button></div></div>
    <div class="card" style="margin-bottom:16px"><div class="row"><button class="icon-btn no-print" data-speak="${esc(v.ex)}">🔊</button><div><div class="de" style="font-size:1.15rem">${esc(v.ex)}</div><div class="muted">${esc(v.exs)}</div></div></div>
    ${v.note ? `<div class="tip">💡 ${esc(v.note)}</div>` : ""}</div>
    <div class="verbtables">
      ${conjTable("Präsens · presente", v.forms.prs, pr)}
      ${conjTable("Perfekt · pasado hablado", v.forms.perf, pr)}
      ${conjTable("Präteritum · pasado escrito", v.forms.prt, pr)}
      ${conjTable("Futur I", v.futur, pr)}
      ${conjTable("Konjunktiv II", v.forms.k2, pr)}
      ${imp}
    </div>`;
}

function phrasesView(groups) {
  return groups.map((g) => `<div class="card" style="margin-bottom:16px"><div class="row" style="justify-content:space-between"><h2>${g.icon} ${esc(g.title)} <span class="lv">${g.level}</span></h2>
    <div class="row no-print"><button class="btn" data-practice-phrases="${g.id}">Practicar</button></div></div>
    <div class="list-rows">${g.items.map((i) => `<div class="r"><span class="row" style="flex-wrap:nowrap"><button class="icon-btn no-print" data-speak="${esc(i.de)}">🔊</button><span class="de">${esc(i.de)}</span></span><span>${esc(i.es)}</span><span class="n">${esc(i.note)}</span></div>`).join("")}</div></div>`).join("")
    + `<div class="row no-print"><button class="btn" onclick="window.print()">Guardar PDF</button></div>`;
}

function swissView(sw) {
  return `<div class="card" style="margin-bottom:16px"><p style="margin:0">${sw.intro}</p>
    <div class="row" style="margin-top:14px"><span class="swiss-type helvetismo">helvetismo</span><span class="muted small">también se escribe en Suiza</span><span class="swiss-type dialecto">dialecto</span><span class="muted small">solo se habla</span></div>
    <div class="row no-print" style="margin-top:14px"><button class="btn primary" data-practice-swiss>Practicar suizo</button><button class="btn" onclick="window.print()">Guardar PDF</button></div></div>`
    + sw.groups.map((g) => `<div class="card" style="margin-bottom:16px"><h2>${g.icon} ${esc(g.title)}</h2><div class="list-rows">${g.items.map((i) => `<div class="r">
      <span class="row" style="flex-wrap:nowrap"><button class="icon-btn no-print" data-speak-ch="${esc(i[0])}">🔊</button><span><span class="de"><b>${esc(i[0])}</b></span><br><span class="swiss-type ${i[3]}">${i[3]}</span></span></span>
      <span><span class="de">${esc(i[1])}</span><br><span class="muted">${esc(i[2])}</span></span><span class="n">${esc(i[4] || "")}</span></div>`).join("")}</div></div>`).join("");
}

function bindLibrary(tab, ref) {
  $$("[data-speak]").forEach((b) => b.addEventListener("click", () => TTS.speak(b.dataset.speak)));
  $$("[data-speak-ch]").forEach((b) => b.addEventListener("click", () => TTS.speak(b.dataset.speakCh, { swiss: true })));
  $$("[data-practice-theme]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=theme&ref=${b.dataset.practiceTheme}`)));
  $$("[data-practice-sheet]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=sheet&ref=${b.dataset.practiceSheet}`)));
  $$("[data-practice-phrases]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=phrases&ref=${b.dataset.practicePhrases}`)));
  $$("[data-practice-verbs]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=verbs`)));
  $$("[data-practice-swiss]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=swiss`)));
  $$("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    $$("[data-filter]").forEach((x) => x.classList.toggle("on", x === b));
    $$(".wcard").forEach((c) => c.classList.toggle("hidden", b.dataset.filter !== "all" && c.dataset.art !== b.dataset.filter));
  }));
  const hide = $("#hide-es");
  if (hide) hide.addEventListener("click", () => {
    hide.classList.toggle("on");
    $$(".wcard .m, .wcard .x").forEach((m) => { m.style.filter = hide.classList.contains("on") ? "blur(6px)" : ""; });
  });
  if (tab === "verbos" && !ref) {
    const active = new Set();
    const apply = () => {
      const q = ($("#vsearch").value || "").toLowerCase().trim();
      $$("#vlist .r").forEach((r) => {
        const okq = !q || r.dataset.q.includes(q);
        const okt = [...active].every((t) => r.dataset.tags.split(" ").includes(t));
        r.classList.toggle("hidden", !(okq && okt));
      });
    };
    $("#vsearch").addEventListener("input", apply);
    $$("[data-tag]").forEach((b) => b.addEventListener("click", () => {
      b.classList.toggle("on");
      b.classList.contains("on") ? active.add(b.dataset.tag) : active.delete(b.dataset.tag);
      apply();
    }));
  }
  if (tab === "notas") notesView();
}

async function notesView(selectId) {
  const notes = await api.get("/api/notes");
  const colors = { amber: "var(--focus)", der: "var(--der)", die: "var(--die)", das: "var(--das)", pl: "var(--pl)" };
  let cur = notes.find((n) => n.id === selectId) || notes[0] || null;
  const draw = () => {
    $("#notes").innerHTML = `<div class="notes-grid">
      <div class="no-print"><button class="btn primary" id="newnote" style="width:100%;justify-content:center;margin-bottom:12px">+ Nueva nota</button>
        ${notes.map((n) => `<button class="note-item ${cur && cur.id === n.id ? "on" : ""}" data-id="${n.id}" style="--nc:${colors[n.color] || colors.amber}"><b>${esc(n.title)}</b><br><span class="muted small">${new Date(n.updated * 1000).toLocaleDateString("es-ES")}</span></button>`).join("") || `<p class="muted">Aquí puedes guardar tus propios apuntes: frases de clase, dudas, palabras de la calle…</p>`}
      </div>
      <div class="card">${cur ? `
        <input type="text" id="ntitle" value="${esc(cur.title)}" style="font-size:1.3rem;font-weight:700;margin-bottom:10px">
        <div class="row no-print" style="margin-bottom:10px">${Object.entries(colors).map(([k, v]) => `<button class="chip ${cur.color === k ? "on" : ""}" data-color="${k}"><span style="color:${v}">●</span></button>`).join("")}</div>
        <textarea id="nbody" placeholder="Escribe aquí…">${esc(cur.body)}</textarea>
        <div class="row no-print" style="margin-top:12px"><button class="btn primary" id="nsave">Guardar</button><button class="btn" onclick="window.print()">Guardar PDF</button><button class="btn ghost" id="ndel">Borrar</button></div>`
        : `<p class="muted">Crea tu primera nota con «Nueva nota».</p>`}</div></div>`;
    $("#newnote").addEventListener("click", async () => {
      const r = await api.post("/api/notes", { title: "Nueva nota", body: "", color: "amber" });
      notesView(r.id);
    });
    $$(".note-item").forEach((b) => b.addEventListener("click", () => { cur = notes.find((n) => n.id === Number(b.dataset.id)); draw(); }));
    if (!cur) return;
    $$("[data-color]").forEach((b) => b.addEventListener("click", () => { cur.color = b.dataset.color; $$("[data-color]").forEach((x) => x.classList.toggle("on", x === b)); }));
    $("#nsave").addEventListener("click", async () => {
      await api.post("/api/notes", { id: cur.id, title: $("#ntitle").value || "Sin título", body: $("#nbody").value, color: cur.color });
      toast("Nota guardada");
      notesView(cur.id);
    });
    $("#ndel").addEventListener("click", async () => {
      if (!confirm("¿Borrar esta nota?")) return;
      await api.post("/api/notes", { id: cur.id, delete: true });
      notesView();
    });
  };
  draw();
}

// ====================================================================== ruta
async function viewRoute() {
  const p = await api.get("/api/progress");
  const cur = LEVELS.indexOf(p.level);
  mount("ruta", `<div class="view-head"><div><h1>Tu ruta A1 → B2</h1><p class="muted">Basada en el MCER y en los temas de los exámenes Goethe y telc.</p></div></div>
    <div class="route">${p.levels.map((lv, k) => `<div class="level ${k === cur ? "current" : k < cur ? "done" : ""}">
      <div class="badge">${lv.id}</div>
      <div class="card">
        <div class="row" style="justify-content:space-between"><h2 style="margin:0">${esc(lv.title)}</h2><span class="muted small">${esc(lv.exam)}</span></div>
        <ul class="cando">${lv.cando.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
        <div class="units">${lv.units.map((u) => `<div class="unit"><div class="row" style="justify-content:space-between"><span class="t">${esc(u.title)}</span><span class="muted small">${u.known}/${u.total}</span></div>
          <div class="bar" style="margin:8px 0"><i style="width:${u.total ? (u.seen / u.total) * 100 : 0}%;opacity:.45"></i></div>
          <div class="row small">${u.themes.map((t, j) => `<a class="chip small" href="#/apuntes/vocab/${t}">${esc(u.vocab[j])}</a>`).join("")}${u.grammar.map((g) => `<a class="chip small" href="#/apuntes/gram/${g.id}">🧩 ${esc(g.title)}</a>`).join("")}</div></div>`).join("")}</div>
      </div></div>`).join("")}</div>`);
}

// ====================================================================== progreso
async function viewProgress() {
  const p = await api.get("/api/progress");
  const max = Math.max(1, ...p.heat.map((d) => d.n));
  const lvl = (n) => (n === 0 ? "" : n < max / 3 ? "l1" : n < (2 * max) / 3 ? "l2" : "l3");
  // alinear el mapa de calor a semanas que empiezan en lunes
  const first = new Date(p.heat[0].day + "T12:00:00");
  const pad = (first.getDay() + 6) % 7;
  const cells = Array(pad).fill(`<i style="visibility:hidden"></i>`).concat(p.heat.map((d) => `<i class="${lvl(d.n)}" title="${d.day}: ${d.n} ejercicios"></i>`));
  const skills = Object.entries(p.skills).filter(([k]) => k !== "speak");
  mount("progreso", `<div class="view-head"><div><h1>Progreso</h1><p class="muted">Nivel actual: <b>${p.level}</b> · ${p.minutes} min de estudio en total</p></div>
    <button class="btn primary" id="weak">🎯 Practicar puntos débiles</button></div>
    <div class="grid g3">
      <div class="card stat"><div class="v">${p.streak}</div><div class="l">días de racha</div></div>
      <div class="card stat"><div class="v">${p.words.learned}<span class="muted" style="font-size:1rem"> / ${p.words.total}</span></div><div class="l">palabras aprendidas · ${p.words.mastered} dominadas</div></div>
      <div class="card stat"><div class="v">${p.xp}</div><div class="l">puntos · ${p.due} repasos pendientes hoy</div></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h2>Últimas 12 semanas</h2><div class="heat">${cells.join("")}</div><p class="small muted" style="margin-top:12px">Cada casilla es un día. Más color = más ejercicios.</p></div>
      <div class="card"><h2>Por destreza</h2>${skills.map(([k, s]) => `<div class="skill"><span>${SKILL_ICON[k]} ${s.label}</span>
        <div class="bar"><i style="width:${s.accuracy == null ? 0 : Math.round(s.accuracy * 100)}%"></i></div>
        <span class="small muted">${s.accuracy == null ? "—" : Math.round(s.accuracy * 100) + " %"}</span><span class="lv lvx">${s.level || "—"}</span></div>`).join("")}
        <p class="small muted">El nivel por destreza aparece cuando hay al menos 8 respuestas de ese nivel con un 70 % de aciertos. La pronunciación llega en la fase 2.</p></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h2>Lo que más te cuesta</h2>${p.weak.length ? p.weak.map((w) => `<div class="weak-row"><span class="de"><b class="${w.art === "pl" ? "pl" : w.art}">${esc(w.label)}</b> <span class="muted small">${esc(w.kind === "gram" ? "" : w.es)}</span></span><span class="muted small">${w.wrong} fallo${w.wrong > 1 ? "s" : ""}</span></div>`).join("") : `<p class="muted">Aún no hay datos suficientes. ¡Bien!</p>`}</div>
      <div class="card"><h2>Gramática a reforzar</h2>${p.weak_topics.length ? p.weak_topics.map((t) => `<div class="weak-row"><a href="#/apuntes/gram/${t.id}">🧩 ${esc(t.title)}</a><button class="btn small" data-sheet="${t.id}">Practicar</button></div>`).join("") : `<p class="muted">Ningún tema por debajo del 75 % de aciertos.</p>`}</div>
    </div>`);
  $("#weak").addEventListener("click", () => startSession("/api/practice?kind=weak"));
  $$("[data-sheet]").forEach((b) => b.addEventListener("click", () => startSession(`/api/practice?kind=sheet&ref=${b.dataset.sheet}`)));
}

// ====================================================================== ajustes
async function viewSettings() {
  const s = await api.get("/api/settings");
  Object.assign(S.settings, s);
  const voices = S.voices;
  mount("ajustes", `<div class="view-head"><div><h1>Ajustes</h1><p class="muted">Versión ${esc(s.version)}</p></div></div>
    <div class="grid g2">
      <div class="card stack voicecard" id="voz"><div class="row" style="justify-content:space-between"><h2 style="margin:0">Voz natural</h2>
          <span class="chip ${s.voice_engine === "azure" && s.azure_key_set ? "on" : ""}">${s.voice_engine === "azure" && s.azure_key_set ? "✓ Voz natural activa (Azure)" : "Ahora: voz del Mac"}</span></div>
        <p class="muted" style="margin:0">Para entender bien la pronunciación necesitas voces grabadas de personas reales. Las de Azure son neuronales y suenan casi humanas. El plan gratuito incluye 500 000 caracteres al mes, y todo el contenido de la app ocupa unos 30 000.</p>
        <div class="grid g2">
          <div>
            ${s.azure_key_set ? "" : `<ol class="steps">
              <li>Crea una cuenta gratuita en <b>azure.microsoft.com/free</b>. Te pedirán una tarjeta solo para verificar tu identidad: con el plan F0 no se cobra nada.</li>
              <li>En <b>portal.azure.com</b>, busca «Speech» (Servicios de voz) y pulsa <b>Crear</b>. Plan de tarifa: <b>Free F0</b>. Región: <b>West Europe</b>.</li>
              <li>Abre el recurso → <b>Claves y punto de conexión</b> → copia la <b>Clave 1</b>.</li>
              <li>Pégala aquí y pulsa <b>Guardar y probar</b>.</li></ol>`}
            <label class="field">Clave ${s.azure_key_set ? `<span class="chip small">guardada ✓</span>` : ""}</label><input type="password" id="akey" placeholder="${s.azure_key_set ? "•••••••• (déjala vacía para no cambiarla)" : "Pega la Clave 1 aquí"}">
            <label class="field" style="margin-top:10px">Región</label><input type="text" id="aregion" value="${esc(s.azure_region)}">
          </div>
          <div>
            <label class="field">Voz alemana</label><select id="avoice">${s.azure_voices.filter((v) => !v[0].startsWith("de-CH")).map((v) => `<option value="${v[0]}" ${v[0] === s.azure_voice ? "selected" : ""}>${esc(v[1])}</option>`).join("")}</select>
            <label class="field" style="margin-top:10px">Voz suiza</label><select id="avoicech">${s.azure_voices.filter((v) => v[0].startsWith("de-CH")).map((v) => `<option value="${v[0]}" ${v[0] === s.azure_voice_ch ? "selected" : ""}>${esc(v[1])}</option>`).join("")}</select>
            <div><label class="field" style="margin-top:10px">Velocidad: <span id="ratev">${Number(s.rate).toFixed(2)}</span>×</label><input type="range" id="rate" min="0.6" max="1.2" step="0.05" value="${s.rate}"></div>
            <div class="row" style="margin-top:12px"><button class="btn primary" id="asave">Guardar y probar</button>${s.azure_key_set ? `<button class="btn ghost" id="aclear">Quitar clave</button>` : ""}</div>
          </div>
        </div>
        ${s.azure_key_set ? `<div class="tip"><b>Usar sin conexión:</b> descarga una vez todos los audios (unos 1 200, tarda alrededor de una hora; puedes seguir usando la app mientras tanto).
          <div class="row" style="margin-top:10px"><button class="btn" id="prefetch">⬇ Descargar todos los audios</button><span class="muted small" id="pfstat"></span></div>
          <div class="bar" style="margin-top:10px"><i id="pfbar" style="width:0%"></i></div></div>` : ""}
        <div class="row"><button class="btn" id="test-voice">🔊 Probar voz</button><button class="btn" id="test-ch"><span class="swissflag">+</span> Probar voz suiza</button>
          <span class="muted small">Motor:</span><button class="chip ${s.voice_engine === "azure" ? "on" : ""}" data-engine="azure">Azure</button><button class="chip ${s.voice_engine !== "azure" ? "on" : ""}" data-engine="system">Mac (sin conexión)</button></div>
        <details><summary class="small"><b>Voz de reserva del Mac</b> (se usa si no hay conexión o Azure falla)</summary>
          <select id="sysvoice" style="margin-top:10px">${voices.length ? voices.map((v) => `<option value="${esc(v.name)}" ${v.name === s.system_voice ? "selected" : ""}>${esc(v.name)} (${esc(v.lang)})</option>`).join("") : `<option value="">No se han encontrado voces alemanas</option>`}</select>
          <p class="small muted">Para mejorarla: Ajustes del Sistema → Accesibilidad → Contenido leído → Voz del sistema → Gestionar voces → Alemán → descarga las voces «premium» o «mejorada».</p>
        </details>
      </div>
      <div class="card stack"><h2>Tu sesión</h2>
        <div><label class="field">Duración: <span id="minv">${s.minutes}</span> min</label><input type="range" id="minutes" min="10" max="60" step="5" value="${s.minutes}"></div>
        <div><label class="field">Ejercicios por bloque</label><div class="choices" style="margin:0">${[5, 8, 12].map((n) => `<button class="chip ${Number(s.block_size) === n ? "on" : ""}" data-block="${n}">${n}</button>`).join("")}</div>
          <p class="small muted">Bloques más cortos = pausas más frecuentes.</p></div>
        <label class="row"><input type="checkbox" id="timer" ${s.show_timer !== false ? "checked" : ""}> Mostrar el tiempo durante la sesión</label>
        <div><label class="field">Tu nombre</label><input type="text" id="name" value="${esc(s.name || "")}"></div>
      </div>
      <div class="card stack"><h2>Nivel</h2>
        <div class="choices" style="margin:0">${LEVELS.map((l) => `<button class="chip ${s.level === l ? "on" : ""}" data-level="${l}">${l}</button>`).join("")}</div>
        <p class="small muted">La app sube de nivel sola cuando has visto casi todo el tuyo con buenos resultados. Aquí puedes cambiarlo a mano.</p>
        <button class="btn" id="retest">Repetir el test de nivel</button>
        <h2 style="margin-top:24px">Apariencia</h2>
        <div class="choices" style="margin:0">${[["light", "Clara · blanco hueso"], ["dark", "Oscura"]].map(([k, l]) => `<button class="chip ${(s.theme === "dark" ? "dark" : "light") === k ? "on" : ""}" data-theme="${k}">${l}</button>`).join("")}</div>
      </div>
      <div class="card stack"><h2>Tus datos</h2>
        <p class="muted small">Todo se guarda solo en tu Mac, en:<br><code style="word-break:break-all">${esc(s.data_dir)}</code></p>
        <a class="btn primary" href="/api/backup">⬇ Descargar copia de seguridad</a>
        <a class="btn" href="/api/export">Exportar mis datos (JSON)</a>
        <div><label class="field">Restaurar una copia</label><input type="file" id="restore" accept=".zip">
          <p class="small muted">Antes de restaurar, la app guarda automáticamente una copia del estado actual.</p></div>
      </div>
    </div>`);

  const save = async (d) => { await api.post("/api/settings", d); Object.assign(S.settings, d); };
  $("#minutes").addEventListener("input", (e) => { $("#minv").textContent = e.target.value; });
  $("#minutes").addEventListener("change", (e) => save({ minutes: Number(e.target.value) }));
  $$("[data-block]").forEach((b) => b.addEventListener("click", () => { save({ block_size: Number(b.dataset.block) }); $$("[data-block]").forEach((x) => x.classList.toggle("on", x === b)); }));
  $("#timer").addEventListener("change", (e) => save({ show_timer: e.target.checked }));
  $("#name").addEventListener("change", (e) => save({ name: e.target.value.trim() }));
  $$("[data-level]").forEach((b) => b.addEventListener("click", () => { save({ level: b.dataset.level }); $$("[data-level]").forEach((x) => x.classList.toggle("on", x === b)); toast(`Nivel cambiado a ${b.dataset.level}`); }));
  $("#retest").addEventListener("click", () => { location.hash = "#/test"; });
  $$("[data-theme]").forEach((b) => b.addEventListener("click", () => { save({ theme: b.dataset.theme }).then(applyTheme); $$("[data-theme]").forEach((x) => x.classList.toggle("on", x === b)); }));
  $$("[data-engine]").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.engine === "azure" && !S.settings.azure_key_set) { toast("Primero pega tu clave de Azure y pulsa «Guardar y probar»."); $("#akey").focus(); return; }
    save({ voice_engine: b.dataset.engine }); $$("[data-engine]").forEach((x) => x.classList.toggle("on", x === b));
  }));
  $("#sysvoice").addEventListener("change", (e) => save({ system_voice: e.target.value }));
  $("#rate").addEventListener("input", (e) => { $("#ratev").textContent = Number(e.target.value).toFixed(2); });
  $("#rate").addEventListener("change", (e) => save({ rate: Number(e.target.value) }));
  $("#test-voice").addEventListener("click", () => TTS.speak("Grüezi! Ich heiße Anna und arbeite als Grafikdesignerin in Basel."));
  $("#test-ch").addEventListener("click", () => {
    if (S.settings.voice_engine !== "azure" && !S.voices.some((v) => /de[-_]CH/i.test(v.lang))) toast("Tu Mac no tiene voz suiza: se usará la alemana. Con Azure tendrás Leni o Jan.");
    TTS.speak("Grüezi mitenand! Mir näme s Tram zum Bahnhof.", { swiss: true });
  });
  $("#asave").addEventListener("click", async () => {
    const d = { azure_region: $("#aregion").value.trim(), azure_voice: $("#avoice").value, azure_voice_ch: $("#avoicech").value };
    const k = $("#akey").value.trim();
    if (k) d.azure_key = k;
    await api.post("/api/settings", d);
    const fresh = await api.get("/api/settings");
    Object.assign(S.settings, fresh);
    if (!fresh.azure_key_set) { toast("Falta la clave de Azure."); return; }
    const r = await fetch(`/api/tts?text=${encodeURIComponent("Hallo! Die Verbindung funktioniert.")}&voice=${encodeURIComponent(d.azure_voice)}`);
    if (r.ok) {
      await save({ voice_engine: "azure" });
      new Audio(URL.createObjectURL(await r.blob())).play();
      toast("Azure funciona. Voz activada.");
      viewSettings();
    } else {
      const e = await r.json().catch(() => ({}));
      toast(e.error === "azure-401" ? "La clave no es válida para esa región." : `Azure no responde (${e.error || r.status}). Revisa la clave, la región y tu conexión.`, 5000);
    }
  });
  const pfPoll = async () => {
    const st = await api.get("/api/audio/status");
    if (!$("#pfstat")) return;
    $("#pfstat").textContent = st.total ? `${st.done} / ${st.total}${st.running ? " · descargando…" : st.done >= st.total ? " · ✓ completo" : ""}${st.last_error ? " · último error: " + st.last_error : ""}` : "";
    $("#pfbar").style.width = st.total ? `${(st.done / st.total) * 100}%` : "0%";
    if (st.running) setTimeout(pfPoll, 3000);
  };
  if ($("#prefetch")) {
    pfPoll();
    $("#prefetch").addEventListener("click", async () => { await api.post("/api/audio/prefetch"); pfPoll(); });
  }
  if ($("#aclear")) $("#aclear").addEventListener("click", async () => { await api.post("/api/settings", { azure_key_clear: true, voice_engine: "system" }); toast("Clave eliminada"); viewSettings(); });
  $("#restore").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f || !confirm("Se sustituirá tu progreso actual por el de la copia. ¿Continuar?")) return;
    const r = await fetch("/api/restore", { method: "POST", body: await f.arrayBuffer() });
    const j = await r.json();
    toast(j.ok ? "Copia restaurada" : j.error, 4000);
    if (j.ok) { S.lib = null; boot(); }
  });
}

// ====================================================================== arranque
async function boot() {
  S.settings = await api.get("/api/settings");
  applyTheme();
  TTS.init();
  route();
}
window.addEventListener("hashchange", () => { document.onkeydown = null; S.lib = location.hash.startsWith("#/apuntes") ? S.lib : null; route(); });
setInterval(() => fetch("/api/ping").catch(() => {}), 60000);
fetch("/api/ping");
boot();
