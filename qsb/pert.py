"""PERT 计划评审：三点估算 (o/m/p) + 关键路径 + 工期概率（正态近似）。"""
import math
from . import report as R

SPEC = {
    "desc": "PERT 三点估算：每项活动给乐观 o、最可能 m、悲观 p，期望 te=(o+4m+p)/6、方差=((p-o)/6)^2。"
            "求关键路径（期望最长路径），给出项目期望工期、标准差，以及『在某时点前完成』的概率 Φ((T-te)/σ)。",
    "form": [
        {"id": "edges", "type": "textarea", "label": "活动（每行 前驱>后继>o>m>p）",
         "value": "1>2>2>3>5\n1>3>3>4>6\n2>4>4>6>8\n3>5>2>3>4\n4>5>1>2>3"},
        {"id": "T", "type": "float", "label": "目标工期 T（用于完成概率）", "value": "12"},
    ],
}


def _norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _lines(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    acts, nodes = [], set()
    for ln in _lines(p["edges"]):
        parts = [t for t in ln.replace(">", " ").split() if t]
        if len(parts) < 5:
            continue
        f, t, o, m, pp = parts[0], parts[1], float(parts[2]), float(parts[3]), float(parts[4])
        te = (o + 4 * m + pp) / 6.0
        var = ((pp - o) / 6.0) ** 2
        acts.append((f, t, te, var))
        nodes.add(f); nodes.add(t)
    if not acts:
        return R.error("无有效活动。格式：每行 前驱>后继>o>m>p。")

    indeg = {n: 0 for n in nodes}
    adj = {n: [] for n in nodes}
    for f, t, te, var in acts:
        adj[f].append(t); indeg[t] += 1
    from collections import deque
    q = deque([n for n in nodes if indeg[n] == 0])
    topo = []
    while q:
        n = q.popleft(); topo.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(topo) != len(nodes):
        return R.error("活动网络含环，不是合法 DAG，无法求关键路径。")

    es = {n: 0.0 for n in nodes}
    best = {}
    for n in topo:
        for m in adj[n]:
            te_a, var_a = next((a[2], a[3]) for a in acts if a[0] == n and a[1] == m)
            if es[n] + te_a > es[m]:
                es[m] = es[n] + te_a
                best[m] = n
    duration = max(es.values())
    end = max(es, key=lambda n: es[n])
    path = [end]
    while path[-1] in best:
        path.append(best[path[-1]])
    path.reverse()
    crit = [a for a in acts if a[0] in path and a[1] in path and
            abs(es[a[1]] - (es[a[0]] + a[2])) < 1e-9]
    sd = math.sqrt(sum(v for _, _, _, v in crit))
    T = float(p.get("T", duration))
    prob = _norm_cdf((T - duration) / sd) if sd > 0 else (1.0 if T >= duration else 0.0)

    rows = [[a[0], a[1], R.fmt(a[2]), R.fmt(a[3])] for a in acts]
    return R.report(
        "optimal",
        headline=f"关键路径 {'→'.join(path)}：期望工期 {R.fmt(duration)}，σ = {R.fmt(sd)}，P(≤{R.fmt(T)}) = {R.fmt(prob)}",
        tables=[R.table("活动三点估算", ["前驱", "后继", "期望 te", "方差"], rows)],
        notes=[
            "te=(o+4m+p)/6；σ²=Σ((p-o)/6)²（仅关键路径上）。",
            f"项目完成时间近似正态 N({R.fmt(duration)}, {R.fmt(sd)}²)。",
            f"在 {R.fmt(T)} 前完成 = Φ(({R.fmt(T)}-{R.fmt(duration)})/{R.fmt(sd)}) = {R.fmt(prob)}。",
        ])


if __name__ == "__main__":
    print(solve({"edges": "1>2>2>3>5\n1>3>3>4>6\n2>4>4>6>8\n3>5>2>3>4\n4>5>1>2>3", "T": 12})["headline"])
