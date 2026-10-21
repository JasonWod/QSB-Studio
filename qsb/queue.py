"""排队论：M/M/1、M/M/c（Erlang C）、M/M/1/K（有限容量）稳态指标。

演示帧：生灭过程状态转移图 → 稳态概率 P₀ 与 Pₙ 分布 → Little 公式求 L、Lq、W、Wq
       → 一段离散事件仿真的「系统内顾客数」轨迹，对照理论 L 看时间平均如何收敛。
"""
import math
import random

from . import graphviz as GV
from . import parse as P
from . import report as R

SPEC = {
    "desc": "排队模型：M/M/1 单服务台、M/M/c 多服务台（Erlang C）、M/M/1/K 有限容量。"
            "先由生灭过程求稳态概率，再用 Little 公式 L=λW 得到平均队长与等待时间，最后用仿真验证。",
    "form": [
        {"id": "method", "type": "select", "label": "模型", "value": "mmc", "options": [
            {"v": "mm1", "t": "M/M/1 单服务台"},
            {"v": "mmc", "t": "M/M/c 多服务台"},
            {"v": "mm1k", "t": "M/M/1/K 有限容量"}]},
        {"id": "lambda", "type": "float", "label": "到达率 λ (人/单位时间)", "value": "4"},
        {"id": "mu", "type": "float", "label": "每个服务台的服务率 μ", "value": "3"},
        {"id": "c", "type": "int", "label": "服务台数 c（M/M/c 用）", "value": "2"},
        {"id": "K", "type": "int", "label": "系统容量 K（M/M/1/K 用）", "value": "5"},
    ],
}


def _simulate(lam, mu, c, K, T, seed=7):
    """离散事件仿真，返回 [(时刻, 系统内人数)] 阶梯轨迹与时间平均人数。"""
    rng = random.Random(seed)
    t, nsys = 0.0, 0
    next_arr = rng.expovariate(lam)
    deps = []                       # 各在服顾客的离开时刻
    pts = [(0.0, 0)]
    area = 0.0
    while True:
        nd = min(deps) if deps else math.inf
        tn = min(next_arr, nd)
        if tn > T:
            area += nsys * (T - t)
            break
        area += nsys * (tn - t)
        t = tn
        if next_arr <= nd:
            if K is None or nsys < K:
                nsys += 1
                if len(deps) < c:
                    deps.append(t + rng.expovariate(mu))
            next_arr = t + rng.expovariate(lam)
        else:
            deps.remove(nd)
            nsys -= 1
            if nsys >= c:
                deps.append(t + rng.expovariate(mu))
        pts.append((t, nsys))
    return pts, area / T


def solve(p):
    m = p.get("method", "mm1")
    if m not in ("mm1", "mmc", "mm1k"):
        raise R.InputError("模型只能是 mm1 / mmc / mm1k。")
    lam = P.num(p, "lambda", None, "到达率 λ")
    mu = P.num(p, "mu", None, "服务率 μ")
    if lam <= 0 or mu <= 0:
        raise R.InputError("到达率 λ 与服务率 μ 都必须为正数。")
    c = P.integer(p, "c", 2, "服务台数 c", 1, 50) if m == "mmc" else 1
    K = P.integer(p, "K", 5, "系统容量 K", 1, 60) if m == "mm1k" else None
    rho = lam / (c * mu)
    a = lam / mu
    name = {"mm1": "M/M/1", "mmc": f"M/M/{c}", "mm1k": f"M/M/1/{K}"}[m]
    frames = []

    # ---- 生灭过程图 ----
    N = K if K is not None else min(max(c + 3, 6), 10)
    ids = [str(i) for i in range(N + 1)]
    pos = {ids[i]: (0.06 + 0.88 * i / N, 0.5) for i in range(N + 1)}
    ed = []
    for i in range(N):
        ed.append((ids[i], ids[i + 1], "λ", "flow"))
        ed.append((ids[i + 1], ids[i], f"{min(i + 1, c)}μ", "path"))
    g = GV.positioned_graph(pos, {x: x for x in ids}, {"0": "src"}, ed, directed=True, layout="row")
    frames.append(R.frame(f"第 1 步：{name} 的状态转移图",
                          f"状态 n = 系统内顾客数。顾客以速率 λ = {R.fmt(lam)} 到达（n→n+1），"
                          f"服务完成速率为 min(n, c)·μ（n→n−1，μ = {R.fmt(mu)}）。"
                          + ("状态无上限，图只画出前几个。" if K is None else f"系统最多容纳 K = {K} 人，满员时新到者离开。"),
                          graph=g))
    if K is None and rho >= 1:
        frames.append(R.frame("稳定性检验", f"ρ = λ/(cμ) = {R.fmt(rho)} ≥ 1：到达比服务快，队伍会无限变长，没有稳态。"))
        return R.report("unstable", headline=f"系统不稳定：ρ = {R.fmt(rho)} ≥ 1，队列将无限增长",
                        message="请增大服务率 μ、增加服务台 c，或降低到达率 λ。", steps=frames)

    # ---- 稳态概率 ----
    if m == "mm1":
        P0 = 1 - rho
        pn = lambda n: (1 - rho) * rho ** n
        p0_txt = f"P₀ = 1 − ρ = 1 − {R.fmt(rho)} = {R.fmt(P0)}"
        Lq = rho * rho / (1 - rho); L = Lq + rho
        lam_eff = lam
        Pw = rho
    elif m == "mmc":
        s = sum(a ** n / math.factorial(n) for n in range(c))
        term = a ** c / math.factorial(c) / (1 - rho)
        P0 = 1.0 / (s + term)
        pn = lambda n: P0 * a ** n / math.factorial(n) if n < c else P0 * a ** n / (math.factorial(c) * c ** (n - c))
        p0_txt = (f"P₀ = [Σₙ₌₀^{c - 1} aⁿ/n! + a^c/(c!(1−ρ))]⁻¹，a = λ/μ = {R.fmt(a)}，"
                  f"得 P₀ = {R.fmt(P0)}")
        Pw = term * P0
        Lq = Pw * rho / (1 - rho); L = Lq + a
        lam_eff = lam
    else:
        if abs(rho - 1) < 1e-12:
            P0 = 1.0 / (K + 1)
            pn = lambda n: 1.0 / (K + 1)
        else:
            P0 = (1 - rho) / (1 - rho ** (K + 1))
            pn = lambda n: P0 * rho ** n
        p0_txt = f"P₀ = (1−ρ)/(1−ρ^(K+1)) = {R.fmt(P0)}（ρ = λ/μ = {R.fmt(rho)}，有限容量时 ρ 可以 ≥ 1）"
        L = sum(n * pn(n) for n in range(K + 1))
        PK = pn(K)
        lam_eff = lam * (1 - PK)
        Lq = L - (1 - P0)
        Pw = 1 - P0 - PK
    frames.append(R.frame("第 2 步：求空闲概率 P₀",
                          f"由「流入 = 流出」的平衡方程 λPₙ = min(n+1,c)μPₙ₊₁ 递推，所有 Pₙ 之和为 1，得 {p0_txt}。"))
    nmax = K if K is not None else max(8, min(25, int(L * 3) + c + 2))
    probs = [pn(n) for n in range(nmax + 1)]
    chart = {"type": "bar", "x": [str(n) for n in range(nmax + 1)],
             "series": [{"name": "Pₙ", "values": [round(v, 6) for v in probs]}],
             "xtitle": "系统内人数 n", "title": f"{name} 稳态概率分布"}
    frames.append(R.frame("第 3 步：稳态分布 Pₙ",
                          f"系统里恰有 n 人的长期比例。P₀ = {R.fmt(P0)} 表示服务台全空闲的时间占比。"
                          + (f" 满员概率 P_K = {R.fmt(pn(K))}，这部分顾客被拒之门外。" if K else ""),
                          chart=chart))
    Wq = Lq / lam_eff; W = L / lam_eff
    frames.append(R.frame("第 4 步：Little 公式",
                          f"平均队长 Lq = {R.fmt(Lq)}，系统内平均人数 L = {R.fmt(L)}。"
                          f"由 Little 公式 L = λW：W = L/λ{'_eff' if K else ''} = {R.fmt(W)}，Wq = Lq/λ{'_eff' if K else ''} = {R.fmt(Wq)}。"
                          + (f" 这里有效到达率 λ_eff = λ(1−P_K) = {R.fmt(lam_eff)}。" if K else "")))
    T = 20000.0 / lam                     # 约 2 万个顾客，时间平均足够稳定
    pts, avg = _simulate(lam, mu, c, K, T)
    show = pts[:400]                      # 图上只画开头约 400 个事件，阶梯形状清晰
    t_end = show[-1][0]
    xs, ys = [], []
    for (t0, n0), (t1, _) in zip(show, show[1:] + [(t_end, show[-1][1])]):
        xs += [round(t0, 4), round(t1, 4)]; ys += [n0, n0]
    err = abs(avg - L) / L if L > 0 else 0.0
    sim_chart = {"type": "line", "numx": True, "x": xs, "series": [{"name": "系统内人数（仿真）", "values": ys},
                                                                  {"name": f"理论 L = {R.fmt(L)}", "values": [L] * len(xs),
                                                                   "dashed": True}],
                 "xtitle": "时间", "title": "仿真样本轨迹"}
    frames.append(R.frame("第 5 步：仿真验证",
                          f"随机生成到达与服务时间，图中是开头一段（约 {R.fmt(t_end, 1)} 个时间单位）的系统内人数，忽高忽低。"
                          f"把仿真延长到约 2 万名顾客（{R.fmt(T, 0)} 个时间单位），时间平均人数 = {R.fmt(avg)}，"
                          f"理论 L = {R.fmt(L)}，相对误差 {R.fmt(100 * err, 1)}%。"
                          + ("负载越高，随机波动越大，需要更长的仿真才能收敛。" if rho > 0.8 and K is None else ""),
                          chart=sim_chart))
    rows = [["利用率 ρ = λ/(cμ)", R.fmt(rho)], ["服务台全空闲概率 P₀", R.fmt(P0)],
            ["顾客需要排队的概率", R.fmt(Pw)],
            ["系统平均顾客数 L", R.fmt(L)], ["平均队长 Lq", R.fmt(Lq)],
            ["平均逗留时间 W", R.fmt(W)], ["平均等待时间 Wq", R.fmt(Wq)]]
    if K:
        rows += [["满员（被拒）概率 P_K", R.fmt(pn(K))], ["有效到达率 λ_eff", R.fmt(lam_eff)]]
    return R.report("optimal",
                    headline=f"{name}：L = {R.fmt(L)}，Lq = {R.fmt(Lq)}，W = {R.fmt(W)}，Wq = {R.fmt(Wq)}",
                    tables=[R.table(f"{name} 稳态指标", ["指标", "值"], rows)],
                    chart=chart, steps=frames,
                    notes=["时间单位与 λ、μ 一致（如 λ 为人/小时，则 W 单位为小时）。",
                           "Little 公式 L = λW 对几乎所有稳定排队系统都成立。"])


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    for mth in ("mm1", "mmc", "mm1k"):
        print(solve(dict(base, method=mth, **({"lambda": 2} if mth == "mm1" else {})))["headline"])
    print(solve(dict(base, method="mm1"))["headline"])
