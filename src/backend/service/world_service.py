"""src.backend.service.world_service — 世界推进（事件/时间）服务。

阶段一只实现骨架，真正的 LLM 管线在阶段二补。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.backend.storage import models
from src.backend.storage.connection import default_save_manager


# 游戏时间格式：{纪元}{年}年{月}月{日}日{时}时{分}分{秒}秒
_TIME_RE = re.compile(
    r"^(?P<era>[^0-9]+?)(?P<year>\d+)年(?P<month>\d+)月(?P<day>\d+)日"
    r"(?:(?P<hour>\d+)时(?P<minute>\d+)分(?P<second>\d+)秒)?$"
)


def parse_game_time(s: str) -> Optional[Dict[str, Any]]:
    """解析游戏时间字符串。返回 {era, year, month, day, hour, minute, second}。"""
    if not s:
        return None
    m = _TIME_RE.match(s.strip())
    if not m:
        return None
    return {
        "era": m.group("era"),
        "year": int(m.group("year")),
        "month": int(m.group("month")),
        "day": int(m.group("day")),
        "hour": int(m.group("hour") or 0),
        "minute": int(m.group("minute") or 0),
        "second": int(m.group("second") or 0),
    }


def format_game_time(d: Dict[str, Any]) -> str:
    return (
        f"{d['era']}{d['year']}年{d['month']}月{d['day']}日"
        f"{d['hour']:02d}时{d['minute']:02d}分{d['second']:02d}秒"
    )


def advance_game_time(game_time: str, seconds: int) -> str:
    """推进游戏时间。用 divmod 一次性处理大跨度，避免 while 循环。"""
    d = parse_game_time(game_time)
    if not d:
        return game_time

    total_seconds = (
        d["second"]
        + d["minute"] * 60
        + d["hour"] * 3600
        + (d["day"] - 1) * 86400
    ) + seconds

    # 一次性 divmod
    days, rem = divmod(total_seconds, 86400)
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)

    # 把 days 转回 (year, month, day)
    year = d["year"]
    month = d["month"]
    day = 1 + days
    # 简化的月历（每月30天，每年12月）
    while day > 30:
        day -= 30
        month += 1
    while month > 12:
        month -= 12
        year += 1

    return format_game_time({
        "era": d["era"], "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute, "second": second,
    })


def create_event(
    event_type: str,
    content_raw: str,
    location_map_id: Optional[int] = None,
    location_detail_raw: Optional[str] = None,
    importance: int = 3,
    visibility: str = "public",
    participants: Optional[list] = None,
    content_polished: Optional[str] = None,
    custom_attrs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """写入一条世界事件（含参与人）。"""
    sm = default_save_manager()
    meta = sm.get_meta()
    e = models.Event.create(
        tick_num=meta["tick_num"],
        game_time=meta["game_time"],
        event_type=event_type,
        location_map_id=location_map_id,
        location_detail_raw=location_detail_raw,
        content_raw=content_raw,
        content_polished=content_polished,
        importance=importance,
        visibility=visibility,
        custom_attrs=custom_attrs or {},
    )
    # 写参与人
    if participants:
        for p in participants:
            models.EventParticipant.create(
                event_id=e.id,
                participant_type=p.get("type", "character"),
                participant_id=p["id"],
                role_raw=p.get("role", "witness"),
                perception_raw=p.get("perception"),
            )
    return e.to_dict()


def list_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    importance_min: int = 0,
    tick_from: Optional[int] = None,
    tick_to: Optional[int] = None,
) -> Dict[str, Any]:
    """列出世界事件（按 tick 倒序、id 倒序，最新在上）。"""
    where_parts: List[str] = []
    params: list = []
    if event_type:
        where_parts.append("event_type = ?")
        params.append(event_type)
    if importance_min > 0:
        where_parts.append("importance >= ?")
        params.append(importance_min)
    if tick_from is not None:
        where_parts.append("tick_num >= ?")
        params.append(tick_from)
    if tick_to is not None:
        where_parts.append("tick_num <= ?")
        params.append(tick_to)
    where = " AND ".join(where_parts) if where_parts else ""
    items = models.Event.list(
        where=where, params=params, order_by="tick_num DESC, id DESC", limit=limit
    )
    total = models.Event.count(where=where, params=params)
    return {"items": [e.to_dict() for e in items], "count": len(items), "total": total}


def tick_once(seconds: int = 60) -> Dict[str, Any]:
    """正常推进 1 tick。阶段一只更新元信息，不调 LLM。

    seconds: 这一 tick 代表多少游戏内秒。
    """
    sm = default_save_manager()
    meta = sm.get_meta()
    new_game_time = advance_game_time(meta["game_time"], seconds)
    sm.update_meta(tick_num=meta["tick_num"] + 1, game_time=new_game_time)
    return sm.get_meta()


def time_jump(seconds: int) -> Dict[str, Any]:
    """时间跨越：仅更新元信息。真正的史诗摘要由阶段二的 time_skip_summarizer 生成。"""
    sm = default_save_manager()
    meta = sm.get_meta()
    new_game_time = advance_game_time(meta["game_time"], seconds)
    sm.update_meta(tick_num=meta["tick_num"] + 1, game_time=new_game_time)
    return {
        "from_tick": meta["tick_num"],
        "to_tick": meta["tick_num"] + 1,
        "from_time": meta["game_time"],
        "to_time": new_game_time,
        "jumped_seconds": seconds,
        "note": "时间已跨越；史诗摘要将在阶段二接入 LLM 后生成",
    }
