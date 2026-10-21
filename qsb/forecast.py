"""时间序列预测：移动平均(MA)、简单指数平滑(SES)、Holt 双参数(水平+趋势)、线性回归趋势。

演示帧逐期推进：每期展示「用到的数据 → 代入公式 → 得到下一期预测」，图上实际值与预测值同步延伸；
最后给出 MAD / MSE / MAPE 三项误差指标与下一期预测。
"""
from . import parse as P
from . import report as R

SPEC = {
    "desc": "时间序列预测：移动平均、简单指数平滑、Holt 双参数（水平+趋势）、最小二乘线性趋势。"
            "逐期给出 1 步预测并计算 MAD、MSE、MAPE，最后外推下一期。",
    "form": [
        {"id": "series", "type": "textarea", "label": "时间序列 (每行一个观测, 按时间先后)", "rows": 6,
         "value": "34\n36\n38\n39\n41\n40\n43\n45\n46\n48"},
        {"id": "method", "type": "select", "label": "方法", "value": "holt",
         "options": [{"v": "ma", "t": "移动平均 MA"}, {"v": "ses", "t": "单次指数平滑 SES"},
                     {"v": "holt", "t": "Holt 双参数（水平+趋势）"}, {"v": "regression", "t": "线性回归趋势"}]},
        {"id": "k", "type": "int", "label": "MA 窗口 k (仅 MA 用)", "value": "3"},
        {"id": "alpha", "type": "float", "label": "平滑系数 α (SES/Holt)", "value": "0.5"},
        {"id": "beta", "type": "float", "label": "趋势系数 β (Holt)", "value": "0.3"},
    ],
}


def solve(p):
    s = P.nums(p.get("series"), "时间序列")
    n = len(s)
    if n < 3:
        raise R.InputError("序列太短，至少需要 3 个观测。")
    if n > 500:
        raise R.InputError("最多 500 个观测。")
    m = p.get("method", "ma")
    F = [None] * (n + 1)          # F[t] = 对第 t 期（0 起）的预测
    expl = [""] * (n + 1)
    extra = {}
    if m == "ma":
        k = P.integer(p, "k", 3, "窗口 k", 1, n)
        for t in range(k, n + 1):
            win = s[t - k:t]
            F[t] = sum(win) / k
            expl[t] = f"F{t + 1} = ({' + '.join(R.fmt(v) for v in win)}) / {k} = {R.fmt(F[t])}"
        name = f"{k} 期移动平均"
    elif m == "ses":
        a = P.num(p, "alpha", 0.5, "α", 0, 1)
        F[1] = s[0]
        expl[1] = f"F2 = A1 = {R.fmt(s[0])}（初值取第一期实际值）"
        for t in range(2, n + 1):
            F[t] = a * s[t - 1] + (1 - a) * F[t - 1]
            expl[t] = (f"F{t + 1} = α·A{t} + (1−α)·F{t} = {R.fmt(a)}×{R.fmt(s[t - 1])} + {R.fmt(1 - a)}×"
                       f"{R.fmt(F[t - 1])} = {R.fmt(F[t])}")
        name = f"指数平滑 α={R.fmt(a)}"
    elif m == "holt":
        a = P.num(p, "alpha", 0.5, "α", 0, 1)
        b = P.num(p, "beta", 0.3, "β", 0, 1)
        # 初值：L₁ = A₁，T₁ = A₂ − A₁；之后每期先用实际值更新水平与趋势，再外推一期
        L, T = s[0], s[1] - s[0]
        for t in range(1, n):            # 第 t+1 期（1 起）的实际值 s[t]
            Lp, Tp = L, T
            L = a * s[t] + (1 - a) * (Lp + Tp)
            T = b * (L - Lp) + (1 - b) * Tp
            F[t + 1] = L + T
            init = (f"初值 L1 = A1 = {R.fmt(s[0])}，T1 = A2 − A1 = {R.fmt(s[1] - s[0])}；") if t == 1 else ""
            expl[t + 1] = (f"{init}L{t + 1} = α·A{t + 1} + (1−α)(L{t}+T{t}) = {R.fmt(a)}×{R.fmt(s[t])} + "
                           f"{R.fmt(1 - a)}×{R.fmt(Lp + Tp)} = {R.fmt(L)}；T{t + 1} = β(L{t + 1}−L{t}) + (1−β)T{t} = "
                           f"{R.fmt(T)}；F{t + 2} = L{t + 1} + T{t + 1} = {R.fmt(L + T)}")
        extra = {"水平 L": L, "趋势 T": T}
        name = f"Holt α={R.fmt(a)}, β={R.fmt(b)}"
    elif m == "regression":
        ts = list(range(1, n + 1))
        mt = (n + 1) / 2.0
        ms = sum(s) / n
        sxx = sum((t - mt) ** 2 for t in ts)
        bcoef = sum((ts[i] - mt) * (s[i] - ms) for i in range(n)) / sxx
        acoef = ms - bcoef * mt
        for t in range(n + 1):
            F[t] = acoef + bcoef * (t + 1)
            expl[t] = f"F{t + 1} = a + b·{t + 1} = {R.fmt(acoef)} + {R.fmt(bcoef)}×{t + 1} = {R.fmt(F[t])}"
        extra = {"截距 a": acoef, "斜率 b": bcoef}
        name = "线性回归趋势"
    else:
        raise R.InputError("未知的预测方法。")

    errs = [(t, s[t] - F[t]) for t in range(n) if F[t] is not None]
    if not errs:
        raise R.InputError("观测数不足以产生任何一期预测（移动平均窗口过大？）。")
    mad = sum(abs(e) for _, e in errs) / len(errs)
    mse = sum(e * e for _, e in errs) / len(errs)
    ape = [abs(e) / abs(s[t]) for t, e in errs if s[t] != 0]
    mape = 100 * sum(ape) / len(ape) if ape else 0.0
    nextf = F[n]
    xs = [str(t + 1) for t in range(n + 1)]

    def chart(upto):
        act = [round(s[t], 6) if t < upto else None for t in range(n)] + [None]
        fc = [round(F[t], 6) if F[t] is not None and t <= upto else None for t in range(n + 1)]
        return {"type": "line", "x": xs, "xtitle": "期", "title": name,
                "series": [{"name": "实际值", "values": act}, {"name": "预测值", "values": fc, "dashed": True}],
                "hl": upto}
    frames = []
    first = next(t for t in range(n + 1) if F[t] is not None)
    frames.append(R.frame("准备", f"共 {n} 期数据。{name}要从第 {first + 1} 期起才能给出预测。", chart=chart(first)))
    for t in range(first, n + 1):
        if t < n:
            e = s[t] - F[t]
            txt = (f"{expl[t] or f'F{t + 1} = {R.fmt(F[t])}'}。实际 A{t + 1} = {R.fmt(s[t])}，"
                   f"误差 e = A − F = {R.fmt(e)}。")
            title = f"第 {t + 1} 期"
        else:
            txt = f"{expl[t] or ''}。这是对未来第 {n + 1} 期的预测。"
            title = f"外推第 {n + 1} 期"
        frames.append(R.frame(title, txt, chart=chart(t + 1 if t < n else n)))
    rows = [[t + 1, R.fmt(s[t]), R.fmt(F[t]) if F[t] is not None else "—",
             R.fmt(s[t] - F[t]) if F[t] is not None else "—"] for t in range(n)]
    rows.append([n + 1, "?", R.fmt(nextf), ""])
    stat = [["MAD 平均绝对误差", R.fmt(mad)], ["MSE 均方误差", R.fmt(mse)], ["MAPE 平均绝对百分比误差", f"{R.fmt(mape)}%"],
            ["下一期预测", R.fmt(nextf)]] + [[k, R.fmt(v)] for k, v in extra.items()]
    final = chart(n)
    return R.report("optimal", headline=f"{name}：MAPE = {R.fmt(mape)}%，下期（第 {n + 1} 期）预测 = {R.fmt(nextf)}",
                    tables=[R.table("误差与预测", ["指标", "值"], stat),
                            R.table("逐期预测", ["期", "实际", "预测", "误差"], rows)],
                    chart=final, steps=frames,
                    notes=["误差 e = 实际 − 预测；MAD、MSE、MAPE 越小越好，可用来比较不同方法和参数。",
                           "α 越大越重视近期数据，反应快但波动大；有明显趋势时 Holt / 回归优于 SES。"])


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    for mth in ("ma", "ses", "holt", "regression"):
        print(solve(dict(base, method=mth))["headline"])
