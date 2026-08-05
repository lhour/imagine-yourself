"""src.backend.storage.models — Active Record 模型层。

按 v3_redesign_spec.md §2 设计的 19 张表：

元信息（1）：
  world_meta            单例元信息

客观表（11）：
  characters            角色
  groups                群体（含热力图字段）
  character_group_relations  角色-群体关系
  group_hierarchies     群体从属
  items                 物品
  item_holds            物品持有（多态）
  maps                  地图容器（含移动地图）
  map_features           地形要素
  character_locations   角色位置
  events                事件流（核心主角）
  event_participants    事件参与人
  settings              设定

主观记忆系统（4）：
  memories              记忆基本表
  memory_index          记忆四维索引
  memory_links          记忆宫殿关联链
  character_impressions 角色印象（顶层摘要）

任务系统（3）：
  character_quests      任务
  character_agendas     行动纲领
  quest_steps           任务大纲步骤
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ============================================================
# 连接池占位（由 connection.py 注入）
# ============================================================

_ACTIVE_CONN: Optional[sqlite3.Connection] = None


def set_active_connection(conn: Optional[sqlite3.Connection]) -> None:
    """由 SaveManager.switch_save 注入当前激活存档的连接。"""
    global _ACTIVE_CONN
    _ACTIVE_CONN = conn


def _conn() -> sqlite3.Connection:
    if _ACTIVE_CONN is None:
        raise RuntimeError("无激活存档；请先 create_save / switch_save")
    return _ACTIVE_CONN


# ============================================================
# BaseEntity（Active Record）
# ============================================================

class BaseEntity:
    """所有实体的 Active Record 基类。

    子类需声明：
        TABLE       表名
        SLUG        URL slug（与表名去复数一致）
        FIELDS      [(db_col, python_name, json?), ...] 按列顺序
    """

    TABLE: str = ""
    SLUG: str = ""
    FIELDS: List[Tuple[str, str, bool]] = []  # (db_col, py_name, is_json)

    def __init__(self, row: Optional[sqlite3.Row] = None) -> None:
        if row is None:
            self.id: Optional[int] = None
            return
        self.id = row["id"]
        for db_col, py_name, is_json in self.FIELDS:
            val = row[db_col]
            if is_json and isinstance(val, str) and val:
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            setattr(self, py_name, val)

    # ---------- 序列化 ----------

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id}
        for db_col, py_name, is_json in self.FIELDS:
            v = getattr(self, py_name, None)
            # 从 entity 属性 → 对外 dict：确保 json 字段是 Python 对象而非字符串
            if is_json and isinstance(v, str) and v:
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    pass
            d[db_col if db_col == py_name else db_col] = v
            # 同时设置 py_name key（兼容调用方两种命名：按 db_col 或 py_name）
            if db_col != py_name:
                d[py_name] = v
        return d

    # ---------- CRUD ----------

    @classmethod
    def get(cls, item_id: int) -> Optional["BaseEntity"]:
        cur = _conn().execute(f"SELECT * FROM {cls.TABLE} WHERE id = ?", [item_id])
        row = cur.fetchone()
        return cls(row) if row else None

    @classmethod
    def list(
        cls,
        where: str = "",
        params: Optional[List[Any]] = None,
        order_by: str = "id ASC",
        limit: int = 50,
        offset: int = 0,
    ) -> List["BaseEntity"]:
        sql = f"SELECT * FROM {cls.TABLE}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
        cur = _conn().execute(sql, params or [])
        return [cls(row) for row in cur.fetchall()]

    @classmethod
    def count(cls, where: str = "", params: Optional[List[Any]] = None) -> int:
        sql = f"SELECT COUNT(*) AS c FROM {cls.TABLE}"
        if where:
            sql += f" WHERE {where}"
        cur = _conn().execute(sql, params or [])
        return cur.fetchone()["c"]

    @classmethod
    def create(cls, **fields) -> "BaseEntity":
        cols, vals = [], []
        for db_col, py_name, is_json in cls.FIELDS:
            if py_name in fields:
                v = fields[py_name]
                if is_json and v is not None and not isinstance(v, str):
                    v = json.dumps(v, ensure_ascii=False)
                cols.append(db_col)
                vals.append(v)
        if not cols:
            raise ValueError(f"无字段可插入 {cls.TABLE}")
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO {cls.TABLE} ({','.join(cols)}) VALUES ({placeholders})"
        cur = _conn().execute(sql, vals)
        _conn().commit()
        return cls.get(cur.lastrowid)  # type: ignore[arg-type]

    @classmethod
    def bulk_create(cls, items: List[Dict[str, Any]]) -> List["BaseEntity"]:
        if not items:
            return []
        valid_cols = {py_name: (db_col, is_json) for db_col, py_name, is_json in cls.FIELDS}
        rows: List[List[Any]] = []
        cols: List[str] = []
        for item in items:
            if not cols:
                cols = [valid_cols[k][0] for k in item.keys() if k in valid_cols]
            row = []
            for k in item:
                if k not in valid_cols:
                    continue
                db_col, is_json = valid_cols[k]
                v = item[k]
                if is_json and v is not None and not isinstance(v, str):
                    v = json.dumps(v, ensure_ascii=False)
                row.append(v)
            rows.append(row)
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO {cls.TABLE} ({','.join(cols)}) VALUES ({placeholders})"
        cur = _conn().executemany(sql, rows)
        _conn().commit()
        last_id = cur.lastrowid or 1
        # 返回新插入的记录（按 ID 升序）
        return cls.list(where=f"id >= ?", params=[last_id], limit=len(items))

    @classmethod
    def update(cls, item_id: int, **fields) -> Optional["BaseEntity"]:
        valid_cols = {py_name: (db_col, is_json) for db_col, py_name, is_json in cls.FIELDS}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in valid_cols:
                continue
            db_col, is_json = valid_cols[k]
            if is_json and v is not None and not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{db_col} = ?")
            vals.append(v)
        if not sets:
            return cls.get(item_id)
        vals.append(item_id)
        sql = f"UPDATE {cls.TABLE} SET {','.join(sets)} WHERE id = ?"
        _conn().execute(sql, vals)
        _conn().commit()
        return cls.get(item_id)

    @classmethod
    def bulk_update(cls, updates: List[Dict[str, Any]]) -> int:
        """updates: [{id: 1, field1: v1, field2: v2}, ...]"""
        n = 0
        for u in updates:
            if "id" not in u:
                continue
            item_id = u.pop("id")
            if cls.update(item_id, **u):
                n += 1
        return n

    @classmethod
    def delete(cls, item_id: int) -> bool:
        cur = _conn().execute(f"DELETE FROM {cls.TABLE} WHERE id = ?", [item_id])
        _conn().commit()
        return cur.rowcount > 0

    @classmethod
    def bulk_delete(cls, ids: List[int]) -> int:
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        cur = _conn().execute(f"DELETE FROM {cls.TABLE} WHERE id IN ({placeholders})", ids)
        _conn().commit()
        return cur.rowcount


# ============================================================
# 元信息（单例）
# ============================================================

class WorldMeta(BaseEntity):
    TABLE = "world_meta"
    SLUG = "world_meta"
    FIELDS = [
        ("tick_num", "tick_num", False),
        ("game_time", "game_time", False),
        ("era_name", "era_name", False),
        ("script_name", "script_name", False),
        ("protagonist_id", "protagonist_id", False),
        ("real_time", "real_time", False),
        ("description", "description", False),
        ("custom_attrs", "custom_attrs", True),
    ]

    @classmethod
    def get_singleton(cls) -> "WorldMeta":
        row = _conn().execute("SELECT * FROM world_meta WHERE id = 1").fetchone()
        if row:
            return cls(row)
        # 自动初始化
        _conn().execute(
            "INSERT INTO world_meta (id, tick_num, game_time, real_time, custom_attrs) "
            "VALUES (1, 1, ?, ?, '{}')",
            ["源石纪元1年1月1日08时00分00秒", time.strftime("%Y-%m-%d %H:%M:%S")],
        )
        _conn().commit()
        return cls.get_singleton()


# ============================================================
# 客观表
# ============================================================

class Character(BaseEntity):
    TABLE = "characters"
    SLUG = "character"
    FIELDS = [
        ("name", "name", False),
        ("appearance_raw", "appearance_raw", False),
        ("appearance_polished", "appearance_polished", False),
        ("personality_raw", "personality_raw", False),
        ("personality_polished", "personality_polished", False),
        ("gender", "gender", False),
        ("age", "age", False),
        ("status", "status", False),
        ("importance", "importance", False),
        ("custom_attrs", "custom_attrs", True),
        ("created_at_tick", "created_at_tick", False),
        ("dead_at_tick", "dead_at_tick", False),
    ]


class Group(BaseEntity):
    """群体表（含热力图字段）。"""
    TABLE = "groups"
    SLUG = "group"
    FIELDS = [
        ("name", "name", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("group_type", "group_type", False),
        ("leader_id", "leader_id", False),
        ("importance", "importance", False),
        ("primary_map_id", "primary_map_id", False),
        ("center_x", "center_x", False),
        ("center_y", "center_y", False),
        ("spread_radius", "spread_radius", False),
        ("distribution_raw", "distribution_raw", False),
        ("heatmap_grid", "heatmap_grid", True),
        ("heatmap_resolution", "heatmap_resolution", False),
        ("heatmap_updated_tick", "heatmap_updated_tick", False),
        ("custom_attrs", "custom_attrs", True),
        ("created_at_tick", "created_at_tick", False),
    ]


class CharacterGroupRelation(BaseEntity):
    TABLE = "character_group_relations"
    SLUG = "character_group_relation"
    FIELDS = [
        ("char_id", "char_id", False),
        ("group_id", "group_id", False),
        ("role_raw", "role_raw", False),
        ("join_tick", "join_tick", False),
        ("leave_tick", "leave_tick", False),
        ("importance_in_group", "importance_in_group", False),
    ]


class GroupHierarchy(BaseEntity):
    TABLE = "group_hierarchies"
    SLUG = "group_hierarchy"
    FIELDS = [
        ("child_group_id", "child_group_id", False),
        ("parent_group_id", "parent_group_id", False),
        ("relation_raw", "relation_raw", False),
        ("weight", "weight", False),
    ]


class Item(BaseEntity):
    TABLE = "items"
    SLUG = "item"
    FIELDS = [
        ("name", "name", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("item_type", "item_type", False),
        ("rarity", "rarity", False),
        ("importance", "importance", False),
        ("is_stackable", "is_stackable", False),
        ("stack_size", "stack_size", False),
        ("custom_attrs", "custom_attrs", True),
        ("created_at_tick", "created_at_tick", False),
    ]


class ItemHold(BaseEntity):
    TABLE = "item_holds"
    SLUG = "item_hold"
    FIELDS = [
        ("item_id", "item_id", False),
        ("quantity", "quantity", False),
        ("holder_type", "holder_type", False),
        ("holder_id", "holder_id", False),
        ("holder_detail", "holder_detail", False),
        ("acquired_tick", "acquired_tick", False),
        ("use_times", "use_times", False),
    ]


class Map(BaseEntity):
    """地图容器（v3 设计）：支持层级嵌套 + 移动地图（飞船）。"""
    TABLE = "maps"
    SLUG = "map"
    FIELDS = [
        ("name", "name", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("parent_map_id", "parent_map_id", False),
        ("map_type", "map_type", False),
        ("coord_system", "coord_system", False),
        ("scale_unit", "scale_unit", False),
        ("scale_per_unit", "scale_per_unit", False),
        ("bbox_x", "bbox_x", False),
        ("bbox_y", "bbox_y", False),
        ("bbox_w", "bbox_w", False),
        ("bbox_h", "bbox_h", False),
        ("bbox_d", "bbox_d", False),
        ("default_zoom", "default_zoom", False),
        ("default_center_x", "default_center_x", False),
        ("default_center_y", "default_center_y", False),
        ("is_mobile", "is_mobile", False),
        ("carrier_char_id", "carrier_char_id", False),
        ("carrier_item_id", "carrier_item_id", False),
        ("current_x", "current_x", False),
        ("current_y", "current_y", False),
        ("current_z", "current_z", False),
        ("current_map_id", "current_map_id", False),
        ("importance", "importance", False),
        ("custom_attrs", "custom_attrs", True),
        ("created_at_tick", "created_at_tick", False),
    ]


class MapFeature(BaseEntity):
    """地形要素（v3 核心新增）：高楼/山川/河流/星球/飞船。"""
    TABLE = "map_features"
    SLUG = "map_feature"
    FIELDS = [
        ("map_id", "map_id", False),
        ("name", "name", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("feature_type", "feature_type", False),
        ("shape", "shape", False),
        ("geometry", "geometry", True),
        ("size_value", "size_value", False),
        ("size_unit_override", "size_unit_override", False),
        ("layer_z", "layer_z", False),
        ("color_hint", "color_hint", False),
        ("icon_hint", "icon_hint", False),
        ("visual_raw", "visual_raw", False),
        ("visual_polished", "visual_polished", False),
        ("is_obstacle", "is_obstacle", False),
        ("is_mobile", "is_mobile", False),
        ("carrier_id", "carrier_id", False),
        ("carrier_type", "carrier_type", False),
        ("current_x", "current_x", False),
        ("current_y", "current_y", False),
        ("current_z", "current_z", False),
        ("child_map_id", "child_map_id", False),
        ("parent_feature_id", "parent_feature_id", False),
        ("importance", "importance", False),
        ("custom_attrs", "custom_attrs", True),
        ("created_at_tick", "created_at_tick", False),
    ]


class CharacterLocation(BaseEntity):
    TABLE = "character_locations"
    SLUG = "character_location"
    FIELDS = [
        ("char_id", "char_id", False),
        ("map_id", "map_id", False),
        ("feature_id", "feature_id", False),
        ("x", "x", False),
        ("y", "y", False),
        ("z", "z", False),
        ("location_detail_raw", "location_detail_raw", False),
        ("last_update_tick", "last_update_tick", False),
    ]


class Event(BaseEntity):
    """事件表（核心主角）：客观视角下的事件。"""
    TABLE = "events"
    SLUG = "event"
    FIELDS = [
        ("tick_num", "tick_num", False),
        ("game_time", "game_time", False),
        ("event_type", "event_type", False),
        ("location_map_id", "location_map_id", False),
        ("location_detail_raw", "location_detail_raw", False),
        ("content_raw", "content_raw", False),
        ("content_polished", "content_polished", False),
        ("importance", "importance", False),
        ("visibility", "visibility", False),
        ("source_event_id", "source_event_id", False),
        ("custom_attrs", "custom_attrs", True),
    ]


class EventParticipant(BaseEntity):
    TABLE = "event_participants"
    SLUG = "event_participant"
    FIELDS = [
        ("event_id", "event_id", False),
        ("participant_type", "participant_type", False),
        ("participant_id", "participant_id", False),
        ("role_raw", "role_raw", False),
        ("perception_raw", "perception_raw", False),
    ]


class Setting(BaseEntity):
    TABLE = "settings"
    SLUG = "setting"
    FIELDS = [
        ("category", "category", False),
        ("title", "title", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("setting_type", "setting_type", False),
        ("importance", "importance", False),
        ("custom_attrs", "custom_attrs", True),
    ]


# ============================================================
# 主观记忆系统（核心创新）
# ============================================================

class Memory(BaseEntity):
    """角色记忆基本表：深度/正确性/视角偏差/遗忘概率。"""
    TABLE = "memories"
    SLUG = "memory"
    FIELDS = [
        ("char_id", "char_id", False),
        ("source_event_id", "source_event_id", False),
        ("memory_raw", "memory_raw", False),
        ("memory_polished", "memory_polished", False),
        ("depth", "depth", False),
        ("correctness", "correctness", False),
        ("perspective_bias_raw", "perspective_bias_raw", False),
        ("mood", "mood", False),
        ("remember_tick", "remember_tick", False),
        ("last_recall_tick", "last_recall_tick", False),
        ("recall_count", "recall_count", False),
        ("forget_prob", "forget_prob", False),
        ("is_false", "is_false", False),
        ("custom_attrs", "custom_attrs", True),
    ]


class MemoryIndex(BaseEntity):
    """记忆四维索引：person / location / time / item / keyword。"""
    TABLE = "memory_index"
    SLUG = "memory_index"
    FIELDS = [
        ("memory_id", "memory_id", False),
        ("char_id", "char_id", False),
        ("index_type", "index_type", False),
        ("index_key", "index_key", False),
        ("index_value", "index_value", False),
    ]


class MemoryLink(BaseEntity):
    """记忆宫殿关联链：A↔B 关联（同场景/因果/情感）。"""
    TABLE = "memory_links"
    SLUG = "memory_link"
    FIELDS = [
        ("char_id", "char_id", False),
        ("memory_a_id", "memory_a_id", False),
        ("memory_b_id", "memory_b_id", False),
        ("link_type", "link_type", False),
        ("link_strength", "link_strength", False),
        ("weight", "weight", False),
    ]


class CharacterImpression(BaseEntity):
    """A 对 B 的顶层印象摘要（按需加载记忆时先拉这个）。"""
    TABLE = "character_impressions"
    SLUG = "character_impression"
    FIELDS = [
        ("observer_char_id", "observer_char_id", False),
        ("target_char_id", "target_char_id", False),
        ("impression_raw", "impression_raw", False),
        ("impression_polished", "impression_polished", False),
        ("favorability", "favorability", False),
        ("trust", "trust", False),
        ("fear", "fear", False),
        ("last_update_tick", "last_update_tick", False),
    ]


# ============================================================
# 任务系统
# ============================================================

class CharacterQuest(BaseEntity):
    TABLE = "character_quests"
    SLUG = "character_quest"
    FIELDS = [
        ("char_id", "char_id", False),
        ("title", "title", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("quest_type", "quest_type", False),
        ("status", "status", False),
        ("priority", "priority", False),
        ("start_tick", "start_tick", False),
        ("estimated_ticks", "estimated_ticks", False),
        ("success_condition_raw", "success_condition_raw", False),
        ("fail_condition_raw", "fail_condition_raw", False),
        ("assigned_by", "assigned_by", False),
        ("parent_quest_id", "parent_quest_id", False),
        ("completion_summary_raw", "completion_summary_raw", False),
        ("blocked_reason_raw", "blocked_reason_raw", False),
        ("custom_attrs", "custom_attrs", True),
    ]


class CharacterAgenda(BaseEntity):
    """角色行动纲领：长期行为准则，被阻碍才中断。"""
    TABLE = "character_agendas"
    SLUG = "character_agenda"
    FIELDS = [
        ("char_id", "char_id", False),
        ("title", "title", False),
        ("principle_raw", "principle_raw", False),
        ("principle_polished", "principle_polished", False),
        ("status", "status", False),
        ("priority", "priority", False),
        ("start_tick", "start_tick", False),
        ("end_tick", "end_tick", False),
        ("conflict_with", "conflict_with", False),
        ("blocked_reason_raw", "blocked_reason_raw", False),
    ]


class QuestStep(BaseEntity):
    """任务大纲步骤。"""
    TABLE = "quest_steps"
    SLUG = "quest_step"
    FIELDS = [
        ("quest_id", "quest_id", False),
        ("step_no", "step_no", False),
        ("action_raw", "action_raw", False),
        ("status", "status", False),
        ("done_tick", "done_tick", False),
        ("condition_raw", "condition_raw", False),
    ]


# ============================================================
# 实体注册表（驱动通用 CRUD + 工具生成）
# ============================================================

ENTITIES: List[type] = [
    # 元信息（不入注册表，单独管理）
    # 客观表（11）
    Character,
    Group,
    CharacterGroupRelation,
    GroupHierarchy,
    Item,
    ItemHold,
    Map,
    MapFeature,
    CharacterLocation,
    Event,
    EventParticipant,
    Setting,
    # 主观记忆系统（4）
    Memory,
    MemoryIndex,
    MemoryLink,
    CharacterImpression,
    # 任务系统（3）
    CharacterQuest,
    CharacterAgenda,
    QuestStep,
]

# slug → model 映射
SLUG_TO_MODEL: Dict[str, type] = {cls.SLUG: cls for cls in ENTITIES}

# model 类名 → slug
MODEL_NAME_TO_SLUG: Dict[str, str] = {cls.__name__: cls.SLUG for cls in ENTITIES}
