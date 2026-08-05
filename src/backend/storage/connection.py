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
    ], []),

    # ---------- 客观表 ----------
    ("characters", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "appearance_raw TEXT NOT NULL",
        "appearance_polished TEXT",
        "personality_raw TEXT NOT NULL",
        "personality_polished TEXT",
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
    ], [
        "CREATE INDEX IF NOT EXISTS idx_event_tick ON events(tick_num)",
        "CREATE INDEX IF NOT EXISTS idx_event_map ON events(location_map_id)",
        "CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_event_importance ON events(importance)",
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
    ], [
        "CREATE INDEX IF NOT EXISTS idx_setting_category ON settings(category)",
        "CREATE INDEX IF NOT EXISTS idx_setting_type ON settings(setting_type)",
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
    ], [
        "CREATE INDEX IF NOT EXISTS idx_mem_char ON memories(char_id)",
        "CREATE INDEX IF NOT EXISTS idx_mem_depth ON memories(char_id, depth)",
        "CREATE INDEX IF NOT EXISTS idx_mem_event ON memories(source_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_mem_correct ON memories(correctness)",
        "CREATE INDEX IF NOT EXISTS idx_mem_tick ON memories(remember_tick)",
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

    # ---------- 路径 ----------

    def save_path(self, name: str) -> Path:
        return self.saves_dir / f"{name}.db"

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
        conn.commit()
        conn.close()
        self.switch_save(name)
        return name

    def delete_save(self, name: str) -> None:
        if self.active_save == name:
            self.close_active()
        p = self.save_path(name)
        if p.exists():
            p.unlink()
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
        return name

    def close_active(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self.active_save = None
            models.set_active_connection(None)

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


# ============================================================
# 默认单例
# ============================================================

_default_sm: Optional[SaveManager] = None


def default_save_manager() -> SaveManager:
    global _default_sm
    if _default_sm is None:
        _default_sm = SaveManager()
    return _default_sm
