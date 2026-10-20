"""
qsb/modules.py — 19 个运筹学模块注册表。

设计：
  * LP 是「定制前端」模块（分步单纯形动画 + 2变量图解 + 灵敏度），单独处理。
  * 其余 18 个走「通用前端」：每个 qsb/<id>.py 提供
        SPEC = {"desc":..., "form":[...]}   # 前端表单描述
        solve(payload) -> {"status","headline","tables","notes"[, "chart"][, "graph"]}
    注册表按 id 去 import 对应文件；import 成功且有 solve+SPEC → status=ready；
    否则自动降级为 status=stub（骨架）。这样未实现的模块不会拖垮整个注册。
  * 教学文案（算法说明 explain + 逐字段 help）集中在 qsb/explain.py，这里负责合并进元数据。
"""
from __future__ import annotations
import importlib
from . import lp
from . import explain as EXPL


# 产出「网络图」可视化的模块（前端据此可优先画网络图）
_GRAPH_MODS = {"shortest", "mst", "maxflow", "tsp", "transport", "assign"}


# ---------------------------------------------------------------------------
# LP —— 唯一定制前端
# ---------------------------------------------------------------------------
def _lp_solve(payload):
    return lp.solve_lp(
        payload["obj"], payload["c"], payload["A"], payload["b"],
        payload["senses"], payload["var_names"],
    )


def _lp_graph(payload, result):
    return lp.graph_2var(
        payload["c"], payload["A"], payload["b"], payload["senses"],
        payload["var_names"], result["solution"], payload["obj"],
    )


# ---------------------------------------------------------------------------
# 通用模块加载
# ---------------------------------------------------------------------------
def _enrich_form(form, mid):
    """把中央文案 EXPL.HELP[mid] 的逐字段解释合并进表单描述。"""
    hmap = EXPL.HELP.get(mid, {})
    out = []
    for f in (form or []):
        nf = dict(f)
        if f.get("id") in hmap:
            nf["help"] = hmap[f["id"]]
        out.append(nf)
    return out


def _reg(mid, name, name_en, desc, category, icon):
    base = {"id": mid, "name": name, "name_en": name_en,
            "desc": desc, "category": category, "icon": icon}
    try:
        mod = importlib.import_module(f"qsb.{mid}")
    except Exception:
        mod = None
    if mod is not None and hasattr(mod, "solve") and hasattr(mod, "SPEC"):
        base.update({
            "status": "ready",
            "has_graph": mid in _GRAPH_MODS,
            "desc": mod.SPEC.get("desc", desc),
            "explain": EXPL.EXPLAIN.get(mid, ""),
            "form": _enrich_form(mod.SPEC.get("form", []), mid),
            "solve": mod.solve,
        })
    else:
        base.update({"status": "stub", "has_graph": False,
                     "explain": EXPL.EXPLAIN.get(mid, ""), "form": []})
    return base


MODULES = [
    {
        "id": "lp", "name": "线性规划", "name_en": "Linear Programming",
        "desc": "大M单纯形法，逐步枢轴迭代；2变量图解；影子价格（灵敏度）。支持 max/min、≤/≥/=、连续非负变量。",
        "category": "优化", "status": "ready", "has_graph": True, "icon": "📊",
        "explain": EXPL.EXPLAIN.get("lp", ""),
        "solve": _lp_solve, "graph": _lp_graph,
    },
    _reg("ilp", "整数规划", "Integer Programming",
         "分支定界法求解整数/0-1/混合整数线性规划。", "优化", "🔢"),
    _reg("nlp", "非线性规划", "Nonlinear Programming",
         "非线性目标 + 线性/非线性约束（梯度法/惩罚法）。", "优化", "📈"),
    _reg("qp", "二次规划", "Quadratic Programming",
         "二次目标 + 线性约束。", "优化", "⚡"),
    _reg("gp", "目标规划", "Goal Programming",
         "多目标按优先级（preemptive）或加权（Archimedan）求解。", "优化", "🎯"),

    _reg("transport", "运输问题", "Transportation Problem",
         "产销平衡最小费用调运（伏格尔法初始解 + 位势法最优性检验）。", "网络与运输", "🚚"),
    _reg("assign", "指派问题", "Assignment Problem",
         "匈牙利算法求 n 人 n 任务最优指派。", "网络与运输", "👥"),
    _reg("shortest", "最短路问题", "Shortest Path",
         "Dijkstra 单源最短路（各点距离与路径）。", "网络与运输", "🧭"),
    _reg("mst", "最小生成树", "Minimum Spanning Tree",
         "Kruskal（并查集）求连通图最小生成树。", "网络与运输", "🌲"),
    _reg("maxflow", "网络最大流", "Maximum Flow",
         "Edmonds-Karp（BFS 增广路）求网络最大流。", "网络与运输", "🌊"),
    _reg("tsp", "旅行商问题", "Traveling Salesman",
         "TSP：n≤8 精确（全排列），n>8 最近邻 + 2-opt 启发式。", "网络与运输", "🗺️"),

    _reg("dp", "动态规划", "Dynamic Planning",
         "背包、驿站马车（stagecoach）等序贯决策。", "决策与规划", "🪜"),
    _reg("da", "决策分析", "Decision Analysis",
         "决策树 / EMV / 贝叶斯 / 二人零和博弈。", "决策与规划", "🎲"),
    _reg("queue", "排队论", "Queuing",
         "M/M/1、M/M/c 排队模型的等待与利用率指标。", "决策与规划", "🚉"),
    _reg("sim", "仿真", "Simulation",
         "蒙特卡洛 / 离散事件仿真，估计随机系统性能。", "决策与规划", "🎰"),

    _reg("forecast", "预测", "Forecasting",
         "移动平均、指数平滑（Holt）、线性回归时间序列预测。", "数据与统计", "📆"),
    _reg("inventory", "库存理论", "Inventory",
         "EOQ 经济订货批量、报童模型。", "数据与统计", "📦"),
    _reg("pert", "项目计划", "PERT/CPM",
         "关键路径法：活动网络、工期与关键路径。", "数据与统计", "🗓️"),
    _reg("stats", "统计分析", "Statistical Analysis",
         "描述统计、假设检验、相关/回归、抽样检验。", "数据与统计", "🧮"),
]

BY_ID = {m["id"]: m for m in MODULES}


def meta_list():
    """给前端的模块元数据（含通用模块的 form 描述、算法说明 explain、逐字段 help）。"""
    out = []
    for m in MODULES:
        out.append({
            "id": m["id"], "name": m["name"], "name_en": m["name_en"],
            "desc": m["desc"], "category": m["category"],
            "icon": m.get("icon", ""), "status": m["status"],
            "has_graph": m.get("has_graph", False),
            "explain": m.get("explain", ""),
            "form": m.get("form", []),
        })
    return out
