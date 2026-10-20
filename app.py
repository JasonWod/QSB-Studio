"""
app.py — QSB Studio FastAPI 入口。
  GET  /api/modules        -> 19 模块元数据
  POST /api/solve/{mid}    -> 求解（body 为模块 payload）
  GET  /                   -> 静态前端 (index.html)
运行:  .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8090
"""
from __future__ import annotations
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException

from qsb import modules

app = FastAPI(title="QSB Studio", version="0.1.0")
BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "qsb-studio", "modules": len(modules.MODULES)}


@app.get("/api/modules")
def api_modules():
    return {"modules": modules.meta_list()}


@app.post("/api/solve/{mid}")
async def api_solve(mid: str, request: Request):
    m = modules.BY_ID.get(mid)
    if not m:
        raise HTTPException(404, f"unknown module: {mid}")
    if not m.get("solve"):
        return {
            "status": "not_implemented",
            "message": f"「{m['name']}」目前是骨架，算法实现中。当前已完整实现的是「线性规划」。",
            "name": m["name"],
        }
    payload = await request.json()
    try:
        result = m["solve"](payload)
    except Exception as e:  # noqa
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}
    if m.get("graph"):
        try:
            result["graph"] = m["graph"](payload, result)
        except Exception:
            result["graph"] = None
    return result


# 静态前端放在最后，/api 路由优先匹配
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
