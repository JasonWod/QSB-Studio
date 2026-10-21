"""安全的数学表达式求值（只允许四则、乘方、数学函数和指定变量）。

学生输入 f(x,y) 之类的公式时用：先用 ast 白名单校验，再编译为函数。
所有常数转成 float，防止 9**9**9 这类大整数运算卡死。
"""
import ast
import math

from .report import InputError

FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
    "log": math.log, "ln": math.log, "sqrt": math.sqrt, "abs": abs,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "min": min, "max": max,
}
CONSTS = {"pi": math.pi, "e": math.e}
_BIN = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_UN = (ast.UAdd, ast.USub)


class _Floatify(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(float(node.value)), node)


def compile_expr(src, variables=("x", "y")):
    """返回 (函数, 规范化后的表达式文本)。函数参数顺序同 variables。"""
    text = str(src or "").strip()
    if not text:
        raise InputError("表达式不能为空。")
    if len(text) > 300:
        raise InputError("表达式过长（最多 300 个字符）。")
    text = text.replace("^", "**").replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise InputError(f"表达式「{src}」语法有误。乘号不能省略，如 2*x 而非 2x；乘方用 ^ 或 **。") from None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, _BIN):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _UN):
            continue
        if isinstance(node, (ast.operator, ast.unaryop)):
            if isinstance(node, _BIN + _UN):
                continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            continue
        if isinstance(node, ast.Name) and (node.id in variables or node.id in CONSTS or node.id in FUNCS):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS \
                and not node.keywords:
            continue
        what = getattr(node, "id", None) or type(node).__name__
        raise InputError(f"表达式「{src}」中含不支持的内容「{what}」。可用变量：{', '.join(variables)}；"
                         f"可用函数：{', '.join(sorted(FUNCS))}。")
    tree = ast.fix_missing_locations(_Floatify().visit(tree))
    code = compile(tree, "<expr>", "eval")
    env = {"__builtins__": {}}
    env.update(FUNCS)
    env.update(CONSTS)

    def f(*args):
        local = dict(zip(variables, args))
        try:
            v = eval(code, env, local)  # noqa: S307 — AST 已按白名单校验
        except (ValueError, ZeroDivisionError, OverflowError):
            return float("inf")
        if isinstance(v, complex) or v != v:
            return float("inf")
        return float(v)

    f(*[0.5] * len(variables))   # 试算一次，尽早暴露问题
    return f, text
