"""最大流：Edmonds-Karp（BFS 找最短增广路，O(VE²)）+ 最小割。

演示帧：每轮在剩余网络中用 BFS 找一条 s→t 增广路（高亮），按瓶颈容量增广，
边标签显示「流量/容量」；最后标出最小割，验证「最大流 = 最小割」。
"""
from collections import deque

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "Edmonds-Karp 最大流：每轮用 BFS 在剩余网络中找边数最少的增广路，按路上最小剩余容量增广，"
            "直到找不到增广路。最后给出最小割（最大流 = 最小割容量）。输入每行 u v 容量。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "有向边 (每行: u v 容量)", "rows": 8,
         "value": "0 1 16\n0 2 13\n1 2 10\n2 1 4\n1 3 12\n3 2 9\n3 5 20\n2 4 14\n4 3 7\n4 5 4"},
        {"id": "source", "type": "int", "label": "源点", "value": "0"},
        {"id": "sink", "type": "int", "label": "汇点", "value": "5"},
    ],
}


def solve(p):
    raw = P.edges(p.get("edges"), what="有向边")
    if not raw:
        raise R.InputError("没有可解析的边，每行写 u v 容量。")
    if any(w < 0 for _, _, w in raw):
        raise R.InputError("容量不能为负。")
    s = P.integer(p, "source", 0, "源点", 0)
    t = P.integer(p, "sink", None, "汇点", 0)
    if s == t:
        raise R.InputError("源点和汇点不能相同。")
    n = max([s, t] + [max(u, v) for u, v, _ in raw]) + 1
    if n > 40:
        raise R.InputError("教学版最多 40 个节点。")
    cap = [[0.0] * n for _ in range(n)]
    for u, v, w in raw:
        cap[u][v] += w
    flow = [[0.0] * n for _ in range(n)]
    ids = list(range(n))
    frames = []

    def edge_flow(u, v):
        return max(0.0, flow[u][v])

    def snap(title, text, path_edges=(), cut=None):
        pe = set(path_edges)
        groups = []
        for i in ids:
            g = "src" if i == s else ("sink" if i == t else "default")
            if cut is not None and i in cut and i not in (s,):
                g = "done"
            groups.append(g)
        ed = []
        for u, v, w in raw:
            f = edge_flow(u, v)
            if (u, v) in pe:
                cls = "active"
            elif cut is not None and u in cut and v not in cut:
                cls = "reject"
            else:
                cls = "flow" if f > 1e-9 else "default"
            ed.append((u, v, f"{R.fmt(f)}/{R.fmt(w)}", cls, f))
        g = GV.circular_graph(ids, [str(i) for i in ids], groups, ed, directed=True)
        frames.append(R.frame(title, text, graph=g))

    snap("初始化", "所有边流量为 0。边上标签为「流量/容量」。")
    total = 0.0
    log = []
    while True:
        prev = [-1] * n
        prev[s] = s
        q = deque([s])
        while q and prev[t] < 0:
            u = q.popleft()
            for v in range(n):
                if prev[v] < 0 and cap[u][v] - flow[u][v] > 1e-12:
                    prev[v] = u; q.append(v)
        if prev[t] < 0:
            break
        path = [t]
        while path[-1] != s:
            path.append(prev[path[-1]])
        path.reverse()
        bott = min(cap[a][b] - flow[a][b] for a, b in zip(path, path[1:]))
        for a, b in zip(path, path[1:]):
            flow[a][b] += bott; flow[b][a] -= bott
        total += bott
        log.append(("→".join(map(str, path)), bott, total))
        shown = [(a, b) if cap[a][b] > 0 else (b, a) for a, b in zip(path, path[1:])]
        extra = "（含反向边：撤回部分已有流量）" if any(cap[a][b] <= 0 for a, b in zip(path, path[1:])) else ""
        snap(f"第 {len(log)} 次增广", f"BFS 找到增广路 {'→'.join(map(str, path))}{extra}，路上最小剩余容量 = {R.fmt(bott)}，"
             f"沿路推送 {R.fmt(bott)} 单位，当前总流量 {R.fmt(total)}。", path_edges=shown)
        if len(log) > 500:
            break
    # 最小割：残量网络中从 s 可达的点集 S
    S = {s}
    q = deque([s])
    while q:
        u = q.popleft()
        for v in range(n):
            if v not in S and cap[u][v] - flow[u][v] > 1e-12:
                S.add(v); q.append(v)
    cut_edges = [(u, v, w) for u, v, w in raw if u in S and v not in S]
    cut_val = sum(w for _, _, w in cut_edges)
    snap("没有增广路了：最大流与最小割",
         f"剩余网络中从源点出发只能到达 {{{', '.join(map(str, sorted(S)))}}}（绿色）。从这些点指向其余点的边（红色）"
         f"构成最小割，容量 {R.fmt(cut_val)} = 最大流 {R.fmt(total)}。", cut=S)
    rows = [[u, v, R.fmt(w), R.fmt(edge_flow(u, v))] for u, v, w in raw]
    return R.report("optimal", headline=f"最大流 = {R.fmt(total)}",
                    tables=[R.table("增广记录", ["次", "增广路", "增广量", "累计流量"],
                                    [[i + 1, a, R.fmt(b), R.fmt(c)] for i, (a, b, c) in enumerate(log)]),
                            R.table("边流量", ["u", "v", "容量", "流量"], rows),
                            R.table("最小割", ["u", "v", "容量"], [[u, v, R.fmt(w)] for u, v, w in cut_edges]
                                    + [["", "合计", R.fmt(cut_val)]])],
                    notes=["Edmonds-Karp：每次用 BFS 找边数最少的增广路，保证多项式时间。",
                           "最大流最小割定理：最大流量 = 最小割容量。"],
                    graph=frames[-1]["graph"], steps=frames)


if __name__ == "__main__":
    r = solve({f["id"]: f["value"] for f in SPEC["form"]})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"][:120])
