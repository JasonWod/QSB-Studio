/* QSB Studio — 前端主逻辑（vanilla JS，无依赖、无构建步骤） */
'use strict';
const $ = (s, root = document) => root.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const STATUS = {
  optimal: '最优解 Optimal', ok: '完成', feasible: '可行解（未证明最优）', significant: '检验显著',
  infeasible: '不可行 Infeasible', unbounded: '无界 Unbounded', unstable: '系统不稳定',
  iteration_limit: '迭代超限', error: '出错', not_implemented: '不可用',
};
const GOOD = new Set(['optimal', 'ok', 'significant', 'feasible']);

const LP_EXAMPLES = {
  classic: { label: '经典例题（max）', obj: 'max', c: [3, 5], A: [[1, 0], [0, 2], [3, 2]], b: [4, 12, 18], senses: ['le', 'le', 'le'] },
  min: { label: '最小化 + ≥ 约束（大 M）', obj: 'min', c: [2, 3], A: [[1, 1], [1, 2], [1, 0]], b: [4, 6, 5], senses: ['ge', 'ge', 'le'] },
  eq: { label: '含等式约束', obj: 'max', c: [1, 2], A: [[1, 1], [1, 0], [0, 1]], b: [4, 3, 3], senses: ['eq', 'le', 'le'] },
  degenerate: { label: '退化（Bland 防循环）', obj: 'max', c: [0.75, -20, 0.5, -6], A: [[0.25, -8, -1, 9], [0.5, -12, -0.5, 3], [0, 0, 1, 0]], b: [0, 0, 1], senses: ['le', 'le', 'le'] },
  infeasible: { label: '不可行', obj: 'max', c: [1, 1], A: [[1, 1], [1, 1]], b: [2, 5], senses: ['le', 'ge'] },
  unbounded: { label: '无界', obj: 'max', c: [1, 1], A: [[1, -1], [-1, 1]], b: [2, 2], senses: ['le', 'le'] },
};

const state = { modules: [], lp: null, desktop: false, redraw: [] };

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

async function postJSON(url, payload) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  let data;
  try { data = await r.json(); } catch (e) { data = { status: 'error', headline: '服务器返回了无法解析的数据', message: `HTTP ${r.status}` }; }
  return data;
}

/* ============================== 侧边栏导航 ============================== */
function buildNav() {
  const nav = $('#module-nav');
  nav.innerHTML = '';
  const cats = {};
  state.modules.forEach((m) => { (cats[m.category] = cats[m.category] || []).push(m); });
  for (const [cat, ms] of Object.entries(cats)) {
    const c = document.createElement('div');
    c.className = 'nav-cat'; c.textContent = cat; nav.appendChild(c);
    ms.forEach((m) => {
      const d = document.createElement('button');
      d.type = 'button';
      d.className = 'nav-item' + (m.id === 'lp' ? ' active' : '');
      d.dataset.id = m.id;
      d.innerHTML = `<span class="ico">${esc(m.icon || '')}</span><span>${esc(m.name)}</span>` +
        (m.status === 'ready' ? '' : '<span class="tag">不可用</span>');
      d.onclick = () => { selectModule(m); location.hash = m.id; };
      nav.appendChild(d);
    });
  }
}

function selectModule(m) {
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.id === m.id));
  Player.stopAll();
  state.redraw = [];
  if (m.id === 'lp') showView('lp');
  else if (m.status === 'ready') { buildGeneric(m); showView('generic'); }
  else {
    $('#stub-title').innerHTML = `${esc(m.name)} <span class="en">${esc(m.name_en)}</span>`;
    $('#stub-desc').textContent = m.desc;
    showView('stub');
  }
  document.body.classList.remove('nav-open');
  $('.main').scrollTop = 0;
}
function showView(v) {
  ['lp', 'generic', 'stub'].forEach((k) => $(`#view-${k}`).classList.toggle('hidden', v !== k));
  if (v === 'lp' && state.lp) renderLPResult();
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

document.addEventListener('keydown', (e) => {
  if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
  const p = [...Player.all].pop(); if (!p) return;
  const map = { ArrowLeft: 'prev', ArrowRight: 'next', Home: 'first', End: 'last', ' ': 'play' };
  if (map[e.key]) { e.preventDefault(); p.act(map[e.key]); }
});

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
    pad = 48; W = Math.max(640, Math.min(1200, width * 80 + 2 * pad));
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
  let s = `<svg viewBox="0 0 ${W} ${H}" class="netsvg" role="img" aria-label="网络图">`;
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
      s += `<rect x="${(lx - tw / 2).toFixed(1)}" y="${(ly - ef * 0.75).toFixed(1)}" width="${tw.toFixed(1)}" height="${(ef * 1.4).toFixed(1)}" rx="4" fill="var(--graph-bg)" opacity="0.85"/>`;
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
  const dpr = window.devicePixelRatio || 1;
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

/* ============================== 通用模块：表单与结果 ============================== */
let gen = { mid: null };
function parseList(s) {
  return String(s).split(/[\s,，;；]+/).filter((x) => x !== '').map((x) => { const n = Number(x); return isNaN(n) ? x : n; });
}
function parseMatrix(s) {
  return String(s).split(/\n+/).map((r) => r.trim()).filter((r) => r !== '').map(parseList);
}
function fieldHTML(f) {
  const id = esc(f.id), label = `<span>${esc(f.label || f.id)}</span>`;
  let inner;
  switch (f.type) {
    case 'int': inner = `<input type="number" step="1" data-id="${id}" data-type="int" value="${esc(f.value ?? '')}">`; break;
    case 'float': inner = `<input type="number" step="any" data-id="${id}" data-type="float" value="${esc(f.value ?? '')}">`; break;
    case 'select':
      inner = `<select data-id="${id}" data-type="select">` + (f.options || []).map((o) => {
        const ov = typeof o === 'object' ? o.v : o, ot = typeof o === 'object' ? (o.t ?? o.v) : o;
        return `<option value="${esc(ov)}" ${String(ov) === String(f.value) ? 'selected' : ''}>${esc(ot)}</option>`;
      }).join('') + '</select>';
      break;
    case 'matrix': inner = `<textarea rows="${+f.rows || 4}" data-id="${id}" data-type="matrix" spellcheck="false">${esc(f.value ?? '')}</textarea>`; break;
    case 'textarea': inner = `<textarea rows="${+f.rows || 5}" data-id="${id}" data-type="text" spellcheck="false">${esc(f.value ?? '')}</textarea>`; break;
    case 'list': inner = `<input type="text" data-id="${id}" data-type="list" value="${esc(f.value ?? '')}" spellcheck="false">`; break;
    default: inner = `<input type="text" data-id="${id}" data-type="text" value="${esc(f.value ?? '')}" spellcheck="false">`;
  }
  const wide = (f.type === 'matrix' || f.type === 'textarea') ? ' wide' : '';
  const help = f.help ? `<small class="fhelp">${f.help}</small>` : '';   // help 为服务端可信文案（含 <b>）
  return `<label class="gen-f${wide}" data-field="${id}">${label}${inner}${help}</label>`;
}
function buildGeneric(m) {
  gen = { mid: m.id, m };
  $('#gen-title').innerHTML = `${esc(m.icon || '')} ${esc(m.name)} <span class="en">${esc(m.name_en)}</span>`;
  $('#gen-desc').textContent = m.desc;
  const gx = $('#gen-explain');
  if (m.explain) { gx.innerHTML = m.explain; gx.classList.remove('hidden'); } else gx.classList.add('hidden');   // explain 为可信文案
  $('#gen-form').innerHTML = (m.form || []).map(fieldHTML).join('');
  const r = $('#gen-result'); r.classList.add('hidden'); r.innerHTML = '';
  $('#gen-solve').onclick = solveGeneric;
  $('#gen-reset').onclick = () => buildGeneric(m);
}
function readGenForm() {
  const payload = {};
  $('#gen-form').querySelectorAll('[data-id]').forEach((el) => {
    const t = el.dataset.type, k = el.dataset.id;
    if (t === 'int' || t === 'float') payload[k] = el.value.trim();
    else if (t === 'matrix') payload[k] = parseMatrix(el.value);
    else if (t === 'list') payload[k] = parseList(el.value);
    else payload[k] = el.value;
  });
  return payload;
}
async function solveGeneric() {
  const box = $('#gen-result');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="panel"><span class="busy">求解中…</span></div>';
  const btn = $('#gen-solve'); btn.disabled = true;
  try { renderGenResult(await postJSON(`/api/solve/${gen.mid}`, readGenForm())); }
  catch (e) { renderGenResult({ status: 'error', headline: '无法连接求解服务', message: String(e) }); }
  finally { btn.disabled = false; }
}
function headHTML(res) {
  return `<div class="res-head"><span class="status-badge ${GOOD.has(res.status) ? 'good' : 'bad'}">${esc(STATUS[res.status] || res.status)}</span>` +
    (res.headline ? `<div class="headline">${esc(res.headline)}</div>` : '') + '</div>';
}
function renderGenResult(res) {
  Player.stopAll(); state.redraw = [];
  const box = $('#gen-result');
  box.classList.remove('hidden');
  let h = headHTML(res);
  if (res.message) h += `<div class="panel msg ${res.status === 'error' ? 'err' : ''}">${esc(res.message)}</div>`;
  const steps = res.steps || [];
  if (steps.length) h += `<div class="panel demo"><h3>动态演示 <span class="en">Step by step</span><span class="hint">← → 键逐步，空格播放</span></h3><div id="gen-player"></div></div>`;
  const tables = res.tables || [];
  if (tables.length) h += `<div class="panel"><h3>结果</h3>${tables.map((t) => `<h4>${esc(t.title || '')}</h4>${tableHTML(t)}`).join('')}</div>`;
  if (res.graph || res.chart) h += `<div class="panel"><h3>${res.graph ? '网络图' : '图示'}</h3><div id="gen-vis" class="vis"></div></div>`;
  if (res.notes && res.notes.length) h += `<div class="panel notes"><h3>要点</h3><ul>${res.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>`;
  box.innerHTML = h;
  if (steps.length) new Player($('#gen-player'), steps, { shared: res.shared });
  if (res.graph || res.chart) drawVisual($('#gen-vis'), res.graph, res.chart, res.shared);
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ============================== 线性规划（定制页） ============================== */
const lpObj = () => $('#lp-obj').value;
function buildModel(keep) {
  const nvar = Math.max(1, Math.min(40, +$('#lp-nvar').value || 1));
  const ncon = Math.max(1, Math.min(120, +$('#lp-ncon').value || 1));
  const old = keep ? collectModel(true) : null;
  let h = '<table class="modeltab"><thead><tr><th>行</th>';
  for (let i = 1; i <= nvar; i++) h += `<th>x${i}</th>`;
  h += '<th>关系</th><th>右端 b</th></tr></thead><tbody>';
  h += `<tr class="objrow"><td class="rowlabel">目标 ${esc(lpObj())}</td>`;
  for (let i = 0; i < nvar; i++) h += `<td><input class="coef cobj" data-i="${i}" value="${old && old.c[i] !== undefined ? old.c[i] : 1}" inputmode="decimal"></td>`;
  h += '<td></td><td></td></tr>';
  for (let i = 0; i < ncon; i++) {
    h += `<tr><td class="rowlabel">约束 ${i + 1}</td>`;
    for (let j = 0; j < nvar; j++) h += `<td><input class="coef ca" data-r="${i}" data-c="${j}" value="${old && old.A[i] && old.A[i][j] !== undefined ? old.A[i][j] : 0}" inputmode="decimal"></td>`;
    const sv = old && old.senses[i] ? old.senses[i] : 'le';
    h += `<td><select class="sense" data-i="${i}">${[['le', '≤'], ['ge', '≥'], ['eq', '=']].map(([v, t]) => `<option value="${v}" ${v === sv ? 'selected' : ''}>${t}</option>`).join('')}</select></td>`;
    h += `<td><input class="coef cb" data-i="${i}" value="${old && old.b[i] !== undefined ? old.b[i] : 1}" inputmode="decimal"></td></tr>`;
  }
  $('#lp-model').innerHTML = h + '</tbody></table>';
}
function loadExample(name) {
  const ex = LP_EXAMPLES[name];
  $('#lp-obj').value = ex.obj; $('#lp-nvar').value = ex.c.length; $('#lp-ncon').value = ex.A.length;
  buildModel(false);
  ex.c.forEach((v, i) => { $(`.cobj[data-i="${i}"]`).value = v; });
  ex.A.forEach((row, i) => row.forEach((v, j) => { $(`.ca[data-r="${i}"][data-c="${j}"]`).value = v; }));
  ex.b.forEach((v, i) => { $(`.cb[data-i="${i}"]`).value = v; });
  ex.senses.forEach((s, i) => { $(`.sense[data-i="${i}"]`).value = s; });
}
function collectModel(raw) {
  const num = (el) => (raw ? el.value : Number(el.value.trim() === '' ? 0 : el.value));
  const c = [...document.querySelectorAll('.cobj')].map(num);
  const b = [...document.querySelectorAll('.cb')].map(num);
  const senses = [...document.querySelectorAll('.sense')].map((el) => el.value);
  const ncon = b.length, nvar = c.length, A = [];
  for (let i = 0; i < ncon; i++) { const row = []; for (let j = 0; j < nvar; j++) row.push(num($(`.ca[data-r="${i}"][data-c="${j}"]`))); A.push(row); }
  return { obj: lpObj(), c, A, b, senses, var_names: c.map((_, i) => 'x' + (i + 1)) };
}
async function solveLP() {
  const payload = collectModel(false);
  const bad = [...payload.c, ...payload.b, ...payload.A.flat()].some((v) => !isFinite(v));
  const box = $('#lp-result'); box.classList.remove('hidden');
  if (bad) { box.innerHTML = headHTML({ status: 'error', headline: '输入有误' }) + '<div class="panel msg err">表格中有不是数字的系数，请检查。</div>'; return; }
  box.innerHTML = '<div class="panel"><span class="busy">求解中…</span></div>';
  const res = await postJSON('/api/solve/lp', payload);
  state.lp = { res, payload };
  renderLPResult();
}
function stepExplain(st, idx, res, payload) {
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
function renderLPResult() {
  if (!state.lp) return;
  Player.stopAll(); state.redraw = [];
  const { res, payload } = state.lp;
  const box = $('#lp-result'); box.classList.remove('hidden');
  let h = headHTML({ status: res.status, headline: res.status === 'optimal' ? `${payload.obj === 'max' ? '最大' : '最小'}值 z = ${fmt(res.objective)}` : (res.headline || '') });
  if (res.message) h += `<div class="panel msg ${res.status === 'error' ? 'err' : ''}">${esc(res.message)}</div>`;
  if (res.status === 'error' || !res.steps) { box.innerHTML = h; return; }
  if (res.status === 'optimal') {
    h += '<div class="grid2"><div class="panel"><h3>最优解</h3>';
    h += `<div class="bigobj">z = <b>${esc(fmt(res.objective))}</b></div>`;
    h += tableHTML({ headers: ['变量', '取值'], rows: Object.entries(res.solution).map(([k, v]) => [k, v]) }, 'sol');
    h += '<h3 style="margin-top:16px">影子价格</h3>';
    h += tableHTML({ headers: ['约束', '影子价格', '含义'], rows: Object.entries(res.shadow_prices || {}).map(([k, v]) => [k, v, v === null ? '—' : (Math.abs(v) < 1e-9 ? '不紧（有剩余），再加资源无价值' : `右端每增 1，目标${(payload.obj === 'max') === (v > 0) ? '增加' : '减少'} ${fmt(Math.abs(v))}`)]) }, 'sol');
    h += '</div><div class="panel"><h3>2 变量图解</h3>';
    h += res.graph ? '<div id="lp-vis" class="vis"></div><p class="desc small">紫色虚线是单纯形走过的顶点路径，随下方演示同步推进。</p>' : '<p class="desc">图解仅适用于 2 个变量的模型。</p>';
    h += '</div></div>';
  } else h += '<div class="panel"><p class="desc">下面的迭代过程展示了算法是如何发现这一点的。</p></div>';
  h += '<div class="panel demo"><h3>单纯形分步迭代 <span class="en">Big-M</span><span class="hint">← → 键逐步，空格播放</span></h3><div id="lp-player"></div></div>';
  if (res.sensitivity) h += `<div class="panel"><h3>灵敏度分析</h3>${sensitivityHTML(res.sensitivity)}</div>`;
  box.innerHTML = h;
  const trail = res.steps.map((s) => (s.x || []).slice(0, 2));
  const drawLP = (k) => { const cv = $('#lp-vis canvas') || (() => { $('#lp-vis').innerHTML = '<canvas class="graph"></canvas>'; return $('#lp-vis canvas'); })(); drawLPGraph(cv, res.graph, trail.slice(0, k + 1)); };
  let cur = 0;
  new Player($('#lp-player'), res.steps, {
    render: (st, el, i) => {
      cur = i;
      el.innerHTML = `<div class="frame-title">${i === 0 ? '初始表' : `第 ${i} 次枢轴`} · 基 { ${esc(st.basis.join(', '))} }</div>` +
        `<div class="frame-text">${stepExplain(st, i, res, payload)}</div>` + simplexTable(st, res.big_m);
      if (res.graph && $('#lp-vis')) drawLP(i);
    },
  });
  if (res.graph) {
    const redraw = () => $('#lp-vis') && drawLP(cur);
    redraw.box = $('#lp-vis');
    state.redraw.push(redraw);
  }
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

/* ============================== 主题 / 桌面模式 / 启动 ============================== */
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  $('#theme-btn').textContent = t === 'dark' ? '☀️ 浅色主题' : '🌙 深色主题';
  state.redraw.forEach((f) => f());
}
window.addEventListener('resize', debounce(() => state.redraw.forEach((f) => f()), 150));

async function heartbeat() {
  try {
    const r = await (await fetch('/api/ping', { cache: 'no-store' })).json();
    if (r.desktop && !state.desktop) {
      state.desktop = true;
      $('#quit-btn').classList.remove('hidden');
    }
    $('#version').textContent = 'v' + r.version;
  } catch (e) { /* 服务已退出 */ }
}

(async function init() {
  try {
    state.modules = (await (await fetch('/api/modules')).json()).modules;
  } catch (e) {
    document.body.innerHTML = `<div style="padding:40px;font-size:16px">无法连接求解服务：${esc(String(e))}<br>请确认 QSB Studio 程序正在运行。</div>`;
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
  $('#quit-btn').onclick = async () => {
    if (!confirm('退出 QSB Studio？')) return;
    try { await fetch('/api/quit', { method: 'POST' }); } catch (_) { /* ignore */ }
    document.body.innerHTML = '<div style="padding:60px;text-align:center;font-size:18px">QSB Studio 已退出，可以关闭此页面。</div>';
  };
  $('#menu-btn').onclick = () => document.body.classList.toggle('nav-open');
  buildNav();
  const lpm = state.modules.find((x) => x.id === 'lp');
  if (lpm && lpm.explain) { const le = $('#lp-explain'); le.innerHTML = lpm.explain; le.classList.remove('hidden'); }
  const sel = $('#lp-examples');
  sel.innerHTML = Object.entries(LP_EXAMPLES).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
  sel.onchange = () => loadExample(sel.value);
  $('#lp-solve').onclick = solveLP;
  $('#lp-nvar').onchange = () => buildModel(true);
  $('#lp-ncon').onchange = () => buildModel(true);
  $('#lp-obj').onchange = () => buildModel(true);
  $('#stub-back').onclick = () => selectModule(lpm);
  loadExample('classic');
  const target = state.modules.find((x) => x.id === location.hash.slice(1));
  selectModule(target || lpm);
  heartbeat(); setInterval(heartbeat, 15000);
})();
