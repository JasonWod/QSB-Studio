"""输入解析工具：所有模块共用。

前端会把 list/matrix 字段解析成数组，脚本调用 API 时也常直接传字符串。
这里统一兼容两种写法，解析失败时抛出带中文说明的 InputError。
"""
import re

from .report import InputError

_SPLIT = re.compile(r"[\s,，;；]+")


def _num(tok, what):
    try:
        v = float(tok)
    except (TypeError, ValueError):
        raise InputError(f"{what}中的「{tok}」不是数字。") from None
    if v != v or v in (float("inf"), float("-inf")):
        raise InputError(f"{what}中出现了非有限数值「{tok}」。")
    return v


def lines(v):
    """多行文本 / 列表 → 非空行列表。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            if isinstance(x, (list, tuple)):
                out.append(" ".join(str(t) for t in x))
            else:
                out.append(str(x))
        return [s.strip() for s in out if s.strip()]
    return [ln.strip() for ln in str(v).splitlines() if ln.strip()]


def nums(v, what="数列"):
    """'1, 2 3' / [1, '2', 3] → [1.0, 2.0, 3.0]。"""
    if v is None:
        return []
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [_num(v, what)]
    if isinstance(v, (list, tuple)):
        toks = []
        for x in v:
            if isinstance(x, (list, tuple)):
                toks.extend(x)
            elif isinstance(x, str):
                toks.extend(t for t in _SPLIT.split(x) if t)
            else:
                toks.append(x)
    else:
        toks = [t for t in _SPLIT.split(str(v)) if t]
    return [_num(t, what) for t in toks]


def matrix(v, what="矩阵"):
    """多行文本 / 二维数组 → 二维 float 列表（每行可不等长，由调用方检查）。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)) and v and all(isinstance(r, (list, tuple)) for r in v):
        rows = [[_num(x, what) for x in r] for r in v]
    else:
        rows = [nums(ln, what) for ln in lines(v)]
    return [r for r in rows if r]


def square(v, what="矩阵", min_n=1, max_n=None):
    m = matrix(v, what)
    n = len(m)
    if n < min_n:
        raise InputError(f"{what}至少需要 {min_n}×{min_n}。")
    if any(len(r) != n for r in m):
        raise InputError(f"{what}必须是方阵：共 {n} 行，但某些行的元素个数不是 {n}。")
    if max_n and n > max_n:
        raise InputError(f"{what}规模 {n}×{n} 超过上限 {max_n}×{max_n}（教学版限制，避免长时间计算）。")
    return m


def num(p, key, default=None, what=None, lo=None, hi=None):
    v = p.get(key, default)
    if v is None or (isinstance(v, str) and not v.strip()):
        if default is None:
            raise InputError(f"缺少「{what or key}」。")
        v = default
    x = _num(v, f"「{what or key}」")
    if lo is not None and x < lo:
        raise InputError(f"「{what or key}」不能小于 {lo}（当前 {x:g}）。")
    if hi is not None and x > hi:
        raise InputError(f"「{what or key}」不能大于 {hi}（当前 {x:g}）。")
    return x


def integer(p, key, default=None, what=None, lo=None, hi=None):
    x = num(p, key, default, what, lo, hi)
    if abs(x - round(x)) > 1e-9:
        raise InputError(f"「{what or key}」必须是整数（当前 {x:g}）。")
    return int(round(x))


def optional_int(p, key):
    v = p.get(key)
    if v is None or (isinstance(v, str) and v.strip() in ("", "None")):
        return None
    return integer(p, key)


_OPS = (("<=", "le"), (">=", "ge"), ("≤", "le"), ("≥", "ge"), ("=", "eq"), ("<", "le"), (">", "ge"))


def constraint(ln, n=None, what="约束"):
    """'6,4 <= 24' → ([6,4], 'le', 24)。n 给定时检查系数个数。"""
    for sym, op in _OPS:
        if sym in ln:
            lhs, _, rhs = ln.partition(sym)
            coef = nums(lhs, what)
            rv = nums(rhs, what)
            if len(rv) != 1:
                raise InputError(f"{what}「{ln}」右端应为一个数。")
            if n is not None and len(coef) != n:
                raise InputError(f"{what}「{ln}」有 {len(coef)} 个系数，但变量有 {n} 个。")
            return coef, op, rv[0]
    raise InputError(f"{what}「{ln}」缺少关系符号，应写成 a1,a2,... <= b（或 >=、=）。")


def edges(v, weighted=True, what="边"):
    """'u v w' 每行一条 → [(u, v, w)]；节点编号须为非负整数。"""
    out = []
    for ln in lines(v):
        toks = [t for t in _SPLIT.split(ln) if t]
        need = 3 if weighted else 2
        if len(toks) < need:
            raise InputError(f"{what}「{ln}」格式不对，每行应为 u v{' w' if weighted else ''}。")
        u, w_ = _num(toks[0], what), _num(toks[1], what)
        if u < 0 or w_ < 0 or u != int(u) or w_ != int(w_):
            raise InputError(f"{what}「{ln}」中节点编号必须是非负整数。")
        wt = _num(toks[2], what) if weighted else 1.0
        out.append((int(u), int(w_), wt))
    return out
