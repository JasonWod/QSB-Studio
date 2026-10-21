"""项目计划 PERT / CPM：双代号（箭线）网络，正推最早时间、逆推最迟时间、计算时差、找关键路线、算完工概率。

活动写法：前驱事件>后继事件>工期（CPM，确定工期）或 前驱事件>后继事件>o>m>p（PERT 三点估计）。
演示帧：节点按拓扑层从左到右排列，逐个事件正推 ES、逆推 LF，节点下方显示 [ES / LF]，
最后高亮总时差为 0 的关键活动，并画出完工时间的正态分布。
"""
import math
from collections import deque

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "项目网络计划：正推求各事件最早时间 ES，逆推求最迟时间 LF，活动总时差 = LF(终) − ES(始) − 工期，"
            "总时差为 0 的活动构成关键路线。三点估计时 te=(o+4m+p)/6，按关键路线方差求按期完工概率。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "活动（每行 前驱>后继>o>m>p，或 前驱>后继>工期）", "rows": 8,
         "value": "1>2>2>3>4\n1>3>3>5>7\n2>4>4>6>14\n3>4>2>4>6\n3>5>5>6>7\n4>6>3>4>5\n5>6>2>2>2"},
        {"id": "T", "type": "float", "label": "目标工期 T（求按期完工概率）", "value": "16"},
    ],
}


def solve(p):
    acts = []
    for ln in P.lines(p.get("edges")):
        parts = [t.strip() for t in ln.replace(",", ">").split(">") if t.strip()]
        if len(parts) == 3:
            d = P.nums(parts[2], "工期")[0]
            o = m = pp = d
        elif len(parts) == 5:
            o, m, pp = (P.nums(x, "工期估计")[0] for x in parts[2:5])
            if not (o <= m <= pp):
                raise R.InputError(f"活动「{ln}」需满足 乐观 o ≤ 最可能 m ≤ 悲观 p。")
        else:
            raise R.InputError(f"活动「{ln}」格式应为 前驱>后继>工期 或 前驱>后继>o>m>p。")
        if min(o, m, pp) < 0:
            raise R.InputError(f"活动「{ln}」的工期不能为负。")
        te = (o + 4 * m + pp) / 6.0
        var = ((pp - o) / 6.0) ** 2
        acts.append({"from": parts[0], "to": parts[1], "o": o, "m": m, "p": pp, "te": te, "var": var,
                     "name": f"{parts[0]}→{parts[1]}"})
    if not acts:
        raise R.InputError("没有有效活动。格式：每行 前驱>后继>o>m>p。")
    if len(acts) > 60:
        raise R.InputError("最多 60 项活动。")
    pert = any(a["var"] > 0 for a in acts)
    nodes = []
    for a in acts:
        for x in (a["from"], a["to"]):
            if x not in nodes:
                nodes.append(x)
    out = {v: [] for v in nodes}
    inn = {v: [] for v in nodes}
    for a in acts:
        out[a["from"]].append(a); inn[a["to"]].append(a)
    indeg = {v: len(inn[v]) for v in nodes}
    q = deque([v for v in nodes if indeg[v] == 0])
    topo, level = [], {v: 0 for v in nodes}
    while q:
        u = q.popleft(); topo.append(u)
        for a in out[u]:
            level[a["to"]] = max(level[a["to"]], level[u] + 1)
            indeg[a["to"]] -= 1
            if indeg[a["to"]] == 0:
                q.append(a["to"])
    if len(topo) != len(nodes):
        raise R.InputError("活动网络中有回路，不是合法的项目网络。")
    starts = [v for v in nodes if not inn[v]]
    ends = [v for v in nodes if not out[v]]
    pos = GV.layered_positions(topo, level)
    ES, LF = {}, {}
    frames = []

    def snap(title, text, cur=None, crit=None, hl_acts=()):
        groups, subs = {}, {}
        for v in nodes:
            g = "src" if v in starts else ("sink" if v in ends else "default")
            if v == cur:
                g = "current"
            groups[v] = g
            subs[v] = f"[{R.fmt(ES[v]) if v in ES else '?'} / {R.fmt(LF[v]) if v in LF else '?'}]"
        ed = []
        for a in acts:
            if crit is not None and a["name"] in crit:
                cls = "path"
            elif a["name"] in hl_acts:
                cls = "active"
            else:
                cls = "default"
            ed.append((a["from"], a["to"], R.fmt(a["te"], 2), cls))
        g = GV.positioned_graph(pos, {v: v for v in nodes}, groups, ed, directed=True, subs=subs)
        frames.append(R.frame(title, text, graph=g))

    if pert:
        rows = [[a["name"], R.fmt(a["o"]), R.fmt(a["m"]), R.fmt(a["p"]), R.fmt(a["te"]), R.fmt(a["var"])] for a in acts]
        frames.append(R.frame("第 0 步：三点估计", "每项活动期望工期 te = (o + 4m + p)/6，方差 σ² = ((p − o)/6)²。"
                              "图中边上数字为 te，节点下方 [ES / LF] 待计算。",
                              tables=[R.table("三点估计", ["活动", "o", "m", "p", "te", "σ²"], rows)]))
        snap("项目网络", "箭线代表活动，圆圈代表事件。下面先正推再逆推。")
    else:
        snap("项目网络", "箭线代表活动（边上数字为工期），圆圈代表事件。节点下方 [ES / LF] 待计算。")
    for v in topo:
        if not inn[v]:
            ES[v] = 0.0
            snap(f"正推：事件 {v}", f"事件 {v} 是起点，最早时间 ES = 0。", cur=v)
            continue
        cands = [(ES[a["from"]] + a["te"], a) for a in inn[v]]
        ES[v] = max(c[0] for c in cands)
        terms = ", ".join("ES({})+{}".format(a["from"], R.fmt(a["te"], 2)) for _, a in cands)
        vals = ", ".join(R.fmt(c[0], 2) for c in cands)
        snap(f"正推：事件 {v}", f"ES({v}) = max{{{terms}}} = max{{{vals}}} = {R.fmt(ES[v], 2)}。所有紧前活动都完成，事件才能发生。",
             cur=v, hl_acts=[a["name"] for _, a in cands])
    TE = max(ES[v] for v in ends)
    for v in reversed(topo):
        if not out[v]:
            LF[v] = TE
            snap(f"逆推：事件 {v}", f"终点事件的最迟时间 LF = 总工期 {R.fmt(TE, 2)}。", cur=v)
            continue
        cands = [(LF[a["to"]] - a["te"], a) for a in out[v]]
        LF[v] = min(c[0] for c in cands)
        terms = ", ".join("LF({})−{}".format(a["to"], R.fmt(a["te"], 2)) for _, a in cands)
        snap(f"逆推：事件 {v}", f"LF({v}) = min{{{terms}}} = {R.fmt(LF[v], 2)}。再晚就会拖延紧后活动。", cur=v, hl_acts=[a["name"] for _, a in cands])
    for a in acts:
        a["es"] = ES[a["from"]]; a["ef"] = a["es"] + a["te"]
        a["lf"] = LF[a["to"]]; a["ls"] = a["lf"] - a["te"]
        a["tf"] = a["lf"] - a["es"] - a["te"]
        a["ff"] = ES[a["to"]] - a["es"] - a["te"]
    crit = {a["name"] for a in acts if abs(a["tf"]) < 1e-9}
    path = [starts[0]] if starts else []
    while path and out[path[-1]]:
        nxt = [a for a in out[path[-1]] if a["name"] in crit]
        if not nxt:
            break
        path.append(nxt[0]["to"])
    rows = [[a["name"], R.fmt(a["te"], 2), R.fmt(a["es"], 2), R.fmt(a["ef"], 2), R.fmt(a["ls"], 2), R.fmt(a["lf"], 2),
             R.fmt(a["tf"], 2), R.fmt(a["ff"], 2), "★" if a["name"] in crit else ""] for a in acts]
    cells = {(i, 8): "c-good" for i, a in enumerate(acts) if a["name"] in crit}
    tbl = R.table("活动时间参数", ["活动", "工期", "ES", "EF", "LS", "LF", "总时差", "自由时差", "关键"], rows, cells=cells)
    snap("时差与关键路线", f"总时差 = LF(终) − ES(始) − 工期；为 0 的活动没有任何机动余地，连成关键路线 "
         f"{' → '.join(path)}（紫色），总工期 {R.fmt(TE, 2)}。", crit=crit)
    frames[-1]["tables"] = [tbl]
    notes = ["总时差：在不推迟总工期的前提下活动可推迟的时间；自由时差：不推迟紧后活动最早开始的可推迟时间。"]
    head = f"关键路线 {' → '.join(path)}：总工期 {R.fmt(TE, 2)}"
    tables = [tbl]
    chart = None
    if pert:
        T = P.num(p, "T", TE, "目标工期 T")
        sd = math.sqrt(sum(a["var"] for a in acts if a["name"] in crit and a["from"] in path and a["to"] in path
                           and path.index(a["to"]) == path.index(a["from"]) + 1))
        prob = 0.5 * (1 + math.erf((T - TE) / (sd * math.sqrt(2)))) if sd > 0 else (1.0 if T >= TE else 0.0)
        if sd > 0:
            xs = [TE + sd * (-3.5 + 0.1 * i) for i in range(71)]
            pdf = [math.exp(-((x - TE) / sd) ** 2 / 2) / (sd * math.sqrt(2 * math.pi)) for x in xs]
            hl = min(range(len(xs)), key=lambda i: abs(xs[i] - T))
            chart = {"type": "line", "x": [R.fmt(x, 1) for x in xs], "title": f"完工时间 ~ N({R.fmt(TE, 2)}, {R.fmt(sd, 3)}²)",
                     "series": [{"name": "概率密度", "values": [round(v, 5) for v in pdf], "shade": [[0, hl]]}],
                     "xtitle": "完工时间", "hl": hl}
        frames.append(R.frame("按期完工概率",
                              f"关键路线工期之和近似正态：均值 {R.fmt(TE, 2)}，σ = √(关键活动方差之和) = {R.fmt(sd)}。"
                              f"P(工期 ≤ {R.fmt(T)}) = Φ(({R.fmt(T)} − {R.fmt(TE, 2)}) / {R.fmt(sd)}) = Φ({R.fmt((T - TE) / sd if sd else 0)})"
                              f" = {R.fmt(prob)}（阴影面积）。", chart=chart))
        head += f"，σ = {R.fmt(sd)}，P(≤{R.fmt(T)}) = {R.fmt(prob)}"
        notes.append("PERT 假设关键路线上各活动独立；若有多条关键路线或近关键路线，概率会偏乐观。")
    return R.report("optimal", headline=head, tables=tables, graph=frames[-2 if pert else -1]["graph"],
                    chart=chart, steps=frames, notes=notes)


if __name__ == "__main__":
    r = solve({f["id"]: f["value"] for f in SPEC["form"]})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], "|", f["text"][:110])
    print(solve({"edges": "1>2>3\n1>3>2\n2>4>4\n3>4>6", "T": 9})["headline"])
