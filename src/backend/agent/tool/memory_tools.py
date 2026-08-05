"""src.backend.agent.tool.memory_tools — 记忆专用工具。

提供给 memory_encoder / memory_retriever 等 skill 使用。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.service import memory_service


@tool(
    name="memory_retrieve",
    desc="按需加载角色记忆：先返回印象摘要，再按深度概率抽样，可按索引过滤，支持宫殿展开",
    params={
        "type": "object",
        "properties": {
            "char_id": {"type": "integer"},
            "query": {"type": "string", "description": "自然语言查询"},
            "index_filter": {"type": "object", "description": "{person|location|time|keyword: value}"},
            "max_count": {"type": "integer"},
            "expand_palace": {"type": "boolean"},
            "palace_depth": {"type": "integer"},
        },
        "required": ["char_id"],
    },
)
def memory_retrieve(
    char_id: int,
    query: str = "",
    index_filter: Dict[str, str] = None,
    max_count: int = 20,
    expand_palace: bool = True,
    palace_depth: int = 1,
) -> dict:
    return memory_service.retrieve_memories(
        char_id=char_id,
        query=query or None,
        index_filter=index_filter,
        max_count=max_count,
        expand_palace=expand_palace,
        palace_depth=palace_depth,
    )


@tool(
    name="memory_decay",
    desc="模拟角色记忆衰减：correctness 下降、forget_prob 上升",
    params={
        "type": "object",
        "properties": {
            "char_id": {"type": "integer"},
            "ticks_passed": {"type": "integer"},
        },
        "required": ["char_id"],
    },
)
def memory_decay(char_id: int, ticks_passed: int = 1) -> dict:
    return memory_service.decay_memories(char_id, ticks_passed)


@tool(
    name="memory_distort",
    desc="篡改记忆内容（虚假记忆植入）",
    params={
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer"},
            "new_content": {"type": "string"},
        },
        "required": ["memory_id", "new_content"],
    },
)
def memory_distort(memory_id: int, new_content: str) -> dict:
    try:
        return memory_service.distort_memory(memory_id, new_content)
    except ValueError as e:
        return {"error": str(e)}


@tool(
    name="memory_palace",
    desc="记忆宫殿展开：以某条记忆为中心，BFS 展开关联记忆",
    params={
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer"},
            "depth": {"type": "integer"},
        },
        "required": ["memory_id"],
    },
)
def memory_palace(memory_id: int, depth: int = 2) -> dict:
    return memory_service.get_palace(memory_id, depth)


@tool(
    name="memory_encode_event",
    desc="把一条事件编码为参与人各自的记忆（按角色深度分配）",
    params={
        "type": "object",
        "properties": {"event_id": {"type": "integer"}},
        "required": ["event_id"],
    },
)
def memory_encode_event(event_id: int) -> dict:
    try:
        return {"memories": memory_service.encode_event_to_memories(event_id)}
    except ValueError as e:
        return {"error": str(e)}


MEMORY_TOOLS = [
    "memory_retrieve", "memory_decay", "memory_distort",
    "memory_palace", "memory_encode_event",
]
