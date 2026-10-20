"""二次规划 (QP)：最小化 x^T Q x + c^T x（Q 对称正定），投影梯度下降 + 盒约束。"""
from . import report as R

SPEC = {
    "desc": "二次规划：目标为二次型 x^T Q x + c^T x（Q 对称正定），约束为变量上下界（盒约束）。"
            "用投影梯度下降迭代到收敛，给出最优点、目标值与迭代路径（可动画）。",
    "form": [
        {"id": "Q", "type": "textarea", "label": "二次矩阵 Q（每行逗号分隔，对称正定）", "value": "2,0\n0,2"},
        {"id": "c", "type": "list", "label": "一次项系数 c（逗号分隔）", "value": "-6, -4"},
        {"id": "bounds", "type": "textarea", "label": "变量上下界（每行 lo,hi；留空=无界）", "value": "0,10\n0,10"},
        {"id": "alpha", "type": "float", "label": "步长 α", "value": "0.2"},
    ],
}


def _rows(v):
    if isinstance(v, list):
        v = "\n".join(str(x) for x in v)
    return [ln for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    Q = []
    for ln in _rows(p["Q"]):
        Q.append([float(x) for x in ln.replace(",", " ").split()])
    c = [float(x) for x in (p["c"] if isinstance(p["c"], list) else str(p["c"]).replace(",", " ").split())]
    n = len(c)
    if len(Q) != n or any(len(r) != n for r in Q):
        return R.error(f"Q 必须是 {n}x{n}，与 c 的维度一致。")
    bounds = []
    for ln in _rows(p.get("bounds", "")):
        parts = [float(x) for x in ln.replace(",", " ").split()]
        if len(parts) == 2:
            bounds.append((parts[0], parts[1]))
    alpha = float(p.get("alpha", 0.2))
    x = [0.0] * n
    if bounds:
        for i in range(n):
            if i < len(bounds):
                lo, hi = bounds[i]
                x[i] = max(lo, min(hi, x[i]))
    path = [x[:]]
    obj = lambda v: sum(Q[i][j] * v[i] * v[j] for i in range(n) for j in range(n)) + sum(c[i] * v[i] for i in range(n))
    for it in range(4000):
        grad = [2.0 * sum(Q[i][j] * x[j] for j in range(n)) + c[i] for i in range(n)]
        gx = [x[i] - alpha * grad[i] for i in range(n)]
        for i in range(n):
            if i < len(bounds):
                gx[i] = max(bounds[i][0], min(bounds[i][1], gx[i]))
        if max(abs(gx[i] - x[i]) for i in range(n)) < 1e-7:
            x = gx
            break
        x = gx
        path.append(x[:])
    f = obj(x)
    return R.report(
        "optimal",
        headline=f"二次规划最优：x = ({', '.join(R.fmt(v) for v in x)})，目标值 = {R.fmt(f)}，迭代 {len(path)} 步",
        tables=[R.table("QP 最优解", ["变量", "值", "下界", "上界"],
                        [[f"x{i+1}", R.fmt(x[i]),
                          (R.fmt(bounds[i][0]) if i < len(bounds) else "−∞"),
                          (R.fmt(bounds[i][1]) if i < len(bounds) else "+∞")] for i in range(n)])],
        chart={"title": "QP 投影梯度下降路径",
               "xlabels": [f"it{i}" for i in range(0, len(path), max(1, len(path)//30))],
               "series": [{"name": "x1", "color": "#2563eb",
                           "values": [v[0] for v in path][::max(1, len(path)//30)]},
                          {"name": "x2", "color": "#8b5cf6",
                           "values": [v[1] for v in path][::max(1, len(path)//30)] if n > 1 else []}]},
        notes=[
            "梯度 ∇ = 2Qx + c；每步 x ← project(x − α∇) 到盒约束。",
            "Q 对称正定时目标凸，投影梯度单调下降到最优。",
        ])


if __name__ == "__main__":
    print(solve({"Q": "2,0\n0,2", "c": "-6,-4", "bounds": "0,10\n0,10", "alpha": 0.2})["headline"])
