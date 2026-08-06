"""src.backend.http.routers.traces — 请求日志 / 调用链追踪查询。

对应前端「请求日志」页面：
- GET  /api/traces          列表（摘要，含并发度/耗时）
- GET  /api/traces/{id}     单条完整 span 树
- DELETE /api/traces        清空
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from src.backend.agent import trace

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("")
def list_traces(limit: int = 200, action: Optional[str] = None):
    """请求日志列表（最新在前）。"""
    items = trace.list_traces(limit=limit)
    if action:
        items = [i for i in items if i.get("action") == action]
    return {"items": items, "count": len(items)}


@router.get("/{tid}")
def get_trace(tid: str):
    """单条请求的完整 span 树（前端用于绘制时间轴 + 展开详情）。"""
    d = trace.get_trace(tid)
    if not d:
        raise HTTPException(404, f"trace {tid} 不存在")
    return d


@router.delete("")
def clear_traces():
    """清空请求日志。"""
    n = trace.clear_traces()
    return {"cleared": n}