"""src.backend.http.routers.groups — 群体专用端点（热力图）。"""

from fastapi import APIRouter, Depends, HTTPException

from src.backend.http.deps import require_active_save
from src.backend.service import map_service
from src.backend.storage import models

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("/{group_id}/heatmap")
def get_heatmap(group_id: int, sm=Depends(require_active_save)):
    """单独取某群体的 heatmap_grid。"""
    g = models.Group.get(group_id)
    if not g:
        raise HTTPException(404, f"群体 {group_id} 不存在")
    return {
        "group_id": g.id,
        "group_name": g.name,
        "heatmap_grid": g.heatmap_grid,
        "heatmap_resolution": g.heatmap_resolution,
        "center_x": g.center_x,
        "center_y": g.center_y,
        "spread_radius": g.spread_radius,
        "heatmap_updated_tick": g.heatmap_updated_tick,
    }


@router.post("/{group_id}/refresh_heatmap")
def refresh_heatmap(group_id: int, sm=Depends(require_active_save)):
    """手动触发重新统计热力图（按成员 character_locations 栅格化）。"""
    try:
        return map_service.refresh_group_heatmap(group_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
