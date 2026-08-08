"""src.backend.http.routers.propagation — 信息传播追踪 REST API。

10.1 新增：消息传播机制的可视化追踪接口。
- /api/propagation/disseminations — 定向传播触达记录（event_dissemination 表）
- /api/propagation/public-knowledge — 广播式传播记录（public_knowledge 表）

供世界管理页「信息传播追踪」tab 使用。
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.backend.http.deps import require_active_save
from src.backend.storage import models
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/propagation", tags=["propagation"])


@router.get("/disseminations")
def list_disseminations(
    status: str = "",
    event_id: Optional[int] = None,
    target_char_id: Optional[int] = None,
    limit: int = 200,
    sm: SaveManager = Depends(require_active_save),
):
    """列出定向传播触达记录。

    支持按 status (pending/arrived/distorted/lost) / event_id / target_char_id 过滤。
    """
    where_parts: List[str] = []
    params: List[Any] = []
    if status:
        where_parts.append("status = ?")
        params.append(status)
    if event_id is not None:
        where_parts.append("event_id = ?")
        params.append(event_id)
    if target_char_id is not None:
        where_parts.append("target_char_id = ?")
        params.append(target_char_id)
    where = " AND ".join(where_parts) if where_parts else ""

    items = models.EventDissemination.list(
        where=where, params=params,
        order_by="id DESC",
        limit=min(limit, 1000),
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/disseminations/stats")
def dissemination_stats(sm: SaveManager = Depends(require_active_save)):
    """传播状态统计：按 status 聚合，供前端饼图/概览使用。"""
    stats = {"pending": 0, "arrived": 0, "distorted": 0, "lost": 0, "total": 0}
    try:
        cur = sm._conn.execute(
            "SELECT status, COUNT(*) AS c FROM event_dissemination GROUP BY status"
        )
        for row in cur.fetchall():
            s = row["status"] or "unknown"
            stats[s] = stats.get(s, 0) + row["c"]
            stats["total"] += row["c"]
    except Exception as e:
        raise HTTPException(500, f"统计失败: {e}")
    return stats


@router.get("/public-knowledge")
def list_public_knowledge(
    medium: str = "",
    limit: int = 100,
    sm: SaveManager = Depends(require_active_save),
):
    """列出广播式传播记录（媒体报道/官方公告）。"""
    where_parts: List[str] = []
    params: List[Any] = []
    if medium:
        where_parts.append("medium = ?")
        params.append(medium)
    where = " AND ".join(where_parts) if where_parts else ""

    items = models.PublicKnowledge.list(
        where=where, params=params,
        order_by="id DESC",
        limit=min(limit, 500),
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("/disseminations/{dissemination_id}/mark-arrived")
def mark_arrived(
    dissemination_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    """手动标记某条传播记录为已触达（调试/修正用）。"""
    ed = models.EventDissemination.get(dissemination_id)
    if not ed:
        raise HTTPException(404, f"传播记录 {dissemination_id} 不存在")
    from src.backend.storage.connection import default_save_manager
    meta = default_save_manager().get_meta()
    result = models.EventDissemination.update(
        dissemination_id,
        status="arrived",
        arrived_game_time=ed.expected_arrival_game_time or meta.get("game_time", ""),
        updated_tick=meta.get("tick_num", 0),
    )
    return result.to_dict() if result else {"error": "更新失败"}


@router.post("/disseminations/{dissemination_id}/mark-lost")
def mark_lost(
    dissemination_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    """手动标记某条传播记录为丢失（信息未触达）。"""
    ed = models.EventDissemination.get(dissemination_id)
    if not ed:
        raise HTTPException(404, f"传播记录 {dissemination_id} 不存在")
    from src.backend.storage.connection import default_save_manager
    meta = default_save_manager().get_meta()
    result = models.EventDissemination.update(
        dissemination_id,
        status="lost",
        updated_tick=meta.get("tick_num", 0),
    )
    return result.to_dict() if result else {"error": "更新失败"}
