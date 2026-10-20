"""最小生成树：Kruskal 算法（O(E log E)）。带权连通无向图 → 连接所有点且总权最小的树。"""
from . import report as R
from . import graphviz as GV

SPEC = {
    "desc": "Kruskal 最小生成树：边按权排序 + 并查集避免回环。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "边 (每行: u v w)", "rows": 8,
         "value": "0 1 4\n0 2 4\n1 2 1\n1 3 2\n2 3 6\n2 4 5\n3 4 3\n4 5 6\n3 5 4\n0 5 7"},
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
    if not edges:
        return R.report("error", headline="没有可解析的边")
    parent = {}
    def find(x):
        if x not in parent:
            parent[x] = x
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[ra] = rb
        return True
    mst = []
    total = 0.0
    for u, v, w in sorted(edges, key=lambda e: e[2]):
        if union(u, v):
            mst.append((u, v, w)); total += w
    nodes = set()
    for u, v, w in edges:
        nodes.add(u); nodes.add(v)
    n = max(nodes) + 1
    connected = len({find(i) for i in nodes}) == 1
    # ---- 网络图：全部边(灰) + MST 边(绿高亮) ----
    mset = set()
    for u, v, w in mst:
        mset.add((u, v)); mset.add((v, u))
    edesc = []
    for u, v, w in edges:
        cls = "mst" if ((u, v) in mset or (v, u) in mset) else "default"
        edesc.append((u, v, R.fmt(w), cls))
    g = GV.circular_graph(list(range(n)), [str(i) for i in range(n)], None, edesc, directed=False)
    status = "optimal" if connected else "infeasible"
    return R.report(status,
                    headline=(f"最小生成树总权 = {R.fmt(total)}" if connected
                              else "图不连通，无法生成生成树"),
                    tables=[R.table("MST 选中边", ["u", "v", "权"],
                                    [[u, v, R.fmt(w)] for u, v, w in mst])],
                    notes=["Kruskal：边按权升序，用并查集跳过会造成回路的边；若图不连通得到的是最小生成森林。"],
                    graph=g)


if __name__ == "__main__":
    r = solve({"edges": SPEC["form"][0]["value"]})
    print(r["status"], r["headline"])
    print("graph nodes:", len(r["graph"]["nodes"]), "edges:", len(r["graph"]["edges"]))
