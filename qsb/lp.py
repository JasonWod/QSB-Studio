"""
qsb/lp.py — 线性规划求解器（教学版，纯标准库，无第三方依赖，可离线运行）

实现要点（clean-room，不复制 WinQSB 任何代码）：
  * 大M法(Big-M) + 字典法(dictionary)单纯形：每一步枢轴都记录，前端可做分步动画
  * 支持  max / min 目标；  ≤ / ≥ / =  约束；连续、非负变量
  * 影子价格（对偶值）：显式求基矩阵 B^{-1}，y = c_B^T B^{-1}
  * 两变量图解：各约束线方程 + 可行域顶点 + 最优点（交给前端画）
"""
from __future__ import annotations
import itertools

EPS = 1e-9


def _clean(v):
    if v is None:
        return None
    v = float(v)
    if abs(v) < 1e-7:
        return 0.0
    return round(v, 6)


# ---------------------------------------------------------------------------
# 标准形式构造（统一矩形矩阵）
# ---------------------------------------------------------------------------
def _build_extended(c, A, b, senses, M):
    """返回 (A_ext[m][ncols], b, c_mod[ncols], c_true[ncols], col_names, slack_col, art_cols)

    c_mod  = 求解用（max 的 modified）：原始变量取 c，人工变量取 -M，slack/surplus 取 0
    c_true = 真目标（对偶用）：原始变量取 c，其余 0
    """
    n = len(c)
    m = len(A)
    base = [f"x{i+1}" for i in range(n)]
    extra = []
    for i in range(m):
        spec = {}
        if senses[i] == "le":
            spec[f"s{i+1}"] = 1.0
        elif senses[i] == "ge":
            spec[f"st{i+1}"] = -1.0
            spec[f"a{i+1}"] = 1.0
        else:
            spec[f"a{i+1}"] = 1.0
        extra.append(spec)
    ordered = list(base)
    for spec in extra:
        for cn in spec:
            if cn not in ordered:
                ordered.append(cn)
    idx = {cn: k for k, cn in enumerate(ordered)}
    ncols = len(ordered)
    A_ext = [[0.0] * ncols for _ in range(m)]
    for i in range(m):
        for k in range(n):
            A_ext[i][idx[f"x{k+1}"]] = float(A[i][k])
        for cn, coef in extra[i].items():
            A_ext[i][idx[cn]] = coef
    c_mod = [0.0] * ncols
    c_true = [0.0] * ncols
    for k in range(n):
        c_mod[idx[f"x{k+1}"]] = c[k]
        c_true[idx[f"x{k+1}"]] = c[k]
    for i, spec in enumerate(extra):
        for cn in spec:
            if cn.startswith("a"):
                c_mod[idx[cn]] = -M
    slack_col, art_cols = {}, set()
    for i in range(m):
        if senses[i] == "le":
            slack_col[i] = idx[f"s{i+1}"]
        if senses[i] in ("ge", "eq"):
            art_cols.add(idx[f"a{i+1}"])
    return A_ext, list(b), c_mod, c_true, ordered, slack_col, art_cols


def _initial_basis(A_ext, b, slack_col, art_cols):
    """初始基 = 每个 ≤ 行 slack、每个 ≥/eq 行 artificial（构成单位阵）。"""
    m = len(A_ext)
    basis = []
    for i in range(m):
        basis.append(slack_col[i] if i in slack_col else _art_col(A_ext, i, art_cols))
    return basis


def _art_col(A_ext, row_i, art_cols):
    for j in art_cols:
        if abs(A_ext[row_i][j] - 1.0) < 1e-12:
            return j
    raise ValueError(f"row {row_i} has no artificial basis column")


# ---------------------------------------------------------------------------
# 字典法单纯形（max，Big-M）
# ---------------------------------------------------------------------------
def _make_dict(A_ext, b, c_mod, basis, col_names):
    """从 canonical 初始基构造字典。B 初始为单位阵。"""
    m = len(A_ext)
    N = [j for j in range(len(c_mod)) if j not in set(basis)]
    const, coef, rc = {}, {}, {}
    cb = [c_mod[bc] for bc in basis]
    z0 = sum(cb[i] * b[i] for i in range(m))
    for i, bc in enumerate(basis):
        const[bc] = b[i]
        coef[bc] = {j: A_ext[i][j] for j in N if abs(A_ext[i][j]) > 0.0}
    for j in N:
        zj = sum(cb[i] * A_ext[i][j] for i in range(m))
        rc[j] = c_mod[j] - zj
    return basis, N, const, coef, rc, z0


def _pivot(d, enter, leave):
    """就地枢轴。d = (basis,N,const,coef,rc,z0)。返回新字典元组。"""
    basis, N, const, coef, rc, z0 = d
    a = coef[leave][enter]
    # 新基变量 enter 的方程： x_enter = const[leave]/a - (1/a) x_leave - Σ_{j≠enter} (coef[leave][j]/a) x_j
    ncoef = {j: (1.0 if j == leave else coef[leave].get(j, 0.0) / a)
             for j in N if j != enter}
    # 修正：leave 现在是非基，系数 = 1/a；其它 j≠enter 系数 = coef[leave][j]/a
    ncoef[leave] = 1.0 / a
    newconst = {}
    newcoef = {}
    nN = [j for j in N if j != enter] + [leave]   # 新非基集合
    for base in basis:
        c_ie = coef[base].get(enter, 0.0)
        if base == leave:
            continue
        nc = const[base] - c_ie * const[leave] / a
        nb = {}
        for j in nN:
            if j == leave:
                v = -c_ie / a
            else:
                v = coef[base].get(j, 0.0) - c_ie * coef[leave].get(j, 0.0) / a
            nb[j] = v
        newconst[base] = nc
        newcoef[base] = nb
    # enter 行
    newconst[enter] = const[leave] / a
    newcoef[enter] = ncoef
    # 目标
    r_e = rc[enter]
    nz0 = z0 + r_e * const[leave] / a
    nrc = {}
    for j in nN:
        if j == leave:
            nrc[j] = -r_e / a
        else:
            nrc[j] = rc[j] - r_e * coef[leave].get(j, 0.0) / a
    nbasis = [enter if x == leave else x for x in basis]
    return nbasis, nN, newconst, newcoef, nrc, nz0


MAX_ITER = 5000
TOL_RC = 1e-7


def _simplex_dict(A_ext, b, c_mod, basis0, col_names, max_iter=MAX_ITER):
    """字典法单纯形（max）。

    进基规则：平时用 Dantzig 规则（最大检验数，教学上最直观）；一旦出现退化枢轴
    （最小比值为 0，目标值不变）就切换到 Bland 规则（最小下标进基、比值相同时最小下标离基），
    直到出现一次非退化枢轴再切回。Bland 规则保证退化段内不会循环，非退化枢轴严格改善目标，
    因此整个过程必然在有限步内终止。达到 max_iter 时返回 iteration_limit，绝不冒充最优。
    """
    d = _make_dict(A_ext, b, c_mod, basis0, col_names)
    steps = [_snapshot(d, col_names, "init")]
    it = 0
    status = "iteration_limit"
    bland = False
    while it < max_iter:
        it += 1
        basis, N, const, coef, rc, z0 = d
        cand = [j for j in N if rc[j] > TOL_RC]
        if not cand:
            status = "optimal"
            break
        if bland:
            enter = min(cand)
        else:
            enter = max(cand, key=lambda j: (rc[j], -j))
        # 离基：最小比值（coef[base][enter] > 0），比值相同取下标最小者
        leave, lb = -1, None
        for base in basis:
            cbe = coef[base].get(enter, 0.0)
            if cbe > EPS:
                r = const[base] / cbe
                if lb is None or r < lb - 1e-12 or (abs(r - lb) <= 1e-12 and base < leave):
                    lb, leave = r, base
        if leave == -1:
            status = "unbounded"
            break
        degenerate = lb <= 1e-10
        rule = "Bland" if bland else "Dantzig"
        d = _pivot(d, enter, leave)
        steps.append(_snapshot(d, col_names, "pivot", enter, col_names[enter], col_names[leave],
                               rule, degenerate))
        bland = degenerate
    return status, d, steps


def _snapshot(d, col_names, phase, enter=None, ename=None, lname=None, rule=None, degenerate=False):
    basis, N, const, coef, rc, z0 = d
    rows = []
    for base in basis:
        row = [0.0] * (len(col_names) + 1)
        for j in range(len(col_names)):
            if j == base:
                row[j] = 1.0
            elif j in N:
                row[j] = coef[base].get(j, 0.0)
        row[-1] = const[base]
        rows.append(row)
    obj = [0.0] * (len(col_names) + 1)
    for j in N:
        obj[j] = rc[j]
    obj[-1] = z0
    snap = {
        "phase": phase,
        "basis": [col_names[j] for j in basis],
        "columns": list(col_names),
        "rows": [[_clean(v) for v in r] for r in rows],
        "objective": [_clean(v) for v in obj],
        "objective_value": _clean(z0),
    }
    if phase == "pivot":
        snap["pivot"] = {"enter": ename, "leave": lname, "row": basis.index(enter),
                         "rule": rule, "degenerate": degenerate}
    return snap


# ---------------------------------------------------------------------------
# 基矩阵求逆（高斯-约当）+ 影子价格
# ---------------------------------------------------------------------------
def _invert(mat):
    n = len(mat)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(mat)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        if abs(a[p][i]) < 1e-12:
            raise SingularMatrix()
        a[i], a[p] = a[p], a[i]
        piv = a[i][i]
        a[i] = [v / piv for v in a[i]]
        for r in range(n):
            if r != i and abs(a[r][i]) > 0.0:
                f = a[r][i]
                a[r] = [a[r][k] - f * a[i][k] for k in range(2 * n)]
    return [row[n:] for row in a]


class SingularMatrix(Exception):
    pass


def _dual_shadow(A_ext, b, c_true, basis):
    """y = c_B^T B^{-1}，返回每约束的影子价格（list, len m）。"""
    m = len(A_ext)
    B = [[A_ext[i][bc] for bc in basis] for i in range(m)]
    try:
        Binv = _invert(B)
    except SingularMatrix:
        return [None] * m
    cb = [c_true[bc] for bc in basis]
    # y_j = Σ_i cb[i] * Binv[i][j]
    y = [sum(cb[i] * Binv[i][j] for i in range(m)) for j in range(m)]
    return y


def _sensitivity(A_ext, b, c_true, basis, col_names, n, obj, A2, b2, c_orig, art_cols=frozenset()):
    """灵敏度报告（教科书 sensitivity analysis），基于最优基 B：
       - 影子价格  y = c_B^T B^{-1}
       - 右端区间  对每个约束 i，使当前基保持可行的 b_i 范围（x_B = B^{-1} b 的线性扰动）
       - 目标系数区间 对每个变量 k，使当前基保持最优的 c_k 范围（检验数保持 ≤0）
    无穷界用 None 表示（前端渲染为 ∞）。求解方向用 c_use(=c_true)，展示方向按 obj 翻回。
    """
    m = len(A_ext)
    ncols = len(A_ext[0])
    B = [[A_ext[i][bc] for bc in basis] for i in range(m)]
    try:
        Binv = _invert(B)
    except SingularMatrix:
        return None
    xB = [sum(Binv[r][i] * b[i] for i in range(m)) for r in range(m)]  # 基变量值
    c_use_full = list(c_true)                     # originals = c_use，其余 0
    c_orig_full = c_true if obj == "max" else [-x for x in c_true]
    cb_use = [c_use_full[bc] for bc in basis]
    y_use = [sum(cb_use[i] * Binv[i][j] for i in range(m)) for j in range(m)]
    cb_orig = [c_orig_full[bc] for bc in basis]
    shadow = [sum(cb_orig[i] * Binv[i][j] for i in range(m)) for j in range(m)]
    pos = {bc: p for p, bc in enumerate(basis)}
    N = [j for j in range(ncols) if j not in pos]
    rc_use = {j: c_use_full[j] - sum(y_use[t] * A_ext[t][j] for t in range(m)) for j in N}
    # 真实非基变量（排除人工变量——它们只是起步装置，其检验数无经济意义）
    N_real = [j for j in N if j not in art_cols]

    INF = 1e18
    def fb(x):
        if x is None:
            return None
        if x <= -INF / 2 or x >= INF / 2:
            return None
        return _clean(x)

    # ---- 右端（RHS）灵敏度：目标无关，只看可行性 ----
    rhs = []
    for i in range(m):
        col = [Binv[r][i] for r in range(m)]     # B^{-1} 的第 i 列
        dlo, dhi = -INF, INF                     # δ（b_i 的增量）界
        for r in range(m):
            ccol, v = col[r], xB[r]
            if ccol > EPS:
                dlo = max(dlo, -v / ccol)        # v + ccol·δ ≥ 0  =>  δ ≥ -v/ccol
            elif ccol < -EPS:
                dhi = min(dhi, -v / ccol)        #                    δ ≤ -v/ccol
        dec = (-dlo) if dlo != -INF else None
        inc = dhi if dhi != INF else None
        rhs.append({
            "i": i, "name": f"约束{i+1}", "value": _clean(b2[i]),
            "shadow": _clean(shadow[i]),
            "allow_inc": fb(inc), "allow_dec": fb(dec),
            "range": [fb(None if dlo == -INF else b2[i] + dlo),
                      fb(None if dhi == INF else b2[i] + dhi)],
        })

    # ---- 目标系数灵敏度 ----
    obj_rows = []
    for k in range(n):
        cu = c_use_full[k]
        if k in pos:                                # 基变量：rc_j' = rj - δ·d ≤ 0
            p = pos[k]
            brow = [Binv[p][t] for t in range(m)]
            dlo, dhi = -INF, INF
            for j in N_real:
                d = sum(brow[t] * A_ext[t][j] for t in range(m))
                rj = rc_use[j]
                if d > EPS:
                    dlo = max(dlo, rj / d)          # d>0  =>  δ ≥ rj/d  (下界)
                elif d < -EPS:
                    dhi = min(dhi, rj / d)          # d<0  =>  δ ≤ rj/d  (上界)
            u_lo, u_hi = cu + dlo, cu + dhi         # c_use 空间
        else:                                       # 非基变量：rc' = rj + δ ≤ 0  =>  δ ≤ -rj
            rj = rc_use[k]
            u_lo, u_hi = -INF, cu - rj
        if obj == "min":                            # 展示方向翻回原 min
            u_lo, u_hi = (-u_hi if u_hi != INF else -INF), (-u_lo if u_lo != -INF else INF)
        cur = c_orig_full[k]
        rcdisp = 0.0 if k in pos else (_clean(rc_use[k] * (1 if obj == "max" else -1)))
        obj_rows.append({
            "i": k, "name": col_names[k], "value": _clean(cur),
            "reduced_cost": rcdisp,
            "allow_inc": fb(u_hi - cur if u_hi != INF else None),
            "allow_dec": fb(cur - u_lo if u_lo != -INF else None),
            "range": [fb(None if u_lo == -INF else u_lo),
                      fb(None if u_hi == INF else u_hi)],
        })

    return {"shadow": [_clean(v) for v in shadow], "rhs": rhs, "objective": obj_rows}


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------
class LPInputError(ValueError):
    pass


def validate(obj, c, A, b, senses, var_names, max_vars=40, max_cons=120):
    """检查 LP 输入维度，返回错误说明（None 表示合法）。"""
    if obj not in ("max", "min"):
        return "目标方向必须是 max 或 min。"
    n, m = len(c), len(A)
    if n == 0:
        return "至少需要 1 个决策变量。"
    if m == 0:
        return "至少需要 1 条约束。"
    if n > max_vars or m > max_cons:
        return f"规模超过教学版上限（变量 ≤ {max_vars}，约束 ≤ {max_cons}）。"
    if len(b) != m or len(senses) != m:
        return "约束系数、右端常数、约束类型的条数不一致。"
    if any(len(row) != n for row in A):
        return f"每条约束都应有 {n} 个系数（与变量个数一致）。"
    if any(s not in ("le", "ge", "eq") for s in senses):
        return "约束类型只能是 le(≤) / ge(≥) / eq(=)。"
    if len(var_names) != n:
        return "变量名个数与变量个数不一致。"
    vals = list(c) + list(b) + [v for row in A for v in row]
    try:
        if any(not (abs(float(v)) < 1e12) for v in vals):
            return "系数中有非有限值或过大的数（|值| 须 < 1e12）。"
    except (TypeError, ValueError):
        return "系数必须全部是数字。"
    return None


def solve_lp(obj, c, A, b, senses, var_names, M=None):
    err = validate(obj, c, A, b, senses, var_names)
    if err:
        raise LPInputError(err)
    if M is None:   # 大 M 随目标系数量级自适应，保证足够「大」又不至于吃掉浮点精度
        M = 1e5 * max(1.0, max(abs(float(x)) for x in c))
    # 右端标准化非负
    A2 = [list(map(float, row)) for row in A]
    b2 = [float(x) for x in b]
    s2 = list(senses)
    flip = {"le": "ge", "ge": "le", "eq": "eq"}
    for i in range(len(A2)):
        if b2[i] < 0:
            A2[i] = [-v for v in A2[i]]
            b2[i] = -b2[i]
            s2[i] = flip[s2[i]]

    n = len(c)
    c_use = [float(x) for x in c] if obj == "max" else [-float(x) for x in c]

    A_ext, b_ext, c_mod, c_true, col_names, slack_col, art_cols = _build_extended(
        c_use, A2, b2, s2, M
    )
    basis0 = _initial_basis(A_ext, b_ext, slack_col, art_cols)
    status, d, steps = _simplex_dict(A_ext, b_ext, c_mod, basis0, col_names)
    basis, N, const, coef, rc, z0 = d

    # 人工变量仍 > 0 -> 不可行
    if any(j in art_cols and abs(const[j]) > 1e-5 for j in basis):
        status = "infeasible"

    sol = {}
    for i in range(n):
        col = i
        sol[var_names[i]] = _clean(const[col]) if col in set(basis) else 0.0

    # 真实目标值直接用原始 c 计算（不依赖求解方向与大 M 项，min/max 都不会变号）
    objective = _clean(sum(float(c[i]) * float(sol[var_names[i]]) for i in range(n))) \
        if status == "optimal" else None

    # 每一步的「当前基可行解」与真实目标值，供前端动画解说（大 M 的人工变量单独提示）
    for st in steps:
        cols = st["columns"]
        xs = []
        for k in range(n):
            nm = col_names[k]
            xs.append(st["rows"][st["basis"].index(nm)][len(cols)] if nm in st["basis"] else 0.0)
        st["x"] = [_clean(v) for v in xs]
        st["real_objective"] = _clean(sum(float(c[k]) * xs[k] for k in range(n)))
        st["artificial_in_basis"] = [nm for nm in st["basis"] if col_names.index(nm) in art_cols
                                     and abs(st["rows"][st["basis"].index(nm)][len(cols)]) > 1e-9]

    # 影子价格：用真目标符号（max 用 c，min 用 c；但求解是 -c，对偶需按求解方向，这里按 max 约定）
    y = _dual_shadow(A_ext, b_ext, c_true if obj == "max" else [-x for x in c_true], basis)
    shadow = {}
    for i in range(len(A2)):
        # 该约束对应的对偶值 y[i]
        v = y[i]
        if v is None:
            shadow[f"约束{i+1}"] = None
        else:
            shadow[f"约束{i+1}"] = _clean(v)

    reduced = {}
    for i in range(n):
        if i not in set(basis):
            reduced[var_names[i]] = _clean(rc[i])

    final = _snapshot(d, col_names, "final")

    # 灵敏度报告（仅最优基有意义）
    sensitivity = None
    if status == "optimal":
        sensitivity = _sensitivity(A_ext, b_ext, c_true, basis, col_names, n,
                                   obj, A2, b2, [float(x) for x in c], art_cols)

    return {
        "status": status,
        "objective": objective,
        "objective_value_display": objective,
        "message": {"infeasible": "问题不可行：没有任何点能同时满足所有约束。",
                    "unbounded": "问题无界：目标值可以无限改善。",
                    "iteration_limit": f"单纯形迭代超过 {MAX_ITER} 次仍未结束，已停止（结果不可信）。"}.get(status),
        "solution": sol,
        "steps": steps,
        "final_tableau": {
            "columns": final["columns"],
            "basis": final["basis"],
            "rows": final["rows"],
            "objective": final["objective"],
        },
        "shadow_prices": shadow,
        "reduced_costs": reduced,
        "sensitivity": sensitivity,
        "num_pivots": len(steps) - 1,
        "big_m": M,
    }


# ---------------------------------------------------------------------------
# 两变量图解数据
# ---------------------------------------------------------------------------
def graph_2var(c, A, b, senses, var_names, solution, obj):
    if len(c) != 2:
        return None
    x1n, x2n = var_names[0], var_names[1]
    lines = [{"name": f"约束{i+1}", "a1": float(A[i][0]), "a2": float(A[i][1]),
              "b": float(b[i]), "sense": senses[i], "vertical": abs(A[i][1]) < 1e-12}
             for i in range(len(A))]
    pts = set()
    for (i, r1), (j, r2) in itertools.combinations(
        [(i, A[i]) for i in range(len(A))], 2):
        det = r1[0] * r2[1] - r1[1] * r2[0]
        if abs(det) < 1e-12:
            continue
        b1, b2 = float(b[i]), float(b[j])
        x1 = (b1 * r2[1] - b2 * r1[1]) / det
        x2 = (r1[0] * b2 - r2[0] * b1) / det
        if x1 < -1e-9 or x2 < -1e-9:
            continue
        if _feasible(x1, x2, A, b, senses):
            pts.add((round(x1, 6), round(x2, 6)))
    vertices = sorted(pts)
    if (0.0, 0.0) not in vertices and _feasible(0, 0, A, b, senses):
        vertices.append((0.0, 0.0))
    opt = (float(solution.get(x1n, 0.0)), float(solution.get(x2n, 0.0)))
    iso = {"slope": -float(c[0]) / float(c[1]), "through": opt} if abs(c[1]) > 1e-12 else None
    zval = c[0] * opt[0] + c[1] * opt[1]
    return {"lines": lines, "vertices": vertices, "optimum": opt, "iso_line": iso,
            "objective_value": zval}


def _feasible(x1, x2, A, b, senses, eps=1e-6):
    for i, row in enumerate(A):
        val = row[0] * x1 + row[1] * x2
        if senses[i] == "le" and val > b[i] + eps:
            return False
        if senses[i] == "ge" and val < b[i] - eps:
            return False
        if senses[i] == "eq" and abs(val - b[i]) > eps:
            return False
    return True
