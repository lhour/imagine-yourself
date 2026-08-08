"""src.backend.http.routers.scheduled_events — 周期事件调度 REST API。

10.3 新增：世界事件调度器（上课、火山喷发、媒体报道等周期/突发性事件）。
前端世界管理页专用，支持 CRUD + 激活/停用。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.storage import models
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/scheduled-events", tags=["scheduled-events"])

_VALID_SCOPE = {"character", "group", "global"}
_VALID_SCHEDULE_TYPE = {"recurring", "one_shot"}
_VALID_PATTERN = {"daily", "weekly", "monthly", "yearly", "custom", "once_at"}


def _current_tick(sm: SaveManager) -> int:
    return sm.get_meta().get("tick_num", 0)


class CreateScheduledEventReq(BaseModel):
    title: str
    desc_raw: str = ""
    importance: int = 3
    schedule_type: str = "recurring"
    recurrence_pattern: str = "daily"
    recurrence_detail_raw: str = ""
    next_trigger_game_time: str = ""
    scope: str = "global"
    scope_target_json: List[Any] = []
    event_template_json: Dict[str, Any] = {}
    trigger_condition_raw: str = ""
    expire_condition_raw: str = ""
    created_by: str = "human"


class UpdateScheduledEventReq(BaseModel):
    title: Optional[str] = None
    desc_raw: Optional[str] = None
    importance: Optional[int] = None
    recurrence_pattern: Optional[str] = None
    recurrence_detail_raw: Optional[str] = None
    next_trigger_game_time: Optional[str] = None
    scope: Optional[str] = None
    scope_target_json: Optional[List[Any]] = None
    event_template_json: Optional[Dict[str, Any]] = None
    active: Optional[int] = None


@router.get("")
def list_scheduled_events(
    active_only: int = 0,
    scope: str = "",
    limit: int = 100,
    sm: SaveManager = Depends(require_active_save),
):
    where_parts: List[str] = []
    params: List[Any] = []
    if active_only == 1:
        where_parts.append("active = 1")
    if scope:
        where_parts.append("scope = ?")
        params.append(scope)
    where = " AND ".join(where_parts) if where_parts else ""
    items = models.ScheduledEvent.list(
        where=where, params=params,
        order_by="next_trigger_game_time ASC",
        limit=limit,
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("")
def create_scheduled_event(
    req: CreateScheduledEventReq,
    sm: SaveManager = Depends(require_active_save),
):
    if req.schedule_type not in _VALID_SCHEDULE_TYPE:
        raise HTTPException(400, f"schedule_type 必须是 {_VALID_SCHEDULE_TYPE}")
    if req.recurrence_pattern and req.recurrence_pattern not in _VALID_PATTERN:
        raise HTTPException(400, f"recurrence_pattern 必须是 {_VALID_PATTERN}")
    if req.scope not in _VALID_SCOPE:
        raise HTTPException(400, f"scope 必须是 {_VALID_SCOPE}")

    se = models.ScheduledEvent.create(
        title=req.title,
        desc_raw=req.desc_raw,
        importance=max(0, min(5, req.importance)),
        schedule_type=req.schedule_type,
        recurrence_pattern=req.recurrence_pattern,
        recurrence_detail_raw=req.recurrence_detail_raw,
        next_trigger_game_time=req.next_trigger_game_time,
        scope=req.scope,
        scope_target_json=req.scope_target_json,
        event_template_json=req.event_template_json,
        active=1,
        trigger_condition_raw=req.trigger_condition_raw,
        expire_condition_raw=req.expire_condition_raw,
        created_by=req.created_by,
        created_tick=_current_tick(sm),
    )
    return se.to_dict()


@router.get("/{event_id}")
def get_scheduled_event(
    event_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    se = models.ScheduledEvent.get(event_id)
    if not se:
        raise HTTPException(404, f"周期事件 {event_id} 不存在")
    return se.to_dict()


@router.put("/{event_id}")
def update_scheduled_event(
    event_id: int,
    req: UpdateScheduledEventReq,
    sm: SaveManager = Depends(require_active_save),
):
    se = models.ScheduledEvent.get(event_id)
    if not se:
        raise HTTPException(404, f"周期事件 {event_id} 不存在")

    updates: Dict[str, Any] = {}
    for field in ["title", "desc_raw", "recurrence_pattern", "recurrence_detail_raw",
                  "next_trigger_game_time", "scope"]:
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val
    if req.importance is not None:
        updates["importance"] = max(0, min(5, req.importance))
    if req.scope_target_json is not None:
        updates["scope_target_json"] = req.scope_target_json
    if req.event_template_json is not None:
        updates["event_template_json"] = req.event_template_json
    if req.active is not None:
        updates["active"] = req.active
        if req.active == 0:
            updates["deactivated_tick"] = _current_tick(sm)

    if not updates:
        raise HTTPException(400, "无更新字段")

    result = models.ScheduledEvent.update(event_id, **updates)
    if not result:
        raise HTTPException(500, "更新失败")
    return result.to_dict()


@router.delete("/{event_id}")
def delete_scheduled_event(
    event_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    se = models.ScheduledEvent.get(event_id)
    if not se:
        raise HTTPException(404, f"周期事件 {event_id} 不存在")
    models.ScheduledEvent.delete(event_id)
    return {"deleted": True, "id": event_id}


@router.post("/{event_id}/activate")
def activate_scheduled_event(
    event_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    se = models.ScheduledEvent.get(event_id)
    if not se:
        raise HTTPException(404, f"周期事件 {event_id} 不存在")
    result = models.ScheduledEvent.update(event_id, active=1, deactivated_tick=None)
    return result.to_dict() if result else {"error": "激活失败"}


@router.post("/{event_id}/deactivate")
def deactivate_scheduled_event(
    event_id: int,
    sm: SaveManager = Depends(require_active_save),
):
    se = models.ScheduledEvent.get(event_id)
    if not se:
        raise HTTPException(404, f"周期事件 {event_id} 不存在")
    result = models.ScheduledEvent.update(
        event_id, active=0, deactivated_tick=_current_tick(sm)
    )
    return result.to_dict() if result else {"error": "停用失败"}
