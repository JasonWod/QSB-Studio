"""指派问题（匈牙利算法，O(n³)）。输入方成本矩阵，求最小总成本的最优一一指派。"""
from . import report as R
from . import graphviz as GV

SPEC = {
    "desc": "n 人 n 任务的最小成本指派（匈牙利算法：行列归约 + 增广路匹配，O(n³)）。",
    "form": [
        {"id": "cost", "type": "matrix", "label": "成本矩阵 (行=人, 列=任务)", "rows": 4,
         "value": "5, 1, 7, 4\n8, 3, 2, 9\n2, 6, 7, 5\n6, 9, 3, 4"},
    ],
}


def _as_matrix(v):
    if isinstance(v, str):
        return [[float(x) for x in ln.replace(",", " ").split()]
                for ln in v.splitlines() if ln.strip()]
    return v


def solve(p):
    C = [[float(x) for x in r] for r in _as_matrix(p["cost"])]
    n = len(C)
    if n < 1 or any(len(r) != n for r in C):
        return R.report("error", headline="需要方阵成本矩阵")
    # 匈牙利 (最小化)：1-indexed
    u = [0] * (n + 1); v = [0] * (n + 1); way = [0] * (n + 1); p = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0
        minv = [float("inf")] * (n + 1); used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]; delta = float("inf"); j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = C[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur; way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]; j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0:
                break
    assign = [-1] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assign[p[j] - 1] = j - 1
    total = sum(C[i][assign[i]] for i in range(n))

    # ---- 网络图：人(左) → 任务(右) 的匹配 ----
    left_ids = [f"P{i}" for i in range(n)]
    left_labels = [f"人{i + 1}" for i in range(n)]
    right_ids = [f"T{j}" for j in range(n)]
    right_labels = [f"任务{j + 1}" for j in range(n)]
    edesc = []
    for i in range(n):
        j = assign[i]
        edesc.append((f"P{i}", f"T{j}", R.fmt(C[i][j]), "assign"))
    g = GV.bipartite_graph(left_ids, left_labels, right_ids, right_labels, edesc)
    return R.report("optimal", headline=f"最小总成本 = {R.fmt(total)}",
                    tables=[R.table("最优指派 (人 → 任务)", ["人", "任务", "成本"],
                                    [[i + 1, assign[i] + 1, R.fmt(C[i][assign[i]])] for i in range(n)])],
                    notes=["匈牙利算法：先行/列归约得到候选零，再用增广路找完美匹配。"], graph=g)


if __name__ == "__main__":
    r = solve({"cost": [[5, 1, 7, 4], [8, 3, 2, 9], [2, 6, 7, 5], [6, 9, 3, 4]]})
    print(r["status"], r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
