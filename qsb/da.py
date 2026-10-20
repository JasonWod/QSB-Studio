"""决策分析：风险型决策。期望货币值 EMV + 最大最小(保守) + 最小遗憾(机会损失)。"""
from . import report as R

SPEC = {
    "desc": "风险型决策分析：给定若干方案、各自然状态的概率与收益矩阵，计算每个方案的期望货币值 EMV，"
            "并给出 EMV(期望值)、最大最小(maximin, 保守)、最小遗憾(minimax regret, 机会损失) 三种准则下的最优方案。",
    "form": [
        {"id": "alts", "type": "textarea", "label": "方案（每行一个）", "value": "大规模投资\n小规模投资\n不投资"},
        {"id": "states", "type": "textarea", "label": "自然状态（每行 名称>概率）", "value": "市场好>0.3\n市场平>0.5\n市场差>0.2"},
        {"id": "payoff", "type": "textarea", "label": "收益矩阵（每行=一个方案，逗号分隔各状态收益）",
         "value": "100,50,20\n40,30,10\n0,0,0"},
    ],
}


def _lines(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    alts = _lines(p["alts"])
    states = []
    for s in _lines(p["states"]):
        parts = [t for t in s.replace(">", " ").split() if t]
        if len(parts) >= 2:
            states.append((parts[0], float(parts[1])))
    if not states:
        return R.error("无有效状态。格式：每行 名称>概率。")
    P = [pr for _, pr in states]
    S = sum(P)
    if abs(S - 1) > 0.02:
        P = [x / S for x in P]
    mat = []
    for row in _lines(p["payoff"]):
        vals = [float(x) for x in row.replace(",", " ").split()]
        if vals:
            mat.append(vals)
    if not mat:
        return R.error("无收益矩阵。每行=一个方案在各状态下的收益（逗号分隔）。")
    m = len(mat); ns = len(states)
    emv = [sum(mat[i][j] * P[j] for j in range(min(ns, len(mat[i])))) for i in range(m)]
    i_emv = max(range(m), key=lambda i: emv[i])
    minim = [min(row) for row in mat]
    i_maximin = max(range(m), key=lambda i: minim[i])
    best_each = [max(mat[i][j] for i in range(m)) for j in range(ns)]
    regret = [[best_each[j] - mat[i][j] for j in range(ns)] for i in range(m)]
    maxreg = [max(row) for row in regret]
    i_minimax = min(range(m), key=lambda i: maxreg[i])
    name = lambda i: (alts[i] if i < len(alts) and alts[i] else f"方案{i+1}")
    return R.report(
        "optimal",
        headline=f"EMV 最优：{name(i_emv)} (EMV={R.fmt(emv[i_emv])})；保守 {name(i_maximin)}；最小遗憾 {name(i_minimax)}",
        tables=[
            R.table("收益矩阵（EMV）", ["方案"] + [st[0] for st in states] + ["EMV"],
                    [[name(i)] + [R.fmt(mat[i][j]) for j in range(ns)] + [R.fmt(emv[i])] for i in range(m)]),
            R.table("各准则最优", ["准则", "最优方案", "值"],
                    [["EMV (期望值)", name(i_emv), R.fmt(emv[i_emv])],
                     ["最大最小 maximin (保守)", name(i_maximin), R.fmt(minim[i_maximin])],
                     ["最小遗憾 minimax regret", name(i_minimax), R.fmt(maxreg[i_minimax])]]),
        ],
        notes=[
            "EMV = Σ 概率×收益；期望值准则选 EMV 最大者。",
            "maximin：每方案取最差收益再选最大（最保守）。",
            "minimax regret：构造机会损失矩阵，选最大遗憾最小者（折中）。",
        ])


if __name__ == "__main__":
    print(solve({"alts": "大\n小\n不投", "states": "好>0.3\n平>0.5\n差>0.2",
                 "payoff": "100,50,20\n40,30,10\n0,0,0"})["headline"])
