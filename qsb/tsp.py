"""旅行商 TSP：n ≤ 9 用动态规划（Held-Karp）精确求解；n > 9 用最近邻 + 2-opt 启发式。

演示帧：
  精确：先用最近邻得到初始上界，再展示 Held-Karp 求出的最优回路；
  启发式：最近邻逐城市构造路线，然后 2-opt 每次替换两条边、路线变短一次就是一帧。
"""
import math

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "旅行商问题：n≤9 用 Held-Karp 动态规划精确求最短回路；n>9 用最近邻法构造初始路线，"
            "再用 2-opt 反复交换两条边，直到不能再缩短。输入距离矩阵（可不对称）。",
    "form": [
        {"id": "dist", "type": "matrix", "label": "距离矩阵 (行=起点, 列=终点)", "rows": 6,
         "value": "0, 12, 10, 19, 8, 14\n12, 0, 3, 7, 2, 11\n10, 3, 0, 6, 20, 4\n19, 7, 6, 0, 4, 9\n"
                  "8, 2, 20, 4, 0, 13\n14, 11, 4, 9, 13, 0"},
        {"id": "method", "type": "select", "label": "算法", "value": "auto",
         "options": [{"v": "auto", "t": "自动（n≤9 精确，否则启发式）"}, {"v": "heuristic", "t": "最近邻 + 2-opt"},
                     {"v": "exact", "t": "精确（Held-Karp，n≤12）"}]},
    ],
}


def _len(t, d):
    return sum(d[t[i]][t[(i + 1) % len(t)]] for i in range(len(t)))


def _held_karp(d):
    n = len(d)
    INF = math.inf
    full = 1 << (n - 1)
    dp = [[INF] * n for _ in range(full)]
    par = [[-1] * n for _ in range(full)]
    for k in range(1, n):
        dp[1 << (k - 1)][k] = d[0][k]
    for mask in range(1, full):
        for k in range(1, n):
            if not mask & (1 << (k - 1)) or dp[mask][k] == INF:
                continue
            for j in range(1, n):
                bit = 1 << (j - 1)
                if mask & bit:
                    continue
                v = dp[mask][k] + d[k][j]
                if v < dp[mask | bit][j]:
                    dp[mask | bit][j] = v; par[mask | bit][j] = k
    best, last = INF, -1
    for k in range(1, n):
        v = dp[full - 1][k] + d[k][0]
        if v < best:
            best, last = v, k
    tour, mask, k = [], full - 1, last
    while k > 0:
        tour.append(k)
        pk = par[mask][k]
        mask ^= 1 << (k - 1)
        k = pk
    return [0] + tour[::-1], best


def solve(p):
    d = P.square(p.get("dist"), "距离矩阵", 2, 40)
    n = len(d)
    if any(v < 0 for r in d for v in r):
        raise R.InputError("距离不能为负。")
    method = p.get("method", "auto")
    exact = (method == "exact") or (method == "auto" and n <= 9)
    if exact and n > 12:
        raise R.InputError("精确算法最多支持 12 个城市（状态数 2ⁿ·n 增长太快），请改用启发式。")
    ids = list(range(n))
    sym = all(abs(d[i][j] - d[j][i]) < 1e-12 for i in range(n) for j in range(n))
    frames = []

    def snap(title, text, tour, closed=True, changed=()):
        tp = set()
        ed = []
        k_range = len(tour) if closed else len(tour) - 1
        for k in range(k_range):
            a, b = tour[k], tour[(k + 1) % len(tour)]
            tp.add((a, b))
            ed.append((a, b, R.fmt(d[a][b]), "active" if (a, b) in changed or (b, a) in changed else "path"))
        if n <= 10:
            for i in range(n):
                for j in range(i + 1, n):
                    if (i, j) not in tp and (j, i) not in tp:
                        ed.insert(0, (i, j, "", "default"))
        groups = ["src" if i == tour[0] else ("done" if i in tour else "default") for i in ids]
        if not closed:
            groups[tour[-1]] = "current"
        g = GV.circular_graph(ids, [str(i) for i in ids], groups, ed, directed=True)
        frames.append(R.frame(title, text, graph=g))

    # 最近邻构造
    t = [0]
    unvis = set(range(1, n))
    snap("最近邻：从城市 0 出发", "从 0 出发，每次走向最近的未访问城市。", t, closed=False)
    while unvis:
        cur = t[-1]
        nx = min(unvis, key=lambda v: (d[cur][v], v))
        t.append(nx); unvis.remove(nx)
        snap(f"最近邻：{cur} → {nx}", f"离 {cur} 最近的未访问城市是 {nx}（距离 {R.fmt(d[cur][nx])}）。", t,
             closed=(not unvis), changed={(cur, nx)})
    nn_len = _len(t, d)
    frames[-1]["text"] += f" 回到起点，最近邻路线总长 {R.fmt(nn_len)}。"

    if exact:
        tour, L = _held_karp(d)
        snap("Held-Karp 动态规划：最优回路",
             f"状态 dp[S][k] = 从 0 出发、恰好访问集合 S、停在 k 的最短路长；逐步扩大 S 求得全局最优 {R.fmt(L)}"
             f"（最近邻 {R.fmt(nn_len)}，差 {R.fmt(nn_len - L)}）。", tour)
        mname = "精确（Held-Karp 动态规划）"
    else:
        improved, rounds = True, 0
        while improved and rounds < 500:
            improved = False
            for i in range(1, n - 1):
                for j in range(i + 1, n):
                    a, b, c, e = t[i - 1], t[i], t[j], t[(j + 1) % n]
                    if a == e:
                        continue
                    new = t[:i] + t[i:j + 1][::-1] + t[j + 1:]
                    delta = _len(new, d) - _len(t, d)
                    if delta < -1e-12:
                        rounds += 1
                        t = new
                        snap(f"2-opt 第 {rounds} 次改进",
                             f"去掉边 ({a},{b}) 和 ({c},{e})，改接 ({a},{c}) 与 ({b},{e})（中间一段反向），"
                             f"路线缩短 {R.fmt(-delta)}，现长 {R.fmt(_len(t, d))}。", t, changed={(a, c), (b, e)})
                        improved = True
                        break
                if improved:
                    break
        tour, L = t, _len(t, d)
        frames.append(R.frame("2-opt 结束", f"任意交换两条边都不能再缩短，得到局部最优路线，长 {R.fmt(L)}"
                              f"（最近邻 {R.fmt(nn_len)}）。", graph=frames[-1]["graph"]))
        mname = "启发式（最近邻 + 2-opt）"
    route = "→".join(map(str, tour)) + f"→{tour[0]}"
    return R.report("optimal" if exact else "ok",
                    headline=f"TSP 回路长度 = {R.fmt(L)}  [{mname}]",
                    tables=[R.table("访问顺序", ["步", "城市", "到下一城市距离"],
                                    [[i + 1, tour[i], R.fmt(d[tour[i]][tour[(i + 1) % n]])] for i in range(n)])],
                    notes=[f"路线：{route}", f"n = {n}，{'对称' if sym else '非对称'}距离矩阵。",
                           "精确解保证全局最优；启发式结果只保证 2-opt 局部最优。"],
                    graph=frames[-1]["graph"], steps=R.thin(frames, 70))


if __name__ == "__main__":
    r = solve({f["id"]: f["value"] for f in SPEC["form"]})
    print(r["headline"], len(r["steps"]))
    r = solve({"dist": SPEC["form"][0]["value"], "method": "heuristic"})
    print(r["headline"], len(r["steps"]))
