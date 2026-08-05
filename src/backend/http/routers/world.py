"""src.backend.http.routers.world — 世界推进（事件/时间）路由。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.service import world_service

router = APIRouter(prefix="/api/world", tags=["world"])


class TickReq(BaseModel):
    seconds: int = 60


class TimeJumpReq(BaseModel):
    seconds: int


class CreateEventReq(BaseModel):
    event_type: str = "narrative"
    content_raw: str
    content_polished: Optional[str] = None
    location_map_id: Optional[int] = None
    location_detail_raw: Optional[str] = None
    importance: int = 3
    visibility: str = "public"
    participants: Optional[List[Dict[str, Any]]] = None
    custom_attrs: Optional[Dict[str, Any]] = None


@router.get("/status")
def status(sm=Depends(require_active_save)):
    """健康检查 + 激活存档元信息。"""
    meta = sm.get_meta()
    return {"active_save": sm.active_save, "meta": meta}


@router.post("/tick")
def tick(req: TickReq, sm=Depends(require_active_save)):
    """正常推进 1 tick。"""
    return {"meta": world_service.tick_once(req.seconds)}


@router.post("/time_jump")
def time_jump(req: TimeJumpReq, sm=Depends(require_active_save)):
    """时间跨越。"""
    return world_service.time_jump(req.seconds)


@router.post("/events")
def create_event(req: CreateEventReq, sm=Depends(require_active_save)):
    """写入一条世界事件。"""
    return world_service.create_event(
        event_type=req.event_type,
        content_raw=req.content_raw,
        content_polished=req.content_polished,
        location_map_id=req.location_map_id,
        location_detail_raw=req.location_detail_raw,
        importance=req.importance,
        visibility=req.visibility,
        participants=req.participants,
        custom_attrs=req.custom_attrs,
    )


@router.get("/events")
def list_events(
    sm=Depends(require_active_save),
    limit: int = 100,
    event_type: Optional[str] = None,
    importance_min: int = 0,
    tick_from: Optional[int] = None,
    tick_to: Optional[int] = None,
):
    """列出世界事件（按 tick 倒序）。"""
    return world_service.list_events(
        limit=limit,
        event_type=event_type,
        importance_min=importance_min,
        tick_from=tick_from,
        tick_to=tick_to,
    )


@router.post("/events/{event_id}/polish")
def polish_event(event_id: int, polished: str, sm=Depends(require_active_save)):
    """重新润色事件文案。阶段一仅写库，LLM 润色在阶段二。"""
    from src.backend.storage import models
    e = models.Event.update(event_id, content_polished=polished)
    if not e:
        raise HTTPException(404, f"事件 {event_id} 不存在")
    return e.to_dict()
