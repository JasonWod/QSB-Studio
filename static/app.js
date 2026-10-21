/* QSB Studio — 前端（原生 JS，无依赖、无构建步骤）
   结构：侧栏（模块搜索）| 输入面板 | 可拖动分隔线 | 演示舞台（演示 / 结果 / 原理） */
'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = IS_MAC ? '⌘' : 'Ctrl';

const STATUS = {
  optimal: '已求得最优解', ok: '完成', feasible: '可行解（未证明最优）', significant: '检验显著',
  infeasible: '无可行解', unbounded: '目标无界', unstable: '系统不稳定',
  iteration_limit: '迭代超限', error: '输入有误', not_implemented: '模块不可用',
};
const GOOD = new Set(['optimal', 'ok', 'significant', 'feasible']);

const LP_EXAMPLES = {
  classic: { label: '经典例题（最大化）', obj: 'max', c: [3, 5], A: [[1, 0], [0, 2], [3, 2]], b: [4, 12, 18], senses: ['le', 'le', 'le'] },
  min: { label: '最小化 + ≥ 约束（大 M 法）', obj: 'min', c: [2, 3], A: [[1, 1], [1, 2], [1, 0]], b: [4, 6, 5], senses: ['ge', 'ge', 'le'] },
  eq: { label: '含等式约束', obj: 'max', c: [1, 2], A: [[1, 1], [1, 0], [0, 1]], b: [4, 3, 3], senses: ['eq', 'le', 'le'] },
  degenerate: { label: '退化问题（Bland 规则防循环）', obj: 'max', c: [0.75, -20, 0.5, -6], A: [[0.25, -8, -1, 9], [0.5, -12, -0.5, 3], [0, 0, 1, 0]], b: [0, 0, 1], senses: ['le', 'le', 'le'] },
  infeasible: { label: '无可行解', obj: 'max', c: [1, 1], A: [[1, 1], [1, 1]], b: [2, 5], senses: ['le', 'ge'] },
  unbounded: { label: '目标无界', obj: 'max', c: [1, 1], A: [[1, -1], [-1, 1]], b: [2, 2], senses: ['le', 'le'] },
};

const state = { modules: [], m: null, results: {}, tab: {}, redraw: [], mode: 'server' };

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* 无存储时忽略 */ } },
  del(k) { try { localStorage.removeItem(k); } catch (_) { /* ignore */ } },
};

function fmt(v) {
  if (v === null || v === undefined || v === '') return v === '' ? '' : '—';
  if (typeof v === 'number') {
    if (!isFinite(v)) return v > 0 ? '∞' : '-∞';
    if (Math.abs(v) < 1e-9) return '0';
    if (Math.abs(v) >= 1e5) return v.toExponential(3).replace(/\.?0+e/, 'e');
    return String(Math.round(v * 1e6) / 1e6);
  }
  return String(v);
}
const cssVar = (name, fallback) => (getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const redrawAll = () => state.redraw.forEach((f) => f());

async function postJSON(url, payload) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  try { return await r.json(); } catch (e) { return { status: 'error', headline: '服务器返回了无法解析的数据', message: `HTTP ${r.status}` }; }
}
/* ============================== 通用：表格 ============================== */
function tableHTML(tb, cls = 'sens') {
  const cells = tb.cells || {}, rowcls = tb.rowcls || {}, colcls = tb.colcls || {};
  let h = `<div class="tblwrap"><table class="${cls}"><thead><tr>`;
  tb.headers.forEach((x, j) => { h += `<th class="${esc(colcls[j] || '')}">${esc(x)}</th>`; });
  h += '</tr></thead><tbody>';
  tb.rows.forEach((r, i) => {
    h += `<tr class="${esc(rowcls[i] || '')}">`;
    r.forEach((c, j) => {
      const k = [cells[`${i},${j}`], colcls[j]].filter(Boolean).join(' ');
      h += `<td class="${esc(k)}">${esc(fmt(c))}</td>`;
    });
    h += '</tr>';
  });
  return h + '</tbody></table></div>';
}

/* ============================== 演示播放器 ============================== */
class Player {
  static all = new Set();
  static stopAll() { Player.all.forEach((p) => p.stop()); Player.all.clear(); }

  constructor(root, frames, opts = {}) {
    this.root = root; this.frames = frames; this.i = 0; this.timer = null;
    this.shared = opts.shared || {}; this.render = opts.render || ((f, el) => renderFrame(f, el, this.shared));
    this.speed = +(localStorage.getItem('qsb-speed') || 1);
    Player.all.add(this);
    root.innerHTML = `
      <div class="player">
        <div class="player-bar">
          <button class="btn small ghost" data-a="first" title="第一步（Home）">⏮</button>
          <button class="btn small ghost" data-a="prev" title="上一步（←）">◀</button>
          <button class="btn small primary" data-a="play" title="播放 / 暂停（空格）">▶ 播放</button>
          <button class="btn small ghost" data-a="next" title="下一步（→）">▶</button>
          <button class="btn small ghost" data-a="last" title="最后一步（End）">⏭</button>
          <input type="range" class="scrub" min="0" max="${frames.length - 1}" value="0" aria-label="演示进度">
          <span class="count"></span>
          <select class="speed" aria-label="播放速度">
            ${[0.5, 1, 1.5, 2, 3].map((s) => `<option value="${s}" ${s === this.speed ? 'selected' : ''}>${s}×</option>`).join('')}
          </select>
        </div>
        <div class="frame-view"></div>
      </div>`;
    this.view = $('.frame-view', root);
    root.querySelectorAll('[data-a]').forEach((b) => { b.onclick = () => this.act(b.dataset.a); });
    this.scrub = $('.scrub', root);
    this.scrub.oninput = () => { this.stop(); this.go(+this.scrub.value); };
    $('.speed', root).onchange = (e) => {
      this.speed = +e.target.value;
      try { localStorage.setItem('qsb-speed', this.speed); } catch (_) { /* 无存储时忽略 */ }
      if (this.timer) { this.stop(); this.play(); }
    };
    this.go(0);
  }
  act(a) {
    if (a === 'play') return this.timer ? this.stop() : this.play();
    this.stop();
    if (a === 'first') this.go(0);
    if (a === 'prev') this.go(this.i - 1);
    if (a === 'next') this.go(this.i + 1);
    if (a === 'last') this.go(this.frames.length - 1);
  }
  go(i) {
    this.i = Math.max(0, Math.min(this.frames.length - 1, i));
    this.scrub.value = this.i;
    $('.count', this.root).textContent = `${this.i + 1} / ${this.frames.length}`;
    this.render(this.frames[this.i], this.view, this.i);
    this.view.classList.remove('flash'); void this.view.offsetWidth; this.view.classList.add('flash');
  }
  play() {
    if (this.i >= this.frames.length - 1) this.go(0);
    const btn = $('[data-a="play"]', this.root); btn.textContent = '⏸ 暂停';
    this.timer = setInterval(() => {
      if (this.i >= this.frames.length - 1) return this.stop();
      this.go(this.i + 1);
    }, 1600 / this.speed);
  }
  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    const btn = $('[data-a="play"]', this.root); if (btn) btn.textContent = '▶ 播放';
  }
}

function renderFrame(f, el, shared) {
  const hasVis = f.graph || f.chart;
  let h = `<div class="frame-title">${esc(f.title || '')}</div>`;
  if (f.text) h += `<div class="frame-text">${esc(f.text)}</div>`;
  h += `<div class="frame-body ${hasVis && f.tables ? 'two' : ''}">`;
  if (hasVis) h += '<div class="frame-vis"></div>';
  if (f.tables) h += `<div class="frame-tables">${f.tables.map((t) => `<h4>${esc(t.title || '')}</h4>${tableHTML(t)}`).join('')}</div>`;
  h += '</div>';
  el.innerHTML = h;
  const vis = $('.frame-vis', el);
  if (vis) drawVisual(vis, f.graph, f.chart, shared);
}

/* 把网络图或图表画进容器，并登记以便切换主题 / 改变窗口大小时重画 */
function drawVisual(box, graph, chart, shared) {
  const draw = () => {
    if (!box.isConnected) return;
    if (graph) box.innerHTML = netGraphSVG(graph);
    else if (chart) {
      let cv = $('canvas', box);
      if (!cv) { box.innerHTML = '<canvas class="graph"></canvas>'; cv = $('canvas', box); }
      drawChart(cv, mergeShared(chart, shared));
    }
  };
  draw();
  // 已从页面移除的容器（播放器切帧后）不再重画
  state.redraw = state.redraw.filter((d) => d.box && d.box.isConnected);
  draw.box = box;
  state.redraw.push(draw);
}
function mergeShared(chart, shared) {
  if (chart && chart.use && shared && shared[chart.use]) return Object.assign({}, shared[chart.use], chart);
  return chart;
}
/* ============================== 网络图（SVG） ============================== */
function netGraphSVG(g) {
  if (!g || !g.nodes || !g.nodes.length) return '';
  const n = g.nodes.length;
  const layout = g.layout || 'circular';
  let W, H, pad, nodeR, font;
  if (layout === 'bipartite') {
    const maxc = Math.max(1, ...['left', 'right'].map((side) => g.nodes.filter((x) => x.x < 0.5 === (side === 'left')).length));
    pad = 60; W = 720; H = Math.min(1100, Math.max(420, 2 * pad + (maxc - 1) * 62));
    nodeR = maxc > 8 ? 14 : 18; font = maxc > 8 ? 11 : 12.5;
  } else if (layout === 'tree' || layout === 'layered' || layout === 'row') {
    const depth = new Set(g.nodes.map((x) => x.y)).size;
    const width = new Set(g.nodes.map((x) => x.x)).size;
    pad = 48; W = Math.max(640, Math.min(1300, width * (layout === 'row' ? 130 : 80) + 2 * pad));
    H = layout === 'row' ? 220 : Math.max(320, Math.min(820, depth * 92 + 2 * pad));
    nodeR = n > 24 ? 14 : 18; font = n > 24 ? 10.5 : 12.5;
  } else {
    pad = 52;
    const S = Math.min(900, Math.max(500, Math.round(2 * pad + 56 / Math.sin(Math.PI / Math.max(n, 3)))));
    W = H = S; nodeR = n > 16 ? 14 : 19; font = n > 16 ? 11 : 13;
  }
  const X = (x) => pad + x * (W - 2 * pad), Y = (y) => pad + y * (H - 2 * pad);
  const pos = {}; g.nodes.forEach((nd) => { pos[nd.id] = [X(nd.x), Y(nd.y)]; });
  const C = (k, d) => cssVar(k, d);
  const nodeFill = {
    default: C('--net-node', '#e2e8f0'), src: C('--net-src', '#16a34a'), sink: C('--net-sink', '#ea580c'),
    left: C('--net-left', '#2563eb'), right: C('--net-right', '#8b5cf6'), current: C('--net-cur', '#f59e0b'),
    done: C('--net-done', '#bfdbfe'), pruned: C('--net-pruned', '#cbd5e1'), best: C('--net-best', '#22c55e'),
  };
  const nodeText = { src: '#fff', sink: '#fff', left: '#fff', right: '#fff', best: '#fff' };
  const edgeColor = {
    default: C('--net-edge', '#94a3b8'), path: C('--net-hl', '#8b5cf6'), mst: C('--net-src', '#16a34a'),
    assign: C('--net-assign', '#db2777'), flow: C('--net-flow', '#0ea5e9'), ship: C('--net-ship', '#14b8a6'),
    active: C('--net-cur', '#f59e0b'), reject: C('--bad', '#dc2626'), candidate: C('--net-cand', '#64748b'),
  };
  const maxv = Math.max(1e-9, ...g.edges.map((e) => +e.val || 0));
  const pairs = new Set(g.edges.map((e) => `${e.from}>${e.to}`));
  const ef = n > 16 ? 10.5 : 12;
  const txt = C('--txt', '#1e293b');
  let s = `<svg viewBox="0 0 ${W} ${H}" class="netsvg" role="img" aria-label="网络图" style="max-width:${Math.round(W * 1.2)}px">`;
  s += '<defs>';
  Object.entries(edgeColor).forEach(([cls, col]) => {
    s += `<marker id="arr-${cls}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${col}"/></marker>`;
  });
  s += '</defs>';
  const order = { default: 0, candidate: 1, reject: 2, flow: 3, ship: 3, mst: 4, assign: 4, path: 5, active: 6 };
  const edges = [...g.edges].sort((a, b) => (order[a.cls] || 0) - (order[b.cls] || 0));
  for (const e of edges) {
    const a = pos[e.from], b = pos[e.to]; if (!a || !b) continue;
    const cls = edgeColor[e.cls] ? e.cls : 'default';
    const col = edgeColor[cls];
    const w = cls === 'default' || cls === 'candidate' ? 1.8 : (cls === 'flow' || cls === 'ship' ? 2.4 + 6 * (+e.val || 0) / maxv : 3.6);
    const op = cls === 'default' ? 0.55 : 0.95;
    const dash = cls === 'reject' ? '6 5' : (cls === 'candidate' ? '4 4' : '');
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    const curved = g.directed && pairs.has(`${e.to}>${e.from}`);
    const off = curved ? Math.min(40, L * 0.18) : 0;
    const nx = -dy / L, ny = dx / L;
    const r = nodeR + 3;
    const cx = (a[0] + b[0]) / 2 + nx * off, cy = (a[1] + b[1]) / 2 + ny * off;
    const ua = [cx - a[0], cy - a[1]], ub = [cx - b[0], cy - b[1]];
    const la = Math.hypot(...ua) || 1, lb = Math.hypot(...ub) || 1;
    const ax = a[0] + ua[0] / la * r, ay = a[1] + ua[1] / la * r;
    const bx = b[0] + ub[0] / lb * (r + (g.directed ? 2 : 0)), by = b[1] + ub[1] / lb * (r + (g.directed ? 2 : 0));
    const anim = cls === 'active' ? ' class="e-active"' : '';
    s += `<path${anim} d="M${ax.toFixed(1)},${ay.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)}" fill="none" stroke="${col}" stroke-width="${w.toFixed(1)}" opacity="${op}" stroke-linecap="round" ${dash ? `stroke-dasharray="${dash}"` : ''} ${g.directed ? `marker-end="url(#arr-${cls})"` : ''}/>`;
    if (e.label) {
      const lx = 0.25 * ax + 0.5 * cx + 0.25 * bx, ly = 0.25 * ay + 0.5 * cy + 0.25 * by;
      const tw = String(e.label).length * ef * 0.62 + 6;
      s += `<rect x="${(lx - tw / 2).toFixed(1)}" y="${(ly - ef * 0.75).toFixed(1)}" width="${tw.toFixed(1)}" height="${(ef * 1.4).toFixed(1)}" rx="4" fill="var(--paper)" opacity="0.92"/>`;
      s += `<text x="${lx.toFixed(1)}" y="${(ly + ef * 0.38).toFixed(1)}" text-anchor="middle" font-size="${ef}" fill="${cls === 'default' ? txt : col}" font-weight="${cls === 'default' ? 400 : 700}">${esc(e.label)}</text>`;
    }
  }
  for (const nd of g.nodes) {
    const p = pos[nd.id];
    const grp = nodeFill[nd.group] ? nd.group : 'default';
    const ring = grp === 'current' ? ' class="n-cur"' : '';
    s += `<circle${ring} cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${nodeR}" fill="${nodeFill[grp]}" stroke="${C('--net-node-b', '#64748b')}" stroke-width="2"/>`;
    s += `<text x="${p[0].toFixed(1)}" y="${(p[1] + font / 3).toFixed(1)}" text-anchor="middle" font-size="${font}" font-weight="700" fill="${nodeText[grp] || txt}">${esc(nd.label)}</text>`;
    if (nd.sub) s += `<text x="${p[0].toFixed(1)}" y="${(p[1] + nodeR + font + 2).toFixed(1)}" text-anchor="middle" font-size="${font - 1}" fill="${C('--accent', '#2563eb')}" font-weight="600">${esc(nd.sub)}</text>`;
  }
  s += '</svg>';
  const clsNames = { default: '普通边', path: '路径 / 关键', mst: '选中边', flow: '有流量', ship: '运量', assign: '指派', active: '本步操作', reject: '拒绝 / 割', candidate: '候选' };
  const grpNames = { default: '节点', src: '源点 / 起点', sink: '汇点 / 终点', left: '产地 / 人员', right: '销地 / 任务', current: '本步焦点', done: '已确定', pruned: '剪枝 / 不可行', best: '当前最优' };
  const usedC = [...new Set(g.edges.map((e) => e.cls))].filter((c) => clsNames[c]);
  const usedG = [...new Set(g.nodes.map((x) => x.group))].filter((c) => grpNames[c]);
  s += '<div class="net-legend">' +
    usedC.map((c) => `<span class="nl"><i style="background:${edgeColor[c]}"></i>${clsNames[c]}</span>`).join('') +
    usedG.map((c) => `<span class="nl"><i class="dot" style="background:${nodeFill[c]}"></i>${grpNames[c]}</span>`).join('') + '</div>';
  return s;
}

/* ============================== 图表（Canvas） ============================== */
function setupCanvas(cv, aspect) {
  const dpr = (window.devicePixelRatio || 1) * (parseFloat(document.documentElement.style.zoom) || 1);
  const w = Math.max(320, Math.round(cv.clientWidth || cv.parentElement.clientWidth || 720));
  const h = Math.round(w * aspect);
  cv.style.height = h + 'px';
  cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, W: w, H: h };
}
function palette() {
  return [cssVar('--s1', '#2563eb'), cssVar('--s2', '#f59e0b'), cssVar('--s3', '#16a34a'), cssVar('--s4', '#db2777'), cssVar('--s5', '#8b5cf6')];
}
function niceTicks(lo, hi, n = 5) {
  const span = hi - lo || 1;
  const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= step0) || step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9 * span; v += step) out.push(+v.toFixed(10));
  return out;
}
function drawChart(cv, ch) {
  if (!ch) return;
  if (ch.type === 'plane') return drawPlane(cv, ch);
  if (ch.type === 'scatter') return drawScatter(cv, ch);
  return drawSeries(cv, ch);
}

function axesFrame(ctx, W, H, pad, title) {
  const txt = cssVar('--txt', '#1e293b');
  ctx.fillStyle = cssVar('--graph-bg', '#fff'); ctx.fillRect(0, 0, W, H);
  if (title) { ctx.fillStyle = txt; ctx.font = '600 13px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(title, pad.l, 8); }
}

function drawSeries(cv, ch) {
  const { ctx, W, H } = setupCanvas(cv, 0.56);
  const pad = { l: 58, r: 18, t: 54, b: 46 };
  const pal = palette();
  const txt = cssVar('--txt', '#1e293b'), grid = cssVar('--graph-grid', '#eef2f7'), muted = cssVar('--muted', '#64748b');
  axesFrame(ctx, W, H, pad, ch.title);
  const series = ch.series || [];
  const xs = ch.x || ch.xlabels || [];
  const n = Math.max(xs.length, ...series.map((s) => s.values.length), 1);
  const isBar = ch.type === 'bar';
  let lo = Infinity, hi = -Infinity;
  series.forEach((s) => s.values.forEach((v) => { if (v !== null && v !== undefined && isFinite(+v)) { lo = Math.min(lo, +v); hi = Math.max(hi, +v); } }));
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  if (isBar) lo = Math.min(0, lo);
  if (lo === hi) { lo -= 1; hi += 1; }
  const r0 = hi - lo; if (!isBar) lo -= r0 * 0.06; hi += r0 * 0.08;
  const numx = ch.numx && xs.length;
  const xmin = numx ? Math.min(...xs) : 0, xmax = numx ? Math.max(...xs) : n - 1;
  const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
  const slot = pw / n;
  const X = numx ? (v) => pad.l + (xmax > xmin ? (v - xmin) / (xmax - xmin) : 0.5) * pw
    : (i) => isBar ? pad.l + slot * (i + 0.5) : pad.l + (n > 1 ? i / (n - 1) : 0.5) * pw;
  const xi = (i) => numx ? X(+xs[i]) : X(i);
  const Y = (v) => pad.t + ph - ((v - lo) / (hi - lo)) * ph;
  ctx.font = '11px system-ui, sans-serif';
  niceTicks(lo, hi).forEach((v) => {
    const y = Y(v);
    ctx.strokeStyle = grid; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    ctx.fillStyle = muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(fmt(v), pad.l - 6, y);
  });
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = muted;
  if (numx) niceTicks(xmin, xmax, 8).forEach((v) => ctx.fillText(fmt(v), X(v), H - pad.b + 6));
  else { const stp = Math.max(1, Math.ceil(n / Math.floor(pw / 46))); for (let i = 0; i < xs.length; i += stp) ctx.fillText(String(xs[i]), xi(i), H - pad.b + 6); }
  if (ch.xtitle) { ctx.textAlign = 'right'; ctx.fillText(ch.xtitle, W - pad.r, H - 16); }
  ctx.strokeStyle = muted; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
  const bars = series.filter((s) => isBar && s.kind !== 'line');
  const bw = Math.max(2, slot * 0.8 / Math.max(1, bars.length));
  series.forEach((s, si) => {
    const col = s.color || pal[si % pal.length];
    if (isBar && s.kind !== 'line') {
      const k = bars.indexOf(s);
      ctx.fillStyle = col; ctx.globalAlpha = 0.85;
      s.values.forEach((v, i) => {
        if (v === null || v === undefined) return;
        const x = xi(i) - slot * 0.4 + k * bw, y0 = Y(Math.max(lo, 0)), y1 = Y(+v);
        ctx.fillRect(x, Math.min(y0, y1), bw - 1, Math.abs(y0 - y1));
      });
      ctx.globalAlpha = 1;
      return;
    }
    (s.shade || []).forEach(([a, b]) => {
      ctx.beginPath(); ctx.moveTo(xi(a), Y(Math.max(lo, 0)));
      for (let i = a; i <= b; i++) if (s.values[i] !== null) ctx.lineTo(xi(i), Y(+s.values[i]));
      ctx.lineTo(xi(b), Y(Math.max(lo, 0))); ctx.closePath();
      ctx.fillStyle = cssVar('--shade', 'rgba(220,38,38,.22)'); ctx.fill();
    });
    ctx.strokeStyle = col; ctx.lineWidth = 2.2; ctx.setLineDash(s.dashed ? [6, 4] : []);
    ctx.beginPath(); let pen = false;
    s.values.forEach((v, i) => {
      if (v === null || v === undefined || !isFinite(+v)) { pen = false; return; }
      const x = xi(i), y = Y(+v);
      if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; }
    });
    ctx.stroke(); ctx.setLineDash([]);
    if (n <= 60 && !numx) {
      ctx.fillStyle = col;
      s.values.forEach((v, i) => { if (v !== null && v !== undefined) { ctx.beginPath(); ctx.arc(xi(i), Y(+v), 2.8, 0, 7); ctx.fill(); } });
    }
  });
  if (ch.hl !== undefined && ch.hl !== null && ch.hl >= 0) {
    const x = xi(ch.hl);
    ctx.strokeStyle = cssVar('--net-cur', '#f59e0b'); ctx.lineWidth = 2; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, H - pad.b); ctx.stroke(); ctx.setLineDash([]);
    series.forEach((s, si) => {
      const v = s.values[ch.hl];
      if (v === null || v === undefined || (isBar && s.kind !== 'line')) return;
      ctx.fillStyle = cssVar('--net-cur', '#f59e0b'); ctx.beginPath(); ctx.arc(x, Y(+v), 5, 0, 7); ctx.fill();
    });
    const lab = ch.hl_label || (numx ? '' : String(xs[ch.hl] ?? ''));
    if (lab) { ctx.fillStyle = cssVar('--net-cur', '#f59e0b'); ctx.font = '600 12px system-ui'; ctx.textAlign = x > W - 120 ? 'right' : 'left'; ctx.textBaseline = 'top'; ctx.fillText(lab, x + (x > W - 120 ? -6 : 6), pad.t + 2); }
  }
  legend(ctx, series.map((s, si) => ({ name: s.name, col: s.color || pal[si % pal.length], dashed: s.dashed })), pad.l, 30, txt);
}
function legend(ctx, items, x, y, txt) {
  ctx.font = '12px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  items.forEach((it) => {
    if (!it.name) return;
    ctx.strokeStyle = it.col; ctx.lineWidth = 3; ctx.setLineDash(it.dashed ? [5, 3] : []);
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 18, y); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = txt; ctx.fillText(it.name, x + 23, y);
    x += 23 + ctx.measureText(it.name).width + 16;
  });
}

function drawScatter(cv, ch) {
  const { ctx, W, H } = setupCanvas(cv, 0.62);
  const pad = { l: 58, r: 20, t: 40, b: 46 };
  axesFrame(ctx, W, H, pad, ch.title);
  const pts = ch.points || [];
  const allx = pts.map((p) => p[0]).concat((ch.line || []).map((p) => p[0]));
  const ally = pts.map((p) => p[1]).concat((ch.line || []).map((p) => p[1]));
  let [x0, x1, y0, y1] = [Math.min(...allx), Math.max(...allx), Math.min(...ally), Math.max(...ally)];
  const dx = (x1 - x0) || 1, dy = (y1 - y0) || 1; x0 -= dx * 0.08; x1 += dx * 0.08; y0 -= dy * 0.1; y1 += dy * 0.1;
  const X = (v) => pad.l + (v - x0) / (x1 - x0) * (W - pad.l - pad.r), Y = (v) => H - pad.b - (v - y0) / (y1 - y0) * (H - pad.t - pad.b);
  axesTicks(ctx, W, H, pad, x0, x1, y0, y1, X, Y, ch.xtitle, ch.ytitle);
  const pal = palette();
  if (ch.line) {
    ctx.strokeStyle = pal[1]; ctx.lineWidth = 2.4; ctx.beginPath();
    ch.line.forEach((p, i) => (i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])))); ctx.stroke();
  }
  ctx.fillStyle = pal[0];
  pts.forEach((p) => { ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 4.5, 0, 7); ctx.fill(); });
  legend(ctx, [{ name: '数据点', col: pal[0] }].concat(ch.line ? [{ name: '回归直线', col: pal[1] }] : []), pad.l, 28, cssVar('--txt', '#1e293b'));
}

function axesTicks(ctx, W, H, pad, x0, x1, y0, y1, X, Y, xt, yt) {
  const grid = cssVar('--graph-grid', '#eef2f7'), muted = cssVar('--muted', '#64748b');
  ctx.font = '11px system-ui, sans-serif';
  niceTicks(y0, y1).forEach((v) => {
    ctx.strokeStyle = grid; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pad.l, Y(v)); ctx.lineTo(W - pad.r, Y(v)); ctx.stroke();
    ctx.fillStyle = muted; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(fmt(v), pad.l - 6, Y(v));
  });
  niceTicks(x0, x1, 7).forEach((v) => {
    ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(X(v), pad.t); ctx.lineTo(X(v), H - pad.b); ctx.stroke();
    ctx.fillStyle = muted; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(fmt(v), X(v), H - pad.b + 6);
  });
  ctx.strokeStyle = muted; ctx.strokeRect(pad.l, pad.t, W - pad.l - pad.r, H - pad.t - pad.b);
  ctx.fillStyle = muted;
  if (xt) { ctx.textAlign = 'right'; ctx.textBaseline = 'top'; ctx.fillText(xt, W - pad.r, H - 18); }
  if (yt) { ctx.textAlign = 'left'; ctx.textBaseline = 'bottom'; ctx.fillText(yt, pad.l + 4, pad.t - 4); }
}

/* 平面图：函数热力图 + 等高线 + 不可行区 + 约束线 + 迭代路径 */
function drawPlane(cv, ch) {
  cv.classList.add('plane');
  const pad = { l: 56, r: 20, t: 54, b: 44 };
  const cw0 = Math.max(320, cv.clientWidth || 640);
  const { ctx, W, H } = setupCanvas(cv, (cw0 - pad.l - pad.r + pad.t + pad.b) / cw0);
  axesFrame(ctx, W, H, pad, ch.title);
  const [x0, x1] = ch.xr, [y0, y1] = ch.yr;
  const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
  const X = (v) => pad.l + (v - x0) / (x1 - x0) * pw, Y = (v) => pad.t + ph - (v - y0) / (y1 - y0) * ph;
  ctx.save(); ctx.beginPath(); ctx.rect(pad.l, pad.t, pw, ph); ctx.clip();
  if (ch.grid) {
    const G = ch.grid, ny = G.length, nx = G[0].length;
    const vals = G.flat().filter((v) => v !== null && isFinite(v)).sort((a, b) => a - b);
    const rank = (v) => { let lo = 0, hi = vals.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (vals[m] < v) lo = m + 1; else hi = m; } return lo / Math.max(1, vals.length - 1); };
    const cLo = hexRGB(cssVar('--plane-lo', '#eff6ff')), cHi = hexRGB(cssVar('--plane-hi', '#1d4ed8'));
    const cw = pw / (nx - 1), chh = ph / (ny - 1);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const v = G[j][i]; if (v === null) continue;
      const t = Math.pow(rank(v), 0.8);
      ctx.fillStyle = `rgb(${cLo.map((c, k) => Math.round(c + (cHi[k] - c) * t)).join(',')})`;
      ctx.fillRect(X(x0 + (x1 - x0) * i / (nx - 1)) - cw / 2, Y(y0 + (y1 - y0) * j / (ny - 1)) - chh / 2, cw + 1, chh + 1);
    }
    // 等高线：取 12 个分位数水平，marching squares
    ctx.strokeStyle = cssVar('--contour', 'rgba(15,23,42,.28)'); ctx.lineWidth = 1;
    const levels = [0.04, 0.1, 0.18, 0.27, 0.37, 0.48, 0.6, 0.72, 0.84, 0.94].map((q) => vals[Math.floor(q * (vals.length - 1))]);
    const gx = (i) => X(x0 + (x1 - x0) * i / (nx - 1)), gy = (j) => Y(y0 + (y1 - y0) * j / (ny - 1));
    levels.forEach((lv) => {
      ctx.beginPath();
      for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
        const a = G[j][i], b = G[j][i + 1], c = G[j + 1][i + 1], d = G[j + 1][i];
        if ([a, b, c, d].some((v) => v === null)) continue;
        const pts = [];
        const edge = (v1, v2, p1, p2) => { if ((v1 - lv) * (v2 - lv) < 0) { const t = (lv - v1) / (v2 - v1); pts.push([p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t]); } };
        const P = [[gx(i), gy(j)], [gx(i + 1), gy(j)], [gx(i + 1), gy(j + 1)], [gx(i), gy(j + 1)]];
        edge(a, b, P[0], P[1]); edge(b, c, P[1], P[2]); edge(c, d, P[2], P[3]); edge(d, a, P[3], P[0]);
        for (let k = 0; k + 1 < pts.length; k += 2) { ctx.moveTo(pts[k][0], pts[k][1]); ctx.lineTo(pts[k + 1][0], pts[k + 1][1]); }
      }
      ctx.stroke();
    });
  }
  if (ch.mask) {
    const M = ch.mask, ny = M.length, nx = M[0].length, cw = pw / (nx - 1), chh = ph / (ny - 1);
    ctx.fillStyle = cssVar('--infeasible', 'rgba(71,85,105,.45)');
    const region = new Path2D();
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) if (M[j][i]) region.rect(X(x0 + (x1 - x0) * i / (nx - 1)) - cw / 2 - 0.5, Y(y0 + (y1 - y0) * j / (ny - 1)) - chh / 2 - 0.5, cw + 1, chh + 1);
    ctx.fill(region, 'nonzero');
  }
  const active = new Set(ch.active || []);
  (ch.lines || []).forEach((L, k) => {
    const on = active.has(k);
    ctx.strokeStyle = on ? cssVar('--net-cur', '#f59e0b') : cssVar('--graph-line', '#2563eb');
    ctx.lineWidth = on ? 3.2 : 1.6; ctx.setLineDash(L.kind === 'goal' ? [7, 5] : []);
    ctx.beginPath();
    if (Math.abs(L.a2) < 1e-12) { const x = L.b / L.a1; ctx.moveTo(X(x), Y(y0)); ctx.lineTo(X(x), Y(y1)); }
    else { const f = (x) => (L.b - L.a1 * x) / L.a2; ctx.moveTo(X(x0), Y(f(x0))); ctx.lineTo(X(x1), Y(f(x1))); }
    ctx.stroke(); ctx.setLineDash([]);
    // 约束线标签：放在可见段的中点
    let px, py;
    if (Math.abs(L.a2) < 1e-12) { px = L.b / L.a1; py = y0 + (y1 - y0) * 0.92; }
    else { px = x0 + (x1 - x0) * (0.15 + 0.12 * (k % 6)); py = (L.b - L.a1 * px) / L.a2; }
    if (px >= x0 && px <= x1 && py >= y0 && py <= y1 && L.label) {
      ctx.fillStyle = ctx.strokeStyle; ctx.font = `${on ? 700 : 500} 11px system-ui`; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
      ctx.fillText(L.label, X(px) + 4, Y(py) - 3);
    }
  });
  ctx.restore();
  axesTicks(ctx, W, H, pad, x0, x1, y0, y1, X, Y, ch.xlabel, ch.ylabel);
  const path = ch.path || [];
  const upto = ch.upto === undefined || ch.upto === null ? path.length - 1 : ch.upto;
  const pc = cssVar('--path', '#f97316');
  if (path.length) {
    ctx.strokeStyle = pc; ctx.lineWidth = 2.2; ctx.beginPath();
    for (let i = 0; i <= upto && i < path.length; i++) (i ? ctx.lineTo(X(path[i][0]), Y(path[i][1])) : ctx.moveTo(X(path[i][0]), Y(path[i][1])));
    ctx.stroke();
    ctx.fillStyle = pc;
    for (let i = 0; i <= upto && i < path.length; i++) { ctx.beginPath(); ctx.arc(X(path[i][0]), Y(path[i][1]), 2.6, 0, 7); ctx.fill(); }
    const cur = path[Math.min(upto, path.length - 1)];
    ctx.beginPath(); ctx.arc(X(cur[0]), Y(cur[1]), 6.5, 0, 7); ctx.fillStyle = pc; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    (ch.marks || []).filter((m) => m.i <= upto && m.i < path.length).forEach((m) => {
      const p = path[m.i];
      ctx.fillStyle = cssVar('--txt', '#1e293b'); ctx.font = '600 11px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
      ctx.fillText(m.label, X(p[0]) + 7, Y(p[1]) - 5);
    });
    if (ch.label) { ctx.fillStyle = pc; ctx.font = '700 12px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(`${ch.label} (${fmt(cur[0])}, ${fmt(cur[1])})`, X(cur[0]) + 9, Y(cur[1]) + 6); }
  }
  (ch.pts || []).forEach((p) => {
    ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 7, 0, 7); ctx.fillStyle = pc; ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    if (ch.label) { ctx.fillStyle = pc; ctx.font = '700 12px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(ch.label, X(p[0]) + 10, Y(p[1]) + 6); }
  });
  const items = [];
  if (ch.grid) items.push({ name: '越亮 = 函数值越小', col: cssVar('--plane-lo', '#fff3c4') });
  if (ch.mask) items.push({ name: '阴影 = 不可行', col: cssVar('--infeasible', 'rgba(71,85,105,.6)') });
  if (path.length || (ch.pts || []).length) items.push({ name: path.length ? '迭代路径' : '当前解', col: pc });
  if ((ch.lines || []).length) items.push({ name: active.size ? '橙线 = 起作用约束' : '约束线', col: active.size ? cssVar('--net-cur', '#f59e0b') : cssVar('--graph-line', '#2563eb') });
  legend(ctx, items, pad.l, 32, cssVar('--txt', '#1e293b'));
}
function hexRGB(c) {
  const m = c.match(/^#([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map((k) => parseInt(m[1].slice(k, k + 2), 16));
  const r = c.match(/\d+(\.\d+)?/g);
  return r ? r.slice(0, 3).map(Number) : [200, 200, 200];
}
function parseList(s) {
  return String(s).split(/[\s,，;；]+/).filter((x) => x !== '').map((x) => { const n = Number(x); return isNaN(n) ? x : n; });
}
function parseMatrix(s) {
  return String(s).split(/\n+/).map((r) => r.trim()).filter((r) => r !== '').map(parseList);
}function stepExplain(st, idx, res, payload) {
  const p = st.pivot;
  const xs = (st.x || []).map((v, i) => `x${i + 1}=${fmt(v)}`).join('，');
  const minNote = payload.obj === 'min' ? '（min 问题按 max(−z) 求解，表中检验数与目标行为 −z 的数值）' : '';
  if (!p) {
    const art = st.artificial_in_basis || [];
    return `初始单纯形表：以松弛变量${art.length ? '和人工变量' : ''}为初始基。当前基可行解 ${xs}，真实目标值 ${fmt(st.real_objective)}。` +
      (art.length ? `表中 M 表示大 M（本题取 M = ${fmt(res.big_m)}）。` : '') +
      (art.length ? `人工变量 ${art.join('、')} 仍在基中且取正值，大 M 惩罚会迫使它们尽快离基。` : '') + minNote;
  }
  let t = `${p.enter} 进基（${p.rule === 'Bland' ? 'Bland 规则：下标最小的正检验数' : '检验数最大，Dantzig 规则'}），按最小比值规则 ${p.leave} 离基（第 ${p.row + 1} 行）。`;
  if (p.degenerate) t += '这是一次<b>退化枢轴</b>：最小比值为 0，目标值没有变化，下一步改用 Bland 规则防止循环。';
  t += `新的基可行解 ${xs}，真实目标值 ${fmt(st.real_objective)}。`;
  if (idx === res.steps.length - 1 && res.status === 'optimal') t += '所有检验数都 ≤ 0，已达最优。';
  return t;
}
/* 大 M 法的表中会出现 a·M + b 形式的数，按符号显示更易读 */
function fmtM(v, M) {
  if (!M || typeof v !== 'number' || Math.abs(v) < M * 0.5) return fmt(v);
  const a = Math.round(v / M), b = v - a * M;
  const head = a === 1 ? 'M' : (a === -1 ? '−M' : `${a}M`);
  if (Math.abs(b) < 1e-6) return head;
  return `${head}${b > 0 ? '+' : '−'}${fmt(Math.abs(b))}`;
}
function simplexTable(st, M) {
  const p = st.pivot, cols = st.columns.length;
  const enterIdx = p ? st.columns.indexOf(p.enter) : -1, rowIdx = p ? p.row : -1;
  let h = '<div class="tblwrap"><table class="tab"><thead><tr><th>基</th>';
  st.columns.forEach((cn, i) => { h += `<th class="${i === enterIdx ? 'enter-hl' : ''}">${esc(cn)}</th>`; });
  h += '<th>RHS</th></tr></thead><tbody>';
  st.rows.forEach((row, i) => {
    h += `<tr class="${i === rowIdx ? 'row-hl' : ''}"><td class="base">${esc(st.basis[i] || '')}</td>`;
    for (let j = 0; j < cols; j++) h += `<td class="${i === rowIdx && j === enterIdx ? 'pivot-hl' : (j === enterIdx ? 'col-hl' : '')}">${esc(fmtM(row[j], M))}</td>`;
    h += `<td>${esc(fmtM(row[cols], M))}</td></tr>`;
  });
  h += '<tr class="objrow"><td class="base">检验数</td>';
  for (let j = 0; j < cols; j++) h += `<td>${esc(fmtM(st.objective[j], M))}</td>`;
  return h + `<td>${esc(fmtM(st.objective[cols], M))}</td></tr></tbody></table></div>`;
}
function sensRange(r) {
  const [lo, hi] = r.range;
  if (lo === null && hi === null) return '(−∞, +∞)';
  if (lo === null) return `(−∞, ${fmt(hi)}]`;
  if (hi === null) return `[${fmt(lo)}, +∞)`;
  return `[${fmt(lo)}, ${fmt(hi)}]`;
}
const inf = (v) => (v === null || v === undefined ? '∞' : fmt(v));
function sensitivityHTML(sens) {
  let h = '<h4>右端（RHS）灵敏度：最优基不变时右端的可变范围</h4>';
  h += tableHTML({ headers: ['约束', '右端 b', '影子价格', '允许增加', '允许减少', '有效范围'], rows: sens.rhs.map((r) => [r.name, r.value, r.shadow, inf(r.allow_inc), inf(r.allow_dec), sensRange(r)]) });
  h += '<h4>目标系数灵敏度：最优基不变时 c 的可变范围</h4>';
  h += tableHTML({ headers: ['变量', 'c', '检验数', '允许增加', '允许减少', '有效范围'], rows: sens.objective.map((r) => [r.name, r.value, r.reduced_cost, inf(r.allow_inc), inf(r.allow_dec), sensRange(r)]) });
  return h + '<p class="desc small">在有效范围内单独调整一个右端或目标系数，最优基（哪些变量为正）不变；超出范围最优基就会切换。</p>';
}
function feasiblePolygon(lines, xmax, ymax) {
  let poly = [[0, 0], [xmax, 0], [xmax, ymax], [0, ymax]];
  const clip = (P, f) => {     // 保留 f(p) <= 0 的部分
    const out = [];
    for (let i = 0; i < P.length; i++) {
      const a = P[i], b = P[(i + 1) % P.length], fa = f(a), fb = f(b);
      if (fa <= 1e-9) out.push(a);
      if ((fa < -1e-9 && fb > 1e-9) || (fa > 1e-9 && fb < -1e-9)) { const t = fa / (fa - fb); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
    }
    return out;
  };
  for (const L of lines) {
    const f = (p) => L.a1 * p[0] + L.a2 * p[1] - L.b;
    if (L.sense === 'le' || L.sense === 'eq') poly = clip(poly, f);
    if (L.sense === 'ge' || L.sense === 'eq') poly = clip(poly, (p) => -f(p));
    if (poly.length < 2) return [];
  }
  return poly;
}
function drawLPGraph(cv, g, trail) {
  const { ctx, W, H } = setupCanvas(cv, 0.78);
  const pad = { l: 50, r: 20, t: 26, b: 40 };
  axesFrame(ctx, W, H, pad, '');
  const vs = g.vertices || [];
  let x1 = 1, y1 = 1;
  vs.concat([g.optimum]).forEach((v) => { x1 = Math.max(x1, v[0]); y1 = Math.max(y1, v[1]); });
  x1 *= 1.25; y1 *= 1.25;
  const X = (v) => pad.l + v / x1 * (W - pad.l - pad.r), Y = (v) => H - pad.b - v / y1 * (H - pad.t - pad.b);
  axesTicks(ctx, W, H, pad, 0, x1, 0, y1, X, Y, 'x1', 'x2');
  ctx.save(); ctx.beginPath(); ctx.rect(pad.l, pad.t, W - pad.l - pad.r, H - pad.t - pad.b); ctx.clip();
  const hull = feasiblePolygon(g.lines, x1, y1);
  if (hull.length > 2) {
    ctx.beginPath(); hull.forEach((p, i) => (i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])))); ctx.closePath();
    ctx.fillStyle = cssVar('--graph-hull', 'rgba(21,128,61,.16)'); ctx.fill();
    ctx.strokeStyle = cssVar('--graph-hullline', 'rgba(21,128,61,.55)'); ctx.lineWidth = 1.2; ctx.stroke();
  }
  ctx.strokeStyle = cssVar('--graph-line', '#2563eb'); ctx.lineWidth = 1.5;
  g.lines.forEach((L) => {
    ctx.beginPath();
    if (L.vertical) { const x = L.b / (L.a1 || 1); ctx.moveTo(X(x), Y(0)); ctx.lineTo(X(x), Y(y1)); }
    else { const f = (x) => (L.b - L.a1 * x) / L.a2; ctx.moveTo(X(0), Y(f(0))); ctx.lineTo(X(x1), Y(f(x1))); }
    ctx.stroke();
  });
  if (g.iso_line) {
    ctx.strokeStyle = cssVar('--graph-iso', '#d97706'); ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    const sl = g.iso_line.slope, [ox, oy] = g.iso_line.through, f = (x) => oy + sl * (x - ox);
    ctx.beginPath(); ctx.moveTo(X(0), Y(f(0))); ctx.lineTo(X(x1), Y(f(x1))); ctx.stroke(); ctx.setLineDash([]);
  }
  ctx.restore();
  const dot = (x, y, c, r) => { ctx.beginPath(); ctx.fillStyle = c; ctx.arc(x, y, r, 0, 7); ctx.fill(); };
  vs.forEach((v) => dot(X(v[0]), Y(v[1]), cssVar('--graph-vertex', '#94a3b8'), 3.5));
  const op = g.optimum, oc = cssVar('--graph-opt', '#15803d');
  dot(X(op[0]), Y(op[1]), oc, 6.5);
  ctx.fillStyle = oc; ctx.font = '600 12.5px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
  ctx.fillText(`最优 (${fmt(op[0])}, ${fmt(op[1])})  z=${fmt(g.objective_value)}`, X(op[0]) + 9, Y(op[1]) - 6);
  if (trail && trail.length) {
    const pc = cssVar('--graph-path', '#8b5cf6');
    ctx.strokeStyle = pc; ctx.lineWidth = 2.4; ctx.setLineDash([6, 3]); ctx.beginPath();
    trail.forEach((p, i) => (i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])))); ctx.stroke(); ctx.setLineDash([]);
    trail.forEach((p, i) => {
      const last = i === trail.length - 1;
      dot(X(p[0]), Y(p[1]), last ? cssVar('--graph-path-cur', '#7c3aed') : pc, last ? 7 : 4);
      ctx.fillStyle = pc; ctx.font = '11px system-ui'; ctx.textBaseline = 'top'; ctx.fillText(`第${i}步`, X(p[0]) + 8, Y(p[1]) + 4);
    });
  }
  legend(ctx, [{ name: '可行域', col: cssVar('--graph-hullline', '#15803d') }, { name: '约束线', col: cssVar('--graph-line', '#2563eb') },
    { name: '目标等值线', col: cssVar('--graph-iso', '#d97706'), dashed: true }, { name: '单纯形路径', col: cssVar('--graph-path', '#8b5cf6'), dashed: true }], pad.l + 6, 12, cssVar('--txt', '#1e293b'));
}

/* ============================== 侧栏：模块列表与搜索 ============================== */
function buildNav(filter = '') {
  const nav = $('#module-nav');
  const q = filter.trim().toLowerCase();
  const hit = (m) => !q || [m.name, m.name_en, m.id, m.category, m.desc].join(' ').toLowerCase().includes(q);
  const cats = {};
  state.modules.filter(hit).forEach((m) => { (cats[m.category] = cats[m.category] || []).push(m); });
  let h = '';
  for (const [cat, ms] of Object.entries(cats)) {
    if (cat !== '—') h += `<div class="nav-cat">${esc(cat)}</div>`;
    h += ms.map((m) => `<button type="button" class="nav-item${state.m && state.m.id === m.id ? ' active' : ''}" data-id="${esc(m.id)}" title="${esc(m.name)}">` +
      `<span class="ico">${esc(m.icon || '')}</span><span>${esc(m.name)}</span>${m.status === 'ready' ? '' : '<span class="tag">不可用</span>'}</button>`).join('');
  }
  nav.innerHTML = h || '<div class="nav-empty">没有匹配的模块</div>';
  $$('.nav-item', nav).forEach((b) => { b.onclick = () => openModule(b.dataset.id); });
}

/* ============================== 打开模块 ============================== */
function openModule(mid, push = true) {
  const m = state.modules.find((x) => x.id === mid) || state.modules[0];
  if (state.m && state.m.id !== m.id) saveInputs();
  state.m = m;
  Player.stopAll(); state.redraw = [];
  if (push && location.hash.slice(1) !== m.id) history.replaceState(null, '', '#' + m.id);
  $$('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.id === m.id));
  $('#mod-title').textContent = `${m.icon || ''} ${m.name}`;
  $('#mod-en').textContent = m.name_en;
  document.title = `${m.name} · QSB Studio`;
  applyInputWidth();
  if (m.id === 'lp') buildLPInputs(); else buildGenericInputs(m);
  document.body.classList.remove('nav-open');
  $('#stage').scrollTop = 0;
  if (state.results[m.id]) renderStage(state.results[m.id]);
  else solve();
}

/* ============================== 输入面板：通用模块 ============================== */
const rowsFor = (v, min) => Math.max(+min || 3, Math.min(14, String(v).split('\n').length + 1));   // 文本框高度贴合内容
function fieldHTML(f, saved) {
  const id = esc(f.id);
  const v = saved && saved[f.id] !== undefined ? saved[f.id] : (f.value ?? '');
  let inner;
  switch (f.type) {
    case 'int': inner = `<input type="number" step="1" data-id="${id}" data-type="num" value="${esc(v)}">`; break;
    case 'float': inner = `<input type="number" step="any" data-id="${id}" data-type="num" value="${esc(v)}">`; break;
    case 'select':
      inner = `<select data-id="${id}" data-type="select">` + (f.options || []).map((o) => {
        const ov = typeof o === 'object' ? o.v : o, ot = typeof o === 'object' ? (o.t ?? o.v) : o;
        return `<option value="${esc(ov)}" ${String(ov) === String(v) ? 'selected' : ''}>${esc(ot)}</option>`;
      }).join('') + '</select>';
      break;
    case 'matrix': inner = `<textarea rows="${rowsFor(v, f.rows || 4)}" data-id="${id}" data-type="matrix" spellcheck="false">${esc(v)}</textarea>`; break;
    case 'textarea': inner = `<textarea rows="${rowsFor(v, f.rows || 5)}" data-id="${id}" data-type="text" spellcheck="false">${esc(v)}</textarea>`; break;
    case 'list': inner = `<input type="text" data-id="${id}" data-type="list" value="${esc(v)}" spellcheck="false">`; break;
    default: inner = `<input type="text" data-id="${id}" data-type="text" value="${esc(v)}" spellcheck="false">`;
  }
  const help = f.help ? `<small>${f.help}</small>` : '';   // help 为服务端可信文案（含 <b>）
  return `<label class="field">` + `<span>${esc(f.label || f.id)}</span>${inner}${help}</label>`;
}
function buildGenericInputs(m) {
  const saved = store.get('qsb-in-' + m.id, null);
  const box = $('#inputs');
  box.innerHTML = `<p class="lead">${esc(m.desc)}</p>` +
    (m.form || []).map((f) => fieldHTML(f, saved)).join('') +
    `<p class="hint">输入会自动保存。改完按 ${MOD} + Enter 求解。</p>`;
  box.oninput = debounce(saveInputs, 300);
}
function readGenericInputs(raw) {
  const p = {};
  $$('#inputs [data-id]').forEach((el) => {
    const t = el.dataset.type, k = el.dataset.id, v = el.value;
    if (raw) p[k] = v;
    else if (t === 'num') p[k] = v.trim();
    else if (t === 'matrix') p[k] = parseMatrix(v);
    else if (t === 'list') p[k] = parseList(v);
    else p[k] = v;
  });
  return p;
}
function saveInputs() {
  const m = state.m; if (!m) return;
  if (m.id === 'lp') { if ($('#lp-model')) store.set('qsb-in-lp', collectModel(true)); }
  else store.set('qsb-in-' + m.id, readGenericInputs(true));
}

/* ============================== 输入面板：线性规划 ============================== */
function buildLPInputs() {
  const box = $('#inputs');
  box.innerHTML = `
    <p class="lead">首行是目标函数，下面每行是一条约束：Σ 系数 × 变量（≤ / ≥ / =）右端常数。所有变量默认 ≥ 0。</p>
    <label class="field"><span>载入例题</span><select id="lp-examples"><option value="">— 选择例题 —</option>${Object.entries(LP_EXAMPLES).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('')}</select></label>
    <div class="lp-dims">
      <label class="field"><span>目标</span><select id="lp-obj"><option value="max">最大化</option><option value="min">最小化</option></select></label>
      <label class="field"><span>变量数</span><input type="number" id="lp-nvar" min="1" max="40" value="2"></label>
      <label class="field"><span>约束数</span><input type="number" id="lp-ncon" min="1" max="120" value="3"></label>
    </div>
    <div class="model" id="lp-model"></div>
    <p class="hint">输入会自动保存。改完按 ${MOD} + Enter 求解；拖动右侧分隔线可加宽本区。</p>`;
  const saved = store.get('qsb-in-lp', null);
  if (saved && saved.c) loadModel(saved); else loadModel(LP_EXAMPLES.classic);
  $('#lp-examples').onchange = (e) => { if (e.target.value) { loadModel(LP_EXAMPLES[e.target.value]); saveInputs(); solve(); } e.target.value = ''; };
  ['lp-nvar', 'lp-ncon', 'lp-obj'].forEach((id) => { $('#' + id).onchange = () => { buildModel(true); saveInputs(); }; });
  box.oninput = debounce(saveInputs, 300);
}
function buildModel(keep) {
  const nvar = Math.max(1, Math.min(40, +$('#lp-nvar').value || 1));
  const ncon = Math.max(1, Math.min(120, +$('#lp-ncon').value || 1));
  const old = keep ? collectModel(true) : null;
  const val = (a, d) => (a !== undefined && a !== null && a !== '' ? a : d);
  let h = '<table class="modeltab"><thead><tr><th></th>';
  for (let i = 1; i <= nvar; i++) h += `<th>x${i}</th>`;
  h += '<th></th><th>b</th></tr></thead><tbody>';
  h += `<tr class="objrow"><td class="rowlabel">${$('#lp-obj').value === 'max' ? 'max z' : 'min z'}</td>`;
  for (let i = 0; i < nvar; i++) h += `<td><input class="cobj" data-i="${i}" value="${esc(val(old && old.c[i], 1))}" inputmode="decimal" aria-label="目标系数 x${i + 1}"></td>`;
  h += '<td></td><td></td></tr>';
  for (let i = 0; i < ncon; i++) {
    h += `<tr><td class="rowlabel">约束 ${i + 1}</td>`;
    for (let j = 0; j < nvar; j++) h += `<td><input class="ca" data-r="${i}" data-c="${j}" value="${esc(val(old && old.A[i] && old.A[i][j], 0))}" inputmode="decimal" aria-label="约束${i + 1} x${j + 1} 系数"></td>`;
    const sv = old && old.senses[i] ? old.senses[i] : 'le';
    h += `<td><select class="sense" data-i="${i}" aria-label="约束${i + 1} 关系">${[['le', '≤'], ['ge', '≥'], ['eq', '=']].map(([v, t]) => `<option value="${v}" ${v === sv ? 'selected' : ''}>${t}</option>`).join('')}</select></td>`;
    h += `<td><input class="cb" data-i="${i}" value="${esc(val(old && old.b[i], 1))}" inputmode="decimal" aria-label="约束${i + 1} 右端"></td></tr>`;
  }
  $('#lp-model').innerHTML = h + '</tbody></table>';
}
function loadModel(ex) {
  $('#lp-obj').value = ex.obj; $('#lp-nvar').value = ex.c.length; $('#lp-ncon').value = ex.A.length;
  buildModel(false);
  ex.c.forEach((v, i) => { $(`.cobj[data-i="${i}"]`).value = v; });
  ex.A.forEach((row, i) => row.forEach((v, j) => { $(`.ca[data-r="${i}"][data-c="${j}"]`).value = v; }));
  ex.b.forEach((v, i) => { $(`.cb[data-i="${i}"]`).value = v; });
  ex.senses.forEach((s, i) => { $(`.sense[data-i="${i}"]`).value = s; });
}
function collectModel(raw) {
  const num = (el) => (raw ? el.value : Number(el.value.trim() === '' ? 0 : el.value));
  const c = $$('.cobj').map(num), b = $$('.cb').map(num), senses = $$('.sense').map((el) => el.value);
  const A = b.map((_, i) => c.map((__, j) => num($(`.ca[data-r="${i}"][data-c="${j}"]`))));
  return { obj: $('#lp-obj').value, c, A, b, senses, var_names: c.map((_, i) => 'x' + (i + 1)) };
}

/* ============================== 求解 ============================== */
async function solve() {
  const m = state.m; if (!m) return;
  saveInputs();
  const btn = $('#solve-btn'); btn.disabled = true;
  const inner = $('#stage-inner');
  if (!state.results[m.id]) inner.innerHTML = '<div class="busy">正在求解…</div>';
  let res, payload;
  try {
    if (m.id === 'lp') {
      payload = collectModel(false);
      if ([...payload.c, ...payload.b, ...payload.A.flat()].some((v) => !isFinite(v))) {
        res = { status: 'error', message: '模型表中有不是数字的系数，请检查后再求解。' };
      } else res = await postJSON('/api/solve/lp', payload);
    } else res = await postJSON(`/api/solve/${m.id}`, readGenericInputs(false));
  } catch (e) {
    res = { status: 'error', headline: '无法连接求解服务', message: '内置服务没有响应。请关闭程序后重新打开。' };
  } finally { btn.disabled = false; }
  if (state.m !== m) return;          // 求解期间已切换模块
  state.results[m.id] = { res, payload, mid: m.id };
  renderStage(state.results[m.id]);
}

/* ============================== 舞台：结果分页 ============================== */
function verdictHTML(res, headline) {
  const st = res.status;
  return `<div class="verdict"><span class="badge ${GOOD.has(st) ? 'good' : 'bad'}">${esc(STATUS[st] || st)}</span>` +
    (headline ? `<span class="headline">${esc(headline)}</span>` : '') + '</div>' +
    (res.message ? `<div class="msg ${st === 'error' ? '' : 'warn'}">${esc(res.message)}</div>` : '');
}
function renderStage(entry) {
  Player.stopAll(); state.redraw = [];
  const { res, mid } = entry;
  const m = state.modules.find((x) => x.id === mid);
  const isLP = mid === 'lp';
  const tabs = [];
  const steps = res.steps || [];
  if (steps.length) tabs.push(['demo', '演示', steps.length]);
  if (isLP ? res.status === 'optimal' : (res.tables || []).length || res.graph || res.chart) tabs.push(['result', '结果']);
  if (isLP && res.sensitivity) tabs.push(['sens', '灵敏度']);
  tabs.push(['theory', '原理']);
  let cur = state.tab[mid];
  if (!tabs.some((t) => t[0] === cur)) cur = tabs[0][0];
  state.tab[mid] = cur;
  const headline = isLP && res.status === 'optimal' ? `${entry.payload.obj === 'max' ? '最大' : '最小'}值 z = ${fmt(res.objective)}` : res.headline;
  const inner = $('#stage-inner');
  inner.innerHTML = verdictHTML(res, headline) +
    `<div class="tabs" role="tablist">${tabs.map(([k, t, n]) => `<button type="button" role="tab" class="stab${k === cur ? ' active' : ''}" data-tab="${k}">${t}${n ? `<span class="n">${n} 步</span>` : ''}</button>`).join('')}</div>` +
    '<div id="tab-body"></div>';
  $$('.stab', inner).forEach((b) => { b.onclick = () => { state.tab[mid] = b.dataset.tab; renderStage(entry); }; });
  const body = $('#tab-body');
  if (cur === 'demo') (isLP ? renderLPDemo : renderDemo)(body, entry);
  else if (cur === 'result') (isLP ? renderLPResult : renderResult)(body, entry);
  else if (cur === 'sens') body.innerHTML = `<div class="sheet">${sensitivityHTML(res.sensitivity)}</div>`;
  else body.innerHTML = theoryHTML(m, res);
}
function theoryHTML(m, res) {
  let h = '';
  if (res.notes && res.notes.length) h += `<div class="sheet notes"><h3>本题要点</h3><ul>${res.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>`;
  if (m && m.explain) h += `<div class="sheet explain"><h3>算法原理</h3>${m.explain}</div>`;   // explain 为服务端可信文案
  return h || '<div class="empty"><b>暂无说明</b></div>';
}
function renderDemo(body, entry) {
  body.innerHTML = '<div id="player"></div>';
  new Player($('#player'), entry.res.steps, { shared: entry.res.shared });
}
function renderResult(body, entry) {
  const res = entry.res;
  let h = '';
  if (res.graph || res.chart) h += '<div class="frame-vis" id="final-vis" style="margin-bottom:14px"></div>';
  if ((res.tables || []).length) h += `<div class="sheet">${res.tables.map((t) => `<h4>${esc(t.title || '')}</h4>${tableHTML(t)}`).join('')}</div>`;
  body.innerHTML = h || '<div class="empty"><b>没有可显示的结果</b>请检查输入后重新求解。</div>';
  if (res.graph || res.chart) drawVisual($('#final-vis'), res.graph, res.chart, res.shared);
}

/* ---------- 线性规划：演示与结果 ---------- */
function renderLPDemo(body, entry) {
  const { res, payload } = entry;
  body.innerHTML = '<div id="player"></div>';
  const trail = res.steps.map((s) => (s.x || []).slice(0, 2));
  let cur = 0;
  const draw = () => { const cv = $('#lp-vis canvas'); if (cv) drawLPGraph(cv, res.graph, trail.slice(0, cur + 1)); };
  new Player($('#player'), res.steps, {
    render: (st, el, i) => {
      cur = i;
      const table = `<div class="frame-tables">${simplexTable(st, res.big_m)}</div>`;
      el.innerHTML = `<div class="frame-title">${i === 0 ? '初始单纯形表' : `第 ${i} 次枢轴`}　基 { ${esc(st.basis.join(', '))} }</div>` +
        `<div class="frame-text">${stepExplain(st, i, res, payload)}</div>` +
        (res.graph ? `<div class="frame-body two"><div class="frame-vis" id="lp-vis"><canvas class="graph"></canvas></div>${table}</div>` : table);
      if (res.graph) draw();
    },
  });
  if (res.graph) { draw.box = body; state.redraw.push(draw); }
}
function renderLPResult(body, entry) {
  const { res, payload } = entry;
  const shadow = Object.entries(res.shadow_prices || {}).map(([k, v]) => [k, v, v === null ? '—' : (Math.abs(v) < 1e-9 ? '有剩余，增加资源没有价值' :
    `右端每增加 1，目标${(payload.obj === 'max') === (v > 0) ? '增加' : '减少'} ${fmt(Math.abs(v))}`)]);
  body.innerHTML = `<div class="grid2"><div class="sheet"><div class="bigobj">${payload.obj === 'max' ? '最大' : '最小'}值 z =<b>${esc(fmt(res.objective))}</b></div>` +
    tableHTML({ headers: ['变量', '取值'], rows: Object.entries(res.solution).map(([k, v]) => [k, v]) }, 'sol') +
    `<h4 style="margin-top:16px">影子价格</h4>` + tableHTML({ headers: ['约束', '影子价格', '含义'], rows: shadow }, 'sol') + '</div>' +
    (res.graph ? '<div class="frame-vis" id="lp-final"><canvas class="graph"></canvas></div>' : '<div class="sheet small">图解只适用于 2 个变量的模型。</div>') + '</div>';
  if (res.graph) {
    const trail = res.steps.map((s) => (s.x || []).slice(0, 2));
    const draw = () => { const cv = $('#lp-final canvas'); if (cv) drawLPGraph(cv, res.graph, trail); };
    draw(); draw.box = body; state.redraw.push(draw);
  }
}

/* ============================== 分隔线、全屏演示、侧栏 ============================== */
function inputWidthKey() { return 'qsb-w-' + (state.m ? state.m.id : ''); }
function applyInputWidth() {
  const def = state.m && state.m.id === 'lp' ? 470 : 380;
  const w = store.get(inputWidthKey(), def);
  document.documentElement.style.setProperty('--input-w', Math.max(260, Math.min(820, w)) + 'px');
}
function bindSplitter() {
  const sp = $('#splitter');
  const setW = (w) => {
    w = Math.max(260, Math.min(Math.min(820, window.innerWidth - 420), w));
    document.documentElement.style.setProperty('--input-w', w + 'px');
    return w;
  };
  sp.addEventListener('pointerdown', (e) => {
    e.preventDefault(); sp.setPointerCapture(e.pointerId); sp.classList.add('drag');
    const left = $('#inputs').getBoundingClientRect().left;
    const zoom = parseFloat(document.documentElement.style.zoom) || 1;
    const move = (ev) => setW(ev.clientX / zoom - left / zoom);
    const up = (ev) => {
      sp.releasePointerCapture(e.pointerId); sp.classList.remove('drag');
      sp.removeEventListener('pointermove', move); sp.removeEventListener('pointerup', up);
      store.set(inputWidthKey(), setW(ev.clientX / zoom - left / zoom)); redrawAll();
    };
    sp.addEventListener('pointermove', move); sp.addEventListener('pointerup', up);
  });
  sp.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault(); e.stopPropagation();
    const w = $('#inputs').getBoundingClientRect().width / (parseFloat(document.documentElement.style.zoom) || 1);
    store.set(inputWidthKey(), setW(w + (e.key === 'ArrowLeft' ? -24 : 24))); redrawAll();
  });
}
function togglePresent(on) {
  const v = on === undefined ? !document.body.classList.contains('present') : on;
  document.body.classList.toggle('present', v);
  $('#present-btn').classList.toggle('on', v);
  $('#present-btn').textContent = v ? '退出全屏演示' : '演示全屏';
  setTimeout(redrawAll, 30);
}
function toggleSide() {
  const v = !document.body.classList.contains('side-collapsed');
  document.body.classList.toggle('side-collapsed', v);
  store.set('qsb-side', v);
  $('#collapse-btn span:last-child').textContent = v ? '展开侧栏' : '收起侧栏';
  $('#collapse-btn .ico').textContent = v ? '⇥' : '⇤';
  setTimeout(redrawAll, 30);
}
const ZOOMS = [0.8, 0.9, 1, 1.1, 1.25, 1.4, 1.6];
function setZoom(z) {
  document.documentElement.style.zoom = z === 1 ? '' : z;
  $('#zoom-val').textContent = Math.round(z * 100) + '%';
  store.set('qsb-zoom', z);
  setTimeout(redrawAll, 30);
}
function stepZoom(d) {
  const z = parseFloat(document.documentElement.style.zoom) || 1;
  const i = ZOOMS.findIndex((x) => Math.abs(x - z) < 1e-6);
  setZoom(ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? 2 : i) + d))]);
}
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  $('#theme-label').textContent = t === 'dark' ? '实验台主题' : '黑板主题';
  redrawAll();
}
function showShortcuts() {
  if ($('.shortcut-help')) return $('.shortcut-help').remove();
  const rows = [[`${MOD} Enter`, '求解'], [`${MOD} K`, '搜索模块'], ['← →', '上一步 / 下一步'], ['空格', '播放 / 暂停'],
    ['Home End', '第一步 / 最后一步'], ['F', '演示全屏'], ['Esc', '退出全屏 / 关闭本窗口'], ['?', '显示本帮助']];
  const d = document.createElement('div');
  d.className = 'shortcut-help';
  d.innerHTML = `<div class="card" role="dialog" aria-label="快捷键"><h3>快捷键</h3><table>${rows.map(([k, t]) => `<tr><td>${k.split(' ').map((x) => `<kbd>${esc(x)}</kbd>`).join(' ')}</td><td>${t}</td></tr>`).join('')}</table></div>`;
  d.onclick = () => d.remove();
  document.body.appendChild(d);
}

document.addEventListener('keydown', (e) => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key === 'Enter') { e.preventDefault(); solve(); return; }
  if (mod && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault();
    if (document.body.classList.contains('side-collapsed')) toggleSide();
    if (window.innerWidth <= 900) document.body.classList.add('nav-open');
    $('#search').focus(); $('#search').select(); return;
  }
  if (e.key === 'Escape') {
    if ($('.shortcut-help')) return $('.shortcut-help').remove();
    if (document.body.classList.contains('present')) return togglePresent(false);
    if (e.target === $('#search')) { $('#search').value = ''; buildNav(); e.target.blur(); }
    return;
  }
  if (typing || mod || e.altKey) return;
  if (e.key === '?') return showShortcuts();
  if (e.key === 'f' || e.key === 'F') return togglePresent();
  const p = [...Player.all].pop(); if (!p) return;
  const map = { ArrowLeft: 'prev', ArrowRight: 'next', Home: 'first', End: 'last', ' ': 'play' };
  if (map[e.key]) { e.preventDefault(); p.act(map[e.key]); }
});
window.addEventListener('resize', debounce(redrawAll, 150));
window.addEventListener('hashchange', () => { const id = location.hash.slice(1); if (state.m && id && id !== state.m.id) openModule(id, false); });

/* ============================== 心跳与启动 ============================== */
async function heartbeat() {
  try {
    const r = await (await fetch('/api/ping', { cache: 'no-store' })).json();
    state.mode = r.mode || 'server';
    $('#quit-btn').classList.toggle('hidden', state.mode !== 'browser');   // 原生窗口直接关窗即可
    $('#version').textContent = 'QSB Studio ' + r.version;
  } catch (e) { /* 服务已退出 */ }
}

(async function init() {
  try {
    state.modules = (await (await fetch('/api/modules')).json()).modules;
  } catch (e) {
    $('#stage-inner').innerHTML = '<div class="empty"><b>无法连接求解服务</b>请确认 QSB Studio 程序正在运行，然后刷新本页。</div>';
    return;
  }
  let t = 'light';
  try { t = localStorage.getItem('qsb-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); } catch (_) { /* ignore */ }
  applyTheme(t);
  $('#theme-btn').onclick = () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('qsb-theme', next); } catch (_) { /* ignore */ }
    applyTheme(next);
  };
  const z = store.get('qsb-zoom', 1); $('#zoom-val').textContent = Math.round(z * 100) + '%';
  $('#zoom-in').onclick = () => stepZoom(1); $('#zoom-out').onclick = () => stepZoom(-1);
  if (store.get('qsb-side', false)) toggleSide();
  $('#collapse-btn').onclick = toggleSide;
  $('#help-btn').onclick = showShortcuts;
  $('#menu-btn').onclick = () => document.body.classList.toggle('nav-open');
  $('#solve-btn').onclick = solve;
  $('#solve-key').textContent = `${MOD} ↵`;
  $('#search-key').textContent = `${MOD} K`;
  $('#present-btn').onclick = () => togglePresent();
  $('#reset-btn').onclick = () => {
    const m = state.m; if (!m) return;
    store.del('qsb-in-' + m.id); delete state.results[m.id];
    if (m.id === 'lp') buildLPInputs(); else buildGenericInputs(m);
    solve();
  };
  $('#quit-btn').onclick = async () => {
    if (!confirm('退出 QSB Studio？')) return;
    try { await fetch('/api/quit', { method: 'POST' }); } catch (_) { /* ignore */ }
    document.body.innerHTML = '<div class="empty" style="padding-top:20vh"><b>QSB Studio 已退出</b>可以关闭此页面。</div>';
  };
  const search = $('#search');
  search.oninput = () => buildNav(search.value);
  search.onkeydown = (e) => {
    if (e.key === 'Enter') { const first = $('#module-nav .nav-item'); if (first) { openModule(first.dataset.id); search.value = ''; buildNav(); search.blur(); } }
  };
  bindSplitter();
  buildNav();
  openModule(location.hash.slice(1) || store.get('qsb-last', 'lp'));
  window.addEventListener('beforeunload', () => { saveInputs(); if (state.m) store.set('qsb-last', state.m.id); });
  setInterval(() => { if (state.m) store.set('qsb-last', state.m.id); }, 5000);
  heartbeat(); setInterval(heartbeat, 15000);
})();
