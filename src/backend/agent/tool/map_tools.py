"""src.backend.agent.tool.map_tools — 地图与距离专用工具。

提供给 LLM 的地图查询能力：算距离、查要素、查热力图。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.service import map_service


@tool(
    name="map_distance",
    desc="计算任意两对象（角色/物品/要素/地图）的距离，自动按比例尺换算并返回人话距离",
    params={
        "type": "object",
        "properties": {
            "from": {"type": "object", "description": "{type: character|item|feature|map, id: int}"},
            "to": {"type": "object", "description": "同上"},
            "prefer_unit": {"type": "string", "description": "auto|m|km|AU|ly"},
        },
        "required": ["from", "to"],
    },
)
def map_distance(**kwargs) -> Dict[str, Any]:
    # 适配 from 是 Python 关键字的情况
    from_ref = kwargs.get("from") or kwargs.get("from_ref")
    to_ref = kwargs.get("to") or kwargs.get("to_ref")
    prefer = kwargs.get("prefer_unit", "auto")
    return map_service.distance(from_ref, to_ref, prefer)


@tool(
    name="map_features",
    desc="查询某地图上的所有地形要素（可按 layer_z 过滤）",
    params={
        "type": "object",
        "properties": {
            "map_id": {"type": "integer"},
            "layer_z_min": {"type": "integer"},
            "layer_z_max": {"type": "integer"},
        },
        "required": ["map_id"],
    },
)
def map_features(map_id: int, layer_z_min: int = None, layer_z_max: int = None) -> dict:
    return {"items": map_service.list_features(map_id, layer_z_min, layer_z_max)}


@tool(
    name="map_children",
    desc="查询某地图的所有子地图",
    params={
        "type": "object",
        "properties": {"map_id": {"type": "integer"}},
        "required": ["map_id"],
    },
)
def map_children(map_id: int) -> dict:
    return {"items": map_service.list_children(map_id)}


@tool(
    name="group_heatmaps",
    desc="查询某地图上所有群体的热力图",
    params={
        "type": "object",
        "properties": {"map_id": {"type": "integer"}},
        "required": ["map_id"],
    },
)
def group_heatmaps(map_id: int) -> dict:
    return {"items": map_service.list_heatmaps_on_map(map_id)}


MAP_TOOLS = ["map_distance", "map_features", "map_children", "group_heatmaps"]
