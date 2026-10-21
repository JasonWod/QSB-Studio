"""统一结果报告助手：所有通用模块的 solve() 返回同一形状，前端一个渲染器即可。

report 形状::

    {
      "status":   "optimal"|"ok"|"infeasible"|"unbounded"|"unstable"|"error"|...,
      "headline": "最大流 = 10",                 # 大标题一句话
      "message":  None | "错误/提示信息",
      "tables":   [table, ...],
      "notes":    ["...说明..."],
      "chart":    chart | None,                  # 最终结果图（折线/柱状/平面）
      "graph":    graph | None,                  # 最终结果网络图
      "steps":    [frame, ...],                  # 动态演示帧（可逐帧播放）
    }

table 形状::

    {"title", "headers": [...], "rows": [[...]],
     "cells":   {"r,c": "cls", ...},     # 可选：单元格高亮（cls 见 style.css 的 .c-*）
     "rowcls":  {"r": "cls"}, "colcls": {"c": "cls"}}   # 可选：整行/整列高亮

frame（演示帧）形状::

    {"title": "第 3 步：...", "text": "本步发生了什么（可多句）",
     "tables": [...]?, "graph": {...}?, "chart": {...}?}
"""


class InputError(ValueError):
    """用户输入有误。消息直接展示给学生，应写清「哪里错、正确格式是什么」。"""


def report(status, headline=None, tables=None, notes=None, chart=None, graph=None,
           steps=None, message=None, shared=None):
    """shared: 帧间共享的大块数据（如平面图底图网格）。帧里的 chart 写 {"use": "名字"}，
    前端会把 shared[名字] 与该 chart 合并后再画，避免每帧重复传输。"""
    out = {"status": status, "headline": headline, "message": message,
           "tables": tables or [], "notes": notes or [], "chart": chart,
           "graph": graph, "steps": steps or []}
    if shared:
        out["shared"] = shared
    return out


def error(message, headline="输入有误"):
    return report("error", headline=headline, message=message)


def table(title, headers, rows, cells=None, rowcls=None, colcls=None):
    t = {"title": title, "headers": headers, "rows": rows}
    if cells:
        t["cells"] = {f"{r},{c}": v for (r, c), v in cells.items()}
    if rowcls:
        t["rowcls"] = {str(k): v for k, v in rowcls.items()}
    if colcls:
        t["colcls"] = {str(k): v for k, v in colcls.items()}
    return t


def frame(title, text="", tables=None, graph=None, chart=None):
    f = {"title": title, "text": text}
    if tables:
        f["tables"] = tables
    if graph is not None:
        f["graph"] = graph
    if chart is not None:
        f["chart"] = chart
    return f


def fnum(x, nd=4):
    """数字格式化：整数去小数，None->''"""
    if x is None:
        return ""
    if isinstance(x, float):
        if x != x:            # NaN
            return "NaN"
        if x in (float("inf"), float("-inf")):
            return "∞" if x > 0 else "-∞"
        if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
            return int(round(x))
        v = round(x, nd)
        return 0 if v == 0 else v
    return x


def fmt(x, nd=4):
    if x is None:
        return "—"
    return str(fnum(x, nd))


def thin(frames, limit=60):
    """帧太多时均匀抽样，保留首尾帧，避免前端播放过长。"""
    if len(frames) <= limit:
        return frames
    step = (len(frames) - 1) / (limit - 1)
    idx = sorted({round(i * step) for i in range(limit)})
    return [frames[i] for i in idx]
