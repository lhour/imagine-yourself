"""src.backend.agent.pipeline_v4 — v4 五节点管线（pre_analyzer → actor_decide → coordinator → character_updater → global_updater）。

v4 设计要点：
1. **前置分析节点 (pre_analyzer)**：分析当前背景/人物/场景，输出任务指令作为后续节点的 prompt 组成部分
2. **角色并发推演节点 (actor_decide)**：对每个角色并发决策，支持反应式决策（角色可声明"等 A 出招再决定"）
3. **统筹节点 (coordinator)**：合并所有角色动作，校验合法性+顺序，支持打回重生成，输出完整剧情
4. **角色更新节点 (character_updater)**：基于剧情分析每个角色的数据变更（记忆/好感/经历/性格等），双写关系库+图库
5. **全局更新节点 (global_updater)**：地形变化/地图扩展/世界观/文明/科技等全局变更写入

相比旧管线的改进：
- 反应式决策：角色可声明 dependency（等待他人动作），coordinator 按依赖拓扑排序
- 打回循环：非法动作可被打回，最多 2 次重试
- 双写一致性：character_updater 同时维护关系库 impression_cache 与图库 ViewsAs 边
- 锚点剧情感知：pre_analyzer 会注入当前活跃锚点，coordinator 检查是否满足锚点必然性
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from src.backend import deepseek_client
from src.backend.agent import trace
from src.backend.agent.skill.loader import render_skill
from src.backend.agent.tool.base import ToolManager
from src.backend.env import load_backend_env
from src.backend.service import memory_service, world_service
from src.backend.storage import models
from src.backend.storage.connection import default_save_manager

load_backend_env()


def _build_variables() -> Dict[str, Any]:
    sm = default_save_manager()
    if not sm.active_save:
        return {}
    meta = sm.get_meta()
    from src.backend.http.deps import get_global_config
    sim = get_global_config().get("simulation", {})

    # v5: 玩法选项与上下文打包
    try:
        options = sm.get_gameplay_options()
        from src.backend.agent.context_packager import pack_context_for_skill
        context_vars = pack_context_for_skill(sm, options, "_build_variables")
    except Exception:
        context_vars = {}

    # 世界修改状态
    world_modify_status = "允许" if options.get("world_modify_allowed", False) else "禁止"

    variables: Dict[str, Any] = {
        "tick_num": meta.get("tick_num", 0),
        "game_time": meta.get("game_time", ""),
        "era_name": meta.get("era_name", ""),
        "script_name": meta.get("script_name", ""),
        "role_name": (sm.get_protagonist() or {}).get("name", ""),
        "polish_mode": sim.get("polish_mode", "none"),
        # v5 新增：上下文打包变量
        "world_background": context_vars.get("world_background", ""),
        "stable_context": context_vars.get("stable_context", ""),
        "stable_context_version": context_vars.get("stable_context_version", "0"),
        "gameplay_style_block": context_vars.get("gameplay_style_block", ""),
        "entity_quota_block": context_vars.get("entity_quota_block", ""),
        "dynamic_entities": context_vars.get("dynamic_entities", ""),
        "world_modify_status": world_modify_status,
    }
    return variables


def call_skill(
    skill_name: str,
    user_prompt: str = "",
    variables: Optional[Dict[str, Any]] = None,
    extra_tools: Optional[List[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    variables = {**_build_variables(), **(variables or {})}
    system_prompt = render_skill(skill_name, variables)
    from src.backend.agent.skill.loader import get_skill
    fs = get_skill(skill_name)
    tool_names: List[str] = []
    if fs:
        tool_names.extend(fs.tools)
    if extra_tools:
        tool_names.extend(extra_tools)
    tools_schema = ToolManager.schemas_for(tool_names)

    def _tool_executor(name: str, args: Dict[str, Any]) -> Any:
        return ToolManager.execute(name, args)

    with trace.span(f"skill:{skill_name}", "skill_call", skill_name=skill_name) as ss:
        resp = deepseek_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt or "(无 user prompt，按 system 指令执行)",
            tools=tools_schema if tools_schema else None,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_rounds=5,
            tool_executor=_tool_executor if tools_schema else None,
        )
        ss.record(rounds=resp.get("rounds", 1), mock=deepseek_client.is_mock_mode(), usage=resp.get("usage"))

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

    return {
        "skill": skill_name,
        "content": content,
        "parsed": parsed,
        "tool_calls": resp.get("tool_calls"),
        "tool_results": resp.get("tool_results", []),
        "usage": resp.get("usage"),
        "elapsed_ms": resp.get("elapsed_ms"),
        "rounds": resp.get("rounds", 1),
        "mock": deepseek_client.is_mock_mode(),
    }


def _run_parallel(fns: List[Any], max_workers: int = 8) -> List[Any]:
    if len(fns) <= 1:
        return [f() for f in fns]
    ctx = trace.capture_context()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(trace.run_in_context, ctx, f) for f in fns]
        return [f.result() for f in futures]


# ============================================================
# Node 0.6: 任务/纲领监控（10.2 时间模型）
# ============================================================

def _monitor_quests_agendas(meta: Dict[str, Any]) -> Dict[str, Any]:
    """任务/纲领监控（并发）。

    10.2 重构：quest_monitor 按 deadline_game_time 判断超时，
    agenda_monitor 按 review_game_time 判断回顾，均用游戏时间而非 tick。
    """
    game_time = meta.get("game_time", "")
    tick_num = meta.get("tick_num", 0)

    def _run_quest():
        try:
            return call_skill(
                "quest_monitor",
                user_prompt=f"检查所有 in_progress / planned 任务，按 deadline_game_time 判断是否超时/完成/受阻。当前游戏时间：{game_time}（tick {tick_num}）",
                temperature=0.2,
            )
        except Exception as ex:
            return {"mock": True, "error": str(ex)}

    def _run_agenda():
        try:
            return call_skill(
                "agenda_monitor",
                user_prompt=f"检查所有 active / dormant 纲领，按 review_game_time 判断是否需回顾/冲突/休眠/唤醒。当前游戏时间：{game_time}（tick {tick_num}）",
                temperature=0.2,
            )
        except Exception as ex:
            return {"mock": True, "error": str(ex)}

    qm_result, am_result = _run_parallel([_run_quest, _run_agenda])

    qm_parsed = qm_result.get("parsed") or {}
    am_parsed = am_result.get("parsed") or {}
    return {
        "quest_checked": qm_parsed.get("checked", 0),
        "quest_completed": len(qm_parsed.get("completed", [])),
        "quest_failed": len(qm_parsed.get("failed", [])),
        "quest_blocked": len(qm_parsed.get("blocked", [])),
        "agenda_checked": am_parsed.get("checked", 0),
        "agenda_reviewed": len(am_parsed.get("reviewed", [])),
        "agenda_blocked": len(am_parsed.get("blocked", [])),
        "agenda_dormanted": len(am_parsed.get("dormanted", [])),
        "agenda_awakened": len(am_parsed.get("awakened", [])),
        "mock": qm_result.get("mock") or am_result.get("mock"),
    }


# ============================================================
# Node 0.7: 周期事件调度（10.3）
# ============================================================

def _dispatch_scheduled_events(
    meta: Dict[str, Any],
    events_created: List[int],
) -> Dict[str, Any]:
    """周期事件调度器（10.3）。

    扫描到期的 scheduled_events，生成对应事件，推进下次触发时间。
    依赖 game_time_utils 比较游戏时间。
    """
    from src.backend.service.game_time_utils import compare as gt_compare

    game_time = meta.get("game_time", "")
    tick_num = meta.get("tick_num", 0)

    # 拉取所有活跃周期事件
    try:
        scheduled = models.ScheduledEvent.list(
            where="active = 1", order_by="next_trigger_game_time ASC", limit=200
        )
    except Exception:
        return {"scanned": 0, "triggered": 0, "skipped": True}

    if not scheduled:
        return {"scanned": 0, "triggered": 0}

    # 筛选到期事件（next_trigger_game_time <= 当前游戏时间）
    due = []
    for se in scheduled:
        nt = se.next_trigger_game_time or ""
        if not nt:
            continue
        try:
            cmp = gt_compare(nt, game_time)
            if cmp is not None and cmp <= 0:
                due.append(se)
        except Exception:
            continue

    if not due:
        return {"scanned": len(scheduled), "triggered": 0}

    # 调 skill 生成到期事件内容
    due_dicts = [se.to_dict() for se in due]
    try:
        result = call_skill(
            "scheduled_event_dispatcher",
            user_prompt=(
                f"当前游戏时间：{game_time}（tick {tick_num}）\n\n"
                f"【到期周期事件】\n{json.dumps(due_dicts, ensure_ascii=False, default=str)}\n\n"
                "请为每个到期事件生成事件内容，并返回 JSON。"
            ),
            temperature=0.4,
        )
        parsed = result.get("parsed") or {}
    except Exception:
        parsed = {}

    triggered = parsed.get("triggered", [])
    deactivated = parsed.get("deactivated", [])
    advanced = parsed.get("advanced", [])

    # 落库：为每个触发的事件创建 event 记录
    triggered_count = 0
    for trig in triggered:
        se_id = trig.get("scheduled_event_id")
        content = trig.get("content", "")
        event_type = trig.get("event_type", "scheduled")
        importance = trig.get("importance", 3)
        if not content:
            continue
        try:
            # 查找原 scheduled_event 获取 scope 信息
            se_obj = next((s for s in due if s.id == se_id), None)
            participants = None
            loc_map = None
            if se_obj:
                scope_target = se_obj.scope_target_json or []
                if se_obj.scope == "character" and scope_target:
                    participants = [
                        {"type": "character", "id": tid, "role": "participant", "perception": ""}
                        for tid in scope_target
                    ]
            ev = world_service.create_event(
                event_type=event_type,
                content_raw=content,
                content_polished=content,
                importance=max(0, min(5, importance)),
                participants=participants,
                location_map_id=loc_map,
            )
            if ev.get("id"):
                events_created.append(ev["id"])
                triggered_count += 1
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning(
                "周期事件触发落库失败 se_id=%s: %s", se_id, ex
            )

    # 推进下次触发时间 & 停用
    for adv in advanced:
        se_id = adv.get("scheduled_event_id")
        new_next = adv.get("new_next_trigger", "")
        if se_id and new_next:
            try:
                models.ScheduledEvent.update(se_id, next_trigger_game_time=new_next)
            except Exception:
                pass

    for deact in deactivated:
        se_id = deact.get("scheduled_event_id")
        reason = deact.get("reason", "")
        if se_id:
            try:
                se_obj = models.ScheduledEvent.get(se_id)
                if se_obj:
                    custom = se_obj.custom_attrs or {}
                    custom["deactivate_reason"] = reason
                    models.ScheduledEvent.update(
                        se_id, active=0, deactivated_tick=tick_num, custom_attrs=custom
                    )
            except Exception:
                pass

    return {
        "scanned": len(scheduled),
        "triggered": triggered_count,
        "deactivated": len(deactivated),
        "advanced": len(advanced),
        "mock": result.get("mock") if 'result' in locals() else True,
    }


# ============================================================
# Node 0.8: 消息传播推进（10.1）
# ============================================================

def _propagate_messages(
    meta: Dict[str, Any],
    events_created: List[int],
) -> Dict[str, Any]:
    """消息传播推进器（10.1）。

    1. 为本 tick 新创建且有传播媒介的事件创建 dissemination 记录
    2. 调 rumor_propagator skill 处理到期的 pending 记录，生成失真记忆
    """
    from src.backend.service.propagation_estimator import (
        create_dissemination_records,
        create_public_knowledge_record,
    )
    from src.backend.service.game_time_utils import compare as gt_compare

    game_time = meta.get("game_time", "")
    tick_num = meta.get("tick_num", 0)

    # 1. 为新事件创建传播记录
    dissemination_created = 0
    public_knowledge_created = 0
    for eid in events_created:
        ev = models.Event.get(eid)
        if not ev:
            continue
        medium = getattr(ev, "propagation_medium", None) or "无"
        if medium == "无":
            continue

        # 获取在场角色
        parts = models.EventParticipant.list(where="event_id = ?", params=[eid], limit=1000)
        origin_char_ids = [p.participant_id for p in parts if p.participant_type == "character"]

        # 获取所有活跃角色作为潜在触达目标
        all_chars = models.Character.list(where="dead_at_tick IS NULL", limit=200)
        target_char_ids = [c.id for c in all_chars]

        if medium == "媒体报道":
            # 走广播通道
            pk = create_public_knowledge_record(
                event_id=eid,
                event_content=ev.content_raw,
                medium=medium,
                coverage_scope="全城",
                current_game_time=game_time,
            )
            if pk:
                public_knowledge_created += 1
        else:
            # 走定向传播
            records = create_dissemination_records(
                event_id=eid,
                event_content=ev.content_raw,
                event_location_map_id=ev.location_map_id,
                medium=medium,
                origin_char_ids=origin_char_ids,
                target_char_ids=target_char_ids,
                current_game_time=game_time,
                current_tick=tick_num,
            )
            dissemination_created += len(records)

    # 2. 检查是否有到期的 pending 传播记录
    try:
        pending = models.EventDissemination.list(
            where="status = 'pending'", limit=500
        )
    except Exception:
        pending = []

    due_count = 0
    for ed in pending:
        expected = ed.expected_arrival_game_time or ""
        if not expected:
            continue
        try:
            cmp = gt_compare(expected, game_time)
            if cmp is not None and cmp <= 0:
                due_count += 1
        except Exception:
            continue

    # 3. 有到期记录时调 rumor_propagator skill
    arrived_count = 0
    if due_count > 0:
        try:
            result = call_skill(
                "rumor_propagator",
                user_prompt=(
                    f"当前游戏时间：{game_time}（tick {tick_num}）\n\n"
                    f"有 {due_count} 条到期传播记录待处理。"
                    "请扫描 event_dissemination 表中 status=pending 且 expected_arrival_game_time <= 当前游戏时间的记录，"
                    "为触达角色生成失真记忆。"
                ),
                temperature=0.3,
            )
            parsed = result.get("parsed") or {}
            arrived_count = len(parsed.get("arrived", []))
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning("rumor_propagator 调用失败: %s", ex)

    return {
        "dissemination_created": dissemination_created,
        "public_knowledge_created": public_knowledge_created,
        "due_pending": due_count,
        "arrived": arrived_count,
    }


# ============================================================
# Node 1: 前置分析
# ============================================================

def _pre_analyze(
    seconds: int,
    player_action: Optional[str],
    meta: Dict[str, Any],
    active_chars: List[Any],
    active_anchors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """前置分析节点。

    输出：scene_summary（场景摘要）+ task_instruction（任务指令，会注入到后续每个角色决策的 prompt 中）。
    这一步不做决策，只做信息整合与指令生成。
    """
    # 收集最近事件（给模型做上下文）
    recent_events = models.Event.list(order_by="id DESC", limit=5)
    recent_dicts = [
        {
            "id": e.id,
            "type": e.event_type,
            "content": e.content_raw,
            "tick": e.tick_num,
        }
        for e in recent_events
    ]

    chars_snapshot = [
        {
            "id": c.id,
            "name": c.name,
            "status": c.status,
            "importance": c.importance,
            "abilities": c.ability_raw or "",
        }
        for c in active_chars[:5]
    ]

    user_prompt = (
        f"当前 tick: {meta.get('tick_num')}, 时间跨度: {seconds}秒\n"
        f"当前游戏时间: {meta.get('game_time')}\n"
        f"活跃角色 ({len(active_chars)} 个):\n{json.dumps(chars_snapshot, ensure_ascii=False, default=str)}\n\n"
        f"最近事件:\n{json.dumps(recent_dicts, ensure_ascii=False, default=str)}\n\n"
        f"活跃锚点剧情 ({len(active_anchors)} 个):\n{json.dumps(active_anchors, ensure_ascii=False)}\n\n"
        f"玩家输入: {player_action or '(无)'}\n\n"
        "请分析当前场景背景，输出：\n"
        "1. scene_summary：场景摘要（2-3 句话，描述当前局势、角色位置、紧张度等）\n"
        "2. task_instruction：给后续角色决策节点的指令（告诉模型'发生了什么事，需要做什么'，总结性指导性话术）\n"
        "3. suggested_polish_style：建议的润色风格（可选）"
    )

    result = call_skill(
        "pre_analyzer",
        user_prompt=user_prompt,
        temperature=0.3,
        max_tokens=1024,
    )
    parsed = result.get("parsed") or {}
    return {
        "scene_summary": parsed.get("scene_summary", result.get("content", "")[:200]),
        "task_instruction": parsed.get("task_instruction", ""),
        "suggested_polish_style": parsed.get("suggested_polish_style", "default"),
        "recent_events_count": len(recent_dicts),
        "active_chars_count": len(active_chars),
        "active_anchors_count": len(active_anchors),
        "mock": result.get("mock"),
    }


# ============================================================
# Node 2: 角色并发决策（支持反应式）
# ============================================================

def _actor_decide(
    chars: List[Any],
    pre_analysis: Dict[str, Any],
    player_action: Optional[str],
    proto_id: Optional[int],
    variables: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """对每个角色并发决策。

    支持反应式：角色可返回 dependency 字段声明依赖他人动作。
    例如 B 返回 {"action": "watch_A", "dependency": {"char_id": A.id, "wait_for": "A 的动作"}}
    """
    task_instruction = pre_analysis.get("task_instruction", "")
    scene_summary = pre_analysis.get("scene_summary", "")

    def _decide_one(c: Any) -> Dict[str, Any]:
        scene_vars = {**variables, "role_name": c.name, "scene_description": c.status or "正常"}

        extra_prompt = ""
        if player_action and c.id == proto_id:
            extra_prompt = f"\n（玩家已输入动作：{player_action}，请在此基础上决策）"

        user_prompt = (
            f"【场景摘要】\n{scene_summary}\n\n"
            f"【任务指令】\n{task_instruction}\n\n"
            f"【角色】{c.name}（id={c.id}）\n"
            f"【状态】{c.status or '正常'}\n"
            f"【能力】{c.ability_raw or '未知'}\n"
            f"【性格】{c.personality_raw or '未知'}\n"
            f"【外貌】{c.appearance_raw or '未知'}\n"
            f"【重要度】{c.importance}\n"
            f"{extra_prompt}\n"
            "请决策本 tick 的行动。若你的行动依赖他人（例如等待对方出招），请在 dependency 字段中声明。"
        )

        result = call_skill("actor_decide_v2", user_prompt=user_prompt, variables=scene_vars)
        parsed = result.get("parsed") or {}
        return {
            "char_id": c.id,
            "char_name": c.name,
            "action": parsed.get("action", parsed.get("content", "")),
            "inner_thought": parsed.get("inner_thought", ""),
            "dependency": parsed.get("dependency"),
            "emotion": parsed.get("emotion", ""),
            "target_char_ids": parsed.get("target_char_ids", []),
            "raw": parsed,
        }

    if not chars:
        return []
    return _run_parallel([lambda c=c: _decide_one(c) for c in chars], max_workers=min(len(chars), 8))


# ============================================================
# Node 3: 统筹（含打回重生成循环）
# ============================================================

def _coordinate(
    decisions: List[Dict[str, Any]],
    pre_analysis: Dict[str, Any],
    max_actors: int,
    active_anchors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """统筹节点：合并角色决策，校验合法性，生成完整剧情。

    最多打回 2 次。打回时将非法角色的决策反馈给 actor_decide 重生成。
    active_anchors 直接注入 user_prompt，让 coordinator 在生成 narrative 时
    体现高必然性锚点，并在返回 JSON 中标注本 tick 已满足的锚点 id。
    """
    task_instruction = pre_analysis.get("task_instruction", "")
    decisions_json = json.dumps(decisions, ensure_ascii=False, default=str)

    anchors_block = ""
    if active_anchors:
        anchors_json = json.dumps(active_anchors, ensure_ascii=False, default=str)
        anchors_block = (
            f"【活跃锚点剧情】（共 {len(active_anchors)} 个，inevitability 0-5，5=硬约束必须实现）\n"
            f"{anchors_json}\n\n"
            "注意：inevitability>=3 的锚点应优先在本 tick narrative 中体现走向；"
            "inevitability=5 的锚点必须被实现，否则视为非法。"
            "若本 tick narrative 已充分体现/满足某锚点的 trigger_condition，"
            "把该锚点 id 填入返回 JSON 的 fulfilled_anchor_ids 数组。\n\n"
        )

    user_prompt = (
        f"【任务指令】\n{task_instruction}\n\n"
        f"{anchors_block}"
        f"【角色决策列表】\n{decisions_json}\n\n"
        "请执行以下操作：\n"
        "1. 检查所有决策是否合法（物理上/逻辑上/性格一致性）\n"
        "2. 对有 dependency 的决策，按依赖拓扑排序执行顺序\n"
        "3. 对非法决策，标记 invalid 并说明原因\n"
        "4. 若全部合法，生成一段完整剧情 narrative\n"
        "5. 返回 JSON：{valid: bool, invalid_decisions: [{char_id, reason}], "
        "ordered_sequence: [...], narrative: str, fulfilled_anchor_ids: [int]}\n"
    )

    result = call_skill("coordinator", user_prompt=user_prompt, temperature=0.3,
                        # coordinator 需合并多角色决策 + 生成完整剧情 narrative + 返回 JSON，
                        # 推理模型（deepseek-v4-flash）会把大量 token 花在 reasoning_content 上。
                        # 2048 会被推理耗尽导致 content 为空，此处放宽到 6144 给推理+输出留足空间。
                        max_tokens=6144)
    parsed = result.get("parsed") or {}

    fulfilled_ids = parsed.get("fulfilled_anchor_ids", [])
    if not isinstance(fulfilled_ids, list):
        fulfilled_ids = []

    return {
        "valid": parsed.get("valid", True),
        "invalid_decisions": parsed.get("invalid_decisions", []),
        "ordered_sequence": parsed.get("ordered_sequence", []),
        "narrative": parsed.get("narrative", result.get("content", "")),
        "fulfilled_anchor_ids": fulfilled_ids,
        "rounds": result.get("rounds", 1),
        "mock": result.get("mock"),
        "raw": parsed,
    }


def _coordinate_with_feedback(
    decisions: List[Dict[str, Any]],
    pre_analysis: Dict[str, Any],
    chars: List[Any],
    variables: Dict[str, Any],
    max_retries: int = 2,
    active_anchors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """带打回循环的统筹。"""
    current_decisions = list(decisions)
    sm = default_save_manager()
    proto = sm.get_protagonist()
    proto_id = proto.get("id") if proto else None

    for attempt in range(max_retries + 1):
        coord_result = _coordinate(current_decisions, pre_analysis, len(chars), active_anchors)
        if coord_result["valid"] or attempt >= max_retries:
            coord_result["attempts"] = attempt + 1
            return coord_result

        # 打回：重生成非法角色的决策
        invalid_ids = {d["char_id"] for d in coord_result["invalid_decisions"]}
        retry_chars = [c for c in chars if c.id in invalid_ids]
        if not retry_chars:
            coord_result["attempts"] = attempt + 1
            return coord_result

        # 获取非法原因反馈
        reasons = {d["char_id"]: d.get("reason", "") for d in coord_result["invalid_decisions"]}
        # 用反馈重新决策
        retry_decisions = _actor_decide_with_feedback(retry_chars, reasons, pre_analysis, variables, proto_id)
        # 替换
        current_decisions = [d for d in current_decisions if d["char_id"] not in invalid_ids] + retry_decisions

    coord_result["attempts"] = max_retries + 1
    return coord_result


def _actor_decide_with_feedback(
    chars: List[Any],
    reasons: Dict[int, str],
    pre_analysis: Dict[str, Any],
    variables: Dict[str, Any],
    proto_id: Optional[int],
) -> List[Dict[str, Any]]:
    """带错误反馈的角色决策重生成。"""
    task_instruction = pre_analysis.get("task_instruction", "")
    scene_summary = pre_analysis.get("scene_summary", "")

    def _decide_one(c: Any) -> Dict[str, Any]:
        scene_vars = {**variables, "role_name": c.name, "scene_description": c.status or "正常"}
        reason = reasons.get(c.id, "")
        user_prompt = (
            f"【场景摘要】\n{scene_summary}\n\n"
            f"【任务指令】\n{task_instruction}\n\n"
            f"【角色】{c.name}（id={c.id}）\n"
            f"【状态】{c.status or '正常'}\n"
            f"【能力】{c.ability_raw or '未知'}\n"
            f"【性格】{c.personality_raw or '未知'}\n"
            f"【上一轮决策被否决的原因】{reason}\n"
            "请重新决策本 tick 的行动，确保符合逻辑与性格一致性。"
        )
        result = call_skill("actor_decide_v2", user_prompt=user_prompt, variables=scene_vars)
        parsed = result.get("parsed") or {}
        return {
            "char_id": c.id,
            "char_name": c.name,
            "action": parsed.get("action", parsed.get("content", "")),
            "inner_thought": parsed.get("inner_thought", ""),
            "dependency": parsed.get("dependency"),
            "emotion": parsed.get("emotion", ""),
            "target_char_ids": parsed.get("target_char_ids", []),
            "raw": parsed,
        }

    return _run_parallel([lambda c=c: _decide_one(c) for c in chars], max_workers=min(len(chars), 8))


# ============================================================
# Node 3.5: 动态实体创建（world_react_v2 skill）
# ============================================================

def _world_react_v2(
    narrative: str,
    event_ids: List[int],
    decisions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """v5 新增：基于剧情 narrative 识别并创建动态实体。

    在 coordinator 生成 narrative 后，识别其中提到的新角色/群体/设定等，
    调用 world_react_v2 skill 完成：
    1. 查询既有实体（character_filter 等）
    2. 配额检查（entity_quota_check）
    3. 创建新实体（character_create_dynamic 等）
    4. 写入操作日志（自动）
    """
    if not narrative:
        return {"dynamic_creations": [], "rejected_creations": [], "skipped": True}

    events_data = []
    for eid in event_ids:
        ev = models.Event.get(eid)
        if ev:
            events_data.append({
                "id": eid,
                "type": ev.event_type,
                "content": ev.content_raw,
            })

    decisions_data = [
        {"char_id": d["char_id"], "char_name": d["char_name"],
         "action": d.get("action", "")[:200]}
        for d in decisions[:5]
    ]

    user_prompt = (
        f"【剧情 narrative】\n{narrative[:3000]}\n\n"
        f"【已创建事件】\n{json.dumps(events_data, ensure_ascii=False, default=str)}\n\n"
        f"【角色决策摘要】\n{json.dumps(decisions_data, ensure_ascii=False, default=str)}\n\n"
        "请执行以下操作：\n"
        "1. 阅读 narrative，识别其中首次提到的角色名、群体名、设定名、地名等\n"
        "2. 对每个识别的实体，先用对应 filter 工具查询是否已存在\n"
        "3. 对不存在的新实体，先用 entity_quota_check 检查配额\n"
        "4. 配额通过则调用对应 create_dynamic 工具创建\n"
        "5. 配额超限则在 rejected_creations 中记录，并标记 fallback\n"
        "6. 对设定类实体，仅在 world_modify_allowed=true 时调用 setting_append_dynamic\n"
        "7. 返回 JSON：{dynamic_creations: [...], rejected_creations: [...]}"
    )

    try:
        result = call_skill("world_react_v2", user_prompt=user_prompt, temperature=0.2)
        parsed = result.get("parsed") or {}
        return {
            "dynamic_creations": parsed.get("dynamic_creations", []),
            "rejected_creations": parsed.get("rejected_creations", []),
            "total_created": len(parsed.get("dynamic_creations", [])),
            "total_rejected": len(parsed.get("rejected_creations", [])),
            "mock": result.get("mock"),
        }
    except Exception as e:
        return {
            "dynamic_creations": [],
            "rejected_creations": [],
            "error": str(e),
            "skipped": True,
        }


# ============================================================
# Node 4: 角色更新（双写关系库+图库）
# ============================================================

def _character_update(
    decisions: List[Dict[str, Any]],
    coord_result: Dict[str, Any],
    event_ids: List[int],
) -> Dict[str, Any]:
    """角色更新节点。

    基于剧情结果分析每个角色的数据变更：
    - 新增/更新记忆
    - 更新对他人的印象（favorability/trust/fear）
    - 更新性格/状态
    - 双写关系库 impression_cache + 图库 ViewsAs 边
    """
    if not event_ids:
        return {"updated_characters": 0, "new_memories": 0}

    # Step 4a: 自动编码事件为记忆（双写）
    new_memories_count = 0
    for eid in event_ids:
        try:
            mems = memory_service.encode_event_to_memories(eid)
            new_memories_count += len(mems)
            # 双写向量库
            try:
                from src.backend.storage.vector_store import VectorStore, VectorStoreUnavailable
                sm = default_save_manager()
                vs = VectorStore(sm._conn)
                ev = models.Event.get(eid)
                if ev:
                    vs.upsert_event(eid, ev.content_raw)
                for mem in mems:
                    m_id = mem.get("id") or (m := models.Memory.list(where="source_event_id = ?", params=[eid], limit=1))[0].id
                    if m_id:
                        mm = models.Memory.get(m_id)
                        if mm:
                            vs.upsert_memory(m_id, mm.memory_raw)
            except (VectorStoreUnavailable, Exception):
                pass
        except Exception:
            pass

    # Step 4b: 调用 character_updater skill 做精细更新
    decisions_json = json.dumps(decisions, ensure_ascii=False, default=str)
    events_data = []
    for eid in event_ids:
        ev = models.Event.get(eid)
        if ev:
            events_data.append({
                "id": eid,
                "type": ev.event_type,
                "content": ev.content_raw,
            })

    try:
        result = call_skill(
            "character_updater",
            user_prompt=(
                f"【角色决策】\n{decisions_json}\n\n"
                f"【已创建事件】\n{json.dumps(events_data, ensure_ascii=False, default=str)}\n\n"
                "请分析每个角色应如何变化：\n"
                "1. 对参与角色调用 graph_upsert_views 更新其对他人的看法\n"
                "2. 对有记忆变化的角色，可调用 memory_retrieve 查看当前记忆\n"
                "3. 返回更新摘要 JSON"
            ),
            temperature=0.3,
        )
    except Exception:
        result = {"mock": True, "tool_results": []}

    return {
        "new_memories": new_memories_count,
        "skill_calls": len(result.get("tool_results", [])),
        "mock": result.get("mock"),
    }


# ============================================================
# Node 5: 全局更新
# ============================================================

def _global_update(
    coord_result: Dict[str, Any],
    event_ids: List[int],
) -> Dict[str, Any]:
    """全局更新节点。

    分析地形变化、地图扩展、世界观添加、文明/科技发展等。
    """
    narrative = coord_result.get("narrative", "")
    if not narrative and not event_ids:
        return {"global_changes": 0, "skipped": True}

    events_data = []
    for eid in event_ids:
        ev = models.Event.get(eid)
        if ev:
            events_data.append({
                "id": eid,
                "type": ev.event_type,
                "content": ev.content_raw,
                "location": ev.location_map_id,
            })

    try:
        result = call_skill(
            "global_updater",
            user_prompt=(
                f"【剧情 narrative】\n{narrative}\n\n"
                f"【事件列表】\n{json.dumps(events_data, ensure_ascii=False, default=str)}\n\n"
                "请分析是否需要全局更新：\n"
                "1. 地形变化（地图/地貌）\n"
                "2. 世界观添加（设定/规则）\n"
                "3. 文明/科技发展\n"
                "4. 若需要更新，调用对应工具写入\n"
                "返回 JSON：{changes_count: N, details: [...]}"
            ),
            temperature=0.2,
        )
        parsed = result.get("parsed") or {}
        return {
            "global_changes": parsed.get("changes_count", 0),
            "details": parsed.get("details", []),
            "mock": result.get("mock"),
        }
    except Exception:
        return {"global_changes": 0, "skipped": True}


# ============================================================
# 主入口
# ============================================================

def tick_once_v4(
    seconds: int = 60,
    max_actors: int = 5,
    player_action: Optional[str] = None,
) -> Dict[str, Any]:
    """v4 五节点管线主入口。

    返回每步执行摘要 + 创建的事件 ID 列表。
    """
    sm = default_save_manager()
    if not sm.active_save:
        raise RuntimeError("无激活存档")

    variables = _build_variables()
    steps: List[Dict[str, Any]] = []
    events_created: List[int] = []

    # ---------- 推进 tick ----------
    meta = world_service.tick_once(seconds)
    steps.append({"step": 0, "name": "advance_tick", "meta": meta})

    # ---------- 玩家动作处理（复用旧逻辑，但写入事件以便后续节点引用） ----------
    player_event_id: Optional[int] = None
    if player_action and player_action.strip():
        proto = sm.get_protagonist()
        proto_id = proto.get("id") if proto else None
        proto_name = proto.get("name", "主角") if proto else "主角"

        # 简化处理：玩家动作直接生成一条事件
        pe = world_service.create_event(
            event_type="player_action",
            content_raw=player_action.strip(),
            content_polished=player_action.strip(),
            importance=6,
            participants=[{"type": "character", "id": proto_id, "role": "first_hand", "perception": player_action.strip()}] if proto_id else None,
        )
        if pe.get("id"):
            player_event_id = pe["id"]
            events_created.append(pe["id"])
        steps.append({"step": 0.5, "name": "player_action", "event_id": player_event_id})

    # ---------- Node 0.6: 任务/纲领监控（10.2 时间模型）----------
    with trace.span("monitors", "node", node=0.6):
        monitor_result = _monitor_quests_agendas(meta)
    steps.append({"step": 0.6, "name": "quest_agenda_monitor", **monitor_result})

    # ---------- Node 0.7: 周期事件调度（10.3）----------
    with trace.span("scheduled_event_dispatcher", "node", node=0.7):
        sched_result = _dispatch_scheduled_events(meta, events_created)
    steps.append({"step": 0.7, "name": "scheduled_event_dispatcher", **sched_result})

    # ---------- 收集活跃角色与锚点 ----------
    active_chars = models.Character.list(
        where="dead_at_tick IS NULL", order_by="importance DESC", limit=max_actors
    )
    proto = sm.get_protagonist()
    proto_id = proto.get("id") if proto else None

    active_anchors = models.AnchorPlot.list(
        where="status IN ('pending', 'active') AND inevitability >= 2",
        order_by="inevitability DESC",
        limit=10,
    )
    anchor_dicts = [a.to_dict() for a in active_anchors]

    # ---------- Node 1: 前置分析 ----------
    with trace.span("pre_analyzer", "node", node=1):
        pre_analysis = _pre_analyze(seconds, player_action, meta, active_chars, anchor_dicts)
    steps.append({"step": 1, "name": "pre_analyzer", **pre_analysis})

    # ---------- Node 2: 角色并发决策 ----------
    with trace.span("actor_decide", "node", node=2, actors=len(active_chars)):
        decisions = _actor_decide(active_chars, pre_analysis, player_action, proto_id, variables)
    steps.append({"step": 2, "name": "actor_decide", "decisions_count": len(decisions), "decisions": decisions})

    # ---------- Node 3: 统筹（含打回循环）----------
    with trace.span("coordinator", "node", node=3):
        coord_result = _coordinate_with_feedback(decisions, pre_analysis, active_chars, variables, active_anchors=anchor_dicts)
    steps.append({
        "step": 3, "name": "coordinator",
        "valid": coord_result["valid"],
        "attempts": coord_result.get("attempts", 1),
        "narrative": coord_result["narrative"],
        "invalid_count": len(coord_result["invalid_decisions"]),
    })

    # ---------- 基于统筹结果创建事件 ----------
    if coord_result["narrative"]:
        # A2 修复：narrative 事件补充 participants（参与决策的角色），
        # 否则 encode_event_to_memories 无 participants 可编码、记忆链路断裂
        narr_participants = [
            {
                "type": "character",
                "id": c.id,
                "role": "first_hand" if c.id == proto_id else "supporting",
                "perception": "",
            }
            for c in active_chars
        ]
        ne = world_service.create_event(
            event_type="narrative",
            content_raw=coord_result["narrative"],
            content_polished=coord_result["narrative"],
            importance=5,
            participants=narr_participants,
        )
        if ne.get("id"):
            events_created.append(ne["id"])
            # B1 修复：不再在此处调 encode_event_to_memories —— _character_update
            # 节点（Node 4 Step 4a）会对所有 events_created 统一编码，此处重复调用
            # 会导致每个角色生成两条相同记忆。encode 内部也已加 (char_id, source_event_id)
            # 去重兜底。

            # B3 锚点回链：coordinator 在本 tick narrative 中标注已满足的锚点，
            # 此时 narrative 事件已落库，把 fulfilled_event_id 精确回链到该事件。
            fulfilled_ids = coord_result.get("fulfilled_anchor_ids") or []
            cur_tick = meta.get("tick_num", 1)
            for aid in fulfilled_ids:
                try:
                    aid_int = int(aid)
                except (TypeError, ValueError):
                    continue
                existing = models.AnchorPlot.get(aid_int)
                if existing and existing.status in ("pending", "active"):
                    models.AnchorPlot.update(
                        aid_int,
                        status="fulfilled",
                        fulfilled_tick=cur_tick,
                        fulfilled_event_id=ne["id"],
                    )

    # ---------- Node 3.5: 动态实体创建（v5 新增）----------
    with trace.span("world_react_v2", "node", node=3.5):
        wr_result = _world_react_v2(
            coord_result["narrative"], events_created, decisions
        )
    steps.append({
        "step": 3.5, "name": "world_react_v2",
        "dynamic_creations_count": wr_result.get("total_created", 0),
        "rejected_creations_count": wr_result.get("total_rejected", 0),
        "mock": wr_result.get("mock"),
    })

    # ---------- Node 4: 角色更新 ----------
    with trace.span("character_updater", "node", node=4):
        char_update_result = _character_update(decisions, coord_result, events_created)
    steps.append({"step": 4, "name": "character_updater", **char_update_result})

    # ---------- Node 5: 全局更新 ----------
    with trace.span("global_updater", "node", node=5):
        global_update_result = _global_update(coord_result, events_created)
    steps.append({"step": 5, "name": "global_updater", **global_update_result})

    # ---------- Node 5.5: 消息传播推进（10.1）----------
    with trace.span("rumor_propagator", "node", node=5.5):
        propagation_result = _propagate_messages(meta, events_created)
    steps.append({"step": 5.5, "name": "rumor_propagator", **propagation_result})

    # ---------- 锚点剧情推进检查 ----------
    # 注意：此处需重新读取 DB 当前状态，因为上方 B3 回链可能已把锚点置为 fulfilled。
    for anchor in active_anchors:
        cur = models.AnchorPlot.get(anchor.id)
        if not cur:
            continue
        # 已被本 tick narrative 满足的锚点跳过，避免覆盖 fulfilled 状态
        if cur.status in ("fulfilled", "abandoned", "expired"):
            continue
        if cur.status == "pending" and cur.inevitability >= 3:
            # 必然性 >= 3 的锚点自动激活
            models.AnchorPlot.update(anchor.id, status="active")
            cur = models.AnchorPlot.get(anchor.id)
        if cur and cur.status == "active":
            # 检查是否有事件满足锚点
            if cur.target_tick and meta.get("tick_num", 0) >= cur.target_tick:
                models.AnchorPlot.update(anchor.id, status="expired")

    return {
        "tick": meta["tick_num"],
        "game_time": meta["game_time"],
        "trace": steps,
        "events_created": events_created,
        "decisions": decisions,
        "coordinator_valid": coord_result["valid"],
        "coordinator_attempts": coord_result.get("attempts", 1),
        "mock_mode": deepseek_client.is_mock_mode(),
        "narrative": coord_result["narrative"],
    }
