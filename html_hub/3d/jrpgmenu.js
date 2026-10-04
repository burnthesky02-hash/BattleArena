/* jrpgmenu.js -- the Esc menu: party cards, Items, Magic (healing), Equip, Status, Save, Settings.
   Talks to /api/menu/* (state, use_item, cast, save) and /api/heroes/equip|unequip.
   Opens on Esc when Hub3D.canOpenMenu() says nothing else is going on (no dialogue / event / loading / modal).
   Keyboard: arrows or WASD move, Enter / E / Space confirm, Esc / Backspace back, Q and Tab switch hero. Mouse works too. */
(function () {
  "use strict";
  var M = window.JrpgMenu = {};
  var O = {}, root = null, st = null, isOpen = false, busy = false;
  var CMDS = ["Items", "Magic", "Equip", "Status", "Quests", "Bestiary", "Save", "Settings", "Close"];
  var TITLES = { main: "Main menu", items: "Check items", magic: "Cast magic", equip: "Change equipment", status: "Check status", quests: "Quest log", bestiary: "Bestiary", save: "Save game", settings: "Settings" };
  var STATS = [["max_hp", "HP"], ["max_mp", "MP"], ["atk", "ATK"], ["def_", "DEF"], ["mag", "MAG"], ["res", "RES"], ["spd", "SPD"], ["luk", "LUK"]];
  var SLOT_LABEL = { weapon: "Weapon", offhand: "Off-hand", armor: "Armor", helmet: "Helmet", boots: "Boots", accessory: "Accessory" };
  var WEIGHT = { light: 0, medium: 1, heavy: 2 }, ARMOR = { armor: 1, helmet: 1, boots: 1 };
  var mode = "main", ph = "cmd", cmd = 0, li = 0, ci = 0, cas = 0, si = 0, pi = 0, yes = 0, sr = 0, msg = "", msgBad = false, bz = 0, bst = null, qz = 0, qf = 0, qv = [];

  /* ---------- settings ---------- */
  var SET_KEY = "rpgSettings";
  function loadSettings() { var d = { music: 0.35, sfx: 0.7, hints: true }; try { var s = JSON.parse(localStorage.getItem(SET_KEY) || "{}"); for (var k in d) if (s[k] != null) d[k] = s[k]; } catch (e) {} return d; }
  var settings = loadSettings();
  function applySettings() {
    try { localStorage.setItem(SET_KEY, JSON.stringify(settings)); } catch (e) {}
    var s = document.getElementById("jm-hintstyle");
    if (!s) { s = document.createElement("style"); s.id = "jm-hintstyle"; document.head.appendChild(s); }
    s.textContent = settings.hints ? "" : ".h3d-hint{display:none!important}";
    try { window.dispatchEvent(new CustomEvent("rpg-settings", { detail: settings })); } catch (e) {}
  }
  M.settings = function () { return settings; };

  /* ---------- helpers ---------- */
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function sfx(n) { if (O.sfx && O.SFX && O.SFX[n]) O.sfx(O.SFX[n]); }
  function party() { return (st && st.party) || []; }
  function hero(i) { return party()[i]; }
  function canEquip(h, it) {
    if (it.slot === "weapon") return h.weapon_types.indexOf(it.subtype) !== -1;
    if (it.slot === "offhand") return h.offhand_types.indexOf(it.subtype) !== -1;
    if (ARMOR[it.slot]) return WEIGHT[it.subtype] <= WEIGHT[h.armor_weight];
    return true;
  }
  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(function (r) { return r.json(); });
  }
  function refresh() { return fetch("/api/menu/state").then(function (r) { return r.json(); }).then(function (s) { st = s; if (ci >= party().length) ci = Math.max(0, party().length - 1); }); }
  function say(t, bad) { msg = t || ""; msgBad = !!bad; }
  function usable(it) { return !it.revive && !it.cure_status && (it.heal_hp > 0 || it.heal_mp > 0); }
  function allSkills(h) { return (h && h.skills) || []; }
  function castable(s) { return s && s.kind === "heal"; }
  function candidates() {
    var h = hero(ci); if (!h) return [];
    var slot = st.slots[si], out = [];
    if (h.equipped[slot]) out.push({ unequip: true });
    st.stash.filter(function (s) { return s.slot === slot; }).forEach(function (s) { s.ok = canEquip(h, s); out.push(s); });
    return out;
  }
  function cardsActive() {
    return (mode === "items" && ph === "target") || (mode === "magic" && (ph === "caster" || ph === "target")) || ((mode === "equip" || mode === "status") && ph === "hero");
  }

  /* ---------- rendering ---------- */
  function bar(cls, label, v, max) {
    var p = max > 0 ? Math.max(0, Math.min(100, v / max * 100)) : 0;
    return '<div class="jm-bar ' + cls + '"><b>' + label + '</b><span class="jm-track"><i style="width:' + p + '%"></i></span><em>' + v + "/" + max + "</em></div>";
  }
  function cardsHtml() {
    var h = "", act = cardsActive();
    for (var i = 0; i < 4; i++) {
      var p = hero(i);
      if (!p) { h += '<div class="jm-card empty"><span>Empty</span></div>'; continue; }
      var next = p.xp_next == null ? "MAX" : Math.max(0, p.xp_next - p.xp);
      var sel = act && i === ci, dim = mode === "magic" && ph === "target" && false;
      h += '<div class="jm-card' + (sel ? " sel" : "") + (act ? " pick" : "") + (p.hp <= 0 ? " ko" : "") + '" data-a="card" data-i="' + i + '">' +
        '<img src="' + esc(p.portrait) + '" onerror="this.style.display=\'none\'" alt="">' +
        '<div class="jm-cinfo"><div class="jm-cls">' + esc(p.class_name) + '</div><div class="jm-nm">' + esc(p.name) + '</div>' +
        '<div class="jm-lv"><b>LV</b> ' + p.level + '</div><div class="jm-nx">Next level <b>' + next + (next === "MAX" ? "" : " XP") + '</b></div>' +
        bar("hp", "HP", p.hp, p.stats.max_hp) + bar("mp", "MP", p.mp, p.stats.max_mp) + "</div></div>";
    }
    return '<div class="jm-cards">' + h + "</div>";
  }
  function cmdListHtml() {
    var h = '<div class="jm-panel jm-cmds">';
    CMDS.forEach(function (c, i) { h += '<div class="jm-row' + (i === cmd ? " cur" : "") + (ph === "cmd" ? "" : " off") + '" data-a="cmd" data-i="' + i + '">' + c + "</div>"; });
    return h + "</div>";
  }
  function itemListHtml() {
    var inv = st.inventory, h = '<div class="jm-panel jm-list"><div class="jm-ptitle">Items</div><div class="jm-scroll">';
    if (!inv.length) h += '<div class="jm-empty">You are carrying nothing.</div>';
    inv.forEach(function (it, i) { h += '<div class="jm-row' + (i === li ? " cur" : "") + (usable(it) ? "" : " dim") + '" data-a="li" data-i="' + i + '"><span>' + esc(it.name) + "</span><em>x" + it.count + "</em></div>"; });
    h += "</div>";
    var it = inv[li]; h += '<div class="jm-desc">' + (it ? esc(it.description) + (usable(it) ? "" : " (Battle only.)") : "") + "</div></div>";
    return h;
  }
  function skillListHtml() {
    var h0 = hero(cas), ss = allSkills(h0);
    var h = '<div class="jm-panel jm-list"><div class="jm-ptitle">' + esc(h0 ? h0.name : "") + ' &middot; Magic</div><div class="jm-scroll">';
    ss.forEach(function (s, i) { h += '<div class="jm-row' + (i === li ? " cur" : "") + (!castable(s) || h0.mp < s.mp_cost ? " dim" : "") + '" data-a="li" data-i="' + i + '"><span>' + esc(s.name) + "</span><em>" + s.mp_cost + " MP" + (castable(s) ? "" : " &middot; battle") + "</em></div>"; });
    h += "</div>";
    var s = ss[li]; h += '<div class="jm-desc">' + (s ? esc(s.description || "") + (s.kind === "heal" ? (s.target === "all_allies" ? " (Whole party.)" : s.target === "self" ? " (Self.)" : "") : " (Battle only.)") + " Rank " + s.rank + "." : "") + "</div></div>";
    return h;
  }
  function infoHtml() {
    return '<div class="jm-panel jm-info"><div><b>Gold</b><span>' + (st.money || 0).toLocaleString() + '</span></div><div><b>Gems</b><span>' + (st.gems || 0) + '</span></div><div><b>Rank</b><span>' + (st.rank || 1) + '</span></div><div><b>Renown</b><span>' + (st.renown || 0) + "</span></div></div>";
  }
  function delta(h, slot, c) {
    var cur = (h.equipped[slot] && h.equipped[slot].bonuses) || {}, nw = c ? (c.unequip ? {} : (c.bonuses || {})) : cur, out = {};
    STATS.forEach(function (s) { out[s[0]] = (nw[s[0]] || 0) - (cur[s[0]] || 0); });
    return out;
  }
  function equipHtml() {
    var h = hero(ci), slot = st.slots[si], c = ph === "pick" ? candidates()[pi] : null, d = delta(h, slot, c);
    var o = '<div class="jm-panel jm-detail"><div class="jm-dhead"><img src="' + esc(h.portrait) + '" onerror="this.style.display=\'none\'" alt=""><div><div class="jm-cls">' + esc(h.class_name) + '</div><div class="jm-nm">' + esc(h.name) + ' <small>LV ' + h.level + '</small></div></div><div class="jm-hint">Q / Tab: next hero</div></div><div class="jm-cols">';
    o += '<div class="jm-col"><div class="jm-ptitle">Equipment</div>';
    st.slots.forEach(function (s, i) {
      var e = h.equipped[s];
      o += '<div class="jm-row' + (i === si ? " cur" : "") + (ph === "pick" && i !== si ? " off" : "") + '" data-a="slot" data-i="' + i + '"><b>' + SLOT_LABEL[s] + "</b><span>" + (e ? esc(e.name) : "&mdash;") + "</span></div>";
    });
    o += '</div><div class="jm-col"><div class="jm-ptitle">' + SLOT_LABEL[slot] + ' &middot; stash</div><div class="jm-scroll">';
    if (ph === "pick") {
      var list = candidates();
      if (!list.length) o += '<div class="jm-empty">Nothing to equip here.</div>';
      list.forEach(function (it, i) {
        o += '<div class="jm-row' + (i === pi ? " cur" : "") + (it.unequip || it.ok ? "" : " dim") + '" data-a="pick" data-i="' + i + '">' + (it.unequip ? "<span>&ndash; Unequip &ndash;</span>" : "<span>" + esc(it.name) + "</span><em>" + esc(it.bonus_text) + (it.ok ? "" : " (can't use)") + "</em>") + "</div>";
      });
    } else {
      var e = h.equipped[slot];
      o += e ? '<div class="jm-eqd"><b>' + esc(e.name) + "</b><br>" + esc(e.bonus_text) + "</div>" : '<div class="jm-empty">Empty.</div>';
      o += '<div class="jm-empty">Enter to change.</div>';
    }
    o += '</div></div><div class="jm-col"><div class="jm-ptitle">Stats</div>';
    STATS.forEach(function (s) {
      var v = h.stats[s[0]], dv = d[s[0]];
      o += '<div class="jm-stat"><b>' + s[1] + "</b><span>" + v + "</span>" + (dv ? '<i class="' + (dv > 0 ? "up" : "dn") + '">' + (v + dv) + " (" + (dv > 0 ? "+" : "") + dv + ")</i>" : "") + "</div>";
    });
    return o + "</div></div></div>";
  }
  function statusHtml() {
    var h = hero(ci), next = h.xp_next == null ? "MAX" : Math.max(0, h.xp_next - h.xp);
    var o = '<div class="jm-panel jm-detail"><div class="jm-dhead"><img src="' + esc(h.portrait) + '" onerror="this.style.display=\'none\'" alt=""><div><div class="jm-cls">' + esc(h.class_name) + '</div><div class="jm-nm">' + esc(h.name) + ' <small>LV ' + h.level + '</small></div><div class="jm-nx">Next level <b>' + next + '</b>' + (next === "MAX" ? "" : " XP") + '</div></div><div class="jm-hint">&larr; &rarr; / Q: switch hero</div></div><div class="jm-cols">';
    o += '<div class="jm-col"><div class="jm-ptitle">Stats</div>' + bar("hp", "HP", h.hp, h.stats.max_hp) + bar("mp", "MP", h.mp, h.stats.max_mp);
    STATS.slice(2).forEach(function (s) { o += '<div class="jm-stat"><b>' + s[1] + "</b><span>" + h.stats[s[0]] + "</span></div>"; });
    o += '</div><div class="jm-col"><div class="jm-ptitle">Equipment</div>';
    st.slots.forEach(function (s) { var e = h.equipped[s]; o += '<div class="jm-stat"><b>' + SLOT_LABEL[s] + "</b><span>" + (e ? esc(e.name) : "&mdash;") + "</span></div>"; });
    o += '</div><div class="jm-col"><div class="jm-ptitle">Skills</div><div class="jm-scroll">';
    (h.skills || []).forEach(function (s) { o += '<div class="jm-skill"><b>' + esc(s.name) + "</b> <em>" + s.mp_cost + " MP &middot; rank " + s.rank + "</em><br><small>" + esc(s.description || "") + "</small></div>"; });
    return o + "</div></div></div></div>";
  }
  function bestiaryHtml() {
    if (!bst) return '<div class="jm-panel jm-center"><div class="jm-big">Loading&hellip;</div></div>';
    var es = bst.entries || [], e = es[bz] || {}, list = "";
    es.forEach(function (x, i) {
      list += '<div class="jm-row' + (i === bz ? " cur" : "") + (x.seen ? "" : " dim") + '" data-a="bz" data-i="' + i + '"><span>' + (x.seen ? esc(x.name) : "???") + "</span><em>" + (x.defeated ? "&times;" + x.defeated : x.seen ? "seen" : "") + "</em></div>";
    });
    var d = '<div class="jm-bhead"><div class="jm-nm">' + (e.seen ? esc(e.name) : "???") + (e.kind === "boss" ? ' <small>BOSS</small>' : "") + '</div><div class="jm-cls">Seen ' + (e.seen || 0) + " &middot; Defeated " + (e.defeated || 0) + "</div></div>";
    d += '<div class="jm-bbody"><div class="jm-bart">' + (e.art ? '<img src="' + esc(e.art) + '" class="' + (e.seen ? "" : "sil") + '" alt="">' : '<div class="jm-empty">No art yet</div>') + "</div>";
    if (!e.seen) d += '<div class="jm-binfo"><div class="jm-empty">You have not met this foe yet.</div></div>';
    else if (!e.defeated) d += '<div class="jm-binfo"><div class="jm-empty">Defeat it in battle to learn its stats, skills and weaknesses.</div></div>';
    else {
      d += '<div class="jm-binfo">';
      var st2 = e.stats || {}; Object.keys(st2).forEach(function (k) { d += '<div class="jm-stat"><b>' + k + "</b><span>" + st2[k] + "</span></div>"; });
      d += '<div class="jm-skill"><b>Skills</b><br><small>' + esc((e.skills || []).join(", ") || "&mdash;") + "</small></div>";
      d += '<div class="jm-skill"><b>Weak to</b> <em>' + esc((e.weak || []).join(", ") || "&mdash;") + "</em> &middot; <b>Resists</b> <em>" + esc((e.resists || []).join(", ") || "&mdash;") + "</em></div>";
      d += '<div class="jm-skill"><b>Habits</b><br><small>' + esc(e.habits || "") + "</small></div></div>";
    }
    d += "</div>";
    return '<div class="jm-panel jm-bestiary"><div class="jm-ptitle">Seen ' + bst.seen + " / " + bst.total + " &middot; Defeated " + bst.defeated + '</div><div class="jm-bgrid"><div class="jm-scroll jm-blist">' + list + '</div><div class="jm-bdetail">' + d + "</div></div></div>";
  }
  /* ---------- quest log ---------- */
  var QF = ["All", "Main", "Side"];
  function questList() {
    var all = (window.Hub3D && Hub3D.quests) ? Hub3D.quests() : [], want = qf === 1 ? "main" : qf === 2 ? "side" : "";
    var f = all.filter(function (q) { return !want || q.kind === want; });
    var rank = function (q) { return (q.status === "done" ? 2 : 0) + (q.kind === "main" ? 0 : 1); };
    return f.map(function (q, i) { return { q: q, i: i }; }).sort(function (a, b) { return rank(a.q) - rank(b.q) || a.i - b.i; }).map(function (x) { return x.q; });
  }
  function questHtml() {
    qv = questList(); if (qz >= qv.length) qz = Math.max(0, qv.length - 1);
    var tabs = '<div class="jm-qtabs">' + QF.map(function (t, i) { return '<span class="' + (i === qf ? "on" : "") + '" data-a="qf" data-i="' + i + '">' + t + "</span>"; }).join("") + "</div>";
    var list = "";
    qv.forEach(function (q, i) {
      var mark = q.status === "done" ? "&#10003;" : q.tracked ? "&#9670;" : "&#9671;";
      list += '<div class="jm-row' + (i === qz ? " cur" : "") + (q.status === "done" ? " dim" : "") + '" data-a="qz" data-i="' + i + '"><span><b class="jm-qk ' + q.kind + '">' + (q.kind === "main" ? "M" : "S") + "</b> " + mark + " " + esc(q.title) + "</span><em>" + (q.status === "ready" ? "return" : q.status === "done" ? "done" : "") + "</em></div>";
    });
    if (!qv.length) list = '<div class="jm-empty">' + (qf ? "No quests of this kind yet." : "No quests yet. Talk to people with a ! over their heads.") + "</div>";
    var q = qv[qz], d = "";
    if (q) {
      d += '<div class="jm-bhead"><div class="jm-nm">' + esc(q.title) + ' <small class="jm-qk ' + q.kind + '">' + (q.kind === "main" ? "MAIN QUEST" : "SIDE QUEST") + "</small></div><div class=\"jm-cls\">" +
        (q.status === "done" ? "Completed" : q.status === "ready" ? "Objective complete &mdash; return to " + esc(q.giver || "the quest giver") : "In progress") + "</div></div>";
      d += '<div class="jm-binfo">';
      if (q.giver || q.where) d += '<div class="jm-stat"><b>From</b><span>' + esc(q.giver || "&mdash;") + "</span></div><div class=\"jm-stat\"><b>Where</b><span>" + esc(q.where || "&mdash;") + "</span></div>";
      if (q.status !== "done") d += '<div class="jm-skill"><b>Objective</b><br><small>' + esc(q.text) + (q.count ? " (" + q.count[0] + "/" + q.count[1] + ")" : "") + "</small></div>";
      d += '<div class="jm-skill"><b>Story</b><br><small>' + esc(q.summary) + "</small></div>";
      if (q.status !== "done") d += '<div class="jm-row jm-qtrack' + (q.tracked ? " on" : "") + '" data-a="qtrack">' + (q.tracked ? "&#9670; Tracked &mdash; Enter to stop tracking" : "&#9671; Not tracked &mdash; Enter to track") + "</div>";
      d += "</div>";
    } else d = '<div class="jm-empty">Quests you accept appear here. Tracked quests are listed on the screen while you explore.</div>';
    var leg = (window.Hub3D && Hub3D.markLegend) ? Hub3D.markLegend() : [];
    var lg = '<div class="jm-legend">' + leg.map(function (l) { return '<span><i style="background:' + l.bg + ";color:" + l.fg + '">' + l.glyph + "</i>" + esc(l.label) + "</span>"; }).join("") + "</div>";
    return '<div class="jm-panel jm-bestiary"><div class="jm-ptitle">Quest log</div>' + tabs + '<div class="jm-bgrid"><div class="jm-scroll jm-blist">' + list + '</div><div class="jm-bdetail">' + d + "</div></div>" + lg + "</div>";
  }
  function saveHtml() {
    return '<div class="jm-panel jm-center"><div class="jm-big">Save your progress?</div><div class="jm-yn"><div class="jm-row' + (yes === 0 ? " cur" : "") + '" data-a="yn" data-i="0">Yes</div><div class="jm-row' + (yes === 1 ? " cur" : "") + '" data-a="yn" data-i="1">No</div></div></div>';
  }
  function settingsHtml() {
    function row(i, name, val) { return '<div class="jm-row' + (i === sr ? " cur" : "") + '" data-a="set" data-i="' + i + '"><b>' + name + '</b><span class="jm-slide">' + val + "</span></div>"; }
    function sl(v) { var n = Math.round(v * 10), s = ""; for (var i = 0; i < 10; i++) s += '<u class="' + (i < n ? "on" : "") + '"></u>'; return '<i data-a="dec">&#9664;</i>' + s + '<i data-a="inc">&#9654;</i>'; }
    return '<div class="jm-panel jm-center wide"><div class="jm-ptitle">Settings</div>' + row(0, "Music volume", sl(settings.music / 0.7)) + row(1, "Sound effects", sl(settings.sfx)) + row(2, "Control hints", '<i data-a="tog">' + (settings.hints ? "On" : "Off") + "</i>") + '<div class="jm-empty">&uarr;&darr; choose &middot; &larr;&rarr; change</div></div>';
  }
  function render() {
    if (!root || !st) return;
    var left, right;
    if (mode === "items" && (ph === "list" || ph === "target")) left = itemListHtml();
    else if (mode === "magic" && (ph === "skills" || ph === "target")) left = skillListHtml();
    else left = cmdListHtml();
    if (mode === "equip" && ph !== "hero") right = equipHtml();
    else if (mode === "status" && ph === "view") right = statusHtml();
    else if (mode === "bestiary") right = bestiaryHtml();
    else if (mode === "quests") right = questHtml();
    else if (mode === "save") right = saveHtml();
    else if (mode === "settings") right = settingsHtml();
    else right = cardsHtml();
    var hint = { main: "Choose a command", items: ph === "target" ? "Use on whom?" : "Pick an item", magic: ph === "caster" ? "Whose abilities?" : ph === "skills" ? "Healing spells can be cast here" : "Cast on whom?", equip: ph === "hero" ? "Choose a hero" : ph === "slot" ? "Choose a slot" : "Choose gear", status: "Choose a hero", quests: "Enter: track / untrack  \u00b7  \u2190 \u2192: filter", save: "", settings: "" }[mode] || "";
    root.innerHTML = '<div class="jm-wrap"><div class="jm-head"><div class="jm-title">' + TITLES[mode] + '</div><div class="jm-sub">' + (msg ? '<span class="' + (msgBad ? "bad" : "good") + '">' + esc(msg) + "</span>" : esc(hint)) +
      '</div><div class="jm-back" data-a="back">Esc &middot; ' + (mode === "main" ? "Close" : "Back") + '</div></div><div class="jm-left">' + left + infoHtml() + '</div><div class="jm-right">' + right + "</div></div>";
    var cur = root.querySelector(".jm-list .cur, .jm-col .cur"); if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
  }

  /* ---------- actions ---------- */
  function go(m, p) { mode = m; ph = p; msg = ""; }
  function afterAction(r, sound) {
    if (r && r.state) st = r.state;
    say(r && r.message, !(r && r.ok)); sfx(r && r.ok ? (sound || "confirm") : "denied"); render();
  }
  function confirm() {
    if (busy) return;
    var h, c;
    if (mode === "main") {
      var n = CMDS[cmd]; msg = "";
      if (n === "Close") return M.close();
      if (n === "Items") { li = 0; go("items", "list"); }
      else if (n === "Magic") { ci = 0; go("magic", "caster"); }
      else if (n === "Equip") { ci = 0; si = 0; go("equip", "hero"); }
      else if (n === "Status") { ci = 0; go("status", "hero"); }
      else if (n === "Quests") { qz = 0; go("quests", "view"); }
      else if (n === "Bestiary") { bz = 0; bst = null; go("bestiary", "view"); fetch("/api/bestiary").then(function (r) { return r.json(); }).then(function (b) { bst = b; render(); }).catch(function () { say("The server could not be reached.", true); render(); }); }
      else if (n === "Save") { yes = 0; go("save", "confirm"); }
      else if (n === "Settings") { sr = 0; go("settings", "rows"); }
      if (!party().length && (n === "Magic" || n === "Equip" || n === "Status")) { go("main", "cmd"); say("No one is in your party.", true); }
      sfx("confirm"); return render();
    }
    if (mode === "items") {
      if (ph === "list") {
        var it = st.inventory[li]; if (!it) { sfx("denied"); return; }
        if (!usable(it)) { say("That can only be used in battle.", true); sfx("denied"); return render(); }
        ph = "target"; ci = Math.max(0, Math.min(ci, party().length - 1)); msg = ""; sfx("confirm"); return render();
      }
      h = hero(ci); if (!h) return; busy = true;
      return post("/api/menu/use_item", { item_id: st.inventory[li].id, character_id: h.id }).then(function (r) {
        busy = false; afterAction(r, "confirm");
        if (st.inventory.length === 0) { ph = "list"; li = 0; render(); }
        else if (li >= st.inventory.length) { li = st.inventory.length - 1; render(); }
      }, fail);
    }
    if (mode === "magic") {
      if (ph === "caster") {
        h = hero(ci); if (!h) return;
        if (!allSkills(h).length) { say(h.name + " has no abilities.", true); sfx("denied"); return render(); }
        cas = ci; li = 0; ph = "skills"; msg = ""; sfx("confirm"); return render();
      }
      var h0 = hero(cas), sk = allSkills(h0)[li];
      if (ph === "skills") {
        if (!sk) return;
        if (!castable(sk)) { say(sk.name + " can only be used in battle.", true); sfx("denied"); return render(); }
        if (h0.mp < sk.mp_cost) { say("Not enough MP.", true); sfx("denied"); return render(); }
        if (sk.target === "single_ally") { ph = "target"; ci = cas; msg = ""; sfx("confirm"); return render(); }
        busy = true; return post("/api/menu/cast", { caster_id: h0.id, skill_id: sk.id }).then(function (r) { busy = false; afterAction(r, "confirm"); }, fail);
      }
      if (ph === "target") { busy = true; var tg = hero(ci); return post("/api/menu/cast", { caster_id: h0.id, skill_id: sk.id, target_id: tg && tg.id }).then(function (r) { busy = false; afterAction(r, "confirm"); }, fail); }
    }
    if (mode === "equip") {
      if (ph === "hero") { si = 0; ph = "slot"; sfx("confirm"); return render(); }
      if (ph === "slot") { pi = 0; ph = "pick"; sfx("confirm"); return render(); }
      if (ph === "pick") {
        h = hero(ci); c = candidates()[pi]; if (!c) return;
        if (!c.unequip && !c.ok) { say(h.name + " can't use that.", true); sfx("denied"); return render(); }
        busy = true;
        var req = c.unequip ? post("/api/heroes/unequip", { character_id: h.id, slot: st.slots[si] }) : post("/api/heroes/equip", { character_id: h.id, instance_id: c.instance_id });
        return req.then(function (r) { return refresh().then(function () { busy = false; ph = "slot"; say(r.message, !r.ok); sfx(r.ok ? "confirm" : "denied"); render(); }); }, fail);
      }
    }
    if (mode === "status" && ph === "hero") { ph = "view"; sfx("confirm"); return render(); }
    if (mode === "quests") {
      var cq = qv[qz]; if (!cq || cq.status === "done") { sfx("denied"); return; }
      if (window.Hub3D && Hub3D.setTracked) Hub3D.setTracked(cq.id, !cq.tracked);
      sfx("confirm"); return render();
    }
    if (mode === "save") {
      if (yes === 1) return back();
      busy = true; return post("/api/menu/save").then(function (r) { busy = false; go("main", "cmd"); afterAction(r, "confirm"); }, fail);
    }
    if (mode === "settings") { if (sr === 2) adjust(1); }
  }
  function fail() { busy = false; say("The server could not be reached.", true); render(); }
  function back() {
    if (busy) return;
    msg = "";
    if (mode === "main") return M.close();
    if (mode === "items" && ph === "target") ph = "list";
    else if (mode === "magic" && ph === "target") ph = "skills";
    else if (mode === "magic" && ph === "skills") { ph = "caster"; ci = cas; }
    else if (mode === "equip" && ph === "pick") ph = "slot";
    else if (mode === "equip" && ph === "slot") ph = "hero";
    else if (mode === "status" && ph === "view") ph = "hero";
    else go("main", "cmd");
    sfx("decline"); render();
  }
  function adjust(dir) {
    if (sr === 0) settings.music = Math.max(0, Math.min(0.7, Math.round((settings.music / 0.7 + dir * 0.1) * 10) / 10 * 0.7));
    else if (sr === 1) settings.sfx = Math.max(0, Math.min(1, Math.round((settings.sfx + dir * 0.1) * 10) / 10));
    else if (sr === 2) settings.hints = !settings.hints;
    applySettings(); sfx("hover"); render();
  }
  function move(dx, dy) {
    var n = party().length, ctx = mode + "/" + ph;
    function wrap(v, len) { return len ? (v + len) % len : 0; }
    if (ctx === "main/cmd") cmd = wrap(cmd + dy + dx, CMDS.length);
    else if (ctx === "items/list") li = wrap(li + dy, st.inventory.length);
    else if (ctx === "magic/skills") li = wrap(li + dy, allSkills(hero(cas)).length);
    else if (cardsActive()) ci = wrap(ci + dx + (mode === "equip" || mode === "status" ? dy : 0), n);
    else if (ctx === "equip/slot") { if (dy) si = wrap(si + dy, st.slots.length); else if (dx) ci = wrap(ci + dx, n); }
    else if (ctx === "equip/pick") pi = wrap(pi + dy, candidates().length);
    else if (ctx === "status/view") ci = wrap(ci + dx, n);
    else if (ctx === "quests/view") { if (dy) qz = wrap(qz + dy, qv.length); else if (dx) { qf = wrap(qf + dx, QF.length); qz = 0; } }
    else if (ctx === "bestiary/view") { if (!bst) return; bz = wrap(bz + dy + dx * 6, bst.entries.length); }
    else if (ctx === "save/confirm") yes = wrap(yes + dx + dy, 2);
    else if (ctx === "settings/rows") { if (dy) sr = wrap(sr + dy, 3); else if (dx) return adjust(dx); }
    else return;
    msg = ""; sfx("hover"); render();
  }
  function cycleHero() { var n = party().length; if (n < 2 || !(mode === "equip" && ph !== "hero" || mode === "status" && ph === "view")) return; ci = (ci + 1) % n; render(); sfx("hover"); }

  /* ---------- input ---------- */
  function onKey(e) {
    if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (!isOpen) {
      if (e.key === "Escape" && !e.repeat && window.Hub3D && Hub3D.on && Hub3D.canOpenMenu && Hub3D.canOpenMenu()) { e.preventDefault(); M.open(); }
      return;
    }
    var k = e.key.toLowerCase();
    e.stopPropagation(); e.preventDefault();
    if (k === "escape" || k === "backspace") { if (!e.repeat) back(); }
    else if (k === "arrowup" || k === "w") move(0, -1);
    else if (k === "arrowdown" || k === "s") move(0, 1);
    else if (k === "arrowleft" || k === "a") move(-1, 0);
    else if (k === "arrowright" || k === "d") move(1, 0);
    else if (k === "enter" || k === "e" || k === " ") { if (!e.repeat) confirm(); }
    else if (k === "q" || k === "tab") cycleHero();
  }
  function onClick(e) {
    var t = e.target.closest("[data-a]"); if (!t || !isOpen) return;
    var a = t.getAttribute("data-a"), i = parseInt(t.getAttribute("data-i"), 10);
    if (a === "back") return back();
    if (a === "cmd") { if (ph !== "cmd") { go("main", "cmd"); } cmd = i; return confirm(); }
    if (a === "card") { if (!cardsActive()) return; ci = i; return confirm(); }
    if (a === "li") { li = i; return confirm(); }
    if (a === "bz") { bz = i; sfx("hover"); return render(); }
    if (a === "qz") { qz = i; sfx("hover"); return render(); }
    if (a === "qf") { qf = i; qz = 0; sfx("hover"); return render(); }
    if (a === "qtrack") return confirm();
    if (a === "slot") { if (ph === "pick") ph = "slot"; si = i; ph = "slot"; return confirm(); }
    if (a === "pick") { pi = i; return confirm(); }
    if (a === "yn") { yes = i; return confirm(); }
    if (a === "set") { sr = i; var d = e.target.getAttribute("data-a"); if (d === "dec") return adjust(-1); if (d === "inc") return adjust(1); if (d === "tog") return adjust(1); render(); return; }
    if (a === "dec" || a === "inc" || a === "tog") { var row = t.closest("[data-i]"); sr = row ? parseInt(row.getAttribute("data-i"), 10) : sr; return adjust(a === "dec" ? -1 : 1); }
  }

  /* ---------- open / close ---------- */
  M.isOpen = function () { return isOpen; };
  M.open = function () {
    if (isOpen) return; build();
    fetch("/api/menu/state").then(function (r) { return r.json(); }).then(function (s) {
      st = s; mode = "main"; ph = "cmd"; cmd = 0; ci = 0; msg = ""; isOpen = true; root.style.display = "block"; sfx("confirm"); render();
    }).catch(function () { });
  };
  M.close = function () { if (!isOpen) return; isOpen = false; root.style.display = "none"; sfx("decline"); if (window.Hub3D && Hub3D.refreshState) Hub3D.refreshState(); };
  M.init = function (o) { O = o || {}; applySettings(); };

  function build() {
    if (root) return;
    var css = document.createElement("style");
    css.textContent = [
      "#jm{position:fixed;inset:0;z-index:60;display:none;background:radial-gradient(ellipse at 50% 30%,rgba(18,70,92,.93),rgba(4,18,30,.97));font-family:'Segoe UI',system-ui,sans-serif;color:#f3efd8;user-select:none}",
      "#jm *{box-sizing:border-box}",
      ".jm-wrap{position:absolute;inset:3vh 2.5vw;display:grid;grid-template-columns:clamp(210px,23vw,300px) 1fr;grid-template-rows:auto 1fr;gap:12px}",
      ".jm-head{grid-column:1/3;display:flex;align-items:center;gap:18px;padding:8px 18px;border:2px solid #e8c766;border-radius:10px;background:linear-gradient(180deg,#14607a,#0b3a4f);box-shadow:0 0 0 2px #072433,inset 0 0 14px rgba(0,0,0,.35)}",
      ".jm-title{font-size:clamp(18px,2.4vh,26px);font-weight:700;letter-spacing:.04em;color:#ffe9a0;text-shadow:0 2px 0 #052030}",
      ".jm-sub{flex:1;font-size:15px;opacity:.9}.jm-sub .good{color:#a8f0b0}.jm-sub .bad{color:#ffa89a}",
      ".jm-back{font-size:13px;color:#e8c766;cursor:pointer;padding:4px 10px;border:1px solid #e8c76688;border-radius:6px}.jm-back:hover{background:#e8c76622}",
      ".jm-left{display:flex;flex-direction:column;gap:12px;min-height:0}.jm-right{min-height:0;min-width:0;display:flex}",
      ".jm-panel{border:2px solid #e8c766;border-radius:10px;background:linear-gradient(180deg,#125a73,#0a3347);box-shadow:0 0 0 2px #072433,inset 0 0 14px rgba(0,0,0,.35);padding:10px}",
      ".jm-cmds{padding:12px 8px}.jm-cmds .jm-row{justify-content:flex-start}.jm-list{flex:1;min-height:0;display:flex;flex-direction:column}",
      ".jm-ptitle{font-size:14px;font-weight:700;color:#e8c766;letter-spacing:.06em;text-transform:uppercase;margin:0 4px 6px}",
      ".jm-scroll{flex:1;min-height:0;overflow:auto}",
      ".jm-row{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 12px;margin:2px 0;border-radius:6px;font-size:clamp(15px,2.1vh,19px);cursor:pointer;border:1px solid transparent}",
      ".jm-row b{font-weight:600;color:#bfe3ee}.jm-row em{font-style:normal;font-size:.8em;opacity:.8}",
      ".jm-row:hover{background:rgba(232,199,102,.12)}.jm-row.cur{background:linear-gradient(90deg,rgba(255,226,140,.38),rgba(255,226,140,.06));border-color:#e8c766;color:#fff}",
      ".jm-row.cur::before{content:'\\25B6';color:#ffe9a0;margin-right:6px;font-size:.7em}.jm-row.off.cur{opacity:.6}.jm-row.dim{opacity:.45}",
      ".jm-desc{margin-top:8px;padding:8px;font-size:13px;color:#cfe8f0;border-top:1px solid #e8c76655;min-height:3.2em}",
      ".jm-empty{padding:8px;font-size:13px;opacity:.7}",
      ".jm-info{margin-top:auto;display:grid;gap:4px;padding:10px 14px}.jm-info div{display:flex;justify-content:space-between;font-size:14px}.jm-info b{color:#e8c766}",
      ".jm-cards{flex:1;display:grid;grid-template-columns:repeat(4,1fr);gap:10px;min-width:0}",
      ".jm-card{position:relative;overflow:hidden;border:2px solid #e8c766;border-radius:10px;background:#0a2a3a;box-shadow:0 0 0 2px #072433;min-width:0}",
      ".jm-card.empty{display:flex;align-items:center;justify-content:center;opacity:.35;font-size:15px}",
      ".jm-card img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 12%}",
      ".jm-card.pick{cursor:pointer}.jm-card.pick:not(.sel){filter:brightness(.7)}",
      ".jm-card.sel{border-color:#fff3b0;box-shadow:0 0 0 2px #072433,0 0 18px 4px rgba(255,230,140,.75)}.jm-card.ko img{filter:grayscale(1)}",
      ".jm-cinfo{position:absolute;left:0;right:0;bottom:0;padding:34px 10px 10px;background:linear-gradient(180deg,transparent,rgba(3,22,34,.92) 34%)}",
      ".jm-cls{font-size:12px;color:#e8c766;letter-spacing:.05em}.jm-nm{font-size:clamp(17px,2.4vh,24px);font-weight:700;text-shadow:0 2px 3px #000}.jm-nm small{font-size:.6em;color:#bfe3ee}",
      ".jm-lv{font-size:14px}.jm-lv b{color:#e8c766}.jm-nx{font-size:12px;opacity:.85;margin-bottom:4px}.jm-nx b{color:#ffe9a0}",
      ".jm-bar{display:flex;align-items:center;gap:6px;font-size:12px;margin-top:3px}.jm-bar b{width:22px;color:#e8c766}.jm-bar em{font-style:normal;min-width:62px;text-align:right}",
      ".jm-track{flex:1;height:9px;border-radius:5px;background:#03131c;border:1px solid #e8c76688;overflow:hidden}.jm-track i{display:block;height:100%}",
      ".jm-bar.hp i{background:linear-gradient(180deg,#9df08a,#3da842)}.jm-bar.mp i{background:linear-gradient(180deg,#8fd4ff,#2a79c8)}",
      ".jm-detail{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0}",
      ".jm-dhead{display:flex;align-items:center;gap:14px;padding-bottom:8px;border-bottom:1px solid #e8c76655}.jm-dhead img{width:64px;height:64px;border-radius:8px;object-fit:cover;object-position:50% 10%;border:2px solid #e8c766}.jm-hint{margin-left:auto;font-size:12px;opacity:.7}",
      ".jm-cols{flex:1;min-height:0;display:grid;grid-template-columns:1.1fr 1.2fr 1fr;gap:12px;padding-top:10px}.jm-col{min-width:0;min-height:0;display:flex;flex-direction:column}",
      ".jm-col .jm-row{font-size:clamp(13px,1.8vh,16px);padding:6px 8px}.jm-col .jm-row span{text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
      ".jm-stat{display:flex;gap:10px;padding:5px 8px;font-size:clamp(13px,1.8vh,16px);border-bottom:1px solid rgba(232,199,102,.18)}.jm-stat b{width:78px;color:#bfe3ee;font-weight:600}.jm-stat span{font-weight:700}.jm-stat i{font-style:normal;margin-left:auto;font-weight:700}.jm-stat i.up{color:#9df08a}.jm-stat i.dn{color:#ff9a8a}",
      ".jm-eqd{padding:8px;font-size:14px;line-height:1.5}.jm-skill{padding:5px 6px;border-bottom:1px solid rgba(232,199,102,.18);font-size:14px}.jm-skill em{font-style:normal;font-size:12px;opacity:.75}.jm-skill small{opacity:.8}",
      ".jm-center{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px}.jm-center.wide{align-items:stretch;padding:20px 8%}.jm-big{font-size:26px;font-weight:700;color:#ffe9a0}",
      ".jm-qtabs{display:flex;gap:8px;margin:0 0 8px}.jm-qtabs span{cursor:pointer;padding:2px 12px;border:1px solid rgba(232,199,102,.3);border-radius:999px;font-size:13px;opacity:.7}.jm-qtabs span.on{opacity:1;border-color:#e8c766;color:#e8c766}",
      ".jm-qk{display:inline-block;font-style:normal;font-size:11px;font-weight:800;padding:0 5px;border-radius:4px}.jm-qk.main{background:#ffd23f;color:#2a1d00}.jm-qk.side{background:#4fb3ff;color:#04223a}",
      ".jm-qtrack{margin-top:10px;text-align:center}.jm-qtrack.on{border-color:#e8c766}",
      ".jm-legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px;font-size:11px;opacity:.85}.jm-legend span{display:inline-flex;align-items:center;gap:5px}.jm-legend i{display:inline-block;min-width:15px;height:15px;line-height:15px;text-align:center;border-radius:50%;font-style:normal;font-size:10px;font-weight:900}",
      ".jm-bestiary{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0}.jm-bgrid{flex:1;min-height:0;display:grid;grid-template-columns:minmax(150px,.8fr) 2.2fr;gap:12px}",
      ".jm-blist{border-right:1px solid #e8c76655;padding-right:6px}.jm-bdetail{min-width:0;min-height:0;display:flex;flex-direction:column}.jm-bhead{padding:2px 6px 8px;border-bottom:1px solid #e8c76655}",
      ".jm-bbody{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;gap:12px;padding-top:8px}.jm-bart{display:flex;align-items:flex-end;justify-content:center;min-height:0;border-radius:8px;background:radial-gradient(ellipse at 50% 80%,rgba(255,230,140,.16),rgba(0,0,0,.25))}",
      ".jm-bart img{max-width:100%;max-height:100%;object-fit:contain}.jm-bart img.sil{filter:brightness(0) opacity(.55)}.jm-binfo{min-width:0;min-height:0;overflow:auto}",
      ".jm-yn{display:flex;gap:16px}.jm-yn .jm-row{min-width:120px;justify-content:center;font-size:20px}",
      ".jm-slide{display:flex;align-items:center;gap:4px}.jm-slide u{display:inline-block;width:14px;height:16px;border:1px solid #e8c76688;border-radius:3px;background:#03131c}.jm-slide u.on{background:linear-gradient(180deg,#ffe9a0,#d8a63a)}.jm-slide i{font-style:normal;cursor:pointer;color:#e8c766;padding:0 6px}",
      "@media(max-width:820px){.jm-bgrid,.jm-bbody{grid-template-columns:1fr}.jm-wrap{grid-template-columns:1fr;grid-template-rows:auto auto 1fr;inset:1vh 1vw}.jm-head{grid-column:1}.jm-left{flex-direction:row}.jm-cols{grid-template-columns:1fr}.jm-cards{grid-template-columns:repeat(2,1fr)}}"
    ].join("\n");
    document.head.appendChild(css);
    root = document.createElement("div"); root.id = "jm"; document.body.appendChild(root);
    root.addEventListener("click", onClick);
    root.addEventListener("contextmenu", function (e) { e.preventDefault(); back(); });
    root.addEventListener("wheel", function (e) { e.stopPropagation(); }, { passive: true });
  }
  window.addEventListener("keydown", onKey, true);
  applySettings();
})();
