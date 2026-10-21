"""库存模型：EOQ 经济订货批量（含再订货点）、报童模型（正态需求）。

演示帧：
  EOQ——订货量 Q 从小到大扫描，成本曲线上标出当前 Q 的订货费、持有费、总费用，最终停在两者相等的 Q*；
        再画出库存水平随时间的锯齿图与再订货点
  报童——展示欠货/过量的边际成本、临界分位，以及期望利润随订货量变化的曲线
"""
import math

from . import parse as P
from . import report as R

SPEC = {
    "desc": "库存决策：EOQ 在订货费 (D/Q)·S 与持有费 (Q/2)·H 之间权衡，Q* = √(2DS/H)，并给出再订货点；"
            "报童模型（一次性订货）用临界分位 Cu/(Cu+Co) 确定最优订货量。",
    "form": [
        {"id": "method", "type": "select", "label": "模型", "value": "eoq", "options": [
            {"v": "eoq", "t": "EOQ 经济订货量"}, {"v": "news", "t": "报童模型"}]},
        {"id": "D", "type": "float", "label": "年需求量 D (EOQ)", "value": "12000"},
        {"id": "S", "type": "float", "label": "每次订货成本 S (EOQ)", "value": "60"},
        {"id": "H", "type": "float", "label": "单位年持有成本 H (EOQ)", "value": "4"},
        {"id": "lead", "type": "float", "label": "订货提前期（天，EOQ）", "value": "6"},
        {"id": "days", "type": "int", "label": "每年工作日（EOQ）", "value": "360"},
        {"id": "mu", "type": "float", "label": "需求均值 μ (报童)", "value": "100"},
        {"id": "sigma", "type": "float", "label": "需求标准差 σ (报童)", "value": "20"},
        {"id": "sell", "type": "float", "label": "单位售价 (报童)", "value": "12"},
        {"id": "cost", "type": "float", "label": "单位进价 (报童)", "value": "8"},
        {"id": "salvage", "type": "float", "label": "单位残值 (报童)", "value": "5"},
    ],
}


def _cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pdf(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def _ppf(p):
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if _cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _eoq(p):
    D = P.num(p, "D", None, "年需求量 D"); S = P.num(p, "S", None, "订货成本 S"); H = P.num(p, "H", None, "持有成本 H")
    if D <= 0 or S <= 0 or H <= 0:
        raise R.InputError("D、S、H 都必须为正。")
    lead = P.num(p, "lead", 0, "提前期", 0)
    days = P.integer(p, "days", 360, "每年工作日", 1, 366)
    Q = math.sqrt(2 * D * S / H)
    oc = lambda q: D / q * S
    hc = lambda q: q / 2 * H
    tc = lambda q: oc(q) + hc(q)
    qs = [Q * f for f in [0.2 + 0.05 * i for i in range(57)]]
    xs = [R.fmt(q, 0) for q in qs]
    base = {"type": "line", "x": xs, "xtitle": "订货量 Q", "title": "年成本 vs 订货量",
            "series": [{"name": "订货费 (D/Q)S", "values": [round(oc(q), 2) for q in qs]},
                       {"name": "持有费 (Q/2)H", "values": [round(hc(q), 2) for q in qs]},
                       {"name": "总成本", "values": [round(tc(q), 2) for q in qs]}]}
    frames = []
    for f in (0.3, 0.5, 0.7, 1.6, 2.4, 1.0):
        q = Q * f
        i = min(range(len(qs)), key=lambda k: abs(qs[k] - q))
        if f == 1.0:
            title = "Q = Q*：两项费用相等，总成本最低"
            text = (f"Q* = √(2DS/H) = √(2×{R.fmt(D)}×{R.fmt(S)}/{R.fmt(H)}) = {R.fmt(Q)}。此时订货费 {R.fmt(oc(Q))} = "
                    f"持有费 {R.fmt(hc(Q))}，总成本 {R.fmt(tc(Q))} 最低。")
        else:
            title = f"试 Q = {R.fmt(q, 0)}"
            text = (f"每年订 {R.fmt(D / q)} 次：订货费 {R.fmt(oc(q))}，持有费 {R.fmt(hc(q))}，总成本 {R.fmt(tc(q))}。"
                    + ("订得太少太勤，订货费偏高。" if f < 1 else "一次订太多，库存积压，持有费偏高。"))
        frames.append(R.frame(title, text, chart=dict(base, hl=i)))
    d = D / days
    rop = d * lead
    cyc = Q / d
    T = cyc * 3
    xs2, ys2 = [], []
    for c in range(3):
        xs2 += [round(c * cyc, 3), round((c + 1) * cyc, 3)]
        ys2 += [round(Q, 3), 0.0]
    saw = {"type": "line", "numx": True, "x": xs2, "xtitle": "天", "title": "库存水平（锯齿图）",
           "series": [{"name": "库存量", "values": ys2},
                      {"name": f"再订货点 {R.fmt(rop)}", "values": [rop] * len(xs2), "dashed": True}]}
    frames.append(R.frame("库存随时间变化",
                          f"每次到货 {R.fmt(Q)} 件，以每天 {R.fmt(d)} 件的速度消耗，{R.fmt(cyc)} 天用完。"
                          f"提前期 {R.fmt(lead)} 天，所以库存降到再订货点 ROP = d×L = {R.fmt(rop)} 时就要下单。", chart=saw))
    rows = [["经济订货批量 Q* = √(2DS/H)", R.fmt(Q)], ["年订货次数 D/Q*", R.fmt(D / Q)],
            ["订货周期（天）", R.fmt(cyc)], ["年订货费", R.fmt(oc(Q))], ["年持有费", R.fmt(hc(Q))],
            ["年总库存成本", R.fmt(tc(Q))], ["日需求量 d", R.fmt(d)], ["再订货点 ROP", R.fmt(rop)]]
    return R.report("optimal", headline=f"EOQ = {R.fmt(Q)}，年订货 {R.fmt(D / Q)} 次，再订货点 {R.fmt(rop)}",
                    tables=[R.table("EOQ 结果", ["指标", "值"], rows)],
                    chart=dict(base, hl=min(range(len(qs)), key=lambda k: abs(qs[k] - Q))), steps=frames,
                    notes=["总成本曲线在 Q* 附近很平坦：订货量偏离 Q* 20%，总成本只增加约 2%。",
                           "模型假设：需求均匀已知、瞬时补货、不允许缺货。"])


def _news(p):
    mu = P.num(p, "mu", None, "需求均值 μ"); sigma = P.num(p, "sigma", None, "标准差 σ")
    sell = P.num(p, "sell", None, "售价"); cost = P.num(p, "cost", None, "进价"); sv = P.num(p, "salvage", None, "残值")
    if sigma <= 0:
        raise R.InputError("需求标准差 σ 必须为正。")
    if not (sv < cost < sell):
        raise R.InputError("需满足 残值 < 进价 < 售价，否则订货决策没有意义。")
    Cu, Co = sell - cost, cost - sv
    cr = Cu / (Cu + Co)
    z = _ppf(cr)
    Q = mu + z * sigma

    def eprofit(q):
        zz = (q - mu) / sigma
        es = sigma * (_pdf(zz) - zz * (1 - _cdf(zz)))   # 期望缺货量
        esales = mu - es
        eleft = q - esales
        return sell * esales + sv * eleft - cost * q
    qs = [mu + sigma * (-3 + 0.1 * i) for i in range(61)]
    qs = [q for q in qs if q >= 0]
    base = {"type": "line", "x": [R.fmt(q, 0) for q in qs], "xtitle": "订货量 Q", "title": "期望利润 vs 订货量",
            "series": [{"name": "期望利润", "values": [round(eprofit(q), 3) for q in qs]}]}
    iq = min(range(len(qs)), key=lambda k: abs(qs[k] - Q))
    frames = [
        R.frame("第 1 步：两种错误的代价", f"多订 1 件卖不掉，亏 Co = 进价 − 残值 = {R.fmt(Co)}；"
                f"少订 1 件错过销售，少赚 Cu = 售价 − 进价 = {R.fmt(Cu)}。", chart=dict(base, hl=0)),
        R.frame("第 2 步：边际分析", f"再多订 1 件值得，当且仅当 P(需求 > Q)·Cu ≥ P(需求 ≤ Q)·Co，"
                f"即 P(需求 ≤ Q) ≤ Cu/(Cu+Co) = {R.fmt(cr)}（临界分位）。", chart=dict(base, hl=iq // 2)),
        R.frame("第 3 步：最优订货量", f"需求 ~ N({R.fmt(mu)}, {R.fmt(sigma)}²)，临界分位 {R.fmt(cr)} 对应 z = {R.fmt(z)}，"
                f"Q* = μ + zσ = {R.fmt(Q)}，期望利润 {R.fmt(eprofit(Q))}（曲线最高点）。", chart=dict(base, hl=iq)),
    ]
    tb = R.table("报童模型", ["量", "值"], [
        ["欠货成本 Cu = 售价 − 进价", R.fmt(Cu)], ["过量成本 Co = 进价 − 残值", R.fmt(Co)],
        ["临界分位 Cu/(Cu+Co)", R.fmt(cr)], ["标准正态 z 值", R.fmt(z)],
        ["最优订货量 Q* = μ + zσ", R.fmt(Q)], ["期望利润", R.fmt(eprofit(Q))]])
    return R.report("optimal", headline=f"报童最优订货量 Q* = {R.fmt(Q)}（服务水平 {R.fmt(100 * cr)}%）",
                    tables=[tb], chart=dict(base, hl=iq), steps=frames,
                    notes=["Cu > Co 时多订（Q* > μ）；Cu < Co 时少订（Q* < μ）。"])


def solve(p):
    return _news(p) if p.get("method") == "news" else _eoq(p)


if __name__ == "__main__":
    base = {f["id"]: f["value"] for f in SPEC["form"]}
    print(solve(base)["headline"])
    print(solve(dict(base, method="news"))["headline"])
