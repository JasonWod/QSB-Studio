"""最小生成树：Kruskal（边排序 + 并查集）或 Prim（从一点向外生长）。

演示帧：Kruskal 逐条考察边，接受（绿）或因成环拒绝（红虚线）；Prim 每步加入跨越切割的最轻边。
"""
import heapq

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "最小生成树：Kruskal 把边按权从小到大逐条考察，不成环就选入（并查集判环）；"
            "Prim 从一个点出发，每次加入连接「树内—树外」的最轻边。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "边 (每行: u v w)", "rows": 8,
         "value": "0 1 4\n0 2 4\n1 2 1\n1 3 2\n2 3 6\n2 4 5\n3 4 3\n4 5 6\n3 5 4\n0 5 7"},
        {"id": "method", "type": "select", "label": "算法", "value": "kruskal",
         "options": [{"v": "kruskal", "t": "Kruskal（避圈法）"}, {"v": "prim", "t": "Prim（加点法）"}]},
    ],
}


def solve(p):
    edges = P.edges(p.get("edges"))
    if not edges:
        raise R.InputError("没有可解析的边，每行写 u v w。")
    method = p.get("method", "kruskal")
    nodes = sorted({u for u, _, _ in edges} | {v for _, v, _ in edges})
    n = max(nodes) + 1
    if n > 40:
        raise R.InputError("教学版最多 40 个节点。")
    ids = list(range(n))
    chosen, rejected = set(), set()
    frames = []
    in_tree = set()

    def snap(title, text, cur=None, cur_cls="active", cand=()):
        ed = []
        for k, (u, v, w) in enumerate(edges):
            cls = "mst" if k in chosen else ("reject" if k in rejected else ("candidate" if k in cand else "default"))
            if k == cur:
                cls = cur_cls
            ed.append((u, v, R.fmt(w), cls))
        groups = ["done" if i in in_tree else "default" for i in ids] if method == "prim" else None
        g = GV.circular_graph(ids, [str(i) for i in ids], groups, ed, directed=False)
        total = sum(edges[k][2] for k in chosen)
        tb = R.table("已选边", ["u", "v", "权"], [[edges[k][0], edges[k][1], R.fmt(edges[k][2])] for k in sorted(chosen)]
                     + [["", "合计", R.fmt(total)]])
        frames.append(R.frame(title, text, tables=[tb], graph=g))

    if method == "kruskal":
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        order = sorted(range(len(edges)), key=lambda k: (edges[k][2], k))
        snap("准备：边按权排序", "边按权从小到大：" + "，".join(f"({edges[k][0]},{edges[k][1]}):{R.fmt(edges[k][2])}"
                                                    for k in order) + "。")
        step = 0
        for k in order:
            if len(chosen) == len(nodes) - 1:
                break
            u, v, w = edges[k]
            step += 1
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
                chosen.add(k)
                snap(f"第 {step} 步：选入边 ({u},{v})", f"边 ({u},{v}) 权 {R.fmt(w)}，两端属于不同的树，选入并合并两棵树。", cur=k,
                     cur_cls="mst")
            else:
                rejected.add(k)
                snap(f"第 {step} 步：拒绝边 ({u},{v})", f"边 ({u},{v}) 权 {R.fmt(w)}，两端已经连通，加入会形成回路，跳过。",
                     cur=k, cur_cls="reject")
        comps = len({find(i) for i in nodes})
    else:
        start = nodes[0]
        in_tree.add(start)
        adj = {i: [] for i in ids}
        for k, (u, v, w) in enumerate(edges):
            adj[u].append((w, k, v)); adj[v].append((w, k, u))
        pq = [(w, k, v) for w, k, v in adj[start]]
        heapq.heapify(pq)
        snap("准备：从节点 %d 出发" % start, f"把节点 {start} 放进树中，候选边（虚线）是所有一端在树内、一端在树外的边。",
             cand=[k for _, k, _ in pq])
        step = 0
        while pq and len(in_tree) < len(nodes):
            w, k, v = heapq.heappop(pq)
            if v in in_tree:
                continue
            step += 1
            in_tree.add(v)
            chosen.add(k)
            for item in adj[v]:
                if item[2] not in in_tree:
                    heapq.heappush(pq, item)
            cand = [kk for _, kk, vv in pq if vv not in in_tree]
            snap(f"第 {step} 步：加入节点 {v}", f"跨越「树内—树外」的边中 ({edges[k][0]},{edges[k][1]}) 最轻（权 {R.fmt(w)}），"
                 f"选入，节点 {v} 进树。", cur=k, cur_cls="mst", cand=cand)
        comps = 1 if len(in_tree) == len(nodes) else 2
    total = sum(edges[k][2] for k in chosen)
    connected = comps == 1
    ed = [(u, v, R.fmt(w), "mst" if k in chosen else "default") for k, (u, v, w) in enumerate(edges)]
    g = GV.circular_graph(ids, [str(i) for i in ids], None, ed, directed=False)
    frames.append(R.frame("结果", f"共选 {len(chosen)} 条边，总权 {R.fmt(total)}。"
                          + ("" if connected else "图不连通，得到的是最小生成森林。"), graph=g))
    return R.report("optimal" if connected else "infeasible",
                    headline=(f"最小生成树总权 = {R.fmt(total)}" if connected else "图不连通，无法生成生成树"),
                    tables=[R.table("MST 选中边", ["u", "v", "权"],
                                    [[edges[k][0], edges[k][1], R.fmt(edges[k][2])] for k in sorted(chosen)])],
                    notes=["Kruskal：边按权升序，用并查集跳过会形成回路的边。" if method == "kruskal" else
                           "Prim：维护一棵树，反复加入连接树内外的最轻边（切割性质保证正确）。",
                           f"n 个节点的生成树恰有 n−1 = {len(nodes) - 1} 条边。"],
                    graph=g, steps=frames)


if __name__ == "__main__":
    for mth in ("kruskal", "prim"):
        r = solve({"edges": SPEC["form"][0]["value"], "method": mth})
        print(r["headline"], len(r["steps"]))
