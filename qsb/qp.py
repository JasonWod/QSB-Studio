"""二次规划 (QP)：min ½xᵀQx + cᵀx，s.t. 线性约束 Ax (≤/≥/=) b，可选 x ≥ 0。

算法：原始有效集法（active-set method，凸 QP 的教科书算法）。
  1. 从可行点出发，把取等号的约束放进「有效集」W；
  2. 在 W 上解等式约束子问题（KKT 方程组）得到搜索方向 p；
  3. p≠0：沿 p 前进，若被某条约束挡住就把它加入 W；
     p=0：看拉格朗日乘子 λ，全部 ≥0 即最优（KKT 条件成立），否则把 λ 最负的约束移出 W。
演示帧：2 变量时画目标热力图 + 不可行区阴影 + 迭代点，逐步显示有效集的增删。
"""
import math

from . import lp as _lp
from . import parse as P
from . import report as R

SPEC = {
    "desc": "二次规划：目标 ½xᵀQx + cᵀx（Q 对称正定 → 凸，最优解唯一），约束为一般线性约束。"
            "用有效集法：在当前起作用的约束上解 KKT 方程，被新约束挡住就加入有效集，乘子为负就移出，直到 KKT 条件成立。",
    "form": [
        {"id": "Q", "type": "matrix", "label": "二次项矩阵 Q（每行逗号分隔，对称正定）", "rows": 2, "value": "2, 0\n0, 2"},
        {"id": "c", "type": "list", "label": "一次项系数 c", "value": "-6, -4"},
        {"id": "constraints", "type": "textarea", "label": "线性约束（每行 a1,a2,... <= b，也可 >= / =）",
         "rows": 3, "value": "1, 1 <= 3\n1, 0 <= 1.5"},
        {"id": "nonneg", "type": "select", "label": "变量非负 x ≥ 0", "value": "yes",
         "options": [{"v": "yes", "t": "是"}, {"v": "no", "t": "否（自由变量）"}]},
        {"id": "start", "type": "list", "label": "起点（须可行；留空自动找）", "value": "0, 0"},
    ],
}

TOL = 1e-9


def _solve_linear(M, rhs):
    """高斯消元（列主元）。奇异返回 None。"""
    n = len(M)
    a = [row[:] + [rhs[i]] for i, row in enumerate(M)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(a[r][i]))
        if abs(a[piv][i]) < 1e-12:
            return None
        a[i], a[piv] = a[piv], a[i]
        for r in range(n):
            if r != i and a[r][i] != 0.0:
                fct = a[r][i] / a[i][i]
                for k in range(i, n + 1):
                    a[r][k] -= fct * a[i][k]
    return [a[i][n] / a[i][i] for i in range(n)]


def _is_pd(Q):
    n = len(Q)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = Q[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 1e-12:
                    return False
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return True


def _rank_ok(rows):
    """rows 是否线性无关（高斯消元求秩）。"""
    if not rows:
        return True
    a = [r[:] for r in rows]
    m, n = len(a), len(a[0])
    rank, col = 0, 0
    while rank < m and col < n:
        piv = max(range(rank, m), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-10:
            col += 1
            continue
        a[rank], a[piv] = a[piv], a[rank]
        for r in range(rank + 1, m):
            f = a[r][col] / a[rank][col]
            a[r] = [a[r][k] - f * a[rank][k] for k in range(n)]
        rank += 1
        col += 1
    return rank == m


def _feasible_point(n, cons, nonneg):
    """用 LP（目标为 0）找一个可行点；自由变量拆成 x = u − v。"""
    if nonneg:
        A = [c[0] for c in cons]; b = [c[2] for c in cons]; s = [c[1] for c in cons]
        r = _lp.solve_lp("min", [0.0] * n, A, b, s, [f"x{i}" for i in range(n)])
        return [float(r["solution"][f"x{i}"]) for i in range(n)] if r["status"] == "optimal" else None
    A = [c[0] + [-v for v in c[0]] for c in cons]; b = [c[2] for c in cons]; s = [c[1] for c in cons]
    r = _lp.solve_lp("min", [0.0] * (2 * n), A, b, s, [f"z{i}" for i in range(2 * n)])
    if r["status"] != "optimal":
        return None
    z = [float(r["solution"][f"z{i}"]) for i in range(2 * n)]
    return [z[i] - z[n + i] for i in range(n)]


def solve(p):
    Q = P.square(p.get("Q"), "矩阵 Q", 1, 8)
    c = P.nums(p.get("c"), "一次项系数 c")
    n = len(c)
    if len(Q) != n:
        raise R.InputError(f"Q 是 {len(Q)}×{len(Q)}，但 c 有 {n} 个分量，维度必须一致。")
    asym = max(abs(Q[i][j] - Q[j][i]) for i in range(n) for j in range(n))
    Q = [[(Q[i][j] + Q[j][i]) / 2 for j in range(n)] for i in range(n)]
    if not _is_pd(Q):
        raise R.InputError("Q 必须正定（例如对角元为正且占优）。教学版的有效集法要求严格凸的目标。")
    cons = []
    for ln in P.lines(p.get("constraints")):
        cons.append(P.constraint(ln, n))
    nonneg = p.get("nonneg", "yes") in ("yes", True, "true", "1")
    if len(cons) > 30:
        raise R.InputError("最多 30 条线性约束。")

    # 统一成 a·x ≤ b（等式单独标记），非负约束写成 −x_i ≤ 0
    rows, kinds, labels = [], [], []
    for k, (a, op, bv) in enumerate(cons):
        if op == "ge":
            rows.append(([-v for v in a], -bv)); kinds.append("ineq")
        else:
            rows.append((a[:], bv)); kinds.append("eq" if op == "eq" else "ineq")
        labels.append(f"约束{k + 1}")
    if nonneg:
        for i in range(n):
            a = [0.0] * n; a[i] = -1.0
            rows.append((a, 0.0)); kinds.append("ineq"); labels.append(f"x{i + 1}≥0")
    m = len(rows)
    dot = lambda u, v: sum(u[i] * v[i] for i in range(len(u)))
    fobj = lambda x: 0.5 * sum(Q[i][j] * x[i] * x[j] for i in range(n) for j in range(n)) + dot(c, x)
    slack = lambda i, x: rows[i][1] - dot(rows[i][0], x)
    feas = lambda x: all((abs(slack(i, x)) < 1e-7 if kinds[i] == "eq" else slack(i, x) > -1e-7) for i in range(m))

    s = P.nums(p.get("start"), "起点")
    note_start = ""
    if s and len(s) != n:
        raise R.InputError(f"起点需要 {n} 个分量。")
    if not s or not feas(s):
        if s:
            note_start = "给定起点不可行，已用 LP 自动找一个可行起点。"
        s = _feasible_point(n, cons, nonneg)
        if s is None:
            return R.report("infeasible", headline="约束互相矛盾，可行域为空。")
    x = s[:]

    W = []
    for i in range(m):
        if (kinds[i] == "eq" or abs(slack(i, x)) < 1e-9) and _rank_ok([rows[j][0] for j in W] + [rows[i][0]]):
            W.append(i)

    path = [x[:]]
    log = []
    frames_meta = [("初始化", f"从可行点 x = ({', '.join(R.fmt(v) for v in x)}) 出发，f = {R.fmt(fobj(x))}。"
                   f"{note_start}起作用约束（有效集）W = {{{', '.join(labels[i] for i in W) or '空'}}}。", W[:], None)]
    status = "iteration_limit"
    lam_final = {}
    for it in range(1, 200):
        g = [sum(Q[i][j] * x[j] for j in range(n)) + c[i] for i in range(n)]
        k = len(W)
        K = [[0.0] * (n + k) for _ in range(n + k)]
        for i in range(n):
            for j in range(n):
                K[i][j] = Q[i][j]
        for t, wi in enumerate(W):
            for j in range(n):
                K[n + t][j] = rows[wi][0][j]
                K[j][n + t] = rows[wi][0][j]
        sol = _solve_linear(K, [-v for v in g] + [0.0] * k)
        if sol is None:
            return R.report("error", headline="KKT 方程组奇异（有效集约束线性相关）", message="请检查是否有重复约束。")
        pdir, lam = sol[:n], sol[n:]
        if math.sqrt(dot(pdir, pdir)) < 1e-9:
            ineq = [(lam[t], W[t]) for t in range(k) if kinds[W[t]] == "ineq"]
            neg = [it_ for it_ in ineq if it_[0] < -1e-9]
            lam_txt = "，".join(f"λ({labels[wi]}) = {R.fmt(lv)}" for lv, wi in zip(lam, W)) or "（有效集为空）"
            if not neg:
                status = "optimal"
                lam_final = {W[t]: lam[t] for t in range(k)}
                frames_meta.append((f"第 {it} 步：检验 KKT 条件",
                                    f"在当前有效集上方向 p = 0，乘子 {lam_txt} 都 ≥ 0 → KKT 条件成立，当前点就是最优解。",
                                    W[:], "opt"))
                log.append((it, "最优", x[:], fobj(x), W[:], lam_txt))
                break
            lv, wi = min(neg)
            W.remove(wi)
            frames_meta.append((f"第 {it} 步：移出约束",
                                f"p = 0，但乘子 {lam_txt} 中 {labels[wi]} 的 λ = {R.fmt(lv)} < 0，说明离开这条约束还能继续下降，"
                                f"把它移出有效集。", W[:], None))
            log.append((it, f"移出 {labels[wi]}", x[:], fobj(x), W[:], lam_txt))
            continue
        alpha, block = 1.0, None
        for i in range(m):
            if i in W or kinds[i] == "eq":
                continue
            ap = dot(rows[i][0], pdir)
            if ap > TOL:
                step = slack(i, x) / ap
                if step < alpha - 1e-12:
                    alpha, block = max(0.0, step), i
        x = [x[j] + alpha * pdir[j] for j in range(n)]
        path.append(x[:])
        ptxt = f"({', '.join(R.fmt(v) for v in pdir)})"
        if block is not None:
            W.append(block)
            frames_meta.append((f"第 {it} 步：沿方向前进，被约束挡住",
                                f"在有效集上解 KKT 得方向 p = {ptxt}；走到步长 α = {R.fmt(alpha)} 时碰到 {labels[block]}，"
                                f"停在 x = ({', '.join(R.fmt(v) for v in x)})，f = {R.fmt(fobj(x))}，把 {labels[block]} 加入有效集。",
                                W[:], None))
            log.append((it, f"前进 α={R.fmt(alpha)}，加入 {labels[block]}", x[:], fobj(x), W[:], ""))
        else:
            frames_meta.append((f"第 {it} 步：沿方向走满一步",
                                f"方向 p = {ptxt}，整步 α = 1 不碰任何约束，到达当前有效集上的最优点 "
                                f"x = ({', '.join(R.fmt(v) for v in x)})，f = {R.fmt(fobj(x))}。", W[:], None))
            log.append((it, "前进 α=1", x[:], fobj(x), W[:], ""))

    # ---- 图示 ----
    base = None
    if n == 2:
        xs = [q[0] for q in path]; ys = [q[1] for q in path]
        try:
            xu = _solve_linear(Q, [-v for v in c])   # 无约束极小点，帮助定范围
        except Exception:
            xu = None
        if xu:
            xs.append(xu[0]); ys.append(xu[1])
        lo_x, hi_x, lo_y, hi_y = min(xs + [0]), max(xs), min(ys + [0]), max(ys)
        span = max(hi_x - lo_x, hi_y - lo_y, 2.0)
        cx, cy = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
        xr, yr = [cx - span * 0.65, cx + span * 0.65], [cy - span * 0.65, cy + span * 0.65]
        G = 56
        grid, mask = [], []
        for j in range(G):
            yy = yr[0] + (yr[1] - yr[0]) * j / (G - 1)
            grid.append([round(fobj([xr[0] + (xr[1] - xr[0]) * i / (G - 1), yy]), 6) for i in range(G)])
            mask.append([0 if feas([xr[0] + (xr[1] - xr[0]) * i / (G - 1), yy]) else 1 for i in range(G)])
        lines = [{"a1": rows[i][0][0], "a2": rows[i][0][1], "b": rows[i][1], "label": labels[i]}
                 for i in range(m)]
        base = {"type": "plane", "xr": xr, "yr": yr, "grid": grid, "mask": mask, "lines": lines,
                "xlabel": "x1", "ylabel": "x2", "title": "½xᵀQx + cᵀx",
                "path": [[round(a, 6), round(b, 6)] for a, b in path]}

    frames = []
    pi = 0
    for title, text, Wk, flag in frames_meta:
        if "前进" in title or "走满" in title or "挡住" in title:
            pi += 1
        ch = None
        if base:
            ch = {"type": "plane", "use": "plane", "upto": pi,
                  "active": [labels.index(labels[i]) for i in Wk], "label": "最优" if flag == "opt" else None}
        tb = R.table("当前状态", ["项", "值"],
                     [["当前点 x", ", ".join(R.fmt(v) for v in path[pi])],
                      ["目标 f(x)", R.fmt(fobj(path[pi]))],
                      ["有效集 W", ", ".join(labels[i] for i in Wk) or "空"]])
        frames.append(R.frame(title, text, tables=[tb], chart=ch))

    rows_out = [[f"x{i + 1}", R.fmt(x[i])] for i in range(n)]
    cons_rows = [[labels[i], R.fmt(slack(i, x)), "是" if abs(slack(i, x)) < 1e-7 else "否",
                  R.fmt(lam_final.get(i, 0.0))] for i in range(m)]
    log_rows = [[it, act, ", ".join(R.fmt(v) for v in xx), R.fmt(fv), ", ".join(labels[i] for i in Wk) or "空"]
                for it, act, xx, fv, Wk, _ in log]
    notes = ["KKT 条件：∇f(x*) + Σλᵢaᵢ = 0，起作用不等式约束的乘子 λᵢ ≥ 0。",
             "乘子 λᵢ 也是影子价格：约束右端放宽 1 单位，目标约下降 λᵢ。"]
    if asym > 1e-12:
        notes.insert(0, "输入的 Q 不对称，已按 (Q+Qᵀ)/2 对称化（二次型取值不变）。")
    head = (f"二次规划最优：x = ({', '.join(R.fmt(v) for v in x)})，目标值 = {R.fmt(fobj(x))}"
            if status == "optimal" else "有效集法未在 200 步内收敛")
    return R.report(status, headline=head,
                    tables=[R.table("最优解", ["变量", "值"], rows_out),
                            R.table("约束状态（松弛量 = 右端 − 左端）", ["约束", "松弛量", "起作用", "乘子 λ"], cons_rows),
                            R.table("有效集迭代记录", ["步", "动作", "x", "f(x)", "有效集 W"], log_rows)],
                    chart=dict(base, upto=len(path) - 1, label="最优") if base else None,
                    steps=frames, shared={"plane": base} if base else None, notes=notes)


if __name__ == "__main__":
    r = solve({"Q": "2,0\n0,2", "c": "-6,-4", "constraints": "1,1<=3\n1,0<=1.5", "nonneg": "yes", "start": "0,0"})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"])
