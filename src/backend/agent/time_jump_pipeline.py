"""src.backend.agent.time_jump_pipeline — 时间跨越管线。

按跨度分层：
- 短期（3-30 天）：每日事件，10+ 事件
- 中期（30 天-1 年）：周度摘要，5-10 个里程碑
- 长期（1-100 年）：年度摘要，3-7 个里程碑
- 超长期（100-10000 年）：朝代级，3-5 个里程碑
- 纪元级（10000+ 年）：宇宙级
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.backend.agent.pipeline import _build_variables, call_skill
from src.backend.service import world_service
from src.backend.storage import models
from src.backend.storage.connection import default_save_manager


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

    return {
        **jump_result,
        "span_type": span_type,
        "span_label": span_label,
        "summary": parsed.get("summary") if parsed else summarizer_result.get("content"),
        "events_created": events_created,
        "milestone_count": len(events_created),
        "mock_mode": summarizer_result.get("mock", False),
        "usage": summarizer_result.get("usage"),
    }


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
