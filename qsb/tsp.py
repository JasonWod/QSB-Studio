"""旅行商 TSP：n<=8 用全排列精确；否则 最近邻 + 2-opt 启发式。输入：距离矩阵。"""
import itertools
from . import report as R
from . import graphviz as GV

SPEC = {
    "desc": "TSP：n≤8 精确搜索（全排列）；n>8 用最近邻+2-opt 启发式。输入方距离矩阵。",
    "form": [
        {"id": "dist", "type": "matrix", "label": "距离矩阵 (行=起点, 列=终点)", "rows": 4, "cols": 4,
         "value": "0,10,15,20\n10,0,35,25\n15,35,0,30\n20,25,30,0"},
    ],
}


def _as_matrix(v):
    if isinstance(v, str):
        return [[float(x) for x in ln.replace(",", " ").split()]
                for ln in v.splitlines() if ln.strip()]
    return v


def _len(t, dist):
    return sum(dist[t[i]][t[(i + 1) % len(t)]] for i in range(len(t)))


def _two_opt(t, dist):
    n = len(t); improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                if j == i + 1:
                    continue
                a, b, c, d = t[i - 1], t[i], t[j], t[(j + 1) % n]
                if dist[a][c] + dist[b][d] < dist[a][b] + dist[c][d] - 1e-12:
                    t[i:j + 1] = reversed(t[i:j + 1]); improved = True
    return t


def solve(p):
    dist = _as_matrix(p["dist"]); n = len(dist)
    if n < 2:
        return R.report("error", headline="距离矩阵至少 2×2")
    if n <= 8:
        best = None
        for perm in itertools.permutations(range(1, n)):
            t = [0] + list(perm)
            L = _len(t, dist)
            if best is None or L < best[0]:
                best = (L, t)
        method = "精确 (全排列)"
    else:
        t = [0]; unvis = list(range(1, n))
        while unvis:
            cur = t[-1]
            nx = min(unvis, key=lambda v: dist[cur][v])
            t.append(nx); unvis.remove(nx)
        t = _two_opt(t, dist)
        best = (_len(t, dist), t); method = "启发式 (最近邻 + 2-opt)"
    L, t = best
    tour = "→".join(str(x) for x in t) + f"→{t[0]}"

    # ---- 网络图：城市圆布局，tour 闭合环高亮，n<=8 时底层画淡全连接 ----
    tpairs = set()
    tour_edges = []
    for k in range(len(t)):
        a, b = t[k], t[(k + 1) % len(t)]
        tpairs.add(frozenset((a, b)))
        tour_edges.append((a, b, R.fmt(dist[a][b]), "path"))
    full_edges = []
    if n <= 8:
        for i in range(n):
            for j in range(i + 1, n):
                if frozenset((i, j)) not in tpairs:
                    full_edges.append((i, j, "", "default"))
    g = GV.circular_graph(list(range(n)), [str(i) for i in range(n)], None,
                          full_edges + tour_edges, directed=True)
    return R.report("optimal", headline=f"TSP 最短 tour 长度 = {R.fmt(L)}  [{method}]",
                    tables=[R.table("访问顺序", ["步", "城市"], [[i + 1, t[i]] for i in range(n)])],
                    notes=[f"n={n}，采用{method}。路线：{tour}"], graph=g)


if __name__ == "__main__":
    r = solve({"dist": [[0, 10, 15, 20], [10, 0, 35, 25], [15, 35, 0, 30], [20, 25, 30, 0]]})
    print(r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
