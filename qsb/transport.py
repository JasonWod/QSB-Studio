"""运输问题（最小费用调运）：伏格尔法初始解 + 位势法（MODI）最优性检验 + 闭回路调整。

* 供 ≠ 需时自动补 0 运费的虚拟产地 / 虚拟销地
* 伏格尔法：每轮算各行各列「次小运费 − 最小运费」罚数，在罚数最大的行/列里填最便宜的格
* 退化（基格不足 m+n−1 个）时补 0 运量的基格，保持基格构成生成树
* 位势法：由基格 uᵢ + vⱼ = cᵢⱼ 求位势，非基格检验数 σᵢⱼ = cᵢⱼ − uᵢ − vⱼ；
  有负检验数就让它进基，沿闭回路 +θ / −θ 调整，直到全部 σ ≥ 0
"""
from collections import deque

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "运输问题：伏格尔法给初始调运方案，再用位势法（MODI）求检验数，负检验数的格沿闭回路调整运量，"
            "直到所有检验数 ≥ 0 即最优。供≠需时自动补虚拟产地/销地。",
    "form": [
        {"id": "supply", "type": "list", "label": "各产地供应量", "value": "10, 40, 10"},
        {"id": "demand", "type": "list", "label": "各销地需求量", "value": "15, 10, 15, 20"},
        {"id": "cost", "type": "matrix", "label": "运费矩阵 (行=产地, 列=销地)", "rows": 3,
         "value": "4, 10, 13, 7\n3, 14, 4, 9\n12, 8, 3, 8"},
    ],
}

EPS = 1e-9


def _vogel(supply, demand, cost, m, n, rl, cl):
    s, d = supply[:], demand[:]
    rows, cols = set(range(m)), set(range(n))
    x = [[0.0] * n for _ in range(m)]
    basic = set()
    frames = []

    def pen(vals):
        vs = sorted(vals)
        return (vs[1] - vs[0]) if len(vs) >= 2 else (vs[0] if vs else 0.0)

    k = 0
    while rows and cols:
        k += 1
        rp = {i: pen([cost[i][j] for j in cols]) for i in rows}
        cp = {j: pen([cost[i][j] for i in rows]) for j in cols}
        best = max([(v, 0, i) for i, v in rp.items()] + [(v, 1, j) for j, v in cp.items()],
                   key=lambda t: (t[0], -t[1], -t[2]))
        if best[1] == 0:
            i = best[2]; j = min(cols, key=lambda jj: (cost[i][jj], jj))
            why = f"{rl[i]} 的罚数 {R.fmt(best[0])} 最大，在该行选运费最低的 {cl[j]}"
        else:
            j = best[2]; i = min(rows, key=lambda ii: (cost[ii][j], ii))
            why = f"{cl[j]} 的罚数 {R.fmt(best[0])} 最大，在该列选运费最低的 {rl[i]}"
        q = min(s[i], d[j])
        x[i][j] = q; basic.add((i, j))
        s[i] -= q; d[j] -= q
        # 行列同时满足时只划去一个（保持基格数 m+n−1）；最后一行/列时两者都划
        if abs(s[i]) < EPS and abs(d[j]) < EPS and len(rows) > 1 and len(cols) > 1:
            rows.discard(i)
        else:
            if abs(s[i]) < EPS:
                rows.discard(i)
            if abs(d[j]) < EPS:
                cols.discard(j)
        hdr = ["产地\\销地"] + cl + ["行罚数"]
        body = []
        for r in range(m):
            body.append([rl[r]] + [(R.fmt(x[r][c]) if (r, c) in basic else f"({R.fmt(cost[r][c])})") for c in range(n)]
                        + [R.fmt(rp[r]) if r in rp else "—"])
        body.append(["列罚数"] + [R.fmt(cp[c]) if c in cp else "—" for c in range(n)] + [""])
        cells = {(r, c + 1): "c-basic" for (r, c) in basic}
        cells[(i, j + 1)] = "c-enter"
        frames.append(R.frame(
            f"伏格尔第 {k} 步", f"{why}，填入 min(剩余供应 {R.fmt(s[i] + q)}, 剩余需求 {R.fmt(d[j] + q)}) = {R.fmt(q)}。"
                               "括号内为尚未分配格的运费。",
            tables=[R.table("伏格尔法（数字=运量，括号=运费）", hdr, body, cells=cells)]))
    return x, basic, frames


def _complete_tree(basic, m, n, cost):
    """退化时补 0 运量基格，使基格恰好构成 m+n−1 条边的生成树（按运费从低到高尝试）。"""
    parent = list(range(m + n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for (i, j) in basic:
        parent[find(i)] = find(m + j)
    added = []
    for (c, i, j) in sorted((cost[i][j], i, j) for i in range(m) for j in range(n) if (i, j) not in basic):
        if len(basic) >= m + n - 1:
            break
        a, b = find(i), find(m + j)
        if a != b:
            parent[a] = b; basic.add((i, j)); added.append((i, j))
    return added


def _potentials(basic, m, n, cost):
    u, v = [None] * m, [None] * n
    u[0] = 0.0
    adj_r = {i: [] for i in range(m)}; adj_c = {j: [] for j in range(n)}
    for (i, j) in basic:
        adj_r[i].append(j); adj_c[j].append(i)
    q = deque([("r", 0)])
    while q:
        t, k = q.popleft()
        if t == "r":
            for j in adj_r[k]:
                if v[j] is None:
                    v[j] = cost[k][j] - u[k]; q.append(("c", j))
        else:
            for i in adj_c[k]:
                if u[i] is None:
                    u[i] = cost[i][k] - v[k]; q.append(("r", i))
    return u, v


def _cycle(basic, i0, j0, m, n):
    """在基格生成树中找 C_j0 → R_i0 的路径，与进基格 (i0,j0) 组成闭回路。返回有序格子列表。"""
    adj = {}
    for (i, j) in basic:
        adj.setdefault(("r", i), []).append(("c", j))
        adj.setdefault(("c", j), []).append(("r", i))
    start, goal = ("c", j0), ("r", i0)
    prev = {start: None}
    q = deque([start])
    while q:
        u = q.popleft()
        if u == goal:
            break
        for w in adj.get(u, []):
            if w not in prev:
                prev[w] = u; q.append(w)
    path = []
    u = goal
    while u is not None:
        path.append(u); u = prev[u]
    path.reverse()                    # C_j0, R_a, C_b, ..., R_i0
    cells = [(i0, j0)]
    for a, b in zip(path, path[1:]):
        (ta, ka), (tb, kb) = a, b
        cells.append((kb, ka) if ta == "c" else (ka, kb))
    return cells


def solve(p):
    supply = P.nums(p.get("supply"), "供应量")
    demand = P.nums(p.get("demand"), "需求量")
    cost = P.matrix(p.get("cost"), "运费矩阵")
    m0, n0 = len(supply), len(demand)
    if m0 == 0 or n0 == 0:
        raise R.InputError("供应量和需求量都至少要有一个。")
    if m0 > 12 or n0 > 12:
        raise R.InputError("教学版最多 12 个产地、12 个销地。")
    if len(cost) != m0 or any(len(r) != n0 for r in cost):
        raise R.InputError(f"运费矩阵应为 {m0} 行 × {n0} 列（行=产地，列=销地）。")
    if any(v < 0 for v in supply + demand):
        raise R.InputError("供应量与需求量不能为负。")
    S, D = sum(supply), sum(demand)
    sup, dem, C = supply[:], demand[:], [r[:] for r in cost]
    rl = [f"产地{i + 1}" for i in range(m0)]
    cl = [f"销地{j + 1}" for j in range(n0)]
    balance_note = "产销平衡。"
    if S < D - EPS:
        sup.append(D - S); C.append([0.0] * n0); rl.append("虚拟产地")
        balance_note = f"总供应 {R.fmt(S)} < 总需求 {R.fmt(D)}，补一个供应 {R.fmt(D - S)}、运费 0 的虚拟产地（表示缺货）。"
    elif S > D + EPS:
        dem.append(S - D); C = [r + [0.0] for r in C]; cl.append("虚拟销地")
        balance_note = f"总供应 {R.fmt(S)} > 总需求 {R.fmt(D)}，补一个需求 {R.fmt(S - D)}、运费 0 的虚拟销地（表示库存）。"
    m, n = len(sup), len(dem)

    x, basic, frames = _vogel(sup, dem, C, m, n, rl, cl)
    if not frames:
        raise R.InputError("供应量与需求量全为 0，没有可调运的货物。")
    frames.insert(0, R.frame("准备：检查产销平衡", balance_note,
                             tables=[R.table("运费矩阵", ["产地\\销地"] + cl + ["供应"],
                                             [[rl[i]] + [R.fmt(v) for v in C[i]] + [R.fmt(sup[i])] for i in range(m)]
                                             + [["需求"] + [R.fmt(v) for v in dem] + [""]])]))
    added = _complete_tree(basic, m, n, C)
    vogel_cost = sum(C[i][j] * x[i][j] for i in range(m) for j in range(n))

    def grid_table(title, cells_extra=None, show_sigma=None, u=None, v=None):
        hdr = ["产地\\销地"] + cl + (["uᵢ"] if u else [])
        body, cells = [], {}
        for i in range(m):
            row = [rl[i]]
            for j in range(n):
                if (i, j) in basic:
                    row.append(R.fmt(x[i][j])); cells[(i, j + 1)] = "c-basic"
                elif show_sigma is not None:
                    row.append(f"σ={R.fmt(show_sigma[i][j])}")
                    if show_sigma[i][j] < -EPS:
                        cells[(i, j + 1)] = "c-bad"
                else:
                    row.append("")
            if u:
                row.append(R.fmt(u[i]))
            body.append(row)
        if v:
            body.append(["vⱼ"] + [R.fmt(t) for t in v] + ([""] if u else []))
        for k, cls in (cells_extra or {}).items():
            cells[k] = cls
        return R.table(title, hdr, body, cells=cells)

    if added:
        frames.append(R.frame("退化处理", f"基格只有 {m + n - 1 - len(added)} 个，少于 m+n−1 = {m + n - 1}，位势无法全部求出。"
                              f"补 {', '.join(f'({rl[i]},{cl[j]})' for i, j in added)} 为运量 0 的基格（红框），"
                              "使基格连成一棵树。",
                              tables=[grid_table("补 0 后的基格", cells_extra={(i, j + 1): "c-enter" for i, j in added})]))
    frames.append(R.frame("伏格尔法完成：初始调运方案", f"初始方案总运费 = {R.fmt(vogel_cost)}。接下来用位势法检验它是否最优。",
                          tables=[grid_table("初始方案（绿色=基格运量）")]))

    it = 0
    while it < 100:
        it += 1
        u, v = _potentials(basic, m, n, C)
        sigma = [[C[i][j] - u[i] - v[j] for j in range(n)] for i in range(m)]
        cand = [(sigma[i][j], i, j) for i in range(m) for j in range(n) if (i, j) not in basic]
        neg = min(cand) if cand else (0, -1, -1)
        cur = sum(C[i][j] * x[i][j] for i in range(m) for j in range(n))
        if neg[0] >= -EPS:
            frames.append(R.frame(f"位势法第 {it} 轮：检验数全部 ≥ 0",
                                  f"由基格 uᵢ+vⱼ=cᵢⱼ 求出位势，所有非基格检验数 σ ≥ 0，当前方案最优，总运费 {R.fmt(cur)}。",
                                  tables=[grid_table("位势与检验数", show_sigma=sigma, u=u, v=v)]))
            break
        _, i0, j0 = neg
        loop = _cycle(basic, i0, j0, m, n)
        minus = loop[1::2]
        theta, leave = min((x[i][j], (i, j)) for (i, j) in minus)
        frames.append(R.frame(f"位势法第 {it} 轮：求检验数",
                              f"令 u₁=0，由基格 uᵢ+vⱼ=cᵢⱼ 求出全部位势；非基格 σᵢⱼ=cᵢⱼ−uᵢ−vⱼ。"
                              f"最负的是 ({rl[i0]},{cl[j0]})，σ = {R.fmt(neg[0])}，让它进基可降低运费。",
                              tables=[grid_table("位势与检验数（红=负检验数）", show_sigma=sigma, u=u, v=v,
                                                 cells_extra={(i0, j0 + 1): "c-enter"})]))
        marks = {}
        for k, (i, j) in enumerate(loop):
            marks[(i, j + 1)] = "c-plus" if k % 2 == 0 else "c-minus"
        loop_txt = " → ".join(f"({rl[i]},{cl[j]}){'+' if k % 2 == 0 else '−'}" for k, (i, j) in enumerate(loop))
        frames.append(R.frame(f"位势法第 {it} 轮：闭回路调整",
                              f"闭回路：{loop_txt}。θ = 「−」格中最小运量 = {R.fmt(theta)}，"
                              f"+格加 θ、−格减 θ，({rl[leave[0]]},{cl[leave[1]]}) 出基。"
                              + (f"运费下降 σ×θ = {R.fmt(-neg[0] * theta)}。" if theta > EPS else
                                 "这是退化调整：θ = 0，运费暂时不变，但基格换了，下一轮就能继续改进。"),
                              tables=[grid_table("闭回路（蓝=+θ，橙=−θ）", cells_extra=marks)]))
        for k, (i, j) in enumerate(loop):
            x[i][j] += theta if k % 2 == 0 else -theta
        basic.discard(leave); basic.add((i0, j0))
        x[leave[0]][leave[1]] = 0.0

    opt_cost = sum(C[i][j] * x[i][j] for i in range(m) for j in range(n))
    hdr = ["产地\\销地"] + cl + ["供应量"]
    body = [[rl[i]] + [R.fmt(x[i][j]) if x[i][j] > EPS else "" for j in range(n)] + [R.fmt(sup[i])] for i in range(m)]
    body.append(["需求量"] + [R.fmt(d) for d in dem] + [""])
    cells = {(i, j + 1): "c-basic" for i in range(m) for j in range(n) if x[i][j] > EPS}
    u, v = _potentials(basic, m, n, C)
    edesc = [(f"L{i}", f"R{j}", R.fmt(x[i][j]), "ship", x[i][j])
             for i in range(m) for j in range(n) if x[i][j] > EPS]
    g = GV.bipartite_graph([f"L{i}" for i in range(m)], rl, [f"R{j}" for j in range(n)], cl, edesc)
    frames.append(R.frame("最优调运方案", f"最小总运费 = {R.fmt(opt_cost)}（伏格尔初始方案 {R.fmt(vogel_cost)}）。"
                          "线越粗表示运量越大。", graph=g))
    return R.report(
        "optimal", headline=f"最小运输总费用 = {R.fmt(opt_cost)}",
        tables=[R.table("最优调运方案", hdr, body, cells=cells),
                R.table("位势（对偶变量）", ["", "值"], [[f"u{i + 1}（{rl[i]}）", R.fmt(u[i])] for i in range(m)]
                        + [[f"v{j + 1}（{cl[j]}）", R.fmt(v[j])] for j in range(n)])],
        notes=[balance_note,
               f"伏格尔法初始成本 {R.fmt(vogel_cost)}，位势法迭代 {it - 1} 次后最优成本 {R.fmt(opt_cost)}。",
               "位势 uᵢ、vⱼ 就是对偶变量：检验数 σᵢⱼ = cᵢⱼ − uᵢ − vⱼ ≥ 0 即对偶可行，当前方案最优。"],
        graph=g, steps=frames)


if __name__ == "__main__":
    r = solve({k: f["value"] for k, f in ((f["id"], f) for f in SPEC["form"])})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"][:120])
