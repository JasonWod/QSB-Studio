"""动态规划：0/1 背包（自底向上填表 + 回溯选品）。DP 的典型教学范例。"""
from . import report as R

SPEC = {
    "desc": "0/1 背包：n 件物品各有重量 w 与价值 v，背包容量 W。自底向上填 dp[i][c]=前 i 件容量 c 的最大价值，"
            "再回溯出选中的物品。DP 状态转移 + 最优子结构的经典演示。",
    "form": [
        {"id": "W", "type": "int", "label": "背包容量 W", "value": "10"},
        {"id": "items", "type": "textarea", "label": "物品（每行 重量>价值）",
         "value": "2>3\n3>4\n4>5\n5>8\n9>10"},
    ],
}


def _lines(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def solve(p):
    W = max(0, int(p["W"]))
    objs = []
    for ln in _lines(p["items"]):
        parts = [t for t in ln.replace(">", " ").split() if t]
        if len(parts) >= 2:
            objs.append((int(float(parts[0])), int(float(parts[1]))))
    if not objs:
        return R.error("无有效物品。格式：每行 重量>价值。")
    n = len(objs)
    dp = [[0] * (W + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w, v = objs[i - 1]
        for c in range(W + 1):
            dp[i][c] = dp[i - 1][c]
            if w <= c and dp[i - 1][c - w] + v > dp[i][c]:
                dp[i][c] = dp[i - 1][c - w] + v
    chosen, c = [], W
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]:
            w, _ = objs[i - 1]
            chosen.append(i - 1); c -= w
    chosen.reverse()
    used_w = sum(objs[i][0] for i in chosen)
    total_v = dp[n][W]
    tbl_rows = []
    for i in range(1, n + 1):
        tbl_rows.append([f"i={i}"] + [str(dp[i][c]) for c in range(W + 1)])
    return R.report(
        "optimal",
        headline=f"最优价值 = {R.fmt(total_v)}，选 {len(chosen)} 件，总重 {R.fmt(used_w)}/{W}",
        tables=[
            R.table(f"0/1 背包 DP 表 (n={n}, W={W})", ["物品\\容量"] + [str(c) for c in range(W + 1)], tbl_rows),
            R.table("选中的物品", ["序号", "重量", "价值"], [[i + 1, objs[i][0], objs[i][1]] for i in chosen]),
        ],
        notes=[
            "状态转移：dp[i][c] = max(dp[i-1][c], dp[i-1][c-w_i]+v_i)。",
            "自底向上填表 + 从 dp[n][W] 回溯得到选中的物品集合。",
            f"背包容量 W={W}，实际用重 {used_w}，剩余 {W - used_w}。",
        ])


if __name__ == "__main__":
    print(solve({"W": 10, "items": "2>3\n3>4\n4>5\n5>8\n9>10"})["headline"])
