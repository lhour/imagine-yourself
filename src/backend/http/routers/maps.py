"""src.backend.http.routers.maps — 地图与距离专用端点。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.http.deps import require_active_save
from src.backend.service import map_service

router = APIRouter(prefix="/api/maps", tags=["maps"])


class DistanceReq(BaseModel):
    from_ref: Dict[str, Any] = Field(..., alias="from")
    to_ref: Dict[str, Any] = Field(..., alias="to")
    prefer_unit: str = "auto"


@router.get("/{map_id}/features")
def list_features(
    map_id: int,
    layer_z_min: Optional[int] = Query(None),
    layer_z_max: Optional[int] = Query(None),
    sm=Depends(require_active_save),
):
    """取该地图的所有地形要素（按 layer_z 排序）。"""
    return {"items": map_service.list_features(map_id, layer_z_min, layer_z_max)}


@router.get("/{map_id}/children")
def list_children(map_id: int, sm=Depends(require_active_save)):
    """子地图列表。"""
    return {"items": map_service.list_children(map_id)}


@router.get("/{map_id}/heatmaps")
def list_heatmaps(map_id: int, sm=Depends(require_active_save)):
    """该地图上所有群体的热力图。"""
    return {"items": map_service.list_heatmaps_on_map(map_id)}


@router.post("/distance")
def distance(req: DistanceReq, sm=Depends(require_active_save)):
    """计算两对象距离。

    请求体:
        {"from": {"type": "character|item|feature|map", "id": 1},
         "to":   {"type": "character|item|feature|map", "id": 2},
         "prefer_unit": "auto|m|km|AU|ly"}
    """
    return map_service.distance(req.from_ref, req.to_ref, req.prefer_unit)


@router.get("/{map_id}/distance_matrix")
def distance_matrix(
    map_id: int,
    ids: str = Query(..., description="逗号分隔的 ID 列表"),
    id_type: str = Query("feature"),
    sm=Depends(require_active_save),
):
    """多对象两两距离矩阵。"""
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    if len(id_list) < 2:
        raise HTTPException(400, "至少需要 2 个 ID")
    return map_service.distance_matrix(id_list, id_type)


@router.get("/path_to")
def path_to(from_map_id: int, target_map_id: int, sm=Depends(require_active_save)):
    """两地图间的祖先链路径。"""
    anc_a = map_service.get_map_ancestors(from_map_id)
    anc_b = map_service.get_map_ancestors(target_map_id)
    return {"from_ancestors": anc_a, "to_ancestors": anc_b}
