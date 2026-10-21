"""与 Web 框架无关的 API 层：校验请求、调用求解器、把异常转成学生能看懂的提示。

返回 (HTTP 状态码, JSON 可序列化对象)。app.py 只负责收发 HTTP。
"""
import json
import logging
import math
import traceback

from . import lp
from . import modules
from .report import InputError

log = logging.getLogger("qsb")

MAX_BODY = 512 * 1024          # 请求体上限：512 KB，足够任何教学规模的题目


def health():
    return 200, {"ok": True, "service": "qsb-studio", "modules": len(modules.MODULES)}


def module_list():
    return 200, {"modules": modules.meta_list()}


def _clean(o):
    """把 NaN / ±inf 转成 None，保证输出是合法 JSON。"""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def solve(mid, body: bytes):
    m = modules.BY_ID.get(mid)
    if not m:
        return 404, {"detail": f"unknown module: {mid}"}
    if not m.get("solve"):
        return 200, {"status": "not_implemented", "name": m["name"],
                     "message": f"「{m['name']}」模块加载失败，请查看服务端日志。"}
    if len(body) > MAX_BODY:
        return 413, {"status": "error", "headline": "请求过大", "message": "题目数据超过 512 KB，教学版不支持这么大的规模。"}
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"status": "error", "headline": "请求格式错误", "message": "请求体必须是 UTF-8 编码的 JSON 对象。"}
    if not isinstance(payload, dict):
        return 400, {"status": "error", "headline": "请求格式错误", "message": "请求体必须是 JSON 对象（{...}）。"}
    try:
        result = m["solve"](payload)
    except (InputError, lp.LPInputError) as e:
        return 200, {"status": "error", "headline": "输入有误", "message": str(e)}
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, OverflowError) as e:
        log.warning("模块 %s 输入异常: %s\n%s", mid, e, traceback.format_exc())
        hint = f"缺少字段「{e.args[0]}」" if isinstance(e, KeyError) else "请检查各输入框的格式是否与说明一致"
        return 200, {"status": "error", "headline": "无法解析输入", "message": f"{hint}。"}
    except Exception:  # noqa: BLE001 — 兜底：记录完整堆栈，前端只显示简短提示
        log.exception("模块 %s 求解出错", mid)
        return 500, {"status": "error", "headline": "求解出错", "message": "求解器内部错误，已记录日志。请换一组数据或反馈问题。"}
    if m.get("graph"):
        try:
            result["graph"] = m["graph"](payload, result)
        except Exception:  # noqa: BLE001
            log.exception("模块 %s 生成图解失败", mid)
            result["graph"] = None
    return 200, _clean(result)
