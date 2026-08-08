"""src.backend.agent.tool.graph_tools — 图库专用工具。

v4 新增：基于 KuzuDB 图库的关系查询工具。
取代旧 character_impressions 表的直接查询，通过图库 ViewsAs 边
获取 A 对 B 的主观看法、二跳敌人、记忆宫殿 BFS 等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.storage import models


def _get_graph():
    g = models.graph()
    if g is None:
        return None
    return g


@tool(
    name="graph_views_as",
    desc="查询角色对他人的主观看法（图库 ViewsAs 边）。返回 favorability/trust/fear/impression。",
    params={
        "type": "object",
        "properties": {
            "observer_id": {"type": "integer", "description": "观察者角色 ID"},
            "target_id": {"type": "integer", "description": "目标角色 ID（0=查全部）"},
        },
        "required": ["observer_id"],
    },
)
def graph_views_as(observer_id: int, target_id: int = 0) -> dict:
    g = _get_graph()
    if g is None:
        return {"error": "图库未就绪", "items": []}
    try:
        if target_id:
            rows = g.get_views_as(observer_id, target_id)
        else:
            rows = g.get_views_as(observer_id)
        return {"items": rows}
    except Exception as e:
        return {"error": str(e), "items": []}


@tool(
    name="graph_two_hop_enemies",
    desc="二跳敌人查询：A 的朋友中对某角色信任度低的人（间接敌人）",
    params={
        "type": "object",
        "properties": {
            "char_id": {"type": "integer"},
        },
        "required": ["char_id"],
    },
)
def graph_two_hop_enemies(char_id: int) -> dict:
    g = _get_graph()
    if g is None:
        return {"error": "图库未就绪", "items": []}
    try:
        rows = g.get_two_hop_enemies(char_id)
        return {"items": rows}
    except Exception as e:
        return {"error": str(e), "items": []}


@tool(
    name="graph_memory_palace",
    desc="记忆宫殿 BFS 展开：以某条记忆为中心展开关联记忆",
    params={
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer"},
            "depth": {"type": "integer", "description": "BFS 跳数，默认 3"},
        },
        "required": ["memory_id"],
    },
)
def graph_memory_palace(memory_id: int, depth: int = 3) -> dict:
    g = _get_graph()
    if g is None:
        return {"error": "图库未就绪", "items": []}
    try:
        rows = g.expand_memory_palace(memory_id, depth)
        return {"items": rows}
    except Exception as e:
        return {"error": str(e), "items": []}


@tool(
    name="graph_event_participants",
    desc="查询某事件的所有参与角色（通过图库 ParticipatedIn 边）",
    params={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer"},
        },
        "required": ["event_id"],
    },
)
def graph_event_participants(event_id: int) -> dict:
    g = _get_graph()
    if g is None:
        return {"error": "图库未就绪", "items": []}
    try:
        rows = g.get_event_participants(event_id)
        return {"items": rows}
    except Exception as e:
        return {"error": str(e), "items": []}


@tool(
    name="graph_upsert_views",
    desc="写入/更新 A 对 B 的主观看法（双写图库 ViewsAs + character_impressions_cache）",
    params={
        "type": "object",
        "properties": {
            "observer_id": {"type": "integer"},
            "target_id": {"type": "integer"},
            "impression_raw": {"type": "string"},
            "impression_polished": {"type": "string"},
            "favorability": {"type": "integer", "description": "-100 到 100"},
            "trust": {"type": "integer"},
            "fear": {"type": "integer"},
        },
        "required": ["observer_id", "target_id"],
    },
)
def graph_upsert_views(
    observer_id: int,
    target_id: int,
    impression_raw: str = "",
    impression_polished: str = "",
    favorability: int = 50,
    trust: int = 50,
    fear: int = 0,
) -> dict:
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 1)

    # 双写关系库（印象缓存表）
    existing = models.CharacterImpressionsCache.list(
        where="observer_char_id = ? AND target_char_id = ?",
        params=[observer_id, target_id],
    )
    if existing:
        ic = existing[0]
        models.CharacterImpressionsCache.update(
            ic.id,
            favorability=max(-100, min(100, favorability)),
            trust=max(-100, min(100, trust)),
            fear=max(0, fear),
            impression_polished=impression_polished or ic.impression_polished,
            last_update_tick=cur_tick,
        )
    else:
        models.CharacterImpressionsCache.create(
            observer_char_id=observer_id,
            target_char_id=target_id,
            favorability=max(-100, min(100, favorability)),
            trust=max(-100, min(100, trust)),
            fear=max(0, fear),
            impression_polished=impression_polished,
            last_update_tick=cur_tick,
        )

    # 双写图库
    g = _get_graph()
    if g is not None:
        try:
            g.upsert_views_as(
                observer_id=observer_id,
                target_id=target_id,
                impression_raw=impression_raw,
                impression_polished=impression_polished,
                favorability=max(-100, min(100, favorability)),
                trust=max(-100, min(100, trust)),
                fear=max(0, fear),
                last_update_tick=cur_tick,
            )
        except Exception as e:
            return {"warning": f"图库写入失败: {e}", "status": "partial"}

    return {"status": "ok", "observer": observer_id, "target": target_id}


@tool(
    name="graph_add_member",
    desc="添加角色到群体的成员关系（图库 MemberOf 边）",
    params={
        "type": "object",
        "properties": {
            "char_id": {"type": "integer"},
            "group_id": {"type": "integer"},
            "role": {"type": "string", "description": "member|leader|subordinate"},
            "importance": {"type": "integer"},
        },
        "required": ["char_id", "group_id"],
    },
)
def graph_add_member(
    char_id: int,
    group_id: int,
    role: str = "member",
    importance: int = 3,
) -> dict:
    g = _get_graph()
    if g is None:
        return {"error": "图库未就绪"}
    from src.backend.storage.connection import default_save_manager
    sm = default_save_manager()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 1)
    try:
        g.add_member_of(char_id, group_id, role=role, join_tick=cur_tick, importance=importance)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


GRAPH_TOOLS = [
    "graph_views_as",
    "graph_two_hop_enemies",
    "graph_memory_palace",
    "graph_event_participants",
    "graph_upsert_views",
    "graph_add_member",
]
