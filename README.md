# QSB Studio

**运筹学交互式教学工作台** —— 类 WinQSB 的在线实验平台：19 个求解模块，线性规划分步单纯形动画，做完题还能读到算法原理。

An interactive Operations Research teaching workbench — 19 solvers with step-by-step simplex animation, network visualization, and built-in Chinese algorithm explanations.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Solver deps: none](https://img.shields.io/badge/solver%20dependencies-stdlib--only-green)
![Frontend: vanilla JS](https://img.shields.io/badge/frontend-vanilla%20JS-orange)

QSB Studio 解决的是运筹学课上「答案抄得会，过程看不懂」的问题：你填入题目，它不只给最优解，
而是把**求解过程**摊开——单纯形的每一轮枢轴、可行域的每个顶点、最短路高亮在网络图上、关键路径标在项目网络中，
并在结果旁直接附上该算法的原理、复杂度与适用条件。

**Clean-room 声明**：本项目为独立实现，不是 WinQSB 的反编译、移植或模仿拷贝。
所有算法按教科书原理自行编写，未使用任何第三方软件的代码、资源或数据文件；
Web 界面为自研，可安全用于教学、二次开发与公开发布。

## 特性

- **分步枢轴动画**：大M法 + 字典法单纯形，逐轮枢轴可前进/回退，每步都带中文文字说明（基变量换进换出、检验数如何变号）
- **2 变量图解**：各约束线方程、可行域顶点、最优点一次画出，配合目标函数等值线理解「为什么最优解在顶点」
- **影子价格与灵敏度**：显式求基逆 `B⁻¹` 得对偶值 `y = c_Bᵀ B⁻¹`，直接读出「资源再加 1 单位值多少钱」
- **网络图可视化**：最短路 / 最小生成树 / 最大流 / TSP / 运输 / 指派 的结果高亮在环形网络图上，源汇点自动着色
- **算法说明随题输出**：每个模块内置 `explain` 文案（原理 + 复杂度 + 适用条件），学生做完题即读到，不用另翻书
- **逐字段帮助**：表单每个输入框都有 hover 提示，不先懂符号也敢填
- **后端驱动表单**：18 个通用模块的输入界面由后端 `SPEC` 描述自动渲染，加字段不用动前端 JS
- **算法零第三方依赖**：全部求解代码只用 Python 标准库（无 numpy / scipy / 任何求解器），机房离线环境照样跑
- **中文排版与打印**：结果按实验报告格式呈现，可直接打印交作业

## 模块覆盖（19 个，全部已实现）

| 分类 | 模块 | 算法与要点 |
|---|---|---|
| — | 📊 **线性规划 LP** | 大M法 + 字典法单纯形；逐步枢轴动画；`B⁻¹` 影子价格与 reduced cost；2 变量图解；max/min、≤/≥/= |
| 优化 | 🔢 整数规划 ILP | 分支定界法，支持纯整数 / 0-1 / 混合整数 |
| 优化 | 📈 非线性规划 NLP | 非线性目标 + 线性/非线性约束（梯度法 / 惩罚法） |
| 优化 | ⚡ 二次规划 QP | 二次目标 + 线性约束 |
| 优化 | 🎯 目标规划 GP | 优先式(preemptive) 与加权(Archimedean) 多目标 |
| 网络与运输 | 🚚 运输问题 | 伏格尔(Vogel) 初始基可行解 + 位势法最优性检验，产销平衡 |
| 网络与运输 | 👥 指派问题 | 匈牙利算法，n 人 n 任务最优指派 |
| 网络与运输 | 🧭 最短路 | Dijkstra，堆优化 `O((V+E) log V)`，单源到各点距离与路径 |
| 网络与运输 | 🌲 最小生成树 | Kruskal + 并查集 |
| 网络与运输 | 🌊 网络最大流 | Edmonds-Karp（BFS 增广路） |
| 网络与运输 | 🗺️ 旅行商 TSP | `n ≤ 8` 全排列精确解；`n > 8` 最近邻 + 2-opt 启发式 |
| 决策与规划 | 🪜 动态规划 DP | 0-1 背包、驿站马车(stagecoach) 等序贯决策 |
| 决策与规划 | 🎲 决策分析 DA | 决策树 / EMV / 贝叶斯后验 / 二人零和博弈 |
| 决策与规划 | 🚉 排队论 | M/M/1、M/M/c 的队长、等待时间与服务利用率 |
| 决策与规划 | 🎰 仿真 | 蒙特卡洛 / 离散事件仿真，可固定随机种子复现 |
| 数据与统计 | 📆 预测 | 移动平均、指数平滑(Holt)、线性回归趋势 |
| 数据与统计 | 📦 库存理论 | EOQ 经济订货批量、报童模型(newsvendor) |
| 数据与统计 | 🗓️ 项目计划 | PERT / CPM 关键路径、活动工期与松弛时间 |
| 数据与统计 | 🧮 统计分析 | 描述统计、假设检验、相关与回归、抽样检验 |

## 快速开始

```bash
cd ~/projects/qsb-studio

# 建议用虚拟环境（依赖只装在 .venv/ 内，已被 .gitignore 排除）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 启动服务（端口换成你机器上空着的即可）
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000> 即可使用。自检：

```bash
curl -s localhost:8000/api/health
# {"ok":true,"service":"qsb-studio","modules":19}
```

> **端口提示**：本项目在 5000 端口上会被系统 `airtap` 服务占用，请避开；`--reload` 便于开发但会持续刷 stderr 日志。
> Web 层只需要 `fastapi` + `uvicorn` 两个包；求解算法本身零依赖，把 `qsb/` 单独拷走也能 `import`。

## HTTP API

前端与任何第三方客户端统一走这套无状态 JSON 接口，可直接用脚本批量跑题、集成进作业系统。

| 方法与路径 | 作用 |
|---|---|
| `GET /api/health` | 健康检查，返回服务名与模块数量 |
| `GET /api/modules` | 全部模块元数据：中英文名、分类、图标、`status`、`has_graph`、算法说明 `explain`、动态表单描述 `form` |
| `POST /api/solve/{mid}` | 提交题目求解，body 为该模块 payload |

模块 id 见上表英文缩写（`lp` `ilp` `nlp` `qp` `gp` `transport` `assign` `shortest` `mst` `maxflow` `tsp` `dp` `da` `queue` `sim` `forecast` `inventory` `pert` `stats`）。
未知 id 返回 `404 {"detail":"unknown module: xxx"}`。

### 通用模块（18 个）的响应形状

所有通用模块经 `qsb/report.py` 归一成同一形状，前端一个渲染器通吃：

```bash
curl -s -X POST localhost:8000/api/solve/shortest \
  -H 'Content-Type: application/json' \
  -d '{"edges":"0 1 2\n0 2 5\n1 2 4\n1 3 1\n2 3 8\n2 4 10\n3 4 3","source":0,"target":4}'
```

```jsonc
{
  "status": "optimal",
  "headline": "0 → 4 最短距离 = 6",
  "tables": [{ "title": "最短距离表", "headers": ["节点","最短距离","路径"], "rows": [["4","6","0→1→3→4"]] }],
  "notes":  ["Dijkstra：贪心 + 优先队列；边权须非负。"],
  "chart":  null,
  "graph":  { "nodes": [...], "edges": [...] }   // 前端网络图，最短路边被标记为 "path"
}
```

### LP（定制前端）的响应形状

LP 需要驱动分步动画与图解，返回的是专属结构，字段比通用形状丰富：

```bash
curl -s -X POST localhost:8000/api/solve/lp \
  -H 'Content-Type: application/json' \
  -d '{"obj":"max","c":[3,5],"A":[[1,0],[0,2],[3,2]],"b":[4,12,18],"senses":["le","le","le"],"var_names":["x1","x2"]}'
```

```jsonc
{
  "status": "optimal",
  "objective": "max",
  "objective_value_display": "36.0",
  "solution": { "x1": 2.0, "x2": 6.0 },
  "num_pivots": 2,
  "steps": [ { "phase": "...", "basis": [...], "columns": [...], "rows": [...], "objective": ..., "objective_value": ... } ],
  "final_tableau":  { ... },
  "shadow_prices":  { "约束1": 0.0, "约束2": 1.5, "约束3": 1.0 },
  "reduced_costs":  { ... },
  "sensitivity":    { ... },
  "graph":          { ... }   // 2 变量图解：约束线、可行域顶点、最优点
}
```

`steps[]` 就是动画的逐帧数据：每帧一份完整单纯形表 + 当前基，前端按序播放即可。

## 加一个新模块（3 步，不用动前端）

除 LP 之外，其余 18 个模块共用一套「后端描述 → 前端渲染」的通用管线。新增模块：

**1. 新建 `qsb/<id>.py`，暴露 `SPEC` 与 `solve`：**

```python
"""<模块说明>"""
from . import report as R

SPEC = {
    "desc": "一句话简介（显示在模块卡片上）",
    "form": [
        {"id": "edges", "type": "textarea", "label": "边 (每行: u v w)", "rows": 8,
         "value": "0 1 4\n0 2 3"},          # 默认值即示例题
        {"id": "source", "type": "int", "label": "源点", "value": "0"},
    ],
}

def solve(payload: dict) -> dict:
    ...
    return R.report("optimal", headline="...",
                   tables=[R.table("结果表", ["列1", "列2"], [["a", 1]])],
                   notes=["算法要点提示"])
```

表单字段 `type` 支持 `int` / `textarea` 等，前端据此渲染对应控件；`value` 作为预填示例，学生一进来就有题可算。

**2. 在 `qsb/explain.py` 补两段文案：** `EXPLAIN["<id>"]`（算法原理、复杂度、适用条件）与 `HELP["<id>"]`（逐字段 hover 帮助，按 `form` 里的 `id` 对应）。

**3. 在 `qsb/modules.py` 注册一行：**

```python
_reg("mymod", "我的模块", "My Module", "简介", "分类", "🧩"),
```

注册表会自动 `importlib` 加载并判定：`solve` 与 `SPEC` 都在 → `status="ready"`，前端立即出现；
缺任何一个 → 自动降级为 `status="stub"` 骨架，**不会抛异常拖垮整个模块列表**。想产网络图，把 id 加进 `_GRAPH_MODS` 即可。

## 目录结构

```
qsb-studio/
├── app.py                  # FastAPI 入口：3 个 API 路由 + 静态目录挂载
├── requirements.txt        # 仅 fastapi / uvicorn
├── qsb/                    # 求解核心（全部纯标准库）
│   ├── modules.py          # 19 个模块注册表：动态加载、降级、元数据导出
│   ├── explain.py          # 集中维护教学文案：EXPLAIN(算法说明) + HELP(逐字段帮助)
│   ├── lp.py               # LP 定制算法：大M字典法单纯形、B⁻¹ 影子价格、2变量图解
│   ├── report.py           # 统一结果结构 report()/table()/fmt()，保证前端单渲染器
│   ├── graphviz.py         # 网络图几何生成：环形布局、分组着色、路径高亮
│   └── <id>.py             # 18 个通用模块，各暴露 SPEC + solve
└── static/                 # 前端（原生 JS，无构建步骤）
    ├── index.html          # 页面骨架
    ├── app.js              # 模块列表、动态表单、动画播放、图表/网络图渲染
    └── style.css           # 中文排版与打印样式
```

## License

本项目采用 [MIT License](LICENSE) · Copyright © 2026 JasonWod

WinQSB 为第三方既有软件，与本项目无任何关联；本项目未使用其代码或资源，仅面向相同的教学场景独立实现。

