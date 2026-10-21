"""网络图可视化数据构造器。

把各模块的解转成统一的 {nodes, edges} 图描述，交给前端 SVG 渲染器画成网络图：
  * 节点坐标归一化到 [0,1]（前端再缩放到画布）
  * edges 用 from/to 指向节点 id；cls 决定高亮样式；val 决定线宽（流量/运量）
  * node.group 决定节点颜色；node.sub 是节点下方的小字注释（如当前距离）

节点 group：default / src / sink / left / right / current(本步焦点) / done(已确定)
           / pruned(被剪枝) / best(当前最优)
边 cls：    default / path / mst / flow / ship / assign / active(本步焦点) / reject(拒绝)
           / candidate(候选)

布局：circular（圆环）、bipartite（左右两列）、layered（按拓扑层从左到右）、tree（自上而下的树）。
"""
import math


def _circular(n):
    if n <= 0:
        return []
    if n == 1:
        return [(0.5, 0.5)]
    out = []
    for i in range(n):
        ang = 2 * math.pi * i / n - math.pi / 2
        out.append((0.5 + 0.42 * math.cos(ang), 0.5 + 0.42 * math.sin(ang)))
    return out


def _col(n, x):
    if n <= 0:
        return []
    if n == 1:
        return [(x, 0.5)]
    return [(x, 0.12 + 0.76 * i / (n - 1)) for i in range(n)]


def _edges(lst):
    out = []
    for e in lst:
        out.append({
            "from": str(e[0]), "to": str(e[1]),
            "label": str(e[2]) if len(e) > 2 and e[2] not in (None, "") else "",
            "cls": e[3] if len(e) > 3 and e[3] else "default",
            "val": e[4] if len(e) > 4 else None,
        })
    return out


def _node(nid, label, x, y, group="default", sub=None):
    d = {"id": str(nid), "label": str(label), "x": round(x, 4), "y": round(y, 4),
         "group": group or "default"}
    if sub not in (None, ""):
        d["sub"] = str(sub)
    return d


def circular_graph(ids, labels, groups, edges, directed=False, subs=None):
    """ids: 节点 id 列表；labels: 标签（同长）；groups: 组名列表或 None；subs: 注释列表或 None。
       edges: [(from, to, label?, cls?, val?)]。"""
    pos = _circular(len(ids))
    nodes = [_node(lid, labels[i], pos[i][0], pos[i][1],
                   groups[i] if groups else "default", subs[i] if subs else None)
             for i, lid in enumerate(ids)]
    return {"kind": "network", "directed": directed, "layout": "circular",
            "nodes": nodes, "edges": _edges(edges)}


def bipartite_graph(left_ids, left_labels, right_ids, right_labels, edges,
                    left_groups=None, right_groups=None, left_subs=None, right_subs=None):
    """左列 + 右列；edges 为 (from_id, to_id, label?, cls?, val?)。"""
    lp = _col(len(left_ids), 0.20)
    rp = _col(len(right_ids), 0.80)
    nodes = []
    for i, lid in enumerate(left_ids):
        nodes.append(_node(lid, left_labels[i], lp[i][0], lp[i][1],
                           left_groups[i] if left_groups else "left",
                           left_subs[i] if left_subs else None))
    for i, rid in enumerate(right_ids):
        nodes.append(_node(rid, right_labels[i], rp[i][0], rp[i][1],
                           right_groups[i] if right_groups else "right",
                           right_subs[i] if right_subs else None))
    return {"kind": "network", "directed": True, "layout": "bipartite",
            "nodes": nodes, "edges": _edges(edges)}


def layered_positions(order, level):
    """order: 节点（拓扑序）；level: {node: 层号}。返回 {node: (x, y)}，层从左到右。"""
    maxl = max(level.values()) if level else 0
    cols = {}
    for nd in order:
        cols.setdefault(level[nd], []).append(nd)
    pos = {}
    for lv, ns in cols.items():
        x = 0.08 + 0.84 * (lv / maxl if maxl else 0.5)
        for i, nd in enumerate(ns):
            y = 0.5 if len(ns) == 1 else 0.15 + 0.7 * i / (len(ns) - 1)
            pos[nd] = (x, y)
    return pos


def positioned_graph(pos, labels, groups, edges, directed=True, subs=None, layout="layered"):
    """pos: {id: (x, y)}；labels/groups/subs: {id: ...}。"""
    nodes = [_node(nid, labels.get(nid, nid), x, y,
                   (groups or {}).get(nid, "default"), (subs or {}).get(nid))
             for nid, (x, y) in pos.items()]
    return {"kind": "network", "directed": directed, "layout": layout,
            "nodes": nodes, "edges": _edges(edges)}


def tree_positions(children, root):
    """children: {id: [child ids]}。叶子等距排开，父节点居中；返回 {id: (x, y)}。"""
    depth, xs, leaf = {}, {}, [0]

    def walk(u, d):
        depth[u] = d
        ch = children.get(u, [])
        if not ch:
            xs[u] = leaf[0]
            leaf[0] += 1
        else:
            for c in ch:
                walk(c, d + 1)
            xs[u] = (xs[ch[0]] + xs[ch[-1]]) / 2

    walk(root, 0)
    nl = max(1, leaf[0] - 1)
    md = max(1, max(depth.values()))
    return {u: (0.08 + 0.84 * (xs[u] / nl if leaf[0] > 1 else 0.5),
                0.1 + 0.8 * depth[u] / md) for u in depth}
