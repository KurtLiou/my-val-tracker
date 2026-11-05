/* VAL 小戰績 前端 */
"use strict";

const VAPI = "https://valorant-api.com/v1";
const A = { agents: {}, agentsEn: {}, maps: {}, tiers: {}, weapons: {}, loaded: false };
const S = { status: null, stats: null, queue: "all", liveTimer: null, lineup: { agent: null, map: null }, evId: 0, pack: null };
// valorant-api.com 還沒收錄的新特務（ID 從你的對局資料找到的）
const EXTRA_AGENTS = { "ddd5a15c-4fbe-42fa-3789-11a55ca5ee04": { name: "靜", en: "Hush" } };
const QUEUES = { all: "全部", competitive: "競技", unrated: "一般", deathmatch: "死鬥", swiftplay: "快速對戰",
  hurm: "團隊死鬥", premier: "Premier", spikerush: "Spike Rush", ggteam: "Escalation", newmap: "新地圖", custom: "自訂", "": "自訂" };
// lineup 常用特務（英文名，對應 valorant-api）
const LINEUP_AGENTS = ["Sova", "Viper", "Brimstone", "KAY/O", "Killjoy", "Cypher", "Gekko", "Fade", "Breach", "Raze", "Deadlock", "Harbor", "Astra", "Tejo", "Vyse", "Hush"];
const BADGE_EMOJI = { ace: "🌟", clutch: "👑", headhunter: "🎯", mvp: "🏆", entry: "🚪", planter: "💣", defuser: "🧯", wall: "🛡️", streak: "🚂", grinder: "🔥" };

/* ---------------- 原創吉祥物：啾啾（漂浮小機器人） ---------------- */
function mascot(cls = "", mood = "happy") {
  const mouth = mood === "sad"
    ? `<path d="M42 66 q8 -6 16 0" stroke="#1b2036" stroke-width="3" fill="none" stroke-linecap="round"/>`
    : mood === "wow"
      ? `<ellipse cx="50" cy="66" rx="5" ry="6" fill="#1b2036"/>`
      : `<path d="M41 62 q9 9 18 0" stroke="#1b2036" stroke-width="3" fill="none" stroke-linecap="round"/>`;
  return `<svg class="mascot ${cls}" viewBox="0 0 100 100" aria-label="吉祥物啾啾" role="img">
    <defs><linearGradient id="mg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#dfe3ff"/></linearGradient></defs>
    <ellipse cx="50" cy="94" rx="20" ry="3.5" fill="#000" opacity=".25"/>
    <line x1="50" y1="22" x2="50" y2="10" stroke="#c7cdf5" stroke-width="3" stroke-linecap="round"/>
    <path d="M50 2 l2.6 5.3 5.8.8 -4.2 4.1 1 5.8 -5.2-2.7 -5.2 2.7 1-5.8 -4.2-4.1 5.8-.8z" fill="#ffd166"/>
    <ellipse cx="14" cy="56" rx="7" ry="11" fill="#ff4f64"/><ellipse cx="86" cy="56" rx="7" ry="11" fill="#ff4f64"/>
    <rect x="16" y="20" width="68" height="66" rx="32" fill="url(#mg)"/>
    <rect x="25" y="34" width="50" height="38" rx="18" fill="#2a2f55"/>
    <g class="eye"><ellipse cx="39" cy="50" rx="5" ry="6.5" fill="#4fe3b5"/><circle cx="41" cy="47.5" r="1.8" fill="#fff"/></g>
    <g class="eye"><ellipse cx="61" cy="50" rx="5" ry="6.5" fill="#4fe3b5"/><circle cx="63" cy="47.5" r="1.8" fill="#fff"/></g>
    <rect x="25" y="34" width="50" height="38" rx="18" fill="none" stroke="#a98bff" stroke-width="2" opacity=".6"/>
    <g transform="translate(0,-2)">${mouth.replace(/#1b2036/g, "#c7cdf5")}</g>
    <ellipse cx="30" cy="62" rx="4" ry="2.5" fill="#ff9f80" opacity=".8"/><ellipse cx="70" cy="62" rx="4" ry="2.5" fill="#ff9f80" opacity=".8"/>
    <path d="M38 86 q12 8 24 0" fill="#c7cdf5"/>
  </svg>`;
}

/* ---------------- 小工具 ---------------- */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, suf = "", nd) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : `${nd !== undefined ? Number(v).toFixed(nd) : v}${suf}`;
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const qName = (q) => QUEUES[q] ?? q;
const agentName = (id) => A.agents[id]?.name || (id ? "新特務" : "未知特務");
const mapInfo = (id) => A.maps[id] || A.maps[(id || "").toLowerCase()] || null;
const mapName = (id) => mapInfo(id)?.name || (id || "").split("/").pop() || "—";
const tierName = (t) => (t ? (A.tiers[t]?.name || `Tier ${t}`) : "未定階");

function timeAgo(ms) {
  if (!ms) return "—";
  const m = Math.max(0, Math.round((Date.now() - ms) / 60000));
  if (m < 1) return "剛剛";
  if (m < 60) return `${m} 分鐘前`;
  if (m < 1440) return `${Math.round(m / 60)} 小時前`;
  return `${Math.round(m / 1440)} 天前`;
}
function fallbackIcon(id) {
  // 沒有官方圖片的特務：畫一個可愛的佔位頭像（顏色由 ID 決定）
  let h = 0;
  for (const c of id || "?") h = (h * 31 + c.charCodeAt(0)) % 360;
  const n = A.agents[id]?.name || "?";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="hsl(${h},80%,65%)"/><stop offset="1" stop-color="hsl(${(h + 50) % 360},70%,45%)"/></linearGradient></defs>
    <rect width="64" height="64" rx="16" fill="url(#g)"/><circle cx="22" cy="27" r="3.5" fill="#fff"/><circle cx="42" cy="27" r="3.5" fill="#fff"/>
    <path d="M24 38 q8 7 16 0" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>
    <text x="32" y="58" font-size="12" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="700">${n.slice(0, 2)}</text></svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}
function agentIcon(id) { return A.agents[id]?.icon || (id ? fallbackIcon(id) : null); }
function agentImg(id, cls = "av") {
  const a = A.agents[id];
  const icon = agentIcon(id);
  if (icon) return `<img class="${cls}" src="${icon}" alt="${esc(a?.name || "")}" loading="lazy" crossorigin="anonymous">`;
  return `<div class="${cls} av-fb">?</div>`;
}
function tierImg(t, cls = "tierimg") {
  const x = A.tiers[t];
  return x?.icon ? `<img class="${cls}" src="${x.icon}" alt="">` : "";
}
function rankCell(t, extra = "") {
  if (!t) return `<span class="faint">未定階</span>`;
  return `<span class="rankcell">${tierImg(t)}${esc(tierName(t))}${extra}</span>`;
}
function weaponName(w) {
  if (!w) return "其他";
  if (A.weapons[w]) return A.weapons[w].name;
  const map = { ability1: "技能 Q", ability2: "技能 E", grenadeability: "技能 C", ultimate: "大招", bomb: "炸彈", melee: "近戰" };
  return map[w] || (w.includes("-") ? "未知武器" : w);
}
function toast(msg, ms = 2800) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
async function api(path, body) {
  const opt = body !== undefined
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const j = await r.json();
  if (j && j.error) throw new Error(j.error);
  return j;
}
function loading(msg = "載入中…") {
  return `<div class="loading">${mascot("small")}<span>${esc(msg)}</span></div>`;
}
function emptyBox(html, mood = "happy") {
  return `<div class="card empty">${mascot("", mood)}<div>${html}</div></div>`;
}

/* ---------------- 素材（特務、地圖、牌位、武器） ---------------- */
async function loadAssets() {
  const get = (p) => fetch(VAPI + p).then((r) => r.json()).then((j) => j.data || []).catch(() => []);
  const [ag, agEn, maps, tiers, weapons] = await Promise.all([
    get("/agents?isPlayableCharacter=true&language=zh-TW"),
    get("/agents?isPlayableCharacter=true&language=en-US"),
    get("/maps?language=zh-TW"), get("/competitivetiers?language=zh-TW"), get("/weapons?language=zh-TW"),
  ]);
  for (const a of ag) {
    A.agents[a.uuid.toLowerCase()] = { name: a.displayName, icon: a.displayIcon, portrait: a.fullPortrait,
      role: a.role?.displayName, color: a.backgroundGradientColors?.[0] };
  }
  for (const a of agEn) {
    const id = a.uuid.toLowerCase();
    A.agentsEn[id] = a.displayName;
    if (A.agents[id]) A.agents[id].en = a.displayName;
  }
  const mapsEn = await get("/maps?language=en-US");
  const en = Object.fromEntries(mapsEn.map((m) => [m.uuid, m.displayName]));
  for (const m of maps) {
    const info = { name: m.displayName, en: en[m.uuid] || m.displayName, splash: m.splash, list: m.listViewIcon, uuid: m.uuid, url: m.mapUrl,
      mini: m.displayIcon, xm: m.xMultiplier, ym: m.yMultiplier, xs: m.xScalarToAdd, ys: m.yScalarToAdd };
    A.maps[m.mapUrl] = info;
    A.maps[m.uuid] = info;
    A.maps[m.uuid.toLowerCase()] = info;
  }
  const latest = tiers[tiers.length - 1];
  for (const t of latest?.tiers || []) A.tiers[t.tier] = { name: t.tierName, icon: t.smallIcon || t.largeIcon, color: t.color };
  for (const w of weapons) A.weapons[w.uuid.toLowerCase()] = { name: w.displayName, icon: w.killStreamIcon || w.displayIcon };
  for (const [id, x] of Object.entries(EXTRA_AGENTS)) if (!A.agents[id]) A.agents[id] = { ...x, extra: true };
  // 你自己放的特務圖片（檔名用特務中文名、英文名或 ID 都可以，例如「靜.png」）
  try {
    const { files } = await api("/api/custom-agents");
    const key = (s) => (s || "").toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff-]/g, "");
    for (const f of files) {
      const base = key(f.replace(/\.[^.]+$/, ""));
      for (const [id, a] of Object.entries(A.agents)) {
        if ([id, key(a.en), key(a.name)].includes(base)) a.icon = "/custom/" + encodeURIComponent(f);
      }
    }
  } catch { /* ignore */ }
  A.loaded = ag.length > 0;
  try {
    const maps = {}, agents = {};
    for (const [k, m] of Object.entries(A.maps)) if (k.startsWith("/Game")) maps[k] = m.name;
    for (const [k, a] of Object.entries(A.agents)) agents[k] = a.name;
    api("/api/names", { maps, agents });
  } catch { /* ignore */ }
}

/* 遊戲座標 → 小地圖 0~1 座標（valorant-api 提供的換算參數） */
function toMini(mi, xy) {
  if (!mi || mi.xm === undefined || !xy || xy[0] == null) return null;
  const nx = xy[1] * mi.xm + mi.xs, ny = xy[0] * mi.ym + mi.ys;
  return nx >= -0.05 && nx <= 1.05 && ny >= -0.05 && ny <= 1.05 ? [nx, ny] : null;
}

/* ---------------- 小圖表（純 SVG） ---------------- */
function rrChart(hist) {
  if (!hist?.length) return `<div class="faint">還沒有 RR 紀錄，打幾場競技再同步看看。</div>`;
  const pts = hist.map((h) => h.tier * 100 + h.rr);
  const W = 640, H = 200, P = 28;
  const min = Math.min(...pts) - 20, max = Math.max(...pts) + 20;
  const x = (i) => P + (i * (W - P * 2)) / Math.max(1, pts.length - 1);
  const y = (v) => H - P - ((v - min) / (max - min || 1)) * (H - P * 2);
  const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(pts.length - 1)},${H - P} L${x(0)},${H - P} Z`;
  let grid = "";
  for (let t = Math.ceil(min / 100); t * 100 <= max; t++) {
    const yy = y(t * 100);
    grid += `<line x1="${P}" x2="${W - P}" y1="${yy}" y2="${yy}" stroke="#2b3554" stroke-dasharray="4 4"/>
      <text x="${W - P + 4}" y="${yy + 4}" fill="#6b7598" font-size="10">${esc(tierName(t))}</text>`;
  }
  const dots = hist.map((h, i) => `<circle cx="${x(i)}" cy="${y(pts[i])}" r="4" fill="${h.change >= 0 ? "#4fe3b5" : "#ff6b81"}" stroke="#1a2137" stroke-width="2">
      <title>${esc(tierName(h.tier))} ${h.rr} RR（${h.change >= 0 ? "+" : ""}${h.change}）${h.date ? " · " + new Date(h.date).toLocaleDateString("zh-TW") : ""}</title></circle>`).join("");
  return `<svg viewBox="0 0 ${W + 40} ${H}" style="width:100%;height:auto">
    <defs><linearGradient id="rra" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a98bff" stop-opacity=".35"/><stop offset="1" stop-color="#a98bff" stop-opacity="0"/></linearGradient></defs>
    ${grid}<path d="${area}" fill="url(#rra)"/><path d="${line}" fill="none" stroke="#a98bff" stroke-width="3" stroke-linejoin="round"/>${dots}</svg>`;
}

function radar(o, e) {
  const items = [
    ["K/D", o.kd, 1.0], ["爆頭率", o.hs, 20], ["ADR", o.adr, 140],
    ["KAST", o.kast, 70], ["首殺率", e.fk_per_round ? e.fk_per_round * 100 : null, 12], ["殘局勝率", e.clutch.rate, 15],
  ];
  const C = 120, R = 85, n = items.length;
  const pt = (i, r) => [C + r * Math.sin((2 * Math.PI * i) / n), C - r * Math.cos((2 * Math.PI * i) / n)];
  let rings = "";
  for (const f of [0.25, 0.5, 0.75, 1]) {
    rings += `<polygon points="${items.map((_, i) => pt(i, R * f).join(",")).join(" ")}" fill="none" stroke="#2b3554"/>`;
  }
  const vals = items.map(([, v, b]) => Math.min(1, Math.max(0.05, ((v || 0) / b) * 0.5)));
  const shape = vals.map((v, i) => pt(i, R * v).join(",")).join(" ");
  const labels = items.map(([l, v], i) => {
    const [lx, ly] = pt(i, R + 22);
    return `<text x="${lx}" y="${ly}" fill="#9aa4c4" font-size="11" text-anchor="middle">${l}</text>
      <text x="${lx}" y="${ly + 13}" fill="#eef1fb" font-size="11" font-weight="600" text-anchor="middle">${v === null || v === undefined ? "—" : Math.round(v * 100) / 100}</text>`;
  }).join("");
  return `<svg viewBox="0 0 240 250" style="width:100%;max-width:300px;margin:auto;display:block">
    ${rings}<polygon points="${shape}" fill="rgba(255,79,100,.25)" stroke="#ff4f64" stroke-width="2"/>${labels}
    <polygon points="${items.map((_, i) => pt(i, R * 0.5).join(",")).join(" ")}" fill="none" stroke="#ffd166" stroke-dasharray="3 3" opacity=".7"/></svg>
    <div class="faint" style="text-align:center;font-size:12px">黃色虛線 ＝ 一般玩家水準</div>`;
}

function donut(pct, color, label) {
  const r = 34, c = 2 * Math.PI * r, v = (pct || 0) / 100;
  return `<div style="text-align:center"><svg viewBox="0 0 90 90" width="96" height="96">
    <circle cx="45" cy="45" r="${r}" fill="none" stroke="#212a44" stroke-width="10"/>
    <circle cx="45" cy="45" r="${r}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"
      stroke-dasharray="${c * v} ${c}" transform="rotate(-90 45 45)"/>
    <text x="45" y="50" text-anchor="middle" fill="#eef1fb" font-size="16" font-weight="700">${fmt(pct, "%")}</text></svg>
    <div class="muted" style="font-size:12px">${label}</div></div>`;
}

function heatmap(heat) {
  const days = ["一", "二", "三", "四", "五", "六", "日"];
  let html = `<div class="heat"><div></div>${Array.from({ length: 24 }, (_, h) => `<div class="h">${h % 3 === 0 ? h : ""}</div>`).join("")}`;
  heat.forEach((row, d) => {
    html += `<div>週${days[d]}</div>`;
    row.forEach(([g, w], h) => {
      let bg = "";
      if (g) {
        const wr = w / g;
        const col = wr >= 0.55 ? "79,227,181" : wr <= 0.45 ? "255,107,129" : "255,209,102";
        bg = `style="background:rgba(${col},${Math.min(1, 0.25 + g * 0.18)})"`;
      }
      html += `<div class="c" ${bg} title="週${days[d]} ${h}:00 · ${g} 場${g ? `，勝率 ${Math.round((w / g) * 100)}%` : ""}"></div>`;
    });
  });
  return html + `</div><div class="row faint" style="font-size:12px;margin-top:8px">
    <span>顏色：</span><span style="color:var(--win)">■ 勝率高</span><span style="color:var(--sun)">■ 普通</span><span style="color:var(--loss)">■ 勝率低</span><span>（越深 = 打越多場）</span></div>`;
}

function dayBars(days) {
  if (!days.length) return "";
  const W = 640, H = 120, bw = (W - 20) / days.length;
  const maxG = Math.max(...days.map((d) => d.games));
  return `<svg viewBox="0 0 ${W} ${H + 20}" style="width:100%;height:auto">${days.map((d, i) => {
    const h = (d.games / maxG) * H, wr = d.wins / d.games;
    const col = wr >= 0.55 ? "#4fe3b5" : wr <= 0.45 ? "#ff6b81" : "#ffd166";
    return `<rect x="${10 + i * bw + 1}" y="${H - h}" width="${Math.max(2, bw - 3)}" height="${h}" rx="3" fill="${col}">
      <title>${d.date}：${d.games} 場 ${d.wins} 勝，K/D ${d.kd ?? "—"}</title></rect>`;
  }).join("")}<text x="10" y="${H + 15}" fill="#6b7598" font-size="8">${days[0].date}</text>
    <text x="${W - 10}" y="${H + 15}" fill="#6b7598" font-size="8" text-anchor="end">${days[days.length - 1].date}</text></svg>`;
}

/* ---------------- 吉祥物講評 ---------------- */
function mascotLine(st) {
  const o = st.overall, lines = [];
  if (st.tilt) return { mood: "sad", text: `連輸 ${st.tilt.losses} 場了…先喝口水、伸個懶腰再回來好不好？` };
  if (st.streak >= 3) lines.push(`連勝 ${st.streak} 場！手感燙到可以煎蛋了 🍳`);
  if (o.hs >= 25) lines.push(`爆頭率 ${o.hs}%，你的準心是黏在別人頭上嗎？`);
  if (o.kd >= 1.2) lines.push(`K/D ${o.kd}，今天你就是隊上的大哥！`);
  if (st.extra.clutch.total_won >= 3) lines.push(`已經贏了 ${st.extra.clutch.total_won} 次殘局，心臟好大顆 👑`);
  if (st.extra.multi["5"]) lines.push(`打出過 ACE！啾啾幫你放煙火 🎆`);
  if (o.kast >= 75) lines.push(`KAST ${o.kast}%，你是最穩的那個隊友～`);
  if (!lines.length) lines.push("每一場都是練習，啾啾陪你一起變強！", "今天也要開開心心打排位喔～");
  return { mood: lines.length > 1 ? "wow" : "happy", text: pick(lines) };
}

/* ---------------- 頁面 ---------------- */
const PAGES = [
  ["overview", "總覽", '<path d="M3 12l9-8 9 8M5 10v10h14V10" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>'],
  ["matches", "對局紀錄", '<path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'],
  ["agents", "特務・地圖・武器", '<circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2" fill="none"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6" stroke="currentColor" stroke-width="2" fill="none"/>'],
  ["habits", "習慣分析", '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'],
  ["room", "角色房間", '<path d="M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6C19 16.5 12 21 12 21z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>'],
  ["recap", "我的回顧", '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>'],
  ["live", "對戰中", '<circle cx="12" cy="12" r="3" fill="currentColor"/><circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="2" fill="none"/>'],
  ["lineups", "Lineup 影片庫", '<rect x="3" y="5" width="18" height="14" rx="3" stroke="currentColor" stroke-width="2" fill="none"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>'],
  ["settings", "設定", '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'],
];

function renderShell() {
  $("#logo").innerHTML = `${mascot("small")}<div><b><span>VAL</span> 小戰績</b><small>你的特戰英豪小幫手</small></div>`;
  $("#nav").innerHTML = PAGES.map(([id, label, icon]) =>
    `<a href="#/${id}" data-p="${id}"><svg viewBox="0 0 24 24">${icon}</svg><span>${label}</span></a>`).join("");
}

function renderSource() {
  const s = S.status;
  if (!s) return;
  const p = s.profile || {};
  $("#src").innerHTML = `
    <div><span class="dot ${s.game_open ? "on" : ""}"></span>${s.demo ? "展示模式" : s.game_open ? "遊戲已連線" : "遊戲未開啟"}</div>
    <div style="margin-top:4px"><span class="dot ${s.henrik_ready ? "on" : ""}"></span>離線查詢${s.henrik_ready ? "可用" : "未設定"}</div>
    <div style="margin-top:8px" class="faint">${s.match_count} 場已存 · ${p.last_sync ? "同步 " + timeAgo(p.last_sync) : "尚未同步"}</div>
    <button class="btn ghost" id="syncBtn" style="width:100%;justify-content:center;margin-top:10px">⟳ 同步戰績</button>
    ${S.update?.available ? `<button class="btn" id="updBtn" style="width:100%;justify-content:center;margin-top:8px">⬆️ 更新到 ${esc(S.update.latest)}</button>` : ""}`;
  $("#syncBtn").onclick = doSync;
  if ($("#updBtn")) $("#updBtn").onclick = applyUpdate;
}

async function doSync() {
  const b = $("#syncBtn");
  if (b) { b.disabled = true; b.textContent = "同步中…"; }
  try {
    const r = await api("/api/sync", {});
    toast(r.source === "riot" ? `從遊戲同步完成，新增 ${r.new} 場` : r.source === "henrik" ? `離線同步完成，新增 ${r.new} 場` : "同步完成");
    S.stats = null;
    await refreshStatus();
    route();
  } catch (e) {
    toast("同步失敗：" + e.message);
    if (b) { b.disabled = false; b.textContent = "⟳ 同步戰績"; }
  }
}

async function refreshStatus() {
  try { S.status = await api("/api/status"); } catch { S.status = null; }
  renderSource();
}

async function getStats() {
  if (!S.stats || S.stats._queue !== S.queue) {
    const st = await api(`/api/stats?queue=${encodeURIComponent(S.queue)}`);
    st._queue = S.queue;
    S.stats = st;
  }
  return S.stats;
}

function queueChips(st) {
  const qs = ["all", ...(st.queues || []).filter((q) => q && q !== "custom")];
  return `<div class="chips">${qs.map((q) => `<button class="chip ${q === S.queue ? "on" : ""}" data-q="${q}">${esc(qName(q))}</button>`).join("")}</div>`;
}
function bindQueue() {
  document.querySelectorAll("[data-q]").forEach((b) => b.onclick = () => { S.queue = b.dataset.q; route(); });
}
function noData() {
  const s = S.status || {};
  return emptyBox(`<h3>還沒有戰績資料</h3>
    <p class="muted">${s.game_open ? "按左下角「同步戰績」從遊戲抓資料。" : "開啟特戰英豪後按「同步戰績」；或到「設定」填 HenrikDev key 和 Riot ID，沒開遊戲也能抓。"}</p>
    <button class="btn" onclick="doSync()">⟳ 立刻同步</button>`);
}

/* ===== 總覽 ===== */
async function pageOverview(el) {
  const st = await getStats();
  if (st.empty || !st.overall.games) { el.innerHTML = noData(); return; }
  const o = st.overall, e = st.extra, r = st.me.rank || {}, rec = st.recent;
  const topAgent = st.agents[0]?.agent, topMap = st.maps[0]?.map;
  const portrait = A.agents[topAgent]?.portrait;
  const splash = mapInfo(topMap)?.splash;
  const ml = mascotLine(st);
  const delta = (cur, avg, inv) => {
    if (cur == null || avg == null || st.overall.games < 8) return "";
    const diff = cur - avg, good = inv ? diff < 0 : diff > 0;
    if (Math.abs(diff) < (Math.abs(avg) * 0.03 || 0.01)) return `<div class="d faint">近 5 場持平</div>`;
    return `<div class="d ${good ? "win" : "loss"}">${diff > 0 ? "▲" : "▼"} 近 5 場 ${fmt(cur)}</div>`;
  };
  const tile = (k, v, ic, d = "", extra = "") => `<div class="tile ${extra}"><div class="k">${k}</div><div class="v num">${v}</div>${d}<div class="ic">${ic}</div></div>`;

  el.innerHTML = `
    <div class="topbar"><h2>總覽</h2><div class="sp"></div>${queueChips(st)}</div>
    <div class="hero">
      ${splash ? `<div class="bgmap" style="background-image:url('${splash}')"></div>` : ""}
      ${portrait ? `<img class="portrait" src="${portrait}" alt="">` : ""}
      <div class="who">
        ${tierImg(r.tier, "rankicon")}
        <div>
          <h1>${esc(st.me.name || "我")}</h1>
          <div class="rk">${esc(tierName(r.tier))} ${r.tier ? `<small>${r.rr} RR</small>` : ""}</div>
          ${r.tier ? `<div class="rrbar"><i style="width:${Math.min(100, r.rr)}%"></i></div>` : ""}
          <div class="meta">最高 ${esc(tierName(r.peak))} · 本季 ${r.wins ?? 0}W / ${Math.max(0, (r.games ?? 0) - (r.wins ?? 0))}L
            ${topAgent ? ` · 本命特務 <b>${esc(agentName(topAgent))}</b>` : ""}</div>
        </div>
      </div>
      <div class="mascot-wrap"><div class="bubble" id="bubble">${esc(ml.text)}</div>${mascot("", ml.mood)}</div>
    </div>

    ${st.tilt ? `<div class="alert"><div class="em">🫖</div><div><b>狀態提醒</b><div class="muted">連輸 ${st.tilt.losses} 場，最近 5 場 K/D ${st.tilt.recent_kd}（平常 ${st.tilt.avg_kd}）。
      休息一下再打，通常比硬上分更有效喔。</div></div></div>` : ""}

    <div class="tiles">
      ${tile("勝率", fmt(o.winrate, "%"), "🏆", `<div class="d faint">${o.wins}W ${o.losses}L · ${o.games} 場</div>`, "hl")}
      ${tile("K/D", fmt(o.kd), "⚔️", delta(rec.kd, o.kd))}
      ${tile("爆頭率", fmt(o.hs, "%"), "🎯", delta(rec.hs, o.hs))}
      ${tile("ADR 場均傷害", fmt(o.adr), "💥", delta(rec.adr, o.adr))}
      ${tile("ACS 戰鬥分數", fmt(o.acs), "📈", delta(rec.acs, o.acs))}
      ${tile(`KAST <span class="tag-new">加碼</span>`, fmt(o.kast, "%"), "🛡️", `<div class="d faint">有貢獻的回合比例</div>`)}
      ${tile(`DDΔ <span class="tag-new">加碼</span>`, (o.dd > 0 ? "+" : "") + fmt(o.dd), "⚖️", `<div class="d faint">每回合傷害差</div>`)}
      ${tile(`首殺 / 首死 <span class="tag-new">加碼</span>`, `${e.fk} / ${e.fd}`, "🚪", `<div class="d faint">比值 ${fmt(e.fk_fd)}</div>`)}
      ${tile(`殘局 <span class="tag-new">加碼</span>`, `${e.clutch.total_won} / ${e.clutch.total_att}`, "👑", `<div class="d faint">勝率 ${fmt(e.clutch.rate, "%")}</div>`)}
      ${tile("KDA", fmt(o.kda), "🤝", `<div class="d faint">${o.k} / ${o.d} / ${o.a}</div>`)}
      ${st.forecast ? tile(`上分預測 <span class="tag-new">加碼</span>`,
        st.forecast.dir === "up" ? `${st.forecast.games} 場` : st.forecast.dir === "down" ? "⚠️ 掉分中" : "持平",
        "🔮", `<div class="d ${st.forecast.dir === "up" ? "win" : st.forecast.dir === "down" ? "loss" : "faint"}">${
          st.forecast.dir === "up" ? `照目前節奏升上 ${esc(tierName(st.forecast.next))}（平均 +${st.forecast.avg}/場）`
          : st.forecast.dir === "down" ? `再 ${st.forecast.games} 場可能掉到 ${esc(tierName(st.forecast.next))}`
          : `最近平均 ${st.forecast.avg} RR/場`}</div>`) : ""}
    </div>

    <div class="grid g2 section">
      <div class="card"><h3>📈 RR 走勢 <span class="hint">競技模式</span></h3>${rrChart(st.rr_history)}</div>
      <div class="card"><h3>🕸️ 能力雷達</h3>${radar(o, e)}</div>
    </div>

    <div class="grid g2 section">
      <div class="card"><h3>🔥 近 20 場 <span class="hint">${st.streak > 0 ? `${st.streak} 連勝中` : st.streak < 0 ? `${-st.streak} 連敗中` : ""} · 最長連勝 ${st.best_streak}</span></h3>
        <div class="form">${st.form.map((f) => `<span class="${f}">${f === "W" ? "勝" : f === "L" ? "敗" : "平"}</span>`).join("")}</div>
        <div class="grid g3" style="margin-top:16px">
          <div><div class="faint" style="font-size:12px">MVP 次數</div><div style="font-size:20px;font-weight:700">${e.mvps} <span class="faint" style="font-size:12px">+ 隊伍 MVP ${e.team_mvps}</span></div></div>
          <div><div class="faint" style="font-size:12px">總遊玩時間</div><div style="font-size:20px;font-weight:700">${e.playtime_h} 小時</div></div>
          <div><div class="faint" style="font-size:12px">單場最佳</div><div style="font-size:20px;font-weight:700">${st.best_match ? `${st.best_match.acs} ACS` : "—"}</div>
            ${st.best_match ? `<div class="faint" style="font-size:12px">${esc(agentName(st.best_match.agent))} · ${esc(mapName(st.best_match.map))}</div>` : ""}</div>
        </div>
      </div>
      <div class="card"><h3>🎖️ 成就徽章 <span class="hint">${st.badges.filter((b) => b.count).length} / ${st.badges.length}</span></h3>
        <div class="badges">${st.badges.map((b) => `<div class="badge ${b.count ? "got" : ""}" title="${esc(b.desc)}">
          <div class="em">${BADGE_EMOJI[b.id] || "⭐"}</div><b>${esc(b.name)}</b><small>${b.count ? `<span class="cnt">×${b.count}</span>` : esc(b.desc)}</small></div>`).join("")}</div>
      </div>
    </div>`;
  bindQueue();
  $(".hero .mascot").onclick = () => { const l = mascotLine(st); $("#bubble").textContent = l.text; };
}

/* ===== 對局紀錄 ===== */
function matchTags(m) {
  return m.tags.map((t) => {
    const c = t === "ACE" ? "ACE" : t === "MVP" ? "MVP" : t === "4K" ? "k4" : t === "殘局" ? "clutch" : "tmvp";
    return `<span class="mtag ${c}">${esc(t)}</span>`;
  }).join("");
}
async function pageMatches(el) {
  const st = await getStats();
  if (st.empty || !st.matches.length) { el.innerHTML = noData(); return; }
  el.innerHTML = `
    <div class="topbar"><h2>對局紀錄</h2><span class="faint">${st.matches.length} 場 · 點一下看細節</span><div class="sp"></div>${queueChips(st)}</div>
    <div class="mlist">${st.matches.map((m) => {
      const res = m.won === true ? "W" : m.won === false ? "L" : "D";
      const mi = mapInfo(m.map);
      return `<div class="mrow ${res}" data-id="${esc(m.id)}">
        ${mi?.list ? `<div class="mapbg" style="background-image:url('${mi.list}')"></div>` : ""}
        <div class="bar"></div>
        ${agentImg(m.agent)}
        <div><div class="big">${esc(mapName(m.map))}</div><div class="lbl">${esc(qName(m.queue))} · ${timeAgo(m.start)}</div></div>
        <div><div class="big ${res === "W" ? "win" : res === "L" ? "loss" : "draw"}">${res === "W" ? "勝利" : res === "L" ? "落敗" : "平手"}</div><div class="lbl num">${m.score || "—"}</div></div>
        <div><div class="big num">${m.k} / ${m.d} / ${m.a}</div><div class="lbl">K / D / A</div></div>
        <div><div class="big num ${m.kd >= 1 ? "win" : "loss"}">${fmt(m.kd, "", 2)}</div><div class="lbl">K/D</div></div>
        <div><div class="big num">${fmt(m.acs)}</div><div class="lbl">ACS</div></div>
        <div class="opt"><div class="big num">${fmt(m.adr)}</div><div class="lbl">ADR</div></div>
        <div class="opt"><div class="big num">${fmt(m.hs, "%")}</div><div class="lbl">爆頭率</div></div>
        <div class="mtags">${matchTags(m)}</div>
      </div>`;
    }).join("")}</div>`;
  bindQueue();
  document.querySelectorAll(".mrow").forEach((r) => r.onclick = () => openMatch(r.dataset.id));
}

async function openMatch(id) {
  const wrap = document.createElement("div");
  wrap.className = "modal";
  wrap.innerHTML = `<div class="box">${loading("讀取對局…")}</div>`;
  wrap.onclick = (ev) => { if (ev.target === wrap) wrap.remove(); };
  document.body.appendChild(wrap);
  try {
    const d = await api(`/api/match/${encodeURIComponent(id)}`);
    const res = d.won === true ? "勝利" : d.won === false ? "落敗" : "平手";
    const ICON = { elim: "☠", detonate: "💥", defuse: "🧯", time: "⏱", surrender: "🏳" };
    const half = { competitive: 12, unrated: 12, premier: 12, swiftplay: 4, spikerush: 3 }[d.queue];
    const tl = d.round_log.map((r, i) => `<div class="rd ${r.won ? "w" : "l"} ${half && i && i % half === 0 && i <= half ? "half" : ""}"
        title="第 ${i + 1} 回合 · ${r.won ? "贏" : "輸"} · ${r.side === "atk" ? "進攻" : r.side === "def" ? "防守" : ""} · 擊殺 ${r.k}${r.fk ? " · 首殺" : ""}${r.clutch ? ` · 1v${r.clutch} 殘局！` : ""}${r.plant ? " · 你埋的包" : ""}">
        ${r.k ? `<span class="k">${r.k}</span>` : ""}<i>${r.clutch ? "👑" : ICON[r.result] || "•"}</i><span>${i + 1}</span></div>`).join("");
    const rowsFor = (ally) => d.board.filter((b) => b.ally === ally).map((b) => `<tr class="${b.me ? "me" : ally ? "" : "enemy"}">
        <td><div class="rankcell">${agentImg(b.agent, "av sm")}<span>${b.name ? esc(b.name) : `<span class="muted">${esc(agentName(b.agent))}</span>`}
          ${b.me ? '<span class="pill">我</span>' : b.party ? '<span class="pill" style="background:var(--lilac)">組隊</span>' : ""}</span></div></td>
        <td>${b.tier ? rankCell(b.tier) : '<span class="faint">—</span>'}</td>
        <td class="r num">${fmt(b.acs)}</td><td class="r num">${b.k} / ${b.d} / ${b.a}</td>
        <td class="r num">${fmt(b.adr)}</td><td class="r num">${fmt(b.hs, "%")}</td></tr>`).join("");
    const clutches = Object.entries(d.clutch_won).filter(([, v]) => v).map(([k, v]) => `1v${k} ×${v}`).join("、");
    wrap.querySelector(".box").innerHTML = `
      <button class="close" aria-label="關閉">✕</button>
      <div class="row">${agentImg(d.agent, "av lg")}<div>
        <h2 style="margin:0">${esc(mapName(d.map))} · <span class="${d.won ? "win" : d.won === false ? "loss" : "draw"}">${res} ${d.score || ""}</span></h2>
        <div class="muted">${esc(qName(d.queue))} · ${esc(agentName(d.agent))} · ${d.start ? new Date(d.start).toLocaleString("zh-TW") : ""} · ${Math.round((d.len || 0) / 60000)} 分鐘</div></div></div>
      <div class="tiles">
        <div class="tile"><div class="k">K / D / A</div><div class="v num">${d.k}/${d.d}/${d.a}</div></div>
        <div class="tile"><div class="k">ACS</div><div class="v num">${fmt(d.acs)}</div></div>
        <div class="tile"><div class="k">ADR</div><div class="v num">${fmt(d.adr)}</div></div>
        <div class="tile"><div class="k">爆頭率</div><div class="v num">${fmt(d.hs, "%")}</div></div>
        <div class="tile"><div class="k">KAST</div><div class="v num">${fmt(d.kast, "%")}</div></div>
        <div class="tile"><div class="k">首殺 / 首死</div><div class="v num">${d.fk} / ${d.fd}</div></div>
        <div class="tile"><div class="k">進攻 / 防守</div><div class="v num" style="font-size:20px">${d.atk[0]}/${d.atk[1]} · ${d.def[0]}/${d.def[1]}</div></div>
        <div class="tile"><div class="k">平均裝備價值</div><div class="v num" style="font-size:20px">${fmt(d.loadout)}</div></div>
      </div>
      ${d.round_log.length ? `<h3 style="margin:20px 0 4px">回合時間軸</h3><div class="faint" style="font-size:12px">☠ 殲滅 · 💥 引爆 · 🧯 拆除 · ⏱ 時間到 · 👑 你的殘局 · 右上數字 = 你的擊殺</div>
        <div class="timeline">${tl}</div>` : ""}
      ${clutches ? `<div class="muted">👑 這場你贏了：${clutches}</div>` : ""}
      <h3 style="margin:20px 0 6px">🗺️ 2D 回放 <span class="hint" style="font-weight:400;color:var(--faint);font-size:12px">每次擊殺當下大家站的位置 · 點回合或按播放</span></h3>
      <div class="replay" id="replayBox"></div>
      <h3 style="margin:20px 0 6px">計分板</h3>
      <div class="faint" style="font-size:12px;margin-bottom:6px">只顯示你和組隊隊友的名稱，其他玩家以特務顯示。</div>
      <table><thead><tr><th>玩家</th><th>牌位</th><th class="r">ACS</th><th class="r">K / D / A</th><th class="r">ADR</th><th class="r">爆頭率</th></tr></thead>
      <tbody><tr class="teamsep"><td colspan="6">我方</td></tr>${rowsFor(true)}<tr class="teamsep"><td colspan="6">敵方</td></tr>${rowsFor(false)}</tbody></table>`;
    wrap.querySelector(".close").onclick = () => wrap.remove();
    mountReplay(wrap.querySelector("#replayBox"), d);
  } catch (e) {
    wrap.querySelector(".box").innerHTML = `<div class="err">${esc(e.message)}</div>`;
  }
}

/* ===== 特務・地圖・武器 ===== */
async function pageAgents(el) {
  const st = await getStats();
  if (st.empty || !st.overall.games) { el.innerHTML = noData(); return; }
  const maxW = Math.max(1, ...st.weapons.map((w) => w.kills));
  el.innerHTML = `
    <div class="topbar"><h2>特務・地圖・武器</h2><div class="sp"></div>${queueChips(st)}</div>
    <div class="card"><h3>🧑‍🚀 特務表現 <span class="hint">依場數排序</span></h3>
      <div class="acards">${st.agents.map((a) => `<div class="acard">
        ${agentImg(a.agent, "av lg")}
        <div style="flex:1"><b>${esc(agentName(a.agent))}</b> <span class="faint" style="font-size:12px">${a.games} 場</span>
          <div class="st">勝率 <b class="${(a.winrate ?? 0) >= 50 ? "win" : "loss"}">${fmt(a.winrate, "%")}</b> · K/D ${fmt(a.kd)} · ACS ${fmt(a.acs)}</div>
          <div class="st">爆頭 ${fmt(a.hs, "%")} · ADR ${fmt(a.adr)} · KAST ${fmt(a.kast, "%")}</div>
          <div class="wbar"><i style="width:${a.winrate || 0}%"></i></div></div></div>`).join("")}</div></div>

    <div class="card section"><h3>🗺️ 地圖表現 <span class="hint">點地圖看你的擊殺／陣亡熱點 🔥</span></h3>
      <div class="grid g3">${st.maps.map((m) => {
        const mi = mapInfo(m.map);
        return `<div class="mapcard clickable" data-heat="${esc(m.map)}" title="點我看這張圖的熱點">${mi?.splash ? `<div class="bg" style="background-image:url('${mi.splash}')"></div>` : ""}
          <div class="in"><h4>${esc(mapName(m.map))}</h4>
            <div class="muted" style="font-size:13px">${m.games} 場 · 勝率 <b class="${(m.winrate ?? 0) >= 50 ? "win" : "loss"}">${fmt(m.winrate, "%")}</b> · K/D ${fmt(m.kd)}</div>
            <div class="sides"><span>⚔️ 進攻 ${fmt(m.atk, "%")}</span><span>🛡️ 防守 ${fmt(m.def, "%")}</span></div>
            ${m.best_agent ? `<div class="reco">${agentImg(m.best_agent.agent, "av sm")} 推薦：${esc(agentName(m.best_agent.agent))}（${m.best_agent.games} 場勝率 ${fmt(m.best_agent.winrate, "%")}）</div>` : ""}
          </div></div>`;
      }).join("")}</div></div>

    <div class="card section"><h3>🔫 武器擊殺榜</h3>
      <div class="wlist">${st.weapons.slice(0, 12).map((w) => {
        const icon = A.weapons[w.weapon]?.icon;
        return `<div class="wrow">${icon ? `<img src="${icon}" alt="">` : `<span class="faint">—</span>`}
          <span>${esc(weaponName(w.weapon))}</span><div class="hbar"><i style="width:${(w.kills / maxW) * 100}%"></i></div>
          <span class="num r">${w.kills}<span class="faint"> · ${w.share}%</span></span></div>`;
      }).join("") || '<div class="faint">沒有擊殺資料</div>'}</div></div>`;
  bindQueue();
  el.querySelectorAll("[data-heat]").forEach((c) => c.onclick = () => openHeat(c.dataset.heat));
}

/* ===== 習慣分析 ===== */
async function pageHabits(el) {
  const st = await getStats();
  if (st.empty || !st.overall.games) { el.innerHTML = noData(); return; }
  const e = st.extra;
  const cl = [1, 2, 3, 4, 5].map((n) => {
    const att = e.clutch.att[n] || 0, won = e.clutch.won[n] || 0;
    return `<tr><td>1v${n}</td><td class="r num">${won} / ${att}</td><td style="width:50%"><div class="hbar"><i style="width:${att ? (won / att) * 100 : 0}%;background:linear-gradient(90deg,var(--sky),var(--mint))"></i></div></td></tr>`;
  }).join("");
  const mk = [2, 3, 4, 5].map((n) => `<div class="tile"><div class="k">${n === 5 ? "ACE" : n + "K"}</div><div class="v num">${e.multi[n] || 0}</div></div>`).join("");
  const castNames = ["C 技能", "Q 技能", "E 技能", "大招"];
  el.innerHTML = `
    <div class="topbar"><h2>習慣分析</h2><div class="sp"></div>${queueChips(st)}</div>
    <div class="card"><h3>🗓️ 什麼時候打最強？ <span class="hint">本機時間</span></h3>${heatmap(st.heat)}</div>
    <div class="card section"><h3>📅 每日場數與勝率 <span class="hint">近 60 天</span></h3>${dayBars(st.days)}</div>

    <div class="grid g3 section">
      <div class="card"><h3>⚔️ 攻守表現</h3><div class="row" style="justify-content:space-around">
        ${donut(e.atk.rate, "#ff4f64", `進攻 ${e.atk.won}/${e.atk.played}`)}${donut(e.def.rate, "#5ab8ff", `防守 ${e.def.won}/${e.def.played}`)}</div></div>
      <div class="card"><h3>👑 殘局</h3><table><tbody>${cl}</tbody></table></div>
      <div class="card"><h3>💥 多殺</h3><div class="tiles" style="margin:0;grid-template-columns:1fr 1fr">${mk}</div></div>
    </div>

    <div class="grid g2 section">
      <div class="card"><h3>🤝 最佳拍檔 <span class="hint">一起組隊的人</span></h3>
        ${st.partners.length ? `<table><thead><tr><th>隊友</th><th class="r">場數</th><th class="r">勝率</th></tr></thead><tbody>
          ${st.partners.map((p) => `<tr><td>${esc(p.name)}</td><td class="r num">${p.games}</td><td class="r num ${(p.winrate ?? 0) >= 50 ? "win" : "loss"}">${fmt(p.winrate, "%")}</td></tr>`).join("")}</tbody></table>` : `<div class="faint">還沒有組隊紀錄。</div>`}
        <div class="grid g2" style="margin-top:14px">
          <div class="tile"><div class="k">單排</div><div class="v num">${fmt(st.solo.winrate, "%")}</div><div class="d faint">${st.solo.games} 場 · K/D ${fmt(st.solo.kd)}</div></div>
          <div class="tile"><div class="k">組隊</div><div class="v num">${fmt(st.duo.winrate, "%")}</div><div class="d faint">${st.duo.games} 場 · K/D ${fmt(st.duo.kd)}</div></div>
        </div></div>
      <div class="card"><h3>🧠 打法細節</h3>
        <div class="tiles" style="margin:0">
          <div class="tile"><div class="k">每回合擊殺</div><div class="v num">${fmt(st.overall.kpr)}</div></div>
          <div class="tile"><div class="k">首殺率</div><div class="v num">${e.fk_per_round ? fmt(Math.round(e.fk_per_round * 1000) / 10, "%") : "—"}</div></div>
          <div class="tile"><div class="k">幫隊友報仇</div><div class="v num">${e.trades}</div><div class="d faint">5 秒內交易擊殺</div></div>
          <div class="tile"><div class="k">被報仇</div><div class="v num">${e.traded}</div><div class="d faint">陣亡後有人補位</div></div>
          <div class="tile"><div class="k">平均裝備價值</div><div class="v num">${fmt(e.loadout)}</div></div>
          <div class="tile"><div class="k">埋包 / 拆包</div><div class="v num">${e.plants} / ${e.defuses}</div></div>
        </div>
        ${e.casts ? `<h3 style="margin-top:16px">✨ 每回合技能使用</h3><div class="wlist">${e.casts.map((c, i) => `<div class="wrow" style="grid-template-columns:70px 1fr 50px">
          <span>${castNames[i]}</span><div class="hbar"><i style="width:${Math.min(100, (c / 2) * 100)}%"></i></div><span class="r num">${c}</span></div>`).join("")}</div>` : ""}
      </div>
    </div>`;
  bindQueue();
}

/* ===== 對戰中 ===== */
async function pageLive(el) {
  clearInterval(S.liveTimer);
  const draw = async () => {
    if (!location.hash.startsWith("#/live") || !el.isConnected) { clearInterval(S.liveTimer); return; }
    let d;
    try { d = await api("/api/live"); } catch (e) { el.innerHTML = `<div class="topbar"><h2>對戰中</h2></div>${emptyBox(`<span class="err">${esc(e.message)}</span>`, "sad")}`; return; }
    if (d.phase === "offline") {
      el.innerHTML = `<div class="topbar"><h2>對戰中</h2></div>${emptyBox("<h3>遊戲還沒開</h3><p class='muted'>開啟特戰英豪後，這頁會自動顯示選角／對戰中的玩家。</p>")}`;
      return;
    }
    if (d.phase === "menus") {
      el.innerHTML = `<div class="topbar"><h2>對戰中</h2><span class="faint">每 15 秒自動檢查</span></div>${emptyBox("<h3>目前在大廳</h3><p class='muted'>進入選角或對戰後，隊友資料和這張地圖的 lineup 會自動出現。</p>")}`;
      return;
    }
    const me = d.players.find((p) => p.me);
    const mi = mapInfo(d.map);
    const showEnemy = S.status?.settings?.show_enemies !== false;
    const row = (p) => {
      const r = p.rank;
      return `<tr class="${p.me ? "me" : ""}">
        <td><div class="rankcell">${p.agent ? agentImg(p.agent, "av sm") : ""}<span>${p.agent ? esc(agentName(p.agent)) : '<span class="faint">選擇中…</span>'}</span>${!p.locked ? ' <span class="faint">(未鎖定)</span>' : ""}</div></td>
        <td>${p.hidden ? '<span class="hidden-tag">已隱藏</span>' : esc(p.name || "—")} ${p.me ? '<span class="pill">我</span>' : ""}</td>
        <td>${r ? rankCell(r.tier, r.tier ? ` <span class="faint">${r.rr} RR</span>` : "") : '<span class="faint">—</span>'}</td>
        <td>${r ? rankCell(r.peak) : '<span class="faint">—</span>'}</td>
        <td class="r num">${r && r.games ? `${Math.round((r.wins / r.games) * 100)}% <span class="faint">(${r.wins}W/${r.games - r.wins}L)</span>` : "—"}</td>
        <td class="r num">${fmt(p.level)}</td></tr>`;
    };
    const avgTier = (ps) => {
      const t = ps.map((p) => p.rank?.tier).filter(Boolean);
      return t.length ? Math.round(t.reduce((a, b) => a + b, 0) / t.length) : 0;
    };
    const allies = d.players.filter((p) => p.side !== "enemy"), enemies = d.players.filter((p) => p.side === "enemy");
    const aT = avgTier(allies), eT = avgTier(enemies);
    const thead = `<thead><tr><th>特務</th><th>玩家</th><th>目前牌位</th><th>最高牌位</th><th class="r">本季勝率</th><th class="r">等級</th></tr></thead>`;
    const enemyCard = !showEnemy ? "" : d.phase === "pregame"
      ? `<div class="card section"><h3>😈 敵方</h3><div class="faint">選角階段 Riot 不提供敵方資料，進入對戰後會自動出現。</div></div>`
      : enemies.length ? `<div class="card section enemy-card"><h3>😈 敵方 ${eT ? `<span class="hint">平均 ${rankCell(eT)}</span>` : ""}</h3>
          <table>${thead}<tbody>${enemies.map(row).join("")}</tbody></table></div>` : "";
    el.innerHTML = `
      <div class="topbar"><h2>對戰中</h2><span class="faint">每 15 秒自動更新</span><div class="sp"></div>
        <label class="switch" style="padding:0"><input type="checkbox" id="fEnemy" ${showEnemy ? "checked" : ""}><span></span><div style="font-size:13px">顯示敵方</div></label></div>
      <div class="livehead">${mi?.splash ? `<div class="bg" style="background-image:url('${mi.splash}')"></div>` : ""}
        <div class="pulse"></div><span class="pill">${d.phase === "pregame" ? "選角中" : "對戰中"}</span>
        <div><div style="font-size:20px;font-weight:700">${esc(mapName(d.map))}</div><div class="muted">${esc(qName(d.queue))}</div></div>
        ${aT && eT && showEnemy ? `<div class="vs">${rankCell(aT)}<b>VS</b>${rankCell(eT)}</div>` : ""}
        <div style="flex:1"></div>${me?.agent ? `${agentImg(me.agent, "av lg")}<div><div class="faint" style="font-size:12px">你的特務</div><b>${esc(agentName(me.agent))}</b></div>` : ""}</div>
      <div class="card section"><h3>👥 我方 ${aT ? `<span class="hint">平均 ${rankCell(aT)}</span>` : ""}</h3>
        <table>${thead}<tbody>${allies.map(row).join("")}</tbody></table></div>
      ${enemyCard}
      <div class="faint" style="font-size:12px;margin-top:8px">開了「隱藏名稱」的玩家（不分敵我）都不會查詢名字、牌位和等級。</div>
      <div class="card section"><h3>🎬 這場的 Lineup <span class="hint">${me?.agent ? esc(agentName(me.agent)) + " × " : ""}${esc(mapName(d.map))}</span></h3>
        <div id="liveLineup"></div></div>`;
    $("#fEnemy", el).onchange = async (ev) => {
      await api("/api/settings", { show_enemies: ev.target.checked });
      await refreshStatus();
      draw();
    };
    renderLineupContent($("#liveLineup", el), me?.agent || null, mi?.uuid || d.map, true);
  };
  el.innerHTML = loading("檢查對戰狀態…");
  await draw();
  S.liveTimer = setInterval(() => { if (!document.querySelector(".vid iframe")) draw(); }, 15000);
}

/* ===== Lineup 影片庫 ===== */
function slug(s) { return (s || "").toLowerCase().replace(/[^a-z0-9]/g, ""); }
function ytId(url) {
  const m = String(url).match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}
function videoCard(v, removable) {
  const id = ytId(v.url);
  return `<div class="vid">${id
    ? `<img class="thumb" src="https://i.ytimg.com/vi/${id}/hqdefault.jpg" data-yt="${id}" alt="" loading="lazy">`
    : `<a class="linkcard" href="${esc(v.url)}" target="_blank" rel="noopener" style="border-radius:0;border:0"><span class="em">🔗</span><span>開啟影片</span></a>`}
    <div class="t"><span>${esc(v.title || (id ? "YouTube 影片" : v.url))}</span>
    ${removable ? `<button class="x" data-del="${esc(v.id)}" title="移除">✕</button>` : ""}</div></div>`;
}
function bindVideos(root) {
  root.querySelectorAll("[data-yt]").forEach((img) => img.onclick = () => {
    const f = document.createElement("iframe");
    f.src = `https://www.youtube-nocookie.com/embed/${img.dataset.yt}?autoplay=1`;
    f.allow = "autoplay; encrypted-media; picture-in-picture";
    f.allowFullscreen = true;
    img.replaceWith(f);
  });
  root.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
    await api("/api/favorites/delete", { id: b.dataset.del });
    toast("已移除");
    renderLineupContent(root.closest("[data-lineup-root]") || root, S.lineup.agent, S.lineup.map);
  });
}

async function renderLineupContent(box, agent, map, compact = false) {
  box.setAttribute("data-lineup-root", "1");
  const a = A.agents[agent], mi = mapInfo(map);
  const enA = a?.en || "", enM = mi?.en || "";
  const q = `${enA} ${enM} lineups`.trim();
  const zh = `${a?.name || ""} ${mi?.name || ""} 點位`.trim();
  const tParams = new URLSearchParams();
  if (enA) tParams.set("agent", slug(enA));
  if (enM) tParams.set("map", slug(enM));
  const links = [
    ["▶️", "YouTube 英文 lineup", `https://www.youtube.com/results?search_query=${encodeURIComponent(q || "valorant lineups")}`],
    ["📺", "YouTube 中文教學", `https://www.youtube.com/results?search_query=${encodeURIComponent("特戰英豪 " + zh)}`],
    ["🎞️", "Tracker.gg 教學片段", `https://tracker.gg/valorant/guides/clips${tParams.toString() ? "?" + tParams : ""}`],
  ];
  let favs = [];
  try { favs = await api("/api/favorites"); } catch { /* ignore */ }
  if (!S.pack) { try { S.pack = await fetch("/static/lineups.json").then((r) => r.json()); } catch { S.pack = []; } }
  const sameMap = (m) => enM && m && slug(m) === slug(enM);
  const forAgent = S.pack.filter((v) => enA && slug(v.agent) === slug(enA));
  let picks = [...forAgent.filter((v) => sameMap(v.map)), ...forAgent.filter((v) => !v.map)];
  if (!enM) picks = [...forAgent.filter((v) => !v.map), ...forAgent.filter((v) => v.map)];
  if (picks.length < 3) picks = [...picks, ...S.pack.filter((v) => !v.agent)];
  if (compact) picks = picks.slice(0, 6);
  const mapKey = mi?.uuid || map;
  const mine = favs.filter((f) => (!agent || f.agent === agent) && (!mapKey || !f.map || f.map === mapKey));
  const ytKey = S.status?.settings?.youtube_key;

  box.innerHTML = `
    <div class="linkcards">${links.map(([em, t, u]) => `<a class="linkcard" href="${u}" target="_blank" rel="noopener"><span class="em">${em}</span><div><b>${t}</b><div class="faint" style="font-size:12px">${esc(enA || "全部特務")} · ${esc(enM || "全部地圖")}</div></div></a>`).join("")}</div>
    <h3 style="margin:20px 0 10px">📦 精選影片 <span class="hint">${esc(a?.name || "")}${enM ? " × " + esc(mi.name) : " · 全地圖"} · 點縮圖直接播</span></h3>
    ${picks.length ? `<div class="videos">${picks.map((v) => videoCard({ ...v, title: (v.map ? `【${Object.values(A.maps).find((m) => slug(m.en) === slug(v.map))?.name || v.map}】` : (v.agent ? "【全地圖】" : "【通用】")) + v.title })).join("")}</div>`
      : `<div class="faint">這個特務還沒有精選影片，可以用上面的連結找，找到好的就收藏起來。</div>`}
    <h3 style="margin:20px 0 10px">⭐ 我的收藏 <span class="hint">${mine.length} 部</span></h3>
    ${mine.length ? `<div class="videos">${mine.map((v) => videoCard(v, true)).join("")}</div>` : `<div class="faint">${compact ? "還沒有這個組合的收藏，可以到「Lineup 影片庫」新增。" : "還沒有收藏。看到好用的影片，把網址貼到下面就能存起來，之後對戰中會自動帶出來。"}</div>`}
    ${compact ? "" : `<div class="row" style="margin-top:12px">
      <input id="favUrl" placeholder="貼上 YouTube 或其他影片網址" style="flex:2;min-width:240px;background:var(--bg2);border:1px solid var(--line);color:var(--text);padding:10px 12px;border-radius:12px">
      <input id="favTitle" placeholder="備註（例：A 點後排 lineup）" style="flex:1;min-width:160px;background:var(--bg2);border:1px solid var(--line);color:var(--text);padding:10px 12px;border-radius:12px">
      <button class="btn" id="favAdd">＋ 收藏</button></div>`}
    <h3 style="margin:20px 0 10px">🔎 YouTube 搜尋結果 <span class="hint">${ytKey ? "在 App 裡直接播" : "設定 YouTube API key 後可在這裡直接播放"}</span></h3>
    <div id="ytResults">${ytKey ? loading("搜尋影片…") : `<div class="faint">沒有 key 也沒關係，點上面的連結會開啟搜尋結果。</div>`}</div>`;
  bindVideos(box);

  const addBtn = $("#favAdd", box);
  if (addBtn) addBtn.onclick = async () => {
    try {
      await api("/api/favorites", { url: $("#favUrl", box).value, title: $("#favTitle", box).value, agent, map: mapKey });
      toast("已加入收藏 ⭐");
      renderLineupContent(box, agent, map, compact);
    } catch (e) { toast(e.message); }
  };

  if (ytKey) {
    const res = $("#ytResults", box);
    try {
      const u = `https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=${compact ? 4 : 9}&q=${encodeURIComponent("valorant " + (q || "lineups"))}&key=${encodeURIComponent(ytKey)}`;
      const j = await fetch(u).then((r) => r.json());
      if (j.error) throw new Error(j.error.message);
      res.innerHTML = `<div class="videos">${(j.items || []).map((it) => videoCard({ url: `https://youtu.be/${it.id.videoId}`, title: it.snippet.title.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&") })).join("")}</div>`;
      bindVideos(res);
    } catch (e) {
      res.innerHTML = `<div class="err">YouTube 搜尋失敗：${esc(e.message)}</div>`;
    }
  }
}

async function pageLineups(el) {
  const ids = Object.keys(A.agents);
  const hot = ids.filter((id) => LINEUP_AGENTS.includes(A.agents[id].en));
  const rest = ids.filter((id) => !hot.includes(id)).sort((x, y) => agentName(x).localeCompare(agentName(y), "zh-Hant"));
  const mapList = [...new Map(Object.values(A.maps).filter((m) => m.url && !/range|basic|tutorial|skirmish|kasbah|district|piazza|drift|glitch/i.test(m.url)).map((m) => [m.uuid, m])).values()];
  if (!S.lineup.agent && hot.length) S.lineup.agent = hot[0];
  el.innerHTML = `
    <div class="topbar"><h2>Lineup 影片庫</h2><span class="faint">選特務、選地圖，收藏好用的影片</span></div>
    ${ids.length ? "" : `<div class="card err">讀不到特務資料（valorant-api.com 連不上），請確認網路。</div>`}
    <div class="card"><h3>選特務 <span class="hint">🔥 = lineup 常用</span></h3>
      <div class="agentpick">${[...hot, ...rest].map((id) => `<button data-agent="${id}" class="${id === S.lineup.agent ? "on" : ""}">${agentImg(id, "")}${hot.includes(id) ? "🔥" : ""}${esc(agentName(id))}</button>`).join("")}</div>
      <h3 style="margin-top:18px">選地圖</h3>
      <div class="chips"><button class="chip ${!S.lineup.map ? "on" : ""}" data-map="">全部地圖</button>
        ${mapList.map((m) => `<button class="chip ${m.uuid === S.lineup.map ? "on" : ""}" data-map="${m.uuid}">${esc(m.name)}</button>`).join("")}</div>
    </div>
    <div class="card section" id="lineupBox"></div>`;
  el.querySelectorAll("[data-agent]").forEach((b) => b.onclick = () => { S.lineup.agent = b.dataset.agent; pageLineups(el); });
  el.querySelectorAll("[data-map]").forEach((b) => b.onclick = () => { S.lineup.map = b.dataset.map || null; pageLineups(el); });
  renderLineupContent($("#lineupBox", el), S.lineup.agent, S.lineup.map);
}

/* ===== 設定 ===== */
async function pageSettings(el) {
  await refreshStatus();
  const s = S.status || {}, cfg = s.settings || {}, p = s.profile || {};
  el.innerHTML = `
    <div class="topbar"><h2>設定</h2></div>
    <div class="grid g2">
      <div class="card"><h3>🔌 資料來源</h3>
        <p><span class="dot ${s.game_open ? "on" : ""}"></span><b>遊戲連線</b>：${s.game_open ? "已連線（最完整、最即時）" : "遊戲沒開"}</p>
        <p><span class="dot ${s.henrik_ready ? "on" : ""}"></span><b>離線查詢（HenrikDev）</b>：${s.henrik_ready ? "可用" : "需要 API key ＋ Riot ID"}</p>
        <p class="muted" style="font-size:13px">同步時會先用遊戲；遊戲沒開才改用 HenrikDev。抓過的對局會存在電腦裡，沒網路也能看。</p>
        <p class="faint" style="font-size:13px">帳號：${esc(p.name || "—")} · 區域：${esc(p.region || "—")} · 已存 ${s.match_count || 0} 場</p>
        <div class="row"><button class="btn" id="sSync">⟳ 立刻同步</button><button class="btn ghost" id="sClear">清除對局快取</button></div>
      </div>
      <div class="card"><h3>🛠️ 設定</h3>
        <div class="field"><label>Riot ID（離線查詢用）</label><input id="fRiot" placeholder="名字#TAG" value="${esc(cfg.riot_id || "")}">
          <small>開過一次遊戲後 App 會自動記住你，通常不用填。</small></div>
        <div class="field"><label>HenrikDev API key ${cfg.henrik_key_set ? '<span class="win">（已設定）</span>' : ""}</label>
          <input id="fHenrik" type="password" placeholder="${cfg.henrik_key_set ? "已設定，留空表示不變" : "HDEV-xxxx…"}">
          <small>到 <a href="https://api.henrikdev.xyz/dashboard/" target="_blank" rel="noopener">HenrikDev 後台</a> 登入後產生免費 key。只存在你的電腦。</small></div>
        <div class="field"><label>YouTube Data API key（選填）</label><input id="fYt" type="password" placeholder="AIza…" value="${esc(cfg.youtube_key || "")}">
          <small>填了之後，Lineup 頁可以直接在 App 裡搜尋和播放影片。到 Google Cloud Console 開啟 YouTube Data API v3 取得。</small></div>
        <div class="field"><label>每次同步幾場</label><input id="fCount" type="number" min="5" max="150" value="${cfg.sync_count || 40}"></div>
        <button class="btn" id="sSave">儲存設定</button>
      </div>
    </div>
    <div class="grid g2 section">
      <div class="card"><h3>🚀 自動化</h3>
        <label class="switch"><input type="checkbox" id="fAuto"><span></span>
          <div><b>開特戰英豪時自動打開 App</b><div class="faint" style="font-size:12px">開機後在背景待命，偵測到遊戲啟動就自動打開（不碰遊戲本身）</div></div></label>
        <div id="autoDiag" class="diag"></div>
        <button class="btn ghost" id="sShortcut" style="margin:4px 0 8px">🖥️ 在桌面建立捷徑</button>
        <label class="switch"><input type="checkbox" id="fAutoSync" ${cfg.auto_sync !== false ? "checked" : ""}><span></span>
          <div><b>每場打完自動同步</b><div class="faint" style="font-size:12px">打完回到大廳後自動抓這場戰績，跳出結算卡片</div></div></label>
      </div>
      <div class="card"><h3>⬆️ 更新 <span class="hint" id="verLabel"></span></h3>
        <div class="field"><label>更新來源（GitHub 帳號/repo）</label><input id="fRepo" placeholder="例如 kurt/my-val-tracker" value="${esc(cfg.update_repo || "")}">
          <small>設定好之後，按「檢查更新」就會自動下載新版，不用再手動下載 zip。</small></div>
        <div class="row"><button class="btn" id="sUpd">檢查更新</button>${S.update?.available ? `<button class="btn" id="sApply">⬆️ 更新到 ${esc(S.update.latest)}</button>` : ""}</div>
      </div>
    </div>
    <div class="card section buddy-card"><h3>🐣 對戰陪伴啾啾 <span class="hint">對戰時在右下角陪你，只給鼓勵，不給戰術</span></h3>
      <h4 style="margin:4px 0 10px">選角色 <span class="faint" style="font-weight:400;font-size:12px">（新增角色、上傳表情、改個性都在「角色房間」）</span></h4>
      <div class="skins" id="skinPick">${loading()}</div>
      <div class="row" style="margin:14px 0 6px">
        <span class="muted" style="font-size:13px">大小</span>
        <div class="chips">${[["s", "小"], ["m", "中"], ["l", "大"]].map(([v, t]) => `<button class="chip ${v === (cfg.buddy_size || "m") ? "on" : ""}" data-size="${v}">${t}</button>`).join("")}</div>
        <span class="muted" style="font-size:13px;margin-left:12px">位置</span>
        <button class="btn ghost" id="bPos">📍 調整位置</button>
        ${cfg.buddy_pos_set ? `<button class="btn ghost" id="bPosReset">↩ 回到右下角</button>` : ""}
      </div>
      <div class="grid g2">
        <div>
          <label class="switch"><input type="checkbox" id="bOn" ${cfg.buddy_enabled !== false ? "checked" : ""}><span></span>
            <div><b>對戰時自動出現</b><div class="faint" style="font-size:12px">進入對戰自動跳出，打完自動消失</div></div></label>
          <label class="switch"><input type="checkbox" id="bClick" ${cfg.buddy_clickthrough !== false ? "checked" : ""}><span></span>
            <div><b>滑鼠穿透</b><div class="faint" style="font-size:12px">點不到啾啾，不會干擾遊戲（建議開著）</div></div></label>
          <div class="field" style="margin-top:8px"><label>多久說一次話（秒）</label><input id="bInt" type="number" min="10" max="120" value="${cfg.buddy_interval || 20}"></div>
        </div>
        <div>
          <div class="field"><label>讓啾啾「看得到畫面」（選填）</label>
            <select id="bProv"><option value="none">不用 AI（隨機鼓勵台詞）</option><option value="gemini">Google Gemini</option><option value="claude">Claude</option></select>
            <small>選 AI 後，啾啾會看你的遊戲畫面，殺人時誇你、被殺時安慰你。截圖只送給你選的 AI，不會存檔。</small></div>
          <div class="field"><label>AI 金鑰 ${cfg.buddy_key_set ? '<span class="win">（已設定）</span>' : ""}</label>
            <input id="bKey" type="password" placeholder="${cfg.buddy_key_set ? "已設定，留空表示不變" : "貼上 API key"}">
            <small>Gemini：<a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">Google AI Studio</a> 免費申請 · Claude：<a href="https://console.anthropic.com/" target="_blank" rel="noopener">Claude Console</a>（依用量計費）</small></div>
          <div class="field"><label>模型（選填，留空用預設）</label><input id="bModel" placeholder="Gemini 預設 gemini-2.5-flash · Claude 預設 claude-haiku-5-5" value="${esc(cfg.buddy_model || "")}"></div>
        </div>
      </div>
      <div class="row"><button class="btn" id="bSave">儲存</button><button class="btn ghost" id="bPreview">👀 現在叫出來看看</button>
        <button class="btn ghost" id="bTest">🧪 測試：讓啾啾看一次畫面</button></div>
      <p class="faint" style="font-size:12px;margin-bottom:0">遊戲請用「視窗化全螢幕」，啾啾才能顯示在遊戲上面（獨占全螢幕會蓋掉它）。</p>
    </div>
    <div class="card section"><h3>🖼️ 特務圖片</h3>
      <p class="muted" style="margin-top:0">新特務（例如「靜」）官方資料還沒有圖片時，App 會先畫一個可愛的佔位頭像。
        想換成真的圖：把圖片放進下面的資料夾，檔名用特務名字，例如 <b>靜.png</b> 或 <b>Hush.png</b>，重開 App 就會換上。</p>
      <button class="btn ghost" id="sAgents">📂 打開特務圖片資料夾</button>
    </div>
    <div class="card section"><h3>🛡️ 安全說明</h3>
      <ul class="muted" style="margin:0;padding-left:20px">
        <li>對戰中可以看隊友和敵方（可在「對戰中」頁關掉敵方）；開了「隱藏名稱」的玩家不分敵我都不查詢。</li>
        <li>對局詳細只顯示你和組隊隊友的名稱。</li>
        <li>是否在對戰中，是問電腦上的 Riot Client，不會一直打 Riot 伺服器。</li>
        <li>不讀取記憶體、不注入遊戲、不碰 Vanguard 監控的任何東西。</li>
      </ul></div>`;
  $("#sSave").onclick = async () => {
    const body = { riot_id: $("#fRiot").value.trim(), youtube_key: $("#fYt").value.trim(), sync_count: +$("#fCount").value,
      update_repo: $("#fRepo").value.trim(), auto_sync: $("#fAutoSync").checked };
    const hk = $("#fHenrik").value.trim();
    if (hk) body.henrik_key = hk;
    try { await api("/api/settings", body); toast("設定已儲存 ✓"); pageSettings(el); } catch (e) { toast(e.message); }
  };
  $("#sSync").onclick = doSync;
  api("/api/version").then((v) => { $("#verLabel", el).textContent = "目前版本 " + v.version; }).catch(() => {});
  const drawDiag = (a) => {
    const ok = (b) => b ? '<span class="win">✓</span>' : '<span class="loss">✗</span>';
    $("#autoDiag", el).innerHTML = !a.windows ? "" : `
      <div>${ok(a.enabled)} 開機捷徑 ${a.enabled ? "已建立" : "沒有建立"}</div>
      <div>${ok(a.watcher_running)} 背景監看程式 ${a.watcher_running ? "正在待命" : "沒有在跑"}</div>
      <div>${a.game_running ? "🎮 偵測到特戰英豪正在執行" : '<span class="faint">特戰英豪目前沒開</span>'}</div>
      ${a.enabled && !a.watcher_running ? '<button class="btn" id="sWatch" style="margin-top:6px">▶ 重新啟動監看</button>' : ""}
      <details style="margin-top:6px"><summary class="faint">診斷紀錄</summary><pre>${esc((a.log || []).join("\n") || "（還沒有紀錄）")}</pre></details>`;
    const w = $("#sWatch", el);
    if (w) w.onclick = async () => {
      try { drawDiag({ ...(await api("/api/autostart", { enabled: true })), windows: true }); toast("監看程式已啟動 ✓"); }
      catch (e) { toast(e.message, 5000); }
      api("/api/autostart").then(drawDiag);
    };
  };
  api("/api/autostart").then((a) => {
    drawDiag(a);
    const box = $("#fAuto", el);
    box.checked = a.enabled;
    box.disabled = !a.windows;
    box.onchange = async () => {
      try {
        const r = await api("/api/autostart", { enabled: box.checked });
        toast(r.enabled ? "已開啟：之後開特戰英豪會自動打開 App ✓" : "已關閉自動啟動");
        api("/api/autostart").then(drawDiag);
      } catch (e) { box.checked = !box.checked; toast("設定失敗：" + e.message, 4000); }
    };
  }).catch(() => {});
  $("#fAutoSync").onchange = async () => { await api("/api/settings", { auto_sync: $("#fAutoSync").checked }); toast("已儲存 ✓"); };
  $("#sUpd").onclick = async () => {
    if ($("#fRepo").value.trim() !== (cfg.update_repo || "")) await api("/api/settings", { update_repo: $("#fRepo").value.trim() });
    await refreshStatus();
    const r = await checkUpdate(false);
    if (r?.available) pageSettings(el);
  };
  if ($("#sApply")) $("#sApply").onclick = applyUpdate;
  $("#bProv").value = cfg.buddy_provider || "none";
  let sizeSel = cfg.buddy_size || "m";
  api("/api/buddy/skin").then((bs) => {
    const cards = [["jiujiu", "啾啾", window.SKINS.jiujiu.svg("happy"), "漂浮小機器人"],
      ...bs.characters.map((c) => ["custom:" + c.id, c.name, c.cover ? `<img src="/custom-buddy/${encodeURIComponent(c.id)}/${encodeURIComponent(c.cover)}" style="width:100%;height:100%;object-fit:contain">` : "🖼️", "自訂角色"])];
    $("#skinPick", el).innerHTML = cards.map(([id, name, art, desc]) => `<button class="skin ${id === bs.skin ? "on" : ""}" data-skin="${esc(id)}">
      <div class="skin-art">${art}</div><b>${esc(name)}</b><small>${esc(desc)}</small></button>`).join("")
      + `<button class="skin" data-goroom><div class="skin-art">➕</div><b>新增角色</b><small>到角色房間</small></button>`;
    el.querySelectorAll("[data-skin]").forEach((b) => b.onclick = async () => {
      el.querySelectorAll("[data-skin]").forEach((x) => x.classList.toggle("on", x === b));
      await api("/api/settings", { buddy_skin: b.dataset.skin });
      await refreshStatus();
      toast(`已換成「${b.querySelector("b").textContent}」✓`);
    });
    el.querySelector("[data-goroom]").onclick = () => { location.hash = "#/room"; };
  });
  el.querySelectorAll("[data-size]").forEach((b) => b.onclick = async () => {
    sizeSel = b.dataset.size;
    el.querySelectorAll("[data-size]").forEach((x) => x.classList.toggle("on", x === b));
    await api("/api/settings", { buddy_size: sizeSel });
    toast("大小已儲存 ✓（下次出現時生效）");
  });
  $("#bPos", el).onclick = async () => {
    try { await api("/api/buddy/setup", {}); alertBox("角色出現了！把它<b>拖到想要的位置</b>，再按左上角的「✓ 完成」。<br><span class='faint'>拖的時候暫時不會滑鼠穿透。</span>"); }
    catch (e) { toast(e.message, 4000); }
  };
  if ($("#bPosReset", el)) $("#bPosReset", el).onclick = async () => { await api("/api/buddy/setup", { reset: true }); toast("已回到右下角 ✓"); pageSettings(el); };
  const saveBuddy = async () => {
    const body = { buddy_enabled: $("#bOn").checked, buddy_clickthrough: $("#bClick").checked,
      buddy_interval: +$("#bInt").value, buddy_provider: $("#bProv").value, buddy_model: $("#bModel").value.trim() };
    const k = $("#bKey").value.trim();
    if (k) body.buddy_key = k;
    await api("/api/settings", body);
    await refreshStatus();
  };
  $("#bSave").onclick = async () => { try { await saveBuddy(); toast("啾啾設定已儲存 ✓"); } catch (e) { toast(e.message); } };
  $("#bPreview").onclick = async () => {
    try { await saveBuddy(); await api("/api/buddy/preview", {}); toast("啾啾出現在右下角了（45 秒後自己消失）"); }
    catch (e) { toast("叫不出來：" + e.message, 4000); }
  };
  $("#bTest").onclick = async () => {
    const b = $("#bTest");
    b.disabled = true; b.textContent = "啾啾看畫面中…";
    try {
      await saveBuddy();
      const r = await api("/api/buddy/test", {});
      alertBox(`啾啾說：「${esc(r.line)}」${r.error ? `<br><span class="err" style="font-size:13px">AI 沒有回應，先用離線台詞：${esc(r.error)}</span>` : ""}`);
    } catch (e) { toast(e.message, 4000); }
    b.disabled = false; b.textContent = "🧪 測試：讓啾啾看一次畫面";
  };
  $("#sShortcut").onclick = () => api("/api/desktop-shortcut", {})
    .then(() => alertBox("桌面多了一個「VAL 小戰績」捷徑 🎉<br>以後雙擊它就能開 App。<br><span class='faint'>程式資料夾不要移動或刪除喔。</span>"))
    .catch((e) => toast("建立失敗：" + e.message, 4000));
  $("#sAgents").onclick = () => api("/api/open-folder", { which: "agents" }).then((r) => toast("資料夾：" + r.path, 4000)).catch((e) => toast(e.message));
  $("#sClear").onclick = async () => {
    if (!confirm("確定清除所有已存的對局？下次同步會重新下載。")) return;
    await api("/api/clear-cache", {});
    S.stats = null;
    toast("已清除");
    refreshStatus();
  };
}


/* ================= 超酷功能 1：2D 回放 ================= */
const SIDE_COLOR = { me: "#ffd166", ally: "#4fe3b5", enemy: "#ff6b81" };
function mmss(ms) { const t = Math.round((ms || 0) / 1000); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; }

function miniSvgOpen(mi, extra = "") {
  return `<svg class="minimap" viewBox="0 0 1000 1000" ${extra}>
    <rect width="1000" height="1000" fill="#0b0f1c"/>
    ${mi?.mini ? `<image href="${mi.mini}" x="0" y="0" width="1000" height="1000" opacity=".9"/>` : ""}`;
}
function agentDot(agent, side, x, y, r = 26, dim = false) {
  const id = "c" + Math.random().toString(36).slice(2, 8);
  return `<g opacity="${dim ? 0.35 : 1}"><defs><clipPath id="${id}"><circle cx="${x}" cy="${y}" r="${r - 3}"/></clipPath></defs>
    <circle cx="${x}" cy="${y}" r="${r}" fill="#0e1220" stroke="${SIDE_COLOR[side]}" stroke-width="5"/>
    <image href="${agentIcon(agent) || ""}" x="${x - r + 3}" y="${y - r + 3}" width="${(r - 3) * 2}" height="${(r - 3) * 2}" clip-path="url(#${id})"/></g>`;
}
function skull(x, y, col) {
  return `<g transform="translate(${x},${y})"><circle r="15" fill="${col}" opacity=".9"/>
    <path d="M-7 -7 L7 7 M7 -7 L-7 7" stroke="#0e1220" stroke-width="4" stroke-linecap="round"/></g>`;
}

function mountReplay(box, d) {
  const R = d.replay, mi = mapInfo(d.map);
  if (!R || !mi || mi.xm === undefined) {
    box.innerHTML = `<div class="faint">這場沒有位置資料（舊版同步的對局，或地圖資料還沒載入）。重新同步後就會有。</div>`;
    return;
  }
  const rounds = R.rounds.length || Math.max(...R.kills.map((k) => k.r)) + 1;
  const st = { r: 0, i: 0, timer: null, mode: "round" };
  const killsOf = (r) => R.kills.filter((k) => k.r === r);
  const P = (xy) => { const v = toMini(mi, xy); return v ? [v[0] * 1000, v[1] * 1000] : null; };

  function draw() {
    let svg = miniSvgOpen(mi);
    let list = "";
    if (st.mode === "all") {
      for (const k of R.kills) {
        if (k.ks === "me") { const v = P(k.vxy); if (v) svg += `<circle cx="${v[0]}" cy="${v[1]}" r="11" fill="#4fe3b5" stroke="#0e1220" stroke-width="3"/>`; }
        if (k.vs === "me") { const v = P(k.vxy); if (v) svg += skull(v[0], v[1], "#ff6b81"); }
      }
      list = `<div class="muted">🟢 你的擊殺位置　❌ 你陣亡的位置</div>`;
    } else {
      const ks = killsOf(st.r);
      const cur = ks[Math.min(st.i, ks.length - 1)];
      const plant = R.plants.find((p) => p[0] === st.r);
      if (plant) { const v = P([plant[1], plant[2]]); if (v) svg += `<text x="${v[0]}" y="${v[1] + 14}" font-size="40" text-anchor="middle">💣</text>`; }
      ks.slice(0, st.i).forEach((k) => { const v = P(k.vxy); if (v) svg += skull(v[0], v[1], SIDE_COLOR[k.vs]); });
      if (cur) {
        const kv = P(cur.kxy), vv = P(cur.vxy);
        for (const [pi, x, y] of cur.pos) {
          const v = P([x, y]);
          if (v && pi !== cur.v) svg += agentDot(R.players[pi]?.agent, R.players[pi]?.side, v[0], v[1], pi === cur.k ? 32 : 24);
        }
        if (kv && vv) svg += `<line x1="${kv[0]}" y1="${kv[1]}" x2="${vv[0]}" y2="${vv[1]}" stroke="#fff" stroke-width="5" stroke-dasharray="14 10" opacity=".9"/>`;
        if (vv) svg += agentDot(R.players[cur.v]?.agent, cur.vs, vv[0], vv[1], 24, true) + skull(vv[0], vv[1] - 30, SIDE_COLOR[cur.vs]);
      }
      const who = (side, idx) => side === "me" ? "<b style='color:var(--sun)'>你</b>" : `${side === "ally" ? "隊友" : "敵方"} ${esc(agentName(R.players[idx]?.agent))}`;
      list = ks.map((k, j) => `<div class="kl ${j === st.i ? "on" : ""}" data-i="${j}">
        <span class="faint">${mmss(k.t)}</span> ${who(k.ks, k.k)} <span class="faint">→</span> ${who(k.vs, k.v)}
        <span class="faint" style="font-size:11px">${esc(weaponName(k.w))}</span></div>`).join("") || `<div class="faint">這回合沒有擊殺資料</div>`;
    }
    svg += "</svg>";
    box.querySelector(".rp-map").innerHTML = svg;
    box.querySelector(".rp-list").innerHTML = list;
    box.querySelectorAll(".rp-rounds button").forEach((b) => b.classList.toggle("on", st.mode === "round" && +b.dataset.r === st.r));
    box.querySelector(".rp-all").classList.toggle("on", st.mode === "all");
    box.querySelectorAll(".kl").forEach((el) => el.onclick = () => { stop(); st.i = +el.dataset.i; draw(); });
  }
  function stop() { clearInterval(st.timer); st.timer = null; box.querySelector(".rp-play").textContent = "▶ 播放"; }
  function play() {
    if (st.timer) return stop();
    st.mode = "round";
    box.querySelector(".rp-play").textContent = "⏸ 暫停";
    st.timer = setInterval(() => {
      if (!box.isConnected) return stop();
      const n = killsOf(st.r).length;
      if (st.i < n - 1) st.i++;
      else if (st.r < rounds - 1) { st.r++; st.i = 0; }
      else return stop();
      draw();
    }, 1100);
  }
  box.innerHTML = `
    <div class="rp-rounds">${Array.from({ length: rounds }, (_, r) => `<button data-r="${r}" class="${R.rounds[r] ? "w" : "l"}">${r + 1}</button>`).join("")}
      <button class="rp-all">全場</button></div>
    <div class="rp-body"><div class="rp-map"></div>
      <div class="rp-side"><div class="row" style="margin-bottom:8px">
        <button class="btn ghost rp-prev">◀</button><button class="btn rp-play">▶ 播放</button><button class="btn ghost rp-next">▶</button></div>
        <div class="faint" style="font-size:12px;margin-bottom:6px">🟡 你　🟢 隊友　🔴 敵方　虛線 = 擊殺</div>
        <div class="rp-list"></div></div></div>`;
  box.querySelectorAll(".rp-rounds button[data-r]").forEach((b) => b.onclick = () => { stop(); st.mode = "round"; st.r = +b.dataset.r; st.i = 0; draw(); });
  box.querySelector(".rp-all").onclick = () => { stop(); st.mode = "all"; draw(); };
  box.querySelector(".rp-play").onclick = play;
  box.querySelector(".rp-prev").onclick = () => { stop(); st.mode = "round"; if (st.i > 0) st.i--; else if (st.r > 0) { st.r--; st.i = Math.max(0, killsOf(st.r).length - 1); } draw(); };
  box.querySelector(".rp-next").onclick = () => { stop(); st.mode = "round"; if (st.i < killsOf(st.r).length - 1) st.i++; else if (st.r < rounds - 1) { st.r++; st.i = 0; } draw(); };
  draw();
}

/* ================= 超酷功能 2：地圖熱點 ================= */
async function openHeat(mapId) {
  const mi = mapInfo(mapId);
  const wrap = document.createElement("div");
  wrap.className = "modal";
  wrap.innerHTML = `<div class="box">${loading("計算熱點…")}</div>`;
  wrap.onclick = (ev) => { if (ev.target === wrap) wrap.remove(); };
  document.body.appendChild(wrap);
  const h = await api(`/api/heat?map=${encodeURIComponent(mapId)}`);
  const st = { show: "deaths", side: "all" };
  const box = wrap.querySelector(".box");
  function draw() {
    const pts = h[st.show].filter((p) => st.side === "all" || p[2] === st.side);
    const col = st.show === "kills" ? "79,227,181" : "255,107,129";
    let svg = miniSvgOpen(mi) + `<defs><radialGradient id="hg"><stop offset="0" stop-color="rgb(${col})" stop-opacity=".55"/><stop offset="1" stop-color="rgb(${col})" stop-opacity="0"/></radialGradient></defs>`;
    for (const p of pts) { const v = toMini(mi, p); if (v) svg += `<circle cx="${v[0] * 1000}" cy="${v[1] * 1000}" r="55" fill="url(#hg)"/>`; }
    for (const p of pts) { const v = toMini(mi, p); if (v) svg += `<circle cx="${v[0] * 1000}" cy="${v[1] * 1000}" r="6" fill="rgb(${col})"/>`; }
    svg += "</svg>";
    box.innerHTML = `<button class="close">✕</button>
      <h2 style="margin:0 0 4px">🔥 ${esc(mapName(mapId))} 熱點圖</h2>
      <div class="muted" style="margin-bottom:12px">${h.games} 場 · 越紅/越綠的地方代表越常發生</div>
      <div class="row" style="margin-bottom:12px">
        <div class="chips"><button class="chip ${st.show === "deaths" ? "on" : ""}" data-s="deaths">❌ 我常死在哪（${h.deaths.length}）</button>
          <button class="chip ${st.show === "kills" ? "on" : ""}" data-s="kills">🟢 我常在哪殺人（${h.kills.length}）</button></div>
        <div class="chips"><button class="chip ${st.side === "all" ? "on" : ""}" data-d="all">全部</button>
          <button class="chip ${st.side === "atk" ? "on" : ""}" data-d="atk">進攻</button><button class="chip ${st.side === "def" ? "on" : ""}" data-d="def">防守</button></div></div>
      <div class="heatmap-wrap">${mi?.xm !== undefined ? svg : `<div class="faint">這張地圖沒有座標資料。</div>`}</div>
      <div class="faint" style="margin-top:8px;font-size:12px">小提醒：常死的熱點就是對手最會架的位置，下次換個路線或先丟技能清點。</div>`;
    box.querySelector(".close").onclick = () => wrap.remove();
    box.querySelectorAll("[data-s]").forEach((b) => b.onclick = () => { st.show = b.dataset.s; draw(); });
    box.querySelectorAll("[data-d]").forEach((b) => b.onclick = () => { st.side = b.dataset.d; draw(); });
  }
  draw();
}

/* ================= 超酷功能 3：我的回顧（可存成圖片） ================= */
function recapSlides(st) {
  const o = st.overall, e = st.extra;
  const topA = st.agents[0], topM = [...st.maps].filter((m) => m.games >= 2).sort((a, b) => (b.winrate || 0) - (a.winrate || 0))[0];
  const w = st.weapons[0];
  let bestHour = null, max = -1;
  st.heat.forEach((row) => row.forEach(([g], h) => { if (g > max) { max = g; bestHour = h; } }));
  const owl = bestHour === null ? "" : bestHour >= 22 || bestHour < 4 ? "🦉 夜貓子玩家" : bestHour < 12 ? "🐓 早起鳥玩家" : bestHour < 18 ? "☀️ 午後玩家" : "🌆 下班後玩家";
  const portrait = (id) => A.agents[id]?.portrait || agentIcon(id);
  const slides = [
    { bg: "linear-gradient(135deg,#ff4f64,#a98bff)", html: `<div class="rc-kicker">VAL 小戰績 · 我的回顧</div><div class="rc-big">${esc(st.me.name || "我")}</div>
      <div class="rc-mid">最近 ${o.games} 場 · ${e.playtime_h} 小時</div><div class="rc-sub">${owl}</div>` },
    topA && { bg: "linear-gradient(135deg,#1a2137,#3a2a6e)", img: portrait(topA.agent), html: `<div class="rc-kicker">你的本命特務</div>
      <div class="rc-big">${esc(agentName(topA.agent))}</div><div class="rc-mid">${topA.games} 場 · 勝率 ${fmt(topA.winrate, "%")}</div><div class="rc-sub">K/D ${fmt(topA.kd)} · ACS ${fmt(topA.acs)}</div>` },
    { bg: "linear-gradient(135deg,#0f6e5a,#1a2137)", html: `<div class="rc-kicker">你的戰鬥數據</div>
      <div class="rc-grid"><div><b>${fmt(o.kd)}</b><span>K/D</span></div><div><b>${fmt(o.hs, "%")}</b><span>爆頭率</span></div>
      <div><b>${fmt(o.adr)}</b><span>ADR</span></div><div><b>${fmt(o.kast, "%")}</b><span>KAST</span></div>
      <div><b>${o.k}</b><span>總擊殺</span></div><div><b>${fmt(o.winrate, "%")}</b><span>勝率</span></div></div>` },
    { bg: "linear-gradient(135deg,#ffb347,#ff4f64)", html: `<div class="rc-kicker">高光時刻</div>
      <div class="rc-grid"><div><b>${e.multi["5"] || 0}</b><span>ACE</span></div><div><b>${e.multi["4"] || 0}</b><span>4 殺</span></div>
      <div><b>${e.clutch.total_won}</b><span>殘局勝利</span></div><div><b>${e.mvps}</b><span>全場 MVP</span></div>
      <div><b>${e.fk}</b><span>首殺</span></div><div><b>${st.best_streak}</b><span>最長連勝</span></div></div>` },
    topM && { bg: "linear-gradient(135deg,#1a2137,#235a8c)", img: mapInfo(topM.map)?.splash, cover: true, html: `<div class="rc-kicker">你的主場</div>
      <div class="rc-big">${esc(mapName(topM.map))}</div><div class="rc-mid">勝率 ${fmt(topM.winrate, "%")} · ${topM.games} 場</div>` },
    w && { bg: "linear-gradient(135deg,#2a2050,#1a2137)", img: A.weapons[w.weapon]?.icon, contain: true, html: `<div class="rc-kicker">最愛的武器</div>
      <div class="rc-big">${esc(weaponName(w.weapon))}</div><div class="rc-mid">${w.kills} 殺 · 佔 ${w.share}%</div>` },
    { bg: "linear-gradient(135deg,#a98bff,#4fe3b5)", html: `<div class="rc-kicker">啾啾的評語</div><div class="rc-quote">「${esc(mascotLine(st).text)}」</div>
      <div class="rc-sub">${st.badges.filter((b) => b.count).map((b) => BADGE_EMOJI[b.id]).join(" ")}</div>`, mascot: true },
  ].filter(Boolean);
  return slides;
}
async function pageRecap(el) {
  const st = await getStats();
  if (st.empty || !st.overall.games) { el.innerHTML = noData(); return; }
  const slides = recapSlides(st);
  let i = 0;
  el.innerHTML = `<div class="topbar"><h2>我的回顧</h2><span class="faint">像年度回顧一樣，把你的戰績做成卡片</span><div class="sp"></div>${queueChips(st)}</div>
    <div class="recap-stage"><button class="rc-nav prev">‹</button><div class="recap" id="recapCard"></div><button class="rc-nav next">›</button></div>
    <div class="row" style="justify-content:center;margin-top:14px"><div class="rc-dots"></div>
      <button class="btn" id="rcSave">📸 存成圖片</button><button class="btn ghost" id="rcAll">🖼️ 全部存成一張</button></div>`;
  bindQueue();
  const card = $("#recapCard", el);
  const slideHtml = (sl) => `<div class="rc-in" style="background:${sl.bg}">
      ${sl.img ? `<img class="rc-img ${sl.cover ? "cover" : ""} ${sl.contain ? "contain" : ""}" src="${sl.img}" crossorigin="anonymous" alt="">` : ""}
      <div class="rc-text">${sl.html}</div>${sl.mascot ? `<div class="rc-mascot">${mascot()}</div>` : ""}
      <div class="rc-foot">${mascot("tiny")} VAL 小戰績</div></div>`;
  const show = () => {
    card.innerHTML = slideHtml(slides[i]);
    $(".rc-dots", el).innerHTML = slides.map((_, j) => `<span class="${j === i ? "on" : ""}"></span>`).join("");
  };
  $(".prev", el).onclick = () => { i = (i - 1 + slides.length) % slides.length; show(); };
  $(".next", el).onclick = () => { i = (i + 1) % slides.length; show(); };
  const save = async (node) => {
    try {
      if (!window.html2canvas) await new Promise((ok, bad) => {
        const sc = document.createElement("script");
        sc.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
        sc.onload = ok; sc.onerror = () => bad(new Error("載入截圖工具失敗，請確認網路"));
        document.head.appendChild(sc);
      });
      const canvas = await window.html2canvas(node, { backgroundColor: "#0e1220", useCORS: true, scale: 2 });
      const r = await api("/api/save-image", { data: canvas.toDataURL("image/png") });
      toast("已存到：" + r.path, 4000);
    } catch (e) { toast("存圖失敗：" + e.message, 4000); }
  };
  $("#rcSave", el).onclick = () => save(card);
  $("#rcAll", el).onclick = async () => {
    const strip = document.createElement("div");
    strip.className = "recap-strip";
    strip.innerHTML = slides.map((sl) => `<div class="recap">${slideHtml(sl)}</div>`).join("");
    document.body.appendChild(strip);
    await save(strip);
    strip.remove();
  };
  document.onkeydown = (ev) => {
    if (!el.isConnected) return;
    if (ev.key === "ArrowRight") $(".next", el).click();
    if (ev.key === "ArrowLeft") $(".prev", el).click();
  };
  show();
}

/* ================= 打完自動同步的通知 ================= */
function matchPopup(ev) {
  const old = document.querySelector(".matchpop");
  if (old) old.remove();
  const res = ev.won === true ? "勝利" : ev.won === false ? "落敗" : "平手";
  const el = document.createElement("div");
  el.className = `matchpop ${ev.won ? "w" : ev.won === false ? "l" : ""}`;
  el.innerHTML = `${agentImg(ev.agent, "av")}<div style="flex:1"><div class="faint" style="font-size:12px">比賽結束 · ${esc(mapName(ev.map))} · 已自動同步</div>
    <div style="font-size:18px;font-weight:700"><span class="${ev.won ? "win" : ev.won === false ? "loss" : "draw"}">${res}</span>
    ${ev.k}/${ev.d}/${ev.a} · ACS ${fmt(ev.acs)}${ev.rr != null ? ` · <span class="${ev.rr >= 0 ? "win" : "loss"}">${ev.rr >= 0 ? "+" : ""}${ev.rr} RR</span>` : ""}</div></div>
    ${mascot("small", ev.won ? "wow" : ev.won === false ? "sad" : "happy")}<button class="x">✕</button>`;
  el.querySelector(".x").onclick = () => el.remove();
  el.onclick = (e) => { if (e.target.className !== "x") { location.hash = "#/matches"; el.remove(); openMatch(ev.id); } };
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 15000);
}
async function pollEvents() {
  try {
    const evs = await api(`/api/events?since=${S.evId}`);
    for (const ev of evs) {
      S.evId = Math.max(S.evId, ev.id);
      if (ev.kind === "match_end") {
        S.stats = null;
        matchPopup(ev);
        refreshStatus();
        if (/^#\/(overview|matches|agents|habits|recap)?$/.test(location.hash || "#/")) route();
      } else if (ev.kind === "progress") {
        if (ev.sub === "level_up") levelUpBox(ev);
        else if (ev.sub === "unlock") toast(`🎁 解鎖新東西了！到「角色房間」看看`, 5000);
        else if (ev.sub === "bond_up") toast(`💞 親密度升級：${ev.stage}`, 5000);
        else if (ev.sub === "backfill") toast(`已把以前的 ${ev.matches} 場算進養成，現在 Lv.${ev.level} 🎉`, 6000);
      } else if (ev.kind === "game_open") {
        toast("偵測到特戰英豪已開啟 🎮");
        refreshStatus();
      }
    }
  } catch { /* ignore */ }
}

/* ================= 檢查更新 ================= */
async function checkUpdate(silent = true) {
  if (!S.status?.settings?.update_repo) {
    if (!silent) toast("還沒設定更新來源");
    return null;
  }
  try {
    const r = await api("/api/update/check", {});
    S.update = r;
    renderSource();
    if (!silent) toast(r.available ? `有新版本 ${r.latest}！` : `已經是最新版（${r.current}）`);
    return r;
  } catch (e) { if (!silent) toast("檢查更新失敗：" + e.message, 4000); return null; }
}
async function applyUpdate() {
  if (!confirm(`要更新到 ${S.update?.latest || "最新版"} 嗎？更新完要重新開 App。`)) return;
  try {
    const r = await api("/api/update/apply", {});
    alertBox(`更新完成（${r.version}，${r.updated} 個檔案）🎉<br>請關掉 App 視窗，再重新打開就是新版本了。`);
  } catch (e) { toast("更新失敗：" + e.message, 5000); }
}
function alertBox(html) {
  const wrap = document.createElement("div");
  wrap.className = "modal";
  wrap.innerHTML = `<div class="box" style="max-width:440px;text-align:center">${mascot()}<p style="font-size:15px">${html}</p><button class="btn">好</button></div>`;
  wrap.querySelector(".btn").onclick = () => wrap.remove();
  document.body.appendChild(wrap);
}


/* ================= 角色房間（陪伴角色養成） ================= */
const MOODS = [["happy", "平常"], ["wow", "驚喜"], ["sad", "難過"], ["cheer", "加油"]];
const VOICE_LIST = [["zh-TW-HsiaoYuNeural", "曉雨（台灣・活潑）"], ["zh-TW-HsiaoChenNeural", "曉臻（台灣・溫柔）"],
  ["zh-CN-XiaoyiNeural", "曉伊（可愛）"], ["zh-CN-XiaoxiaoNeural", "曉曉（自然）"], ["zh-TW-YunJheNeural", "雲哲（台灣・男聲）"]];
const MEM_TEXT = { ace: "打出 ACE 🌟", clutch: "贏下殘局 👑", k4: "打出 4 殺 💥", mvp: "拿下全場 MVP 🏆" };

function customSrcOf(sk, mood) {
  if (!sk.char) return null;
  const pack = (sk.outfits || []).find((o) => o.name === sk.outfit);
  const files = pack ? pack.files.map((f) => pack.name + "/" + f) : (sk.files || []);
  const f = window.pickMoodFile(files, mood);
  return f ? "/custom-buddy/" + [sk.char, ...f.split("/")].map(encodeURIComponent).join("/") : null;
}

async function pageRoom(el, keep = {}) {
  const [pr, sk] = await Promise.all([api("/api/progress"), api("/api/buddy/skin")]);
  const cfg = S.status?.settings || {};
  const skinId = pr.skin, mood = keep.mood || "happy";
  const isCustom = String(skinId).startsWith("custom:");
  const P = isCustom ? (await api("/api/persona")) : null;
  const VL = await api("/api/voices").catch(() => ({ voices: [], sovits: {} }));
  const bond = pr.current_bond;
  const bondPct = bond.next ? Math.round(((bond.points - bond.base) / (bond.next - bond.base)) * 100) : 100;
  const stage = () => window.renderBuddy(skinId, mood, pr.equipped, { customSrc: customSrcOf(sk, mood), adjust: sk.adjust });
  const itemCard = (it) => {
    const on = pr.equipped.includes(it.id);
    return `<button class="item ${it.unlocked ? "" : "locked"} ${on ? "on" : ""}" data-item="${it.id}" title="${esc(it.cond)}">
      <div class="item-art">${window.accessoryIcon(it.id)}</div><b>${esc(it.name)}</b>
      ${it.unlocked ? `<small>${on ? "✓ 穿戴中" : "點一下穿上"}</small>`
        : `<small>🔒 ${esc(it.cond)}</small><div class="hbar" style="margin-top:4px"><i style="width:${Math.round((it.have / it.need) * 100)}%"></i></div>`}</button>`;
  };
  const adjRows = isCustom ? pr.equipped.map((id) => {
    const a = (pr.adjust[skinId] || {})[id] || { x: 0, y: 0, s: 1 };
    return `<div class="adj" data-adj="${id}"><b>${esc(window.ACCESSORY_NAMES[id] || id)}</b>
      <label>左右<input type="range" min="-60" max="60" step="1" value="${a.x}" data-k="x"></label>
      <label>上下<input type="range" min="-60" max="60" step="1" value="${a.y}" data-k="y"></label>
      <label>大小<input type="range" min="0.3" max="3" step="0.05" value="${a.s}" data-k="s"></label></div>`;
  }).join("") : "";

  el.innerHTML = `
    <div class="topbar"><h2>角色房間</h2><span class="faint">一起打越多場，角色越強、越懂你</span></div>
    <div class="room-top">
      <div class="room-stage"><div class="room-bot" id="roomBot">${stage()}</div>
        <div class="chips" style="justify-content:center">${MOODS.map(([m, t]) => `<button class="chip ${m === mood ? "on" : ""}" data-mood="${m}">${t}</button>`).join("")}</div></div>
      <div class="room-info">
        <div class="row"><div class="lvbig">Lv.<b>${pr.level}</b></div>
          <div style="flex:1"><div class="muted" style="font-size:12px">經驗值 ${pr.xp} / ${pr.xp_next || "MAX"}　·　累計 ${pr.total_xp} XP　·　${pr.counters.games} 場</div>
          <div class="xpbar"><i style="width:${pr.xp_next ? Math.round((pr.xp / pr.xp_next) * 100) : 100}%"></i></div></div></div>
        <div class="row" style="margin-top:14px"><div class="bondic">💞</div>
          <div style="flex:1"><div class="muted" style="font-size:12px">和「${esc(isCustom ? (sk.custom_name || "自訂角色") : "啾啾")}」的親密度：<b style="color:var(--peach)">${esc(bond.name)}</b>
            ${bond.next ? `（${bond.points} / ${bond.next}）` : "（已經是最高階段！）"}</div>
          <div class="xpbar bond"><i style="width:${bondPct}%"></i></div>
          <div class="faint" style="font-size:11px;margin-top:4px">${pr.stages.map((st, i) => `<span class="${i <= bond.index ? "win" : ""}">${st.name}</span>`).join(" → ")}</div></div></div>
        <div class="field" style="margin-top:16px"><label>角色要怎麼叫你</label>
          <div class="row"><input id="rNick" value="${esc(pr.nickname)}" maxlength="20" style="flex:1"><button class="btn" id="rNickSave">儲存</button></div>
          <small>預設是你的遊戲名字，想改就改。</small></div>
        <div class="muted" style="font-size:12px;margin:4px 0 6px">選角色</div>
        <div class="charpick">${[["jiujiu", "啾啾", null], ...sk.characters.map((c) => ["custom:" + c.id, c.name, c])].map(([id, name, c]) => `<button class="charbtn ${id === skinId ? "on" : ""}" data-skin="${esc(id)}">
            <div class="charart">${c ? (c.cover ? `<img src="/custom-buddy/${encodeURIComponent(c.id)}/${encodeURIComponent(c.cover)}">` : "🖼️") : window.SKINS.jiujiu.svg("happy")}</div><span>${esc(name)}</span></button>`).join("")}
          <button class="charbtn" id="rNewChar"><div class="charart">➕</div><span>新增角色</span></button></div>
      </div>
    </div>

    ${isCustom ? personaCard(P) : ""}
    ${isCustom ? `<div class="card section"><h3>🎭 表情欄位 <span class="hint">點「上傳」選圖片，自動存好；背景透明的 PNG／動態 WebP／GIF 最好看</span></h3>
      <div class="slots">${sk.moods.map((m) => {
        const file = (sk.files || []).find((f) => f.replace(/\.[^.]+$/, "").toLowerCase() === m.id);
        const locked = sk.bond < m.need;
        return `<div class="slot ${locked ? "locked" : ""}">
          <div class="slot-art">${file ? `<img src="/custom-buddy/${encodeURIComponent(sk.char)}/${encodeURIComponent(file)}?t=${Date.now()}" alt="">` : `<span class="faint">${m.need ? "專屬" : "空"}</span>`}</div>
          <b>${esc(m.name)}</b>
          <small>${m.need ? (locked ? `🔒 親密度「${esc(pr.stages[m.need].name)}」解鎖（可以先放圖）` : "✨ 已解鎖") : "基本表情"}</small>
          <div class="row" style="justify-content:center;gap:6px">
            <label class="btn ghost small">上傳<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" data-up="${m.id}" hidden></label>
            ${file ? `<button class="btn ghost small" data-rm="${m.id}">移除</button>` : ""}</div></div>`;
      }).join("")}</div>
      <div class="faint" style="font-size:12px;margin-top:8px">專屬欄位沒放圖的話，會用最接近的基本表情代替。</div></div>` : ""}

    <div class="card section"><h3>👗 衣櫃 <span class="hint">同一個位置只能戴一個；換角色時配件各自記住</span></h3>
      <div class="items">${pr.items.map(itemCard).join("")}</div>
      ${isCustom && pr.equipped.length ? `<h4 style="margin:16px 0 6px">把配件對到你的圖片上</h4><div class="adjs">${adjRows}</div>` : ""}
    </div>

    ${isCustom ? `<div class="card section"><h3>🎽 自訂造型包</h3>
      <p class="muted" style="margin-top:0;font-size:13px">在自訂圖片資料夾裡建立子資料夾，一個資料夾就是一套造型，裡面放 happy.png、wow.png、sad.png、cheer.png。
        資料夾取名 <b>Lv10</b> 就是等級 10 解鎖，取名 <b>ACE</b> 就是打出 ACE 解鎖，其他名字直接可以穿。</p>
      <div class="chips"><button class="chip ${!pr.outfit ? "on" : ""}" data-outfit="">基本造型</button>
        ${pr.outfits.map((o) => `<button class="chip ${o.name === pr.outfit ? "on" : ""} ${o.unlocked ? "" : "lockedchip"}" data-outfit="${esc(o.name)}" ${o.unlocked ? "" : "disabled"}>${o.unlocked ? "" : "🔒 "}${esc(o.name)}${o.unlocked ? "" : `（${esc(o.cond)}）`}</button>`).join("")}</div>
      <button class="btn ghost" id="rFolder" style="margin-top:10px">📂 打開這個角色的資料夾</button>
      <button class="btn ghost" id="rDelChar" style="margin:10px 0 0 6px;color:var(--loss)">🗑 刪除這個角色</button></div>` : ""}

    <div class="grid g2 section">
      <div class="card"><h3>💬 對話框</h3>
        <div class="frames">${pr.frames.map((f) => `<button class="frame-btn ${f.id === pr.frame ? "on" : ""} ${f.unlocked ? "" : "locked"}" data-frame="${f.id}" ${f.unlocked ? "" : "disabled"}>
          <span class="bubble-mini f-${f.id}">嗨～</span><small>${f.unlocked ? esc(f.name) : "🔒 " + esc(f.cond)}</small></button>`).join("")}</div></div>
      <div class="card"><h3>🔊 語音</h3>
        <label class="switch"><input type="checkbox" id="vOn" ${cfg.voice_enabled !== false ? "checked" : ""}><span></span><div><b>角色說話時念出來</b></div></label>
        <div class="faint" style="font-size:12px;margin:8px 0 4px">預設聲音（啾啾和沒有設定專屬聲音的角色都用這個）</div>
        <div class="row" style="margin:0 0 10px">${voiceSelect("vPick", VL.voices, false)}</div>
        <label class="slider">語速 <input type="range" id="vRate" min="-30" max="50" value="${cfg.voice_rate ?? 5}"><span></span></label>
        <label class="slider">音調 <input type="range" id="vPitch" min="-20" max="40" value="${cfg.voice_pitch ?? 10}"><span></span></label>
        <label class="slider">音量 <input type="range" id="vVol" min="0" max="100" value="${cfg.voice_volume ?? 70}"><span></span></label>
        ${isCustom ? `<h4 style="margin:14px 0 6px">${esc(sk.custom_name || "這個角色")}的專屬聲音</h4>
        <div class="row" style="margin:0 0 8px">${voiceSelect("cvPick", VL.voices, true)}</div>
        <div id="cvSliders"><label class="slider">語速 <input type="range" id="cvRate" min="-30" max="50" value="${P.persona.voice?.rate ?? 0}"><span></span></label>
        <label class="slider">音調 <input type="range" id="cvPitch" min="-20" max="40" value="${P.persona.voice?.pitch ?? 0}"><span></span></label></div>` : ""}
        <div class="row" style="margin-top:8px"><button class="btn" id="vSave">儲存</button><button class="btn ghost" id="vTest">▶ 試聽</button></div>
        <div class="faint" style="font-size:12px;margin-top:6px">失敗時會自動退回：我的聲音 → Edge 神經語音 → Windows 內建語音。俄文一律用俄文語音念。音調只對 Edge 語音有效。</div></div>
    </div>

    <div class="card section"><h3>🎙️ 我的聲音（聲音複製） <span class="hint">用你自己的聲音念角色的台詞</span></h3>
      <p class="muted" style="margin-top:0;font-size:13px">只能放你自己、或本人明確同意的聲音（例如問過爸媽）。不要放聲優、藝人或其他人的聲音。聲音只存在你的電腦，不會上傳。</p>
      <div class="grid g2">
        <div><h4 style="margin:0 0 6px">① GPT-SoVITS 位置</h4>
          <div class="row"><input id="svDir" class="inp" style="flex:1" placeholder="例如 D:\\GPT-SoVITS-v4-20250422fix" value="${esc(cfg.sovits_dir || "")}"><button class="btn ghost" id="svSave">儲存</button></div>
          <div id="svStat" class="faint" style="font-size:13px;margin-top:6px"></div>
          <div class="row" style="margin-top:6px"><button class="btn ghost" id="svStart">啟動</button><button class="btn ghost" id="svStop">停止</button></div></div>
        <div><h4 style="margin:0 0 6px">② 新增一段錄音（5～10 秒）</h4>
          <div class="row"><input id="nvName" class="inp" placeholder="名字，例如：我" style="width:120px">
            <select id="nvLang" class="sel"><option value="zh">中文</option><option value="en">英文</option><option value="ja">日文</option><option value="yue">粵語</option></select></div>
          <textarea id="nvText" class="inp" rows="2" style="width:100%;margin-top:6px" placeholder="錄音裡講的每一個字（一字不差，標點也打上）"></textarea>
          <div class="row" style="margin-top:6px"><input type="file" id="nvFile" accept=".wav,.mp3,.m4a,.flac,.ogg,audio/*"><button class="btn" id="nvAdd">加入</button></div></div>
      </div>
      <h4 style="margin:14px 0 6px">聲音庫</h4>
      ${VL.voices.length ? `<table><tbody>${VL.voices.map((v) => `<tr><td><b>${esc(v.name)}</b>${v.seconds ? ` <span class="faint">${v.seconds} 秒${v.seconds < 3 || v.seconds > 10 ? "（建議 3～10 秒）" : ""}</span>` : ""}
        <div class="faint" style="font-size:12px">「${esc(v.text)}」</div></td>
        <td class="r"><button class="btn ghost small" data-vtest="${v.id}">▶ 試聽</button> <button class="btn ghost small" data-vdel="${v.id}" style="color:var(--loss)">刪除</button></td></tr>`).join("")}</tbody></table>`
        : `<div class="faint">還沒有錄音。用手機或電腦錄一段 5～10 秒、安靜環境、正常語氣的話，再打上逐字稿就好。</div>`}
    </div>

    <div class="grid g2 section">
      <div class="card"><h3>📖 回憶簿 <span class="hint">你們一起經歷的高光時刻</span></h3>
        ${pr.memories.length ? `<div class="mems">${pr.memories.slice(0, 20).map((m) => `<div class="mem">${agentImg(m.agent, "av sm")}<div>
          <b>${MEM_TEXT[m.kind] || "高光時刻"}${m.kind === "clutch" && m.vs ? `（1v${m.vs}）` : ""}</b>
          <div class="faint" style="font-size:12px">${esc(mapName(m.map))} · ${esc(agentName(m.agent))} · ${m.k}/${m.d}/${m.a} · ${m.t ? new Date(m.t).toLocaleDateString("zh-TW") : ""}</div></div></div>`).join("")}</div>`
          : `<div class="faint">還沒有回憶。打出 ACE、4 殺、殘局或全場 MVP 就會記下來。</div>`}</div>
      <div class="card"><h3>✨ 經驗值怎麼拿</h3>
        <table><tbody>${pr.rules.map(([, t, v]) => `<tr><td>${esc(t)}</td><td class="r num win">+${v}</td></tr>`).join("")}</tbody></table>
        <div class="faint" style="font-size:12px;margin-top:8px">輸了也有經驗，不會扣。親密度：目前的角色陪你打一場 +10，贏了 +5，ACE 再 +5。</div></div>
    </div>`;

  const rerender = (k = {}) => pageRoom(el, { mood, ...k });
  el.querySelectorAll("[data-mood]").forEach((b) => b.onclick = () => rerender({ mood: b.dataset.mood }));
  el.querySelectorAll("[data-skin]").forEach((b) => b.onclick = async () => { await api("/api/settings", { buddy_skin: b.dataset.skin }); await refreshStatus(); rerender(); });
  el.querySelectorAll("[data-item]").forEach((b) => b.onclick = async () => {
    const it = pr.items.find((x) => x.id === b.dataset.item);
    if (!it.unlocked) return toast(`🔒 還沒解鎖：${it.cond}`);
    await api("/api/progress/equip", { skin: skinId, item: it.id, on: !pr.equipped.includes(it.id) });
    rerender();
  });
  el.querySelectorAll("[data-up]").forEach((inp) => inp.onchange = () => {
    const file = inp.files[0];
    if (!file) return;
    const rd = new FileReader();
    rd.onload = async () => {
      try { await api("/api/buddy/upload", { mood: inp.dataset.up, name: file.name, data: rd.result }); toast("已放進表情欄位 ✓"); rerender(); }
      catch (e) { toast("上傳失敗：" + e.message, 4000); }
    };
    rd.readAsDataURL(file);
  });
  $("#rNewChar", el).onclick = async () => {
    const name = prompt("新角色的名字？", "");
    if (!name) return;
    await api("/api/characters/create", { name });
    await refreshStatus();
    toast(`已新增「${name}」，去上傳表情圖吧 ✓`);
    rerender();
  };
  if (isCustom) bindPersona(el, P, rerender);
  el.querySelectorAll("[data-rm]").forEach((b) => b.onclick = async () => { await api("/api/buddy/remove", { mood: b.dataset.rm }); rerender(); });
  el.querySelectorAll("[data-frame]").forEach((b) => b.onclick = async () => { await api("/api/progress/frame", { frame: b.dataset.frame }); rerender(); });
  el.querySelectorAll("[data-outfit]").forEach((b) => b.onclick = async () => {
    try { await api("/api/progress/outfit", { outfit: b.dataset.outfit }); rerender(); } catch (e) { toast(e.message); }
  });
  if ($("#rDelChar", el)) $("#rDelChar", el).onclick = async () => {
    if (!confirm(`確定刪除「${sk.custom_name || "這個角色"}」？圖片和角色設定都會刪掉（等級不會受影響）。`)) return;
    await api("/api/characters/delete", { id: sk.char });
    await refreshStatus();
    rerender();
  };
  if ($("#rFolder", el)) $("#rFolder", el).onclick = () => api("/api/open-folder", { which: "buddy" }).then((r) => toast("資料夾：" + r.path, 4000));
  $("#rNickSave", el).onclick = async () => { await api("/api/progress/nickname", { nickname: $("#rNick", el).value }); toast("角色記住你的名字了 💕"); };
  // 自訂圖片的配件位置：拉動就即時預覽，放開才存
  el.querySelectorAll("[data-adj]").forEach((row) => {
    const id = row.dataset.adj;
    const read = () => Object.fromEntries([...row.querySelectorAll("input")].map((i) => [i.dataset.k, +i.value]));
    row.querySelectorAll("input").forEach((inp) => {
      inp.oninput = () => {
        sk.adjust = { ...(sk.adjust || {}), [id]: read() };
        $("#roomBot", el).innerHTML = window.renderBuddy(skinId, mood, pr.equipped, { customSrc: customSrcOf(sk, mood), adjust: sk.adjust });
      };
      inp.onchange = () => { const v = read(); api("/api/progress/adjust", { skin: skinId, item: id, ...v }); };
    });
  });
  // 語音
  const pickVal = (sel) => { const [engine, ...rest] = $(sel, el).value.split(":"); const v = rest.join(":");
    return { engine, name: engine === "edge" ? v : "", clone: engine === "clone" ? v : "" }; };
  $("#vPick", el).value = cfg.voice_engine === "clone" && cfg.voice_clone ? "clone:" + cfg.voice_clone
    : cfg.voice_engine === "windows" ? "windows" : "edge:" + (cfg.voice_name || VOICE_LIST[0][0]);
  if (!$("#vPick", el).value) $("#vPick", el).value = "edge:" + VOICE_LIST[0][0];
  if (isCustom) {
    const cv = P.persona.voice || {};
    $("#cvPick", el).value = cv.engine === "clone" ? "clone:" + cv.clone : cv.engine === "edge" ? "edge:" + cv.name : cv.engine === "windows" ? "windows" : "default";
    if (!$("#cvPick", el).value) $("#cvPick", el).value = "default";
    const tog = () => { $("#cvSliders", el).style.display = $("#cvPick", el).value === "default" ? "none" : ""; };
    $("#cvPick", el).onchange = tog; tog();
  }
  el.querySelectorAll(".slider input").forEach((i) => { const sp = i.nextElementSibling; sp.textContent = i.value; i.oninput = () => { sp.textContent = i.value; }; });
  const saveVoice = async () => {
    const g = pickVal("#vPick");
    const patch = { voice_enabled: $("#vOn", el).checked, voice_engine: g.engine,
      voice_rate: +$("#vRate", el).value, voice_pitch: +$("#vPitch", el).value, voice_volume: +$("#vVol", el).value };
    if (g.engine === "edge") patch.voice_name = g.name;
    if (g.engine === "clone") patch.voice_clone = g.clone;
    await api("/api/settings", patch);
    if (isCustom) {
      const c = pickVal("#cvPick");
      P.persona.voice = { ...c, rate: +$("#cvRate", el).value, pitch: +$("#cvPitch", el).value };
      await api("/api/persona", { char: P.char, persona: { voice: P.persona.voice } });
    }
    await refreshStatus();
  };
  const ENG = { clone: "我的聲音", edge: "Edge 神經語音", windows: "Windows 內建語音" };
  const testVoice = async (btn, override) => {
    const t = btn.textContent; btn.disabled = true; btn.textContent = "念念中…";
    try {
      const r = await fetch("/api/voice/test", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `嗨，${pr.nickname || "你"}！今天也一起加油吧！`, voice: override }) }).then((x) => x.json());
      if (!r.engine) toast("語音失敗：" + (r.error || "未知原因"), 6000);
      else if (r.error) toast(r.error, 7000);
      else toast(`用${ENG[r.engine] || r.engine}念的 ✓`);
    } catch (e) { toast(e.message, 5000); }
    btn.disabled = false; btn.textContent = t;
  };
  $("#vSave", el).onclick = async () => { await saveVoice(); toast("語音設定已儲存 ✓"); };
  $("#vTest", el).onclick = async () => { await saveVoice(); testVoice($("#vTest", el)); };
  // 我的聲音
  const svShow = (st) => {
    $("#svStat", el).innerHTML = !st.dir ? "還沒設定資料夾" : !st.dir_ok ? "⚠️ 這個資料夾裡找不到 api_v2.py，請選解壓縮後的那一層"
      : !st.python_ok ? "⚠️ 找不到 runtime\\python.exe，請用官方 Windows 整合包"
      : st.running ? `✅ 正在執行（port ${st.port}）` : st.starting ? "⏳ 啟動中…（第一次約 30 秒～2 分鐘）"
      : st.error ? "⚠️ " + esc(st.error) : "已就緒，要用的時候會自動啟動";
  };
  svShow(VL.sovits || {});
  const svPoll = async (n = 0) => { const v = await api("/api/voices"); svShow(v.sovits); if (!v.sovits.running && (v.sovits.starting || n < 3) && n < 70 && el.isConnected) setTimeout(() => svPoll(n + 1), 2000); };
  $("#svSave", el).onclick = async () => { await api("/api/settings", { sovits_dir: $("#svDir", el).value }); await refreshStatus(); svShow((await api("/api/voices")).sovits); toast("已儲存 ✓"); };
  $("#svStart", el).onclick = async () => { await api("/api/settings", { sovits_dir: $("#svDir", el).value }); svShow(await api("/api/sovits/start", {})); svPoll(); };
  $("#svStop", el).onclick = async () => { await api("/api/sovits/stop", {}); setTimeout(() => svPoll(5), 800); };
  $("#nvAdd", el).onclick = () => {
    const file = $("#nvFile", el).files[0];
    if (!file) return toast("先選一個錄音檔");
    if (!$("#nvText", el).value.trim()) return toast("請打上錄音裡講的每一個字");
    const rd = new FileReader();
    rd.onload = async () => {
      try {
        await api("/api/voices/add", { name: $("#nvName", el).value || "我的聲音", text: $("#nvText", el).value, lang: $("#nvLang", el).value, filename: file.name, data: rd.result });
        toast("已加入聲音庫 ✓ 按「▶ 試聽」看看像不像"); rerender();
      } catch (e) { toast("加入失敗：" + e.message, 5000); }
    };
    rd.readAsDataURL(file);
  };
  el.querySelectorAll("[data-vtest]").forEach((b) => b.onclick = () => testVoice(b, { engine: "clone", clone: b.dataset.vtest, rate: 0 }));
  el.querySelectorAll("[data-vdel]").forEach((b) => b.onclick = async () => {
    if (!confirm("確定刪除這段錄音？")) return;
    await api("/api/voices/delete", { id: b.dataset.vdel }); await refreshStatus(); rerender();
  });
}

function voiceSelect(id, clones, withDefault) {
  return `<select id="${id}" class="sel" style="flex:1">
    ${withDefault ? `<option value="default">跟預設聲音一樣</option>` : ""}
    ${clones.length ? `<optgroup label="🎙️ 我的聲音（GPT-SoVITS）">${clones.map((v) => `<option value="clone:${v.id}">${esc(v.name)}</option>`).join("")}</optgroup>` : ""}
    <optgroup label="Edge 神經語音">${VOICE_LIST.map(([v, t]) => `<option value="edge:${v}">${t}</option>`).join("")}</optgroup>
    <option value="windows">Windows 內建語音</option></select>`;
}

function levelUpBox(ev) {
  const wrap = document.createElement("div");
  wrap.className = "modal";
  const sk = S.status?.settings?.buddy_skin || "jiujiu";
  wrap.innerHTML = `<div class="box lvup" style="max-width:420px;text-align:center">
    <div class="confetti">${Array.from("🎉✨⭐💖🎊".repeat(4)).map((c, i) => `<span style="--i:${i}">${c}</span>`).join("")}</div>
    <div style="width:150px;height:150px;margin:0 auto">${window.renderBuddy(sk === "custom" ? "jiujiu" : sk, "wow", [])}</div>
    <h2 style="margin:8px 0 0">升級！Lv.${ev.level}</h2><p class="muted">一起變強了！去「角色房間」看看有沒有新配件 ✨</p>
    <div class="row" style="justify-content:center"><button class="btn" data-go>去角色房間</button><button class="btn ghost" data-x>好</button></div></div>`;
  wrap.querySelector("[data-go]").onclick = () => { wrap.remove(); location.hash = "#/room"; };
  wrap.querySelector("[data-x]").onclick = () => wrap.remove();
  document.body.appendChild(wrap);
}


/* ================= 角色設定（個性、語氣、台詞） ================= */
const MOOD_LABEL = { happy: "平常", wow: "驚喜（打得好）", sad: "難過（被殺）", cheer: "加油", comfort: "加碼安慰（連敗）", proud: "傲嬌的肯定（打得特別好）", daily: "專屬日常（閒聊）" };
const STAGE_NAMES = ["初次見面", "熟悉", "好朋友", "最佳戰友"];
function personaCard(P) {
  const p = P.persona;
  const lines = p.lines || {};
  return `<div class="card section persona"><h3>🎭 角色設定 <span class="hint">AI 會照這份設定講話；沒接 AI 時用下面的台詞</span></h3>
    <div class="row" style="gap:16px;flex-wrap:wrap">
      <label class="switch" style="padding:0"><input type="checkbox" id="pOn" ${p.enabled ? "checked" : ""}><span></span><div><b>使用角色設定</b></div></label>
      <div class="field" style="margin:0;flex:1;min-width:200px"><label>角色名字</label><input id="pName" value="${esc(p.name || "")}" maxlength="16" placeholder="例如：艾莉"></div>
    </div>
    <div class="field"><label>個性與說話方式（給 AI 看的設定）</label><textarea id="pPrompt" rows="8">${esc(p.prompt || "")}</textarea></div>
    <details><summary><b>四個親密度階段的語氣與稱呼</b></summary>
      <div class="ptones">${STAGE_NAMES.map((n, i) => `<div class="ptone"><b>${n}</b>
        <input data-addr="${i}" value="${esc((p.address || [])[i] || "{n}")}" title="稱呼玩家的方式，{n} 會換成你的暱稱">
        <textarea data-tone="${i}" rows="2">${esc((p.tones || [])[i] || "")}</textarea></div>`).join("")}</div>
      <div class="faint" style="font-size:12px">稱呼欄位的 {n} 會換成你的暱稱，例如「{n}同學」。</div></details>
    <details><summary><b>口頭禪</b>（一行一句）</summary><textarea id="pCatch" rows="4">${esc((p.catchphrases || []).join("\n"))}</textarea></details>
    <details><summary><b>各情境台詞</b>（沒接 AI 時用，一行一句；俄文後面加（翻譯））</summary>
      <div class="plines">${Object.keys(MOOD_LABEL).map((m) => `<div><label>${MOOD_LABEL[m]}</label><textarea data-line="${m}" rows="4">${esc((lines[m] || []).join("\n"))}</textarea></div>`).join("")}</div></details>
    <div class="row" style="margin-top:12px"><button class="btn" id="pSave">儲存角色設定</button>
      <button class="btn ghost" id="pTest">💬 讓角色說一句看看</button>
      ${P.has_template ? `<button class="btn ghost" id="pReset">↩ 還原成預設範本</button>` : ""}</div>
  </div>`;
}
function bindPersona(el, P, rerender) {
  const read = () => {
    const lines = {};
    el.querySelectorAll("[data-line]").forEach((t) => { lines[t.dataset.line] = t.value.split("\n").map((x) => x.trim()).filter(Boolean); });
    return {
      enabled: $("#pOn", el).checked, name: $("#pName", el).value.trim(), prompt: $("#pPrompt", el).value.trim(),
      tones: [...el.querySelectorAll("[data-tone]")].map((t) => t.value.trim()),
      address: [...el.querySelectorAll("[data-addr]")].map((t) => t.value.trim() || "{n}"),
      catchphrases: $("#pCatch", el).value.split("\n").map((x) => x.trim()).filter(Boolean), lines,
    };
  };
  $("#pSave", el).onclick = async () => {
    try { await api("/api/persona", { char: P.char, persona: read() }); toast("角色設定已儲存 ✓"); rerender(); } catch (e) { toast(e.message, 4000); }
  };
  if ($("#pReset", el)) $("#pReset", el).onclick = async () => {
    if (!confirm("還原成預設範本？你改過的內容會不見。")) return;
    await api("/api/persona/reset", { char: P.char });
    toast("已還原 ✓");
    rerender();
  };
  $("#pTest", el).onclick = async () => {
    try {
      await api("/api/persona", { char: P.char, persona: read() });
      const r = await api("/api/buddy/test", {});
      alertBox(`${esc(read().name || "角色")}說：「${esc(r.line)}」${r.error ? `<br><span class="err" style="font-size:13px">（AI 沒回應，先用離線台詞：${esc(r.error)}）</span>` : ""}`);
    } catch (e) { toast(e.message, 4000); }
  };
}

/* ---------------- 路由 ---------------- */
const ROUTES = { room: pageRoom, recap: pageRecap, overview: pageOverview, matches: pageMatches, agents: pageAgents, habits: pageHabits, live: pageLive, lineups: pageLineups, settings: pageSettings };
async function route() {
  const id = (location.hash.match(/^#\/(\w+)/) || [])[1] || "overview";
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.p === id));
  // 每次換頁都用新的容器，舊頁面還沒跑完的非同步結果會寫到已經拿掉的容器，不會蓋掉新頁面
  const el = document.createElement("div");
  $("#main").replaceChildren(el);
  if (id !== "live") clearInterval(S.liveTimer);
  el.innerHTML = loading();
  try {
    await (ROUTES[id] || pageOverview)(el);
  } catch (e) {
    el.innerHTML = emptyBox(`<span class="err">出錯了：${esc(e.message)}</span>`, "sad");
  }
  window.scrollTo(0, 0);
}

(async function init() {
  renderShell();
  $("#main").innerHTML = loading("準備中…");
  await Promise.all([loadAssets(), refreshStatus()]);
  window.addEventListener("hashchange", route);
  route();
  try { S.evId = Math.max(0, ...(await api("/api/events?since=0")).map((e) => e.id)); } catch { /* ignore */ }
  setInterval(pollEvents, 8000);
  setInterval(refreshStatus, 30000);
  checkUpdate(true);
})();
