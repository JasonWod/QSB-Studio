"""排队论：M/M/1 与 M/M/c（Erlang C）稳态性能指标。"""
import math
from . import report as R

SPEC = {
    "desc": "排队模型：M/M/1 单服务台、M/M/c 多服务台（Erlang C）。给出利用率、排队长度、等待时间等稳态指标。",
    "form": [
        {"id": "method", "type": "select", "label": "模型", "value": "mm1", "options": [
            {"v": "mm1", "t": "M/M/1 单服务台"},
            {"v": "mmc", "t": "M/M/c 多服务台"}]},
        {"id": "lambda", "type": "float", "label": "到达率 λ (顾客/单位时间)", "value": "0.4"},
        {"id": "mu", "type": "float", "label": "服务率 μ (单位时间)", "value": "0.6"},
        {"id": "c", "type": "int", "label": "服务台数 c (M/M/c 用)", "value": "2"},
    ],
}


def _fac(n):
    return math.factorial(n)


def solve(p):
    m = p.get("method", "mm1")
    lam = float(p["lambda"]); mu = float(p["mu"])
    c = 1 if m != "mmc" else max(2, int(p.get("c", 2)))
    rho = lam / (c * mu)
    if rho >= 1:
        return R.report("unstable",
                        headline=f"系统不稳定：利用率 ρ = {R.fmt(rho)} ≥ 1，队列将无限增长")
    if c == 1:
        Lq = rho * rho / (1 - rho); L = rho / (1 - rho)
        Wq = Lq / lam; W = L / lam
        rows = [["利用率 ρ = λ/μ", R.fmt(rho)], ["服务台空闲概率 1-ρ", R.fmt(1 - rho)],
                ["系统平均顾客数 L", R.fmt(L)], ["队列平均长度 Lq", R.fmt(Lq)],
                ["平均停留时间 W = L/λ", R.fmt(W)], ["平均等待时间 Wq = Lq/λ", R.fmt(Wq)]]
        return R.report("optimal",
                        headline=f"M/M/1：Lq = {R.fmt(Lq)}，Wq = {R.fmt(Wq)} 期，ρ = {R.fmt(rho)}",
                        tables=[R.table("M/M/1 指标", ["指标", "值"], rows)],
                        notes=["M/M/1：单服务台，指数到达(λ)与指数服务(μ)。ρ<1 才有稳态。"])
    # M/M/c — Erlang C
    a = lam / mu
    s = 0.0
    for n in range(c):
        s += a ** n / _fac(n)
    term = a ** c / _fac(c) / (1 - rho)
    P0 = 1.0 / (s + term)
    C = term * P0  # Erlang C = 到达者需等待的概率
    Lq = C * rho / (1 - rho); L = Lq + a
    Wq = Lq / lam; W = Wq + 1.0 / mu
    rows = [["利用率 ρ = λ/(cμ)", R.fmt(rho)], ["服务台空闲概率 P0", R.fmt(P0)],
            ["Erlang C（需等待概率）", R.fmt(C)], ["系统平均顾客数 L", R.fmt(L)],
            ["队列平均长度 Lq", R.fmt(Lq)], ["平均停留时间 W = Wq+1/μ", R.fmt(W)],
            ["平均等待时间 Wq = Lq/λ", R.fmt(Wq)]]
    return R.report("optimal",
                    headline=f"M/M/{c}：等待概率 = {R.fmt(C)}，Lq = {R.fmt(Lq)}，Wq = {R.fmt(Wq)}",
                    tables=[R.table(f"M/M/{c} 指标", ["指标", "值"], rows)],
                    notes=[f"c={c} 个服务台，Erlang C 给出到达者需排队等待的概率。"])


if __name__ == "__main__":
    print(solve({"method": "mm1", "lambda": 0.4, "mu": 0.6})["headline"])
    print(solve({"method": "mmc", "lambda": 10, "mu": 6, "c": 2})["headline"])
