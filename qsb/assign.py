"""指派问题：匈牙利算法（教科书「划线法」）。

1. 行归约、列归约：每行、每列减去该行列的最小值（不改变最优指派）
2. 用最少的直线覆盖全部 0（König 定理：最少直线数 = 0 元素上的最大匹配数）
3. 线数 = n → 找到 n 个独立 0，即最优指派；否则取未被覆盖元素的最小值 θ，
   未覆盖元素减 θ、交叉点加 θ，回到第 2 步
支持最大化（转为「最大值 − 收益」再求最小）与非方阵（补 0 成本的虚拟人/任务）。
"""
from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "指派问题（匈牙利算法 · 划线法）：行列归约造出 0，用最少直线覆盖所有 0；线数不足 n 就调整矩阵，"
            "直到找到 n 个位于不同行不同列的独立 0。支持最大化与人数≠任务数（自动补虚拟行/列）。",
    "form": [
        {"id": "obj", "type": "select", "label": "目标", "value": "min",
         "options": [{"v": "min", "t": "最小化成本"}, {"v": "max", "t": "最大化收益"}]},
        {"id": "cost", "type": "matrix", "label": "成本矩阵 (行=人, 列=任务)", "rows": 4,
         "value": "9, 11, 3, 6, 6\n10, 12, 6, 8, 9\n8, 11, 4, 7, 7\n5, 8, 6, 9, 10\n11, 9, 4, 6, 7"},
    ],
}


def _max_matching(Z, n):
    """Z[i][j] 为 True 的格子上做二分图最大匹配。返回 match_col[j] = i 或 -1。"""
    match_col = [-1] * n

    def try_row(i, seen):
        for j in range(n):
            if Z[i][j] and not seen[j]:
                seen[j] = True
                if match_col[j] < 0 or try_row(match_col[j], seen):
                    match_col[j] = i
                    return True
        return False

    for i in range(n):
        try_row(i, [False] * n)
    return match_col


def _cover(Z, n, match_col):
    """由最大匹配构造最小覆盖（König）：从未匹配行出发沿「0 → 匹配」交替走，
    覆盖 = 未到达的行 ∪ 到达的列。"""
    match_row = [-1] * n
    for j, i in enumerate(match_col):
        if i >= 0:
            match_row[i] = j
    vis_r, vis_c = set(), set()
    stack = [i for i in range(n) if match_row[i] < 0]
    vis_r.update(stack)
    while stack:
        i = stack.pop()
        for j in range(n):
            if Z[i][j] and j not in vis_c:
                vis_c.add(j)
                k = match_col[j]
                if k >= 0 and k not in vis_r:
                    vis_r.add(k); stack.append(k)
    rows = {i for i in range(n) if i not in vis_r}
    return rows, vis_c


def solve(p):
    obj = p.get("obj", "min")
    C0 = P.matrix(p.get("cost"), "成本矩阵")
    if not C0:
        raise R.InputError("请输入成本矩阵（每行一个人，逗号分隔各任务成本）。")
    nr, nc = len(C0), len(C0[0])
    if any(len(r) != nc for r in C0):
        raise R.InputError("成本矩阵每行的元素个数必须相同。")
    if max(nr, nc) > 12:
        raise R.InputError("教学版最多 12 人 × 12 任务。")
    n = max(nr, nc)
    rl = [f"人{i + 1}" for i in range(nr)] + [f"虚拟人{i + 1}" for i in range(n - nr)]
    cl = [f"任务{j + 1}" for j in range(nc)] + [f"虚拟任务{j + 1}" for j in range(n - nc)]
    notes = []
    if obj == "max":
        big = max(max(r) for r in C0)
        C = [[big - v for v in r] for r in C0]
        notes.append(f"最大化：用最大值 {R.fmt(big)} 减去每个收益，转成等价的最小化问题。")
    else:
        C = [r[:] for r in C0]
    C = [r + [0.0] * (n - nc) for r in C] + [[0.0] * n for _ in range(n - nr)]
    if n != nr or n != nc:
        notes.append(f"人数 {nr} ≠ 任务数 {nc}，补 0 成本的虚拟行/列成为 {n}×{n} 方阵；分给虚拟方的表示空缺。")

    frames = []
    hdr = ["人\\任务"] + cl

    def mat_table(title, M, cells=None, rowcls=None, colcls=None):
        body = [[rl[i]] + [R.fmt(M[i][j]) for j in range(n)] for i in range(n)]
        return R.table(title, hdr, body, cells=cells, rowcls=rowcls, colcls=colcls)

    def zero_cells(M, star=None):
        cells = {}
        for i in range(n):
            for j in range(n):
                if abs(M[i][j]) < 1e-9:
                    cells[(i, j + 1)] = "c-zero"
        for (i, j) in (star or []):
            cells[(i, j + 1)] = "c-star"
        return cells

    frames.append(R.frame("准备：成本矩阵", " ".join(notes) or "原始成本矩阵，目标是每人一项任务、总成本最小。",
                          tables=[mat_table("成本矩阵", C)]))
    M = [r[:] for r in C]
    rmin = [min(r) for r in M]
    M = [[M[i][j] - rmin[i] for j in range(n)] for i in range(n)]
    frames.append(R.frame("第 1 步：行归约", "每行减去本行最小值（" + "、".join(R.fmt(v) for v in rmin) + "），每行至少出现一个 0。",
                          tables=[mat_table("行归约后（黄色=0）", M, cells=zero_cells(M))]))
    cmin = [min(M[i][j] for i in range(n)) for j in range(n)]
    M = [[M[i][j] - cmin[j] for j in range(n)] for i in range(n)]
    frames.append(R.frame("第 2 步：列归约", "每列再减去本列最小值（" + "、".join(R.fmt(v) for v in cmin) + "），每列也至少有一个 0。",
                          tables=[mat_table("列归约后", M, cells=zero_cells(M))]))

    it = 0
    while True:
        it += 1
        Z = [[abs(M[i][j]) < 1e-9 for j in range(n)] for i in range(n)]
        mc = _max_matching(Z, n)
        stars = [(i, j) for j, i in enumerate(mc) if i >= 0]
        rows, cols = _cover(Z, n, mc)
        lines = len(rows) + len(cols)
        rowcls = {i: "c-cover" for i in rows}
        colcls = {j + 1: "c-cover" for j in cols}
        if lines >= n:
            frames.append(R.frame(f"第 {it + 2} 步：划线检验 → 最优",
                                  f"覆盖全部 0 至少需要 {lines} 条线 = n，能找到 {n} 个不同行不同列的独立 0（深色格），"
                                  "它们的位置就是最优指派。",
                                  tables=[mat_table("独立 0 = 最优指派", M, cells=zero_cells(M, stars))]))
            break
        theta = min(M[i][j] for i in range(n) for j in range(n) if i not in rows and j not in cols)
        unc = {(i, j + 1): "c-enter" for i in range(n) for j in range(n)
               if i not in rows and j not in cols and abs(M[i][j] - theta) < 1e-9}
        cells = zero_cells(M); cells.update(unc)
        frames.append(R.frame(f"第 {it + 2} 步：划线检验",
                              f"最少用 {lines} 条线（灰色行/列）就能盖住所有 0，少于 n = {n}，还找不到完整指派。"
                              f"未被覆盖的元素中最小值 θ = {R.fmt(theta)}（红框）。",
                              tables=[mat_table("最少直线覆盖", M, cells=cells, rowcls=rowcls, colcls=colcls)]))
        for i in range(n):
            for j in range(n):
                if i not in rows and j not in cols:
                    M[i][j] -= theta
                elif i in rows and j in cols:
                    M[i][j] += theta
        frames.append(R.frame(f"第 {it + 2} 步：调整矩阵",
                              f"未覆盖元素减 θ = {R.fmt(theta)}，被两条线交叉覆盖的元素加 θ，其余不变——造出新的 0。",
                              tables=[mat_table("调整后", M, cells=zero_cells(M))]))
        if it > 50:
            break

    assign = [-1] * n
    for (i, j) in stars:
        assign[i] = j
    total = sum(C0[i][assign[i]] for i in range(nr) if assign[i] < nc)
    rows_out = []
    for i in range(nr):
        j = assign[i]
        rows_out.append([rl[i], cl[j], R.fmt(C0[i][j]) if j < nc else "（空缺）"])
    edesc = [(f"P{i}", f"T{assign[i]}", R.fmt(C0[i][assign[i]]) if i < nr and assign[i] < nc else "0", "assign")
             for i in range(n)]
    g = GV.bipartite_graph([f"P{i}" for i in range(n)], rl, [f"T{j}" for j in range(n)], cl, edesc)
    frames.append(R.frame("最优指派", f"总{'收益' if obj == 'max' else '成本'} = {R.fmt(total)}。", graph=g))
    word = "最大总收益" if obj == "max" else "最小总成本"
    return R.report("optimal", headline=f"{word} = {R.fmt(total)}",
                    tables=[R.table("最优指派 (人 → 任务)", ["人", "任务", "收益" if obj == "max" else "成本"], rows_out)],
                    notes=notes + ["匈牙利算法：归约不改变最优解；最少覆盖线数 = 最多独立 0 个数（König 定理）。"],
                    graph=g, steps=frames)


if __name__ == "__main__":
    r = solve({f["id"]: f["value"] for f in SPEC["form"]})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"][:100])
