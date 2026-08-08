"""src.backend.storage.connection — SaveManager + 多存档分库 + 幂等迁移。

SaveManager 负责：
1. 存档 CRUD：create / delete / switch / list
2. 元信息：get_meta / update_meta
3. 主角：get_protagonist / set_protagonist
4. 快照：create / list / restore / delete
5. schema 初始化：_init_schema 在 create_save / switch_save 都触发
6. 迁移：PRAGMA table_info 检测缺列 + ALTER TABLE 补齐
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backend.env import BACKEND_DIR, load_backend_env
from src.backend.storage import models
from src.backend.storage.gameplay_defaults import get_default_gameplay_options

load_backend_env()

SAVES_DIR = Path(os.environ.get("SAVES_DIR", str(BACKEND_DIR / "saves")))
SAVES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Schema 定义（按 v3_redesign_spec.md §2）
# ============================================================

# (table_name, column_definitions, indexes)
SCHEMA: List[Tuple[str, List[str], List[str]]] = [
    # ---------- 元信息 ----------
    ("world_meta", [
        "id INTEGER PRIMARY KEY",
        "tick_num INTEGER NOT NULL DEFAULT 1",
        "game_time TEXT NOT NULL",
        "era_name TEXT",
        "script_name TEXT",
        "protagonist_id INTEGER REFERENCES characters(id)",
        "real_time TEXT NOT NULL",
        "description TEXT",
        "custom_attrs TEXT DEFAULT '{}'",
        # v4 新增：三库就绪状态 + 锚点计数缓存
        "active_anchors_count INTEGER DEFAULT 0",
        "vector_store_ready INTEGER DEFAULT 0",
        "graph_store_ready INTEGER DEFAULT 0",
        # v5 新增：恒定背景（需求四）
        "world_background_raw TEXT",
        "world_background_polished TEXT",
        "civilization_summary TEXT",
        "stable_context_version INTEGER DEFAULT 0",
        # v5 新增：玩法选项（需求一，JSON）
        "gameplay_options TEXT DEFAULT '{}'",
    ], []),

    # ---------- 客观表 ----------
    ("characters", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "appearance_raw TEXT NOT NULL",
        "appearance_polished TEXT",
        "personality_raw TEXT NOT NULL",
        "personality_polished TEXT",
        # v4 新增：客观能力（武力/智力/技能）
        "ability_raw TEXT",
        "ability_polished TEXT",
        "gender TEXT",
        "age INTEGER",
        "status TEXT DEFAULT ''",
        "importance INTEGER DEFAULT 3",
        "custom_attrs TEXT DEFAULT '{}'",
        "created_at_tick INTEGER DEFAULT 0",
        "dead_at_tick INTEGER",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_char_name ON characters(name)",
        "CREATE INDEX IF NOT EXISTS idx_char_status ON characters(status)",
        "CREATE INDEX IF NOT EXISTS idx_char_importance ON characters(importance)",
    ]),

    ("groups", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "group_type TEXT NOT NULL",
        "leader_id INTEGER REFERENCES characters(id)",
        "importance INTEGER DEFAULT 3",
        "primary_map_id INTEGER REFERENCES maps(id)",
        "center_x REAL",
        "center_y REAL",
        "spread_radius REAL DEFAULT 0.0",
        "distribution_raw TEXT",
        "heatmap_grid TEXT",
        "heatmap_resolution INTEGER DEFAULT 16",
        "heatmap_updated_tick INTEGER",
        "custom_attrs TEXT DEFAULT '{}'",
        "created_at_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_group_name ON groups(name)",
        "CREATE INDEX IF NOT EXISTS idx_group_type ON groups(group_type)",
        "CREATE INDEX IF NOT EXISTS idx_group_map ON groups(primary_map_id)",
    ]),

    ("character_group_relations", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "group_id INTEGER NOT NULL REFERENCES groups(id)",
        "role_raw TEXT DEFAULT 'member'",
        "join_tick INTEGER DEFAULT 0",
        "leave_tick INTEGER",
        "importance_in_group INTEGER DEFAULT 3",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_cgr_char ON character_group_relations(char_id)",
        "CREATE INDEX IF NOT EXISTS idx_cgr_group ON character_group_relations(group_id)",
    ]),

    ("group_hierarchies", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "child_group_id INTEGER NOT NULL REFERENCES groups(id)",
        "parent_group_id INTEGER NOT NULL REFERENCES groups(id)",
        "relation_raw TEXT DEFAULT 'subset'",
        "weight REAL DEFAULT 1.0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_gh_child ON group_hierarchies(child_group_id)",
        "CREATE INDEX IF NOT EXISTS idx_gh_parent ON group_hierarchies(parent_group_id)",
    ]),

    ("items", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "item_type TEXT NOT NULL",
        "rarity INTEGER DEFAULT 1",
        "importance INTEGER DEFAULT 3",
        "is_stackable INTEGER DEFAULT 0",
        "stack_size INTEGER DEFAULT 1",
        "custom_attrs TEXT DEFAULT '{}'",
        "created_at_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_item_name ON items(name)",
        "CREATE INDEX IF NOT EXISTS idx_item_type ON items(item_type)",
    ]),

    ("item_holds", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "item_id INTEGER NOT NULL REFERENCES items(id)",
        "quantity INTEGER DEFAULT 1",
        "holder_type TEXT NOT NULL",
        "holder_id INTEGER NOT NULL",
        "holder_detail TEXT",
        "acquired_tick INTEGER DEFAULT 0",
        "use_times INTEGER DEFAULT -1",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_ih_item ON item_holds(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_ih_holder ON item_holds(holder_type, holder_id)",
    ]),

    ("maps", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "parent_map_id INTEGER REFERENCES maps(id)",
        "map_type TEXT NOT NULL",
        "coord_system TEXT DEFAULT 'cartesian_2d'",
        "scale_unit TEXT DEFAULT 'm'",
        "scale_per_unit REAL DEFAULT 1.0",
        "bbox_x REAL DEFAULT 0.0",
        "bbox_y REAL DEFAULT 0.0",
        "bbox_w REAL NOT NULL",
        "bbox_h REAL NOT NULL",
        "bbox_d REAL",
        "default_zoom REAL DEFAULT 1.0",
        "default_center_x REAL",
        "default_center_y REAL",
        "is_mobile INTEGER DEFAULT 0",
        "carrier_char_id INTEGER REFERENCES characters(id)",
        "carrier_item_id INTEGER REFERENCES items(id)",
        "current_x REAL",
        "current_y REAL",
        "current_z REAL",
        "current_map_id INTEGER REFERENCES maps(id)",
        "importance INTEGER DEFAULT 3",
        "custom_attrs TEXT DEFAULT '{}'",
        "created_at_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_map_parent ON maps(parent_map_id)",
        "CREATE INDEX IF NOT EXISTS idx_map_type ON maps(map_type)",
        "CREATE INDEX IF NOT EXISTS idx_map_mobile ON maps(is_mobile)",
        "CREATE INDEX IF NOT EXISTS idx_map_current ON maps(current_map_id)",
    ]),

    ("map_features", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "map_id INTEGER NOT NULL REFERENCES maps(id)",
        "name TEXT NOT NULL",
        "desc_raw TEXT",
        "desc_polished TEXT",
        "feature_type TEXT NOT NULL",
        "shape TEXT NOT NULL",
        "geometry TEXT NOT NULL",
        "size_value REAL",
        "size_unit_override TEXT",
        "layer_z INTEGER DEFAULT 0",
        "color_hint TEXT",
        "icon_hint TEXT",
        "visual_raw TEXT",
        "visual_polished TEXT",
        "is_obstacle INTEGER DEFAULT 0",
        "is_mobile INTEGER DEFAULT 0",
        "carrier_id INTEGER",
        "carrier_type TEXT",
        "current_x REAL",
        "current_y REAL",
        "current_z REAL",
        "child_map_id INTEGER REFERENCES maps(id)",
        "parent_feature_id INTEGER REFERENCES map_features(id)",
        "importance INTEGER DEFAULT 3",
        "custom_attrs TEXT DEFAULT '{}'",
        "created_at_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_mf_map ON map_features(map_id)",
        "CREATE INDEX IF NOT EXISTS idx_mf_type ON map_features(feature_type)",
        "CREATE INDEX IF NOT EXISTS idx_mf_layer ON map_features(map_id, layer_z)",
        "CREATE INDEX IF NOT EXISTS idx_mf_child ON map_features(child_map_id)",
        "CREATE INDEX IF NOT EXISTS idx_mf_mobile ON map_features(is_mobile)",
    ]),

    ("character_locations", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL UNIQUE REFERENCES characters(id)",
        "map_id INTEGER REFERENCES maps(id)",
        "feature_id INTEGER REFERENCES map_features(id)",
        "x REAL",
        "y REAL",
        "z REAL",
        "location_detail_raw TEXT",
        "last_update_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_cl_char ON character_locations(char_id)",
        "CREATE INDEX IF NOT EXISTS idx_cl_map ON character_locations(map_id)",
        "CREATE INDEX IF NOT EXISTS idx_cl_feature ON character_locations(feature_id)",
    ]),

    ("events", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "tick_num INTEGER NOT NULL",
        "game_time TEXT NOT NULL",
        "event_type TEXT NOT NULL",
        "location_map_id INTEGER REFERENCES maps(id)",
        "location_detail_raw TEXT",
        "content_raw TEXT NOT NULL",
        "content_polished TEXT",
        "importance INTEGER DEFAULT 3",
        "visibility TEXT DEFAULT 'public'",
        "source_event_id INTEGER REFERENCES events(id)",
        "custom_attrs TEXT DEFAULT '{}'",
        # v4 新增：锚点回链 + 剧情弧
        "anchor_id INTEGER REFERENCES anchor_plots(id)",
        "plot_arc TEXT",
        # 10.1 新增：消息传播字段
        "propagation_medium TEXT DEFAULT '无'",
        "propagation_origin_map_id INTEGER",
        "propagation_origin_group_id INTEGER",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_event_tick ON events(tick_num)",
        "CREATE INDEX IF NOT EXISTS idx_event_map ON events(location_map_id)",
        "CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_event_importance ON events(importance)",
        "CREATE INDEX IF NOT EXISTS idx_event_anchor ON events(anchor_id)",
        "CREATE INDEX IF NOT EXISTS idx_event_plot_arc ON events(plot_arc)",
    ]),

    ("event_participants", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "event_id INTEGER NOT NULL REFERENCES events(id)",
        "participant_type TEXT NOT NULL",
        "participant_id INTEGER NOT NULL",
        "role_raw TEXT NOT NULL",
        "perception_raw TEXT",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_ep_event ON event_participants(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_ep_participant ON event_participants(participant_type, participant_id)",
    ]),

    ("settings", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "category TEXT NOT NULL",
        "title TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "setting_type TEXT DEFAULT 'essential'",
        "importance INTEGER DEFAULT 3",
        "custom_attrs TEXT DEFAULT '{}'",
        # v5 新增：追加式设定控制（决策3）
        "source TEXT DEFAULT 'drama'",  # drama/human/model
        "immutable INTEGER DEFAULT 0",  # 1=初始设定不可修改/删除
        "parent_setting_id INTEGER REFERENCES settings(id)",  # 追加到哪条设定
        "append_note TEXT",  # 追加理由/补充说明
        "created_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_setting_category ON settings(category)",
        "CREATE INDEX IF NOT EXISTS idx_setting_type ON settings(setting_type)",
        "CREATE INDEX IF NOT EXISTS idx_setting_source ON settings(source)",
        "CREATE INDEX IF NOT EXISTS idx_setting_immutable ON settings(immutable)",
    ]),

    # ---------- 主观记忆系统 ----------
    ("memories", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "source_event_id INTEGER REFERENCES events(id)",
        "memory_raw TEXT NOT NULL",
        "memory_polished TEXT",
        "depth INTEGER DEFAULT 3",
        "correctness INTEGER DEFAULT 100",
        "perspective_bias_raw TEXT",
        "mood TEXT",
        "remember_tick INTEGER NOT NULL",
        "last_recall_tick INTEGER",
        "recall_count INTEGER DEFAULT 0",
        "forget_prob REAL DEFAULT 0.0",
        "is_false INTEGER DEFAULT 0",
        "custom_attrs TEXT DEFAULT '{}'",
        # v4 新增：精确索引维度（JSON 数组，替代 memory_index）+ 向量库回链
        "person_ids TEXT DEFAULT '[]'",
        "location_ids TEXT DEFAULT '[]'",
        "emotion_tags TEXT DEFAULT '[]'",
        "vector_id INTEGER",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_mem_char ON memories(char_id)",
        "CREATE INDEX IF NOT EXISTS idx_mem_depth ON memories(char_id, depth)",
        "CREATE INDEX IF NOT EXISTS idx_mem_event ON memories(source_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_mem_correct ON memories(correctness)",
        "CREATE INDEX IF NOT EXISTS idx_mem_tick ON memories(remember_tick)",
        "CREATE INDEX IF NOT EXISTS idx_mem_vector ON memories(vector_id)",
    ]),

    ("memory_index", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "memory_id INTEGER NOT NULL REFERENCES memories(id)",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "index_type TEXT NOT NULL",
        "index_key TEXT NOT NULL",
        "index_value TEXT",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_mi_mem ON memory_index(memory_id)",
        "CREATE INDEX IF NOT EXISTS idx_mi_lookup ON memory_index(char_id, index_type, index_key)",
    ]),

    ("memory_links", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "memory_a_id INTEGER NOT NULL REFERENCES memories(id)",
        "memory_b_id INTEGER NOT NULL REFERENCES memories(id)",
        "link_type TEXT NOT NULL",
        "link_strength REAL DEFAULT 0.8",
        "weight REAL DEFAULT 1.0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_ml_char_a ON memory_links(char_id, memory_a_id)",
        "CREATE INDEX IF NOT EXISTS idx_ml_char_b ON memory_links(char_id, memory_b_id)",
    ]),

    ("character_impressions", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "observer_char_id INTEGER NOT NULL REFERENCES characters(id)",
        "target_char_id INTEGER NOT NULL REFERENCES characters(id)",
        "impression_raw TEXT NOT NULL",
        "impression_polished TEXT",
        "favorability INTEGER DEFAULT 50",
        "trust INTEGER DEFAULT 50",
        "fear INTEGER DEFAULT 0",
        "last_update_tick INTEGER DEFAULT 0",
    ], [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ci_pair ON character_impressions(observer_char_id, target_char_id)",
    ]),

    # ---------- 任务系统 ----------
    ("character_quests", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "title TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "quest_type TEXT DEFAULT 'side'",
        "status TEXT DEFAULT 'planned'",
        "priority INTEGER DEFAULT 3",
        "start_tick INTEGER NOT NULL",
        "estimated_ticks INTEGER",
        # 10.2 时间模型重构：弃 tick 计数，改游戏时间计量
        "estimated_duration_raw TEXT",
        "deadline_game_time TEXT",
        "success_condition_raw TEXT NOT NULL",
        "fail_condition_raw TEXT",
        "assigned_by TEXT DEFAULT 'player'",
        "parent_quest_id INTEGER REFERENCES character_quests(id)",
        "completion_summary_raw TEXT",
        "blocked_reason_raw TEXT",
        "custom_attrs TEXT DEFAULT '{}'",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_cq_char_status ON character_quests(char_id, status)",
    ]),

    ("character_agendas", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "char_id INTEGER NOT NULL REFERENCES characters(id)",
        "title TEXT NOT NULL",
        "principle_raw TEXT NOT NULL",
        "principle_polished TEXT",
        "status TEXT DEFAULT 'active'",
        "priority INTEGER DEFAULT 3",
        "start_tick INTEGER NOT NULL",
        "end_tick INTEGER",
        # 10.2 时间模型重构：纲领用游戏时间回顾，新增 dormant 休眠状态
        "expected_span_raw TEXT",
        "review_game_time TEXT",
        "conflict_with TEXT",
        "blocked_reason_raw TEXT",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_ca_char ON character_agendas(char_id, status)",
    ]),

    ("quest_steps", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "quest_id INTEGER NOT NULL REFERENCES character_quests(id)",
        "step_no INTEGER NOT NULL",
        "action_raw TEXT NOT NULL",
        "status TEXT DEFAULT 'pending'",
        "done_tick INTEGER",
        "condition_raw TEXT",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_qs_quest ON quest_steps(quest_id)",
    ]),

    # ---------- v4 横切：锚点剧情表 ----------
    ("anchor_plots", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "title TEXT NOT NULL",
        "desc_raw TEXT NOT NULL",
        "desc_polished TEXT",
        "inevitability INTEGER NOT NULL DEFAULT 3",  # 0-5
        "status TEXT NOT NULL DEFAULT 'pending'",    # pending|active|fulfilled|expired|abandoned
        "trigger_condition_raw TEXT",
        "target_tick INTEGER",
        "created_tick INTEGER NOT NULL",
        "fulfilled_tick INTEGER",
        "fulfilled_event_id INTEGER REFERENCES events(id)",
        "created_by TEXT NOT NULL DEFAULT 'model'",  # human|model|system
        "priority INTEGER DEFAULT 3",
        "plot_arc TEXT",
        "tags TEXT DEFAULT '[]'",
        "custom_attrs TEXT DEFAULT '{}'",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_anchor_status ON anchor_plots(status, inevitability)",
        "CREATE INDEX IF NOT EXISTS idx_anchor_target ON anchor_plots(target_tick) WHERE status IN ('pending','active')",
        "CREATE INDEX IF NOT EXISTS idx_anchor_arc ON anchor_plots(plot_arc)",
        "CREATE INDEX IF NOT EXISTS idx_anchor_created_by ON anchor_plots(created_by)",
    ]),

    # ---------- v4 主观层：印象缓存表（图库 ViewsAs 边的快查镜像） ----------
    ("character_impressions_cache", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "observer_char_id INTEGER NOT NULL REFERENCES characters(id)",
        "target_char_id INTEGER NOT NULL REFERENCES characters(id)",
        "favorability INTEGER DEFAULT 50",
        "trust INTEGER DEFAULT 50",
        "fear INTEGER DEFAULT 0",
        "impression_polished TEXT",
        "last_update_tick INTEGER DEFAULT 0",
    ], [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ci_cache_pair ON character_impressions_cache(observer_char_id, target_char_id)",
        "CREATE INDEX IF NOT EXISTS idx_ci_cache_observer ON character_impressions_cache(observer_char_id)",
    ]),

    # ---------- v5 新增：操作审计日志（需求一 / 七公共基础设施） ----------
    ("operation_log", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "op_type TEXT NOT NULL",              # create_dynamic_entity / append_setting / web_fetch / kb_add / ...
        "op_entity_type TEXT",                # character / group / setting / map / map_feature / item
        "op_entity_id INTEGER",               # 操作的实体 id
        "actor TEXT NOT NULL",                # model / human / system
        "tool TEXT NOT NULL",                 # 调用的工具名
        "args_json TEXT DEFAULT '{}'",        # 工具参数
        "result_json TEXT DEFAULT '{}'",      # 工具返回结果
        "tick_num INTEGER DEFAULT 0",
        "game_time TEXT",
        "created_at TEXT NOT NULL",           # ISO 时间戳
        "success INTEGER DEFAULT 1",          # 1=成功 0=失败
        "error_msg TEXT",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_oplog_type ON operation_log(op_type)",
        "CREATE INDEX IF NOT EXISTS idx_oplog_entity ON operation_log(op_entity_type, op_entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_oplog_tick ON operation_log(tick_num)",
        "CREATE INDEX IF NOT EXISTS idx_oplog_actor ON operation_log(actor)",
        "CREATE INDEX IF NOT EXISTS idx_oplog_time ON operation_log(created_at)",
    ]),

    # ---------- 10.3 周期事件调度（世界事件调度器，不进 ENTITIES）----------
    ("scheduled_events", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "title TEXT NOT NULL",
        "desc_raw TEXT",
        "importance INTEGER DEFAULT 3",            # 0-5，遵守项目硬约束
        "schedule_type TEXT NOT NULL DEFAULT 'recurring'",  # recurring / one_shot
        "recurrence_pattern TEXT",                 # daily / weekly / monthly / yearly / custom / once_at
        "recurrence_detail_raw TEXT",              # 自然语言（"每天上午8点上课"）
        "next_trigger_game_time TEXT",             # 下次触发游戏时间
        "scope TEXT DEFAULT 'global'",             # character / group / global
        "scope_target_json TEXT DEFAULT '[]'",     # 影响的角色/群体ID数组
        "event_template_json TEXT DEFAULT '{}'",   # 触发时生成的事件模板
        "active INTEGER DEFAULT 1",                # 是否激活
        "trigger_condition_raw TEXT",              # 激活条件
        "expire_condition_raw TEXT",               # 失效条件
        "created_by TEXT DEFAULT 'drama'",         # drama / model / human
        "created_tick INTEGER DEFAULT 0",
        "deactivated_tick INTEGER",
        "custom_attrs TEXT DEFAULT '{}'",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_se_active ON scheduled_events(active, next_trigger_game_time)",
        "CREATE INDEX IF NOT EXISTS idx_se_scope ON scheduled_events(scope)",
    ]),

    # ---------- 10.1 消息传播（定向传播触达追踪 + 媒体广播通道，不进 ENTITIES）----------
    ("event_dissemination", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "event_id INTEGER NOT NULL REFERENCES events(id)",
        "target_char_id INTEGER NOT NULL REFERENCES characters(id)",
        "status TEXT NOT NULL DEFAULT 'pending'",
        "expected_arrival_game_time TEXT",
        "arrived_game_time TEXT",
        "distortion_level INTEGER DEFAULT 0",
        "received_version_raw TEXT",
        "source_path_json TEXT DEFAULT '[]'",
        "hops INTEGER DEFAULT 0",
        "created_tick INTEGER DEFAULT 0",
        "updated_tick INTEGER DEFAULT 0",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_ed_status ON event_dissemination(status, expected_arrival_game_time)",
        "CREATE INDEX IF NOT EXISTS idx_ed_event ON event_dissemination(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_ed_target ON event_dissemination(target_char_id)",
    ]),

    ("public_knowledge", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "event_id INTEGER NOT NULL REFERENCES events(id)",
        "published_game_time TEXT",
        "medium TEXT",
        "coverage_scope TEXT",
        "version_raw TEXT",
        "reach_tags_json TEXT DEFAULT '[]'",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_pk_event ON public_knowledge(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_pk_medium ON public_knowledge(medium)",
    ]),
]


# ============================================================
# SaveManager
# ============================================================

class SaveManager:
    """多存档分库管理器。"""

    def __init__(self, saves_dir: Optional[Path] = None) -> None:
        self.saves_dir = saves_dir or SAVES_DIR
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        self.active_save: Optional[str] = None
        self._conn: Optional[sqlite3.Connection] = None
        # v4 新增：图库/向量库激活引用
        self._active_graph: Optional["graph_store.GraphStore"] = None
        self._active_vector: Optional[Any] = None  # v4: VectorStore 单例

    # ---------- 路径 ----------

    def save_path(self, name: str) -> Path:
        return self.saves_dir / f"{name}.db"

    @property
    def _active_save_file(self) -> Path:
        """持久化活跃存档名的文件（后端重启后自动恢复）。"""
        return self.saves_dir / ".active_save"

    def _persist_active(self) -> None:
        """把当前活跃存档名写入文件，供重启后恢复。"""
        try:
            if self.active_save:
                self._active_save_file.write_text(
                    self.active_save, encoding="utf-8"
                )
            elif self._active_save_file.exists():
                self._active_save_file.unlink()
        except OSError:
            pass  # 持久化失败不阻断主流程

    def restore_active(self) -> Optional[str]:
        """从文件恢复上次激活的存档（后端重启后调用）。

        仅当存档文件仍存在时才恢复；恢复失败（如 db 损坏）时静默返回 None。
        """
        try:
            if not self._active_save_file.exists():
                return None
            name = self._active_save_file.read_text(encoding="utf-8").strip()
            if not name or not self.save_path(name).exists():
                # 存档已被删除，清理残留的标记文件
                self._active_save_file.unlink(missing_ok=True)
                return None
            self.switch_save(name)
            return name
        except Exception:
            return None

    def snapshots_dir(self, name: str) -> Path:
        return self.saves_dir / f"{name}.snapshots"

    # ---------- 存档 CRUD ----------

    def list_saves(self) -> List[str]:
        return sorted(
            p.stem for p in self.saves_dir.glob("*.db")
            if p.is_file() and not p.name.startswith(".")
        )

    def create_save(self, name: str) -> str:
        """创建新存档并激活。重名直接报错，不覆盖。"""
        if not name or any(c in name for c in r'\/:*?"<>|'):
            raise ValueError(f"非法存档名: {name!r}")
        p = self.save_path(name)
        if p.exists():
            raise FileExistsError(f"存档已存在: {name}")
        # 连接新 db 并初始化 schema
        conn = sqlite3.connect(p, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema(conn)
        # 初始化元信息单例行
        conn.execute(
            "INSERT OR IGNORE INTO world_meta (id, tick_num, game_time, real_time, custom_attrs) "
            "VALUES (1, 1, ?, ?, '{}')",
            ["源石纪元1年1月1日08时00分00秒", time.strftime("%Y-%m-%d %H:%M:%S")],
        )
        # v4: 初始化向量库虚拟表
        self._init_vector(conn)
        conn.commit()
        conn.close()
        # v4: 初始化图库（KuzuDB）
        self._init_graph(p)
        self.switch_save(name)
        return name

    def delete_save(self, name: str) -> None:
        p = self.save_path(name)
        if not p.exists():
            raise FileNotFoundError(f"存档不存在: {name}")
        if self.active_save == name:
            self.close_active()
        p.unlink()
        # v4: 同步删除图库目录
        kuzu_path = self.saves_dir / f"{name}.kuzu"
        if kuzu_path.exists():
            shutil.rmtree(kuzu_path, ignore_errors=True)
        sd = self.snapshots_dir(name)
        if sd.exists():
            shutil.rmtree(sd, ignore_errors=True)

    def switch_save(self, name: str) -> str:
        p = self.save_path(name)
        if not p.exists():
            raise FileNotFoundError(f"存档不存在: {name}")
        self.close_active()
        conn = sqlite3.connect(p, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # 触发迁移（旧存档自动补列）
        self._init_schema(conn)
        # v4: 确保向量库虚拟表存在并保存实例（避免后续重复 sqlite_vec.load）
        self._active_vector = self._init_vector(conn)
        models.set_active_vector(self._active_vector)
        # 确保元信息单例行存在
        conn.execute(
            "INSERT OR IGNORE INTO world_meta (id, tick_num, game_time, real_time, custom_attrs) "
            "VALUES (1, 1, ?, ?, '{}')",
            ["源石纪元1年1月1日08时00分00秒", time.strftime("%Y-%m-%d %H:%M:%S")],
        )
        conn.commit()
        self._conn = conn
        self.active_save = name
        models.set_active_connection(conn)
        # v4: 激活图库
        self._active_graph = self._connect_graph(p)
        models.set_active_graph(self._active_graph)
        # 持久化活跃存档名（后端重启后自动恢复）
        self._persist_active()
        return name

    def close_active(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        # v4: 关闭图库
        if self._active_graph is not None:
            self._active_graph.close()
            self._active_graph = None
        # v4: 清理向量库引用（依附 conn，无需显式 close）
        self._active_vector = None
        self.active_save = None
        models.set_active_connection(None)
        models.set_active_graph(None)
        models.set_active_vector(None)
        # 清除持久化标记（当前无活跃存档）
        self._persist_active()

    # ---------- 元信息 ----------

    def get_meta(self) -> Dict[str, Any]:
        if not self._conn:
            raise RuntimeError("无激活存档")
        row = self._conn.execute("SELECT * FROM world_meta WHERE id = 1").fetchone()
        if not row:
            return {}
        d = dict(row)
        # 解析 custom_attrs
        if d.get("custom_attrs"):
            try:
                d["custom_attrs"] = __import__("json").loads(d["custom_attrs"])
            except Exception:
                pass
        return d

    def update_meta(self, **fields) -> Dict[str, Any]:
        if not self._conn:
            raise RuntimeError("无激活存档")
        import json
        allowed = {
            "tick_num", "game_time", "era_name", "script_name",
            "protagonist_id", "description",
            # v5 新增：恒定背景 + 玩法选项
            "world_background_raw", "world_background_polished",
            "civilization_summary", "stable_context_version",
            "gameplay_options",
        }
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k} = ?")
            vals.append(v)
        # real_time 自动刷新
        sets.append("real_time = ?")
        vals.append(time.strftime("%Y-%m-%d %H:%M:%S"))
        if "custom_attrs" in fields:
            v = fields["custom_attrs"]
            if isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            sets.append("custom_attrs = ?")
            vals.append(v)
        vals.append(1)
        self._conn.execute(f"UPDATE world_meta SET {','.join(sets)} WHERE id = ?", vals)
        self._conn.commit()
        return self.get_meta()

    # ---------- 主角 ----------

    def get_protagonist(self) -> Optional[Dict[str, Any]]:
        meta = self.get_meta()
        pid = meta.get("protagonist_id")
        if not pid:
            return None
        row = self._conn.execute("SELECT * FROM characters WHERE id = ?", [pid]).fetchone()  # type: ignore[union-attr]
        return dict(row) if row else None

    def set_protagonist(self, char_id: int) -> Dict[str, Any]:
        return self.update_meta(protagonist_id=char_id)

    def get_save_meta(self, name: str) -> Dict[str, Any]:
        """读取指定存档的元信息，不切换当前存档。"""
        p = self.save_path(name)
        if not p.exists():
            raise FileNotFoundError(f"存档不存在: {name}")
        conn = sqlite3.connect(p, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            # 尝试运行 schema 迁移（幂等），失败时忽略
            try:
                self._init_schema(conn)
            except Exception:
                pass
            # 确保元信息行存在
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO world_meta (id, tick_num, game_time, real_time, custom_attrs) "
                    "VALUES (1, 1, ?, ?, '{}')",
                    ["源石纪元1年1月1日08时00分00秒", time.strftime("%Y-%m-%d %H:%M:%S")],
                )
                conn.commit()
            except Exception:
                pass
            row = conn.execute("SELECT * FROM world_meta WHERE id = 1").fetchone()
            if not row:
                return {"save": name}
            d = dict(row)
            if d.get("custom_attrs"):
                try:
                    import json as _json
                    d["custom_attrs"] = _json.loads(d["custom_attrs"])
                except Exception:
                    pass
            # 读取主角信息
            pid = d.get("protagonist_id")
            if pid:
                try:
                    char_row = conn.execute("SELECT id, name FROM characters WHERE id = ?", [pid]).fetchone()
                    if char_row:
                        cd = dict(char_row)
                        d["protagonist_name"] = cd.get("name") or f"#{pid}"
                except Exception:
                    pass
            d["save"] = name
            return d
        finally:
            conn.close()

    def get_all_saves_meta(self) -> List[Dict[str, Any]]:
        """批量读取所有存档的元信息，不切换当前存档。"""
        result = []
        for name in self.list_saves():
            try:
                result.append(self.get_save_meta(name))
            except Exception:
                result.append({"save": name, "error": True})
        return result

    # ---------- 快照 ----------

    def list_snapshots(self, name: str) -> List[Dict[str, Any]]:
        sd = self.snapshots_dir(name)
        if not sd.exists():
            return []
        out = []
        for p in sorted(sd.glob("*.db")):
            stat = p.stat()
            out.append({
                "file": p.name,
                "size": stat.st_size,
                "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            })
        return out

    def create_snapshot(self) -> str:
        if not self.active_save:
            raise RuntimeError("无激活存档")
        name = self.active_save
        sd = self.snapshots_dir(name)
        sd.mkdir(parents=True, exist_ok=True)
        # 用当前 tick 作快照名
        meta = self.get_meta()
        tick = meta.get("tick_num", 0)
        fname = f"round_{tick:04d}_{time.strftime('%Y%m%d_%H%M%S')}.db"
        snap_path = sd / fname
        # VACUUM INTO 创建独立快照
        self._conn.execute(f"VACUUM INTO '{snap_path.as_posix()}'")  # type: ignore[union-attr]
        return fname

    def restore_snapshot(self, snapshot_file: str) -> str:
        if not self.active_save:
            raise RuntimeError("无激活存档")
        name = self.active_save
        snap_path = self.snapshots_dir(name) / snapshot_file
        if not snap_path.exists():
            raise FileNotFoundError(f"快照不存在: {snapshot_file}")
        # 关闭当前连接，覆盖 db 文件
        self.close_active()
        shutil.copy2(snap_path, self.save_path(name))
        self.switch_save(name)
        return name

    def delete_snapshot(self, snapshot_file: str) -> None:
        if not self.active_save:
            raise RuntimeError("无激活存档")
        p = self.snapshots_dir(self.active_save) / snapshot_file
        if p.exists():
            p.unlink()

    # ---------- v5: 玩法选项（gameplay_options） ----------

    def get_gameplay_options(self) -> Dict[str, Any]:
        """获取当前存档的玩法选项（含默认值合并）。"""
        meta = self.get_meta()
        gopts = meta.get("gameplay_options") or {}
        import json
        defaults = get_default_gameplay_options()
        if isinstance(gopts, str):
            try:
                gopts = json.loads(gopts)
            except Exception:
                gopts = {}
        merged = self._deep_merge(defaults, gopts)
        return merged

    def set_gameplay_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """更新玩法选项。"""
        import json
        self.update_meta(gameplay_options=json.dumps(options, ensure_ascii=False))
        return self.get_gameplay_options()

    def patch_gameplay_options(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """部分更新玩法选项。"""
        current = self.get_gameplay_options()
        merged = self._deep_merge(current, patch)
        return self.set_gameplay_options(merged)

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """深度合并两个 dict：override 覆盖 base，嵌套 dict 也深合并。"""
        import copy
        result = copy.deepcopy(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = SaveManager._deep_merge(result[key], val)
            else:
                result[key] = copy.deepcopy(val)
        return result

    # ---------- v5: 操作审计日志（operation_log） ----------

    def log_operation(self, op_type: str, tool: str, *,
                     op_entity_type: str = "", op_entity_id: Optional[int] = None,
                     actor: str = "model", args: Optional[Dict] = None,
                     result: Optional[Dict] = None, success: bool = True,
                     error_msg: str = "") -> int:
        """写入一条操作日志，返回新记录 id。"""
        if not self._conn:
            raise RuntimeError("无激活存档")
        meta = self.get_meta()
        import json
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._conn.execute(
            "INSERT INTO operation_log "
            "(op_type, op_entity_type, op_entity_id, actor, tool, "
            "args_json, result_json, tick_num, game_time, created_at, success, error_msg) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                op_type, op_entity_type, op_entity_id, actor, tool,
                json.dumps(args or {}, ensure_ascii=False),
                json.dumps(result or {}, ensure_ascii=False),
                meta.get("tick_num", 0),
                meta.get("game_time", ""),
                created_at,
                1 if success else 0,
                error_msg,
            ]
        )
        self._conn.commit()
        last_id = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return last_id

    def query_operations(self, *,
                         op_type: str = "", actor: str = "",
                         op_entity_type: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """查询操作日志，默认最近 50 条。"""
        if not self._conn:
            return []
        sql = "SELECT * FROM operation_log WHERE 1=1"
        params: List[Any] = []
        if op_type:
            sql += " AND op_type = ?"
            params.append(op_type)
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if op_entity_type:
            sql += " AND op_entity_type = ?"
            params.append(op_entity_type)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        result = []
        import json
        for row in rows:
            d = dict(row)
            for k in ("args_json", "result_json"):
                if d.get(k):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        pass
            result.append(d)
        return result

    # ---------- v5: 动态实体计数（供配额检查器使用） ----------

    def count_dynamic_entities(self, entity_type: str, since_tick: int = 0) -> int:
        """统计指定实体类型自 since_tick 以来的新增数量。"""
        if not self._conn:
            return 0
        sql = (
            "SELECT COUNT(*) FROM operation_log "
            "WHERE op_type = 'create_dynamic_entity' "
            "AND op_entity_type = ? AND tick_num >= ? AND success = 1"
        )
        row = self._conn.execute(sql, [entity_type, since_tick]).fetchone()
        return row[0] if row else 0

    def count_dynamic_entities_total(self, entity_type: str) -> int:
        """统计指定实体类型的累计新增总量。"""
        if not self._conn:
            return 0
        sql = (
            "SELECT COUNT(*) FROM operation_log "
            "WHERE op_type = 'create_dynamic_entity' "
            "AND op_entity_type = ? AND success = 1"
        )
        row = self._conn.execute(sql, [entity_type]).fetchone()
        return row[0] if row else 0

    # ---------- Schema 初始化 + 迁移 ----------

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """建表 + 补列（幂等）。在 create_save / switch_save 都触发。"""
        cur = conn.cursor()
        for table, cols, indexes in SCHEMA:
            col_defs = ", ".join(cols)
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})")
            for idx_sql in indexes:
                cur.execute(idx_sql)
        # 迁移：检测已有表的缺列，ALTER TABLE 补齐
        for table, cols, _ in SCHEMA:
            existing = {row["name"] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
            for col_def in cols:
                # 解析列定义首段为列名
                first = col_def.strip().split()[0]
                if first.upper() in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"):
                    continue
                col_name = first
                if col_name not in existing:
                    # 添加列（带默认值）
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        conn.commit()

    # ---------- v4: 向量库 & 图库 初始化 ----------

    def _init_vector(self, conn: sqlite3.Connection) -> Optional[Any]:
        """幂等：初始化 sqlite-vec 虚拟表并返回 VectorStore 实例。

        忽略不可用错误（旧存档无扩展时降级，返回 None）。
        返回实例供 switch_save 保存到 _active_vector，避免后续重复 sqlite_vec.load 报错。
        """
        try:
            from src.backend.storage.vector_store import VectorStore
            vs = VectorStore(conn)
            vs.init_database()
            # 把三库就绪状态写回 meta
            try:
                conn.execute(
                    "UPDATE world_meta SET vector_store_ready = 1 WHERE id = 1"
                )
                conn.commit()
            except Exception:
                pass
            return vs
        except Exception:
            # sqlite-vec 加载失败不阻塞主流程
            return None

    def _init_graph(self, save_path: Path) -> "graph_store.GraphStore":
        """创建新存档的图库并初始化节点/边表。返回 GraphStore。

        若 kuzu 不可用则返回空壳 GraphStore，不阻塞主流程。
        """
        from src.backend.storage import graph_store
        gs = graph_store.GraphStore.connect_for_save(save_path)
        try:
            gs.init_database()
            try:
                self._conn.execute(
                    "UPDATE world_meta SET graph_store_ready = 1 WHERE id = 1"
                )
                self._conn.commit()
            except Exception:
                pass
        except graph_store.GraphStoreUnavailable:
            pass  # 图库不可用不阻塞
        return gs

    def _connect_graph(self, save_path: Path) -> "graph_store.GraphStore":
        """连接现有存档的图库（若不存在则创建）。"""
        from src.backend.storage import graph_store
        gs = graph_store.GraphStore.connect_for_save(save_path)
        try:
            gs.init_database()
        except graph_store.GraphStoreUnavailable:
            pass
        return gs


# ============================================================
# 默认单例
# ============================================================

_default_sm: Optional[SaveManager] = None


def default_save_manager() -> SaveManager:
    global _default_sm
    if _default_sm is None:
        _default_sm = SaveManager()
        # 后端重启后自动恢复上次激活的存档（从 .active_save 文件读取），
        # 避免前端显示「当前存档 未激活」——用户无需手动重新切换。
        _default_sm.restore_active()
    return _default_sm
