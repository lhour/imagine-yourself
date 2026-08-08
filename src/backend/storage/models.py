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
_ACTIVE_GRAPH: Optional[Any] = None  # v4: GraphStore 单例
_ACTIVE_VECTOR: Optional[Any] = None  # v4: VectorStore 单例


def set_active_connection(conn: Optional[sqlite3.Connection]) -> None:
    """由 SaveManager.switch_save 注入当前激活存档的连接。"""
    global _ACTIVE_CONN
    _ACTIVE_CONN = conn


def set_active_graph(graph: Optional[Any]) -> None:
    """v4: 由 SaveManager.switch_save 注入当前激活存档的图库。"""
    global _ACTIVE_GRAPH
    _ACTIVE_GRAPH = graph


def set_active_vector(vs: Optional[Any]) -> None:
    """v4: 由 SaveManager.switch_save 注入当前激活存档的向量库实例。"""
    global _ACTIVE_VECTOR
    _ACTIVE_VECTOR = vs


def _conn() -> sqlite3.Connection:
    if _ACTIVE_CONN is None:
        raise RuntimeError("无激活存档；请先 create_save / switch_save")
    return _ACTIVE_CONN


def graph() -> Optional[Any]:
    """v4: 获取当前激活的图库；未就绪时返回 None。"""
    return _ACTIVE_GRAPH


def vector() -> Optional[Any]:
    """v4: 获取当前激活的向量库实例；未就绪时返回 None。"""
    return _ACTIVE_VECTOR


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
        # v4 新增：客观能力（武力/智力/技能），从 custom_attrs 提升
        ("ability_raw", "ability_raw", False),
        ("ability_polished", "ability_polished", False),
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
        # v4 新增：锚点回链（若本事件实现了某锚点）+ 剧情弧
        ("anchor_id", "anchor_id", False),
        ("plot_arc", "plot_arc", False),
        # 10.1 新增：消息传播字段
        ("propagation_medium", "propagation_medium", False),
        ("propagation_origin_map_id", "propagation_origin_map_id", False),
        ("propagation_origin_group_id", "propagation_origin_group_id", False),
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
    """角色记忆基本表：深度/正确性/视角偏差/遗忘概率。

    v4 新增 person_ids/location_ids/emotion_tags/vector_id：
    取代旧 memory_index 倒排（精确索引走 JSON 数组，语义召回走向量库）。
    """
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
        # v4 新增：精确索引维度（JSON 数组，替代 memory_index）
        ("person_ids", "person_ids", True),
        ("location_ids", "location_ids", True),
        ("emotion_tags", "emotion_tags", True),
        # v4 新增：向量库回链（vec_memories 虚拟表 rowid）
        ("vector_id", "vector_id", False),
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
    """角色任务（短期，最长几天）。

    10.2 时间模型重构：estimated_ticks 弃用（tick 长度不等无法表达"几天"），
    改用 estimated_duration_raw（自然语言时长）+ deadline_game_time（截止游戏时间点）。
    """
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
        # 10.2：自然语言时长（"约3天"/"半天"/"数小时"）+ 截止游戏时间点
        ("estimated_duration_raw", "estimated_duration_raw", False),
        ("deadline_game_time", "deadline_game_time", False),
        ("success_condition_raw", "success_condition_raw", False),
        ("fail_condition_raw", "fail_condition_raw", False),
        ("assigned_by", "assigned_by", False),
        ("parent_quest_id", "parent_quest_id", False),
        ("completion_summary_raw", "completion_summary_raw", False),
        ("blocked_reason_raw", "blocked_reason_raw", False),
        ("custom_attrs", "custom_attrs", True),
    ]


class CharacterAgenda(BaseEntity):
    """角色行动纲领：长期追求（几个月到几年）。

    10.2 时间模型重构：end_tick 弃用（纲领不该有硬结束 tick），
    改用 expected_span_raw（预期跨度）+ review_game_time（下次回顾游戏时间点）。
    status 新增 dormant（休眠，等触发条件唤醒）。
    """
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
        # 10.2：预期跨度（"半年"/"数年"/"终身"）+ 下次回顾游戏时间点
        ("expected_span_raw", "expected_span_raw", False),
        ("review_game_time", "review_game_time", False),
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
# v4 横切：锚点剧情表
# ============================================================

class AnchorPlot(BaseEntity):
    """锚点剧情表（v4 新增核心）。

    人工/模型可随时写入「希望未来发生的剧情」，引导或强制模型实现指定走向。
    inevitability 0-5：0=纯引导灵感，1-2=软引导，3-4=强引导，5=硬约束(必须实现)。
    status 生命周期：pending → active → fulfilled | expired | abandoned。
    """
    TABLE = "anchor_plots"
    SLUG = "anchor_plot"
    FIELDS = [
        ("title", "title", False),
        ("desc_raw", "desc_raw", False),
        ("desc_polished", "desc_polished", False),
        ("inevitability", "inevitability", False),
        ("status", "status", False),
        ("trigger_condition_raw", "trigger_condition_raw", False),
        ("target_tick", "target_tick", False),
        ("created_tick", "created_tick", False),
        ("fulfilled_tick", "fulfilled_tick", False),
        ("fulfilled_event_id", "fulfilled_event_id", False),
        ("created_by", "created_by", False),
        ("priority", "priority", False),
        ("plot_arc", "plot_arc", False),
        ("tags", "tags", True),
        ("custom_attrs", "custom_attrs", True),
    ]


# ============================================================
# v4 主观层：印象缓存表（图库 ViewsAs 边的快查镜像）
# ============================================================

class CharacterImpressionsCache(BaseEntity):
    """A 对 B 的顶层印象缓存（v4 新增）。

    作为图库 ViewsAs 边的关系库快查镜像（双写）：写图库边时同步 upsert 本表，
    读路径优先读本表，缺失/stale 时回退图库。取代旧 character_impressions 表。
    """
    TABLE = "character_impressions_cache"
    SLUG = "character_impressions_cache"
    FIELDS = [
        ("observer_char_id", "observer_char_id", False),
        ("target_char_id", "target_char_id", False),
        ("favorability", "favorability", False),
        ("trust", "trust", False),
        ("fear", "fear", False),
        ("impression_polished", "impression_polished", False),
        ("last_update_tick", "last_update_tick", False),
    ]


class ScheduledEvent(BaseEntity):
    """周期/计划事件调度表（10.3 新增，不进 ENTITIES）。

    世界事件调度器：上课、火山喷发、媒体报道等周期/突发性事件。
    schedule_type: recurring（周期）/ one_shot（一次性）
    recurrence_pattern: daily / weekly / monthly / yearly / custom / once_at
    active: 是否激活（放假关上课、火山喷发后关火山活动）
    """
    TABLE = "scheduled_events"
    SLUG = "scheduled_event"
    FIELDS = [
        ("title", "title", False),
        ("desc_raw", "desc_raw", False),
        ("importance", "importance", False),
        ("schedule_type", "schedule_type", False),
        ("recurrence_pattern", "recurrence_pattern", False),
        ("recurrence_detail_raw", "recurrence_detail_raw", False),
        ("next_trigger_game_time", "next_trigger_game_time", False),
        ("scope", "scope", False),
        ("scope_target_json", "scope_target_json", True),
        ("event_template_json", "event_template_json", True),
        ("active", "active", False),
        ("trigger_condition_raw", "trigger_condition_raw", False),
        ("expire_condition_raw", "expire_condition_raw", False),
        ("created_by", "created_by", False),
        ("created_tick", "created_tick", False),
        ("deactivated_tick", "deactivated_tick", False),
        ("custom_attrs", "custom_attrs", True),
    ]


class EventDissemination(BaseEntity):
    """定向传播触达追踪表（10.1 新增，不进 ENTITIES）。

    承载口头/书信/电话/网络等定向传播的触达追踪。
    status: pending / arrived / distorted / lost
    """
    TABLE = "event_dissemination"
    SLUG = "event_dissemination"
    FIELDS = [
        ("event_id", "event_id", False),
        ("target_char_id", "target_char_id", False),
        ("status", "status", False),
        ("expected_arrival_game_time", "expected_arrival_game_time", False),
        ("arrived_game_time", "arrived_game_time", False),
        ("distortion_level", "distortion_level", False),
        ("received_version_raw", "received_version_raw", False),
        ("source_path_json", "source_path_json", True),
        ("hops", "hops", False),
        ("created_tick", "created_tick", False),
        ("updated_tick", "updated_tick", False),
    ]


class PublicKnowledge(BaseEntity):
    """媒体报道广播通道表（10.1 新增，不进 ENTITIES）。

    媒体报道/官方公告等广播式传播，不预建 per-char 记录。
    角色是否获知由 actor_decide 时按 reach_tags 动态判断。
    """
    TABLE = "public_knowledge"
    SLUG = "public_knowledge"
    FIELDS = [
        ("event_id", "event_id", False),
        ("published_game_time", "published_game_time", False),
        ("medium", "medium", False),
        ("coverage_scope", "coverage_scope", False),
        ("version_raw", "version_raw", False),
        ("reach_tags_json", "reach_tags_json", True),
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
    # 主观记忆系统（4，v4: MemoryIndex/MemoryLink/CharacterImpression 计划废弃迁图库，暂保留兼容）
    Memory,
    MemoryIndex,
    MemoryLink,
    CharacterImpression,
    # 任务系统（3）
    CharacterQuest,
    CharacterAgenda,
    QuestStep,
    # v4 横切：锚点剧情表（阶段 A 通用 CRUD，阶段 B 换专用 anchor_tools）
    AnchorPlot,
    # v4 主观层：character_impressions_cache 不入注册表（避免通用 CRUD 破坏图库一致性，走专用双写）
]

# slug → model 映射
SLUG_TO_MODEL: Dict[str, type] = {cls.SLUG: cls for cls in ENTITIES}

# model 类名 → slug
MODEL_NAME_TO_SLUG: Dict[str, str] = {cls.__name__: cls.SLUG for cls in ENTITIES}
