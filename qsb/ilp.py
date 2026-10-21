"""整数线性规划：分支定界 (branch & bound)，支持纯整数 / 0-1 / 混合整数。

每个节点用大 M 单纯形解 LP 松弛；按「界最好优先」展开；对最「分数」的整数变量分支
x ≤ ⌊v⌋ / x ≥ ⌈v⌉；界不优于当前最优整数解的节点剪枝。演示帧逐节点画出分支定界树。
"""
import heapq
import math

from . import graphviz as GV
from . import lp as _lp
from . import parse as P
from . import report as R

SPEC = {
    "desc": "整数规划 (ILP)：分支定界法。每个节点解 LP 松弛得到界，对取分数值的整数变量分支 x≤⌊v⌋ / x≥⌈v⌉，"
            "界不优于当前最优整数解就剪枝。变量可设为整数(i) / 0-1(b) / 连续(c)，即纯整数、0-1、混合整数规划。",
    "form": [
        {"id": "obj", "type": "select", "label": "方向", "value": "max",
         "options": [{"v": "max", "t": "最大化 max"}, {"v": "min", "t": "最小化 min"}]},
        {"id": "c", "type": "list", "label": "目标系数 c（逗号分隔）", "value": "5, 8"},
        {"id": "constraints", "type": "textarea", "label": "约束（每行 a1,a2,...,an <op> b；op 用 <= / >= / =）",
         "value": "1,1 <= 6\n5,9 <= 45"},
        {"id": "types", "type": "list", "label": "变量类型（i=整数, b=0-1, c=连续；留空=全整数）", "value": "i, i"},
        {"id": "max_nodes", "type": "int", "label": "最大搜索节点数", "value": "200"},
    ],
}

INT_TOL = 1e-6


def _parse(p):
    obj = p.get("obj", "max")
    if obj not in ("max", "min"):
        raise R.InputError("方向必须是 max 或 min。")
    c = P.nums(p.get("c"), "目标系数")
    n = len(c)
    if n == 0:
        raise R.InputError("至少需要一个目标系数。")
    if n > 12:
        raise R.InputError("教学版整数规划最多 12 个变量。")
    A, b, senses = [], [], []
    for ln in P.lines(p.get("constraints")):
        coef, op, rhs = P.constraint(ln, n)
        A.append(coef); b.append(rhs); senses.append(op)
    if not A:
        raise R.InputError("至少需要一条约束。")
    toks = [t.lower() for t in P._SPLIT.split(" ".join(P.lines(p.get("types")))) if t]
    if not toks:
        toks = ["i"] * n
    if len(toks) != n or any(t not in ("i", "b", "c") for t in toks):
        raise R.InputError(f"变量类型应给出 {n} 个，取值 i(整数) / b(0-1) / c(连续)，如「i, i, c」。")
    max_nodes = P.integer(p, "max_nodes", 200, "最大搜索节点数", 1, 2000)
    return obj, c, A, b, senses, toks, max_nodes


def solve(p):
    obj, c, A0, b0, s0, types, max_nodes = _parse(p)
    n = len(c)
    names = [f"x{i + 1}" for i in range(n)]
    sign = 1.0 if obj == "max" else -1.0         # 内部统一按 max(sign·c·x) 比较
    A, b, senses = [r[:] for r in A0], b0[:], s0[:]
    for k, t in enumerate(types):
        if t == "b":                              # 0-1 变量：加 x ≤ 1
            row = [0.0] * n; row[k] = 1.0
            A.append(row); b.append(1.0); senses.append("le")
    is_int = [t in ("i", "b") for t in types]

    nodes = {}          # id -> dict
    children = {}
    counter = [0]
    best_x, best_val = None, None   # best_val 为原始目标值
    frames = []

    def solve_node(extra):
        AA = A + [e[0] for e in extra]
        bb = b + [e[1] for e in extra]
        ss = senses + [e[2] for e in extra]
        r = _lp.solve_lp("max", [sign * v for v in c], AA, bb, ss, names)
        if r["status"] != "optimal":
            return r["status"], None, None
        x = [float(r["solution"][nm]) for nm in names]
        return "optimal", x, sum(c[k] * x[k] for k in range(n))

    def better(v, ref):
        return ref is None or (v > ref + 1e-9 if obj == "max" else v < ref - 1e-9)

    def snapshot(cur, title, text):
        groups, subs, labels, edges = {}, {}, {}, []
        for nid, nd in nodes.items():
            labels[nid] = f"N{nid}"
            st = nd["state"]
            groups[nid] = {"current": "current", "integer": "best", "pruned": "pruned",
                           "infeasible": "pruned", "branched": "done", "open": "default",
                           "limit": "default"}[st]
            if nid == cur:
                groups[nid] = "current"
            if best_x is not None and nd.get("x") == best_x and st == "integer":
                groups[nid] = "best"
            subs[nid] = ("z=" + R.fmt(nd["z"], 3)) if nd.get("z") is not None else (
                "不可行" if st == "infeasible" else "")
            if nd["parent"] is not None:
                edges.append((nd["parent"], nid, nd["branch"],
                              "active" if nid == cur else "default"))
        pos = GV.tree_positions(children, 0)
        g = GV.positioned_graph(pos, labels, groups, edges, directed=True, subs=subs, layout="tree")
        rows = [[f"N{nid}", nd["branch"] or "根", ", ".join(R.fmt(v, 3) for v in nd["x"]) if nd.get("x") else "—",
                 R.fmt(nd["z"], 4) if nd.get("z") is not None else "—", nd["verdict"]]
                for nid, nd in sorted(nodes.items())]
        cells = {(i, 0): "c-cur" for i, (nid, _) in enumerate(sorted(nodes.items())) if nid == cur}
        tb = R.table("节点记录", ["节点", "新增分支约束", "LP 松弛解 x", "LP 目标 z", "处理结果"], rows, cells=cells)
        inc = ("当前最优整数解：" + ", ".join(f"{names[k]}={R.fmt(best_x[k])}" for k in range(n))
               + f"，目标 {R.fmt(best_val)}") if best_x else "当前还没有找到整数可行解。"
        frames.append(R.frame(title, text + " " + inc, tables=[tb], graph=g))

    # 优先队列：按 LP 界最好优先（max 空间取负号入堆）
    heap = []

    def push(parent, branch, extra):
        nid = counter[0]; counter[0] += 1
        status, x, z = solve_node(extra)
        nodes[nid] = {"parent": parent, "branch": branch, "extra": extra, "x": x, "z": z,
                      "state": "open", "verdict": "待处理"}
        children.setdefault(nid, [])
        if parent is not None:
            children[parent].append(nid)
        if status != "optimal":
            nodes[nid]["state"] = "infeasible"
            nodes[nid]["verdict"] = "LP 不可行 → 剪枝" if status == "infeasible" else f"LP {status} → 停止该分支"
            return nid
        heapq.heappush(heap, (-sign * z, nid))
        return nid

    push(None, "", [])
    root = nodes[0]
    if root["state"] == "infeasible":
        snapshot(0, "根节点：LP 松弛不可行", "去掉整数要求后的 LP 已经无解，整数规划自然也无解。")
        return R.report("infeasible", headline="LP 松弛不可行，整数规划无可行解。", steps=frames,
                        tables=frames[-1]["tables"])
    snapshot(0, "第 0 步：解根节点的 LP 松弛",
             f"先忽略整数要求，解 LP 得 z = {R.fmt(root['z'])}，"
             f"x = ({', '.join(R.fmt(v, 3) for v in root['x'])})。这是整数最优值的{'上' if obj == 'max' else '下'}界。")

    expanded = 0
    while heap:
        _, nid = heapq.heappop(heap)
        nd = nodes[nid]
        if expanded >= max_nodes:
            nd["state"] = "limit"; nd["verdict"] = "达到节点上限，未处理"
            continue
        expanded += 1
        x, z = nd["x"], nd["z"]
        step_title = f"第 {expanded} 步：处理节点 N{nid}"
        if best_val is not None and not better(z, best_val):
            nd["state"] = "pruned"
            nd["verdict"] = f"界 {R.fmt(z, 4)} 不优于最优 {R.fmt(best_val)} → 剪枝"
            snapshot(nid, step_title, f"N{nid} 的 LP 界 z = {R.fmt(z)} 已经不比当前最优整数解好，整枝剪掉，不再展开。")
            continue
        frac = [k for k in range(n) if is_int[k] and abs(x[k] - round(x[k])) > INT_TOL]
        if not frac:
            nd["state"] = "integer"
            if better(z, best_val):
                best_val, best_x = z, [round(v) if is_int[k] else v for k, v in enumerate(x)]
                nd["x"] = best_x
                nd["verdict"] = "整数解，更新最优"
                snapshot(nid, step_title, f"N{nid} 的 LP 解恰好满足整数要求，z = {R.fmt(z)}，成为新的最优整数解。")
            else:
                nd["verdict"] = "整数解，但不更优"
                snapshot(nid, step_title, f"N{nid} 得到整数解 z = {R.fmt(z)}，但不比当前最优好。")
            continue
        k = max(frac, key=lambda j: (min(x[j] - math.floor(x[j]), math.ceil(x[j]) - x[j]), -j))
        fl, ce = math.floor(x[k]), math.ceil(x[k])
        row = [0.0] * n; row[k] = 1.0
        nd["state"] = "branched"
        nd["verdict"] = f"{names[k]}={R.fmt(x[k], 3)} 非整数 → 分支"
        a = push(nid, f"{names[k]}≤{fl}", nd["extra"] + [(row, float(fl), "le")])
        bb = push(nid, f"{names[k]}≥{ce}", nd["extra"] + [(row, float(ce), "ge")])
        da, db = nodes[a], nodes[bb]
        desc = lambda d, i: (f"N{i}：z = {R.fmt(d['z'])}" if d["z"] is not None else f"N{i}：不可行")
        snapshot(nid, step_title,
                 f"N{nid} 的 LP 解中 {names[k]} = {R.fmt(x[k], 4)} 不是整数，分成两支："
                 f"{names[k]} ≤ {fl} 与 {names[k]} ≥ {ce}。{desc(da, a)}；{desc(db, bb)}。")

    if best_x is None:
        status = "infeasible"
        head = f"未找到整数可行解（展开 {expanded} 个节点{'，已达上限' if expanded >= max_nodes else ''}）。"
    else:
        status = "optimal" if expanded < max_nodes or not heap else "feasible"
        head = (f"最优整数解 {' '.join(f'{names[k]}={R.fmt(best_x[k])}' for k in range(n))}，"
                f"目标值 = {R.fmt(best_val)}")
        if expanded >= max_nodes:
            status = "feasible"
            head += f"（达到节点上限 {max_nodes}，不保证最优）"
    root_z = root["z"]
    summary = [["决策变量", ", ".join(f"{names[k]}={R.fmt(best_x[k])}" for k in range(n)) if best_x else "—"],
               ["目标值（整数最优）", R.fmt(best_val)],
               ["根节点 LP 松弛界", R.fmt(root_z)],
               ["整数间隙 |LP界 − 整数解|", R.fmt(abs(root_z - best_val)) if best_x else "—"],
               ["变量类型", ", ".join(f"{names[k]}:{ {'i': '整数', 'b': '0-1', 'c': '连续'}[types[k]] }"
                                    for k in range(n))],
               ["生成 / 展开节点数", f"{len(nodes)} / {expanded}（上限 {max_nodes}）"]]
    return R.report(
        status, headline=head,
        tables=[R.table("分支定界结果", ["项", "值"], summary), frames[-1]["tables"][0]],
        graph=frames[-1]["graph"],
        steps=R.thin(frames, 80),
        notes=["每个节点解 LP 松弛得到界；对分数变量分支 x≤⌊v⌋ / x≥⌈v⌉。",
               "按界最好优先展开；界不优于当前最优整数解的节点被剪枝。",
               "树中颜色：橙=本步处理，绿=最优整数解，灰=剪枝/不可行，蓝=已分支。"])


if __name__ == "__main__":
    print(solve({"obj": "max", "c": "5, 8", "constraints": "1,1 <= 6\n5,9 <= 45"})["headline"])
