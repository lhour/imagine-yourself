"""src.backend.service.memory_service — 记忆按需加载服务。

A2 重构（v4 字段 + 向量召回）：
- 读路径废弃 CharacterImpression / MemoryIndex / MemoryLink 旧表
- 印象摘要改读 character_impressions_cache（图库 ViewsAs 镜像）
- 精确过滤改用 memories.person_ids / location_ids JSON 数组
- 有 query 时走向量语义召回（search_memories_mixed），无 query 走确定性加载
- 记忆宫殿展开暂保留 memory_links 表（后续迁图库 MemoryLink 边）
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

from src.backend.storage import models
from src.backend.storage.connection import default_save_manager

logger = logging.getLogger(__name__)


# 深度加载策略（仅用于 prompt 注入时的概率抽样，retrieve_memories 读路径不再使用）
DEPTH_LOAD_PROB = {
    5: 1.0,   # 必加载
    4: 0.85,
    3: 0.55,
    2: 0.25,
    1: 0.10,
    0: 0.03,
}


def _parse_json_array(raw: Optional[str]) -> List[Any]:
    """安全解析 JSON 数组字段（person_ids / location_ids / emotion_tags）。"""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def retrieve_memories(
    char_id: int,
    query: Optional[str] = None,
    index_filter: Optional[Dict[str, str]] = None,
    max_count: int = 20,
    include_outline_only: bool = True,
    expand_palace: bool = True,
    palace_depth: int = 1,
) -> Dict[str, Any]:
    """按需加载角色记忆（A2 重构：v4 字段 + 向量召回）。

    读路径改造：
    1. 印象摘要改读 character_impressions_cache（图库 ViewsAs 镜像），废弃 CharacterImpression
    2. 精确过滤改用 memories.person_ids / location_ids JSON 数组，废弃 MemoryIndex
    3. 有 query 时走向量语义召回（search_memories_mixed），深度加权排序
    4. 无 query 时走确定性加载（depth DESC + remember_tick DESC）
    5. 记忆宫殿展开保留（暂用 memory_links 表，后续迁图库）

    index_filter 支持的 key：
    - person: 按人物ID过滤（匹配 person_ids JSON 数组）
    - location: 按地点ID过滤（匹配 location_ids JSON 数组）
    - emotion: 按情绪标签过滤（匹配 emotion_tags JSON 数组）
    """
    # 1. 印象摘要 —— 改读 character_impressions_cache（v4 图库镜像）
    outline: List[Dict[str, Any]] = []
    try:
        impressions = models.CharacterImpressionsCache.list(
            where="observer_char_id = ?", params=[char_id], limit=100
        )
        outline = [i.to_dict() for i in impressions]
    except Exception as ex:
        # 旧存档可能尚未迁移出 cache 表，回退读 character_impressions 兜底
        logger.warning("character_impressions_cache 读取失败 char_id=%s，回退旧表: %s", char_id, ex)
        try:
            impressions = models.CharacterImpression.list(
                where="observer_char_id = ?", params=[char_id], limit=100
            )
            outline = [i.to_dict() for i in impressions]
        except Exception:
            pass

    # 2. 有 query 且向量库可用 → 语义召回（search_memories_mixed 支持精确过滤）
    vs = models.vector()
    selected_mems: List[models.Memory] = []

    if query and vs is not None:
        try:
            person_filter = None
            location_filter = None
            if index_filter:
                person_filter = index_filter.get("person")
                location_filter = index_filter.get("location")
            hits = vs.search_memories_mixed(
                query_text=query,
                char_id=char_id,
                person_filter=person_filter,
                location_filter=location_filter,
                top_k=max_count,
            )
            # hits 是 dict 列表，需回查 Memory 实体
            hit_ids = [h["memory_id"] for h in hits if h.get("memory_id")]
            for mid in hit_ids:
                m = models.Memory.get(mid)
                if m:
                    selected_mems.append(m)
        except Exception as ex:
            logger.warning("向量语义召回失败 char_id=%s query=%s，降级确定性加载: %s",
                           char_id, query[:50] if query else "", ex)

    # 3. 无 query / 向量召回失败 / 无结果 → 确定性加载 + JSON 数组过滤
    if not selected_mems:
        all_mems = models.Memory.list(
            where="char_id = ?", params=[char_id],
            order_by="depth DESC, remember_tick DESC",
            limit=10000,
        )
        if not all_mems:
            return {"outline": outline, "memories": [], "expanded": []}

        # 按 index_filter 过滤（v4：JSON 数组字段）
        if index_filter:
            filtered: List[models.Memory] = []
            for m in all_mems:
                if _match_index_filter(m, index_filter):
                    filtered.append(m)
            all_mems = filtered

        selected_mems = all_mems[:max_count]

    # 4. 记忆宫殿展开（暂用 memory_links 表）
    expanded: List[Dict[str, Any]] = []
    if expand_palace and selected_mems:
        sel_ids = {m.id for m in selected_mems}
        for m in selected_mems:
            try:
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
            except Exception as ex:
                logger.debug("memory_links 展开失败 char_id=%s mem_id=%s: %s", char_id, m.id, ex)

    return {
        "outline": outline,
        "memories": [m.to_dict() for m in selected_mems],
        "expanded": expanded[:max_count],
    }


def _match_index_filter(mem: models.Memory, index_filter: Dict[str, str]) -> bool:
    """检查单条记忆是否匹配 index_filter（v4 JSON 数组字段）。

    支持的 key：person / location / emotion。
    每个 key 的 value 是要匹配的 ID/标签字符串。
    """
    for k, v in index_filter.items():
        if k == "person":
            ids = _parse_json_array(getattr(mem, "person_ids", None))
            # 同时匹配 char_id 本身（记忆所属角色）与 person_ids 列表
            if str(mem.char_id) != str(v) and str(v) not in [str(x) for x in ids]:
                return False
        elif k == "location":
            ids = _parse_json_array(getattr(mem, "location_ids", None))
            if str(v) not in [str(x) for x in ids]:
                return False
        elif k == "emotion":
            tags = _parse_json_array(getattr(mem, "emotion_tags", None))
            if str(v) not in [str(x) for x in tags]:
                return False
        # 其他 key（time/keyword）暂不支持精确过滤，避免误用旧 MemoryIndex
    return True


def sample_memories_for_prompt(
    char_id: int,
    max_count: int = 20,
) -> List[Dict[str, Any]]:
    """概率抽样记忆用于 prompt 注入（上下文预算控制）。

    仅在向 LLM prompt 注入记忆时使用：深度越高越可能被加载，
    避免低深度记忆淹没上下文。读路径（前端展示/检索）请用 retrieve_memories。
    """
    all_mems = models.Memory.list(
        where="char_id = ?", params=[char_id], order_by="depth DESC, remember_tick DESC",
        limit=10000,
    )
    if not all_mems:
        return []
    rng = random.Random()
    selected: List[models.Memory] = []
    for m in all_mems:
        prob = DEPTH_LOAD_PROB.get(m.depth, 0.3)
        if rng.random() < prob:
            selected.append(m)
        if len(selected) >= max_count * 2:
            break
    if len(selected) > max_count:
        selected = rng.sample(selected, max_count)
    return [m.to_dict() for m in selected]


def _rewrite_memories_by_perspective(
    event: Any,
    participants: List[Any],
) -> Dict[int, Dict[str, Any]]:
    """B2：按角色视角批量改写记忆。

    调一次轻量 LLM，传入事件原文 + 所有参与角色的姓名/性格/角色定位，
    一次性产出每个角色的主观记忆版本（memory_raw）+ 视角偏差（perspective_bias_raw）
    + 情绪标签（emotion_tags）。

    返回 {char_id: {"memory_raw": str, "perspective_bias_raw": str, "emotion_tags": [str]}}。
    mock 模式或调用失败时返回空 dict，调用方回退用事件原文。
    """
    from src.backend import deepseek_client

    # mock 模式直接跳过，回退原文
    if deepseek_client.is_mock_mode():
        return {}

    # 收集参与角色信息（姓名/性格/角色定位）
    char_infos: List[Dict[str, Any]] = []
    char_ids: List[int] = []
    for p in participants:
        if p.participant_type != "character":
            continue
        c = models.Character.get(p.participant_id)
        if not c:
            continue
        char_infos.append({
            "char_id": p.participant_id,
            "name": c.name,
            "role": p.role_raw or "witness",
            "personality": getattr(c, "personality_raw", "") or getattr(c, "personality", "") or "",
        })
        char_ids.append(p.participant_id)

    if not char_infos:
        return {}

    system_prompt = (
        "你是记忆编码器。给定一个客观事件和多个参与角色，请从每个角色的视角改写他们各自记得的版本。\n\n"
        "规则：\n"
        "1. 每个角色记得的内容受其性格、角色定位（主角/配角/旁观者）影响\n"
        "2. 主角/第一人称参与者记得最详细准确；旁观者只记得表面\n"
        "3. 同一事件不同角色可能关注不同细节、产生不同情绪反应\n"
        "4. 严禁凭空捏造事件中不存在的情节，只做视角偏差与情感滤镜\n"
        "5. perspective_bias_raw 记录该角色记忆与客观事件的偏差点（如'忽略了对方的善意'）\n"
        "6. emotion_tags 是该角色对此事的情绪标签数组（如['愤怒','委屈']）\n\n"
        "输出 JSON：\n"
        '{"rewrites": [{"char_id": 1, "memory_raw": "...", "perspective_bias_raw": "...", "emotion_tags": ["..."]}, ...]}'
    )
    user_prompt = (
        f"【客观事件】\n{event.content_raw}\n\n"
        f"【参与角色】\n{json.dumps(char_infos, ensure_ascii=False)}\n\n"
        f"请为每个角色生成其主观记忆版本。"
    )

    try:
        resp = deepseek_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=2048,
        )
        content = resp.get("content", "")
        parsed = None
        if content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                import re
                m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
                if m:
                    try:
                        parsed = json.loads(m.group(1))
                    except json.JSONDecodeError:
                        pass
        if not parsed or "rewrites" not in parsed:
            return {}
        result: Dict[int, Dict[str, Any]] = {}
        for rw in parsed["rewrites"]:
            cid = rw.get("char_id")
            if cid is None:
                continue
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            if cid_int not in char_ids:
                continue
            result[cid_int] = {
                "memory_raw": rw.get("memory_raw", ""),
                "perspective_bias_raw": rw.get("perspective_bias_raw", ""),
                "emotion_tags": rw.get("emotion_tags", []),
            }
        return result
    except Exception as ex:
        logger.warning("B2 视角改写 LLM 调用失败 event_id=%s: %s", event.id, ex)
        return {}


def encode_event_to_memories(event_id: int) -> List[Dict[str, Any]]:
    """事件 → 每个参与人一条记忆。

    A2：填充 v4 字段（person_ids/location_ids/emotion_tags）+ 写向量库回填 vector_id。
    B2：调 LLM 按角色视角改写 memory_raw（mock 模式/失败时回退事件原文）。
    """
    e = models.Event.get(event_id)
    if not e:
        raise ValueError(f"事件 {event_id} 不存在")
    parts = models.EventParticipant.list(where="event_id = ?", params=[event_id], limit=1000)
    sm = default_save_manager()
    meta = sm.get_meta()

    # A2：提取事件级 v4 字段 —— 涉及的人物ID列表 + 地点ID列表 + 情绪标签
    person_ids = [p.participant_id for p in parts if p.participant_type == "character"]
    location_ids = []
    loc_map = getattr(e, "location_map_id", None)
    if loc_map:
        location_ids.append(loc_map)
    # emotion_tags：从 event.tags 推断（tags 可能是 JSON 字符串或 None）
    emotion_tags = []
    raw_tags = getattr(e, "tags", None)
    if raw_tags:
        try:
            emotion_tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
        except Exception:
            emotion_tags = []
    person_ids_json = json.dumps(person_ids, ensure_ascii=False)
    location_ids_json = json.dumps(location_ids, ensure_ascii=False)
    emotion_tags_json = json.dumps(emotion_tags, ensure_ascii=False)

    # A2：获取向量库实例（switch_save 时已初始化并缓存，不可用时降级）
    vs = models.vector()

    # B2：批量调 LLM 按角色视角改写记忆（mock 模式/失败返回空 dict，回退原文）
    rewrites = _rewrite_memories_by_perspective(e, parts)

    # B1 修复：按 (char_id, source_event_id) 去重，避免重复编码产生重复记忆。
    # 同一事件可能被 tick_once_v4 和 _character_update 各调一次 encode，也可能
    # 因参与者重复（同一角色多条 participant 记录）导致重复。这里统一兜底去重。
    seen_char_ids: set[int] = set()
    created = []
    for p in parts:
        if p.participant_type != "character":
            continue
        if p.participant_id in seen_char_ids:
            continue
        # 查库确认该 (char_id, source_event_id) 尚无记忆
        already = models.Memory.list(
            where="char_id = ? AND source_event_id = ?",
            params=[p.participant_id, event_id],
            limit=1,
        )
        if already:
            seen_char_ids.add(p.participant_id)
            continue
        seen_char_ids.add(p.participant_id)

        # 根据 role 决定 depth + correctness
        role = p.role_raw or "witness"
        if "protagonist" in role or "first_hand" in role or role == "主角":
            depth, correctness = 5, 100
        elif "supporting" in role or "main" in role:
            depth, correctness = 4, 90
        elif "witness" in role or "bystander" in role or role == "旁观者":
            depth, correctness = 2, 60
        else:
            depth, correctness = 3, 80

        # B2：优先用 LLM 视角改写版本，回退事件原文
        rw = rewrites.get(p.participant_id, {})
        mem_raw = rw.get("memory_raw") or e.content_raw
        persp_bias = rw.get("perspective_bias_raw") or p.perception_raw or ""
        # B2：角色级情绪标签优先于事件级
        rw_emotion_tags = rw.get("emotion_tags") or []
        final_emotion_tags = rw_emotion_tags if rw_emotion_tags else emotion_tags
        final_emotion_tags_json = json.dumps(final_emotion_tags, ensure_ascii=False)

        mem = models.Memory.create(
            char_id=p.participant_id,
            source_event_id=event_id,
            memory_raw=mem_raw,
            memory_polished=e.content_polished,
            depth=depth,
            correctness=correctness,
            perspective_bias_raw=persp_bias,
            remember_tick=meta["tick_num"],
            # A2：填充 v4 字段
            person_ids=person_ids_json,
            location_ids=location_ids_json,
            emotion_tags=final_emotion_tags_json,
        )

        # A2：写向量库回填 vector_id（失败时降级为仅关系库查询，但记录告警便于排查）
        if vs is not None:
            try:
                embed_text = mem.memory_raw or e.content_raw or ""
                vs.upsert_memory(mem.id, embed_text)
                models.Memory.update(mem.id, vector_id=str(mem.id))
            except Exception as vex:
                # 不阻断记忆写入，但留下告警 —— 之前 except: pass 导致
                # sqlite3.serialize 缺失这类错误被完全吞掉、vector_id 永不回填
                logger.warning(
                    "向量库 upsert_memory 失败 mem_id=%s event_id=%s: %s",
                    mem.id, event_id, vex,
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
