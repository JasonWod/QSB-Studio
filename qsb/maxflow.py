"""最大流：Edmonds-Karp（BFS 增广路，O(VE²)）。"""
from collections import deque
from . import report as R
from . import graphviz as GV

SPEC = {
    "desc": "Edmonds-Karp 最大流：BFS 找增广路，反复增广直到没有。输入每行 u v 容量。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "有向边 (每行: u v 容量)", "rows": 8,
         "value": "0 1 16\n0 2 13\n1 2 10\n2 1 4\n1 3 12\n3 2 9\n3 4 20\n2 4 14"},
        {"id": "source", "type": "int", "label": "源点", "value": "0"},
        {"id": "sink", "type": "int", "label": "汇点", "value": "4"},
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
    raw = _parse_edges(p.get("edges"))
    s = int(p.get("source", 0) or 0)
    t = int(p.get("sink", -1) or -1)
    nodes = {s, t}
    for u, v, w in raw:
        nodes.add(u); nodes.add(v)
    n = max(nodes) + 1
    cap = [[0.0] * n for _ in range(n)]
    for u, v, w in raw:
        cap[u][v] += w
    flow = [[0.0] * n for _ in range(n)]
    total = 0.0
    # 记录 (u,v) 原始容量 + 最终流量，用于画图
    base = {}
    for u, v, w in raw:
        base[(u, v)] = base.get((u, v), 0) + w
    while True:
        level = [-1] * n; level[s] = 0
        q = deque([s])
        while q and level[t] < 0:
            u = q.popleft()
            for v in range(n):
                if level[v] < 0 and (cap[u][v] - flow[u][v]) > 0:
                    level[v] = level[u] + 1; q.append(v)
        if level[t] < 0:
            break
        # 回溯找增广量
        path_flow = float("inf"); v = t
        while v != s:
            u = max((x for x in range(n) if (cap[x][v] - flow[x][v]) > 0 and level[x] == level[v] - 1),
                    default=-1)
            if u < 0:
                break
            path_flow = min(path_flow, cap[u][v] - flow[u][v])
            v = u
        if path_flow == float("inf"):
            break
        v = t
        while v != s:
            u = max((x for x in range(n) if (cap[x][v] - flow[x][v]) > 0 and level[x] == level[v] - 1),
                    default=-1)
            if u < 0:
                break
            flow[u][v] += path_flow; flow[v][u] -= path_flow
            v = u
        total += path_flow
    # 每条有向边 (u,v) 的净流量
    rows = []
    for u, v, w in raw:
        f = flow[u][v] - flow[v][u]
        rows.append([u, v, R.fmt(w), R.fmt(f)])
    # ---- 网络图：有向，边粗细表流量 ----
    edesc = []
    for u, v, w in raw:
        f = flow[u][v] - flow[v][u]
        cls = "flow" if f > 1e-9 else "default"
        edesc.append((u, v, f"{R.fmt(w)}" + (f"/{R.fmt(f)}" if f > 1e-9 else ""), cls, max(0.0, f)))
    groups = ["default"] * n
    groups[s] = "src"; groups[t] = "sink"
    g = GV.circular_graph(list(range(n)), [str(i) for i in range(n)], groups, edesc, directed=True)
    return R.report("optimal", headline=f"最大流 = {R.fmt(total)}",
                    tables=[R.table("边流量 (前向边)", ["u", "v", "容量", "流量"], rows)],
                    notes=["Edmonds-Karp：每次用 BFS 找一条可增广路（最短增广路），增广量取路上残差最小值。"],
                    graph=g)


if __name__ == "__main__":
    r = solve({"edges": SPEC["form"][0]["value"], "source": 0, "sink": 4})
    print(r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
