"""src.backend.http.routers.memory — 记忆系统专用端点。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.service import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class RetrieveReq(BaseModel):
    char_id: int
    query: Optional[str] = None
    index_filter: Optional[Dict[str, str]] = None
    max_count: int = 20
    include_outline_only: bool = True
    expand_palace: bool = True
    palace_depth: int = 1


class DistortReq(BaseModel):
    new_content: str


class DecayReq(BaseModel):
    ticks_passed: int = 1


class ImpressionUpsertReq(BaseModel):
    target_char_id: int
    impression_raw: str
    impression_polished: str | None = None
    valence: float | None = None
    arousal: float | None = None
    weight: float | None = None
    last_update_tick: int | None = None


@router.post("/retrieve")
def retrieve(req: RetrieveReq, sm=Depends(require_active_save)):
    """按需加载角色记忆（深度+索引+宫殿展开+抽样）。"""
    return memory_service.retrieve_memories(
        char_id=req.char_id,
        query=req.query,
        index_filter=req.index_filter,
        max_count=req.max_count,
        include_outline_only=req.include_outline_only,
        expand_palace=req.expand_palace,
        palace_depth=req.palace_depth,
    )


@router.get("/impressions/{char_id}")
def list_impressions(char_id: int, sm=Depends(require_active_save)):
    """列出某角色的所有印象摘要（A 对 B 的顶层印象）。"""
    from src.backend.storage import models
    items = models.CharacterImpression.list(
        where="observer_char_id = ?", params=[char_id], limit=1000
    )
    return {"items": [i.to_dict() for i in items]}


@router.post("/impressions/{observer_id}")
def upsert_impression(
    observer_id: int,
    req: ImpressionUpsertReq,
    sm=Depends(require_active_save),
):
    """更新/新建 A（observer_id）对 B（target_char_id）的单条印象。"""
    from src.backend.storage import models
    # 校验存在性
    obs = models.Character.get(observer_id)
    tgt = models.Character.get(req.target_char_id)
    if obs is None or tgt is None:
        raise HTTPException(404, "observer 或 target 角色不存在")
    existing = models.CharacterImpression.list(
        where="observer_char_id = ? AND target_char_id = ?",
        params=[observer_id, req.target_char_id],
        limit=1,
    )
    payload = dict(
        impression_raw=req.impression_raw,
        impression_polished=req.impression_polished,
        valence=req.valence,
        arousal=req.arousal,
        weight=req.weight,
        last_update_tick=req.last_update_tick,
    )
    if existing:
        models.CharacterImpression.update(existing[0].id, **payload)
        item = models.CharacterImpression.get(existing[0].id)
        return {"ok": True, "created": False, "impression": item.to_dict() if item else None}
    created = models.CharacterImpression.create(
        observer_char_id=observer_id,
        target_char_id=req.target_char_id,
        **payload,
    )
    return {"ok": True, "created": True, "impression": created.to_dict()}


@router.post("/decay/{char_id}")
def decay(req: DecayReq, char_id: int, sm=Depends(require_active_save)):
    """记忆衰减。"""
    return memory_service.decay_memories(char_id, req.ticks_passed)


@router.post("/distort/{memory_id}")
def distort(memory_id: int, req: DistortReq, sm=Depends(require_active_save)):
    """篡改记忆（虚假记忆植入）。"""
    try:
        return memory_service.distort_memory(memory_id, req.new_content)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/palace/{memory_id}")
def palace(memory_id: int, depth: int = 2, sm=Depends(require_active_save)):
    """记忆宫殿展开。"""
    return memory_service.get_palace(memory_id, depth)


@router.post("/encode_event/{event_id}")
def encode_event(event_id: int, sm=Depends(require_active_save)):
    """事件 → 每个参与人一条记忆。"""
    try:
        return {"memories": memory_service.encode_event_to_memories(event_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))
