"""src.backend.http.routers.anchors — 锚点剧情专用 REST 路由。

v4 锚点剧情表（AnchorPlot）的语义化 CRUD + 状态流转端点，
供前端锚点管理 tab 直接调用（不依赖 LLM）。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.storage import models
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/anchors", tags=["anchors"])


_VALID_STATUS = {"pending", "active", "fulfilled", "expired", "abandoned"}
# 状态流转终态（不可再变）
_TERMINAL_STATUS = {"fulfilled", "expired", "abandoned"}


def _current_tick(sm: SaveManager) -> int:
    return int(sm.get_meta().get("tick_num", 1) or 1)


def _get_or_404(anchor_id: int) -> models.AnchorPlot:
    a = models.AnchorPlot.get(anchor_id)
    if not a:
        raise HTTPException(404, f"锚点 {anchor_id} 不存在")
    return a


# ============================================================
# 请求体
# ============================================================

class CreateAnchorReq(BaseModel):
    title: str
    desc_raw: str = ""
    desc_polished: Optional[str] = None
    inevitability: int = 3
    trigger_condition_raw: str = ""
    target_tick: Optional[int] = None
    created_by: str = "human"
    priority: int = 3
    plot_arc: str = ""
    tags: Optional[List[str]] = None


class UpdateAnchorReq(BaseModel):
    title: Optional[str] = None
    desc_raw: Optional[str] = None
    desc_polished: Optional[str] = None
    inevitability: Optional[int] = None
    trigger_condition_raw: Optional[str] = None
    target_tick: Optional[int] = None
    priority: Optional[int] = None
    plot_arc: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class FulfillReq(BaseModel):
    event_id: Optional[int] = None
    reason: Optional[str] = None


class AbandonReq(BaseModel):
    reason: Optional[str] = None


# ============================================================
# CRUD
# ============================================================

@router.get("")
def list_anchors(
    sm: SaveManager = Depends(require_active_save),
    status: Optional[str] = None,
    min_inevitability: int = 0,
    plot_arc: Optional[str] = None,
    limit: int = 100,
):
    """列出锚点剧情。默认返回 pending+active，按必然性降序。"""
    where_parts: List[str] = ["inevitability >= ?"]
    params: List[Any] = [min_inevitability]
    if status:
        if status not in _VALID_STATUS:
            raise HTTPException(400, f"status 必须是 {sorted(_VALID_STATUS)}")
        where_parts.append("status = ?")
        params.append(status)
    else:
        where_parts.append("status IN ('pending', 'active')")
    if plot_arc:
        where_parts.append("plot_arc LIKE ?")
        params.append(f"%{plot_arc}%")

    where = " AND ".join(where_parts)
    items = models.AnchorPlot.list(
        where=where, params=params,
        order_by="inevitability DESC, priority DESC, id ASC",
        limit=limit,
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("")
def create_anchor(req: CreateAnchorReq, sm: SaveManager = Depends(require_active_save)):
    """创建锚点剧情。自动填 created_tick=当前 tick、status=pending。"""
    a = models.AnchorPlot.create(
        title=req.title,
        desc_raw=req.desc_raw,
        desc_polished=req.desc_polished,
        inevitability=max(0, min(5, req.inevitability)),
        status="pending",
        trigger_condition_raw=req.trigger_condition_raw or "",
        target_tick=req.target_tick,
        created_tick=_current_tick(sm),
        created_by=req.created_by or "human",
        priority=max(1, min(5, req.priority)),
        plot_arc=req.plot_arc or "",
        tags=req.tags or [],
    )
    return a.to_dict()


@router.get("/{anchor_id}")
def get_anchor(anchor_id: int, sm: SaveManager = Depends(require_active_save)):
    return _get_or_404(anchor_id).to_dict()


@router.put("/{anchor_id}")
def update_anchor(
    anchor_id: int,
    req: UpdateAnchorReq,
    sm: SaveManager = Depends(require_active_save),
):
    a = _get_or_404(anchor_id)
    # 终态锚点不允许再改关键字段（仅允许终态间不再流转）
    if a.status in _TERMINAL_STATUS and req.status and req.status != a.status:
        raise HTTPException(400, f"锚点已处于终态 {a.status}，不可再流转")

    fields: Dict[str, Any] = {}
    if req.title is not None:
        fields["title"] = req.title
    if req.desc_raw is not None:
        fields["desc_raw"] = req.desc_raw
    if req.desc_polished is not None:
        fields["desc_polished"] = req.desc_polished
    if req.inevitability is not None:
        fields["inevitability"] = max(0, min(5, req.inevitability))
    if req.trigger_condition_raw is not None:
        fields["trigger_condition_raw"] = req.trigger_condition_raw
    if req.target_tick is not None:
        fields["target_tick"] = req.target_tick
    if req.priority is not None:
        fields["priority"] = max(1, min(5, req.priority))
    if req.plot_arc is not None:
        fields["plot_arc"] = req.plot_arc
    if req.tags is not None:
        fields["tags"] = req.tags
    if req.status is not None:
        if req.status not in _VALID_STATUS:
            raise HTTPException(400, f"status 必须是 {sorted(_VALID_STATUS)}")
        fields["status"] = req.status

    if not fields:
        return a.to_dict()
    updated = models.AnchorPlot.update(anchor_id, **fields)
    return updated.to_dict() if updated else a.to_dict()


@router.delete("/{anchor_id}")
def delete_anchor(anchor_id: int, sm: SaveManager = Depends(require_active_save)):
    _get_or_404(anchor_id)
    ok = models.AnchorPlot.delete(anchor_id)
    return {"deleted": ok, "id": anchor_id}


# ============================================================
# 状态流转
# ============================================================

@router.post("/{anchor_id}/activate")
def activate_anchor(anchor_id: int, sm: SaveManager = Depends(require_active_save)):
    a = _get_or_404(anchor_id)
    if a.status != "pending":
        raise HTTPException(400, f"仅 pending 锚点可激活，当前状态 {a.status}")
    updated = models.AnchorPlot.update(anchor_id, status="active")
    return updated.to_dict() if updated else a.to_dict()


@router.post("/{anchor_id}/fulfill")
def fulfill_anchor(
    anchor_id: int,
    req: FulfillReq,
    sm: SaveManager = Depends(require_active_save),
):
    """标记锚点已实现，可回链满足它的 narrative 事件。"""
    a = _get_or_404(anchor_id)
    fields: Dict[str, Any] = {
        "status": "fulfilled",
        "fulfilled_tick": _current_tick(sm),
    }
    if req.event_id:
        fields["fulfilled_event_id"] = req.event_id
    if req.reason:
        custom = a.custom_attrs or {}
        if isinstance(custom, str):
            import json as _json
            try:
                custom = _json.loads(custom)
            except Exception:
                custom = {}
        custom["transition_reason"] = req.reason
        fields["custom_attrs"] = custom
    updated = models.AnchorPlot.update(anchor_id, **fields)
    return updated.to_dict() if updated else a.to_dict()


@router.post("/{anchor_id}/abandon")
def abandon_anchor(
    anchor_id: int,
    req: AbandonReq,
    sm: SaveManager = Depends(require_active_save),
):
    """放弃锚点（不再追求该走向）。"""
    a = _get_or_404(anchor_id)
    fields: Dict[str, Any] = {"status": "abandoned"}
    if req.reason:
        custom = a.custom_attrs or {}
        if isinstance(custom, str):
            import json as _json
            try:
                custom = _json.loads(custom)
            except Exception:
                custom = {}
        custom["transition_reason"] = req.reason
        fields["custom_attrs"] = custom
    updated = models.AnchorPlot.update(anchor_id, **fields)
    return updated.to_dict() if updated else a.to_dict()
