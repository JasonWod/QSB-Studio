"""仿真：蒙特卡洛抽样 与 单服务台离散事件仿真（种子固定，可复现）。

* 蒙特卡洛：从正态 / 均匀 / 指数分布抽样，演示帧随样本量 N 增大展示直方图逼近理论密度、
  样本均值逼近理论均值（大数定律）
* 离散事件：顾客逐个到达、排队、接受服务，演示帧逐个顾客推进「仿真表」，最后与 M/M/1 理论比较
"""
import math
import random

from . import parse as P
from . import report as R

SPEC = {
    "desc": "仿真：蒙特卡洛法从指定分布大量抽样，估计均值、分位数与事件概率，观察样本量增大时估计如何收敛；"
            "离散事件仿真逐个推进顾客的到达—排队—服务—离开，手工仿真表一目了然。随机种子固定，结果可复现。",
    "form": [
        {"id": "method", "type": "select", "label": "仿真类型", "value": "mc",
         "options": [{"v": "mc", "t": "蒙特卡洛抽样"}, {"v": "des", "t": "排队系统离散事件仿真"}]},
        {"id": "dist", "type": "select", "label": "分布（蒙特卡洛）", "value": "normal",
         "options": [{"v": "normal", "t": "正态 N(μ,σ)"},
                     {"v": "uniform", "t": "均匀 U(a,b)"},
                     {"v": "exponential", "t": "指数 Exp(率 λ)"}]},
        {"id": "p1", "type": "float", "label": "参数1 (μ / a / λ)", "value": "50"},
        {"id": "p2", "type": "float", "label": "参数2 (σ / b)", "value": "10"},
        {"id": "N", "type": "int", "label": "样本数 / 顾客数 N", "value": "5000"},
        {"id": "T", "type": "float", "label": "阈值 T（估计 P(X>T)）", "value": "65"},
        {"id": "lam", "type": "float", "label": "到达率 λ（离散事件）", "value": "1"},
        {"id": "mu", "type": "float", "label": "服务率 μ（离散事件）", "value": "1.25"},
        {"id": "seed", "type": "int", "label": "随机种子（可复现）", "value": "42"},
    ],
}


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _mc(p):
    d = p.get("dist", "normal")
    if d not in ("normal", "uniform", "exponential"):
        raise R.InputError("分布只能是 normal / uniform / exponential。")
    p1, p2 = P.num(p, "p1", 0, "参数1"), P.num(p, "p2", 1, "参数2")
    N = P.integer(p, "N", 5000, "样本数 N", 10, 200000)
    T = P.num(p, "T", 1, "阈值 T")
    rng = random.Random(P.integer(p, "seed", 42, "随机种子"))
    if d == "normal":
        if p2 <= 0:
            raise R.InputError("正态分布的 σ 必须为正。")
        draw = lambda: rng.gauss(p1, p2)
        mean_t, sd_t = p1, p2
        pdf = lambda x: math.exp(-((x - p1) / p2) ** 2 / 2) / (p2 * math.sqrt(2 * math.pi))
        ptail = 1 - _norm_cdf((T - p1) / p2)
        dname = f"N(μ={R.fmt(p1)}, σ={R.fmt(p2)})"
    elif d == "uniform":
        lo, hi = min(p1, p2), max(p1, p2)
        if hi - lo <= 0:
            raise R.InputError("均匀分布需要 a < b。")
        draw = lambda: rng.uniform(lo, hi)
        mean_t, sd_t = (lo + hi) / 2, (hi - lo) / math.sqrt(12)
        pdf = lambda x: 1 / (hi - lo) if lo <= x <= hi else 0.0
        ptail = min(1.0, max(0.0, (hi - T) / (hi - lo)))
        dname = f"U({R.fmt(lo)}, {R.fmt(hi)})"
    else:
        if p1 <= 0:
            raise R.InputError("指数分布的率 λ 必须为正。")
        draw = lambda: rng.expovariate(p1)
        mean_t = sd_t = 1 / p1
        pdf = lambda x: p1 * math.exp(-p1 * x) if x >= 0 else 0.0
        ptail = math.exp(-p1 * max(T, 0))
        dname = f"Exp(λ={R.fmt(p1)})"
    vals = [draw() for _ in range(N)]
    lo_v, hi_v = min(vals), max(vals)
    if hi_v - lo_v < 1e-12:
        hi_v = lo_v + 1
    nb = 20
    width = (hi_v - lo_v) / nb
    mids = [lo_v + width * (i + 0.5) for i in range(nb)]

    def hist(k):
        cnt = [0] * nb
        for v in vals[:k]:
            cnt[min(nb - 1, int((v - lo_v) / width))] += 1
        theo = [round(pdf(mm) * width * k, 3) for mm in mids]
        return {"type": "bar", "x": [R.fmt(mm, 1) for mm in mids], "title": f"{dname}：前 {k} 个样本的直方图",
                "series": [{"name": "样本频数", "values": cnt},
                           {"name": "理论期望频数", "values": theo, "kind": "line"}],
                "xtitle": "取值"}
    frames = []
    checkpoints = sorted({k for k in (10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000) if k < N} | {N})
    running, s = [], 0.0
    for i, v in enumerate(vals):
        s += v
        running.append(s / (i + 1))
    for k in checkpoints:
        sub = vals[:k]
        m = sum(sub) / k
        pr = sum(1 for v in sub if v > T) / k
        frames.append(R.frame(f"N = {k}", f"已抽 {k} 个样本：样本均值 {R.fmt(m)}（理论 {R.fmt(mean_t)}，误差 {R.fmt(abs(m - mean_t))}），"
                              f"P(X>{R.fmt(T)}) 估计 {R.fmt(pr)}（理论 {R.fmt(ptail)}）。"
                              + ("样本少时直方图起伏很大。" if k < 300 else "样本越多，直方图越贴近理论曲线。"),
                              chart=hist(k)))
    mean = running[-1]
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (N - 1))
    srt = sorted(vals)
    q = lambda f: srt[min(N - 1, int(f * N))]
    prob = sum(1 for v in vals if v > T) / N
    se = sd / math.sqrt(N)
    idx = sorted({min(N - 1, int(round(10 ** (i / 40 * math.log10(N))))) for i in range(41)})
    conv = {"type": "line", "x": [str(i + 1) for i in idx], "title": "样本均值随 N 的收敛（大数定律）",
            "series": [{"name": "样本均值", "values": [round(running[i], 5) for i in idx]},
                       {"name": "理论均值", "values": [mean_t] * len(idx), "dashed": True}], "xtitle": "N（对数间隔）"}
    frames.append(R.frame("收敛过程", f"样本均值在 N 小时剧烈波动，随后稳定在理论值 {R.fmt(mean_t)} 附近；"
                          f"标准误 σ/√N = {R.fmt(se)}，样本量增加 4 倍误差约减半。", chart=conv))
    return R.report(
        "optimal",
        headline=f"{dname}，N={N}：均值 ≈ {R.fmt(mean)}，σ ≈ {R.fmt(sd)}，P(X>{R.fmt(T)}) ≈ {R.fmt(prob)}",
        tables=[R.table("蒙特卡洛估计 vs 理论值", ["统计量", "仿真估计", "理论值"],
                        [["均值", R.fmt(mean), R.fmt(mean_t)], ["标准差", R.fmt(sd), R.fmt(sd_t)],
                         [f"P(X>{R.fmt(T)})", R.fmt(prob), R.fmt(ptail)],
                         ["均值的 95% 置信区间", f"[{R.fmt(mean - 1.96 * se)}, {R.fmt(mean + 1.96 * se)}]", ""],
                         ["5% / 50% / 95% 分位", f"{R.fmt(q(0.05))} / {R.fmt(q(0.5))} / {R.fmt(q(0.95))}", ""]])],
        chart=hist(N), steps=frames,
        notes=["种子固定 → 结果可复现；改种子可看到另一组随机结果。",
               "蒙特卡洛估计的误差按 1/√N 缩小。"])


def _des(p):
    lam = P.num(p, "lam", 1, "到达率 λ")
    mu = P.num(p, "mu", 1.25, "服务率 μ")
    if lam <= 0 or mu <= 0:
        raise R.InputError("到达率与服务率都必须为正。")
    N = P.integer(p, "N", 500, "顾客数 N", 5, 100000)
    rng = random.Random(P.integer(p, "seed", 42, "随机种子"))
    t_arr, free_at = 0.0, 0.0
    recs = []
    for i in range(N):
        ia = rng.expovariate(lam)
        t_arr += ia
        st = rng.expovariate(mu)
        start = max(t_arr, free_at)
        end = start + st
        recs.append((i + 1, ia, t_arr, start, st, end, start - t_arr, end - t_arr))
        free_at = end
    hdr = ["顾客", "到达间隔", "到达时刻", "开始服务", "服务时长", "离开时刻", "等待", "逗留"]
    frames = []
    show = min(12, N)
    for k in range(1, show + 1):
        r = recs[k - 1]
        rows = [[x[0]] + [R.fmt(v, 2) for v in x[1:]] for x in recs[:k]]
        cells = {(k - 1, c): "c-cur" for c in range(8)}
        why = ("服务台空闲，立即开始服务" if r[6] < 1e-9 else
               f"服务台忙到 {R.fmt(r[3], 2)}，需等待 {R.fmt(r[6], 2)}")
        frames.append(R.frame(f"顾客 {k} 到达",
                              f"随机抽取到达间隔 {R.fmt(r[1], 2)} → 在 {R.fmt(r[2], 2)} 到达；{why}；"
                              f"抽取服务时长 {R.fmt(r[4], 2)}，于 {R.fmt(r[5], 2)} 离开。",
                              tables=[R.table("仿真表", hdr, rows, cells=cells)],
                              chart={"type": "bar", "x": [str(x[0]) for x in recs[:k]], "title": "各顾客等待时间",
                                     "series": [{"name": "等待时间", "values": [round(x[6], 3) for x in recs[:k]]}],
                                     "xtitle": "顾客"}))
    Wq = sum(r[6] for r in recs) / N
    W = sum(r[7] for r in recs) / N
    span = recs[-1][5]
    util = sum(r[4] for r in recs) / span
    pw = sum(1 for r in recs if r[6] > 1e-9) / N
    rho = lam / mu
    theo = rho < 1
    th_Wq = rho / (mu - lam) if theo else None
    th_W = 1 / (mu - lam) if theo else None
    frames.append(R.frame(f"继续仿真到第 {N} 位顾客",
                          f"平均等待 {R.fmt(Wq)}，平均逗留 {R.fmt(W)}，服务台利用率 {R.fmt(util)}。"
                          + (f"M/M/1 理论值：Wq = {R.fmt(th_Wq)}，W = {R.fmt(th_W)}，ρ = {R.fmt(rho)}。" if theo else
                             "ρ ≥ 1，系统不稳定，等待时间会随顾客数不断增长。"),
                          chart={"type": "line", "x": [str(r[0]) for r in recs[::max(1, N // 300)]],
                                 "series": [{"name": "等待时间", "values": [round(r[6], 3) for r in recs[::max(1, N // 300)]]}],
                                 "title": "全部顾客的等待时间", "xtitle": "顾客序号"}))
    rows = [["平均等待时间 Wq", R.fmt(Wq), R.fmt(th_Wq) if theo else "不稳定"],
            ["平均逗留时间 W", R.fmt(W), R.fmt(th_W) if theo else "不稳定"],
            ["服务台利用率", R.fmt(util), R.fmt(min(rho, 1))],
            ["需要等待的顾客比例", R.fmt(pw), R.fmt(rho) if theo else "—"]]
    return R.report("optimal", headline=f"仿真 {N} 位顾客：平均等待 {R.fmt(Wq)}，平均逗留 {R.fmt(W)}，利用率 {R.fmt(util)}",
                    tables=[R.table("仿真结果 vs M/M/1 理论", ["指标", "仿真", "理论"], rows),
                            R.table("仿真表（前 12 位顾客）", hdr, [[x[0]] + [R.fmt(v, 2) for v in x[1:]] for x in recs[:12]])],
                    steps=frames,
                    notes=["到达间隔 ~ Exp(λ)，服务时长 ~ Exp(μ)；开始服务 = max(到达时刻, 上一位离开时刻)。",
                           "顾客数越多，仿真平均值越接近理论值。"])


def solve(p):
    return _des(p) if p.get("method") == "des" else _mc(p)


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    print(solve(base)["headline"])
    print(solve(dict(base, method="des", N=2000))["headline"])
