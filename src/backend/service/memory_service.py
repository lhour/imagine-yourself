"""src.backend.service.memory_service — 记忆按需加载服务。

阶段一只实现骨架与查询逻辑，LLM 编码/衰减/篡改逻辑在阶段二接入。
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional

from src.backend.storage import models
from src.backend.storage.connection import default_save_manager


# 深度加载策略：每次 retrieve 必加载深度 5，其余按概率加载
DEPTH_LOAD_PROB = {
    5: 1.0,   # 必加载
    4: 0.85,
    3: 0.55,
    2: 0.25,
    1: 0.10,
    0: 0.03,
}


def retrieve_memories(
    char_id: int,
    query: Optional[str] = None,
    index_filter: Optional[Dict[str, str]] = None,
    max_count: int = 20,
    include_outline_only: bool = True,
    expand_palace: bool = True,
    palace_depth: int = 1,
) -> Dict[str, Any]:
    """按需加载角色记忆。

    加载顺序：
    1. 先拉 character_impressions（顶层摘要）
    2. 按深度概率筛选记忆（必加载深度 5，深度 0 几乎不加载）
    3. 按 index_filter 过滤（person/location/time/keyword）
    4. 若 expand_palace，按 memory_links 展开关联记忆
    5. 抽样 max_count 条
    """
    # 1. 印象摘要
    impressions = models.CharacterImpression.list(
        where="observer_char_id = ?", params=[char_id], limit=100
    )
    outline = [i.to_dict() for i in impressions]

    # 2. 拉该角色的所有记忆
    all_mems = models.Memory.list(
        where="char_id = ?", params=[char_id], order_by="depth DESC, remember_tick DESC",
        limit=10000,
    )
    if not all_mems:
        return {"outline": outline, "memories": [], "expanded": []}

    # 3. 按 index_filter 过滤
    if index_filter or query:
        idx_map: Dict[int, bool] = {}
        if index_filter:
            for k, v in index_filter.items():
                rows = models.MemoryIndex.list(
                    where="char_id = ? AND index_type = ? AND index_value LIKE ?",
                    params=[char_id, k, f"%{v}%"], limit=10000
                )
                for r in rows:
                    idx_map[r.memory_id] = True
        all_mems = [m for m in all_mems if (not index_filter) or m.id in idx_map]

    # 4. 按深度概率抽样
    rng = random.Random()
    selected: List[models.Memory] = []
    for m in all_mems:
        prob = DEPTH_LOAD_PROB.get(m.depth, 0.3)
        if rng.random() < prob:
            selected.append(m)
        if len(selected) >= max_count * 2:
            break

    # 5. 抽样到 max_count
    if len(selected) > max_count:
        selected = rng.sample(selected, max_count)

    # 6. 宫殿展开
    expanded: List[Dict[str, Any]] = []
    if expand_palace and selected:
        sel_ids = {m.id for m in selected}
        # 找关联记忆
        for m in selected:
            links = models.MemoryLink.list(
                where="char_id = ? AND (memory_a_id = ? OR memory_b_id = ?)",
                params=[char_id, m.id, m.id], limit=10
            )
            for link in links:
                other_id = link.memory_b_id if link.memory_a_id == m.id else link.memory_a_id
                if other_id in sel_ids:
                    continue
                om = models.Memory.get(other_id)
                if om:
                    expanded.append({
                        "via_memory_id": m.id,
                        "link_type": link.link_type,
                        "strength": link.link_strength,
                        "memory": om.to_dict(),
                    })

    return {
        "outline": outline,
        "memories": [m.to_dict() for m in selected],
        "expanded": expanded[:max_count],
    }


def encode_event_to_memories(event_id: int) -> List[Dict[str, Any]]:
    """事件 → 每个参与人一条记忆。阶段一仅做机械写入，LLM 视角偏差在阶段二补。"""
    e = models.Event.get(event_id)
    if not e:
        raise ValueError(f"事件 {event_id} 不存在")
    parts = models.EventParticipant.list(where="event_id = ?", params=[event_id], limit=1000)
    sm = default_save_manager()
    meta = sm.get_meta()
    created = []
    for p in parts:
        if p.participant_type != "character":
            continue
        # 根据 role 决定 depth + correctness
        role = p.role_raw or "witness"
        if "protagonist" in role:
            depth, correctness = 5, 100
        elif "supporting" in role or "main" in role:
            depth, correctness = 4, 90
        elif "witness" in role or "bystander" in role:
            depth, correctness = 2, 60
        else:
            depth, correctness = 3, 80

        # memory_raw 是事件内容的副本（阶段二 LLM 会改写为该角色视角）
        mem = models.Memory.create(
            char_id=p.participant_id,
            source_event_id=event_id,
            memory_raw=e.content_raw,
            memory_polished=e.content_polished,
            depth=depth,
            correctness=correctness,
            perspective_bias_raw=p.perception_raw or "",
            remember_tick=meta["tick_num"],
        )
        created.append(mem.to_dict())
    return created


def decay_memories(char_id: int, ticks_passed: int) -> Dict[str, Any]:
    """记忆衰减：correctness 随时间下降，forget_prob 上升。

    阶段一用线性衰减，阶段二接入 LLM 失真改写。
    """
    mems = models.Memory.list(where="char_id = ?", params=[char_id], limit=10000)
    n = 0
    for m in mems:
        # 衰减率：每 tick 衰减 0.5 % × (6 - depth)，深度高衰减少
        decay_rate = 0.005 * (6 - m.depth) * ticks_passed
        new_correctness = max(0, int(m.correctness * (1 - decay_rate)))
        new_forget_prob = min(1.0, m.forget_prob + decay_rate * 0.5)
        models.Memory.update(m.id, correctness=new_correctness, forget_prob=new_forget_prob)
        n += 1
    return {"decayed_count": n, "ticks_passed": ticks_passed}


def distort_memory(memory_id: int, new_content: str) -> Dict[str, Any]:
    """篡改记忆内容（用于剧情事件：被洗脑/催眠/虚假记忆植入）。"""
    m = models.Memory.update(memory_id, memory_raw=new_content)
    if not m:
        raise ValueError(f"记忆 {memory_id} 不存在")
    # 标记为虚假记忆
    models.Memory.update(memory_id, is_false=1)
    return m.to_dict()


def get_palace(memory_id: int, depth: int = 2) -> Dict[str, Any]:
    """记忆宫殿展开：以 memory_id 为中心，BFS 展开关联记忆。

    depth=1 只展开直接关联；depth=2 展开两层。
    """
    visited = {memory_id}
    layers: List[List[Dict[str, Any]]] = []
    current_level = [memory_id]
    for d in range(depth):
        next_level: List[int] = []
        layer_data: List[Dict[str, Any]] = []
        for mid in current_level:
            links = models.MemoryLink.list(
                where="memory_a_id = ? OR memory_b_id = ?",
                params=[mid, mid], limit=100
            )
            for link in links:
                other_id = link.memory_b_id if link.memory_a_id == mid else link.memory_a_id
                if other_id in visited:
                    continue
                visited.add(other_id)
                next_level.append(other_id)
                om = models.Memory.get(other_id)
                if om:
                    layer_data.append({
                        "from_memory_id": mid,
                        "link_type": link.link_type,
                        "strength": link.link_strength,
                        "memory": om.to_dict(),
                    })
        if layer_data:
            layers.append(layer_data)
        current_level = next_level
        if not current_level:
            break
    center = models.Memory.get(memory_id)
    return {
        "center": center.to_dict() if center else None,
        "layers": layers,
        "total_related": sum(len(l) for l in layers),
    }
