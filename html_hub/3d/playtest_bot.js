/* playtest_bot.js -- DEBUG ONLY. A bot that plays the whole story like a player and writes a report.

   Served by hub_server.py only when the server runs with --debug (DEBUG=1), and only loaded by the pages when the server
   reports debug mode (hub3d.js via state.debug, the battle page via its debug check). It runs in two places:

   HUB (the 3D scenes): reads every scene file (html_hub/3d/*.json) and plays them the way the offline walker
     (game/playtest_walker.py) does: talk to everyone, step on every trigger zone, take every warp, win every fight,
     follow the quest marks. It moves by teleporting next to the thing it wants (so it is not a walking test), but it
     asks the game's own pathfinder whether each NPC / zone can be reached on foot and reports the ones that cannot.
     Dialogue and cutscenes play through the real script engine. Gear is bought through the real shop API, the
     Colosseum ladder is fought for real when a rank gate needs it, and defeats are retried (and, after three, helped
     with a few wild fights and then a logged cheat so the run can continue).
   BATTLE: switches the existing battle bot on, clicks through dialogue / level-ups / the result screen, retries
     defeats, and logs every result.

   Everything it sees goes to saves/playtest_log.jsonl and saves/playtest_live_report.md (through /api/debug/bot_log).
   Start / pause / fresh run from the yellow "Playtest bot" panel (bottom-left of the hub). Console: window.__ptBot.
*/
(function () {
  "use strict";
  if (window.__ptBot || window.__ptBotLoaded) return;
  window.__ptBotLoaded = true;
  let unloading = false;                 // the page is being left (a fight starting, a scene change): in-flight requests fail on purpose
  window.addEventListener("pagehide", () => { unloading = true; });
  window.addEventListener("beforeunload", () => { unloading = true; });
  const IS_BATTLE = location.pathname.indexOf("/battle") === 0;
  const SCENES = ["island", "forest", "dungeon", "outside", "olympus", "prison", "vault", "reach", "asteroid"];
  const KEY = "ptBot";
  const TICK_MS = 350;
  const IDLE_LIMIT_S = 80;               // no progress for this long = stuck
  const MAIN_DONE_FALLBACK = "rc_end";   // the last main quest's done flag, if quests.json cannot be read
  const now = () => Date.now();

  /* ------------------------------------------------------------------ persisted run state */
  function defaults() {
    return { on: false, mode: "full", watch: true, run: null, t0: 0, seq: 0, sentSeq: 0, log: [], fired: {}, defeats: {}, battles: [],
      assists: [], counts: {}, flagsSeen: [], visitedScenes: [], encTested: {}, shopped: {}, rests: 0, arenaFights: 0, arenaLosses: 0,
      lastProgress: 0, lastTick: 0, stuckLevel: 0, pending: null, assist: null, done: "", doneAt: 0, smoke: false };
  }
  let cfg = (function () { try { return Object.assign(defaults(), JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) { return defaults(); } })();
  function save() { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch (e) { /* storage full / blocked: the run still works */ } }
  const curScene = () => { try { const a = window.Hub3D && Hub3D.botApi && Hub3D.botApi(); const S = a && a.S(); return (S && S.name) || new URLSearchParams(location.search).get("scene") || ""; } catch (e) { return ""; } };

  function log(kind, msg, extra) {
    const e = Object.assign({ n: ++cfg.seq, t: cfg.t0 ? Math.round((now() - cfg.t0) / 1000) : 0, kind, msg: String(msg).slice(0, 400), ctx: IS_BATTLE ? "battle" : "hub", scene: curScene() }, extra || {});
    cfg.log.push(e);
    if (cfg.log.length > 1200) cfg.log.splice(0, cfg.log.length - 900);
    save();
    try { console.log("[playtest]", kind, e.msg); } catch (x) { /* ignore */ }
    return e;
  }
  let flushing = false;
  async function flush(report) {
    if (flushing && !report) return;
    flushing = true;
    try {
      const lines = cfg.log.filter((e) => e.n > cfg.sentSeq).slice(0, 150);
      if (!lines.length && !report) return;
      const body = JSON.stringify({ run: cfg.run, lines, report: report || undefined });
      const r = await fetch("/api/debug/bot_log", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: body.length < 60000 });
      if (r.ok && lines.length) { cfg.sentSeq = lines[lines.length - 1].n; save(); }
    } catch (e) { /* the server may be mid page-change; the lines stay queued */ } finally { flushing = false; }
  }
  const jget = async (u) => { const r = await fetch(u, { cache: "no-store" }); if (!r.ok) throw new Error(u + " -> HTTP " + r.status); return r.json(); };
  const jpost = async (u, b) => { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }); if (!r.ok) throw new Error(u + " -> HTTP " + r.status); return r.json(); };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const progress = () => { cfg.lastProgress = now(); cfg.stuckLevel = 0; };

  /* ------------------------------------------------------------------ error / traffic capture */
  window.addEventListener("error", (ev) => log("error", "JS error: " + (ev.message || "?") + " @ " + String(ev.filename || "").split("/").pop() + ":" + ev.lineno));
  window.addEventListener("unhandledrejection", (ev) => log("error", "Unhandled promise rejection: " + String((ev.reason && ev.reason.message) || ev.reason)));
  const origWarn = console.warn;
  console.warn = function () { try { const s = Array.prototype.join.call(arguments, " "); if (/\[Hub3D\]|failed|could not/i.test(s)) log("warn", "console.warn: " + s); } catch (e) { /* ignore */ } return origWarn.apply(console, arguments); };
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const p = origFetch.apply(this, arguments);
    if (cfg.on && url.indexOf("/api/") === 0 && url.indexOf("/api/debug/bot_log") !== 0) {
      p.then((r) => { if (!r.ok) log("error", "HTTP " + r.status + " from " + url.split("?")[0]); }, (e) => { if (!unloading) log("error", "request failed: " + url.split("?")[0] + " (" + e.message + ")"); });
      if (url.indexOf("/api/world/hub_battle") === 0 && init && init.body) {
        try { const b = JSON.parse(init.body); if (!b.retry) { cfg.pending = { boss: b.boss_id || "", level: b.level || b.level_min || 0, key: "", scene: curScene(), t: now() }; save(); } } catch (e) { /* ignore */ }
      }
    }
    return p;
  };

  /* ------------------------------------------------------------------ flag logic (same rules as hub3d.js / game/playtest_walker.py) */
  const hasF = (F, spec) => !spec || String(spec).split(",").every((t) => { t = t.trim(); return !t || (t[0] === "!" ? !F.has(t.slice(1)) : F.has(t)); });
  const visibleF = (o, F) => (!o.hideIf || !hasF(F, o.hideIf)) && (!o.showIf || hasF(F, o.showIf));
  let scenesDef = {}, quests = { quests: [], marks: {} };
  function minRankOf(e, scene) { let m = e.minRank; if (typeof m === "string") m = (scenesDef[scene] || {})[m]; return +m || 0; }
  function condF(e, scene, F, R, blocks) {
    if (e.if && !hasF(F, e.if)) return false;
    if (e.unless && hasF(F, e.unless)) return false;
    const mr = minRankOf(e, scene);
    if (mr && R < mr) { if (blocks) blocks.push({ scene, needs: mr }); return false; }
    return true;
  }
  function simulate(actions, scene, F, R, blocks) {
    const G = new Set(F); let outcome = "end", pa = null;
    for (const a of actions) {
      if (!condF(a, scene, G, R, blocks)) continue;
      if (a.type === "flag" && a.key) G.add(a.key);
      else if (a.type === "unflag") { if (a.key) G.delete(a.key); if (a.prefix) for (const k of [...G]) if (k.indexOf(a.prefix) === 0) G.delete(k); }
      else if (a.type === "reset_progress") { for (const k of [...G]) if (a.prefix && k.indexOf(a.prefix) === 0) G.delete(k); }
      else if (a.type === "warp") { outcome = "warp"; pa = a; break; }
      else if (a.type === "battle") { outcome = "battle"; pa = a; break; }
    }
    return { outcome, a: pa, G };
  }
  function triggersOf(scene, F) {
    const d = scenesDef[scene]; if (!d) return [];
    const out = [];
    for (const e of d.events || []) if (visibleF(e, F)) out.push({ kind: "event", id: e.id || "?", o: e });
    for (const n of d.npcs || []) if (visibleF(n, F)) out.push({ kind: "npc", id: n.id || "?", o: n });
    return out;
  }
  function markOf(scene, id, F, R) {
    const spec = (quests.marks || {})[scene + "/" + id];
    if (typeof spec === "string") return spec;
    if (Array.isArray(spec)) { for (const m of spec) if (condF(m, scene, F, R, null)) return m.mark || ""; }
    return "";
  }
  function warpGraph(F, R) {
    const g = {};
    for (const s of Object.keys(scenesDef)) {
      g[s] = [];
      for (const t of triggersOf(s, F)) {
        const w = (t.o.actions || []).find((a) => a.type === "warp" && condF(a, s, F, R, null));
        if (w && scenesDef[w.scene]) g[s].push({ t, dest: w.scene });
      }
    }
    return g;
  }
  function reachable(src, F, R) {
    const g = warpGraph(F, R), paths = {}; paths[src] = []; const q = [src];
    while (q.length) { const cur = q.shift(); for (const { t, dest } of g[cur] || []) if (!(dest in paths)) { paths[dest] = paths[cur].concat([{ scene: cur, t, dest }]); q.push(dest); } }
    return paths;
  }
  const hasBattle = (o) => (o.actions || []).some((a) => a.type === "battle");
  function plan(F, R, here) {
    const blocks = [], reach = reachable(here, F, R), cands = [];
    for (const sc of Object.keys(reach)) {
      for (const e of (scenesDef[sc] || {}).autorun || []) {          // an autorun waiting on a Colosseum rank (the Pit's freedom)
        if (hasF(F, e.if) && !(e.unless && hasF(F, e.unless)) && minRankOf(e, sc) > R) blocks.push({ scene: sc, needs: minRankOf(e, sc) });
      }
      for (const t of triggersOf(sc, F)) {
        const key = sc + "/" + t.kind + ":" + t.id;
        if ((cfg.fired[key] || 0) >= (hasBattle(t.o) ? 10 : 6)) continue;
        if (!(t.o.actions || []).length) continue;
        const sim = simulate(t.o.actions, sc, F, R, blocks);
        const added = [...sim.G].filter((x) => !F.has(x));
        if (sim.outcome === "battle" && sim.a.key && !F.has(sim.a.key)) added.push(sim.a.key);
        if (!added.length) continue;
        const mk = markOf(sc, t.id, F, R);
        cands.push({ scene: sc, t, path: reach[sc], dist: reach[sc].length, main: mk.indexOf("main") === 0, side: mk.indexOf("side") === 0 || String(t.id).indexOf("sq_") === 0, key, battle: hasBattle(t.o) });
      }
    }
    return { cands, blocks };
  }
  function pick(cands) {
    const nearest = (pool) => pool.reduce((a, b) => (a && a.dist <= b.dist ? a : b), null);
    if (cfg.mode === "full") { const p = nearest(cands.filter((c) => c.side && !c.main)); if (p) return p; }
    let p = nearest(cands.filter((c) => c.main)); if (p) return p;
    p = nearest(cands.filter((c) => !c.side)); if (p) return p;
    return cfg.mode === "full" ? nearest(cands) : null;
  }

  /* ------------------------------------------------------------------ HUB: driving the scene */
  let api = null, busy = false, lastScene = null, sceneAt = 0, lastPos = null, prevFlagCount = -1, sayWaitSince = 0, lastSayText = "", loadedData = false, lastTickSig = "";
  const getApi = () => { try { return window.Hub3D && Hub3D.botApi ? Hub3D.botApi() : null; } catch (e) { return null; } };
  const flagsNow = () => api.cleared();
  const rankNow = () => ((api.state() && api.state().ladder && api.state().ladder.rank) || 0);

  async function loadData() {
    scenesDef = {};
    await Promise.all(SCENES.map(async (s) => { try { scenesDef[s] = await jget("/hub3d/" + s + ".json"); } catch (e) { log("error", "cannot read scene file " + s + ": " + e.message); } }));
    try { quests = await jget("/hub3d/quests.json"); } catch (e) { log("warn", "quests.json unreadable: " + e.message); }
    loadedData = Object.keys(scenesDef).length > 0;
  }
  const mainDoneFlags = () => { const m = (quests.quests || []).filter((q) => q.kind === "main").map((q) => q.done).filter(Boolean); return m.length ? m : [MAIN_DONE_FALLBACK]; };

  function closeModals() {
    const tut = document.getElementById("tut-overlay");
    if (tut && tut.classList.contains("open")) { const b = tut.querySelector("button"); if (b) { b.click(); log("info", "closed the tutorial overlay"); return true; } }
    return false;
  }
  function sayVisible() { const el = api.say(); return !!el && el.style.display !== "none" && el.offsetParent !== null; }
  function handleScript(sc) {
    if (sc.choosing) { api.choose && api.choose(0); progress(); return; }                                // first option = accept / play / continue
    if (cfg.watch === false && sc.cineRun && !sc.skip) { api.skip(); return; }
    if (sc.waiting && !sc.lock) {
      if (!sayWaitSince) sayWaitSince = now();
      const vis = sayVisible();
      if (vis || now() - sayWaitSince > 6000) {
        const el = api.say(); const txt = el ? ((el.querySelector(".s-who") || {}).textContent || "") + ": " + ((el.querySelector(".s-text") || {}).textContent || "") : "";
        if (!vis) log("warn", "a script was waiting 6 s with no dialogue box showing (async action never answered?)");
        lastSayText = txt.slice(0, 160); cfg.counts.say = (cfg.counts.say || 0) + 1; sayWaitSince = 0; progress(); api.advance();
      }
    } else sayWaitSince = 0;
  }

  async function checkReach(S, t) {
    const key = S.name + "/" + t.kind + ":" + t.id;
    if (cfg.counts["reach:" + key]) return; cfg.counts["reach:" + key] = 1;
    try {
      const sp = (lastPos && lastPos.scene === S.name) ? lastPos : (S.def.spawn || { x: S.player.x, z: S.player.z });
      const r = api.findPath(sp.x, sp.z, t.o.x, t.o.z);
      const last = (r.pts && r.pts.length) ? r.pts[r.pts.length - 1] : { x: sp.x, z: sp.z };
      const d = Math.hypot(last.x - t.o.x, last.z - t.o.z);
      if (d > 3.5) log("walk", "the game's pathfinder finds no route to " + key + " from " + (lastPos && lastPos.scene === S.name ? "the previous stop (" + lastPos.id + ")" : "the scene spawn") + " (stops " + d.toFixed(0) + " units short)");
    } catch (e) { /* pathfinding is a bonus check */ }
  }

  async function fireTrigger(scene, t) {
    const S = api.S(), key = scene + "/" + t.kind + ":" + t.id;
    const live = t.kind === "npc" ? S.npcs.find((n) => n.id === t.id) : S.events.find((e) => e.id === t.id);
    cfg.fired[key] = (cfg.fired[key] || 0) + 1; save();
    if (!live) { log("warn", "scene file says " + key + " is visible, but the loaded scene does not have it (flags / filtering differ)"); cfg.fired[key] += 3; return; }
    await checkReach(S, t);
    const p = S.player; p.target = null; p.wantNpc = null; p.moving = false;
    log("fire", key + (hasBattle(t.o) ? " [fight]" : ""));
    lastPos = { scene: S.name, x: live.x, z: live.z, id: t.id };
    if (t.kind === "npc") { p.x = live.x + 0.9; p.z = live.z + 0.9; api.interact(live); return; }
    if (live.trigger === "talk") { p.x = live.x; p.z = live.z; api.primeEvents(); api.stepEvents(); api.run(S.activeEv || live); return; }
    p.x = live.x - live.w / 2 - 2.2; p.z = live.z; api.primeEvents();        // start outside the zone, then step in: a real "touch"
    p.x = live.x; p.z = live.z; api.stepEvents();
  }

  /* --- upkeep done through the same APIs the screens use */
  async function upkeepBeforeFight() {
    try {
      const m = await jget("/api/menu/state");
      const worst = Math.min.apply(null, (m.party || []).map((h) => (h.hp == null ? 1 : h.hp / Math.max(1, (h.stats || {}).max_hp || 1))).concat([1]));
      if (worst < 0.5) { await jpost("/api/menu/rest", {}); cfg.rests++; log("rest", "party at " + Math.round(worst * 100) + "% HP: rested before the next fight"); }
    } catch (e) { log("warn", "upkeep check failed: " + e.message); }
  }
  async function shopIfAny(S) {
    for (const n of S.npcs || []) {
      if (n.action !== "shop") continue;
      const vendor = S.name + "/" + n.id, wins = cfg.counts["battle_win"] || 0;
      if (cfg.shopped[vendor] != null && wins < cfg.shopped[vendor] + 2) continue;
      cfg.shopped[vendor] = wins; save();
      try { await shopRoutine(vendor); } catch (e) { log("error", "shopping at " + vendor + " failed: " + e.message); }
    }
  }
  async function shopRoutine(vendor) {
    let sh = await jget("/api/shop?vendor=" + encodeURIComponent(vendor));
    const story = (api.state().story_party || []);
    if (!story.length) return;
    let bought = [];
    const W = { max_hp: 0.1, max_mp: 0.05, atk: 1, def_: 1, mag: 1, res: 0.8, spd: 0.6, luk: 0.3 };
    for (let round = 0; round < 12; round++) {
      let best = null;
      for (const eq of sh.equipment || []) {
        for (const h of story) {
          const fit = (eq.fits || {})[h.id]; if (!fit || !fit.can || !fit.delta) continue;
          let score = 0; for (const k in fit.delta) score += (W[k] || 0) * fit.delta[k];
          if (score > 0.5 && eq.cost <= sh.money * 0.7 && (!best || score / Math.max(1, eq.cost) > best.v)) best = { eq, h, v: score / Math.max(1, eq.cost) };
        }
      }
      if (!best) break;
      const r = await jpost("/api/shop/buy_equip", { equipment_id: best.eq.id, character_id: best.h.id });
      if (!r.ok) { log("warn", "buy_equip refused: " + r.message); break; }
      bought.push(best.eq.name + " -> " + best.h.name); sh = r;
    }
    for (const it of sh.items || []) {
      const want = it.id === "potion" ? 5 : (it.id === "ether" || it.id === "antidote") ? 2 : (it.id === "phoenix_down" ? 2 : 0);
      let have = it.owned || 0, guard = 0;
      while (have < want && it.cost <= sh.money * 0.5 && guard++ < 8) { const r = await jpost("/api/shop/buy_item", { item_id: it.id }); if (!r.ok) break; have++; sh = r; bought.push(it.name); }
    }
    log("shop", vendor + ": " + (bought.length ? bought.join(", ") : "nothing worth buying") + " (gold now " + sh.money + ")");
    if (api.state && window.Hub3D && Hub3D.onState) { try { const st = await jget("/api/state"); Hub3D.onState(st); } catch (e) { /* ignore */ } }
  }
  async function assistAfterDefeats(a) {
    // 1) three wild fights at party level, 2) one more honest try, 3) if the fight is still unbeatable: level everyone up (logged as a cheat)
    if ((cfg.grind || 0) < 3) {
      cfg.grind = (cfg.grind || 0) + 1; save();
      log("assist", "grinding: wild fight " + cfg.grind + "/3 before retrying " + a.key);
      await jpost("/api/world/hub_battle", { boss_id: "", level_rel: [-1, 0], pool: [] });
      cfg.pending = { boss: "", level: 0, key: "", scene: a.scene, t: now(), grind: true }; save();
      location.href = "/battle?return=hub3d&scene=" + encodeURIComponent(a.scene);
      return true;
    }
    if (!cfg.grindTried) {
      cfg.grindTried = true; cfg.assist = null; cfg.defeats[a.key] = 2; save();
      log("assist", "grinding done; one more honest try at " + a.key);
      return false;
    }
    const lv = Math.max.apply(null, (api.state().story_party || []).map((h) => h.level).concat([1])) + 2;
    await jpost("/api/debug/act", { action: "level_all", level: lv });
    cfg.assists.push({ t: Math.round((now() - cfg.t0) / 1000), what: "CHEAT level_all -> " + lv, why: a.key + " was lost 3 times, grinding did not help" });
    log("cheat", "CHEAT level_all -> " + lv + " (needed to get past " + a.key + ")");
    cfg.grind = 0; cfg.grindTried = false; cfg.defeats[a.key] = 0; cfg.assist = null; save();
    try { const st = await jget("/api/state"); Hub3D.onState(st); } catch (e) { /* ignore */ }
    return false;
  }

  /* --- Colosseum ladder, when a minRank gate needs a higher rank (the Pit's freedom rank, ...) */
  async function arenaStep(need) {
    const st = await jget("/api/state"), rank = (st.ladder && st.ladder.rank) || 0;
    if (rank >= need) return false;
    if (cfg.arenaFights >= 60 || cfg.arenaLosses >= 12) {
      await jpost("/api/debug/act", { action: "set_rank", rank: need });
      cfg.assists.push({ t: Math.round((now() - cfg.t0) / 1000), what: "CHEAT set_rank " + need, why: "arena fights did not reach rank " + need + " (" + cfg.arenaFights + " fights, " + cfg.arenaLosses + " losses)" });
      log("cheat", "CHEAT set_rank " + need);
      cfg.arenaFights = 0; cfg.arenaLosses = 0; save();
      const st2 = await jget("/api/state"); Hub3D.onState(st2);
      return false;
    }
    if (!st.slave && !st.arena_team) {
      if (st.money < st.arena_team_cost) { await jpost("/api/debug/act", { action: "add_money", amount: st.arena_team_cost }); cfg.assists.push({ t: Math.round((now() - cfg.t0) / 1000), what: "CHEAT add_money " + st.arena_team_cost, why: "could not afford the arena team" }); log("cheat", "CHEAT add_money for the arena team"); }
      const r = await jpost("/api/arena/buy_team", {}); log("arena", "bought the arena team: " + (r.message || ""));
    }
    let res;
    if (st.ladder && st.ladder.unlocked) { res = await jpost("/api/boss/challenge", {}); log("arena", "boss challenge for rank " + rank + ": " + (res.ok ? res.boss : res.message)); }
    if (!res || !res.ok) res = await jpost("/api/ladder/start", {});
    if (!res.ok) { log("warn", "ladder refused: " + (res.message || JSON.stringify(res))); cfg.arenaLosses++; save(); await sleep(1000); return true; }
    if (res.url === "/party") { const p = await jget("/api/party"); await jpost("/api/party/confirm", { ids: p.selected || [] }); }
    cfg.arenaFights++; cfg.pending = { boss: "", level: 0, key: "", scene: "arena", t: now(), arena: true }; save();
    log("arena", "arena fight " + cfg.arenaFights + " (rank " + rank + " -> need " + need + ")");
    location.href = "/battle";
    return true;
  }

  async function finish(reason, detail) {
    cfg.on = false; cfg.done = reason; cfg.doneAt = now(); save();
    log(reason === "complete" ? "done" : "stuck", reason.toUpperCase() + (detail ? ": " + detail : ""));
    if (reason === "complete" && !cfg.smoke) { cfg.smoke = true; await smoke(); }
    const rep = buildReport(); await flush(rep); updatePanel();
  }
  async function smoke() {
    for (const u of ["/", "/heroes", "/shop", "/party", "/summon", "/world", "/battle"]) {
      try { const r = await origFetch(u, { cache: "no-store" }); log(r.ok ? "smoke" : "error", "page " + u + " -> HTTP " + r.status); } catch (e) { log("error", "page " + u + " unreachable"); }
    }
    for (const u of ["/api/state", "/api/heroes", "/api/menu/state", "/api/summon/state", "/api/party", "/api/shop?vendor=olympus/shop", "/api/world/state"]) {
      try { const r = await origFetch(u, { cache: "no-store" }); if (!r.ok) log("error", "api " + u + " -> HTTP " + r.status); else { await r.json(); log("smoke", "api " + u + " ok"); } } catch (e) { log("error", "api " + u + " failed: " + e.message); }
    }
  }

  async function hubStep() {
    api = getApi();
    if (!api) return;
    if (!loadedData) { await loadData(); if (!loadedData) { await finish("stuck", "no scene files could be read"); return; } }
    const S = api.S();
    if (!S || S.switching || !api.hudLoaded()) return;
    if (S.name !== lastScene) {
      lastScene = S.name; sceneAt = now(); lastPos = null; progress();
      if (cfg.visitedScenes.indexOf(S.name) < 0) cfg.visitedScenes.push(S.name);
      log("scene", "entered " + S.name); save();
      await shopIfAny(S);
    }
    if (closeModals() || api.modalOpen()) return;
    const F = flagsNow();
    if (F.size !== prevFlagCount) {                                   // story progress: note every new flag
      const seen = new Set(cfg.flagsSeen), fresh = [...F].filter((x) => !seen.has(x));
      if (fresh.length) { log("flag", fresh.join(", ")); cfg.flagsSeen = [...new Set(cfg.flagsSeen.concat(fresh))]; progress(); }
      prevFlagCount = F.size;
    }
    const sc = api.script();
    if (sc) { handleScript(sc); return; }
    if (S.encGo) return;
    const R = rankNow(), st = api.state();
    if (!(st.story_party || []).length) { await finish("stuck", "no story heroes in the party"); return; }

    // a defeat sent us back here: help before the next attempt
    if (cfg.assist) { const a = cfg.assist; if (await assistAfterDefeats(a)) return; }

    // finished?
    if (mainDoneFlags().every((f) => F.has(f))) { await finish("complete", "all main quests done (" + mainDoneFlags().join(", ") + ")"); return; }

    // each scene's random encounters get one real fight (checks the pools / levels / enemy builders)
    if (cfg.mode === "full" && S.def && S.def.encounters && !cfg.encTested[S.name] && api.encounter) {
      cfg.encTested[S.name] = 1; save();
      const enc = S.def.encounters, zone = (enc.zones || []).find((z) => !z.safe);
      if (!enc.zones || zone) {
        if (zone) { S.player.x = zone.x; S.player.z = zone.z; }
        log("fire", S.name + ": forcing one random encounter"); await upkeepBeforeFight(); api.encounter(1e6); return;
      }
    }

    const { cands, blocks } = plan(F, R, S.name);
    const c = pick(cands);
    if (!c) {
      if (now() - sceneAt < 3000) return;                              // a scene's autorun starts about 0.7 s after it loads: let it
      const ar = (scenesDef[S.name] || {}).autorun || [], kick = "kick:" + S.name + ":" + F.size + ":" + R;
      if (ar.some((e) => condF(e, S.name, F, R, null)) && !cfg.counts[kick]) {      // an autorun entry matches now (a rank was earned, a flag changed): load the scene again like a page reload would
        cfg.counts[kick] = 1; log("info", "re-entering " + S.name + " so its autorun can run"); sceneAt = now();
        api.switchScene(S.name, S.player.x, S.player.z, true); return;
      }
      const need = blocks.filter((b) => b.needs > R).map((b) => b.needs);
      if (need.length) { if (await arenaStep(Math.min.apply(null, need))) return; return; }
      const open = (quests.quests || []).filter((q) => q.kind === "main" && !F.has(q.done)).map((q) => q.id + (F.has(q.accept) ? " (accepted)" : " (not started)"));
      await finish("stuck", "nothing left to do but the story is not finished; open main quests: " + open.join(", ") + "; last dialogue: " + lastSayText);
      return;
    }
    if (c.battle) await upkeepBeforeFight();
    if (c.path.length) { const hop = c.path[0]; if (hop.scene !== S.name) return; await fireTrigger(hop.scene, hop.t); return; }
    await fireTrigger(c.scene, c.t);
  }

  function watchdog() {
    if (!cfg.on || IS_BATTLE) return;
    const idle = (now() - cfg.lastProgress) / 1000;
    if (idle < IDLE_LIMIT_S) return;
    cfg.stuckLevel++; cfg.lastProgress = now(); save();
    const S = api && api.S && api.S();
    log("stuck", "no progress for " + IDLE_LIMIT_S + " s (level " + cfg.stuckLevel + ") in " + (S ? S.name : "?") + "; last dialogue: " + lastSayText);
    if (cfg.stuckLevel >= 3) { finish("stuck", "the bot made no progress for " + 3 * IDLE_LIMIT_S + " s in " + (S ? S.name : "?")); return; }
    try { if (api.endAmbush) api.endAmbush(); const sp = (S.def && S.def.spawn) || { x: 0, z: 0 }; if (cfg.stuckLevel === 2 && api.switchScene) api.switchScene(S.name, sp.x, sp.z, true); else { S.player.x = sp.x; S.player.z = sp.z; } } catch (e) { /* ignore */ }
  }

  /* ------------------------------------------------------------------ BATTLE page */
  let bt = { start: now(), reported: false, overlaySince: 0, hubClickAt: 0 };
  function battleStep() {
    try { sessionStorage.setItem("dbgAuto", "1"); } catch (e) { /* ignore */ }
    const P = new URLSearchParams(location.search), scene = P.get("scene") || "", key = P.get("key") || "";
    const abtn = document.getElementById("dbg-auto-btn");
    if (abtn && abtn.style.display !== "none" && /OFF/.test(abtn.textContent) && now() - bt.start > 5000 && now() - (bt.autoClick || 0) > 4000) { bt.autoClick = now(); abtn.click(); }
    const lv = document.getElementById("levelup-overlay");
    if (lv && getComputedStyle(lv).display !== "none") { const ok = document.getElementById("levelup-ok"); if (ok) { ok.click(); progress(); } return; }
    const dlg = document.getElementById("dialogue");
    if (dlg && getComputedStyle(dlg).display !== "none") { dlg.click(); progress(); return; }
    const ov = document.getElementById("end-overlay");
    if (ov && getComputedStyle(ov).display !== "none") {
      const result = (ov.className || "").trim().split(/\s+/).pop();
      if (!bt.reported) {
        bt.reported = true; bt.overlaySince = now();
        const info = cfg.pending || {};
        const bkey = key || (info.arena ? "arena" : "wild:" + scene);
        const entry = { t: Math.round((now() - cfg.t0) / 1000), scene: scene || info.scene || "", key: bkey, boss: info.boss || "", level: info.level || 0, result, secs: Math.round((now() - bt.start) / 1000) };
        cfg.battles.push(entry); cfg.counts["battle_" + (result === "victory" ? "win" : "loss")] = (cfg.counts["battle_" + (result === "victory" ? "win" : "loss")] || 0) + 1;
        log("battle", (entry.boss || entry.key) + " " + result.toUpperCase() + " in " + entry.secs + " s (" + entry.scene + ")", entry);
        if (info.arena && result !== "victory") cfg.arenaLosses++;
        if (result === "victory") cfg.defeats[bkey] = 0; else cfg.defeats[bkey] = (cfg.defeats[bkey] || 0) + 1;
        progress(); save(); flush();
      }
      const bkey = key || ((cfg.pending || {}).arena ? "arena" : "wild:" + scene);
      if (result === "victory") { goHub(); return; }
      const hub3d = P.get("return") === "hub3d" && !(cfg.pending || {}).arena;
      if (hub3d && (cfg.defeats[bkey] || 0) < 3) {                                 // "Retry Battle"
        const again = document.getElementById("btn-again");
        if (again && again.style.display !== "none" && !again.disabled && now() - bt.overlaySince > 1200) { again.click(); bt.overlaySince = now() + 99999; }
        return;
      }
      if (hub3d) { cfg.assist = { key: bkey, scene: scene || "olympus" }; save(); flush(); location.href = "/?view=3d&scene=" + encodeURIComponent(scene || "olympus"); return; }
      goHub();
      return;
    }
    const secs = (now() - bt.start) / 1000;
    if (secs > 360 && !bt.warned) { bt.warned = true; log("warn", "a battle has been running for " + Math.round(secs) + " s (bot stuck? scene " + scene + " key " + key + ")"); }
    if (secs > 900) { cfg.on = false; log("stuck", "battle ran over 15 minutes: bot stopped"); save(); flush(buildReport()); }
  }
  function goHub() {
    if (now() - bt.hubClickAt < 3500) return; bt.hubClickAt = now();
    const hb = document.getElementById("btn-hub");
    if (hb && getComputedStyle(hb).display !== "none" && !hb.disabled && !bt.clickedOnce) { bt.clickedOnce = true; hb.click(); return; }
    if (typeof window.returnToHub === "function") window.returnToHub(); else location.href = "/";
  }

  /* ------------------------------------------------------------------ report */
  function buildReport() {
    const mins = cfg.t0 ? ((cfg.doneAt || now()) - cfg.t0) / 60000 : 0, F = new Set(cfg.flagsSeen);
    const L = ["# Live playtest report", "",
      `Status: **${cfg.done ? cfg.done.toUpperCase() : (cfg.on ? "RUNNING" : "PAUSED")}**   Mode: ${cfg.mode}   Run time: ${mins.toFixed(1)} min   Run id: ${cfg.run}`, "",
      `Scenes visited: ${cfg.visitedScenes.join(" -> ") || "none"}`, `Story flags set: ${F.size}   Dialogue lines read: ${cfg.counts.say || 0}   Rests: ${cfg.rests}   Arena fights: ${cfg.arenaFights}`, ""];
    L.push("## Quests", "");
    for (const q of quests.quests || []) { const done = F.has(q.done), acc = F.has(q.accept); L.push(`- [${done ? "x" : " "}] ${q.kind}: ${q.title}${done ? "" : acc ? " (accepted, not finished)" : " (not started)"}`); }
    L.push("", "## Battles", "", "| # | time | scene | fight | level | result | secs |", "|---|---|---|---|---|---|---|");
    cfg.battles.forEach((b, i) => L.push(`| ${i + 1} | ${b.t}s | ${b.scene} | ${b.boss || b.key} | ${b.level || ""} | ${b.result} | ${b.secs} |`));
    const lost = {}; cfg.battles.filter((b) => b.result !== "victory").forEach((b) => { lost[b.key] = (lost[b.key] || 0) + 1; });
    if (Object.keys(lost).length) { L.push("", "Fights that were lost at least once (balance candidates):"); for (const k in lost) L.push(`- ${k}: lost ${lost[k]} time(s)`); }
    L.push("", "## Cheats / assists the bot needed", "");
    L.push(...(cfg.assists.length ? cfg.assists.map((a) => `- ${a.what} (at ${a.t}s): ${a.why}`) : ["- none: the bot got through on its own"]));
    for (const sev of ["error", "stuck", "warn", "walk"]) {
      const items = {}; cfg.log.filter((e) => e.kind === sev).forEach((e) => { const k = e.msg; items[k] = items[k] || { n: 0, scene: e.scene, t: e.t }; items[k].n++; });
      L.push("", `## ${sev === "warn" ? "Warnings" : sev === "stuck" ? "Stuck points" : sev === "walk" ? "Not reachable on foot (informational: the bot teleports, so doors that open later and scripted jumps also show up here)" : "Errors"} (${Object.keys(items).length})`, "");
      L.push(...(Object.keys(items).length ? Object.keys(items).map((k) => `- [${items[k].scene || "?"} @${items[k].t}s] ${k}${items[k].n > 1 ? " (x" + items[k].n + ")" : ""}`) : ["- none"]));
    }
    L.push("", "## Timeline (story flags, scenes, fights)", "");
    cfg.log.filter((e) => ["scene", "flag", "battle", "shop", "cheat", "assist", "arena", "rest", "done"].indexOf(e.kind) >= 0).slice(-260).forEach((e) => L.push(`- ${e.t}s ${e.kind}: ${e.msg}`));
    return L.join("\n") + "\n";
  }

  /* ------------------------------------------------------------------ control panel */
  let panel = null;
  function updatePanel() {
    if (!panel) return;
    const st = panel.querySelector(".pt-st");
    st.textContent = (cfg.done ? cfg.done.toUpperCase() : cfg.on ? "RUNNING" : "paused") + " | " + (curScene() || "-") + " | flags " + cfg.flagsSeen.length + " | fights " + cfg.battles.length;
    panel.querySelector(".pt-go").textContent = cfg.on ? "Pause" : (cfg.run && !cfg.done ? "Resume" : "Start");
    panel.querySelector(".pt-mode").textContent = "Mode: " + (cfg.mode === "full" ? "everything" : "main story only");
    panel.querySelector(".pt-watch").textContent = "Cutscenes: " + (cfg.watch === false ? "skip" : "watch");
  }
  function startRun(fresh) {
    if (!cfg.run || fresh) { const keep = { mode: cfg.mode, watch: cfg.watch }; cfg = Object.assign(defaults(), keep); cfg.run = now().toString(36); cfg.t0 = now(); log("start", "playtest run " + cfg.run + " (" + cfg.mode + ")"); }
    cfg.on = true; cfg.done = ""; cfg.lastProgress = now(); cfg.lastTick = now(); save(); updatePanel();
    try { sessionStorage.setItem("dbgAuto", "1"); } catch (e) { /* ignore */ }   // the battle page switches its bot on by itself
  }
  function buildPanel() {
    if (IS_BATTLE) {
      const b = document.createElement("div");
      b.style.cssText = "position:fixed;top:44px;left:50%;transform:translateX(-50%);z-index:99999;font:12px sans-serif;color:#ffe27a;background:rgba(20,16,0,.8);border:1px dashed #ffe27a;padding:3px 10px;border-radius:6px;cursor:pointer";
      b.textContent = "Playtest bot: " + (cfg.on ? "ON (click to stop)" : "off");
      b.onclick = () => { cfg.on = !cfg.on; save(); b.textContent = "Playtest bot: " + (cfg.on ? "ON (click to stop)" : "off"); };
      document.body.appendChild(b); return;
    }
    panel = document.createElement("div");
    panel.style.cssText = "position:fixed;left:8px;bottom:56px;z-index:99999;font:12px sans-serif;color:#ffe27a;background:rgba(20,16,0,.86);border:1px dashed #ffe27a;padding:6px 8px;border-radius:8px;max-width:330px";
    panel.innerHTML = '<div class="pt-title" style="font-weight:700;margin-bottom:3px;cursor:pointer" title="click to fold">Playtest bot (debug) &#9662;</div><div class="pt-body"><div class="pt-st" style="margin-bottom:5px"></div>' +
      '<button class="pt-go"></button> <button class="pt-fresh" title="Backs up your save, then starts a brand-new game">Fresh run</button> <button class="pt-mode"></button> <button class="pt-watch"></button> <button class="pt-rep">Report</button></div>';
    const fold = (on) => { panel.querySelector(".pt-body").style.display = on ? "none" : "block"; try { localStorage.setItem("ptBotFold", on ? "1" : "0"); } catch (e) { /* ignore */ } };
    let folded = false; try { folded = localStorage.getItem("ptBotFold") === "1"; } catch (e) { /* ignore */ }
    fold(folded);
    panel.querySelector(".pt-title").onclick = () => { folded = !folded; fold(folded); };
    panel.querySelectorAll("button").forEach((b) => { b.style.cssText = "font:11px sans-serif;margin:1px;padding:2px 6px;cursor:pointer"; });
    document.body.appendChild(panel);
    panel.querySelector(".pt-go").onclick = () => { if (cfg.on) { cfg.on = false; save(); flush(buildReport()); } else startRun(false); updatePanel(); };
    panel.querySelector(".pt-mode").onclick = () => { cfg.mode = cfg.mode === "full" ? "main" : "full"; save(); updatePanel(); };
    panel.querySelector(".pt-watch").onclick = () => { cfg.watch = cfg.watch === false; save(); updatePanel(); };
    panel.querySelector(".pt-rep").onclick = async () => { const r = buildReport(); await flush(r); alert("Report written to the saves folder (playtest_live_report.md).\n\n" + r.split("\n").slice(0, 12).join("\n")); };
    panel.querySelector(".pt-fresh").onclick = async () => {
      if (!confirm("Start a FRESH playtest? Your current save is copied to saves/playtest_backup_* first, then the game is reset to a new game.")) return;
      try {
        const b = await jpost("/api/debug/bot_backup", {}); if (!b.ok) throw new Error(b.message || "backup failed");
        await jpost("/api/debug/act", { action: "reset_game" });
        ["h3dCleared", "h3dUntracked"].forEach((k) => { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } });
        try { sessionStorage.clear(); } catch (e) { /* ignore */ }
        startRun(true); log("info", "fresh run; save backed up to " + b.path); await flush();
        location.href = "/";
      } catch (e) { alert("Could not start a fresh run: " + e.message); }
    };
    updatePanel(); setInterval(updatePanel, 1500);
  }

  /* ------------------------------------------------------------------ main loop */
  async function tick() {
    if (!cfg.on || busy) return;
    busy = true;
    try {
      cfg.lastTick = now();
      if (IS_BATTLE) battleStep(); else { watchdog(); await hubStep(); }
    } catch (e) { if (!unloading) log("error", "bot tick failed: " + (e && e.message)); }
    finally { busy = false; }
  }
  function init() {
    // a run left "on" long ago (the page was closed): do not suddenly start playing
    if (cfg.on && cfg.lastTick && now() - cfg.lastTick > 10 * 60000) { cfg.on = false; log("info", "the bot was left running more than 10 minutes ago: paused"); }
    buildPanel(); updatePanel();
    setInterval(tick, TICK_MS);
    setInterval(() => { if (cfg.on) flush(); }, 4000);
    window.addEventListener("beforeunload", () => { if (cfg.on) flush(); });
    window.__ptBot = { cfg: () => cfg, start: () => startRun(false), fresh: () => startRun(true), stop: () => { cfg.on = false; save(); }, report: buildReport, flush, plan: () => (api ? plan(flagsNow(), rankNow(), api.S().name) : null) };
    if (cfg.on) log("info", "resumed after a page change");
  }
  if (document.body) init(); else document.addEventListener("DOMContentLoaded", init);
})();
