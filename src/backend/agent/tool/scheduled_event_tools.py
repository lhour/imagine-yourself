"""src.backend.agent.tool.scheduled_event_tools — 周期事件调度专用工具。

10.3 新增：世界事件调度器（上课、火山喷发、媒体报道等周期/突发性事件）。
模型可随时增删周期事件，受 entity_quota 配额约束。
不进 ENTITIES，用专用工具避免生成无意义 CRUD。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.storage import models


@tool(
    name="scheduled_event_create",
    desc="创建一条周期/计划事件：上课、火山活动、媒体栏目等。模型可随时增删",
    params={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "事件标题（如'每日早课'）"},
            "desc_raw": {"type": "string", "description": "事件详细描述"},
            "importance": {"type": "integer", "description": "重要度 0-5，默认3"},
            "schedule_type": {"type": "string", "description": "recurring（周期）/ one_shot（一次性）"},
            "recurrence_pattern": {"type": "string", "description": "daily/weekly/monthly/yearly/custom/once_at"},
            "recurrence_detail_raw": {"type": "string", "description": "自然语言描述（'每天上午8点上课'）"},
            "next_trigger_game_time": {"type": "string", "description": "下次触发的游戏时间点"},
            "scope": {"type": "string", "description": "character/group/global"},
            "scope_target_json": {"type": "array", "description": "影响的角色/群体ID数组"},
            "event_template_json": {"type": "object", "description": "触发时生成的事件模板"},
            "trigger_condition_raw": {"type": "string", "description": "激活条件"},
            "expire_condition_raw": {"type": "string", "description": "失效条件（'火山喷发后'/'主角毕业'）"},
            "created_by": {"type": "string", "description": "drama/model/human"},
        },
        "required": ["title", "schedule_type", "recurrence_pattern", "next_trigger_game_time"],
    },
)
def scheduled_event_create(
    title: str,
    schedule_type: str,
    recurrence_pattern: str,
    next_trigger_game_time: str,
    desc_raw: str = "",
    importance: int = 3,
    recurrence_detail_raw: str = "",
    scope: str = "global",
    scope_target_json: List[Any] = None,
    event_template_json: Dict[str, Any] = None,
    trigger_condition_raw: str = "",
    expire_condition_raw: str = "",
    created_by: str = "model",
) -> dict:
    """创建周期/计划事件。"""
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 0)

    valid_st = {"recurring", "one_shot"}
    if schedule_type not in valid_st:
        return {"error": f"schedule_type 必须是 {valid_st}"}

    se = models.ScheduledEvent.create(
        title=title,
        desc_raw=desc_raw or "",
        importance=max(0, min(5, importance)),
        schedule_type=schedule_type,
        recurrence_pattern=recurrence_pattern,
        recurrence_detail_raw=recurrence_detail_raw or "",
        next_trigger_game_time=next_trigger_game_time,
        scope=scope or "global",
        scope_target_json=scope_target_json or [],
        event_template_json=event_template_json or {},
        active=1,
        trigger_condition_raw=trigger_condition_raw or "",
        expire_condition_raw=expire_condition_raw or "",
        created_by=created_by,
        created_tick=cur_tick,
    )
    return se.to_dict()


@tool(
    name="scheduled_event_deactivate",
    desc="停用一个周期事件（放假关上课、火山喷发后关火山活动）",
    params={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "要停用的 scheduled_event ID"},
            "reason": {"type": "string", "description": "停用原因"},
        },
        "required": ["event_id"],
    },
)
def scheduled_event_deactivate(event_id: int, reason: str = "") -> dict:
    """停用周期事件。"""
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 0)

    se = models.ScheduledEvent.get(event_id)
    if not se:
        return {"error": f"周期事件 {event_id} 不存在"}

    updates: Dict[str, Any] = {"active": 0, "deactivated_tick": cur_tick}
    if reason:
        custom = se.custom_attrs or {}
        custom["deactivate_reason"] = reason
        updates["custom_attrs"] = custom

    result = models.ScheduledEvent.update(event_id, **updates)
    return result.to_dict() if result else {"error": "更新失败"}


@tool(
    name="scheduled_event_update",
    desc="更新周期事件的字段（修改周期/模板/触发时间等）",
    params={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer"},
            "title": {"type": "string"},
            "desc_raw": {"type": "string"},
            "importance": {"type": "integer"},
            "recurrence_pattern": {"type": "string"},
            "recurrence_detail_raw": {"type": "string"},
            "next_trigger_game_time": {"type": "string"},
            "scope": {"type": "string"},
            "scope_target_json": {"type": "array"},
            "event_template_json": {"type": "object"},
            "active": {"type": "integer", "description": "1=激活 0=停用"},
        },
        "required": ["event_id"],
    },
)
def scheduled_event_update(
    event_id: int,
    title: str = "",
    desc_raw: str = "",
    importance: int = -1,
    recurrence_pattern: str = "",
    recurrence_detail_raw: str = "",
    next_trigger_game_time: str = "",
    scope: str = "",
    scope_target_json: List[Any] = None,
    event_template_json: Dict[str, Any] = None,
    active: int = -1,
) -> dict:
    """更新周期事件字段（仅更新非空/非-1参数）。"""
    se = models.ScheduledEvent.get(event_id)
    if not se:
        return {"error": f"周期事件 {event_id} 不存在"}

    updates: Dict[str, Any] = {}
    if title:
        updates["title"] = title
    if desc_raw:
        updates["desc_raw"] = desc_raw
    if importance >= 0:
        updates["importance"] = max(0, min(5, importance))
    if recurrence_pattern:
        updates["recurrence_pattern"] = recurrence_pattern
    if recurrence_detail_raw:
        updates["recurrence_detail_raw"] = recurrence_detail_raw
    if next_trigger_game_time:
        updates["next_trigger_game_time"] = next_trigger_game_time
    if scope:
        updates["scope"] = scope
    if scope_target_json is not None:
        updates["scope_target_json"] = scope_target_json
    if event_template_json is not None:
        updates["event_template_json"] = event_template_json
    if active >= 0:
        updates["active"] = active

    if not updates:
        return {"error": "无更新字段"}

    result = models.ScheduledEvent.update(event_id, **updates)
    return result.to_dict() if result else {"error": "更新失败"}


@tool(
    name="scheduled_event_list",
    desc="列出周期事件（可按 active/scope 过滤）",
    params={
        "type": "object",
        "properties": {
            "active_only": {"type": "integer", "description": "1=仅活跃 0=全部"},
            "scope": {"type": "string", "description": "过滤 scope"},
            "limit": {"type": "integer"},
        },
    },
)
def scheduled_event_list(
    active_only: int = 1,
    scope: str = "",
    limit: int = 100,
) -> dict:
    """列出周期事件。"""
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


SCHEDULED_EVENT_TOOLS = [
    "scheduled_event_create",
    "scheduled_event_deactivate",
    "scheduled_event_update",
    "scheduled_event_list",
]
