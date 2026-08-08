"""src.backend.agent.tool.anchor_tools — 锚点剧情专用工具。

v4 新增：锚点剧情（AnchorPlot）的创建、推进、查询工具，
支持人工/模型写入引导未来剧情，支持必然性 0-5 分级。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.storage import models


@tool(
    name="anchor_create",
    desc="创建一条锚点剧情：引导或强制模型在未来实现指定走向。inevitability=0 纯引导，5 硬约束",
    params={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "锚点标题（简洁）"},
            "desc_raw": {"type": "string", "description": "锚点剧情详细描述（可含人物/事件/走向）"},
            "inevitability": {"type": "integer", "description": "必然性 0-5：0=引导灵感，3=强引导，5=必须实现"},
            "trigger_condition_raw": {"type": "string", "description": "触发条件（自然语言，如 'A 拔剑相向'）"},
            "target_tick": {"type": "integer", "description": "目标实现 tick（可选）"},
            "created_by": {"type": "string", "description": "human|model|system"},
            "priority": {"type": "integer", "description": "执行优先级 1-5"},
            "plot_arc": {"type": "string", "description": "所属剧情弧（如 '【序幕】'）"},
            "tags": {"type": "array", "description": "标签数组"},
        },
        "required": ["title", "desc_raw"],
    },
)
def anchor_create(
    title: str,
    desc_raw: str,
    inevitability: int = 3,
    trigger_condition_raw: str = "",
    target_tick: int = 0,
    created_by: str = "human",
    priority: int = 3,
    plot_arc: str = "",
    tags: List[str] = None,
) -> dict:
    """创建锚点剧情。"""
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 1)

    a = models.AnchorPlot.create(
        title=title,
        desc_raw=desc_raw,
        inevitability=max(0, min(5, inevitability)),
        trigger_condition_raw=trigger_condition_raw or "",
        target_tick=target_tick or None,
        created_by=created_by,
        priority=priority,
        plot_arc=plot_arc or "",
        tags=tags or [],
        created_tick=cur_tick,
    )
    return a.to_dict()


@tool(
    name="anchor_list_active",
    desc="列出当前所有活跃/待定锚点（按必然性降序）",
    params={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "过滤状态：pending|active|fulfilled|expired|abandoned（空=全部活跃）"},
            "min_inevitability": {"type": "integer", "description": "最低必然性阈值"},
            "limit": {"type": "integer"},
        },
    },
)
def anchor_list_active(
    status: str = "",
    min_inevitability: int = 0,
    limit: int = 50,
) -> dict:
    where = "inevitability >= ?"
    params: List[Any] = [min_inevitability]
    if status:
        where += " AND status = ?"
        params.append(status)
    else:
        where += " AND status IN ('pending', 'active')"
    items = models.AnchorPlot.list(
        where=where, params=params,
        order_by="inevitability DESC, priority DESC, id ASC",
        limit=limit,
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@tool(
    name="anchor_advance",
    desc="推进锚点状态：pending→active→fulfilled/expired/abandoned",
    params={
        "type": "object",
        "properties": {
            "anchor_id": {"type": "integer"},
            "target_status": {"type": "string", "description": "active|fulfilled|expired|abandoned"},
            "fulfilled_event_id": {"type": "integer", "description": "若 fulfilled，关联的事件 ID"},
            "reason": {"type": "string", "description": "状态变更原因"},
        },
        "required": ["anchor_id", "target_status"],
    },
)
def anchor_advance(
    anchor_id: int,
    target_status: str,
    fulfilled_event_id: int = 0,
    reason: str = "",
) -> dict:
    valid = {"active", "fulfilled", "expired", "abandoned"}
    if target_status not in valid:
        return {"error": f"target_status 必须是 {valid}"}
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 1)

    updates: Dict[str, Any] = {"status": target_status}
    if target_status == "fulfilled":
        updates["fulfilled_tick"] = cur_tick
        if fulfilled_event_id:
            updates["fulfilled_event_id"] = fulfilled_event_id
    if reason:
        # 附加到 custom_attrs
        a = models.AnchorPlot.get(anchor_id)
        if not a:
            return {"error": f"锚点 {anchor_id} 不存在"}
        custom = a.custom_attrs or {}
        custom["transition_reason"] = reason
        updates["custom_attrs"] = custom

    result = models.AnchorPlot.update(anchor_id, **updates)
    if not result:
        return {"error": f"锚点 {anchor_id} 不存在"}
    return result.to_dict()


@tool(
    name="anchor_get_by_plot_arc",
    desc="按剧情弧查询锚点（用于管道调度）",
    params={
        "type": "object",
        "properties": {
            "plot_arc": {"type": "string"},
            "status": {"type": "string"},
        },
        "required": ["plot_arc"],
    },
)
def anchor_get_by_plot_arc(plot_arc: str, status: str = "") -> dict:
    where = "plot_arc LIKE ?"
    params: List[Any] = [f"%{plot_arc}%"]
    if status:
        where += " AND status = ?"
        params.append(status)
    items = models.AnchorPlot.list(
        where=where, params=params,
        order_by="inevitability DESC",
    )
    return {"items": [i.to_dict() for i in items], "count": len(items)}


ANCHOR_TOOLS = [
    "anchor_create",
    "anchor_list_active",
    "anchor_advance",
    "anchor_get_by_plot_arc",
]
