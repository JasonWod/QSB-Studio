"""目标规划 (Goal Programming)：优先级（preemptive / 字典序）与加权（Archimedean）两种模式。

每个软目标 a·x (op) target 引入偏差变量：a·x + d⁻ − d⁺ = target。
* 加权：一次 LP，min Σ wᵢ·(被罚的偏差)
* 优先级：P1 → P2 → … 逐级求解；每级在「不让更高优先级变差」的附加约束下最小化本级偏差
演示帧：逐级显示本级目标、偏差与决策；2 变量时画出目标线与当前解。
"""
from . import lp as _lp
from . import parse as P
from . import report as R

SPEC = {
    "desc": "目标规划：多个软目标各带不足 d⁻ / 超出 d⁺ 两个偏差变量。优先级模式按 P1、P2… 逐级最小化偏差，"
            "上一级的达成度不许被下一级破坏；加权模式把所有偏差按权重相加一次求解。硬约束必须严格满足。",
    "form": [
        {"id": "mode", "type": "select", "label": "求解模式", "value": "preemptive",
         "options": [{"v": "preemptive", "t": "优先级（preemptive）"}, {"v": "weighted", "t": "加权（Archimedean）"}]},
        {"id": "hard", "type": "textarea", "label": "硬约束（每行 a1,a2,... <= b；可留空）", "rows": 3,
         "value": "2, 1 <= 11"},
        {"id": "goals", "type": "textarea", "rows": 4,
         "label": "目标（每行 系数 关系 目标值 : 罚哪边 : 优先级 : 权重）",
         "value": "1, -1 <= 0 : over : P1\n1, 2 = 10 : both : P2\n8, 10 >= 62 : under : P3"},
    ],
}


def _parse_goal(ln, n):
    parts = [s.strip() for s in ln.split(":")]
    coef, op, target = P.constraint(parts[0], n, "目标")
    pen = (parts[1] if len(parts) > 1 and parts[1] else {"le": "over", "ge": "under", "eq": "both"}[op]).lower()
    if pen not in ("under", "over", "both"):
        raise R.InputError(f"目标「{ln}」的罚项应为 under（罚不足）/ over（罚超出）/ both（两边都罚）。")
    pr = parts[2].upper().lstrip("P") if len(parts) > 2 and parts[2] else "1"
    try:
        prio = int(pr)
    except ValueError:
        raise R.InputError(f"目标「{ln}」的优先级应写成 P1、P2…") from None
    w = P.nums(parts[3], "权重")[0] if len(parts) > 3 and parts[3] else 1.0
    if w < 0:
        raise R.InputError("权重不能为负。")
    return coef, op, target, pen, prio, w


def solve(p):
    mode = p.get("mode", "preemptive")
    goals_raw = P.lines(p.get("goals"))
    if not goals_raw:
        raise R.InputError("至少需要一个目标。格式：a1,a2 >= 目标值 : under : P1")
    first = P.constraint(goals_raw[0].split(":")[0], None, "目标")
    n = len(first[0])
    goals = [_parse_goal(ln, n) for ln in goals_raw]
    hard = [P.constraint(ln, n, "硬约束") for ln in P.lines(p.get("hard"))]
    G = len(goals)
    ncol = n + 2 * G
    names = [f"x{i + 1}" for i in range(n)]
    for i in range(G):
        names += [f"d-{i + 1}", f"d+{i + 1}"]

    A, b, s = [], [], []
    for coef, op, rhs in hard:
        A.append(coef + [0.0] * 2 * G); b.append(rhs); s.append(op)
    for i, (coef, _op, target, _pen, _pr, _w) in enumerate(goals):
        row = coef + [0.0] * 2 * G
        row[n + 2 * i] = 1.0; row[n + 2 * i + 1] = -1.0
        A.append(row); b.append(target); s.append("eq")

    def penal(i):
        pen, w = goals[i][3], goals[i][5]
        cols = []
        if pen in ("under", "both"):
            cols.append(n + 2 * i)
        if pen in ("over", "both"):
            cols.append(n + 2 * i + 1)
        return [(col, w) for col in cols]

    levels = sorted({g[4] for g in goals}) if mode == "preemptive" else [None]
    frames, achieved = [], []
    extraA, extrab, extras = [], [], []
    res = None
    for lv in levels:
        idx = [i for i in range(G) if lv is None or goals[i][4] == lv]
        cobj = [0.0] * ncol
        for i in idx:
            for col, w in penal(i):
                cobj[col] += w
        res = _lp.solve_lp("min", cobj, A + extraA, b + extrab, s + extras, names)
        if res["status"] != "optimal":
            return R.report(res["status"], headline="硬约束不可行，目标规划无解。" if res["status"] == "infeasible"
                            else f"求解状态：{res['status']}", steps=frames)
        val = res["objective"]
        achieved.append((lv, val))
        if lv is not None:     # 锁定本级达成度，供下一级使用
            extraA.append(cobj); extrab.append(val + 1e-7); extras.append("le")
        sol = res["solution"]
        x = [float(sol[f"x{k + 1}"]) for k in range(n)]
        dev_rows = []
        cells = {}
        for i in range(G):
            dm, dp = float(sol[f"d-{i + 1}"]), float(sol[f"d+{i + 1}"])
            ok = all(float(sol[names[col]]) < 1e-7 for col, _ in penal(i))
            dev_rows.append([f"目标{i + 1}", f"P{goals[i][4]}", goals[i][3], R.fmt(dm), R.fmt(dp),
                             "达成" if ok else "未完全达成"])
            if i in idx:
                cells[(i, 0)] = "c-cur"
            cells[(i, 5)] = "c-good" if ok else "c-bad"
        tb = R.table("各目标偏差", ["目标", "优先级", "罚", "d⁻ 不足", "d⁺ 超出", "状态"], dev_rows, cells=cells)
        ch = None
        if n == 2:
            ch = {"type": "plane", "use": "plane", "pts": [[round(x[0], 6), round(x[1], 6)]],
                  "active": [len(hard) + i for i in idx], "label": f"x=({R.fmt(x[0])}, {R.fmt(x[1])})"}
        if lv is None:
            title = "加权模式：一次求解"
            text = f"最小化所有被罚偏差的加权和，得到 Σw·d = {R.fmt(val)}，决策 x = ({', '.join(R.fmt(v) for v in x)})。"
        else:
            gl = "、".join(f"目标{i + 1}" for i in idx)
            title = f"第 {levels.index(lv) + 1} 级：P{lv}"
            text = (f"在保持更高优先级达成度不变的前提下，最小化 P{lv} 级（{gl}）的偏差，得到 {R.fmt(val)}"
                    f"{'（完全达成）' if val < 1e-7 else ''}。当前决策 x = ({', '.join(R.fmt(v) for v in x)})。")
        frames.append(R.frame(title, text, tables=[tb], chart=ch))

    sol = res["solution"]
    x = [float(sol[f"x{k + 1}"]) for k in range(n)]
    base = None
    if n == 2:
        lines = [{"a1": h[0][0], "a2": h[0][1], "b": h[2], "label": f"硬约束{k + 1}", "kind": "hard"}
                 for k, h in enumerate(hard)]
        lines += [{"a1": g[0][0], "a2": g[0][1], "b": g[2], "label": f"目标{k + 1}", "kind": "goal"}
                  for k, g in enumerate(goals)]
        pts = [abs(v) for h in hard + [(g[0], g[1], g[2]) for g in goals] for v in
               ([h[2] / h[0][0]] if h[0][0] else []) + ([h[2] / h[0][1]] if h[0][1] else [])]
        hi = max([max(x) * 1.3, 1.0] + pts) * 1.1
        base = {"type": "plane", "xr": [0, hi], "yr": [0, hi], "grid": None, "lines": lines,
                "xlabel": "x1", "ylabel": "x2", "title": "硬约束（实线）与目标线（虚线）"}
    summary = [[("P" + str(lv)) if lv is not None else "加权合计", R.fmt(v), "达成" if v < 1e-7 else "有偏差"]
               for lv, v in achieved]
    dev = frames[-1]["tables"][0]
    return R.report(
        "optimal",
        headline=f"决策 {' '.join(f'x{i + 1}={R.fmt(x[i])}' for i in range(n))}；"
                 + "，".join(f"{r[0]} 偏差 {r[1]}" for r in summary),
        tables=[R.table("各优先级达成情况" if mode == "preemptive" else "加权偏差", ["级别", "最小偏差", "状态"], summary),
                dev, R.table("决策变量", ["变量", "值"], [[f"x{i + 1}", R.fmt(x[i])] for i in range(n)])],
        steps=frames, shared={"plane": base} if base else None,
        chart=dict(base, pts=[[x[0], x[1]]], label="最终解") if base else None,
        notes=["每个目标 a·x + d⁻ − d⁺ = target；under 罚 d⁻（不足），over 罚 d⁺（超出），both 两者都罚。",
               "优先级模式：高优先级目标「绝对优先」，低优先级只能在不损害高优先级的解中挑最好的。"
               if mode == "preemptive" else "加权模式：权重越大的目标越被重视，但各目标可以相互抵偿。"])


if __name__ == "__main__":
    r = solve({"mode": "preemptive", "hard": "2,1 <= 11",
               "goals": "1,-1 <= 0 : over : P1\n1,2 = 10 : both : P2\n8,10 >= 62 : under : P3"})
    print(r["headline"])
    for f in r["steps"]:
        print(" ", f["title"], f["text"])
