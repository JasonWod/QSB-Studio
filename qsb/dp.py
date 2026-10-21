"""动态规划：0/1 背包（自底向上填表）与驿站马车（多阶段最短路，逆序递推）。

演示帧：
  背包——每加入一件物品填一行 dp 表，高亮「拿」比「不拿」更优而被改写的格子，最后回溯选品；
  驿站马车——从终点往回逐阶段计算 f(状态) = min{弧长 + f(下一状态)}，网络图同步高亮当前阶段。
"""
from collections import deque

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "动态规划：把问题分阶段，用表格记住子问题的最优值。0/1 背包按物品逐行填 dp[i][c]；"
            "驿站马车（多阶段最短路）从终点逆序递推 f(s) = min{c(s,t) + f(t)}。",
    "form": [
        {"id": "problem", "type": "select", "label": "问题", "value": "knapsack",
         "options": [{"v": "knapsack", "t": "0/1 背包"}, {"v": "stagecoach", "t": "驿站马车（多阶段最短路）"}]},
        {"id": "W", "type": "int", "label": "背包容量 W（背包用）", "value": "10"},
        {"id": "items", "type": "textarea", "label": "物品（背包用，每行 重量>价值）", "rows": 5,
         "value": "2>3\n3>4\n4>5\n5>8\n9>10"},
        {"id": "arcs", "type": "textarea", "label": "弧（驿站马车用，每行 起点>终点>距离）", "rows": 6,
         "value": "A>B>2\nA>C>4\nA>D>3\nB>E>7\nB>F>4\nB>G>6\nC>E>3\nC>F>2\nC>G>4\nD>E>4\nD>F>1\nD>G>5\n"
                  "E>H>1\nE>I>4\nF>H>6\nF>I>3\nG>H>3\nG>I>3\nH>J>3\nI>J>4"},
    ],
}


def _knapsack(p):
    W = P.integer(p, "W", 10, "背包容量 W", 0, 200)
    objs = []
    for ln in P.lines(p.get("items")):
        parts = [t for t in ln.replace(">", " ").replace(",", " ").split() if t]
        if len(parts) < 2:
            raise R.InputError(f"物品「{ln}」格式应为 重量>价值。")
        w, v = P.nums(parts[0], "重量")[0], P.nums(parts[1], "价值")[0]
        if w < 0 or w != int(w):
            raise R.InputError(f"物品「{ln}」的重量须为非负整数（表格按整数容量填写）。")
        objs.append((int(w), v))
    if not objs:
        raise R.InputError("没有有效物品。格式：每行 重量>价值。")
    if len(objs) > 30:
        raise R.InputError("最多 30 件物品。")
    n = len(objs)
    dp = [[0.0] * (W + 1) for _ in range(n + 1)]
    take = [[False] * (W + 1) for _ in range(n + 1)]
    hdr = ["物品 \\ 容量"] + [str(c) for c in range(W + 1)]
    frames = []

    def tbl(upto, hl_row=None, path=None):
        rows = [["i=0（不放）"] + [R.fmt(v) for v in dp[0]]]
        for i in range(1, upto + 1):
            rows.append([f"i={i} (w={objs[i - 1][0]}, v={R.fmt(objs[i - 1][1])})"] + [R.fmt(v) for v in dp[i]])
        cells = {}
        if hl_row:
            for c in range(W + 1):
                if take[hl_row][c]:
                    cells[(hl_row, c + 1)] = "c-good"
        for (i, c) in path or []:
            cells[(i, c + 1)] = "c-star"
        return R.table("DP 表 dp[i][c]：前 i 件物品、容量 c 时的最大价值", hdr, rows, cells=cells)

    frames.append(R.frame("初始化", "第 0 行：一件物品都不放，任何容量的最大价值都是 0。", tables=[tbl(0)]))
    for i in range(1, n + 1):
        w, v = objs[i - 1]
        changed = []
        for c in range(W + 1):
            dp[i][c] = dp[i - 1][c]
            if w <= c and dp[i - 1][c - w] + v > dp[i][c] + 1e-12:
                dp[i][c] = dp[i - 1][c - w] + v
                take[i][c] = True
                changed.append(c)
        ex = ""
        if changed:
            c = changed[0]
            ex = (f"例如容量 {c}：不拿 = dp[{i - 1}][{c}] = {R.fmt(dp[i - 1][c])}，拿 = dp[{i - 1}][{c - w}] + {R.fmt(v)}"
                  f" = {R.fmt(dp[i][c])}，取较大者。")
        frames.append(R.frame(f"第 {i} 行：考虑物品 {i}（重 {w}，价值 {R.fmt(v)}）",
                              f"dp[{i}][c] = max(dp[{i - 1}][c], dp[{i - 1}][c−{w}] + {R.fmt(v)})。"
                              f"绿色格表示「拿物品 {i}」更优（共 {len(changed)} 格）。{ex}",
                              tables=[tbl(i, hl_row=i)]))
    chosen, c, path = [], W, []
    for i in range(n, 0, -1):
        path.append((i, c))
        if take[i][c]:
            chosen.append(i - 1); c -= objs[i - 1][0]
    path.append((0, c))
    chosen.reverse()
    used = sum(objs[i][0] for i in chosen)
    frames.append(R.frame("回溯：找出选中的物品",
                          f"从 dp[{n}][{W}] = {R.fmt(dp[n][W])} 出发向上：若 dp[i][c] ≠ dp[i−1][c] 说明拿了物品 i，"
                          f"容量减去其重量。选中物品 {', '.join(str(i + 1) for i in chosen) or '无'}。",
                          tables=[tbl(n, path=path)]))
    return R.report(
        "optimal", headline=f"最优价值 = {R.fmt(dp[n][W])}，选 {len(chosen)} 件，总重 {used}/{W}",
        tables=[frames[-1]["tables"][0],
                R.table("选中的物品", ["序号", "重量", "价值"], [[i + 1, objs[i][0], R.fmt(objs[i][1])] for i in chosen])],
        notes=["状态转移：dp[i][c] = max(dp[i-1][c], dp[i-1][c-wᵢ] + vᵢ)。",
               "最优子结构：最优方案去掉最后一件物品，剩下的仍是对应子问题的最优方案。"],
        steps=frames)


def _stagecoach(p):
    arcs = []
    for ln in P.lines(p.get("arcs")):
        parts = [t.strip() for t in ln.replace(",", ">").split(">") if t.strip()]
        if len(parts) != 3:
            raise R.InputError(f"弧「{ln}」格式应为 起点>终点>距离。")
        arcs.append((parts[0], parts[1], P.nums(parts[2], "距离")[0]))
    if not arcs:
        raise R.InputError("没有有效的弧。")
    nodes = []
    for a, b, _ in arcs:
        for x in (a, b):
            if x not in nodes:
                nodes.append(x)
    if len(nodes) > 40:
        raise R.InputError("最多 40 个状态。")
    out = {v: [] for v in nodes}
    indeg = {v: 0 for v in nodes}
    for a, b, c in arcs:
        out[a].append((b, c)); indeg[b] += 1
    level = {v: 0 for v in nodes}
    q = deque([v for v in nodes if indeg[v] == 0])
    order, deg = [], dict(indeg)
    while q:
        u = q.popleft(); order.append(u)
        for v, _ in out[u]:
            level[v] = max(level[v], level[u] + 1)
            deg[v] -= 1
            if deg[v] == 0:
                q.append(v)
    if len(order) != len(nodes):
        raise R.InputError("弧中含有回路，多阶段决策网络必须无环。")
    starts = [v for v in nodes if indeg[v] == 0]
    ends = [v for v in nodes if not out[v]]
    if len(starts) != 1 or len(ends) != 1:
        raise R.InputError(f"需要唯一的起点和终点（当前起点 {starts}，终点 {ends}）。")
    s0, t0 = starts[0], ends[0]
    f = {t0: 0.0}
    dec = {}
    pos = GV.layered_positions(order, level)
    maxl = level[t0]
    frames = []

    def snap(title, text, cur_level=None, path=None):
        groups, subs = {}, {}
        for v in nodes:
            g = "done" if v in f else "default"
            if cur_level is not None and level[v] == cur_level:
                g = "current"
            if v == s0:
                g = "src" if g != "current" else g
            if v == t0:
                g = "sink"
            groups[v] = g
            subs[v] = ("f=" + R.fmt(f[v])) if v in f else ""
        pe = set(zip(path, path[1:])) if path else set()
        ed = []
        for a, b, c in arcs:
            if (a, b) in pe:
                cls = "path"
            elif dec.get(a) == b:
                cls = "active" if cur_level is not None and level[a] == cur_level else "mst"
            else:
                cls = "default"
            ed.append((a, b, R.fmt(c), cls))
        g = GV.positioned_graph(pos, {v: v for v in nodes}, groups, ed, directed=True, subs=subs)
        frames.append(R.frame(title, text, graph=g))

    snap("准备：划分阶段", f"按距起点的步数把状态分成 {maxl + 1} 个阶段。终点 {t0} 的 f = 0。从最后一个阶段往回算。",
         cur_level=maxl)
    for lv in range(maxl - 1, -1, -1):
        msgs = []
        for v in [x for x in order if level[x] == lv]:
            cands = [(c + f[b], b, c) for b, c in out[v] if b in f]
            if not cands:
                continue
            best = min(cands)
            f[v] = best[0]; dec[v] = best[1]
            msgs.append(f"f({v}) = min{{{', '.join(f'{R.fmt(c)}+{R.fmt(f[b])}' for _, b, c in cands)}}} = "
                        f"{R.fmt(best[0])}（去 {best[1]}）")
        snap(f"阶段 {lv + 1}：逆序递推", "；".join(msgs) + "。", cur_level=lv)
    path = [s0]
    while path[-1] != t0 and path[-1] in dec:
        path.append(dec[path[-1]])
    snap("顺序回溯：最优路线", f"从 {s0} 出发沿每个状态的最优决策前进：{' → '.join(path)}，总距离 f({s0}) = {R.fmt(f[s0])}。",
         path=path)
    rows = [[v, level[v] + 1, R.fmt(f.get(v)), dec.get(v, "—")] for v in order]
    return R.report("optimal", headline=f"最短路线 {' → '.join(path)}，总距离 = {R.fmt(f[s0])}",
                    tables=[R.table("各状态最优值", ["状态", "阶段", "f(状态)", "最优下一站"], rows)],
                    notes=["逆序递推：f(s) = min_t { c(s,t) + f(t) }，f(终点) = 0。",
                           "最优性原理：无论前面怎么走到 s，从 s 出发的剩余路线都应是最优的。"],
                    graph=frames[-1]["graph"], steps=frames)


def solve(p):
    if p.get("problem", "knapsack") == "stagecoach":
        return _stagecoach(p)
    return _knapsack(p)


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    print(solve(base)["headline"])
    print(solve(dict(base, problem="stagecoach"))["headline"])
