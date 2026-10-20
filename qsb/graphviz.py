"""网络图可视化数据构造器。

把各模块的解转成统一的 {nodes, edges} 图描述，交给前端 SVG 渲染器画成网络图：
  * 节点坐标归一化到 [0,1]（前端再缩放到画布）
  * edges 用 from/to 指向节点 id；cls 决定高亮样式；val 决定线宽（流量/运量）
  * group 决定节点颜色（default / src / sink / left / right）
布局：circular（圆环，通用图）或 bipartite（左右两列，运输/指派）。
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


def circular_graph(ids, labels, groups, edges, directed=False):
    """ids: 节点 id 列表；labels: 标签（同长）；groups: 组名列表或 None。
       edges: [(from, to, label?, cls?, val?)]。"""
    pos = _circular(len(ids))
    nodes = []
    for i, lid in enumerate(ids):
        g = groups[i] if groups else "default"
        nodes.append({"id": str(lid), "label": labels[i],
                      "x": round(pos[i][0], 4), "y": round(pos[i][1], 4),
                      "group": g})
    return {"kind": "network", "directed": directed, "layout": "circular",
            "nodes": nodes, "edges": _edges(edges)}


def bipartite_graph(left_ids, left_labels, right_ids, right_labels, edges):
    """左列 + 右列；edges 为 (from_id, to_id, label?, cls?, val?)。"""
    lp = _col(len(left_ids), 0.20)
    rp = _col(len(right_ids), 0.80)
    nodes = []
    for i, lid in enumerate(left_ids):
        nodes.append({"id": str(lid), "label": left_labels[i],
                      "x": lp[i][0], "y": round(lp[i][1], 4), "group": "left"})
    for i, rid in enumerate(right_ids):
        nodes.append({"id": str(rid), "label": right_labels[i],
                      "x": rp[i][0], "y": round(rp[i][1], 4), "group": "right"})
    return {"kind": "network", "directed": True, "layout": "bipartite",
            "nodes": nodes, "edges": _edges(edges)}
