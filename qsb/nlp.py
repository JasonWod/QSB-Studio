"""非线性规划 (NLP)：二元函数 f(x,y) 的（约束）极小化。

* 目标可自定义表达式，也可选经典测试函数
* 约束 g(x,y) ≤ / ≥ / = 常数，用二次罚函数法转为一串无约束问题（罚系数 μ 逐轮放大）
* 每个无约束子问题用「最速下降 + Armijo 回溯线搜索」或「BFGS 拟牛顿」求解，梯度用中心差分
* 演示帧：函数热力图 + 不可行区域阴影 + 迭代路径逐步延伸
"""
import math

from . import expr as E
from . import parse as P
from . import report as R

PRESETS = {
    "custom": None,
    "bowl": "(x-2)^2 + (y-1)^2",
    "rosenbrock": "(1-x)^2 + 100*(y-x^2)^2",
    "booth": "(x+2*y-7)^2 + (2*x+y-5)^2",
    "himmelblau": "(x^2+y-11)^2 + (x+y^2-7)^2",
}

SPEC = {
    "desc": "非线性规划：极小化二元函数 f(x,y)，可加非线性约束。无约束时直接迭代；有约束时用罚函数法，"
            "把违反约束的程度平方后乘罚系数 μ 加进目标，μ 逐轮放大逼近约束最优。内层可选最速下降或 BFGS。",
    "form": [
        {"id": "func", "type": "select", "label": "目标函数", "value": "custom",
         "options": [{"v": "custom", "t": "自定义（填下方表达式）"},
                     {"v": "bowl", "t": "碗形 (x-2)²+(y-1)²"},
                     {"v": "rosenbrock", "t": "Rosenbrock 香蕉函数"},
                     {"v": "booth", "t": "Booth"},
                     {"v": "himmelblau", "t": "Himmelblau（4 个极小点）"}]},
        {"id": "expr", "type": "text", "label": "f(x, y) 表达式（选「自定义」时生效）",
         "value": "(x-3)^2 + (y-2)^2"},
        {"id": "constraints", "type": "textarea", "label": "约束（每行一个，如 x + y <= 4；可留空）",
         "rows": 3, "value": "x + y <= 4\nx^2 - y <= 2"},
        {"id": "start", "type": "list", "label": "起点 (x0, y0)", "value": "0, 0"},
        {"id": "method", "type": "select", "label": "内层算法", "value": "gd",
         "options": [{"v": "gd", "t": "最速下降 + Armijo 线搜索"},
                     {"v": "bfgs", "t": "BFGS 拟牛顿"}]},
    ],
}


def _parse_constraints(p):
    cons = []
    for ln in P.lines(p.get("constraints")):
        for sym, kind in (("<=", "le"), (">=", "ge"), ("≤", "le"), ("≥", "ge"), ("==", "eq"), ("=", "eq"),
                          ("<", "le"), (">", "ge")):
            if sym in ln:
                lhs, _, rhs = ln.partition(sym)
                g, _ = E.compile_expr(f"({lhs}) - ({rhs})")
                cons.append((ln, kind, g))
                break
        else:
            raise R.InputError(f"约束「{ln}」缺少 <=、>= 或 =。")
    if len(cons) > 6:
        raise R.InputError("最多 6 条约束。")
    return cons


def _violation(cons, x, y):
    """各约束违反量（≥0）。"""
    out = []
    for _, kind, g in cons:
        v = g(x, y)
        out.append(max(0.0, v) if kind == "le" else max(0.0, -v) if kind == "ge" else abs(v))
    return out


def _grad(F, x, y):
    hx, hy = 1e-6 * max(1.0, abs(x)), 1e-6 * max(1.0, abs(y))
    return ((F(x + hx, y) - F(x - hx, y)) / (2 * hx), (F(x, y + hy) - F(x, y - hy)) / (2 * hy))


def _minimize(F, x, y, method, max_iter, path, log, mu_label):
    """无约束极小化，把每次迭代追加进 path / log。返回终点。"""
    fx = F(x, y)
    H = [[1.0, 0.0], [0.0, 1.0]]          # BFGS 逆 Hessian 近似
    gx, gy = _grad(F, x, y)
    for _ in range(max_iter):
        gn = math.hypot(gx, gy)
        if gn < 1e-7:
            break
        if method == "bfgs":
            dx, dy = -(H[0][0] * gx + H[0][1] * gy), -(H[1][0] * gx + H[1][1] * gy)
            if dx * gx + dy * gy >= 0:        # 不是下降方向则重置
                H = [[1.0, 0.0], [0.0, 1.0]]
                dx, dy = -gx, -gy
        else:
            dx, dy = -gx, -gy
        slope = dx * gx + dy * gy
        t = 1.0
        while t > 1e-12:
            nx, ny = x + t * dx, y + t * dy
            nf = F(nx, ny)
            if nf <= fx + 1e-4 * t * slope:
                break
            t *= 0.5
        else:
            break
        ngx, ngy = _grad(F, nx, ny)
        if method == "bfgs":
            s = (nx - x, ny - y)
            q = (ngx - gx, ngy - gy)
            sy = s[0] * q[0] + s[1] * q[1]
            if sy > 1e-12:
                Hy = (H[0][0] * q[0] + H[0][1] * q[1], H[1][0] * q[0] + H[1][1] * q[1])
                yHy = q[0] * Hy[0] + q[1] * Hy[1]
                for i in range(2):
                    for j in range(2):
                        H[i][j] += ((sy + yHy) * s[i] * s[j]) / (sy * sy) - (Hy[i] * s[j] + s[i] * Hy[j]) / sy
        moved = math.hypot(nx - x, ny - y)
        x, y, fx, gx, gy = nx, ny, nf, ngx, ngy
        path.append((x, y))
        log.append((len(path) - 1, mu_label, x, y, fx, math.hypot(gx, gy), t))
        if moved < 1e-10:
            break
    return x, y


def solve(p):
    name = p.get("func", "custom")
    if name not in PRESETS:
        raise R.InputError("未知的目标函数选项。")
    src = p.get("expr") if name == "custom" else PRESETS[name]
    f, ftxt = E.compile_expr(src)
    cons = _parse_constraints(p)
    s = P.nums(p.get("start", "0,0"), "起点")
    if len(s) != 2:
        raise R.InputError("起点需要两个数，如「0, 0」。")
    method = p.get("method", "gd")
    if method not in ("gd", "bfgs"):
        raise R.InputError("内层算法只能是 gd 或 bfgs。")
    x, y = s
    if not math.isfinite(f(x, y)):
        raise R.InputError("目标函数在起点处无定义（例如对负数开方、除以 0），请换一个起点。")

    path = [(x, y)]
    log = [(0, "—", x, y, f(x, y), math.hypot(*_grad(f, x, y)), 0.0)]
    marks = [(0, "起点")]
    inner_iter = 3000 if method == "gd" else 400
    if not cons:
        x, y = _minimize(f, x, y, method, inner_iter, path, log, "—")
        mus = []
    else:
        mus = [1.0, 10.0, 100.0, 1e3, 1e4, 1e5]
        for mu in mus:
            F = (lambda m: (lambda a, b: f(a, b) + m * sum(v * v for v in _violation(cons, a, b))))(mu)
            x, y = _minimize(F, x, y, method, inner_iter, path, log, f"μ={mu:g}")
            marks.append((len(path) - 1, f"μ={mu:g} 结束"))
            if max(_violation(cons, x, y) or [0]) < 1e-6:
                break
    fx = f(x, y)
    viol = _violation(cons, x, y)
    feasible = (max(viol) if viol else 0.0) < 1e-3
    status = "optimal" if feasible else "infeasible"

    # ---- 平面图底图：网格范围覆盖路径并留白 ----
    xs = [q[0] for q in path]; ys = [q[1] for q in path]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    span = max(hi_x - lo_x, hi_y - lo_y, 2.0)
    cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
    half = span * 0.65
    xr, yr = [cx - half, cx + half], [cy - half, cy + half]
    G = 72
    grid, mask = [], []
    for j in range(G):
        yy = yr[0] + (yr[1] - yr[0]) * j / (G - 1)
        row, mrow = [], []
        for i in range(G):
            xx = xr[0] + (xr[1] - xr[0]) * i / (G - 1)
            v = f(xx, yy)
            row.append(round(v, 6) if math.isfinite(v) else None)
            if cons:
                mrow.append(1 if max(_violation(cons, xx, yy)) > 1e-9 else 0)
        grid.append(row)
        if cons:
            mask.append(mrow)
    # 路径抽样到 ≤400 点（保留起点、各轮结束点和终点），只在共享底图里存一份
    keep = set(range(0, len(path), max(1, len(path) // 400))) | {i for i, _ in marks} | {len(path) - 1}
    keep = sorted(keep)
    pos_in_keep = {}
    for j, i in enumerate(keep):
        pos_in_keep[i] = j
    base = {"type": "plane", "xr": xr, "yr": yr, "grid": grid, "mask": mask or None,
            "xlabel": "x", "ylabel": "y", "title": f"f(x,y) = {str(src).strip()}",
            "path": [[round(path[i][0], 6), round(path[i][1], 6)] for i in keep],
            "marks": [{"i": pos_in_keep[i], "label": lab} for i, lab in marks]}

    def plane(k, cur_label=None):
        upto = max(j for j, i in enumerate(keep) if i <= k)
        return {"type": "plane", "use": "plane", "upto": upto, "label": cur_label}

    frames = []
    for k, rec in enumerate(log):
        it, mu_l, xx, yy, fv, gn, t = rec
        if k == 0:
            title = "第 0 步：从起点出发"
            text = (f"起点 ({R.fmt(xx)}, {R.fmt(yy)})，f = {R.fmt(fv)}，梯度范数 ‖∇f‖ = {R.fmt(gn)}。"
                    + (f"有 {len(cons)} 条约束，图中阴影为不可行区域；先用罚系数 μ=1 把约束并入目标。" if cons else ""))
        else:
            title = f"第 {it} 次迭代" + (f"（{mu_l}）" if cons else "")
            text = (f"沿{'负梯度' if method == 'gd' else 'BFGS 搜索'}方向前进，线搜索接受步长 t = {R.fmt(t, 5)}，"
                    f"到达 ({R.fmt(xx)}, {R.fmt(yy)})，f = {R.fmt(f(xx, yy))}，‖∇F‖ = {R.fmt(gn, 6)}。")
            if cons:
                v = _violation(cons, xx, yy)
                text += f" 当前约束最大违反量 {R.fmt(max(v), 6)}。"
        frames.append(R.frame(title, text, chart=plane(k)))
    frames = R.thin(frames, 60)
    frames.append(R.frame("收敛结果",
                          f"终点 ({R.fmt(x)}, {R.fmt(y)})，f = {R.fmt(fx)}，共 {len(path) - 1} 次迭代。"
                          + ("满足全部约束。" if feasible else "仍违反约束，可能问题不可行或需更换起点。"),
                          chart=plane(len(path) - 1, "终点")))

    rows = [[k, mu, R.fmt(a), R.fmt(b), R.fmt(fv), R.fmt(gn, 6), R.fmt(t, 5)]
            for (k, mu, a, b, fv, gn, t) in log]
    if len(rows) > 40:
        rows = rows[:20] + [["…", "", "", "", "", "", ""]] + rows[-19:]
    tables = [R.table("NLP 结果", ["项", "值"],
                      [["目标函数", str(src).strip()], ["最优点 x*", R.fmt(x)], ["最优点 y*", R.fmt(y)],
                       ["f(x*, y*)", R.fmt(fx)], ["迭代次数", len(path) - 1],
                       ["内层算法", "最速下降 + Armijo" if method == "gd" else "BFGS 拟牛顿"],
                       ["起点", f"({R.fmt(s[0])}, {R.fmt(s[1])})"]]),
              R.table("迭代记录", ["k", "罚系数", "x", "y", "f / F", "‖∇‖", "步长 t"], rows)]
    if cons:
        tables.insert(1, R.table("约束检查", ["约束", "g(x*,y*) − 右端", "违反量", "是否起作用"],
                                 [[c[0], R.fmt(c[2](x, y), 6), R.fmt(v, 6),
                                   "是（取等号）" if abs(c[2](x, y)) < 1e-3 else "否"]
                                  for c, v in zip(cons, viol)]))
    return R.report(
        status,
        headline=(f"极小值 f ≈ {R.fmt(fx)}，在 (x, y) = ({R.fmt(x)}, {R.fmt(y)})，{len(path) - 1} 次迭代"
                  if feasible else "罚函数法未能得到满足约束的点"),
        tables=tables, steps=frames, chart=dict(base, **plane(len(path) - 1, "终点")),
        shared={"plane": base},
        notes=["Armijo 条件：f(x+t·d) ≤ f(x) + 10⁻⁴·t·∇fᵀd，不满足就把步长减半。",
               "罚函数法：F_μ = f + μ·Σ(违反量)²；μ 每轮放大 10 倍，解逐渐被「推」进可行域。" if cons else
               "无约束问题：梯度为 0 处即驻点。",
               "梯度法只保证局部最优，非凸函数换起点可能得到不同结果。"])


if __name__ == "__main__":
    r = solve({"func": "custom", "expr": "(x-3)^2+(y-2)^2", "constraints": "x+y<=4\nx^2-y<=2",
               "start": "0,0", "method": "gd"})
    print(r["headline"], len(r["steps"]))
