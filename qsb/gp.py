"""目标规划 (Goal Programming)：多个目标各带偏差变量，最小化加权偏差。化简为 LP 用单纯形求解。"""
from . import report as R
from . import lp as _lp

SPEC = {
    "desc": "目标规划：多个『软目标』，每个目标允许正/负偏差 d⁺/d⁻，最小化加权偏差之和，同时满足硬约束。"
            "化为线性规划（偏差变量）用单纯形求解。示例：利润≥10（罚不足 d⁻）、成本≤12（罚超出 d⁺）。",
    "form": [
        {"id": "hard", "type": "textarea", "label": "硬约束（每行 a1,a2,... <= b；可留空）",
         "value": "1,1 <= 10"},
        {"id": "goals", "type": "textarea",
         "label": "目标（每行 a1,a2,... <op> target : under|over）",
         "value": "1,2 >= 10 : under\n3,1 <= 12 : over"},
    ],
}


def _lines(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    hard = _lines(p.get("hard", ""))
    goals = _lines(p.get("goals", ""))
    if not goals:
        return R.error("至少需要一个目标。格式：a1,a2 <op> target : under|over")
    # 解析目标
    parsed = []
    n = None
    for g in goals:
        head, _, side = g.partition(":")
        pen = side.strip().split()[-1] if side.strip() else "under"
        if "<=" in head:
            lhs, op, rhs = head.partition("<=")
        elif ">=" in head:
            lhs, op, rhs = head.partition(">=")
        else:
            lhs, op, rhs = head.partition("=")
        coef = [float(x) for x in lhs.replace(",", " ").split()]
        target = float(rhs.strip())
        op = {"<=": "le", ">=": "ge", "=": "eq"}[op.strip()]
        if n is None:
            n = len(coef)
        parsed.append((coef, op, target, pen))
    n = n or 1
    # 变量布局: x[0..n-1], 然后每个目标 d- , d+
    xnames = [f"x{i+1}" for i in range(n)]
    cols = n
    dev = []   # 每个目标 (dminus_col, dplus_col)
    A = []; b = []; senses = []; c = [0.0] * (cols + 2 * len(parsed))
    # 硬约束
    for h in hard:
        if "<=" in h:
            lhs, op, rhs = h.partition("<=")
        elif ">=" in h:
            lhs, op, rhs = h.partition(">=")
        else:
            continue
        coef = [float(x) for x in lhs.replace(",", " ").split()]
        if len(coef) == n:
            row = [0.0] * (cols + 2 * len(parsed))
            for k in range(n):
                row[k] = coef[k]
            A.append(row); b.append(float(rhs.strip())); senses.append({"<=": "le", ">=": "ge"}[op.strip()])
    # 目标约束: a·x + d- - d+ = target
    for i, (coef, op, target, pen) in enumerate(parsed):
        dminus = cols + 2 * i; dplus = dminus + 1
        dev.append((dminus, dplus))
        row = [0.0] * (cols + 2 * len(parsed))
        for k in range(n):
            row[k] = coef[k]
        row[dminus] = 1.0; row[dplus] = -1.0
        A.append(row); b.append(target); senses.append("eq")
        if pen == "under":
            c[dminus] = 1.0
        elif pen == "over":
            c[dplus] = 1.0
    names = xnames + [f"d{'-+'}{'-+'}[i]" for i in range(0)] or xnames
    names = xnames + []
    for i in range(len(parsed)):
        names += [f"d-{i+1}", f"d+{i+1}"]
    r = _lp.solve_lp("min", c, A, b, senses, names)
    if r["status"] != "optimal":
        return R.report(r["status"], headline=f"目标规划求解状态：{r['status']}")
    sol = r["solution"]
    xvals = [float(sol[f"x{i+1}"]) for i in range(n)]
    dvals = []
    for i in range(len(parsed)):
        dvals.append((float(sol.get(f"d-{i+1}", 0)), float(sol.get(f"d+{i+1}", 0))))
    total = r["objective"]
    return R.report(
        "optimal",
        headline=f"加权偏差最小 = {R.fmt(total)}，决策 {' '.join(f'x{i+1}={R.fmt(xvals[i])}' for i in range(n))}",
        tables=[R.table("各目标的偏差 (d⁻ 不足, d⁺ 超出)", ["目标", "d⁻ (不足)", "d⁺ (超出)"],
                        [[f"目标{i+1}", R.fmt(dvals[i][0]), R.fmt(dvals[i][1])] for i in range(len(parsed))])],
        notes=[
            "每个目标 a·x + d⁻ - d⁺ = target；罚 under 取 d⁻，罚 over 取 d⁺。",
            "最小化 Σ 加权偏差；用单纯形求解化简后的线性规划。",
        ])


if __name__ == "__main__":
    print(solve({"hard": "1,1 <= 10", "goals": "1,2 >= 10 : under\n3,1 <= 12 : over"})["headline"])
