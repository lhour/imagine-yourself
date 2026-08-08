"""src.backend.service.propagation_estimator — 传播估算模型（10.1 纯代码，无 LLM）。

媒介 × 距离 × 社交网络 → 延迟与失真估算。

媒介延迟模型：
- 口头：同地点秒级，跨城数天，跨国数月
- 书信：依赖交通网络，天数起
- 电话/网络：秒级跨地域，几乎无延迟
- 媒体报道：走广播通道（public_knowledge），不进本估算

失真模型：
- 每跳 +N% 失真（口头高、书信中、影像低）
- 失真累积影响 correctness
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.backend.service.game_time_utils import (
    GameTime,
    Duration,
    add as gt_add,
    parse_game_time,
    parse_duration,
)

logger = logging.getLogger(__name__)

# 媒介 → (基础延迟天数, 每跳失真百分比)
_MEDIUM_PROFILES: Dict[str, Tuple[float, int]] = {
    "口头": (1.0, 15),      # 同城1天起，每跳+15%失真
    "书信": (3.0, 8),       # 3天起，每跳+8%失真
    "电话": (0.01, 2),      # 秒级，几乎无失真
    "网络": (0.01, 3),      # 秒级，轻微失真
    "无": (9999, 0),        # 不传播
}

# 距离等级 → 延迟倍数（基于地图层级，简化模型）
_DISTANCE_MULTIPLIERS = {
    "same_location": 0.01,   # 同地点：秒级
    "same_area": 0.5,        # 同区域：半天
    "same_city": 1.0,        # 同城：1天
    "cross_city": 3.0,       # 跨城：3天
    "cross_region": 10.0,    # 跨区域：10天
    "cross_country": 30.0,   # 跨国：1月
}


def estimate_delay_days(
    medium: str,
    distance_level: str = "same_city",
) -> float:
    """估算传播延迟（天数）。

    Args:
        medium: 传播媒介（口头/书信/电话/网络/无）
        distance_level: 距离等级

    Returns:
        延迟天数（0.01 = 约15分钟，9999 = 不传播）
    """
    base_days, _ = _MEDIUM_PROFILES.get(medium, (1.0, 10))
    multiplier = _DISTANCE_MULTIPLIERS.get(distance_level, 1.0)
    return base_days * multiplier


def estimate_distortion(
    medium: str,
    hops: int = 1,
) -> int:
    """估算失真程度（0-100）。

    Args:
        medium: 传播媒介
        hops: 传播跳数

    Returns:
        失真程度 0-100
    """
    _, per_hop_distortion = _MEDIUM_PROFILES.get(medium, (1.0, 10))
    return min(100, per_hop_distortion * hops)


def compute_expected_arrival(
    current_game_time: str,
    medium: str,
    distance_level: str = "same_city",
) -> Optional[str]:
    """计算预计触达游戏时间。

    Args:
        current_game_time: 当前游戏时间字符串
        medium: 传播媒介
        distance_level: 距离等级

    Returns:
        预计触达游戏时间字符串，解析失败返回 None
    """
    gt = parse_game_time(current_game_time)
    if gt is None:
        return None

    delay_days = estimate_delay_days(medium, distance_level)
    if delay_days >= 9999:
        return None  # 不传播

    dur = Duration(days=delay_days)
    arrival = gt_add(gt, dur)
    from src.backend.service.game_time_utils import format_game_time
    return format_game_time(arrival)


def estimate_distance_level(
    origin_map_id: Optional[int],
    target_char_map_id: Optional[int],
) -> str:
    """估算两地点间的距离等级（简化模型，基于地图ID）。

    实际实现应查 maps 表的层级关系 + map_travel_cost 矩阵，
    这里用简化逻辑：同地图=同地点，不同地图=同城（默认）。
    """
    if origin_map_id is None or target_char_map_id is None:
        return "same_city"
    if origin_map_id == target_char_map_id:
        return "same_location"
    return "same_city"


def create_dissemination_records(
    event_id: int,
    event_content: str,
    event_location_map_id: Optional[int],
    medium: str,
    origin_char_ids: List[int],
    target_char_ids: List[int],
    current_game_time: str,
    current_tick: int,
) -> List[Dict[str, Any]]:
    """为定向传播事件创建触达追踪记录。

    只为不在场的目标角色创建 pending 记录（在场角色已通过 encode_event_to_memories 直接获知）。

    Args:
        event_id: 事件ID
        event_content: 事件原文
        event_location_map_id: 事件发生地点
        medium: 传播媒介
        origin_char_ids: 在场/已知的角色ID列表（不重复创建）
        target_char_ids: 所有可能触达的角色ID列表
        current_game_time: 当前游戏时间
        current_tick: 当前tick

    Returns:
        创建的 dissemination 记录列表
    """
    from src.backend.storage import models

    if medium == "无" or medium == "媒体报道":
        return []  # 媒体报道走广播通道，不进定向传播

    # 排除在场角色
    origin_set = set(origin_char_ids)
    pending_targets = [tid for tid in target_char_ids if tid not in origin_set]

    if not pending_targets:
        return []

    created = []
    for target_id in pending_targets:
        # 查目标角色当前位置
        target_char = models.Character.get(target_id)
        if not target_char:
            continue
        target_map_id = getattr(target_char, "current_map_id", None) or getattr(target_char, "location_map_id", None)

        # 估算距离与延迟
        distance_level = estimate_distance_level(event_location_map_id, target_map_id)
        expected_arrival = compute_expected_arrival(current_game_time, medium, distance_level)

        if expected_arrival is None:
            continue  # 不传播

        # 估算初始失真（1跳）
        distortion = estimate_distortion(medium, hops=1)

        try:
            ed = models.EventDissemination.create(
                event_id=event_id,
                target_char_id=target_id,
                status="pending",
                expected_arrival_game_time=expected_arrival,
                distortion_level=distortion,
                received_version_raw="",  # 触达时由 rumor_propagator 填充
                source_path_json=[],
                hops=1,
                created_tick=current_tick,
                updated_tick=current_tick,
            )
            created.append(ed.to_dict())
        except Exception as ex:
            logger.warning("创建传播记录失败 event_id=%s target=%s: %s", event_id, target_id, ex)

    return created


def create_public_knowledge_record(
    event_id: int,
    event_content: str,
    medium: str,
    coverage_scope: str,
    current_game_time: str,
    reach_tags: List[str] = None,
) -> Optional[Dict[str, Any]]:
    """为媒体报道类事件创建广播通道记录。

    一条媒体报道只建 1 条 public_knowledge 记录，
    角色获知在 actor_decide 时按 reach_tags 动态判定，O(1) 存储。
    """
    from src.backend.storage import models

    try:
        pk = models.PublicKnowledge.create(
            event_id=event_id,
            published_game_time=current_game_time,
            medium=medium,
            coverage_scope=coverage_scope,
            version_raw=event_content,
            reach_tags_json=reach_tags or ["关注时事", "刷手机", "看新闻"],
        )
        return pk.to_dict()
    except Exception as ex:
        logger.warning("创建公开知识记录失败 event_id=%s: %s", event_id, ex)
        return None
