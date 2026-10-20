"""蒙特卡洛模拟 (Monte Carlo)：种子随机数抽样，估计均值/标准差/分位数/事件概率，输出直方图。"""
import random
from . import report as R

SPEC = {
    "desc": "蒙特卡洛模拟：从指定分布（正态 / 均匀 / 指数）抽样 N 次，估计均值、标准差、分位数与『X>阈值』的事件概率，"
            "输出经验分布直方图（种子固定，结果可复现）。",
    "form": [
        {"id": "dist", "type": "select", "label": "分布", "value": "normal",
         "options": [{"v": "normal", "t": "正态 N(μ,σ)"},
                     {"v": "uniform", "t": "均匀 U(a,b)"},
                     {"v": "exponential", "t": "指数 Exp(率)"}]},
        {"id": "p1", "type": "float", "label": "参数1 (μ / a / 率)", "value": "0"},
        {"id": "p2", "type": "float", "label": "参数2 (σ / b)", "value": "1"},
        {"id": "N", "type": "int", "label": "样本数 N", "value": "5000"},
        {"id": "T", "type": "float", "label": "阈值 T（估计 P(X>T)）", "value": "1"},
        {"id": "seed", "type": "int", "label": "随机种子（可复现）", "value": "42"},
    ],
}


def solve(p):
    d = p.get("dist", "normal")
    p1 = float(p.get("p1", 0)); p2 = float(p.get("p2", 1))
    N = max(10, int(p.get("N", 5000)))
    T = float(p.get("T", 1)); seed = int(p.get("seed", 42))
    rng = random.Random(seed)
    vals = []
    if d == "normal":
        for _ in range(N):
            vals.append(rng.gauss(p1, max(1e-9, p2)))
    elif d == "uniform":
        lo, hi = (p1, p2) if p1 <= p2 else (p2, p1)
        for _ in range(N):
            vals.append(rng.uniform(lo, hi))
    else:  # exponential, rate
        rate = max(1e-9, p1)
        for _ in range(N):
            vals.append(rng.expovariate(rate))
    mean = sum(vals) / N
    var = sum((v - mean) ** 2 for v in vals) / (N - 1)
    sd = var ** 0.5
    srt = sorted(vals)
    q = lambda f: srt[min(N - 1, int(f * N))]
    median = q(0.5); p05 = q(0.05); p95 = q(0.95)
    prob = sum(1 for v in vals if v > T) / N
    # 直方图 (12 bins)
    lo, hi = srt[0], srt[-1]
    if hi - lo < 1e-9:
        hi = lo + 1.0
    nb = 12
    widths = [0] * nb
    for v in vals:
        idx = min(nb - 1, int((v - lo) / (hi - lo) * nb))
        widths[idx] += 1
    mids = [lo + (hi - lo) * (i + 0.5) / nb for i in range(nb)]
    dname = {"normal": f"N(μ={p1},σ={p2})", "uniform": f"U({min(p1,p2)},{max(p1,p2)})",
             "exponential": f"Exp(率={p1})"}[d]
    return R.report(
        "optimal",
        headline=f"{dname}，N={N}：均值 ≈ {R.fmt(mean)}，σ ≈ {R.fmt(sd)}，P(X>{R.fmt(T)}) ≈ {R.fmt(prob)}",
        tables=[R.table("蒙特卡洛估计", ["统计量", "值"],
                        [["均值", R.fmt(mean)], ["标准差", R.fmt(sd)],
                         ["最小 / 最大", f"{R.fmt(lo)} / {R.fmt(hi)}"],
                         ["5% / 50% / 95% 分位", f"{R.fmt(p05)} / {R.fmt(median)} / {R.fmt(p95)}"],
                         [f"P(X>{R.fmt(T)})", R.fmt(prob)]])],
        chart={"title": f"{dname} 经验直方图 (N={N})",
               "xlabels": [R.fmt(m) for m in mids],
               "series": [{"name": "频数", "color": "#10b981", "values": widths}]},
        notes=[
            "种子固定 → 结果可复现（同 seed 同分布）。",
            "样本量 N 越大，估计越接近理论值（大数定律）。",
        ])


if __name__ == "__main__":
    print(solve({"dist": "normal", "p1": 0, "p2": 1, "N": 5000, "T": 1, "seed": 42})["headline"])
