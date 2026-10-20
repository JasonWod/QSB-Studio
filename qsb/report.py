"""统一结果报告助手：所有模块 solve() 返回同一形状，前端一个通用渲染器即可。

report 形状:
{
  "status":   "optimal"|"ok"|"infeasible"|"unbounded"|"error"|...,
  "headline": "最大流 = 10",                       # 大标题一句话
  "tables":   [ {"title","headers":[...],"rows":[[...]]} ],
  "notes":    ["...说明..."],
  "chart":    { ... }|None,                        # 可选 canvas 图表(后期)
}
"""

def report(status, headline=None, tables=None, notes=None, chart=None, graph=None):
    return {"status": status, "headline": headline, "tables": tables or [],
            "notes": notes or [], "chart": chart, "graph": graph}

def table(title, headers, rows):
    return {"title": title, "headers": headers, "rows": rows}

def fnum(x, nd=4):
    """数字格式化：整数去小数，None->''"""
    if x is None:
        return ""
    if isinstance(x, float) and x == int(x) and abs(x) < 1e15:
        return int(x)
    if isinstance(x, float):
        return round(x, nd)
    return x

def fmt(x, nd=4):
    if x is None:
        return "—"
    return str(fnum(x, nd))
