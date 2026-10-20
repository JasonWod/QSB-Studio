"""最短路径：Dijkstra 算法（O((V+E) log V)）。输入有向/无向带权图，求单源到各点的最短距离。"""
import heapq
from . import report as R
from . import graphviz as GV

SPEC = {
    "desc": "Dijkstra 单源最短路径：输入带权图（每行 u v w），求源点到各点最短距离与路径。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "边 (每行: u v w，节点编号从0起)", "rows": 8,
         "value": "0 1 2\n0 2 5\n1 2 4\n1 3 1\n2 3 8\n2 4 10\n3 4 3"},
        {"id": "source", "type": "int", "label": "源点", "value": "0"},
        {"id": "target", "type": "int", "label": "目标点 (留空求全部)", "value": "4"},
    ],
}


def _parse_edges(s):
    out = []
    for ln in (s or "").splitlines():
        parts = [x for x in ln.replace(",", " ").split()]
        if len(parts) >= 3:
            out.append((int(float(parts[0])), int(float(parts[1])), float(parts[2])))
    return out


def solve(p):
    edges = _parse_edges(p.get("edges"))
    src = int(p.get("source", 0) or 0)
    tgt = p.get("target", "")
    tgt = int(tgt) if str(tgt).strip() not in ("", "None") else None
    nodes = {src}
    for u, v, w in edges:
        nodes.add(u); nodes.add(v)
    n = max(nodes) + 1
    adj = {i: [] for i in range(n)}
    for u, v, w in edges:
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = {i: float("inf") for i in range(n)}
    prev = {i: None for i in range(n)}
    dist[src] = 0.0
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd; prev[v] = u
                heapq.heappush(pq, (nd, v))
    rows = []
    def path(u):
        out = []
        while u is not None:
            out.append(u); u = prev[u]
        return out[::-1]
    for i in range(n):
        if i == src:
            continue
        rows.append([i, R.fmt(dist[i]) if dist[i] != float("inf") else "∞",
                     "→".join(str(x) for x in path(i)) if dist[i] != float("inf") else ""])
    headline = ""
    if tgt is not None:
        headline = f"{src} → {tgt} 最短距离 = {R.fmt(dist[tgt]) if dist[tgt] != float('inf') else '不可达'}"

    # ---- 网络图：全部边(灰色) + 最短路(高亮) ----
    spath = path(tgt) if (tgt is not None and dist[tgt] != float("inf")) else []
    pset = set()
    for k in range(len(spath) - 1):
        a, b = spath[k], spath[k + 1]
        pset.add((a, b)); pset.add((b, a))
    edesc = []
    for u, v, w in edges:
        cls = "path" if ((u, v) in pset or (v, u) in pset) else "default"
        edesc.append((u, v, R.fmt(w), cls))
    groups = ["default"] * n
    groups[src] = "src"
    if tgt is not None:
        groups[tgt] = "sink"
    g = GV.circular_graph(list(range(n)), [str(i) for i in range(n)], groups, edesc, directed=False)
    return R.report("optimal", headline=headline or f"源点 {src} 到各点最短距离",
                    tables=[R.table("最短距离表", ["节点", "最短距离", "路径"], rows)],
                    notes=["Dijkstra：贪心 + 优先队列；边权须非负。"], graph=g)


if __name__ == "__main__":
    r = solve({"edges": SPEC["form"][0]["value"], "source": 0, "target": 4})
    print(r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
