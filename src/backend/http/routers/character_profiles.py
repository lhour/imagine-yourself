"""src.backend.http.routers.character_profiles — 角色完整档案聚合端点。

聚合角色在数据库中的各类信息：
记忆（memories）、印象（character_impressions）、任务（character_quests）、
纲领（character_agendas）、群体关系（character_group_relations）、
参与事件（event_participants + events）、记忆关联（memory_links）。
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.backend.http.deps import require_active_save
from src.backend.storage import models
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/characters", tags=["characters"])


def _name_map(model_cls, ids) -> Dict[int, str]:
    """id → name 映射（用于 join 名称）。"""
    out: Dict[int, str] = {}
    for i in ids:
        obj = model_cls.get(i)
        if obj:
            out[i] = getattr(obj, "name", "") or ""
    return out


@router.get("/{char_id}/profile")
def character_profile(char_id: int, sm: SaveManager = Depends(require_active_save)):
    """返回角色的完整档案（记忆/印象/任务/纲领/群体关系/事件/关联）。"""
    ch = models.Character.get(char_id)
    if not ch:
        raise HTTPException(404, f"角色 id={char_id} 不存在")

    # 印象（该角色观察到的他人）
    impressions = models.CharacterImpression.list(
        where="observer_char_id = ?", params=[char_id], limit=500
    )
    imp_target_ids = {i.target_char_id for i in impressions}
    imp_names = _name_map(models.Character, imp_target_ids)
    impressions_out = [
        {
            "target_char_id": i.target_char_id,
            "target_name": imp_names.get(i.target_char_id, ""),
            "impression_polished": i.impression_polished or i.impression_raw,
            "favorability": i.favorability,
            "trust": i.trust,
            "fear": i.fear,
            "last_update_tick": i.last_update_tick,
        }
        for i in impressions
    ]

    # 记忆
    memories = models.Memory.list(
        where="char_id = ?", params=[char_id],
        order_by="depth DESC, remember_tick DESC", limit=100,
    )
    memories_out = [
        {
            "id": m.id,
            "memory_polished": m.memory_polished or m.memory_raw,
            "depth": m.depth,
            "correctness": m.correctness,
            "is_false": m.is_false,
            "remember_tick": m.remember_tick,
            "mood": m.mood,
        }
        for m in memories
    ]

    # 任务 / 纲领
    quests = models.CharacterQuest.list(
        where="char_id = ?", params=[char_id], order_by="priority DESC", limit=100
    )
    quests_out = [
        {
            "id": q.id,
            "title": q.title,
            "status": q.status,
            "priority": q.priority,
            "desc_polished": q.desc_polished or q.desc_raw,
        }
        for q in quests
    ]
    agendas = models.CharacterAgenda.list(
        where="char_id = ?", params=[char_id], order_by="priority DESC", limit=100
    )
    agendas_out = [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "priority": a.priority,
            "principle_polished": a.principle_polished or a.principle_raw,
        }
        for a in agendas
    ]

    # 群体关系
    rels = models.CharacterGroupRelation.list(
        where="char_id = ?", params=[char_id], limit=200
    )
    rel_group_ids = {r.group_id for r in rels}
    rel_group_names = _name_map(models.Group, rel_group_ids)
    groups_out = [
        {
            "group_id": r.group_id,
            "group_name": rel_group_names.get(r.group_id, ""),
            "role_raw": r.role_raw,
            "importance_in_group": r.importance_in_group,
            "join_tick": r.join_tick,
        }
        for r in rels
    ]

    # 参与事件
    parts = models.EventParticipant.list(
        where="participant_type = 'character' AND participant_id = ?",
        params=[char_id], order_by="event_id DESC", limit=50,
    )
    recent_events_out = []
    for p in parts:
        ev = models.Event.get(p.event_id)
        if ev:
            recent_events_out.append({
                "event_id": ev.id,
                "tick_num": ev.tick_num,
                "event_type": ev.event_type,
                "content_polished": ev.content_polished or ev.content_raw,
                "role_raw": p.role_raw,
            })

    # 记忆关联（关系网：与该角色共享记忆关联线的其他记忆）
    links = models.MemoryLink.list(
        where="char_id = ?", params=[char_id], limit=200
    )
    related_mem_ids = set()
    for lk in links:
        related_mem_ids.add(lk.memory_a_id)
        related_mem_ids.add(lk.memory_b_id)
    relation_mem = [
        {
            "memory_id": mid,
            "link_type": lk.link_type,
            "link_strength": lk.link_strength,
        }
        for lk in links for mid in (lk.memory_a_id, lk.memory_b_id)
    ]

    return {
        "character": ch.to_dict(),
        "impressions": impressions_out,
        "memories": memories_out,
        "quests": quests_out,
        "agendas": agendas_out,
        "groups": groups_out,
        "recent_events": recent_events_out,
        "memory_links": relation_mem,
    }