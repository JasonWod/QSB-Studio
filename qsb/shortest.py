"""最短路径：Dijkstra 算法（堆优化 O((V+E) log V)），支持有向 / 无向图。

演示帧：每次从「未确定」节点中取出距离最小者标为确定（橙色），用它松弛相邻边（高亮），
节点下方实时显示当前最短距离标号。
"""
import heapq

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "Dijkstra 单源最短路径：每次选出距离标号最小的未确定节点，把它「永久标号」，再用它松弛相邻边。"
            "输入每行 u v w，可选有向/无向。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "边 (每行: u v w，节点编号从 0 起)", "rows": 8,
         "value": "0 1 4\n0 2 2\n1 2 5\n1 3 10\n2 4 3\n4 3 4\n3 5 11\n4 5 9"},
        {"id": "source", "type": "int", "label": "源点", "value": "0"},
        {"id": "target", "type": "int", "label": "目标点 (留空求全部)", "value": "5"},
        {"id": "directed", "type": "select", "label": "图类型", "value": "no",
         "options": [{"v": "no", "t": "无向图"}, {"v": "yes", "t": "有向图"}]},
    ],
}

INF = float("inf")


def solve(p):
    edges = P.edges(p.get("edges"))
    if not edges:
        raise R.InputError("没有可解析的边，每行写 u v w。")
    if any(w < 0 for _, _, w in edges):
        raise R.InputError("Dijkstra 要求边权非负；含负权边请改用 Bellman-Ford。")
    src = P.integer(p, "source", 0, "源点", 0)
    tgt = P.optional_int(p, "target")
    directed = p.get("directed", "no") in ("yes", True)
    n = max([src] + [max(u, v) for u, v, _ in edges] + ([tgt] if tgt is not None else [])) + 1
    if n > 40:
        raise R.InputError("教学版最多 40 个节点。")
    adj = {i: [] for i in range(n)}
    for k, (u, v, w) in enumerate(edges):
        adj[u].append((v, w, k))
        if not directed:
            adj[v].append((u, w, k))

    dist = [INF] * n
    prev = [None] * n
    prev_e = [None] * n
    done = [False] * n
    dist[src] = 0.0
    pq = [(0.0, src)]
    frames = []
    ids = list(range(n))

    def snap(title, text, cur=None, active=(), relaxed=()):
        groups, subs = [], []
        for i in range(n):
            g = "done" if done[i] else "default"
            if i == src:
                g = "src"
            if i == cur:
                g = "current"
            groups.append(g)
            subs.append("d=" + (R.fmt(dist[i]) if dist[i] < INF else "∞"))
        tree = {prev_e[i] for i in range(n) if prev_e[i] is not None}
        ed = []
        for k, (u, v, w) in enumerate(edges):
            cls = "active" if k in relaxed else ("candidate" if k in active else ("path" if k in tree else "default"))
            ed.append((u, v, R.fmt(w), cls))
        g = GV.circular_graph(ids, [str(i) for i in ids], groups, ed, directed=directed, subs=subs)
        tb = R.table("距离标号", ["节点"] + [str(i) for i in ids],
                     [["d(v)"] + [R.fmt(d) if d < INF else "∞" for d in dist],
                      ["前驱"] + ["—" if prev[i] is None else str(prev[i]) for i in ids],
                      ["状态"] + ["已确定" if done[i] else "未确定" for i in ids]],
                     cells={(r, cur + 1): "c-cur" for r in range(3)} if cur is not None else None)
        frames.append(R.frame(title, text, tables=[tb], graph=g))

    snap("初始化", f"源点 {src} 的距离标号设为 0，其余节点为 ∞。紫色边表示当前最短路树。")
    order = []
    while pq:
        d, u = heapq.heappop(pq)
        if done[u] or d > dist[u]:
            continue
        done[u] = True
        order.append(u)
        relaxed, looked, msgs = [], [], []
        for v, w, k in adj[u]:
            if done[v]:
                continue
            looked.append(k)
            nd = d + w
            if nd < dist[v] - 1e-12:
                old = dist[v]
                dist[v] = nd; prev[v] = u; prev_e[v] = k
                heapq.heappush(pq, (nd, v))
                relaxed.append(k)
                msgs.append(f"d({v}) 由 {R.fmt(old) if old < INF else '∞'} 更新为 {R.fmt(d)}+{R.fmt(w)}={R.fmt(nd)}")
            else:
                msgs.append(f"d({v}) = {R.fmt(dist[v])} ≤ {R.fmt(d)}+{R.fmt(w)}，不更新")
        text = (f"未确定节点中 {u} 的距离标号 {R.fmt(d)} 最小，把它永久标号。"
                + (f"用它松弛相邻边：{'；'.join(msgs)}。" if msgs else "它没有未确定的邻居。"))
        snap(f"第 {len(order)} 步：确定节点 {u}", text, cur=u, active=looked, relaxed=relaxed)

    def path(v):
        out = []
        while v is not None:
            out.append(v); v = prev[v]
        return out[::-1]

    rows = [[i, R.fmt(dist[i]) if dist[i] < INF else "∞", "→".join(map(str, path(i))) if dist[i] < INF else "不可达"]
            for i in range(n) if i != src]
    if tgt is not None:
        reach = dist[tgt] < INF
        headline = f"{src} → {tgt} 最短距离 = {R.fmt(dist[tgt])}" if reach else f"{src} 无法到达 {tgt}"
        sp = path(tgt) if reach else []
    else:
        headline = f"源点 {src} 到各点的最短距离"
        sp = []
    pe = set()
    for a, b in zip(sp, sp[1:]):
        pe.add(prev_e[b])
    groups = ["default"] * n
    groups[src] = "src"
    if tgt is not None:
        groups[tgt] = "sink"
    ed = [(u, v, R.fmt(w), "path" if k in pe or (tgt is None and k in set(prev_e)) else "default")
          for k, (u, v, w) in enumerate(edges)]
    subs = ["d=" + (R.fmt(d) if d < INF else "∞") for d in dist]
    g = GV.circular_graph(ids, [str(i) for i in ids], groups, ed, directed=directed, subs=subs)
    if sp:
        frames.append(R.frame("结果：回溯最短路", f"从目标 {tgt} 沿前驱回溯得到最短路 {'→'.join(map(str, sp))}，"
                              f"长度 {R.fmt(dist[tgt])}。", graph=g))
    return R.report("optimal", headline=headline,
                    tables=[R.table("最短距离表", ["节点", "最短距离", "路径"], rows)],
                    notes=["Dijkstra：贪心 + 优先队列；边权非负时，一个点一旦被永久标号，距离就不会再变短。",
                           f"永久标号顺序：{' → '.join(map(str, order))}。"],
                    graph=g, steps=frames)


if __name__ == "__main__":
    r = solve({f["id"]: f["value"] for f in SPEC["form"]})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"][:120])
