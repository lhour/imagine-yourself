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


def _inject_event_meta(items: List[models.Event]) -> List[Dict[str, Any]]:
    """把事件的参与人（含角色名）和谁记得/谁忘了一起注入。"""
    if not items:
        return []
    event_ids = [e.id for e in items]
    placeholder = ",".join("?" * len(event_ids))

    # ---- 参与人：联角色名、群体名、物品名、地图名 ----
    sm_conn = default_save_manager()._conn  # type: ignore[union-attr]
    participant_rows = sm_conn.execute(
        f"""
        SELECT ep.id, ep.event_id, ep.participant_type, ep.participant_id,
               ep.role_raw, ep.perception_raw,
               c.name AS char_name, g.name AS group_name,
               i.name AS item_name, m.name AS map_name
        FROM event_participants ep
        LEFT JOIN characters c ON ep.participant_type = 'character' AND ep.participant_id = c.id
        LEFT JOIN groups g     ON ep.participant_type = 'group'     AND ep.participant_id = g.id
        LEFT JOIN items i      ON ep.participant_type = 'item'      AND ep.participant_id = i.id
        LEFT JOIN maps m       ON ep.participant_type = 'map'       AND ep.participant_id = m.id
        WHERE ep.event_id IN ({placeholder})
        ORDER BY ep.id ASC
        """,
        event_ids,
    ).fetchall()
    participants_by_event: Dict[int, List[Dict[str, Any]]] = {}
    for r in participant_rows:
        r2 = dict(r)
        ptype = r2["participant_type"]
        display = (
            r2.get("char_name") or r2.get("group_name") or
            r2.get("item_name") or r2.get("map_name") or
            f"#{r2['participant_id']}"
        )
        r2["name"] = display
        participants_by_event.setdefault(r2["event_id"], []).append({
            "id": r2["id"],
            "event_id": r2["event_id"],
            "participant_type": ptype,
            "participant_id": r2["participant_id"],
            "role_raw": r2["role_raw"],
            "perception_raw": r2["perception_raw"],
            "name": display,
        })

    # ---- 每条记忆关联到的事件：谁记得 / 谁遗忘（forget_prob>=0.8 算忘）----
    mem_rows = sm_conn.execute(
        f"""
        SELECT m.source_event_id, m.char_id, m.depth, m.correctness,
               m.forget_prob, m.is_false, c.name AS char_name
        FROM memories m
        LEFT JOIN characters c ON m.char_id = c.id
        WHERE m.source_event_id IN ({placeholder})
        """,
        event_ids,
    ).fetchall()
    remembered_by: Dict[int, List[Dict[str, Any]]] = {}
    forgotten_by: Dict[int, List[Dict[str, Any]]] = {}
    for r in mem_rows:
        r2 = dict(r)
        eid = r2["source_event_id"]
        if eid is None:
            continue
        entry = {
            "char_id": r2["char_id"],
            "char_name": r2.get("char_name") or f"#{r2['char_id']}",
            "depth": r2["depth"],
            "correctness": r2["correctness"],
            "forget_prob": r2["forget_prob"],
            "is_false": bool(r2["is_false"]),
        }
        if (r2.get("forget_prob") or 0) >= 0.8:
            forgotten_by.setdefault(eid, []).append(entry)
        else:
            remembered_by.setdefault(eid, []).append(entry)

    out: List[Dict[str, Any]] = []
    for e in items:
        d = e.to_dict()
        pid = e.id
        d["participants"] = participants_by_event.get(pid, [])
        d["remembered_by"] = remembered_by.get(pid, [])
        d["forgotten_by"] = forgotten_by.get(pid, [])
        out.append(d)
    return out


def list_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    importance_min: int = 0,
    tick_from: Optional[int] = None,
    tick_to: Optional[int] = None,
    char_ids: Optional[List[int]] = None,
    map_ids: Optional[List[int]] = None,
    event_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """列出世界事件（按 tick 倒序、id 倒序，最新在上）。
    额外支持按角色/地点多条件筛选，返回时注入参与人和记忆可见性。
    """
    where_parts: List[str] = []
    params: List[Any] = []
    if event_type:
        where_parts.append("event_type = ?")
        params.append(event_type)
    if event_types:
        place = ",".join("?" * len(event_types))
        where_parts.append(f"event_type IN ({place})")
        params.extend(event_types)
    if importance_min > 0:
        where_parts.append("importance >= ?")
        params.append(importance_min)
    if tick_from is not None:
        where_parts.append("tick_num >= ?")
        params.append(tick_from)
    if tick_to is not None:
        where_parts.append("tick_num <= ?")
        params.append(tick_to)
    if char_ids:
        where_parts.append(
            "id IN (SELECT event_id FROM event_participants "
            "WHERE participant_type = 'character' AND participant_id IN ("
            + ",".join("?" * len(char_ids)) + "))"
        )
        params.extend(char_ids)
    if map_ids:
        place = ",".join("?" * len(map_ids))
        where_parts.append(f"location_map_id IN ({place})")
        params.extend(map_ids)
    where = " AND ".join(where_parts) if where_parts else ""
    items = models.Event.list(
        where=where, params=params, order_by="tick_num DESC, id DESC", limit=limit
    )
    total = models.Event.count(where=where, params=params)
    return {"items": _inject_event_meta(items), "count": len(items), "total": total}


def get_event_detail(event_id: int) -> Dict[str, Any]:
    """单条事件详情（含参与人、关联记忆列表）。"""
    e = models.Event.get(event_id)
    if not e:
        raise FileNotFoundError(f"事件 {event_id} 不存在")
    injected = _inject_event_meta([e])
    d = injected[0]
    # 追加关联记忆全量（含 memory_polished 供弹窗展示）
    sm_conn = default_save_manager()._conn  # type: ignore[union-attr]
    mems = sm_conn.execute(
        """
        SELECT m.*, c.name AS char_name FROM memories m
        LEFT JOIN characters c ON m.char_id = c.id
        WHERE source_event_id = ?
        ORDER BY depth DESC, remember_tick DESC
        """,
        [event_id],
    ).fetchall()
    d["linked_memories"] = [dict(r) for r in mems]
    return d


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
