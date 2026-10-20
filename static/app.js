/* QSB Studio — 前端主逻辑（vanilla JS，无依赖） */
const $ = (s) => document.querySelector(s);

const EXAMPLES = {
  classic: { obj: 'max', c: [3, 5], A: [[1, 0], [0, 2], [3, 2]], b: [4, 12, 18], senses: ['le', 'le', 'le'] },
  mixed:   { obj: 'max', c: [1, 1], A: [[1, 1], [1, -1], [0, 1]], b: [4, 1, 3], senses: ['ge', 'le', 'le'] },
  min:     { obj: 'min', c: [1, 1], A: [[1, 2], [1, 0], [0, 1]], b: [4, 3, 4], senses: ['ge', 'le', 'le'] },
  eq:      { obj: 'max', c: [1, 1], A: [[1, 1], [1, 0], [0, 1]], b: [4, 3, 3], senses: ['eq', 'le', 'le'] },
};

const STATUS = {
  optimal: '最优解 Optimal',
  infeasible: '不可行 Infeasible',
  unbounded: '无界 Unbounded',
  error: '出错',
  not_implemented: '待实现',
};

const state = { modules: [], lpResult: null, steps: [], stepIdx: 0, timer: null };

function fmt(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (Math.abs(v) < 1e-6) return '0';
    return String(Math.round(v * 1e6) / 1e6);
  }
  return v;
}
const objVal = () => $('#lp-obj').value;

/* ---------------- 侧边栏导航 ---------------- */
function buildNav() {
  const nav = $('#module-nav');
  nav.innerHTML = '';
  const cats = {};
  state.modules.forEach((m) => { (cats[m.category] = cats[m.category] || []).push(m); });
  for (const [cat, ms] of Object.entries(cats)) {
    const c = document.createElement('div');
    c.className = 'nav-cat'; c.textContent = cat; nav.appendChild(c);
    ms.forEach((m) => {
      const d = document.createElement('div');
      d.className = 'nav-item' + (m.id === 'lp' ? ' active' : '');
      d.dataset.id = m.id;
      d.innerHTML = `<span>${m.name}</span>` +
        `<span class="tag ${m.status}">${m.status === 'ready' ? '可用' : '骨架'}</span>`;
      d.onclick = () => selectModule(m);
      nav.appendChild(d);
    });
  }
}

function selectModule(m) {
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
  const el = document.querySelector(`.nav-item[data-id="${m.id}"]`);
  if (el) el.classList.add('active');
  stopPlay();
  if (m.id === 'lp') {
    showView('lp');
  } else if (m.status === 'ready') {
    buildGeneric(m);
    showView('generic');
  } else {
    $('#stub-title').innerHTML = `${m.name} <span class="en">${m.name_en}</span>`;
    $('#stub-desc').textContent = m.desc;
    showView('stub');
  }
}
function showView(v) {
  $('#view-lp').classList.toggle('hidden', v !== 'lp');
  $('#view-generic').classList.toggle('hidden', v !== 'generic');
  $('#view-stub').classList.toggle('hidden', v !== 'stub');
}

/* ---------------- 建模表单 ---------------- */
function buildModel() {
  const nvar = Math.max(1, Math.min(40, +$('#lp-nvar').value || 1));
  const ncon = Math.max(1, Math.min(120, +$('#lp-ncon').value || 1));
  let h = '<table class="modeltab"><thead><tr><th>表达式</th>';
  for (let i = 1; i <= nvar; i++) h += `<th>x${i}</th>`;
  h += '<th>类型</th><th>常数</th></tr></thead><tbody>';
  // 目标行
  h += `<tr class="objrow"><td class="rowlabel">目标 ${objVal()}</td>`;
  for (let i = 0; i < nvar; i++) h += `<td><input class="coef cobj" data-i="${i}" value="1"></td>`;
  h += '<td></td><td></td></tr>';
  // 约束行
  for (let i = 0; i < ncon; i++) {
    h += `<tr><td class="rowlabel">约束${i + 1}</td>`;
    for (let j = 0; j < nvar; j++) h += `<td><input class="coef ca" data-r="${i}" data-c="${j}" value="0"></td>`;
    h += `<td><select class="sense" data-i="${i}"><option value="le">≤</option><option value="ge">≥</option><option value="eq">=</option></select></td>`;
    h += `<td><input class="coef cb" data-i="${i}" value="1"></td></tr>`;
  }
  h += '</tbody></table>';
  $('#lp-model').innerHTML = h;
}

function loadExample(name) {
  const ex = EXAMPLES[name];
  $('#lp-obj').value = ex.obj;
  $('#lp-nvar').value = ex.c.length;
  $('#lp-ncon').value = ex.A.length;
  buildModel();
  ex.c.forEach((v, i) => { const el = $(`.cobj[data-i="${i}"]`); if (el) el.value = v; });
  ex.A.forEach((row, i) => row.forEach((v, j) => { const el = $(`.ca[data-r="${i}"][data-c="${j}"]`); if (el) el.value = v; }));
  ex.b.forEach((v, i) => { const el = $(`.cb[data-i="${i}"]`); if (el) el.value = v; });
  ex.senses.forEach((s, i) => { const el = $(`.sense[data-i="${i}"]`); if (el) el.value = s; });
}

function collectModel() {
  const nvar = +$('#lp-nvar').value, ncon = +$('#lp-ncon').value;
  const c = [...document.querySelectorAll('.cobj')].map((el) => parseFloat(el.value || 0));
  const b = [...document.querySelectorAll('.cb')].map((el) => parseFloat(el.value || 0));
  const senses = [...document.querySelectorAll('.sense')].map((el) => el.value);
  const A = [];
  for (let i = 0; i < ncon; i++) {
    const row = [];
    for (let j = 0; j < nvar; j++) {
      const el = document.querySelector(`.ca[data-r="${i}"][data-c="${j}"]`);
      row.push(el ? parseFloat(el.value || 0) : 0);
    }
    A.push(row);
  }
  return { obj: objVal(), c, A, b, senses, var_names: c.map((_, i) => 'x' + (i + 1)) };
}

/* ---------------- 求解 + 渲染 ---------------- */
async function solve() {
  stopPlay();
  const payload = collectModel();
  const r = await fetch('/api/solve/lp', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const result = await r.json();
  state.lpResult = result;
  state.steps = result.steps || [];
  state.stepIdx = 0;
  const nv = (payload.c || []).length;
  state.bfsTrail = result.graph ? state.steps.map((s) => bfsOfStep(s, nv)) : [];
  renderResult();
}

function solTable(sol) {
  let h = '<table class="sol"><tr><th>变量</th><th>取值</th></tr>';
  for (const k in sol) h += `<tr><td>${k}</td><td class="val">${fmt(sol[k])}</td></tr>`;
  return h + '</table>';
}
function shadowTable(sh) {
  if (!sh || !Object.keys(sh).length) return '<p class="desc">（无约束，影子价格不适用）</p>';
  let h = '<table class="sol"><tr><th>约束</th><th>影子价格</th><th>含义</th></tr>';
  for (const k in sh) {
    const v = sh[k];
    const note = v == null ? '—' : (v === 0 ? '松弛（不紧，无价值）' : `每增 1 单位右端 → 目标 ${v > 0 ? '改善' : '下降'} ${Math.abs(v)}`);
    h += `<tr><td>${k}</td><td class="val">${fmt(v)}</td><td>${note}</td></tr>`;
  }
  return h + '</table>';
}
function statusText(s) {
  if (s === 'infeasible') return '问题不可行 —— 没有任何点能同时满足所有约束（右端可能相互矛盾）。';
  if (s === 'unbounded') return '问题无界 —— 目标值可无限改善（可行域在该方向上无界）。';
  return '';
}

function inf(v) { return (v === null || v === undefined) ? '∞' : fmt(v); }
function sensRange(r) {
  const lo = r.range[0], hi = r.range[1];
  if (lo === null && hi === null) return '—';
  if (lo === null) return `(-∞, ${fmt(hi)}]`;
  if (hi === null) return `[${fmt(lo)}, +∞)`;
  return `[${fmt(lo)}, ${fmt(hi)}]`;
}
function sensitivityHTML(sens) {
  if (!sens) return '<p class="desc">灵敏度分析需要最优解。</p>';
  let h = '<div class="sens-sub">右端（RHS）灵敏度 —— 当前最优基保持不变时，右端的可变动范围</div>';
  h += '<table class="sol sens"><tr><th>约束</th><th>右端 b</th><th>影子价格</th><th>允许增</th><th>允许减</th><th>有效范围</th></tr>';
  sens.rhs.forEach((r) => {
    h += `<tr><td>${r.name}</td><td class="val">${fmt(r.value)}</td><td class="val">${fmt(r.shadow)}</td>` +
      `<td>${inf(r.allow_inc)}</td><td>${inf(r.allow_dec)}</td><td>${sensRange(r)}</td></tr>`;
  });
  h += '</table><div class="sens-sub" style="margin-top:14px">目标系数灵敏度 —— 当前最优基保持不变时，各 c<sub>k</sub> 的可变动范围</div>';
  h += '<table class="sol sens"><tr><th>变量</th><th>c</th><th>检验数</th><th>允许增</th><th>允许减</th><th>有效范围</th></tr>';
  sens.objective.forEach((r) => {
    h += `<tr><td>${r.name}</td><td class="val">${fmt(r.value)}</td><td class="val">${fmt(r.reduced_cost)}</td>` +
      `<td>${inf(r.allow_inc)}</td><td>${inf(r.allow_dec)}</td><td>${sensRange(r)}</td></tr>`;
  });
  h += '</table>';
  h += '<p class="desc">解读：在“有效范围”内单独调整某个右端或目标系数，最优解所用的基（哪些变量为正）保持不变，目标值按影子价格 / 取值线性变化；超出范围则最优基会切换。∞ = 该方向可无限增大而不改变最优基。基变量检验数为 0；非基变量检验数 &lt; 0 表示它“进基”能改善目标（max）。</p>';
  return h;
}

/* 计算某一步基可行解的原始变量取值（用于 2 变量图解轨迹） */
function bfsOfStep(st, nvar) {
  const out = [];
  for (let k = 0; k < nvar; k++) {
    const name = 'x' + (k + 1);
    const idx = st.basis.indexOf(name);
    out.push(idx >= 0 ? (st.rows[idx][st.columns.length] || 0) : 0);
  }
  return out;
}

function stepperHTML() {
  return `<div class="stepper">
    <button class="btn small ghost" id="st-first">⏮ 初始</button>
    <button class="btn small ghost" id="st-prev">◀ 上一步</button>
    <span class="info" id="st-info"></span>
    <button class="btn small ghost" id="st-next">下一步 ▶</button>
    <button class="btn small ghost" id="st-last">⏭ 最终</button>
    <button class="btn small ghost" id="st-play">⏵ 自动播放</button>
  </div>`;
}

function renderStep() {
  const st = state.steps[state.stepIdx];
  if (!st) return;
  const info = $('#st-info');
  if (info) info.textContent =
    `第 ${state.stepIdx}/${state.steps.length - 1} 步 · 基 { ${st.basis.join(', ')} } · 目标值 ${fmt(st.objective_value)}`;
  const p = st.pivot;
  const enterIdx = p ? st.columns.indexOf(p.enter) : -1;
  const leaveRow = p ? st.basis.indexOf(p.leave) : -1;
  const cols = st.columns.length;
  let h = '<table class="tab"><thead><tr><th>基</th>';
  st.columns.forEach((cn, i) => h += `<th class="${i === enterIdx ? 'enter-hl' : ''}">${cn}</th>`);
  h += '<th>RHS</th></tr></thead><tbody>';
  st.rows.forEach((row, i) => {
    h += '<tr><td class="base">' + (st.basis[i] || '') + '</td>';
    for (let j = 0; j < cols; j++) {
      const hl = (i === leaveRow && j === enterIdx) ? ' class="pivot-hl"' : '';
      h += `<td${hl}>${fmt(row[j])}</td>`;
    }
    h += `<td>${fmt(row[cols])}</td></tr>`;
  });
  h += '<tr class="objrow"><td class="base">检验数</td>';
  for (let j = 0; j < cols; j++) {
    const hl = (j === enterIdx) ? ' class="pivot-hl"' : '';
    h += `<td${hl}>${fmt(st.objective[j])}</td>`;
  }
  h += `<td>${fmt(st.objective[cols])}</td></tr></tbody></table>`;
  if (p) h += `<div class="pivot-note" style="margin-top:10px">枢轴：变量 <b>${p.enter}</b> 进基，<b>${p.leave}</b> 离基（第 ${p.row + 1} 行）</div>`;
  $('#tabwrap').innerHTML = h;
  // 同步 2 变量图解：高亮当前顶点，画出已走过的单纯形路径
  const g = state.lpResult && state.lpResult.graph;
  if (g && state.bfsTrail && state.bfsTrail.length) {
    drawGraph(g, state.bfsTrail[state.stepIdx], state.bfsTrail.slice(0, state.stepIdx + 1));
  }
}

function bindStepper() {
  const stop = stopPlay;
  const goNext = () => {
    if (state.stepIdx < state.steps.length - 1) { state.stepIdx++; renderStep(); if (state.stepIdx === state.steps.length - 1) stop(); }
  };
  const on = (id, fn) => { const el = $(id); if (el) el.onclick = fn; };
  on('#st-first', () => { state.stepIdx = 0; renderStep(); stop(); });
  on('#st-prev', () => { if (state.stepIdx > 0) state.stepIdx--; renderStep(); stop(); });
  on('#st-next', () => { goNext(); stop(); });
  on('#st-last', () => { state.stepIdx = state.steps.length - 1; renderStep(); stop(); });
  on('#st-play', () => {
    if (state.timer) { stop(); return; }
    if (state.stepIdx === state.steps.length - 1) state.stepIdx = 0;
    const b = $('#st-play'); if (b) b.textContent = '⏸ 暂停';
    goNext();
    state.timer = setInterval(goNext, 1100);
  });
}

function stopPlay() {
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  const b = $('#st-play'); if (b) b.textContent = '⏵ 自动播放';
}

function renderResult() {
  const res = state.lpResult;
  const box = $('#lp-result');
  box.classList.remove('hidden');
  const status = res.status;
  const badge = `<div class="status-badge ${status}">${STATUS[status] || status}</div>`;
  if (status === 'error' || status === 'not_implemented') {
    box.innerHTML = badge + `<div class="panel"><p>${res.message || ''}</p></div>`;
    return;
  }
  let h = badge;
  if (status === 'optimal') {
    h += '<div class="grid2">';
    h += `<div class="panel"><h3 class="block">最优解</h3>` +
      `<div class="bigobj">目标值 = <b>${fmt(res.objective)}</b> <small>(${objVal()})</small></div>` +
      solTable(res.solution) +
      `<h3 class="block">影子价格 / 灵敏度</h3>` + shadowTable(res.shadow_prices) + `</div>`;
    h += `<div class="panel"><h3 class="block">2 变量图解 <span class="en">单纯形沿可行域顶点“走路”</span></h3>`;
    if (res.graph) h += '<canvas class="graph" id="gcanvas" width="600" height="460"></canvas><div class="legend" id="glegend"></div><p class="desc">下方步进时，紫色轨迹会同步画出单纯形从起点沿可行域边“走路”到最优点的过程。</p>';
    else h += '<p class="desc">图解仅支持 2 变量 LP；当前模型变量数不是 2，故不显示。</p>';
    h += '</div></div>';
    h += `<div class="panel"><h3 class="block">单纯形分步迭代 <span class="en">Big-M 大M法</span></h3>` + stepperHTML() + '<div id="tabwrap"></div></div>';
    h += `<div class="panel"><h3 class="block">灵敏度分析 <span class="en">Sensitivity Report</span></h3>` + sensitivityHTML(res.sensitivity) + '</div>';
  } else {
    h += `<div class="panel"><p>${statusText(status)}</p></div>`;
  }
  box.innerHTML = h;
  bindStepper();
  renderStep();
  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ---------------- 2变量图解 ---------------- */
function convexHull(pts) {
  if (pts.length < 3) return pts.slice();
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const pt of p) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop(); lower.push(pt); }
  const upper = [];
  for (let i = p.length - 1; i >= 0; i--) { const pt = p[i]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop(); upper.push(pt); }
  lower.pop(); upper.pop();
  return lower.concat(upper);
}
function dot(ctx, x, y, c, r) { ctx.beginPath(); ctx.fillStyle = c; ctx.arc(x, y, r, 0, 7); ctx.fill(); }

function drawGraph(g, bfs, trail) {
  const cv = $('#gcanvas'); if (!cv) return;
  const ctx = cv.getContext('2d');
  // 从 CSS 变量取当前主题配色（浅色/深色自适应）
  const cs = getComputedStyle(cv);
  const gv = (n, d) => (cs.getPropertyValue(n).trim() || d);
  const C = {
    grid: gv('--graph-grid', '#eef2f7'), axis: gv('--graph-axis', '#475569'),
    line: gv('--graph-line', '#2563eb'), iso: gv('--graph-iso', '#d97706'),
    opt: gv('--graph-opt', '#15803d'), vertex: gv('--graph-vertex', '#94a3b8'),
    hull: gv('--graph-hull', 'rgba(21,128,61,.16)'), hullLine: gv('--graph-hullline', 'rgba(21,128,61,.55)'),
    path: gv('--graph-path', '#8b5cf6'), pathCur: gv('--graph-path-cur', '#7c3aed'),
  };
  const W = cv.width, H = cv.height, pad = 44;
  const vs = g.vertices || [];
  let minx = 0, maxx = 1, miny = 0, maxy = 1;
  vs.forEach((v) => { minx = Math.min(minx, v[0]); maxx = Math.max(maxx, v[0]); miny = Math.min(miny, v[1]); maxy = Math.max(maxy, v[1]); });
  minx = Math.min(minx, 0); miny = Math.min(miny, 0);
  const dx = (maxx - minx) || 1, dy = (maxy - miny) || 1;
  maxx += dx * 0.15; maxy += dy * 0.15;
  const X = (x) => pad + (x - minx) / (maxx - minx) * (W - 2 * pad);
  const Y = (y) => H - pad - (y - miny) / (maxy - miny) * (H - 2 * pad);
  ctx.clearRect(0, 0, W, H);

  // 坐标轴
  ctx.strokeStyle = C.axis; ctx.lineWidth = 1; ctx.globalAlpha = 0.5;
  ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(maxx), Y(0)); ctx.stroke(); // x1 轴
  ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(0), Y(maxy)); ctx.stroke(); // x2 轴
  ctx.globalAlpha = 1;

  // 可行域（凸包）
  const hull = convexHull(vs);
  if (hull.length > 2) {
    ctx.beginPath();
    hull.forEach((p, i) => { i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])); });
    ctx.closePath();
    ctx.fillStyle = C.hull; ctx.fill();
    ctx.strokeStyle = C.hullLine; ctx.lineWidth = 1; ctx.stroke();
  }
  // 约束线
  ctx.strokeStyle = C.line; ctx.lineWidth = 1.5;
  g.lines.forEach((L) => {
    ctx.beginPath();
    if (L.vertical) { const x = L.b / (L.a1 || 1); ctx.moveTo(X(x), Y(miny)); ctx.lineTo(X(x), Y(maxy)); }
    else { const x2 = (x1) => (L.b - L.a1 * x1) / L.a2; ctx.moveTo(X(minx), Y(x2(minx))); ctx.lineTo(X(maxx), Y(x2(maxx))); }
    ctx.stroke();
  });
  // 目标等值线
  if (g.iso_line) {
    ctx.strokeStyle = C.iso; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    const sl = g.iso_line.slope, [ox, oy] = g.iso_line.through;
    const x2 = (x1) => oy + sl * (x1 - ox);
    ctx.beginPath(); ctx.moveTo(X(minx), Y(x2(minx))); ctx.lineTo(X(maxx), Y(x2(maxx))); ctx.stroke();
    ctx.setLineDash([]);
  }
  // 顶点 + 最优点
  vs.forEach((v) => dot(ctx, X(v[0]), Y(v[1]), C.vertex, 3));
  const op = g.optimum;
  dot(ctx, X(op[0]), Y(op[1]), C.opt, 6);
  ctx.fillStyle = C.opt; ctx.font = '13px sans-serif';
  ctx.fillText(`最优 (${fmt(op[0])}, ${fmt(op[1])})  Z=${fmt(g.objective_value)}`, X(op[0]) + 8, Y(op[1]) - 8);
  // 单纯形路径：从起点沿可行域边走到最优点
  if (trail && trail.length) {
    ctx.strokeStyle = C.path; ctx.lineWidth = 2; ctx.setLineDash([5, 3]);
    ctx.beginPath();
    trail.forEach((p, i) => { i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])); });
    ctx.stroke(); ctx.setLineDash([]);
    trail.forEach((p, i) => {
      const isCur = bfs && Math.abs(p[0] - bfs[0]) < 1e-6 && Math.abs(p[1] - bfs[1]) < 1e-6;
      dot(ctx, X(p[0]), Y(p[1]), isCur ? C.pathCur : C.path, isCur ? 6 : 3.5);
      ctx.fillStyle = C.path; ctx.font = '11px sans-serif';
      ctx.fillText('第' + i + '步', X(p[0]) + 7, Y(p[1]) + 15);
    });
  }
  // 轴标签
  ctx.fillStyle = C.axis;
  ctx.fillText('x1 →', W - 44, H - pad + 22);
  ctx.fillText('x2 ↑', pad - 30, pad - 10);

  const lg = $('#glegend');
  if (lg) lg.innerHTML =
    `<span><span class="sw" style="background:${C.hull};border:1px solid ${C.hullLine}"></span>可行域</span>` +
    `<span><span class="sw" style="background:${C.line}"></span>约束线</span>` +
    `<span><span class="sw" style="background:${C.iso}"></span>目标等值线</span>` +
    `<span><span class="sw" style="background:${C.opt};border-radius:50%"></span>最优点</span>` +
    (trail && trail.length ? `<span><span class="sw" style="background:${C.pathCur};border-radius:50%"></span>单纯形路径</span>` : '');
}

/* ---------------- 通用模块（动态表单 + 统一结果） ---------------- */
let stateGen = { mid: null, chart: null };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function parseList(s) {
  return String(s).split(/[\s,，;]+/).filter((x) => x !== '').map((x) => { const n = Number(x); return isNaN(n) ? x : n; });
}
function parseMatrix(s) {
  return String(s).split(/\n+/).map((r) => r.trim()).filter((r) => r !== '').map((r) => parseList(r));
}
function fieldHTML(f) {
  const label = `<span>${esc(f.label || f.id)}</span>`;
  let inner = '';
  switch (f.type) {
    case 'int':
      inner = `<input type="number" step="1" min="${f.min ?? ''}" max="${f.max ?? ''}" data-id="${f.id}" data-type="int" value="${f.value ?? ''}">`;
      break;
    case 'float':
      inner = `<input type="number" step="any" min="${f.min ?? ''}" max="${f.max ?? ''}" data-id="${f.id}" data-type="float" value="${f.value ?? ''}">`;
      break;
    case 'select':
      inner = `<select data-id="${f.id}" data-type="select">` +
        (f.options || []).map((o) => {
          const ov = (typeof o === 'object' && o !== null) ? o.v : o;
          const ot = (typeof o === 'object' && o !== null) ? (o.t ?? o.v) : o;
          return `<option value="${esc(ov)}" ${String(ov) === String(f.value) ? 'selected' : ''}>${esc(ot)}</option>`;
        }).join('') + `</select>`;
      break;
    case 'bool':
      inner = `<input type="checkbox" data-id="${f.id}" data-type="bool" ${f.value ? 'checked' : ''}>`;
      break;
    case 'matrix':
      inner = `<textarea rows="${f.rows || 4}" data-id="${f.id}" data-type="matrix" placeholder="每行一条，元素用逗号或空格分隔">${esc(f.value ?? '')}</textarea>`;
      break;
    case 'textarea':
      inner = `<textarea rows="${f.rows || 5}" data-id="${f.id}" data-type="text" placeholder="${esc(f.placeholder || '')}">${esc(f.value ?? '')}</textarea>`;
      break;
    case 'list':
      inner = `<input type="text" data-id="${f.id}" data-type="list" value="${esc(f.value ?? '')}" placeholder="${esc(f.placeholder || '逗号/空格分隔')}">`;
      break;
    default:
      inner = `<input type="text" data-id="${f.id}" data-type="text" value="${esc(f.value ?? '')}" placeholder="${esc(f.placeholder || '')}">`;
  }
  const wide = (f.type === 'matrix' || f.type === 'textarea') ? ' wide' : '';
  const help = f.help ? `<small class="fhelp">${f.help}</small>` : '';
  return `<label class="gen-f${wide}">${label}${inner}${help}</label>`;
}
function buildGeneric(m) {
  stateGen.mid = m.id;
  stateGen.chart = null;
  $('#gen-title').innerHTML = `${m.icon ? m.icon + ' ' : ''}${m.name} <span class="en">${m.name_en}</span>`;
  $('#gen-desc').textContent = m.desc;
  const gx = $('#gen-explain');
  if (m.explain) { gx.innerHTML = m.explain; gx.classList.remove('hidden'); }
  else gx.classList.add('hidden');
  $('#gen-form').innerHTML = (m.form || []).map(fieldHTML).join('');
  const r = $('#gen-result');
  r.classList.add('hidden'); r.innerHTML = '';
  $('#gen-solve').onclick = solveGeneric;
}
function readGenForm() {
  const payload = {};
  $('#gen-form').querySelectorAll('[data-id]').forEach((el) => {
    const t = el.dataset.type;
    if (t === 'bool') payload[el.dataset.id] = el.checked;
    else if (t === 'int') payload[el.dataset.id] = parseInt(el.value || '0', 10);
    else if (t === 'float') payload[el.dataset.id] = parseFloat(el.value || '0');
    else if (t === 'matrix') payload[el.dataset.id] = parseMatrix(el.value);
    else if (t === 'list') payload[el.dataset.id] = parseList(el.value);
    else payload[el.dataset.id] = el.value;
  });
  return payload;
}
async function solveGeneric() {
  const payload = readGenForm();
  const box = $('#gen-result');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="panel"><span class="busy">求解中…</span></div>';
  try {
    const res = await (await fetch(`/api/solve/${stateGen.mid}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    })).json();
    renderGenResult(res);
  } catch (e) {
    renderGenResult({ status: 'error', headline: '请求失败', notes: [String(e)] });
  }
}
function renderGenResult(res) {
  const box = $('#gen-result');
  box.classList.remove('hidden');
  if (res.status === 'not_implemented') {
    box.innerHTML = `<div class="panel placeholder-panel"><div class="ph-icon">🚧</div><div class="ph-title">该模块算法实现中</div><div class="ph-sub">${esc(res.message || '')}</div></div>`;
    return;
  }
  const st = STATUS[res.status] || res.status;
  let html = `<div class="res-head"><span class="status-badge ${res.status}">${esc(st)}</span>` +
    (res.headline ? `<div class="headline">${esc(res.headline)}</div>` : '') + '</div>';
  (res.tables || []).forEach((tb) => {
    html += `<div class="panel"><h3>${esc(tb.title || '')}</h3><div class="tblwrap"><table class="sens">` +
      `<thead><tr>${tb.headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
      tb.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(fmt(c))}</td>`).join('')}</tr>`).join('') +
      `</tbody></table></div></div>`;
  });
  if (res.message) html += `<div class="panel notes"><p>${esc(res.message)}</p></div>`;
  if (res.notes && res.notes.length)
    html += `<div class="panel notes"><h3>说明</h3><ul>${res.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>`;
  if (res.graph) {
    html += `<div class="panel"><h3>网络图 <span class="en" style="font-weight:500">Network Diagram</span></h3><div id="gen-netgraph"></div></div>`;
  } else if (res.chart) {
    html += `<div class="panel"><h3>图示 <span class="en" style="font-weight:500">Chart</span></h3><canvas id="genchart" class="graph" width="640" height="420"></canvas></div>`;
  }
  box.innerHTML = html;
  stateGen.chart = res.chart || null;
  stateGen.netgraph = res.graph || null;
  if (res.graph && window.drawNetGraph) drawNetGraph(res.graph);
  else if (res.chart && window.drawGenChart) drawGenChart(res.chart);
}
function drawGenChart(chart) {
  const cv = document.getElementById('genchart');
  if (!cv) return;
  const cs = getComputedStyle(cv);
  const gv = (n, d) => (cs.getPropertyValue(n).trim() || d);
  const C = {
    grid: gv('--graph-grid', '#eef2f7'), axis: gv('--txt', '#1e293b'),
    text: gv('--txt', '#1e293b'), bg: gv('--graph-bg', '#ffffff'),
    s1: gv('--accent', '#2563eb'), s2: gv('--graph-path', '#8b5cf6'), s3: '#16a34a', s4: '#dc2626',
  };
  const pal = [C.s1, C.s2, C.s3, C.s4];
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  const padL = 52, padR = 18, padT = 26, padB = 42;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
  const series = chart.series || [];
  const x = chart.x || chart.xlabels || [];
  let vmin = Infinity, vmax = -Infinity;
  series.forEach((s) => s.values.forEach((v) => { v = +v; if (v < vmin) vmin = v; if (v > vmax) vmax = v; }));
  if (vmin === vmax) { vmin -= 1; vmax += 1; }
  let rng = vmax - vmin; vmin -= rng * 0.1; vmax += rng * 0.1; rng = vmax - vmin;
  const n = Math.max(x.length, ...series.map((s) => s.values.length), 1);
  const X = (i) => padL + (n > 1 ? (i / (n - 1)) * (W - padL - padR) : (W - padL - padR) / 2);
  const Y = (v) => H - padB - ((v - vmin) / rng) * (H - padT - padB);
  ctx.font = '11px system-ui, sans-serif';
  for (let g = 0; g <= 5; g++) {
    const val = vmin + rng * g / 5, y = Y(val);
    ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
    ctx.fillStyle = C.text; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(val.toFixed(Math.abs(val) < 10 ? 1 : 0), padL - 6, y);
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = C.text;
  const stp = Math.max(1, Math.ceil(n / 10));
  for (let i = 0; i < x.length; i += stp) ctx.fillText(String(x[i]), X(i), H - padB + 6);
  if (chart.xtitle) { ctx.textAlign = 'right'; ctx.fillText(chart.xtitle, W - padR, H - 12); }
  ctx.strokeStyle = C.axis; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.moveTo(padL, padT); ctx.lineTo(padL, H - padB); ctx.lineTo(W - padR, H - padB); ctx.stroke();
  series.forEach((s, si) => {
    const col = pal[si % pal.length];
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath();
    s.values.forEach((v, i) => { const xx = X(i), yy = Y(+v); i ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy); });
    ctx.stroke();
    ctx.fillStyle = col;
    s.values.forEach((v, i) => { ctx.beginPath(); ctx.arc(X(i), Y(+v), 2.6, 0, 7); ctx.fill(); });
  });
  let lx = padL + 8;
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  series.forEach((s, si) => {
    ctx.fillStyle = pal[si % pal.length]; ctx.fillRect(lx, 12, 12, 3);
    ctx.fillStyle = C.text; ctx.fillText(s.name, lx + 16, 13);
    lx += 16 + ctx.measureText(s.name).width + 18;
  });
}
window.drawGenChart = drawGenChart;

/* ---------------- 网络图可视化（网络/运输模块） ---------------- */
function drawNetGraph(g) {
  const box = document.getElementById('gen-netgraph');
  if (!box) return;
  box.innerHTML = '';
  if (!g || !g.nodes || !g.nodes.length) return;
  const cs = getComputedStyle(box);
  const gv = (n, d) => { const v = cs.getPropertyValue(n); return (v && v.trim()) ? v.trim() : d; };
  const n = g.nodes.length;
  const isBi = g.layout === 'bipartite';

  // ---- 自适应画布：节点越多画布越大/越高，保证任意两节点不重叠 ----
  let W, H, pad, nodeR, font;
  if (isBi) {
    const nl = g.nodes.filter((x) => x.group === 'left').length;
    const nr = g.nodes.filter((x) => x.group === 'right').length;
    const maxc = Math.max(1, nl, nr);
    pad = 58; W = 700;
    H = Math.min(1150, Math.max(480, Math.round(2 * pad + (maxc - 1) * 54))); // 列内 ≥~40px
    nodeR = maxc > 8 ? 12 : 16; font = maxc > 8 ? 11 : 13;
  } else {
    // 正圆（方形画布）；半径随 n 增大，使相邻弦长 ≥~44px
    pad = 44;
    const S = Math.min(950, Math.max(520, Math.round(2 * pad + 52.4 / Math.sin(Math.PI / Math.max(n, 3)))));
    W = H = S;
    nodeR = n > 16 ? 12 : 16; font = n > 16 ? 11 : 13;
  }
  const X = (x) => pad + x * (W - 2 * pad);
  const Y = (y) => pad + y * (H - 2 * pad);
  const pos = {};
  g.nodes.forEach((n) => { pos[n.id] = [X(n.x), Y(n.y)]; });
  const nodeFill = {
    default: gv('--net-node', '#e2e8f0'), src: gv('--net-src', '#16a34a'),
    sink: gv('--net-sink', '#ea580c'), left: gv('--net-left', '#2563eb'),
    right: gv('--net-right', '#8b5cf6'),
  };
  const edgeColor = {
    default: gv('--net-edge', '#94a3b8'), path: gv('--net-hl', '#8b5cf6'),
    mst: gv('--net-src', '#16a34a'), assign: gv('--net-assign', '#db2777'),
    flow: gv('--net-flow', '#0ea5e9'), ship: gv('--net-ship', '#14b8a6'),
  };
  const maxv = Math.max(1e-9, ...g.edges.map((e) => e.val || 0));
  const edgeFont = n > 16 ? 10 : 12;
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision" text-rendering="geometricPrecision" style="max-width:1100px;height:auto;margin:0 auto;background:var(--graph-bg);border:1px solid var(--graph-grid);border-radius:10px">`;
  s += '<defs>';
  ['default', 'path', 'mst', 'assign', 'flow', 'ship'].forEach((cls) => {
    s += `<marker id="arr-${cls}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${edgeColor[cls]}"/></marker>`;
  });
  s += '</defs>';
  const sorted = [...g.edges].sort((a, b) => (a.cls === 'default' ? 0 : 1) - (b.cls === 'default' ? 0 : 1));
  for (const e of sorted) {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) continue;
    const col = edgeColor[e.cls] || edgeColor.default;
    let w = (e.cls === 'default') ? 2.2 : ((e.cls === 'flow' || e.cls === 'ship') ? (2.4 + 6 * (e.val || 0) / maxv) : 3.8);
    const op = e.cls === 'default' ? 0.5 : 0.95;
    const r = nodeR + 2, dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    const ax = a[0] + dx / L * r, ay = a[1] + dy / L * r;
    const bx = b[0] - dx / L * r, by = b[1] - dy / L * r;
    s += `<line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${bx.toFixed(1)}" y2="${by.toFixed(1)}" stroke="${col}" stroke-width="${w.toFixed(1)}" opacity="${op}" stroke-linecap="round" ${g.directed ? `marker-end="url(#arr-${e.cls})"` : ''}/>`;
    if (e.label) {
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      s += `<text x="${mx.toFixed(1)}" y="${(my - 5).toFixed(1)}" text-anchor="middle" font-size="${edgeFont}" fill="${gv('--txt', '#334155')}" opacity="0.85">${esc(e.label)}</text>`;
    }
  }
  for (const n2 of g.nodes) {
    const p = pos[n2.id];
    const fill = nodeFill[n2.group] || nodeFill.default;
    s += `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${nodeR}" fill="${fill}" stroke="${gv('--net-node-b', '#64748b')}" stroke-width="2.2"/>`;
    s += `<text x="${p[0].toFixed(1)}" y="${(p[1] + font / 3).toFixed(1)}" text-anchor="middle" font-size="${font}" font-weight="700" fill="${gv('--txt', '#1e293b')}">${esc(n2.label)}</text>`;
  }
  s += '</svg>';
  const clsNames = { default: '普通边', path: '最短路径', mst: 'MST 边', flow: '有流量', ship: '运量', assign: '指派' };
  const grpNames = { default: '节点', src: '源点', sink: '汇点/目标', left: '产地/人员', right: '销地/任务' };
  const usedCls = [...new Set(g.edges.map((e) => e.cls))];
  const usedGrp = [...new Set(g.nodes.map((n) => n.group))];
  const clsLegend = usedCls.map((c) => `<span class="nl"><i style="background:${edgeColor[c] || edgeColor.default}"></i>${clsNames[c] || c}</span>`).join('');
  const grpLegend = usedGrp.map((gr) => `<span class="nl"><i class="dot" style="background:${nodeFill[gr] || nodeFill.default}"></i>${grpNames[gr] || gr}</span>`).join('');
  let widthNote = '';
  const hasFlow = usedCls.includes('flow'), hasShip = usedCls.includes('ship');
  if (hasFlow || hasShip) {
    const c = edgeColor[hasFlow ? 'flow' : 'ship'];
    const unit = (hasShip && !hasFlow) ? '运量' : '流量';
    const fmtNum = (v) => { v = Number(v) || 0; if (Math.abs(v - Math.round(v)) < 1e-9) return String(Math.round(v)); return v.toFixed(2).replace(/0+$/, '').replace(/\.$/, ''); };
    const widthFor = (v) => (2.4 + 6 * (maxv > 1e-9 ? v / maxv : 0));
    const swatch = (v) => `<span style="display:inline-flex;flex-direction:column;align-items:center;margin-right:12px"><svg width="48" height="14" shape-rendering="geometricPrecision" aria-hidden="true"><line x1="4" y1="7" x2="44" y2="7" stroke="${c}" stroke-width="${widthFor(v).toFixed(1)}" stroke-linecap="round"/></svg><span style="font-size:11px;color:var(--muted)">${fmtNum(v)}</span></span>`;
    const scaleRow = [0, maxv / 2, maxv].map(swatch).join('');
    const lbl = hasFlow ? '边标签 = 容量/流量（如 16/12：容量 16，实际流 12）' : '边标签 = 运量';
    const tail = hasFlow ? '；灰色细线 = 未走流的底图边' : '';
    widthNote = `<div style="margin-top:6px;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span>线宽刻度（${unit}）：</span>${scaleRow}</div><div style="font-size:12px;color:var(--muted);margin-top:2px">${lbl}${tail}</div>`;
  }
  s += `<div class="net-legend"><div>边：${clsLegend}</div><div>节点：${grpLegend}</div>${widthNote}</div>`;
  box.innerHTML = s;
}
window.drawNetGraph = drawNetGraph;

/* ---------------- 主题切换（默认浅色，可切深色） ---------------- */
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  const b = $('#theme-btn');
  if (b) b.textContent = (t === 'dark') ? '☀️ 切换到浅色' : '🌙 切换到深色';
  // 图解已绘制时，切主题后按新配色重画
  if (state.lpResult && state.lpResult.graph && state.bfsTrail) {
    drawGraph(state.lpResult.graph, state.bfsTrail[state.stepIdx], state.bfsTrail.slice(0, state.stepIdx + 1));
  }
  if (stateGen && stateGen.netgraph && window.drawNetGraph) drawNetGraph(stateGen.netgraph);
  if (stateGen && stateGen.chart && window.drawGenChart) drawGenChart(stateGen.chart);
}
function bindTheme() {
  $('#theme-btn').onclick = () => {
    const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    const next = cur === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('qsb-theme', next); } catch (e) {}
    applyTheme(next);
  };
}

/* ---------------- 启动 ---------------- */
function bindForms() {
  $('#lp-solve').onclick = solve;
  $('#lp-examples').onclick = () => loadExample('classic');
  $('#lp-nvar').onchange = buildModel;
  $('#lp-ncon').onchange = buildModel;
  $('#lp-obj').onchange = buildModel;
  $('#stub-back').onclick = () => { const m = state.modules.find((x) => x.id === 'lp'); if (m) selectModule(m); };
}

(async function init() {
  try {
    const data = await (await fetch('/api/modules')).json();
    state.modules = data.modules;
  } catch (e) {
    document.body.innerHTML = '<div style="padding:40px">无法连接后端：' + e + '</div>';
    return;
  }
  applyTheme(localStorage.getItem('qsb-theme') || 'light');
  bindTheme();
  buildNav();
  const lpm = state.modules.find((x) => x.id === 'lp');
  if (lpm && lpm.explain) { const le = $('#lp-explain'); le.innerHTML = lpm.explain; le.classList.remove('hidden'); }
  bindForms();
  loadExample('classic');
  showView('lp');
})();
