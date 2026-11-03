/* 마켓 계측소 — 화면 렌더링. 데이터는 data/*.json(자동 갱신)과 content/*.json(직접 편집)에서 읽습니다. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const DOW = ["일", "월", "화", "수", "목", "금", "토"];

  const fmt = (v, d = 2) => (v == null || isNaN(v) ? "—" : Number(v).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sgn = (v, d = 2) => (v == null || isNaN(v) ? "—" : (v > 0 ? "+" : "") + fmt(v, d) + "%");
  const cls = (v) => (v == null || Math.abs(v) < 0.005 ? "flat" : v > 0 ? "up" : "down");
  const price = (v) => (v == null ? "—" : Math.abs(v) >= 1000 ? fmt(v, 0) : Math.abs(v) >= 10 ? fmt(v, 2) : fmt(v, 3));

  const STORE = {
    get(k, d) { try { return JSON.parse(localStorage.getItem("mv:" + k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem("mv:" + k, JSON.stringify(v)); } catch {} },
  };

  async function load(path) {
    const pre = window.__DATA__ && window.__DATA__[path];
    if (pre) return pre;
    try {
      const r = await fetch(path + "?v=" + Math.floor(Date.now() / 60000), { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } catch (e) { console.warn("불러오기 실패", path, e); return null; }
  }

  function hex(c) { const m = c.replace("#", ""); const n = parseInt(m.length === 3 ? m.split("").map((x) => x + x).join("") : m, 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function mix(a, b, t) { const A = hex(a), B = hex(b); return `rgb(${A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(",")})`; }
  function lum(c) { const m = c.match(/\d+/g).map(Number); return (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) / 255; }

  function seg(el, options, value, onChange) {
    el.innerHTML = options.map(([v, l]) => `<button type="button" data-v="${esc(v)}" aria-pressed="${v === value}">${esc(l)}</button>`).join("");
    el.onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      el.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      onChange(b.dataset.v);
    };
  }
  function spark(vals, w = 64, h = 30) {
    if (!vals || vals.length < 2) return "";
    const mn = Math.min(...vals), mx = Math.max(...vals), r = mx - mn || 1;
    const pts = vals.map((v, i) => [(i / (vals.length - 1)) * (w - 4) + 2, h - 3 - ((v - mn) / r) * (h - 6)]);
    const c = vals[vals.length - 1] >= vals[0] ? "var(--up)" : "var(--down)";
    const last = pts[pts.length - 1];
    return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="M${pts.map((p) => p.map((x) => x.toFixed(1)).join(",")).join("L")}L${w - 2},${h}L2,${h}Z" fill="${c}" opacity=".12"/><polyline points="${pts.map((p) => p.join(",")).join(" ")}" fill="none" stroke="${c}" stroke-width="1.5"/><circle cx="${last[0]}" cy="${last[1]}" r="2.2" fill="${c}"/></svg>`;
  }
  const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; document.body.appendChild(tip);
  function showTip(html, e) { tip.innerHTML = html; tip.hidden = false; const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8); const y = e.clientY + 16 + tip.offsetHeight > innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 16; tip.style.left = x + "px"; tip.style.top = y + "px"; }
  function hideTip() { tip.hidden = true; }

  const GROUP_VAR = { 주도: "--g-lead", 방어: "--g-def", 탐색: "--g-exp" };
  const D = {};
  const rerender = [];

  /* ── 상태 표시 ── */
  function stamp() {
    const st = D.status || {};
    const show = (iso) => (iso ? iso.slice(5, 16).replace("T", " ").replace("-", "/") : "—");
    $("#stamp").textContent = st.sample ? "샘플 데이터" : `미장 ${show(st.us)} · 국장 ${show(st.kr)} · BTC ${show(st.btc)}`;
    const sample = Object.values(D).some((x) => x && x.sample);
    $("#sample").hidden = !sample;
  }

  /* ── 나의 한마디 ── */
  function notes() {
    const n = (D.notes && D.notes.items) || [];
    $("#notes").innerHTML = n.length
      ? n.slice(0, 5).map((x) => `<article class="note"><div class="d">${esc(x.date)}</div><h3>${esc(x.title)}</h3><p>${esc(x.body)}</p>${x.link ? `<a href="${esc(x.link)}" target="_blank" rel="noopener">관련 링크 ↗</a>` : ""}</article>`).join("")
      : `<p class="empty">content/notes.json 에 메모를 적으면 여기에 표시됩니다.</p>`;
  }

  /* ── 체온계 ── */
  let thermoMkt = STORE.get("thermo", "us");
  function thermoSVG(t) {
    const v = t == null ? 0 : Math.max(0, Math.min(100, t));
    const top = 18, bot = 200, fillY = bot - (bot - top) * v / 100;
    const col = mix(css("--down"), css("--up"), v / 100);
    const ticks = [0, 20, 40, 60, 80, 100].map((k) => { const y = bot - (bot - top) * k / 100; return `<line x1="70" x2="78" y1="${y}" y2="${y}" stroke="var(--muted)"/><text x="82" y="${y + 4}" font-size="10" fill="var(--muted)" font-family="var(--f-num)">${k}</text>`; }).join("");
    return `<svg viewBox="0 0 120 250" role="img" aria-label="체온 ${fmt(t, 0)}도"><rect x="44" y="${top - 8}" width="22" height="${bot - top + 30}" rx="11" fill="var(--soft)" stroke="var(--line)"/><rect x="50" y="${fillY}" width="10" height="${bot - fillY + 12}" fill="${col}"/><circle cx="55" cy="${bot + 26}" r="20" fill="${col}" stroke="var(--line)"/>${ticks}</svg>`;
  }
  function thermo() {
    const T = D.thermo; const box = $("#thermo-body");
    if (!T) { box.innerHTML = `<p class="empty">체온계 데이터를 아직 받지 못했습니다.</p>`; return; }
    const b = T[thermoMkt];
    if (!b) { box.innerHTML = `<p class="empty">이 시장 데이터가 아직 없습니다.</p>`; return; }
    const gauges = b.parts.map((p) => `<div class="gauge"><div class="row1"><span>${esc(p.label)}</span><b class="num">${p.value == null ? "—" : fmt(p.value, p.unit === "%" ? 1 : 1) + p.unit}</b></div><div class="track"><span class="mk" style="left:${p.score ?? 50}%"></span></div><small>${esc(p.note)} · 점수 ${p.score == null ? "—" : fmt(p.score, 0)}</small></div>`).join("");
    const idx = b.indices.map((i) => `<div class="idx"><span class="n">${esc(i.name)}</span><span class="v">${price(i.last)}</span><span class="c ${cls(i.chg1d)}">${sgn(i.chg1d)} <span class="flat">1주 ${sgn(i.chg1w, 1)}</span></span>${spark(i.spark)}</div>`).join("");
    box.innerHTML = `<div class="thermo"><div class="thermo-fig">${thermoSVG(b.temp)}<div><div class="t num">${fmt(b.temp, 0)}°</div><div class="l">${esc(b.label)}</div><div class="l num">기준일 ${esc(b.asof)}</div></div></div>
      <div class="gauges">${gauges}</div><div class="idx-col"><h3 class="sub">주요 지표</h3><div class="idx-grid">${idx}</div></div></div>
      <div class="hist"><h3>체온 추이 (갱신 시점별)</h3>${histSVG(T.history || [])}<div class="legend"><span><i style="background:var(--accent)"></i>미국</span><span><i style="background:var(--g-lead)"></i>한국</span><span>20 이하 공포 · 80 이상 과열</span></div></div>`;
  }
  function histSVG(h) {
    if (h.length < 2) return `<p class="empty">추이는 갱신이 쌓이면 그려집니다.</p>`;
    const W = 600, H = 120, P = 22, n = h.length;
    const x = (i) => P + (i / (n - 1)) * (W - P - 6), y = (v) => H - 14 - (v / 100) * (H - 24);
    const line = (k, c) => `<polyline fill="none" stroke="${c}" stroke-width="2" points="${h.map((r, i) => (r[k] == null ? null : `${x(i).toFixed(1)},${y(r[k]).toFixed(1)}`)).filter(Boolean).join(" ")}"/>`;
    const grid = [0, 20, 50, 80, 100].map((v) => `<line x1="${P}" x2="${W - 6}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" ${v === 20 || v === 80 ? 'stroke-dasharray="3 3"' : ""}/><text x="0" y="${y(v) + 3}" font-size="10" fill="var(--muted)" font-family="var(--f-num)">${v}</text>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="체온 추이">${grid}${line("us", "var(--accent)")}${line("kr", "var(--g-lead)")}<text x="${P}" y="${H - 1}" font-size="10" fill="var(--muted)">${esc((h[0].at || "").slice(5, 10))}</text><text x="${W - 6}" y="${H - 1}" font-size="10" fill="var(--muted)" text-anchor="end">${esc((h[n - 1].at || "").slice(5, 10))}</text></svg>`;
  }

  /* ── 히트맵 ── */
  let hmMkt = STORE.get("hmMkt", "sp500"), hmPer = STORE.get("hmPer", "d1");
  function heatColor(v) {
    if (v == null) return css("--tile0");
    const t = Math.min(1, Math.abs(v) / 3);
    return mix(css("--tile0"), css(v >= 0 ? "--up" : "--down"), 0.15 + 0.85 * t);
  }
  function heatmap() {
    const box = $("#tm"); const H = D.heat;
    const tiles = H && H[hmMkt];
    if (!tiles || !tiles.length || !window.d3) { box.innerHTML = `<p class="empty" style="padding:16px">히트맵 데이터를 아직 받지 못했습니다.</p>`; return; }
    const W = box.clientWidth, Hh = box.clientHeight;
    const bySec = {};
    tiles.forEach((t) => (bySec[t.sector] ||= []).push(t));
    const root = d3.hierarchy({ children: Object.entries(bySec).map(([s, ch]) => ({ name: s, children: ch })) }).sum((d) => d.cap ? Math.sqrt(d.cap) ** 1.6 : 0).sort((a, b) => b.value - a.value);
    d3.treemap().size([W, Hh]).paddingTop(15).paddingInner(1).paddingOuter(1).round(true).tile(d3.treemapSquarify.ratio(1.2))(root);
    let html = "";
    root.children.forEach((s) => {
      html += `<div class="sec-l" style="left:${s.x0}px;top:${s.y0}px;width:${s.x1 - s.x0}px">${esc(s.data.name)}</div>`;
      s.children.forEach((n, i) => {
        const t = n.data, w = n.x1 - n.x0, h = n.y1 - n.y0, v = t[hmPer], bg = heatColor(v);
        const fs = Math.max(9, Math.min(22, Math.sqrt(w * h) / 5.5));
        const label = w > 34 && h > 24 ? `<b style="font-size:${fs}px">${esc(t.name.length > 8 && w < 90 ? t.t.replace(/\.(KS|KQ)$/, "") : t.name)}</b>${h > 36 ? `<span style="font-size:${Math.max(9, fs * 0.72)}px">${sgn(v, 1)}</span>` : ""}` : "";
        const g = t.group ? ` g" style="--gc:var(${GROUP_VAR[t.group]});` : `" style="`;
        html += `<div class="tile${g}left:${n.x0}px;top:${n.y0}px;width:${w}px;height:${h}px;background:${bg};color:${lum(bg) > 0.55 ? "#111" : "#fff"}" data-k="${esc(hmMkt)}:${esc(s.data.name)}:${i}">${label}</div>`;
      });
    });
    box.innerHTML = html;
    box.onmousemove = (e) => {
      const el = e.target.closest(".tile"); if (!el) return hideTip();
      const [, sec, i] = el.dataset.k.split(":"); const t = bySec[sec][+i] ? root.children.find((s) => s.data.name === sec).children[+i].data : null;
      if (!t) return;
      showTip(`<b>${esc(t.name)}</b> <span class="num">${esc(t.t)}</span><br>${esc(t.sector)}${t.group ? " · " + esc(t.group) : ""}<br><span class="num">${price(t.last)}</span><br><span class="num">1일 ${sgn(t.d1)} · 1주 ${sgn(t.w1)} · 1개월 ${sgn(t.m1)}</span>`, e);
    };
    box.onmouseleave = hideTip;
  }

  /* ── 캘린더 ── */
  let calFilter = STORE.get("calF", "all"), calView = STORE.get("calV", "cal");
  const CAT = {
    macro: ["거시·지표", "var(--muted)"], fomc: ["FOMC", "var(--fomc)"], holiday: ["휴장·시장 이벤트", "var(--line)"],
    주도: ["주도", "var(--g-lead)"], 방어: ["방어", "var(--g-def)"], 탐색: ["탐색", "var(--g-exp)"],
  };
  const lv = (n) => (n >= 3 ? "◆◆◆" : n === 2 ? "◆◆" : n === 1 ? "◆" : "");
  function calPass(e) {
    if (calFilter === "all") return true;
    if (calFilter === "macro") return ["macro", "fomc", "holiday"].includes(e.cat);
    return e.cat === calFilter;
  }
  function evHTML(e) {
    const vals = [e.actual ? `발표 <b>${esc(e.actual)}</b>` : "", e.forecast ? `예상 ${esc(e.forecast)}` : "", e.previous ? `이전 ${esc(e.previous)}` : ""].filter(Boolean).join(" ");
    return `<div class="ev ${e.cat === "fomc" ? "fomc" : ""}" style="--cc:${CAT[e.cat]?.[1] || "var(--line)"}"><div class="tt"><span>${esc(e.time || "종일")}</span><span>${esc(e.flag || "")}</span><span class="lv">${lv(e.level)}</span></div><div class="ti">${e.estimated ? "★ " : ""}${esc(e.title)}</div>${vals ? `<div class="vals">${vals}</div>` : ""}</div>`;
  }
  function calendar() {
    const C = D.cal; const box = $("#cal-body");
    if (!C) { box.innerHTML = `<p class="empty">일정 데이터를 아직 받지 못했습니다.</p>`; return; }
    const evs = C.events.filter(calPass);
    const today = C.start;
    const days = Array.from({ length: 7 }, (_, k) => { const d = new Date(today + "T00:00:00+09:00"); d.setDate(d.getDate() + k); return d; });
    const iso = (d) => new Date(d.getTime() + 9 * 3600e3).toISOString().slice(0, 10);
    let main;
    if (calView === "cal") {
      main = `<div class="week">${days.map((d) => { const k = iso(d); const list = evs.filter((e) => e.date === k); const dw = new Date(k + "T12:00:00+09:00").getUTCDay();
        return `<div class="day ${k === today ? "today" : ""}"><h4><span>${k === today ? "오늘" : DOW[dw] + "요일"}</span><span class="num">${k.slice(5).replace("-", "/")}</span></h4>${list.map(evHTML).join("") || `<span class="flat" style="font-size:12px">일정 없음</span>`}</div>`; }).join("")}</div>`;
    } else {
      main = evs.length ? `<div class="list"><div class="list-scroll"><table><thead><tr><th>날짜·시간</th><th>일정</th><th>분류</th><th>발표 / 예상 / 이전</th></tr></thead><tbody>${evs.map((e) => `<tr><td class="num">${e.date.slice(5).replace("-", "/")} ${esc(e.time || "종일")}</td><td><span class="dot" style="--cc:${CAT[e.cat]?.[1]}"></span>${esc(e.flag || "")} ${e.estimated ? "★ " : ""}${esc(e.title)} <span style="color:var(--accent);font-size:10px">${lv(e.level)}</span></td><td>${esc(CAT[e.cat]?.[0] || e.cat)}</td><td class="num">${esc(e.actual || "—")} / ${esc(e.forecast || "—")} / ${esc(e.previous || "—")}</td></tr>`).join("")}</tbody></table></div></div>` : `<p class="empty">이 분류의 일정이 없습니다.</p>`;
    }
    const dx = C.diagnosis;
    const rx = dx ? `<aside class="rx"><div class="no">CHART NO. ${esc(dx.chart_no)}</div><h3>오늘의 진단서</h3><ul>${dx.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul><div class="verdict">처방: ${esc(dx.verdict)}</div><div class="sig">계측소 자동 진단 · ${esc(dx.date)}</div></aside>` : "";
    box.innerHTML = `<div class="cal-wrap"><div style="min-width:0">${main}</div>${rx}</div>`;
  }

  /* ── BTC 청산맵 ── */
  let btcWin = STORE.get("btcW", "3d"), livePrice = null;
  function btc() {
    const B = D.btc; const cv = $("#btc-cv"); const side = $("#btc-side");
    const w = B && B.windows && B.windows[btcWin];
    if (!w) { side.innerHTML = `<p class="empty">청산맵 데이터를 아직 받지 못했습니다.</p>`; cv.hidden = true; return; }
    cv.hidden = false;
    const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d"); g.scale(dpr, dpr);
    const L = 58, R = 74, T = 8, Bm = 22, pw = W - L - R, ph = H - T - Bm;
    const n = w.times.length, nb = w.edges.length - 1, lo = w.edges[0], hi = w.edges[nb];
    const yP = (p) => T + ph - ((p - lo) / (hi - lo)) * ph;
    g.fillStyle = css("--heat0"); g.fillRect(L, T, pw, ph);
    const stops = ["--heat0", "--heat1", "--heat2", "--heat3"].map(css);
    const ramp = (v) => { const t = Math.sqrt(v / 1000) * 3; const k = Math.min(2, Math.floor(t)); return mix(stops[k], stops[k + 1], Math.min(1, t - k)); };
    const cw = pw / n, ch = ph / nb;
    for (let i = 0; i < n; i++) for (let b = 0; b < nb; b++) { const v = w.heat[i][b]; if (v < 8) continue; g.fillStyle = ramp(v); g.fillRect(L + i * cw, T + ph - (b + 1) * ch, Math.ceil(cw) + 0.5, Math.ceil(ch) + 0.5); }
    // 고저 범위 + 종가선
    g.strokeStyle = css("--ink"); g.lineWidth = 1.6; g.beginPath();
    w.price.forEach((p, i) => { const x = L + (i + 0.5) * cw, y = yP(p); i ? g.lineTo(x, y) : g.moveTo(x, y); }); g.stroke();
    // 현재가
    const cur = livePrice || w.last; const yc = yP(cur);
    g.setLineDash([4, 4]); g.strokeStyle = css("--accent"); g.beginPath(); g.moveTo(L, yc); g.lineTo(L + pw, yc); g.stroke(); g.setLineDash([]);
    // 오른쪽: 남은 청산 물량 프로필
    const mxp = Math.max(...w.long_now, ...w.short_now, 1);
    for (let b = 0; b < nb; b++) {
      const y = T + ph - (b + 1) * ch;
      if (w.long_now[b]) { g.fillStyle = css("--down"); g.fillRect(L + pw + 4, y, (w.long_now[b] / mxp) * (R - 8), Math.max(1, ch - 0.5)); }
      if (w.short_now[b]) { g.fillStyle = css("--up"); g.fillRect(L + pw + 4, y, (w.short_now[b] / mxp) * (R - 8), Math.max(1, ch - 0.5)); }
    }
    // 축
    g.fillStyle = css("--muted"); g.font = `11px ${css("--f-num")}`; g.textAlign = "right";
    for (let k = 0; k <= 6; k++) { const p = lo + (hi - lo) * k / 6; g.fillText(fmt(p, 0), L - 6, yP(p) + 4); }
    g.textAlign = "center";
    const fmtT = (s) => { const d = new Date(s * 1000 + 9 * 3600e3); return btcWin === "24h" ? d.toISOString().slice(11, 16) : d.toISOString().slice(5, 10).replace("-", "/") + " " + d.toISOString().slice(11, 13) + "시"; };
    [0, Math.floor(n / 2), n - 1].forEach((i) => g.fillText(fmtT(w.times[i]), Math.min(Math.max(L + (i + 0.5) * cw, L + 40), L + pw - 40), H - 6));
    g.fillStyle = css("--accent"); g.textAlign = "left"; g.fillText(fmt(cur, 0), L + 4, yc - 5);
    // 툴팁
    cv.onmousemove = (e) => {
      const r = cv.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
      if (x < L || x > L + pw || y < T || y > T + ph) return hideTip();
      const i = Math.min(n - 1, Math.floor((x - L) / cw)), b = Math.min(nb - 1, Math.floor((T + ph - y) / ch));
      showTip(`<span class="num">${fmtT(w.times[i])}</span><br>가격대 <span class="num">${fmt(w.edges[b], 0)}~${fmt(w.edges[b + 1], 0)}</span><br>밀집도 <span class="num">${(w.heat[i][b] / 10).toFixed(0)}%</span> · 종가 <span class="num">${fmt(w.price[i], 0)}</span>`, e);
    };
    cv.onmouseleave = hideTip;
    const m = w.magnet || {};
    const dist = (z) => (z ? sgn((z / cur - 1) * 100, 1) : "—");
    const rel = Object.entries(B.related || {}).map(([t, q]) => `<span class="chip"><b>${esc(t)}</b><span class="num ${cls(q.d1)}">${sgn(q.d1, 1)}</span></span>`).join("");
    side.innerHTML = `<div class="kv"><span class="k">BTC ${livePrice ? "실시간" : "기준"} 가격</span><span class="v">$${fmt(cur, 0)}</span></div>
      <div class="kv"><span class="k">위쪽 숏 청산 밀집</span><span class="v up">$${fmt(m.short_zone, 0)} <small class="num">${dist(m.short_zone)}</small></span></div>
      <div class="kv"><span class="k">아래쪽 롱 청산 밀집</span><span class="v down">$${fmt(m.long_zone, 0)} <small class="num">${dist(m.long_zone)}</small></span></div>
      <div class="legend"><span>적음</span><span class="ramp"></span><span>청산 밀집</span></div>
      <div class="legend"><span><i style="background:var(--up)"></i>숏 청산 잔량</span><span><i style="background:var(--down)"></i>롱 청산 잔량</span></div>
      <div><h3 class="sub">관련주</h3><div class="chips">${rel || '<span class="flat">—</span>'}</div></div>`;
  }
  async function pollBTC() {
    try {
      const r = await fetch("https://api.coinbase.com/v2/prices/BTC-USD/spot", { cache: "no-store" });
      const j = await r.json(); const p = parseFloat(j.data.amount);
      if (p > 0) { livePrice = p; btc(); }
    } catch {}
  }

  /* ── 실적 반응 ── */
  let coSel = STORE.get("co", null);
  function earnings() {
    const E = D.earn; const box = $("#earn-body"); const chips = $("#co-chips");
    const cs = (E && E.companies) || [];
    if (!cs.length) { chips.innerHTML = ""; box.innerHTML = `<p class="empty">실적 이력 데이터를 아직 받지 못했습니다.</p>`; return; }
    if (!cs.find((c) => c.t === coSel)) coSel = cs[0].t;
    chips.innerHTML = cs.map((c) => `<button type="button" aria-pressed="${c.t === coSel}" data-t="${esc(c.t)}" style="--gc:var(${GROUP_VAR[c.group]})">${esc(c.name)}</button>`).join("");
    chips.onclick = (e) => { const b = e.target.closest("button"); if (!b) return; coSel = b.dataset.t; STORE.set("co", coSel); earnings(); };
    const c = cs.find((x) => x.t === coSel); const rows = c.rows;
    const W = 640, H = 260, P = 40, B = 34, n = rows.length;
    const mx = Math.max(4, ...rows.flatMap((r) => [Math.abs(r.d1), Math.abs(r.d5)])) * 1.1;
    const y = (v) => P - 20 + (H - P - B + 20) / 2 - (v / mx) * ((H - P - B + 20) / 2) + 0;
    const bw = (W - P - 10) / n;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(c.name)} 실적 발표 후 주가 반응">`;
    [-mx, -mx / 2, 0, mx / 2, mx].forEach((v) => { svg += `<line x1="${P}" x2="${W - 6}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" ${v ? 'stroke-dasharray="2 4"' : ""}/><text x="${P - 6}" y="${y(v) + 3}" text-anchor="end" font-size="10" fill="var(--muted)" font-family="var(--f-num)">${v > 0 ? "+" : ""}${v.toFixed(0)}%</text>`; });
    rows.forEach((r, i) => {
      const x = P + i * bw + bw * 0.18, w1 = bw * 0.3;
      const bar = (v, xx, op) => `<rect x="${xx}" y="${Math.min(y(0), y(v))}" width="${w1}" height="${Math.max(1, Math.abs(y(v) - y(0)))}" fill="var(${v >= 0 ? "--up" : "--down"})" opacity="${op}"><title>${v.toFixed(1)}%</title></rect>`;
      svg += bar(r.d1, x, 1) + bar(r.d5, x + w1 + 2, 0.45);
      svg += `<text x="${x + w1}" y="${H - B + 14}" text-anchor="middle" font-size="10" fill="var(--muted)" font-family="var(--f-num)">${r.date.slice(2, 7).replace("-", ".")}</text>`;
      if (r.surprise != null) svg += `<text x="${x + w1}" y="${H - B + 27}" text-anchor="middle" font-size="10" fill="var(${r.surprise >= 0 ? "--up" : "--down"})" font-family="var(--f-num)">${r.surprise >= 0 ? "+" : ""}${r.surprise.toFixed(0)}%</text>`;
    });
    svg += `<text x="${P - 6}" y="${H - B + 27}" text-anchor="end" font-size="10" fill="var(--muted)">서프</text></svg>`;
    const last = rows[rows.length - 1];
    box.innerHTML = `<div class="earn"><div style="min-width:0">${svg}<div class="legend"><span><i style="background:var(--up)"></i>발표 후 1일</span><span><i style="background:var(--up);opacity:.45"></i>5일</span><span>아래 숫자: EPS 서프라이즈</span></div>
      <div class="earn-tbl"><table><thead><tr><th>발표일</th><th>시점</th><th>EPS 예상</th><th>EPS 실제</th><th>서프라이즈</th><th>1일 반응</th><th>5일 반응</th></tr></thead><tbody>${rows.slice().reverse().map((r) => `<tr><td class="num">${esc(r.date)}</td><td>${esc(r.when)}</td><td class="num">${fmt(r.eps_est)}</td><td class="num">${fmt(r.eps_act)}</td><td class="num ${cls(r.surprise)}">${sgn(r.surprise, 1)}</td><td class="num ${cls(r.d1)}">${sgn(r.d1, 1)}</td><td class="num ${cls(r.d5)}">${sgn(r.d5, 1)}</td></tr>`).join("")}</tbody></table></div></div>
      <div class="side" style="display:grid;gap:12px;align-content:start">
        <div class="kv"><span class="k">그룹</span><span class="v" style="color:var(${GROUP_VAR[c.group]})">${esc(c.group)}</span></div>
        <div class="kv"><span class="k">평균 1일 변동폭 (절대값)</span><span class="v">${fmt(c.avg_abs_d1, 1)}%</span></div>
        <div class="kv"><span class="k">발표 다음날 상승 비율</span><span class="v">${fmt(c.up_ratio, 0)}%</span></div>
        <div class="kv"><span class="k">직전 분기 반응</span><span class="v ${cls(last.d1)}">${sgn(last.d1, 1)}</span></div>
      </div></div>`;
  }

  /* ── 인물의 한마디 ── */
  let who = "all";
  function voices() {
    const V = (D.voices && D.voices.items) || [];
    const box = $("#quotes"), ppl = $("#people");
    if (!V.length) { ppl.innerHTML = ""; box.innerHTML = `<p class="empty">content/voices.json 에 발언을 추가하면 여기에 날짜순으로 쌓입니다.</p>`; return; }
    const people = [...new Map(V.map((v) => [v.person, v])).values()];
    const hue = (s) => [...s].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
    const av = (p, big) => `<span class="av" style="background:hsl(${hue(p)} 45% 42%)">${esc(p.slice(0, big ? 2 : 1))}</span>`;
    ppl.innerHTML = `<button type="button" data-p="all" aria-pressed="${who === "all"}"><span class="av" style="background:var(--muted)">∗</span>전체</button>` + people.map((v) => `<button type="button" data-p="${esc(v.person)}" aria-pressed="${who === v.person}">${av(v.person)}${esc(v.person)}</button>`).join("");
    ppl.onclick = (e) => { const b = e.target.closest("button"); if (!b) return; who = b.dataset.p; voices(); };
    const list = V.filter((v) => who === "all" || v.person === who).sort((a, b) => (a.date < b.date ? 1 : -1));
    box.innerHTML = list.map((v) => `<article class="q">${av(v.person, true)}<div style="min-width:0"><div class="meta"><b>${esc(v.person)}</b><span>${esc(v.role || "")}</span><span class="num">${esc(v.date)}</span></div><p>${esc(v.summary)}</p>${v.source ? `<a class="src" href="${esc(v.source)}" target="_blank" rel="noopener">출처 ↗</a>` : ""}</div></article>`).join("");
  }

  /* ── 시작 ── */
  async function boot() {
    const [status, thermoD, heat, cal, btcD, earn, notesD, voicesD] = await Promise.all(
      ["data/status.json", "data/thermometer.json", "data/heatmap.json", "data/calendar.json", "data/btc.json", "data/earnings.json", "content/notes.json", "content/voices.json"].map(load));
    Object.assign(D, { status, thermo: thermoD, heat, cal, btc: btcD, earn, notes: notesD, voices: voicesD });
    stamp(); notes();
    seg($("#thermo-seg"), [["us", "미국"], ["kr", "한국"]], thermoMkt, (v) => { thermoMkt = v; STORE.set("thermo", v); thermo(); });
    seg($("#hm-mkt"), [["sp500", "미장 S&P 500"], ["kospi", "국장 코스피"], ["etf", "ETF"]], hmMkt, (v) => { hmMkt = v; STORE.set("hmMkt", v); heatmap(); });
    seg($("#hm-per"), [["d1", "1일"], ["w1", "1주"], ["m1", "1개월"]], hmPer, (v) => { hmPer = v; STORE.set("hmPer", v); heatmap(); });
    seg($("#cal-f"), [["all", "전체"], ["macro", "거시·지표"], ["주도", "주도"], ["방어", "방어"], ["탐색", "탐색"]], calFilter, (v) => { calFilter = v; STORE.set("calF", v); calendar(); });
    seg($("#cal-v"), [["cal", "달력"], ["list", "목록"]], calView, (v) => { calView = v; STORE.set("calV", v); calendar(); });
    seg($("#btc-w"), [["24h", "24시간"], ["3d", "3일"], ["7d", "7일"]], btcWin, (v) => { btcWin = v; STORE.set("btcW", v); btc(); });
    rerender.push(thermo, heatmap, calendar, btc, earnings, voices);
    rerender.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { heatmap(); btc(); }, 150); });
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => rerender.forEach((f) => f()));
    new MutationObserver(() => rerender.forEach((f) => f())).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    if (!(btcD && btcD.sample)) { pollBTC(); setInterval(pollBTC, 5 * 60e3); }
    // 페이지를 열어 둔 동안 10분마다 새 데이터 확인
    if (!window.__DATA__) setInterval(async () => { const s = await load("data/status.json"); if (s && JSON.stringify(s) !== JSON.stringify(D.status)) location.reload(); }, 10 * 60e3);
  }
  boot();
})();
