"""运输问题（产销平衡，最小费用调运）。
教学呈现：伏格尔法给初始基本可行解 → 用(已验证的)LP 单纯形求精确最优分配。
平衡性：供!=需 时自动补 0 成本虚拟产地/销地。
"""
from . import report as R
from . import lp
from . import graphviz as GV


def _as_list(v):
    if isinstance(v, str):
        return [float(x) for x in v.replace(",", " ").split()]
    return [float(x) for x in v]


def _as_matrix(v):
    if isinstance(v, str):
        return [[float(x) for x in ln.replace(",", " ").split()]
                for ln in v.splitlines() if ln.strip()]
    return v


def _vogel(supply, demand, cost, m, n):
    """伏格尔近似法，返回 m×n 初始分配。"""
    s = supply[:]; d = demand[:]
    rows = list(range(m)); cols = list(range(n))
    x = [[0.0] * n for _ in range(m)]
    while rows and cols:
        def row_pen(i):
            cs = sorted(cost[i][j] for j in cols)
            return (cs[1] - cs[0]) if len(cs) >= 2 else (cs[0] if cs else 0)
        def col_pen(j):
            cs = sorted(cost[i][j] for i in rows)
            return (cs[1] - cs[0]) if len(cs) >= 2 else (cs[0] if cs else 0)
        best = None
        for i in rows:
            pen = row_pen(i)
            if best is None or pen > best[0]:
                j = min(cols, key=lambda jj: cost[i][jj])
                best = (pen, i, j)
        for j in cols:
            pen = col_pen(j)
            if pen > best[0]:
                i = min(rows, key=lambda ii: cost[ii][j])
                best = (pen, i, j)
        _, i, j = best
        alloc = min(s[i], d[j])
        x[i][j] = alloc; s[i] -= alloc; d[j] -= alloc
        if abs(s[i]) < 1e-9:
            rows.remove(i)
        if abs(d[j]) < 1e-9:
            cols.remove(j)
    return x


def solve(p):
    supply = _as_list(p["supply"])
    demand = _as_list(p["demand"])
    cost = _as_matrix(p["cost"])
    m, n = len(supply), len(demand)
    if len(cost) != m or any(len(r) != n for r in cost):
        return R.report("error", headline="费用矩阵维度与供应/需求不符")

    # Vogel 初始解（仅教学展示）
    vogel = _vogel(supply[:], demand[:], cost, m, n)
    vogel_cost = sum(cost[i][j] * vogel[i][j] for i in range(m) for j in range(n))

    # 平衡
    S, D = sum(supply), sum(demand)
    bs, bd, bc, m2, n2 = supply[:], demand[:], cost, m, n
    if S < D:
        bs = bs + [D - S]; bc = bc + [[0.0] * n]; m2 += 1
    elif S > D:
        bd = bd + [S - D]; bc = [r + [0.0] for r in bc]; n2 += 1

    # 构造 LP：min Σ cost·x，s.t. 行和=供应、列和=需求，x≥0
    A, b, senses, c, names = [], [], [], [], []
    for i in range(m2):
        row = [0.0] * (m2 * n2)
        for j in range(n2):
            row[i * n2 + j] = 1.0
        A.append(row); b.append(bs[i]); senses.append("eq")
    for j in range(n2):
        row = [0.0] * (m2 * n2)
        for i in range(m2):
            row[i * n2 + j] = 1.0
        A.append(row); b.append(bd[j]); senses.append("eq")
    for i in range(m2):
        for j in range(n2):
            c.append(bc[i][j]); names.append(f"x{i + 1}_{j + 1}")
    res = lp.solve_lp("min", c, A, b, senses, names)
    if res.get("status") != "optimal":
        return R.report(res.get("status", "error"), headline=f"求解失败：{res.get('message', '不可行')}")

    # 提取最优分配（回到原维度）
    alloc = [[0.0] * n for _ in range(m)]
    for i in range(m):
        for j in range(n):
            alloc[i][j] = res["solution"].get(f"x{i + 1}_{j + 1}", 0.0)
    opt_cost = res.get("objective")
    sp = (res.get("sensitivity") or {}).get("shadow") or []

    # 展示矩阵
    def grid(G, title):
        headers = ["产地/销地"] + [f"销地{j + 1}" for j in range(n)] + ["供应量"]
        rows = []
        for i in range(m):
            rows.append([f"产地{i + 1}"] + [R.fmt(G[i][j]) for j in range(n)] + [R.fmt(supply[i])])
        rows.append(["需求"] + [R.fmt(demand[j]) for j in range(n)] + [""])
        return R.table(title, headers, rows)
    notes = [
        f"伏格尔法初始解成本 = {R.fmt(vogel_cost)}；优化后最优成本 = {R.fmt(opt_cost)}"
        + (f"（降低 {R.fmt(vogel_cost - opt_cost)}）" if abs(vogel_cost - opt_cost) > 1e-9 else "（伏格尔法一步到最优）"),
        "用产销平衡等式约束 + 非负变量构成 LP，单纯形求全局最优；行/列供应约束的对偶即位势 u_i、v_j。",
    ]
    tables = [grid(vogel, "伏格尔法初始分配"), grid(alloc, "最优分配（单纯形）")]
    if sp:
        dual_rows = []
        for i in range(m2):
            dual_rows.append([f"产地{i + 1} 供应"] + [R.fmt(sp[i])])
        for j in range(n2):
            dual_rows.append([f"销地{j + 1} 需求"] + [R.fmt(sp[m2 + j])])
        tables.append(R.table("影子价格 / 位势 (对偶)", ["约束", "对偶值"], dual_rows))

    # ---- 网络图：产地(左) → 销地(右)，运量弧线粗细表流量 ----
    left_ids = [f"L{i}" for i in range(m)]
    left_labels = [f"产地{i + 1}" for i in range(m)]
    right_ids = [f"R{j}" for j in range(n)]
    right_labels = [f"销地{j + 1}" for j in range(n)]
    edesc = []
    for i in range(m):
        for j in range(n):
            if alloc[i][j] > 1e-9:
                edesc.append((f"L{i}", f"R{j}", R.fmt(alloc[i][j]), "ship", alloc[i][j]))
    g = GV.bipartite_graph(left_ids, left_labels, right_ids, right_labels, edesc)
    return R.report("optimal", headline=f"最小运输总费用 = {R.fmt(opt_cost)}",
                    tables=tables, notes=notes, graph=g)


SPEC = {
    "desc": "产销平衡运输问题（最小费用调运）。伏格尔法给初始解，单纯形求精确最优。供≠需自动补虚拟产地/销地。",
    "form": [
        {"id": "supply", "type": "list", "label": "各产地供应量", "value": "30, 20, 50"},
        {"id": "demand", "type": "list", "label": "各销地需求量", "value": "35, 30, 35"},
        {"id": "cost", "type": "matrix", "label": "费用矩阵 (行=产地, 列=销地)", "rows": 3,
         "value": "6, 4, 7\n8, 5, 9\n7, 3, 4"},
    ],
}

if __name__ == "__main__":
    r = solve({"supply": [30, 20, 50], "demand": [35, 30, 35],
               "cost": [[6, 4, 7], [8, 5, 9], [7, 3, 4]]})
    print(r["status"], r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
