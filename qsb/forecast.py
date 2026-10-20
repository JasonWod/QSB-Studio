"""时间序列预测：移动平均(MA)、简单指数平滑(SES)、Holt 双参数、线性回归。"""
from . import report as R

SPEC = {
    "desc": "时间序列预测与精度：移动平均、简单指数平滑、Holt 双参数(水平+趋势)、最小二乘回归。给出逐期 1-step 预测、下一期预测与 MAPE。",
    "form": [
        {"id": "series", "type": "textarea", "label": "时间序列 (每行一个观测, 按时间先后)",
         "value": "34\n36\n38\n39\n41\n40\n43\n45\n46\n48"},
        {"id": "method", "type": "select", "label": "方法",
         "options": [
             {"v": "ma", "t": "移动平均 MA"},
             {"v": "ses", "t": "单次指数平滑 SES"},
             {"v": "holt", "t": "Holt 双参数（水平+趋势）"},
             {"v": "regression", "t": "线性回归"},
         ], "value": "ma"},
        {"id": "k", "type": "int", "label": "MA 窗口 k (仅 MA 用)", "value": "3"},
        {"id": "alpha", "type": "float", "label": "SES/Holt 平滑系数 alpha", "value": "0.5"},
        {"id": "beta", "type": "float", "label": "Holt 趋势系数 beta", "value": "0.3"},
    ],
}


def _ma(s, k):
    F = [s[0]]
    for t in range(1, len(s)):
        win = s[max(0, t - k):t]
        F.append(sum(win) / len(win))
    return F


def _ses(s, alpha):
    F = [s[0]]
    for t in range(1, len(s)):
        F.append(alpha * s[t - 1] + (1 - alpha) * F[-1])
    return F


def _holt(s, alpha, beta):
    L, T, F = [s[0]], [0.0], [s[0]]
    for t in range(1, len(s)):
        F.append(L[-1] + T[-1])
        L.append(alpha * s[t] + (1 - alpha) * (L[-1] + T[-1]))
        T.append(beta * (L[-1] - L[-2]) + (1 - beta) * T[-1])
    return F


def _regression(s):
    n = len(s)
    mt = n + 1 / 2.0
    ms = sum(s) / n
    sxx = sum((i + 1 - mt) ** 2 for i in range(n))
    b = (sum((i + 1 - mt) * (s[i] - ms) for i in range(n)) / sxx) if sxx else 0.0
    a = ms - b * mt
    return [a + b * (i + 1) for i in range(n)], a, b


def solve(p):
    import re as _re
    _raw = p["series"]
    if isinstance(_raw, str):
        _raw = [t for t in _re.split(r"[\s,，;]+", _raw) if t]
    s = [float(x) for x in _raw]
    if len(s) < 3:
        return R.report("error", headline="序列太短，至少需要 3 个观测")
    m = p["method"]
    a = b = None
    if m == "ma":
        F = _ma(s, max(1, int(p["k"])))
        nextf = sum(s[-max(1, int(p["k"])):]) / max(1, int(p["k"]))
        name = "移动平均 MA"
    elif m == "ses":
        F = _ses(s, float(p["alpha"]))
        nextf = float(p["alpha"]) * s[-1] + (1 - float(p["alpha"])) * F[-1]
        name = "简单指数平滑 SES"
    elif m == "holt":
        al, be = float(p["alpha"]), float(p["beta"])
        F = _holt(s, al, be)
        L, T = [s[0]], [0.0]
        for t in range(1, len(s)):
            L.append(al * s[t] + (1 - al) * (L[-1] + T[-1]))
            T.append(be * (L[-1] - L[-2]) + (1 - be) * T[-1])
        nextf = L[-1] + T[-1]
        name = "Holt 双参数"
    else:
        F, a, b = _regression(s)
        nextf = a + b * len(s)
        name = "最小二乘回归"

    ape = []
    for t in range(1, len(s)):
        if s[t] != 0:
            ape.append(abs(s[t] - F[t]) / abs(s[t]))
    mape = 100.0 * sum(ape) / len(ape) if ape else 0.0
    rows = [[t + 1, R.fmt(s[t]), R.fmt(F[t])] for t in range(1, len(s))]
    notes = [f"MAPE = {R.fmt(mape)}%（基于 1-step 预测的期内平均绝对百分比误差）。",
             f"下一期预测值 = {R.fmt(nextf)}"]
    if m == "regression":
        notes.insert(0, f"回归方程：y = {R.fmt(a)} + {R.fmt(b)}·t")
    chart = {"type": "line", "x": [t + 1 for t in range(len(s))],
             "series": [{"name": "实际", "values": [R.fmt(v) for v in s]},
                        {"name": "预测", "values": [R.fmt(v) for v in F]}],
             "xtitle": "期"}
    return R.report("optimal", headline=f"{name}：{len(s)-1} 期 MAPE = {R.fmt(mape)}%，下期预测 = {R.fmt(nextf)}",
                    tables=[R.table(f"{name} — 逐期 1-step 预测", ["期", "实际", "预测"], rows)],
                    notes=notes, chart=chart)


if __name__ == "__main__":
    r = solve({"series": [34, 36, 38, 39, 41, 40, 43, 45, 46, 48], "method": "ses",
               "alpha": 0.5, "beta": 0.3, "k": 3})
    print(r["status"], r["headline"]); print(r["tables"][0]["rows"][-3:]); print(r["notes"])
