"""决策分析：风险/不确定型决策准则、贝叶斯修正（含 EVSI）、二人零和矩阵博弈。

* 风险型：EMV、最大最小（悲观）、最大最大（乐观）、Hurwicz 折中、Laplace 等可能、最小最大遗憾、EVPI
* 贝叶斯：先验 × 似然 → 联合概率 → 各信号的后验 → 每个信号下的最优方案 → 有信息时的期望值与 EVSI
* 矩阵博弈：先找鞍点（纯策略）；无鞍点时把收益平移为正，用 LP 求双方混合策略与对策值
"""
from . import lp as _lp
from . import parse as P
from . import report as R

SPEC = {
    "desc": "决策分析：风险型决策（EMV / 悲观 / 乐观 / 折中 / 等可能 / 最小遗憾 / EVPI）；贝叶斯决策（用调查信号修正先验，"
            "计算样本信息价值 EVSI）；二人零和博弈（鞍点或混合策略）。",
    "form": [
        {"id": "method", "type": "select", "label": "类型", "value": "risk",
         "options": [{"v": "risk", "t": "风险/不确定型决策"}, {"v": "bayes", "t": "贝叶斯决策（信息价值）"},
                     {"v": "game", "t": "二人零和博弈"}]},
        {"id": "alts", "type": "textarea", "label": "方案（每行一个；博弈时为甲方策略）", "rows": 3,
         "value": "大规模投资\n小规模投资\n不投资"},
        {"id": "states", "type": "textarea", "label": "自然状态（每行 名称>先验概率；博弈时为乙方策略名）", "rows": 3,
         "value": "市场好>0.3\n市场平>0.5\n市场差>0.2"},
        {"id": "payoff", "type": "matrix", "label": "收益矩阵（行=方案，列=状态）", "rows": 3,
         "value": "100, 50, -120\n40, 30, 10\n0, 0, 0"},
        {"id": "hurwicz", "type": "float", "label": "Hurwicz 乐观系数 α（0~1）", "value": "0.6"},
        {"id": "signals", "type": "textarea", "label": "调查信号似然（贝叶斯用，每行 信号名>P(信号|状态1),P(…|状态2),…）",
         "rows": 3, "value": "乐观报告>0.7,0.3,0.1\n悲观报告>0.3,0.7,0.9"},
    ],
}


def _states(p, need_prob=True):
    out = []
    for ln in P.lines(p.get("states")):
        if ">" in ln:
            nm, _, pr = ln.partition(">")
            out.append((nm.strip(), P.nums(pr, "概率")[0]))
        else:
            out.append((ln.strip(), None))
    return out


def _risk(p, alts, st, M):
    m, k = len(M), len(st)
    probs = [s[1] for s in st]
    if any(x is None for x in probs):
        raise R.InputError("风险型决策需要每个状态的概率，格式「名称>概率」。")
    if any(x < 0 for x in probs) or abs(sum(probs) - 1) > 1e-6:
        raise R.InputError(f"状态概率须非负且和为 1（当前和为 {R.fmt(sum(probs))}）。")
    a = P.num(p, "hurwicz", 0.6, "Hurwicz 系数", 0, 1)
    snames = [s[0] for s in st]
    hdr = ["方案"] + snames
    frames = []
    emv = [sum(M[i][j] * probs[j] for j in range(k)) for i in range(m)]
    rows = [[alts[i]] + [R.fmt(v) for v in M[i]] + [R.fmt(emv[i])] for i in range(m)]
    ib = max(range(m), key=lambda i: emv[i])
    frames.append(R.frame("第 1 步：期望货币值 EMV",
                          "EMV(方案) = Σ P(状态)×收益。" + "；".join(
                              f"{alts[i]}：" + " + ".join(f"{R.fmt(probs[j])}×{R.fmt(M[i][j])}" for j in range(k))
                              + f" = {R.fmt(emv[i])}" for i in range(m)) + f"。EMV 最大的是「{alts[ib]}」。",
                          tables=[R.table("收益矩阵与 EMV", hdr + ["EMV"], rows, cells={(ib, k + 1): "c-good"})]))
    mins, maxs = [min(r) for r in M], [max(r) for r in M]
    hur = [a * maxs[i] + (1 - a) * mins[i] for i in range(m)]
    lap = [sum(r) / k for r in M]
    crit = [("悲观（最大最小）", mins), ("乐观（最大最大）", maxs), (f"折中 Hurwicz α={R.fmt(a)}", hur),
            ("等可能 Laplace", lap)]
    rows = [[alts[i]] + [R.fmt(c[1][i]) for c in crit] for i in range(m)]
    cells = {(max(range(m), key=lambda i: c[1][i]), j + 1): "c-good" for j, c in enumerate(crit)}
    frames.append(R.frame("第 2 步：不确定型准则",
                          "不用概率时的四种态度：悲观者看每个方案最差结果再取最大；乐观者看最好结果；"
                          f"折中 = α×最好 + (1−α)×最差；等可能 = 各状态收益的平均。",
                          tables=[R.table("各准则下的评价值（绿=该准则最优）", ["方案"] + [c[0] for c in crit], rows, cells=cells)]))
    best_col = [max(M[i][j] for i in range(m)) for j in range(k)]
    reg = [[best_col[j] - M[i][j] for j in range(k)] for i in range(m)]
    mreg = [max(r) for r in reg]
    ir = min(range(m), key=lambda i: mreg[i])
    frames.append(R.frame("第 3 步：最小最大遗憾",
                          "遗憾值 = 该状态下最好收益 − 本方案收益（「早知道就……」的损失）。每个方案取最大遗憾，再选最小者："
                          f"「{alts[ir]}」（最大遗憾 {R.fmt(mreg[ir])}）。",
                          tables=[R.table("遗憾（机会损失）矩阵", hdr + ["最大遗憾"],
                                          [[alts[i]] + [R.fmt(v) for v in reg[i]] + [R.fmt(mreg[i])] for i in range(m)],
                                          cells={(ir, k + 1): "c-good"})]))
    ev_pi = sum(probs[j] * best_col[j] for j in range(k))
    evpi = ev_pi - emv[ib]
    frames.append(R.frame("第 4 步：完全信息价值 EVPI",
                          "如果事先确知哪个状态发生，每次都能选该状态下最好的方案："
                          + " + ".join(f"{R.fmt(probs[j])}×{R.fmt(best_col[j])}" for j in range(k))
                          + f" = {R.fmt(ev_pi)}。EVPI = {R.fmt(ev_pi)} − 最大 EMV {R.fmt(emv[ib])} = {R.fmt(evpi)}，"
                          "这是为获取信息最多愿付的代价。"))
    summary = [["期望值 EMV", alts[ib], R.fmt(emv[ib])]] + \
              [[c[0], alts[max(range(m), key=lambda i: c[1][i])], R.fmt(max(c[1]))] for c in crit] + \
              [["最小最大遗憾", alts[ir], R.fmt(mreg[ir])], ["完全信息价值 EVPI", "—", R.fmt(evpi)]]
    return R.report("optimal", headline=f"EMV 最优：{alts[ib]}（EMV = {R.fmt(emv[ib])}），EVPI = {R.fmt(evpi)}",
                    tables=[R.table("各准则最优方案", ["准则", "最优方案", "值"], summary),
                            frames[0]["tables"][0], frames[2]["tables"][0]],
                    notes=["EMV 适合可重复、风险中性的决策；悲观/乐观/折中反映决策者对风险的不同态度。",
                           "EVPI 是任何调查/预测信息价值的上限。"], steps=frames)


def _bayes(p, alts, st, M):
    m, k = len(M), len(st)
    prior = [s[1] for s in st]
    if any(x is None for x in prior) or abs(sum(prior) - 1) > 1e-6:
        raise R.InputError("贝叶斯决策需要先验概率，格式「名称>概率」，且和为 1。")
    sig = []
    for ln in P.lines(p.get("signals")):
        nm, _, rest = ln.partition(">")
        lk = P.nums(rest, "似然")
        if len(lk) != k:
            raise R.InputError(f"信号「{nm}」应给出 {k} 个似然 P(信号|状态)。")
        sig.append((nm.strip(), lk))
    if len(sig) < 2:
        raise R.InputError("至少需要两个调查信号。")
    for j in range(k):
        tot = sum(s[1][j] for s in sig)
        if abs(tot - 1) > 1e-6:
            raise R.InputError(f"对状态「{st[j][0]}」，各信号似然之和应为 1（当前 {R.fmt(tot)}）。")
    snames = [s[0] for s in st]
    frames = []
    emv0 = [sum(M[i][j] * prior[j] for j in range(k)) for i in range(m)]
    i0 = max(range(m), key=lambda i: emv0[i])
    frames.append(R.frame("第 1 步：只用先验概率决策",
                          f"不做调查时按先验算 EMV：" + "，".join(f"{alts[i]} {R.fmt(emv0[i])}" for i in range(m))
                          + f"。最优「{alts[i0]}」，EMV = {R.fmt(emv0[i0])}。"))
    joint = [[s[1][j] * prior[j] for j in range(k)] for s in sig]
    marg = [sum(r) for r in joint]
    frames.append(R.frame("第 2 步：联合概率与信号概率",
                          "P(信号, 状态) = P(信号|状态) × P(状态)；按行求和得各信号出现的概率 P(信号)。",
                          tables=[R.table("联合概率", ["信号"] + snames + ["P(信号)"],
                                          [[sig[t][0]] + [R.fmt(v) for v in joint[t]] + [R.fmt(marg[t])]
                                           for t in range(len(sig))])]))
    post = [[joint[t][j] / marg[t] if marg[t] > 0 else 0.0 for j in range(k)] for t in range(len(sig))]
    frames.append(R.frame("第 3 步：贝叶斯公式求后验",
                          "P(状态|信号) = P(信号, 状态) / P(信号)。调查结果改变了我们对各状态的判断。",
                          tables=[R.table("后验概率", ["信号"] + snames, [[sig[t][0]] + [R.fmt(v) for v in post[t]]
                                                                         for t in range(len(sig))])]))
    best = []
    rows = []
    for t in range(len(sig)):
        e = [sum(M[i][j] * post[t][j] for j in range(k)) for i in range(m)]
        bi = max(range(m), key=lambda i: e[i])
        best.append((bi, e[bi]))
        rows.append([sig[t][0]] + [R.fmt(v) for v in e] + [alts[bi]])
    cells = {(t, best[t][0] + 1): "c-good" for t in range(len(sig))}
    ev_si = sum(marg[t] * best[t][1] for t in range(len(sig)))
    evsi = ev_si - emv0[i0]
    frames.append(R.frame("第 4 步：每个信号下的最优方案",
                          "用后验概率重新算各方案 EMV：" + "；".join(f"收到「{sig[t][0]}」选「{alts[best[t][0]]}」"
                                                            for t in range(len(sig))) + "。",
                          tables=[R.table("后验 EMV", ["信号"] + alts + ["最优方案"], rows, cells=cells)]))
    frames.append(R.frame("第 5 步：样本信息价值 EVSI",
                          "有调查时的期望收益 = Σ P(信号)×该信号下最优 EMV = "
                          + " + ".join(f"{R.fmt(marg[t])}×{R.fmt(best[t][1])}" for t in range(len(sig)))
                          + f" = {R.fmt(ev_si)}。EVSI = {R.fmt(ev_si)} − {R.fmt(emv0[i0])} = {R.fmt(evsi)}；"
                          "调查费用低于 EVSI 才值得做。"))
    return R.report("optimal", headline=f"EVSI = {R.fmt(evsi)}；" + "，".join(
        f"「{sig[t][0]}」→{alts[best[t][0]]}" for t in range(len(sig))),
                    tables=[frames[2]["tables"][0], frames[3]["tables"][0],
                            R.table("信息价值", ["项", "值"], [["无信息最优 EMV", R.fmt(emv0[i0])],
                                                          ["有调查信息的期望值", R.fmt(ev_si)], ["EVSI", R.fmt(evsi)]])],
                    notes=["后验 ∝ 似然 × 先验。", "EVSI ≤ EVPI；两者之比称为信息效率。"], steps=frames)


def _game(p, alts, st, M):
    m, k = len(M), len(st)
    cn = [s[0] for s in st]
    frames = []
    rmin = [min(r) for r in M]
    cmax = [max(M[i][j] for i in range(m)) for j in range(k)]
    lo, hi = max(rmin), min(cmax)
    rows = [[alts[i]] + [R.fmt(v) for v in M[i]] + [R.fmt(rmin[i])] for i in range(m)]
    rows.append(["列最大"] + [R.fmt(v) for v in cmax] + [""])
    i_ = rmin.index(lo); j_ = cmax.index(hi)
    cells = {(i_, k + 1): "c-good", (m, j_ + 1): "c-good"}
    frames.append(R.frame("第 1 步：找鞍点",
                          f"甲（行）保守地取各行最小值的最大者 max min = {R.fmt(lo)}；乙（列）取各列最大值的最小者 "
                          f"min max = {R.fmt(hi)}。" + ("两者相等，存在鞍点！" if abs(lo - hi) < 1e-12 else
                                                    "两者不等，没有鞍点，双方都应采用混合策略。"),
                          tables=[R.table("支付矩阵（甲的收益）", ["甲 \\ 乙"] + cn + ["行最小"], rows, cells=cells)]))
    if abs(lo - hi) < 1e-12:
        frames.append(R.frame("结论：纯策略解", f"甲用「{alts[i_]}」，乙用「{cn[j_]}」，对策值 V = {R.fmt(lo)}。"))
        return R.report("optimal", headline=f"存在鞍点：甲「{alts[i_]}」，乙「{cn[j_]}」，对策值 = {R.fmt(lo)}",
                        tables=[frames[0]["tables"][0]], steps=frames,
                        notes=["鞍点：既是所在行的最小值，又是所在列的最大值。"])
    shift = 1 - min(min(r) for r in M) if min(min(r) for r in M) <= 0 else 0.0
    A = [[M[i][j] + shift for j in range(k)] for i in range(m)]
    # 甲：min Σ x_i  s.t. Σ_i A_ij x_i ≥ 1 ；V = 1/Σx
    r1 = _lp.solve_lp("min", [1.0] * m, [[A[i][j] for i in range(m)] for j in range(k)], [1.0] * k, ["ge"] * k,
                      [f"x{i}" for i in range(m)])
    r2 = _lp.solve_lp("max", [1.0] * k, A, [1.0] * m, ["le"] * m, [f"y{j}" for j in range(k)])
    sx = r1["objective"]; V = 1.0 / sx - shift
    px = [float(r1["solution"][f"x{i}"]) / sx for i in range(m)]
    sy = r2["objective"]
    py = [float(r2["solution"][f"y{j}"]) / sy for j in range(k)]
    frames.append(R.frame("第 2 步：化为线性规划",
                          (f"所有收益加 {R.fmt(shift)} 使其为正（不改变最优策略）。" if shift else "")
                          + "甲：min Σxᵢ s.t. Σᵢ aᵢⱼxᵢ ≥ 1；乙：max Σyⱼ s.t. Σⱼ aᵢⱼyⱼ ≤ 1（互为对偶）。"
                          f"解得对策值 V = 1/Σx − {R.fmt(shift)} = {R.fmt(V)}。"))
    frames.append(R.frame("结论：混合策略",
                          "甲以概率 " + "，".join(f"{alts[i]} {R.fmt(px[i])}" for i in range(m))
                          + " 随机出招；乙以概率 " + "，".join(f"{cn[j]} {R.fmt(py[j])}" for j in range(k))
                          + f"。此时甲的期望收益稳定在 V = {R.fmt(V)}，谁单方面改变都得不到好处。"))
    return R.report("optimal", headline=f"混合策略对策值 V = {R.fmt(V)}",
                    tables=[frames[0]["tables"][0],
                            R.table("甲的最优混合策略", ["策略", "概率"], [[alts[i], R.fmt(px[i])] for i in range(m)]),
                            R.table("乙的最优混合策略", ["策略", "概率"], [[cn[j], R.fmt(py[j])] for j in range(k)])],
                    notes=["极小极大定理：任何有限二人零和博弈在混合策略下都有解。", "甲、乙的 LP 互为对偶，对策值相同。"],
                    steps=frames)


def solve(p):
    method = p.get("method", "risk")
    alts = P.lines(p.get("alts"))
    st = _states(p)
    M = P.matrix(p.get("payoff"), "收益矩阵")
    if not M:
        raise R.InputError("请输入收益矩阵（每行一个方案，逗号分隔各状态收益）。")
    m, k = len(M), len(M[0])
    if any(len(r) != k for r in M):
        raise R.InputError("收益矩阵每行的元素个数必须相同。")
    if m > 15 or k > 15:
        raise R.InputError("最多 15 个方案、15 个状态。")
    alts = (alts + [f"方案{i + 1}" for i in range(len(alts), m)])[:m]
    st = (st + [(f"状态{j + 1}", None) for j in range(len(st), k)])[:k]
    if method == "bayes":
        return _bayes(p, alts, st, M)
    if method == "game":
        return _game(p, alts, st, M)
    return _risk(p, alts, st, M)


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    for mth in ("risk", "bayes"):
        print(solve(dict(base, method=mth))["headline"])
    g = solve(dict(base, method="game", alts="石头\n剪刀\n布", states="石头\n剪刀\n布", payoff="0,1,-1\n-1,0,1\n1,-1,0"))
    print(g["headline"], g["tables"][1]["rows"])
    print(solve(dict(base, method="game", payoff="3,1,4\n2,0,1\n5,-1,6"))["headline"])
