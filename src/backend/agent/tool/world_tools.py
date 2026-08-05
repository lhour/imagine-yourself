"""src.backend.agent.tool.world_tools — 世界推进工具。

提供给 pipeline 调用：创建事件、推进 tick、润色文案。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.service import world_service


@tool(
    name="world_create_event",
    desc="写入一条世界事件（含参与人），自动填充当前 tick 与 game_time",
    params={
        "type": "object",
        "properties": {
            "event_type": {"type": "string", "description": "narrative|player_action|environment|objective|system"},
            "content_raw": {"type": "string", "description": "事件关键文本（LLM 用）"},
            "content_polished": {"type": "string", "description": "润色文案（前端展示用）"},
            "location_map_id": {"type": "integer"},
            "location_detail_raw": {"type": "string"},
            "importance": {"type": "integer"},
            "participants": {"type": "array", "description": "[{type, id, role, perception}]"},
        },
        "required": ["event_type", "content_raw"],
    },
)
def world_create_event(**kwargs) -> dict:
    return world_service.create_event(**kwargs)


@tool(
    name="world_polish_event",
    desc="重新润色事件文案（更新 content_polished 字段）",
    params={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer"},
            "polished": {"type": "string"},
        },
        "required": ["event_id", "polished"],
    },
)
def world_polish_event(event_id: int, polished: str) -> dict:
    from src.backend.storage import models
    e = models.Event.update(event_id, content_polished=polished)
    if not e:
        return {"error": f"事件 {event_id} 不存在"}
    return e.to_dict()


@tool(
    name="world_recent_events",
    desc="查询最近 N 条事件（默认 20 条）",
    params={
        "type": "object",
        "properties": {
            "limit": {"type": "integer"},
            "event_type": {"type": "string"},
        },
    },
)
def world_recent_events(limit: int = 20, event_type: str = "") -> dict:
    from src.backend.storage import models
    where = ""
    params: List[Any] = []
    if event_type:
        where = "event_type = ?"
        params.append(event_type)
    items = models.Event.list(
        where=where, params=params, order_by="id DESC", limit=limit
    )
    return {"items": [e.to_dict() for e in items]}


WORLD_TOOLS = ["world_create_event", "world_polish_event", "world_recent_events"]
