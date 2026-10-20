"""库存模型：EOQ 经济订货批量、报童模型 (正态需求)。"""
import math
from . import report as R

SPEC = {
    "desc": "库存决策：EOQ 经济订货批量（订货/持有成本平衡）与报童模型（临界分位定最优订货量，正态需求）。",
    "form": [
        {"id": "method", "type": "select", "label": "模型", "value": "eoq", "options": [
            {"v": "eoq", "t": "EOQ 经济订货量"},
            {"v": "news", "t": "报童模型 (Newsboy)"}]},
        {"id": "D", "type": "float", "label": "年需求量 D (EOQ)", "value": "10000"},
        {"id": "S", "type": "float", "label": "每次订货成本 S (EOQ)", "value": "50"},
        {"id": "H", "type": "float", "label": "单位年持有成本 H (EOQ)", "value": "2"},
        {"id": "price", "type": "float", "label": "单位采购价 p (可选)", "value": "10"},
        {"id": "mu", "type": "float", "label": "需求均值 μ (报童)", "value": "100"},
        {"id": "sigma", "type": "float", "label": "需求标准差 σ (报童)", "value": "20"},
        {"id": "sell", "type": "float", "label": "单位售价 (报童)", "value": "12"},
        {"id": "cost", "type": "float", "label": "单位成本 (报童)", "value": "8"},
        {"id": "salvage", "type": "float", "label": "单位残值 (报童)", "value": "5"},
    ],
}


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def _norm_ppf(p):
    # 在 erf 版标准正态 CDF 上二分求逆（稳健，无需查表/近似系数）
    if p <= 0:
        return -math.inf
    if p >= 1:
        return math.inf
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def solve(p):
    m = p["method"]
    if m == "eoq":
        D = float(p["D"]); S = float(p["S"]); H = float(p["H"]); price = float(p.get("price") or 0)
        if D <= 0 or S <= 0 or H <= 0:
            return R.report("error", headline="D、S、H 必须为正")
        Q = math.sqrt(2 * D * S / H)
        no = D / Q
        tc = (D / Q) * S + (Q / 2) * H
        rows = [["经济订货批量 Q* = √(2DS/H)", R.fmt(Q)],
                ["年订货次数 D/Q", R.fmt(no)],
                ["订货周期 (天)", R.fmt(365.0 / no if no else 0)],
                ["年订货成本 (D/Q)·S", R.fmt((D / Q) * S)],
                ["年持有成本 (Q/2)·H", R.fmt((Q / 2) * H)]]
        if price:
            tc += D * price
            rows.append(["年总成本 (含采购 D·p)", R.fmt(tc)])
        return R.report("optimal", headline=f"EOQ = {R.fmt(Q)}，年订货 {R.fmt(no)} 次",
                        tables=[R.table("EOQ 结果", ["指标", "值"], rows)],
                        notes=["在订货成本 (D/Q)·S 与持有成本 (Q/2)·H 相等处取得最优。"])
    # 报童
    mu = float(p["mu"]); sigma = float(p["sigma"]); sell = float(p["sell"]); cost = float(p["cost"]); sv = float(p["salvage"])
    if sigma <= 0:
        return R.report("error", headline="报童模型 σ 必须为正")
    Cu = sell - cost; Co = cost - sv
    cr = Cu / (Cu + Co) if (Cu + Co) > 0 else 0.5
    z = _norm_ppf(cr)
    Q = mu + z * sigma
    tb = R.table("报童模型", ["量", "值"], [
        ["欠货成本 Cu = 售价-成本", R.fmt(Cu)],
        ["过货成本 Co = 成本-残值", R.fmt(Co)],
        ["临界分位 Cu/(Cu+Co)", R.fmt(cr)],
        ["对应标准正态 z 值", R.fmt(z)],
        ["最优订货量 Q = μ + z·σ", R.fmt(Q)]])
    return R.report("optimal", headline=f"报童最优订货量 Q = {R.fmt(Q)}（服务水平 {R.fmt(100 * cr)}%）",
                    tables=[tb],
                    notes=["最优订货量满足 P(D≤Q)=Cu/(Cu+Co)；需求设为正态 N(μ,σ²)。"])


if __name__ == "__main__":
    print(solve({"method": "eoq", "D": 10000, "S": 50, "H": 2, "price": 10})["headline"])
    print(solve({"method": "news", "mu": 100, "sigma": 20, "sell": 12, "cost": 8, "salvage": 5})["headline"])
    print("ppf(0.95)=", round(_norm_ppf(0.95), 4), "(expect ~1.6449)")
