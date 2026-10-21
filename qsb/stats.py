"""统计分析：描述统计、单样本 / 双样本 / 配对 t 检验、卡方拟合优度、相关与一元线性回归。

p 值与临界值用标准库自行实现（正则化不完全 Beta / Gamma 函数 + 二分求分位数），不依赖 scipy。
演示帧：按教科书步骤展开——计算样本量、统计量、在分布图上标出拒绝域与统计量位置、下结论。
"""
import math

from . import parse as P
from . import report as R

SPEC = {
    "desc": "统计推断：描述统计、单样本 / 双样本（合并方差）/ 配对 t 检验、卡方拟合优度、Pearson 相关与一元线性回归。"
            "每个检验都画出统计量的分布、拒绝域和观测值位置，p 值精确计算（无第三方库）。",
    "form": [
        {"id": "method", "type": "select", "label": "分析类型", "value": "t1",
         "options": [
             {"v": "descriptive", "t": "描述统计"},
             {"v": "t1", "t": "单样本 t 检验"},
             {"v": "t2", "t": "双样本 t 检验（独立）"},
             {"v": "paired", "t": "配对 t 检验"},
             {"v": "chisq", "t": "卡方拟合优度"},
             {"v": "corr", "t": "相关与线性回归"}]},
        {"id": "data1", "type": "list", "label": "样本1 / x", "value": "5.1, 4.8, 5.3, 5.0, 4.9, 5.2, 4.7, 5.4, 5.6, 5.3"},
        {"id": "data2", "type": "list", "label": "样本2 / y（双样本、配对、回归用）",
         "value": "4.6, 4.9, 4.8, 5.0, 4.5, 4.9, 4.4, 5.1, 5.2, 4.8"},
        {"id": "mu0", "type": "float", "label": "假设均值 μ₀（单样本用）", "value": "5.0"},
        {"id": "observed", "type": "list", "label": "观测频数（卡方用）", "value": "18, 25, 32, 25"},
        {"id": "expected", "type": "list", "label": "期望频数或比例（卡方用）", "value": "25, 25, 25, 25"},
        {"id": "alpha", "type": "float", "label": "显著性水平 α", "value": "0.05"},
    ],
}


def _mean(x):
    return sum(x) / len(x)


def _var(x, ddof=1):
    m = _mean(x)
    return sum((v - m) ** 2 for v in x) / (len(x) - ddof)


def _med(x):
    s = sorted(x); n = len(s)
    k = n // 2
    return s[k] if n % 2 else (s[k - 1] + s[k]) / 2


def _quantile(x, q):
    s = sorted(x)
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos)); hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ---- 正则化不完全 Beta I_x(a,b) ----
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def _t2p(t, df):
    """t 统计量双侧 p 值。"""
    return _betai(df / 2, 0.5, df / (df + t * t))


def _gammap(a, x):
    """正则化下不完全 Gamma P(a, x)。"""
    if x <= 0:
        return 0.0
    if x < a + 1:
        ap, s = a, 1.0 / a
        ds = s
        for _ in range(500):
            ap += 1
            ds *= x / ap
            s += ds
            if abs(ds) < abs(s) * 1e-15:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a
    c, d = 1e300, 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-15:
            break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _chi2p(x, k):
    return 1 - _gammap(k / 2, x / 2)


def _bisect(f, lo, hi, target, inc=True):
    for _ in range(200):
        mid = (lo + hi) / 2
        if (f(mid) < target) == inc:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _tcrit(alpha, df):
    """双侧临界值 t_{α/2}：使 双侧 p = α。"""
    return _bisect(lambda t: _t2p(t, df), 0.0, 1000.0, alpha, inc=False)


def _chi2crit(alpha, k):
    return _bisect(lambda x: _chi2p(x, k), 0.0, 10000.0, alpha, inc=False)


def _tpdf(t, df):
    return math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi) * \
        (1 + t * t / df) ** (-(df + 1) / 2)


def _chi2pdf(x, k):
    if x <= 0:
        return 0.0
    return math.exp((k / 2 - 1) * math.log(x) - x / 2 - (k / 2) * math.log(2) - math.lgamma(k / 2))


def _skew(x):
    n = len(x); m = _mean(x); sd = math.sqrt(_var(x))
    if sd == 0 or n < 3:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((xi - m) / sd) ** 3 for xi in x)


def _t_chart(t, df, tc):
    lim = max(4.0, abs(t) * 1.15, tc * 1.3)
    xs = [-lim + 2 * lim * i / 160 for i in range(161)]
    ys = [round(_tpdf(x, df), 5) for x in xs]
    lo = max(i for i, x in enumerate(xs) if x <= -tc)
    hi = min(i for i, x in enumerate(xs) if x >= tc)
    it = min(range(len(xs)), key=lambda i: abs(xs[i] - t))
    return {"type": "line", "x": [R.fmt(x, 2) for x in xs], "xtitle": "t", "title": f"t 分布（自由度 {df}）",
            "series": [{"name": "密度", "values": ys, "shade": [[0, lo], [hi, len(xs) - 1]]}],
            "hl": it, "hl_label": f"t = {R.fmt(t, 3)}"}


def _ttest_frames(title_stat, steps_txt, t, df, alpha, h0, h1):
    tc = _tcrit(alpha, df)
    pv = _t2p(t, df)
    rej = pv < alpha
    ch = _t_chart(t, df, tc)
    frames = [R.frame("第 1 步：建立假设", f"H₀：{h0}；H₁：{h1}（双侧检验），显著性水平 α = {R.fmt(alpha)}。")]
    frames.append(R.frame("第 2 步：计算检验统计量", steps_txt))
    frames.append(R.frame("第 3 步：确定拒绝域", f"自由度 df = {df}，查 t 分布得临界值 t_(α/2) = ±{R.fmt(tc)}；"
                          f"|t| 超过它（阴影区）就拒绝 H₀。", chart=dict(ch, hl=None)))
    frames.append(R.frame("第 4 步：作出结论",
                          f"{title_stat} = {R.fmt(t)}，{'落在' if rej else '未落入'}拒绝域；双侧 p 值 = {R.fmt(pv, 5)} "
                          f"{'<' if rej else '≥'} α。结论：{'拒绝 H₀，差异显著' if rej else '不能拒绝 H₀，差异不显著'}。",
                          chart=ch))
    return frames, tc, pv, rej, ch


def solve(p):
    m = p.get("method", "descriptive")
    alpha = P.num(p, "alpha", 0.05, "显著性水平 α")
    if not 0 < alpha < 1:
        raise R.InputError("显著性水平 α 必须在 0 与 1 之间。")
    if m == "chisq":
        o = P.nums(p.get("observed"), "观测频数")
        e = P.nums(p.get("expected"), "期望频数")
        if len(o) != len(e) or len(o) < 2:
            raise R.InputError("观测频数与期望频数个数须相同且至少 2 类。")
        if any(v < 0 for v in o) or any(v <= 0 for v in e):
            raise R.InputError("观测频数须 ≥ 0，期望频数须 > 0。")
        N = sum(o)
        if abs(sum(e) - 1) < 1e-9 or abs(sum(e) - N) > 1e-9:
            e = [v / sum(e) * N for v in e]           # 给的是比例或总数不符时按比例换算
        k = len(o) - 1
        comp = [(oi - ei) ** 2 / ei for oi, ei in zip(o, e)]
        chi2 = sum(comp)
        pv = _chi2p(chi2, k)
        cv = _chi2crit(alpha, k)
        rej = pv < alpha
        lim = max(cv * 1.6, chi2 * 1.2, k + 4 * math.sqrt(2 * k))
        xs = [lim * i / 160 for i in range(161)]
        lo = min(i for i, x in enumerate(xs) if x >= cv)
        ic = min(range(len(xs)), key=lambda i: abs(xs[i] - chi2))
        ch = {"type": "line", "x": [R.fmt(x, 1) for x in xs], "xtitle": "χ²", "title": f"χ² 分布（自由度 {k}）",
              "series": [{"name": "密度", "values": [round(_chi2pdf(x, k), 5) for x in xs], "shade": [[lo, 160]]}],
              "hl": ic, "hl_label": f"χ² = {R.fmt(chi2, 3)}"}
        tb = R.table("观测 vs 期望", ["类别", "观测 O", "期望 E", "(O−E)²/E"],
                     [[i + 1, R.fmt(o[i]), R.fmt(e[i]), R.fmt(comp[i])] for i in range(len(o))]
                     + [["合计", R.fmt(N), R.fmt(sum(e)), R.fmt(chi2)]])
        frames = [R.frame("第 1 步：建立假设", f"H₀：观测数据服从给定的期望分布；H₁：不服从。α = {R.fmt(alpha)}。"),
                  R.frame("第 2 步：逐类计算 (O−E)²/E", f"求和得 χ² = {R.fmt(chi2)}。偏差越大，χ² 越大。", tables=[tb]),
                  R.frame("第 3 步：拒绝域", f"自由度 k − 1 = {k}，临界值 χ²_α = {R.fmt(cv)}，右侧阴影为拒绝域。",
                          chart=dict(ch, hl=None)),
                  R.frame("第 4 步：结论", f"χ² = {R.fmt(chi2)}，p = {R.fmt(pv, 5)}。"
                          f"{'拒绝 H₀：与期望分布有显著差异' if rej else '不能拒绝 H₀：与期望分布无显著差异'}。", chart=ch)]
        if any(v < 5 for v in e):
            frames[-1]["text"] += " 注意：有期望频数 < 5，卡方近似可能不准。"
        return R.report("significant" if rej else "optimal",
                        headline=f"χ² = {R.fmt(chi2)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H₀",
                        tables=[tb, R.table("检验结果", ["量", "值"], [["χ² 统计量", R.fmt(chi2)], ["自由度", k],
                                                                    ["临界值", R.fmt(cv)], ["p 值", R.fmt(pv, 5)]])],
                        chart=ch, steps=frames, notes=["χ² = Σ(O − E)²/E；各类期望频数最好都 ≥ 5。"])

    x = P.nums(p.get("data1"), "样本1")
    if len(x) < 2:
        raise R.InputError("样本1 至少需要 2 个数据。")
    if m == "descriptive":
        n = len(x); mn = _mean(x); sd = math.sqrt(_var(x))
        q1, q3 = _quantile(x, 0.25), _quantile(x, 0.75)
        rows = [["样本量 n", n], ["均值 x̄", R.fmt(mn)], ["中位数", R.fmt(_med(x))], ["标准差 s", R.fmt(sd)],
                ["方差 s²", R.fmt(_var(x))], ["最小值 / 最大值", f"{R.fmt(min(x))} / {R.fmt(max(x))}"],
                ["Q1 / Q3", f"{R.fmt(q1)} / {R.fmt(q3)}"], ["极差", R.fmt(max(x) - min(x))],
                ["变异系数 s/x̄", R.fmt(sd / mn) if mn else "—"], ["偏度", R.fmt(_skew(x))]]
        srt = sorted(x)
        ch = {"type": "bar", "x": [str(i + 1) for i in range(n)], "title": "排序后的数据与均值",
              "series": [{"name": "数据（升序）", "values": srt},
                         {"name": f"均值 {R.fmt(mn)}", "values": [mn] * n, "kind": "line", "dashed": True}]}
        frames = [R.frame("第 1 步：排序", f"把 {n} 个数据从小到大排列，中位数 = {R.fmt(_med(x))}，四分位数 Q1 = {R.fmt(q1)}、Q3 = {R.fmt(q3)}。",
                          chart=dict(ch, series=ch["series"][:1])),
                  R.frame("第 2 步：均值", f"x̄ = Σx / n = {R.fmt(sum(x))} / {n} = {R.fmt(mn)}。", chart=ch),
                  R.frame("第 3 步：离散程度", f"s² = Σ(x − x̄)² / (n − 1) = {R.fmt(sum((v - mn) ** 2 for v in x))} / {n - 1} "
                          f"= {R.fmt(_var(x))}，标准差 s = {R.fmt(sd)}。", chart=ch)]
        return R.report("optimal", headline=f"描述统计：均值 = {R.fmt(mn)}，标准差 = {R.fmt(sd)}",
                        tables=[R.table("描述统计", ["指标", "值"], rows)], chart=ch, steps=frames,
                        notes=["样本方差除以 n−1（无偏估计）。"])
    if m == "t1":
        mu0 = P.num(p, "mu0", None, "假设均值 μ₀")
        n = len(x); mn = _mean(x); s = math.sqrt(_var(x))
        if s == 0:
            raise R.InputError("样本数据全部相同，标准差为 0，无法做 t 检验。")
        se = s / math.sqrt(n)
        t = (mn - mu0) / se
        txt = (f"n = {n}，x̄ = {R.fmt(mn)}，s = {R.fmt(s)}，标准误 s/√n = {R.fmt(se)}；"
               f"t = (x̄ − μ₀)/(s/√n) = ({R.fmt(mn)} − {R.fmt(mu0)}) / {R.fmt(se)} = {R.fmt(t)}。")
        frames, tc, pv, rej, ch = _ttest_frames("t", txt, t, n - 1, alpha, f"μ = {R.fmt(mu0)}", f"μ ≠ {R.fmt(mu0)}")
        ci = (mn - tc * se, mn + tc * se)
        rows = [["样本均值 x̄", R.fmt(mn)], ["假设均值 μ₀", R.fmt(mu0)], ["t 统计量", R.fmt(t)], ["自由度", n - 1],
                ["临界值 ±t", R.fmt(tc)], ["双侧 p 值", R.fmt(pv, 5)],
                [f"均值的 {R.fmt(100 * (1 - alpha))}% 置信区间", f"[{R.fmt(ci[0])}, {R.fmt(ci[1])}]"],
                ["结论", "拒绝 H₀" if rej else "不拒绝 H₀"]]
        return R.report("significant" if rej else "optimal",
                        headline=f"单样本 t = {R.fmt(t)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H₀",
                        tables=[R.table("单样本 t 检验", ["量", "值"], rows)], chart=ch, steps=frames,
                        notes=["前提：总体近似正态；置信区间不含 μ₀ ⇔ 双侧检验拒绝 H₀。"])
    y = P.nums(p.get("data2"), "样本2")
    if len(y) < 2:
        raise R.InputError("样本2 至少需要 2 个数据。")
    if m == "t2":
        n1, n2 = len(x), len(y)
        vp = ((n1 - 1) * _var(x) + (n2 - 1) * _var(y)) / (n1 + n2 - 2)
        se = math.sqrt(vp * (1 / n1 + 1 / n2))
        if se == 0:
            raise R.InputError("两组数据方差都为 0，无法检验。")
        t = (_mean(x) - _mean(y)) / se
        txt = (f"x̄₁ = {R.fmt(_mean(x))}，x̄₂ = {R.fmt(_mean(y))}；合并方差 s_p² = [(n₁−1)s₁² + (n₂−1)s₂²]/(n₁+n₂−2) = "
               f"{R.fmt(vp)}；t = (x̄₁ − x̄₂)/√(s_p²(1/n₁+1/n₂)) = {R.fmt(t)}。")
        frames, tc, pv, rej, ch = _ttest_frames("t", txt, t, n1 + n2 - 2, alpha, "μ₁ = μ₂", "μ₁ ≠ μ₂")
        rows = [["x̄₁ / x̄₂", f"{R.fmt(_mean(x))} / {R.fmt(_mean(y))}"], ["s₁² / s₂²", f"{R.fmt(_var(x))} / {R.fmt(_var(y))}"],
                ["合并方差 s_p²", R.fmt(vp)], ["t 统计量", R.fmt(t)], ["自由度", n1 + n2 - 2],
                ["临界值 ±t", R.fmt(tc)], ["双侧 p 值", R.fmt(pv, 5)], ["结论", "拒绝 H₀" if rej else "不拒绝 H₀"]]
        return R.report("significant" if rej else "optimal",
                        headline=f"双样本 t = {R.fmt(t)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H₀",
                        tables=[R.table("双样本 t 检验（合并方差）", ["量", "值"], rows)], chart=ch, steps=frames,
                        notes=["前提：两组独立、近似正态、方差相近。若同一对象前后测量，请用配对 t 检验。"])
    if len(x) != len(y):
        raise R.InputError(f"{'配对检验' if m == 'paired' else '相关回归'}要求两组数据一一对应、个数相同"
                           f"（当前 {len(x)} 与 {len(y)}）。")
    n = len(x)
    if m == "paired":
        d = [a - b for a, b in zip(x, y)]
        md, sd = _mean(d), math.sqrt(_var(d))
        if sd == 0:
            raise R.InputError("所有差值都相同，标准差为 0，无法检验。")
        t = md / (sd / math.sqrt(n))
        txt = (f"逐对相减得差值 d = ({', '.join(R.fmt(v, 3) for v in d)})；d̄ = {R.fmt(md)}，s_d = {R.fmt(sd)}；"
               f"t = d̄ / (s_d/√n) = {R.fmt(t)}。")
        frames, tc, pv, rej, ch = _ttest_frames("t", txt, t, n - 1, alpha, "μ_d = 0（前后无差异）", "μ_d ≠ 0")
        rows = [["差值均值 d̄", R.fmt(md)], ["差值标准差 s_d", R.fmt(sd)], ["t 统计量", R.fmt(t)], ["自由度", n - 1],
                ["临界值 ±t", R.fmt(tc)], ["双侧 p 值", R.fmt(pv, 5)], ["结论", "拒绝 H₀" if rej else "不拒绝 H₀"]]
        return R.report("significant" if rej else "optimal",
                        headline=f"配对 t = {R.fmt(t)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H₀",
                        tables=[R.table("配对 t 检验", ["量", "值"], rows)], chart=ch, steps=frames,
                        notes=["配对检验把两组数据的差值当作一个样本做单样本 t 检验。"])
    # 相关与回归
    if n < 3:
        raise R.InputError("相关回归至少需要 3 对数据。")
    mx, my = _mean(x), _mean(y)
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sxx = sum((v - mx) ** 2 for v in x)
    syy = sum((v - my) ** 2 for v in y)
    if sxx == 0 or syy == 0:
        raise R.InputError("x 或 y 的数据全部相同，无法计算相关系数。")
    r = sxy / math.sqrt(sxx * syy)
    b = sxy / sxx
    a = my - b * mx
    t = r * math.sqrt(n - 2) / math.sqrt(max(1e-300, 1 - r * r))
    pv = _t2p(t, n - 2)
    rej = pv < alpha
    sse = sum((y[i] - a - b * x[i]) ** 2 for i in range(n))
    pts = [[x[i], y[i]] for i in range(n)]
    lo, hi = min(x), max(x)
    sc = {"type": "scatter", "points": pts, "title": "散点图与回归直线", "xtitle": "x", "ytitle": "y"}
    frames = [R.frame("第 1 步：画散点图", f"{n} 对数据。先看点的分布是否大致呈直线趋势。", chart=sc),
              R.frame("第 2 步：最小二乘拟合", f"b = Sxy/Sxx = {R.fmt(sxy)}/{R.fmt(sxx)} = {R.fmt(b)}，a = ȳ − b·x̄ = {R.fmt(a)}，"
                      f"回归方程 ŷ = {R.fmt(a)} + {R.fmt(b)}x。", chart=dict(sc, line=[[lo, a + b * lo], [hi, a + b * hi]])),
              R.frame("第 3 步：相关系数与显著性",
                      f"r = Sxy/√(Sxx·Syy) = {R.fmt(r)}，决定系数 r² = {R.fmt(r * r)}（y 的变化有 {R.fmt(100 * r * r, 1)}% "
                      f"可由 x 解释）。t = r√(n−2)/√(1−r²) = {R.fmt(t)}，p = {R.fmt(pv, 5)} → "
                      f"{'相关显著' if rej else '相关不显著'}。", chart=dict(sc, line=[[lo, a + b * lo], [hi, a + b * hi]]))]
    rows = [["回归方程", f"ŷ = {R.fmt(a)} + {R.fmt(b)}x"], ["Pearson r", R.fmt(r)], ["决定系数 r²", R.fmt(r * r)],
            ["残差标准误", R.fmt(math.sqrt(sse / (n - 2)))], ["t 统计量 (df = n−2)", R.fmt(t)], ["双侧 p 值", R.fmt(pv, 5)],
            ["结论", "相关显著" if rej else "相关不显著"]]
    return R.report("significant" if rej else "optimal",
                    headline=f"ŷ = {R.fmt(a)} + {R.fmt(b)}x，r = {R.fmt(r)}，p = {R.fmt(pv, 4)}",
                    tables=[R.table("相关与回归", ["量", "值"], rows)],
                    chart=frames[-1]["chart"], steps=frames,
                    notes=["相关不等于因果；r 只度量线性关系的强弱。"])


if __name__ == "__main__":
    print("t2p(1.96,30)=", round(_t2p(1.96, 30), 4), "(expect 0.0594)")
    print("tcrit(0.05,9)=", round(_tcrit(0.05, 9), 4), "(expect 2.2622)")
    print("chi2crit(0.05,3)=", round(_chi2crit(0.05, 3), 4), "(expect 7.8147)")
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    for k in ["descriptive", "t1", "t2", "paired", "chisq", "corr"]:
        r = solve(dict(base, method=k))
        print(f"{k:12}", r["status"], "|", r["headline"])
