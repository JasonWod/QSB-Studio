# QSB Studio

**运筹学交互式教学工作台** —— 类 WinQSB 的教学软件：19 个求解模块，每个模块都能**逐步播放算法过程**，做完题还能读到算法原理。

An interactive Operations Research teaching workbench — 19 solvers, every one with a step-by-step animated walkthrough and built-in Chinese explanations.

[![CI](https://github.com/JasonWod/QSB-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonWod/QSB-Studio/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-stdlib--only-green)

QSB Studio 解决运筹学课上「答案抄得会，过程看不懂」的问题：填入题目后，它不只给最优解，
而是把**求解过程一步步摊开**——单纯形的每次枢轴、分支定界树如何生长、Dijkstra 如何逐个永久标号、
匈牙利算法怎样划线、伏格尔法和位势法怎样调整运量……每一步都配有中文解说，可以播放、暂停、逐步前进后退。

**Clean-room 声明**：本项目为独立实现，不是 WinQSB 的反编译、移植或拷贝。所有算法按教科书原理自行编写，
未使用任何第三方软件的代码、资源或数据文件。

## 下载即用（老师 / 学生）

到 [Releases](https://github.com/JasonWod/QSB-Studio/releases) 下载：

| 系统 | 文件 | 用法 |
|---|---|---|
| Windows 10/11 (64 位) | `QSB-Studio-Windows-x64.exe` | 双击运行。首次运行约需几秒解压，之后秒开。 |
| macOS 11+（Apple 芯片与 Intel 通用） | `QSB-Studio-macOS.zip` | 解压后把「QSB Studio.app」拖进「应用程序」。 |

程序会在默认浏览器中打开界面（数据全部在本机计算，不联网）。在页面左下角点「退出程序」即可退出；
关闭浏览器页面约 3 分钟后程序也会自动退出。

**首次打开的安全提示**：应用未购买代码签名证书，系统会提示一次：
- Windows：「Windows 已保护你的电脑」→ 点「更多信息」→「仍要运行」。
- macOS：右键（或按住 Control 点按）应用 →「打开」→「打开」；macOS 15 起若无此选项，先双击一次，
  再到「系统设置 → 隐私与安全性」点「仍要打开」。也可在终端执行
  `xattr -dr com.apple.quarantine "/Applications/QSB Studio.app"`。

## 模块覆盖（19 个，全部带动态演示）

| 分类 | 模块 | 算法与演示内容 |
|---|---|---|
| — | 📊 线性规划 | 大 M 单纯形（退化时自动切换 Bland 规则防循环）；逐步枢轴表 + 2 变量图解中的顶点路径；影子价格与灵敏度分析 |
| 优化 | 🔢 整数规划 | 分支定界（界最好优先），支持整数 / 0-1 / 连续变量混合；演示分支树逐节点生长与剪枝 |
| 优化 | 📈 非线性规划 | 自定义 f(x,y) 与约束；最速下降（Armijo）或 BFGS，罚函数法处理约束；热力图上画迭代路径 |
| 优化 | ⚡ 二次规划 | 有效集法，一般线性约束；演示有效集的加入 / 移出与 KKT 乘子检验 |
| 优化 | 🎯 目标规划 | 优先级（逐级求解）与加权两种模式；逐级展示偏差 |
| 网络与运输 | 🚚 运输问题 | 伏格尔法初始解 → 位势法（MODI）检验数 → 闭回路调整；含退化处理与虚拟产地/销地 |
| 网络与运输 | 👥 指派问题 | 匈牙利算法（划线法）：行列归约、最少直线覆盖、矩阵调整；支持最大化与非方阵 |
| 网络与运输 | 🧭 最短路 | Dijkstra，有向 / 无向；逐步永久标号与松弛 |
| 网络与运输 | 🌲 最小生成树 | Kruskal（避圈法）或 Prim（加点法）；逐边接受 / 拒绝 |
| 网络与运输 | 🌊 网络最大流 | Edmonds-Karp 逐次增广，最后标出最小割 |
| 网络与运输 | 🗺️ 旅行商 | Held-Karp 动态规划精确解（≤12 城）；最近邻 + 2-opt 启发式 |
| 决策与规划 | 🪜 动态规划 | 0/1 背包逐行填表与回溯；驿站马车（多阶段最短路）逆序递推 |
| 决策与规划 | 🎲 决策分析 | EMV / 悲观 / 乐观 / 折中 / 等可能 / 最小遗憾 / EVPI；贝叶斯修正与 EVSI；二人零和博弈（鞍点 / 混合策略） |
| 决策与规划 | 🚉 排队论 | M/M/1、M/M/c、M/M/1/K：生灭过程 → 稳态分布 → Little 公式 → 仿真验证 |
| 决策与规划 | 🎰 仿真 | 蒙特卡洛（直方图逼近理论分布、大数定律）；单服务台离散事件仿真表 |
| 数据与统计 | 📆 预测 | 移动平均、指数平滑、Holt、线性回归；逐期公式代入，MAD / MSE / MAPE |
| 数据与统计 | 📦 库存理论 | EOQ（成本曲线扫描、锯齿图、再订货点）；报童模型（边际分析、期望利润曲线） |
| 数据与统计 | 🗓️ 项目计划 | PERT / CPM：正推 ES、逆推 LF、总时差 / 自由时差、关键路线、按期完工概率 |
| 数据与统计 | 🧮 统计分析 | 描述统计；单样本 / 双样本 / 配对 t 检验；卡方拟合；相关与回归。图上标出拒绝域 |

## 从源码运行（开发 / 课堂服务器）

只需要 Python 3.9 或更高版本，**不需要安装任何第三方包**：

```bash
python3 app.py                      # 打开 http://127.0.0.1:8000
python3 app.py --desktop            # 桌面模式：自动选端口、打开浏览器、页面关闭后自动退出
python3 app.py --host 0.0.0.0 --port 8000   # 机房局域网共享（请配合防火墙使用）
```

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

测试包括教科书例题，以及与穷举法 / 独立算法的随机对拍（LP 顶点枚举、整数规划穷举、运输问题 vs LP、
指派 vs 全排列、最短路 vs Floyd、最大流 vs 最小割、TSP vs 全排列、背包 vs 穷举等），
还有对全部模块的输入模糊测试，保证任何错误输入都只会得到友好的提示。

## 打包 Windows / macOS 应用

```bash
python3 packaging/build.py            # 产物在 dist/
```

在 Linux、macOS 或 Windows 上都能构建两个平台的应用，不需要目标系统：程序只依赖 Python 标准库，
所以直接内置 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 的独立运行时
（下载后做 SHA256 校验，并裁剪掉 Tk、测试包等无用组件），Windows 启动器用 Go 交叉编译成单个 exe。
需要 Go 1.21+；装有 `llvm-rc`/`llvm-cvtres` 时会给 exe 嵌入图标与版本信息。

推送 `v*` 标签时，GitHub Actions 会自动构建，并在真实的 Windows、Apple 芯片 Mac 与 Intel Mac 上启动应用做冒烟测试，
通过后把两个文件发布到 Releases。

## HTTP API

前端与任何脚本都走同一套无状态 JSON 接口：

| 方法与路径 | 作用 |
|---|---|
| `GET /api/health` | 健康检查 |
| `GET /api/modules` | 全部模块元数据：名称、分类、算法说明 `explain`、动态表单 `form`（含逐字段帮助） |
| `POST /api/solve/{mid}` | 求解，body 为该模块的 JSON payload |

模块 id：`lp` `ilp` `nlp` `qp` `gp` `transport` `assign` `shortest` `mst` `maxflow` `tsp` `dp` `da` `queue` `sim` `forecast` `inventory` `pert` `stats`。

```bash
curl -s -X POST localhost:8000/api/solve/shortest \
  -d '{"edges":"0 1 4\n0 2 2\n1 2 5\n1 3 10\n2 4 3\n4 3 4","source":0,"target":3}'
```

通用模块（除 LP 外）统一返回：

```jsonc
{
  "status": "optimal",               // optimal / ok / infeasible / unbounded / unstable / error …
  "headline": "0 → 3 最短距离 = 9",
  "message": null,                   // 出错时为给学生看的中文提示
  "tables": [{ "title": "...", "headers": [...], "rows": [[...]], "cells": {"0,1": "c-good"} }],
  "notes":  ["..."],
  "graph":  { "nodes": [...], "edges": [...] },   // 或 "chart": {...}
  "steps":  [ { "title": "第 1 步：确定节点 0", "text": "…", "graph": {...}, "tables": [...] } ]  // 动态演示帧
}
```

输入错误返回 `status: "error"` 与具体说明（如「约束「6,4 <= x」右端应为一个数」），不会抛出服务器异常。

## 加一个新模块

1. 新建 `qsb/<id>.py`，提供 `SPEC = {"desc": ..., "form": [...]}` 与 `solve(payload)`；用 `qsb/parse.py` 解析输入，
   用 `qsb/report.py` 的 `report()` / `table()` / `frame()` 返回结果与演示帧；输入有误时 `raise InputError("说明")`。
2. 在 `qsb/explain.py` 补 `EXPLAIN["<id>"]`（算法说明）与 `HELP["<id>"]`（逐字段帮助）。
3. 在 `qsb/modules.py` 注册一行 `_reg(...)`。前端无需改动。

## 目录结构

```
qsb-studio/
├── app.py                 # 标准库 HTTP 服务器 + 桌面模式（单实例、自动开浏览器、自动退出）
├── qsb/
│   ├── api.py             # 请求校验、错误处理（与 Web 框架无关）
│   ├── modules.py         # 模块注册表
│   ├── report.py          # 统一结果结构与演示帧
│   ├── parse.py           # 输入解析（兼容字符串与数组）
│   ├── expr.py            # 安全的数学表达式求值（AST 白名单）
│   ├── graphviz.py        # 网络图布局（圆环 / 二分 / 分层 / 树）
│   ├── explain.py         # 教学文案
│   └── <id>.py            # 19 个求解模块
├── static/                # 前端（原生 JS，无构建步骤）：演示播放器、SVG 网络图、Canvas 图表
├── tests/                 # 单元测试与对拍测试
├── packaging/             # 打包脚本、Go 启动器、图标
└── .github/workflows/     # CI 与自动发布
```

## License

[MIT License](LICENSE) · Copyright © 2026 JasonWod

WinQSB 为第三方既有软件，与本项目无任何关联；本项目未使用其代码或资源，仅面向相同的教学场景独立实现。
