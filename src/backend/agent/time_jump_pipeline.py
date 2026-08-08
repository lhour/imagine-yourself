"""src.backend.agent.time_jump_pipeline — 时间跨越管线。

按跨度分层：
- 短期（3-30 天）：每日事件，10+ 事件
- 中期（30 天-1 年）：周度摘要，5-10 个里程碑
- 长期（1-100 年）：年度摘要，3-7 个里程碑
- 超长期（100-10000 年）：朝代级，3-5 个里程碑
- 纪元级（10000+ 年）：宇宙级

10.5 批量结算：跨越期不逐 tick 模拟，而是批量结算：
- 周期事件汇总（常规→1条摘要，偏离→单独event）
- 消息传播批量触达（跨越期内 pending→arrived）
- 任务/纲领推进（按 game_time 判断到期）
- 锚点检查（跨越后强制检查）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from src.backend.agent.pipeline import _build_variables, call_skill
from src.backend.service import world_service
from src.backend.storage import models
from src.backend.storage.connection import default_save_manager

logger = logging.getLogger(__name__)


# 跨度分层
def _classify_span(seconds: int) -> str:
    days = seconds / 86400
    if days <= 30:
        return "short"
    if days <= 365:
        return "medium"
    if days <= 365 * 100:
        return "long"
    if days <= 365 * 10000:
        return "ultra_long"
    return "epochal"


def time_jump(
    seconds: int,
) -> Dict[str, Any]:
    """时间跨越管线。

    1. 推进元信息（tick +1, game_time += seconds）
    2. 调 time_skip_summarizer 生成史诗摘要 + 里程碑事件（中间时段 + 目标时刻）
    3. 把里程碑事件写入 events 表
    4. 批量更新角色/物品/地图/群体的状态变更
    """
    sm = default_save_manager()
    if not sm.active_save:
        raise RuntimeError("无激活存档")

    span_type = _classify_span(seconds)
    span_label = {
        "short": f"短期（{seconds // 86400} 天）",
        "medium": f"中期（{seconds // 86400} 天）",
        "long": f"长期（{seconds // (86400 * 365)} 年）",
        "ultra_long": f"超长期（{seconds // (86400 * 365)} 年）",
        "epochal": f"纪元级（{seconds // (86400 * 365 * 10000)} 万年）",
    }[span_type]

    # Step 1: 推进元信息
    jump_result = world_service.time_jump(seconds)

    # Step 2: 调 time_skip_summarizer
    variables = _build_variables()
    summarizer_result = call_skill(
        "time_skip_summarizer",
        user_prompt=(
            f"时间跨越：{span_label}\n"
            f"起点：{jump_result['from_time']}\n"
            f"终点：{jump_result['to_time']}\n"
            f"跨度秒数：{seconds}\n"
            f"跨度类型：{span_type}\n"
            f"请补全中间时段发生的事件（事件数量依跨度而定），并生成终点时刻的事件。"
        ),
        variables=variables,
        max_tokens=4096,
    )

    # Step 3: 写入里程碑事件
    events_created: List[int] = []
    parsed = summarizer_result.get("parsed")
    if parsed and isinstance(parsed, dict):
        for ms in parsed.get("milestones", []):
            try:
                e = world_service.create_event(
                    event_type=ms.get("event_type", "narrative"),
                    content_raw=ms.get("content_raw", ""),
                    content_polished=ms.get("content_polished"),
                    location_map_id=ms.get("location_map_id"),
                    importance=ms.get("importance", 5),
                    participants=ms.get("participants"),
                    custom_attrs={"time_jump": True, "tick_offset": ms.get("tick_offset", 0)},
                )
                events_created.append(e["id"])
            except Exception:
                pass

        # Step 4: 应用状态变更
        state_changes = parsed.get("state_changes", {})
        _apply_state_changes(state_changes)

    # Step 5: 10.5 批量结算
    settlement = _batch_settle(
        jump_result["from_time"],
        jump_result["to_time"],
        seconds,
        span_type,
        events_created,
    )

    return {
        **jump_result,
        "span_type": span_type,
        "span_label": span_label,
        "summary": parsed.get("summary") if parsed else summarizer_result.get("content"),
        "events_created": events_created,
        "milestone_count": len(events_created),
        "mock_mode": summarizer_result.get("mock", False),
        "usage": summarizer_result.get("usage"),
        "settlement": settlement,
    }


def _batch_settle(
    from_time: str,
    to_time: str,
    seconds: int,
    span_type: str,
    events_created: List[int],
) -> Dict[str, Any]:
    """10.5 批量结算：周期事件汇总 + 传播批量结算 + 任务/纲领推进 + 锚点检查。"""
    from src.backend.service.game_time_utils import compare as gt_compare, parse_game_time, add as gt_add, Duration, format_game_time

    sm = default_save_manager()
    meta = sm.get_meta()
    tick_num = meta.get("tick_num", 0)

    result: Dict[str, Any] = {
        "routine_events_summarized": 0,
        "propagation_settled": 0,
        "quests_failed": 0,
        "quests_completed": 0,
        "agendas_reviewed": 0,
        "anchors_checked": 0,
    }

    # 1. 周期事件汇总：常规周期事件 → 1 条摘要事件
    try:
        scheduled = models.ScheduledEvent.list(
            where="active = 1 AND schedule_type = 'recurring'", limit=200
        )
        routine_count = len(scheduled)
        if routine_count > 0:
            # 生成 1 条"这段时间的日常节律"摘要事件
            summary_content = f"在 {from_time} 至 {to_time} 期间，{routine_count} 项日常周期事件照常进行（上课、集日、作息等），无异常。"
            try:
                ev = world_service.create_event(
                    event_type="routine_summary",
                    content_raw=summary_content,
                    content_polished=summary_content,
                    importance=1,
                    custom_attrs={"time_jump_routine": True, "routine_count": routine_count},
                )
                events_created.append(ev["id"])
                result["routine_events_summarized"] = routine_count
            except Exception as ex:
                logger.warning("周期事件摘要生成失败: %s", ex)

            # 推进所有常规周期事件的 next_trigger_game_time 到跨越后
            to_gt = parse_game_time(to_time)
            if to_gt:
                for se in scheduled:
                    try:
                        # 简化：直接把 next_trigger 推进到终点时间之后
                        # （精确推进应按 recurrence_pattern 多次推进，但跨越期批量结算只需保证下次在终点之后）
                        cur_next = se.next_trigger_game_time or ""
                        if cur_next:
                            cmp = gt_compare(cur_next, to_time)
                            if cmp is not None and cmp < 0:
                                models.ScheduledEvent.update(
                                    se.id, next_trigger_game_time=to_time
                                )
                    except Exception:
                        pass
    except Exception as ex:
        logger.warning("周期事件汇总失败: %s", ex)

    # 2. 消息传播批量结算：所有 pending 且 expected_arrival <= to_time → arrived
    try:
        pending = models.EventDissemination.list(
            where="status = 'pending'", limit=2000
        )
        settled = 0
        for ed in pending:
            expected = ed.expected_arrival_game_time or ""
            if not expected:
                continue
            cmp = gt_compare(expected, to_time)
            if cmp is not None and cmp <= 0:
                # 跨越期内必然触达，批量标记 arrived
                try:
                    models.EventDissemination.update(
                        ed.id,
                        status="arrived",
                        arrived_game_time=expected,
                        updated_tick=tick_num,
                    )
                    settled += 1
                except Exception:
                    pass
        result["propagation_settled"] = settled
    except Exception as ex:
        logger.warning("传播批量结算失败: %s", ex)

    # 3. 任务/纲领推进
    # 3a. 任务：deadline_game_time <= to_time 且未完成 → failed
    try:
        active_quests = models.CharacterQuest.list(
            where="status IN ('in_progress', 'planned')", limit=500
        )
        for q in active_quests:
            deadline = q.deadline_game_time or ""
            if not deadline:
                continue
            cmp = gt_compare(deadline, to_time)
            if cmp is not None and cmp <= 0:
                try:
                    models.CharacterQuest.update(
                        q.id, status="terminated",
                        blocked_reason_raw=f"时间跨越至 {to_time}，任务超期未完成",
                    )
                    result["quests_failed"] += 1
                except Exception:
                    pass
    except Exception as ex:
        logger.warning("任务推进失败: %s", ex)

    # 3b. 纲领：review_game_time <= to_time → 推进回顾时间到跨越后
    try:
        active_agendas = models.CharacterAgenda.list(
            where="status = 'active'", limit=500
        )
        for a in active_agendas:
            review = a.review_game_time or ""
            if not review:
                continue
            cmp = gt_compare(review, to_time)
            if cmp is not None and cmp <= 0:
                # 跨越多个回顾点的纲领合并为一次回顾评估
                # 简化：推进 review_game_time 到跨越后，标记需回顾
                try:
                    models.CharacterAgenda.update(
                        a.id, review_game_time=to_time,
                        custom_attrs={"needs_review_after_jump": True},
                    )
                    result["agendas_reviewed"] += 1
                except Exception:
                    pass
    except Exception as ex:
        logger.warning("纲领推进失败: %s", ex)

    # 4. 锚点检查：跨越后强制检查
    try:
        anchors = models.AnchorPlot.list(
            where="status IN ('pending', 'active')", limit=100
        )
        checked = 0
        for anchor in anchors:
            # target_tick 过期的锚点标记 expired
            if anchor.target_tick and tick_num >= anchor.target_tick:
                try:
                    models.AnchorPlot.update(anchor.id, status="expired")
                    checked += 1
                except Exception:
                    pass
            # inevitability >= 3 的 pending 锚点自动激活
            elif anchor.status == "pending" and anchor.inevitability >= 3:
                try:
                    models.AnchorPlot.update(anchor.id, status="active")
                    checked += 1
                except Exception:
                    pass
        result["anchors_checked"] = checked
    except Exception as ex:
        logger.warning("锚点检查失败: %s", ex)

    return result


def _apply_state_changes(changes: Dict[str, Any]) -> None:
    """应用 time_skip_summarizer 返回的状态变更到数据库。"""
    # 角色变更
    for ch in changes.get("characters", []):
        cid = ch.get("id")
        if not cid:
            continue
        updates = {}
        if "status" in ch:
            updates["status"] = ch["status"]
        if "dead_at_tick" in ch:
            updates["dead_at_tick"] = ch["dead_at_tick"]
        if updates:
            models.Character.update(cid, **updates)

    # 物品变更
    for it in changes.get("items", []):
        iid = it.get("id")
        if not iid:
            continue
        updates = {k: v for k, v in it.items() if k != "id"}
        if updates:
            models.Item.update(iid, **updates)

    # 地图变更
    for mp in changes.get("maps", []):
        mid = mp.get("id")
        if not mid:
            continue
        updates = {k: v for k, v in mp.items() if k != "id"}
        if updates:
            models.Map.update(mid, **updates)

    # 群体变更
    for gp in changes.get("groups", []):
        gid = gp.get("id")
        if not gid:
            continue
        updates = {k: v for k, v in gp.items() if k != "id"}
        if updates:
            models.Group.update(gid, **updates)
