"""整数线性规划：分支定界 (branch & bound)。LP 松弛复用大M单纯形，分数变量逐个分支。"""
import math
from . import report as R
from . import lp as _lp

SPEC = {
    "desc": "整数线性规划 (ILP)：目标与约束线性、变量取整数。分支定界：每个节点解 LP 松弛（大M单纯形）得 bound，"
            "对分数变量分支 x<=floor / x>=ceil，按 bound 剪枝。给出最优整数解与搜索节点数。",
    "form": [
        {"id": "obj", "type": "select", "label": "方向", "value": "max",
         "options": [{"v": "max", "t": "最大化 max"}, {"v": "min", "t": "最小化 min"}]},
        {"id": "c", "type": "list", "label": "目标系数 c（逗号分隔）", "value": "5, 4"},
        {"id": "constraints", "type": "textarea", "label": "约束（每行 a1,a2,...,an <op> b；op 用 <= / >= / =）",
         "value": "6,4 <= 24\n3,4 <= 16"},
        {"id": "max_nodes", "type": "int", "label": "最大搜索节点数", "value": "400"},
    ],
}


def _lines(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    obj = p.get("obj", "max")
    c = [float(x) for x in (p["c"] if isinstance(p["c"], list) else str(p["c"]).replace(",", " ").split())]
    n = len(c)
    names = [f"x{i+1}" for i in range(n)]
    A, b, senses = [], [], []
    for ln in _lines(p["constraints"]):
        if "<=" in ln:
            lhs, op, rhs = ln.partition("<=")
        elif ">=" in ln:
            lhs, op, rhs = ln.partition(">=")
        elif "=" in ln:
            lhs, op, rhs = ln.partition("=")
        else:
            continue
        coef = [float(x) for x in lhs.replace(",", " ").split()]
        try:
            bval = float(rhs.strip())
        except ValueError:
            continue
        op = {"<=": "le", ">=": "ge", "=": "eq"}[op.strip()]
        if len(coef) != n:
            continue
        A.append(coef); b.append(bval); senses.append(op)
    if n == 0 or not A:
        return R.error("需要至少一个目标系数和一个约束。")
    c_use = c if obj == "max" else [-x for x in c]
    best = None; bestobj = None; nodes = 0; maxn = int(p.get("max_nodes", 400))
    stack = [(A, b, senses)]
    first_lb = None
    while stack and nodes < maxn:
        A, b, senses = stack.pop(); nodes += 1
        r = _lp.solve_lp("max", c_use, A, b, senses, names)
        if r["status"] != "optimal":
            continue
        x = [float(r["solution"][names[k]]) for k in range(n)]
        bound = r["objective"]  # c_use 空间（max 的 -c 或 c）
        if all(abs(x[k] - round(x[k])) < 1e-5 for k in range(n)):
            val = bound if obj == "max" else -bound
            better = (bestobj is None) or (val > bestobj if obj == "max" else val < bestobj)
            if better:
                bestobj = val; best = [int(round(v)) for v in x]
        else:
            if bestobj is not None:
                boundval = bound if obj == "max" else -bound
                if (obj == "max" and bound <= bestobj + 1e-9) or (obj == "min" and -bound >= bestobj - 1e-9):
                    continue
            k = max(range(n), key=lambda k: abs(x[k] - round(x[k])))
            fl = math.floor(x[k] + 1e-9); ce = math.ceil(x[k] - 1e-9)
            row = [0.0] * n; row[k] = 1.0
            stack.append((A + [row], b + [fl], senses + ["le"]))
            stack.append((A + [row], b + [ce], senses + ["ge"]))
    if best is None:
        return R.report("infeasible",
                        headline=f"未找到整数可行解（搜索 {nodes} 个节点，上限 {maxn}）。")
    if first_lb is None:
        pass
    return R.report(
        "optimal",
        headline=f"最优整数解 {' '.join(f'{names[k]}={best[k]}' for k in range(n))}，目标值 = {R.fmt(bestobj)}",
        tables=[R.table("分支定界摘要", ["项", "值"],
                        [["决策变量", ", ".join(f"{names[k]}={best[k]}" for k in range(n))],
                         ["目标值 (最优整数)", R.fmt(bestobj)],
                         ["搜索节点数", f"{nodes} / 上限 {maxn}"]])],
        notes=[
            "每个节点解 LP 松弛得到 bound；对分数变量分支 x<=floor / x>=ceil。",
            "LP bound 已不优于当前最优整数解的节点被剪枝。",
        ])


if __name__ == "__main__":
    print(solve({"obj": "max", "c": "5, 4", "constraints": "6,4 <= 24\n3,4 <= 16"})["headline"])
