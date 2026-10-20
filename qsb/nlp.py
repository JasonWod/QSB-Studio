"""非线性规划 (NLP)：回溯线搜索 (Armijo) 梯度下降求解无约束非线性最小化。"""
from . import report as R

FUNCS = {
    "bowl": ("(x-2)^2 + (y-1)^2",
             lambda x, y: (x - 2) ** 2 + (y - 1) ** 2,
             lambda x, y: (2 * (x - 2), 2 * (y - 1))),
    "rosenbrock": ("(1-x)^2 + 100(y-x^2)^2",
                  lambda x, y: (1 - x) ** 2 + 100 * (y - x * x) ** 2,
                  lambda x, y: (-2 * (1 - x) - 400 * x * (y - x * x), 200 * (y - x * x))),
    "booth": ("(x+2y-7)^2 + (2x+y-5)^2",
             lambda x, y: (x + 2 * y - 7) ** 2 + (2 * x + y - 5) ** 2,
             lambda x, y: (2 * (x + 2 * y - 7) + 2 * (2 * x + y - 5),
                           2 * (x + 2 * y - 7) + (2 * x + y - 5))),
}

SPEC = {
    "desc": "非线性规划：最小化给定的二元非线性函数 f(x,y)。用回溯线搜索 (Armijo) 梯度下降从起点迭代到收敛，"
            "给出最优点、函数值与下降路径。内置碗形 / Rosenbrock / Booth 三个经典测试函数。",
    "form": [
        {"id": "func", "type": "select", "label": "目标函数", "value": "bowl",
         "options": [{"v": "bowl", "t": "碗形 (x-2)^2+(y-1)^2"},
                     {"v": "rosenbrock", "t": "Rosenbrock"},
                     {"v": "booth", "t": "Booth"}]},
        {"id": "start", "type": "list", "label": "起点 (x0, y0)", "value": "0, 0"},
    ],
}


def solve(p):
    name = p.get("func", "bowl")
    if name not in FUNCS:
        return R.error("未知函数。可选：bowl / rosenbrock / booth。")
    label, f, g = FUNCS[name]
    s = [float(v) for v in (p["start"] if isinstance(p["start"], list) else str(p["start"]).replace(",", " ").split())]
    x, y = s[0], s[1]
    path = [(x, y, f(x, y))]
    fx = f(x, y)
    for it in range(2000):
        gx, gy = g(x, y)
        grad2 = gx * gx + gy * gy
        if grad2 < 1e-14:
            break
        step = 0.5
        nx, ny = x, y
        while step > 1e-4:
            tx, ty = x - step * gx, y - step * gy
            if f(tx, ty) < fx - 1e-4 * step * grad2:
                nx, ny = tx, ty
                break
            step *= 0.5
        if abs(nx - x) < 1e-9 and abs(ny - y) < 1e-9:
            break
        x, y = nx, ny
        fx = f(x, y)
        path.append((x, y, fx))
    return R.report(
        "optimal",
        headline=f"{label} 最小值 ≈ {R.fmt(fx)}，在 (x, y) = ({R.fmt(x)}, {R.fmt(y)})，{len(path)} 步收敛",
        tables=[R.table("NLP 结果", ["项", "值"],
                        [["函数", label], ["最优点 x", R.fmt(x)], ["最优点 y", R.fmt(y)],
                         ["函数最小值", R.fmt(fx)], ["迭代步数", len(path)],
                         ["起点", f"({s[0]}, {s[1]})"]])],
        chart={"title": f"{label} 梯度下降路径 (f 值)",
               "xlabels": [f"it{i}" for i in range(0, len(path), max(1, len(path)//30))],
               "series": [{"name": "f(x,y)", "color": "#f59e0b",
                           "values": [v[2] for v in path][::max(1, len(path)//30)]}]},
        notes=[
            "回溯线搜索 (Armijo)：沿负梯度方向，逐步缩小步长直到充分下降。",
            "适用于一般可微非线性函数（无约束）。",
        ])


if __name__ == "__main__":
    print(solve({"func": "bowl", "start": "0, 0"})["headline"])
    print(solve({"func": "rosenbrock", "start": "-1.0, 1.0"})["headline"])
