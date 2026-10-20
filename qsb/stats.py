"""统计分析：描述统计、单样本 t、双样本 t、卡方拟合优度、Pearson 相关。
p 值用标准库实现（正则化不完全 Beta / 不完全 Gamma）。
"""
import math
from . import report as R

SPEC = {
    "desc": "统计推断：描述统计、单/双样本 t 检验、卡方拟合优度、Pearson 相关。p 值由不完全 Beta/Gamma 精确计算。",
    "form": [
        {"id": "method", "type": "select", "label": "检验类型",
         "value": "descriptive",
         "options": [
             {"v": "descriptive", "t": "描述统计"},
             {"v": "t1", "t": "单样本 t 检验"},
             {"v": "t2", "t": "双样本 t 检验"},
             {"v": "chisq", "t": "卡方拟合优度"},
             {"v": "corr", "t": "Pearson 相关"}]},
        {"id": "data1", "type": "list", "label": "序列1 / 观测值", "value": "5.1, 4.8, 5.3, 5.0, 4.9, 5.2, 4.7, 5.4"},
        {"id": "data2", "type": "list", "label": "序列2 (t2 / corr 用)", "value": "5.0, 4.9, 5.1, 5.3, 4.8, 5.2, 4.6, 5.5"},
        {"id": "expected", "type": "list", "label": "期望频数 (chisq 用)", "value": "10, 10, 10, 10"},
        {"id": "mu0", "type": "float", "label": "假设均值 μ0 (t1 用)", "value": "5.0"},
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


# ---- 正则化不完全 Beta I_x(a,b) ----
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
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
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1) < EPS:
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
    """t 统计量双侧 p 值 = I_{df/(df+t^2)}(df/2, 1/2)。"""
    return _betai(df / 2, 0.5, df / (df + t * t))


# ---- 正则化下不完全 Gamma P(a,x) ----
def _gammap(a, x):
    if x <= 0:
        return 0.0
    if x < a + 1:
        ap = a
        s = ds = 1.0 / a
        for _ in range(300):
            ap += 1
            ds *= x / ap
            s += ds
            if abs(ds) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 300):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1) < 1e-14:
            break
    Q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1 - Q


def _chi2p(x, k):
    """卡方统计量 x、自由度 k 的右尾 p 值。"""
    return 1 - _gammap(k / 2, x / 2)


def _skew(x):
    n = len(x); m = _mean(x); sd = math.sqrt(_var(x))
    if sd == 0 or n < 3:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((xi - m) / sd) ** 3 for xi in x)


def solve(p):
    m = p["method"]
    alpha = float(p.get("alpha") or 0.05)
    if m == "descriptive":
        x = [float(v) for v in p["data1"]]
        n = len(x)
        rows = [["样本量 n", n], ["均值", R.fmt(_mean(x))], ["中位数", R.fmt(_med(x))],
                ["标准差 (ddof=1)", R.fmt(math.sqrt(_var(x)))],
                ["方差", R.fmt(_var(x))], ["最小值", R.fmt(min(x))],
                ["最大值", R.fmt(max(x))], ["极差", R.fmt(max(x) - min(x))],
                ["偏度", R.fmt(_skew(x))]]
        return R.report("optimal", headline=f"描述统计：均值 = {R.fmt(_mean(x))}，标准差 = {R.fmt(math.sqrt(_var(x)))}",
                        tables=[R.table("描述统计", ["指标", "值"], rows)],
                        notes=[f"共 {n} 个观测。"])
    if m == "t1":
        x = [float(v) for v in p["data1"]]; mu0 = float(p["mu0"]); n = len(x)
        if n < 2:
            return R.report("error", headline="样本量不足")
        t = (_mean(x) - mu0) / (math.sqrt(_var(x) / n))
        df = n - 1
        pv = _t2p(t, df)
        rej = pv < alpha
        rows = [["样本均值", R.fmt(_mean(x))], ["假设均值 μ0", R.fmt(mu0)],
                ["t 统计量", R.fmt(t)], ["自由度 df", df],
                ["双侧 p 值", R.fmt(pv, 4)],
                [f"结论 (α={alpha})", "拒绝 H0（均值≠μ0）" if rej else "不拒绝 H0"]]
        return R.report("optimal" if not rej else "significant",
                        headline=f"单样本 t = {R.fmt(t)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H0",
                        tables=[R.table("单样本 t 检验", ["量", "值"], rows)],
                        notes=["H0: μ=μ0；t=(x̄-μ0)/(s/√n)。"])
    if m == "t2":
        x1 = [float(v) for v in p["data1"]]; x2 = [float(v) for v in p["data2"]]
        n1, n2 = len(x1), len(x2)
        if n1 < 2 or n2 < 2:
            return R.report("error", headline="两组样本量均须 ≥ 2")
        vp = ((n1 - 1) * _var(x1) + (n2 - 1) * _var(x2)) / (n1 + n2 - 2)
        se = math.sqrt(vp * (1 / n1 + 1 / n2))
        t = (_mean(x1) - _mean(x2)) / se
        df = n1 + n2 - 2
        pv = _t2p(t, df)
        rej = pv < alpha
        rows = [["x̄1 / x̄2", f"{R.fmt(_mean(x1))} / {R.fmt(_mean(x2))}"],
                ["合并方差 s_p²", R.fmt(vp)], ["t 统计量", R.fmt(t)], ["自由度 df", df],
                ["双侧 p 值", R.fmt(pv, 4)],
                [f"结论 (α={alpha})", "拒绝 H0（两均值不同）" if rej else "不拒绝 H0"]]
        return R.report("optimal" if not rej else "significant",
                        headline=f"双样本 t = {R.fmt(t)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H0",
                        tables=[R.table("双样本 t 检验（合并方差）", ["量", "值"], rows)],
                        notes=["H0: μ1=μ2；独立样本、方差齐性。"])
    if m == "chisq":
        o = [float(v) for v in p["data1"]]
        e = [float(v) for v in p["expected"]]
        if len(o) != len(e) or len(o) < 2:
            return R.report("error", headline="期望频数须与观测等长且 ≥2 类")
        if any(v <= 0 for v in e):
            return R.report("error", headline="期望频数须 > 0")
        chi2 = sum((oi - ei) ** 2 / ei for oi, ei in zip(o, e))
        df = len(o) - 1
        pv = _chi2p(chi2, df)
        rej = pv < alpha
        rows = [["χ² 统计量", R.fmt(chi2)], ["自由度 df = k-1", df],
                ["右尾 p 值", R.fmt(pv, 4)],
                [f"结论 (α={alpha})", "拒绝 H0（不符预期分布）" if rej else "不拒绝 H0"]]
        return R.report("optimal" if not rej else "significant",
                        headline=f"卡方 χ² = {R.fmt(chi2)}，p = {R.fmt(pv, 4)} → {'拒绝' if rej else '不拒绝'} H0",
                        tables=[R.table("卡方拟合优度", ["量", "值"], rows),
                                R.table("观测 vs 期望", ["类别", "观测", "期望"],
                                        [[i + 1, R.fmt(o[i]), R.fmt(e[i])] for i in range(len(o))])],
                        notes=["H0: 观测服从给定期望分布；χ²=Σ(o-e)²/e。"])
    # corr
    x = [float(v) for v in p["data1"]]; y = [float(v) for v in p["data2"]]
    n = min(len(x), len(y))
    if n < 3:
        return R.report("error", headline="相关分析需至少 3 对数据")
    x, y = x[:n], y[:n]
    mx, my = _mean(x), _mean(y)
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sxx = sum((x[i] - mx) ** 2 for i in range(n))
    syy = sum((y[i] - my) ** 2 for i in range(n))
    r = sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0
    t = r * math.sqrt(n - 2) / math.sqrt(1 - r * r) if abs(r) < 1 else float("inf")
    pv = _t2p(t, n - 2) if math.isfinite(t) else 0.0
    rej = pv < alpha
    rows = [["Pearson r", R.fmt(r)], ["r²（决定系数）", R.fmt(r * r)],
            ["t 统计量 (df=n-2)", R.fmt(t)], ["双侧 p 值", R.fmt(pv, 4)],
            [f"结论 (α={alpha})", "相关显著" if rej else "相关不显著"]]
    return R.report("optimal" if not rej else "significant",
                    headline=f"Pearson r = {R.fmt(r)}，p = {R.fmt(pv, 4)} → {'显著' if rej else '不显著'}",
                    tables=[R.table("相关性", ["量", "值"], rows)],
                    notes=["r 的显著性用 t=r√(n-2)/√(1-r²) 检验。"])


if __name__ == "__main__":
    # 校验数值
    print("t2p(1.96,30)=", round(_t2p(1.96, 30), 4), "(expect ~0.0597)")
    print("chi2p(5.99,1)=", round(_chi2p(5.99, 1), 4), "(expect ~0.0147)")
    print("betai(0.5,0.5,0.5)=", round(_betai(0.5, 0.5, 0.5), 4), "(expect 0.5)")
    for k in ["descriptive", "t1", "t2", "chisq", "corr"]:
        r = solve({"method": k, "data1": [5.1, 4.8, 5.3, 5.0, 4.9, 5.2, 4.7, 5.4],
                   "data2": [5.0, 4.9, 5.1, 5.3, 4.8, 5.2, 4.6, 5.5],
                   "expected": [10, 10, 10, 10], "mu0": 5.0, "alpha": 0.05})
        print(f"{k:12}", r["status"], "|", r["headline"])
