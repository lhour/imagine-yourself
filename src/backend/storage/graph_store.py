"""src.backend.storage.graph_store — KuzuDB 图库封装。

所有实体间关系（客观/主观/记忆宫殿）统一进图库，
作为带类型与属性的边。关系库仅保留 character_impressions_cache
作图库 ViewsAs 边的快查镜像（双写）。

节点表：CharacterNode / GroupNode / ItemNode / MapNode / EventNode / MemoryNode
边表：
  客观边：MemberOf / Leads / SubordinateTo / ParticipatedIn / Holds
  主观边：ViewsAs / ViewsGroupAs（有向，A→B）
  记忆宫殿：MemoryLink

用法：
  gs = GraphStore.connect_for_save(name)
  gs.init_database()         # 建节点/边表（幂等）
  gs.add_character_node(id, name)
  gs.add_views_as_edge(observer_id, target_id, favorability=30, ...)
  rows = gs.query("MATCH (a)-[v:ViewsAs]->(b) WHERE a.id=$aid RETURN b.id")
  gs.close()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import kuzu  # type: ignore[import-not-found]
    _KUZU_AVAILABLE = True
except ImportError:  # pragma: no cover - kuzu 为可选依赖
    kuzu = None  # type: ignore[assignment]
    _KUZU_AVAILABLE = False


def is_available() -> bool:
    """判断 KuzuDB 是否可用。"""
    return _KUZU_AVAILABLE


class GraphStoreUnavailable(RuntimeError):
    """当 kuzu 未安装且调用图库方法时抛出。"""


# ============================================================
# DDL：节点表 & 边表（幂等，init_database 内调用）
# ============================================================

_NODE_DDLS: List[str] = [
    "CREATE NODE TABLE IF NOT EXISTS CharacterNode (id INT64, name STRING, PRIMARY KEY (id))",
    "CREATE NODE TABLE IF NOT EXISTS GroupNode   (id INT64, name STRING, PRIMARY KEY (id))",
    "CREATE NODE TABLE IF NOT EXISTS ItemNode    (id INT64, name STRING, PRIMARY KEY (id))",
    "CREATE NODE TABLE IF NOT EXISTS MapNode     (id INT64, name STRING, PRIMARY KEY (id))",
    "CREATE NODE TABLE IF NOT EXISTS EventNode   (id INT64, tick INT64, PRIMARY KEY (id))",
    "CREATE NODE TABLE IF NOT EXISTS MemoryNode  (id INT64, char_id INT64, depth INT64, PRIMARY KEY (id))",
]

_REL_DDLS: List[str] = [
    # 客观边（kuzu 0.11.x：FROM X TO Y 无逗号）
    "CREATE REL TABLE IF NOT EXISTS MemberOf (FROM CharacterNode TO GroupNode, role STRING, join_tick INT64, leave_tick INT64, importance INT64)",
    "CREATE REL TABLE IF NOT EXISTS Leads (FROM CharacterNode TO GroupNode, since_tick INT64)",
    "CREATE REL TABLE IF NOT EXISTS SubordinateTo (FROM GroupNode TO GroupNode, relation STRING, weight DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS ParticipatedIn (FROM CharacterNode TO EventNode, role STRING, depth_hint INT64)",
    "CREATE REL TABLE IF NOT EXISTS Holds (FROM CharacterNode TO ItemNode, quantity INT64, acquired_tick INT64)",
    # 主观边（有向，A 对 B 的主观看法）
    "CREATE REL TABLE IF NOT EXISTS ViewsAs (FROM CharacterNode TO CharacterNode, impression_raw STRING, impression_polished STRING, favorability INT64, trust INT64, fear INT64, last_update_tick INT64, summary STRING)",
    "CREATE REL TABLE IF NOT EXISTS ViewsGroupAs (FROM CharacterNode TO GroupNode, favorability INT64, trust INT64, last_update_tick INT64)",
    # 记忆宫殿边
    "CREATE REL TABLE IF NOT EXISTS MemoryLink (FROM MemoryNode TO MemoryNode, char_id INT64, link_type STRING, link_strength DOUBLE, weight DOUBLE)",
    # 10.1 社交接触边（日常接触强度，传播路径依据，由 character_updater 维护）
    "CREATE REL TABLE IF NOT EXISTS FrequentContact (FROM CharacterNode TO CharacterNode, weight DOUBLE, last_interaction_tick INT64, interaction_count INT64)",
]


class GraphStore:
    """单存档级别的 KuzuDB 连接封装。

    设计为每个存档持有独立的 .kuzu 目录，通过
    :meth:`connect_for_save` 类方法打开；
    :meth:`init_database` 幂等建表。
    """

    def __init__(self, db: Any = None) -> None:
        self._db = db

    def _require_kuzu(self) -> None:
        if self._db is None or not _KUZU_AVAILABLE:
            raise GraphStoreUnavailable("kuzu 图库不可用，请先安装 kuzu-python")

    # ---------- 生命周期 ----------

    @classmethod
    def connect_for_save(cls, save_path: Path) -> "GraphStore":
        """打开指定存档的图库（路径为 save.db 同级的 .kuzu 目录）。

        若 kuzu 未安装则返回空壳 GraphStore，调用任何操作方法都会抛出
        GraphStoreUnavailable，便于上层降级处理。
        """
        if not _KUZU_AVAILABLE:
            return cls(None)
        kuzu_path = save_path.parent / f"{save_path.stem}.kuzu"
        kuzu_db = kuzu.Database(str(kuzu_path))
        # kuzu 0.11.x：Connection 通过构造函数创建，而非 Database.connect()
        conn = kuzu.Connection(kuzu_db)
        return cls(conn)

    def close(self) -> None:
        """关闭连接（kuzu.Connection 无显式 close，引用释放即可）。"""
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- DDL ----------

    def init_database(self) -> None:
        """幂等：建节点表 & 边表（CREATE TABLE IF NOT EXISTS）。"""
        self._require_kuzu()
        for ddl in _NODE_DDLS:
            self._db.execute(ddl)
        for ddl in _REL_DDLS:
            self._db.execute(ddl)

    # ---------- 节点 ----------

    def add_character_node(self, char_id: int, name: str) -> None:
        self._db.execute(
            "MERGE INTO CharacterNode {id: $id, name: $name}",
            {"id": char_id, "name": name},
        )

    def add_group_node(self, group_id: int, name: str) -> None:
        self._db.execute(
            "MERGE INTO GroupNode {id: $id, name: $name}",
            {"id": group_id, "name": name},
        )

    def add_item_node(self, item_id: int, name: str) -> None:
        self._db.execute(
            "MERGE INTO ItemNode {id: $id, name: $name}",
            {"id": item_id, "name": name},
        )

    def add_map_node(self, map_id: int, name: str) -> None:
        self._db.execute(
            "MERGE INTO MapNode {id: $id, name: $name}",
            {"id": map_id, "name": name},
        )

    def add_event_node(self, event_id: int, tick: int) -> None:
        self._db.execute(
            "MERGE INTO EventNode {id: $id, tick: $tick}",
            {"id": event_id, "tick": tick},
        )

    def add_memory_node(self, memory_id: int, char_id: int, depth: int) -> None:
        self._db.execute(
            "MERGE INTO MemoryNode {id: $id, char_id: $char_id, depth: $depth}",
            {"id": memory_id, "char_id": char_id, "depth": depth},
        )

    # ---------- 边（客观） ----------

    def add_member_of(
        self,
        char_id: int,
        group_id: int,
        role: str = "member",
        join_tick: int = 0,
        leave_tick: Optional[int] = None,
        importance: int = 3,
    ) -> None:
        # MERGE 边的语法在 kuzu 中需要先 MERGE 两端节点
        self.add_character_node(char_id, "")
        self.add_group_node(group_id, "")
        self._db.execute(
            "MERGE (c:CharacterNode {id: $cid})-[r:MemberOf]->(g:GroupNode {id: $gid}) "
            "SET r.role = $role, r.join_tick = $jt, r.leave_tick = $lt, r.importance = $imp",
            {"cid": char_id, "gid": group_id, "role": role, "jt": join_tick, "lt": leave_tick, "imp": importance},
        )

    def add_leads(self, char_id: int, group_id: int, since_tick: int = 0) -> None:
        self.add_character_node(char_id, "")
        self.add_group_node(group_id, "")
        self._db.execute(
            "MERGE (c:CharacterNode {id: $cid})-[r:Leads]->(g:GroupNode {id: $gid}) "
            "SET r.since_tick = $st",
            {"cid": char_id, "gid": group_id, "st": since_tick},
        )

    def add_subordinate_to(
        self, child_group_id: int, parent_group_id: int, relation: str = "subset", weight: float = 1.0
    ) -> None:
        self.add_group_node(child_group_id, "")
        self.add_group_node(parent_group_id, "")
        self._db.execute(
            "MERGE (c:GroupNode {id: $cid})-[r:SubordinateTo]->(p:GroupNode {id: $pid}) "
            "SET r.relation = $rel, r.weight = $w",
            {"cid": child_group_id, "pid": parent_group_id, "rel": relation, "w": weight},
        )

    def add_participated_in(
        self, char_id: int, event_id: int, role: str = "witness", depth_hint: int = 6
    ) -> None:
        self.add_character_node(char_id, "")
        self.add_event_node(event_id, 0)
        self._db.execute(
            "MERGE (c:CharacterNode {id: $cid})-[r:ParticipatedIn]->(e:EventNode {id: $eid}) "
            "SET r.role = $role, r.depth_hint = $dh",
            {"cid": char_id, "eid": event_id, "role": role, "dh": depth_hint},
        )

    def add_holds(self, char_id: int, item_id: int, quantity: int = 1, acquired_tick: int = 0) -> None:
        self.add_character_node(char_id, "")
        self.add_item_node(item_id, "")
        self._db.execute(
            "MERGE (c:CharacterNode {id: $cid})-[r:Holds]->(i:ItemNode {id: $iid}) "
            "SET r.quantity = $q, r.acquired_tick = $at",
            {"cid": char_id, "iid": item_id, "q": quantity, "at": acquired_tick},
        )

    # ---------- 主观边（有向 A → B 的主观看法）----------

    def upsert_views_as(
        self,
        observer_id: int,
        target_id: int,
        impression_raw: str = "",
        impression_polished: str = "",
        favorability: int = 50,
        trust: int = 50,
        fear: int = 0,
        last_update_tick: int = 0,
        summary: str = "",
    ) -> None:
        """写 A 对 B 的主观看法（有向）。重复调用即 upsert。"""
        self.add_character_node(observer_id, "")
        self.add_character_node(target_id, "")
        self._db.execute(
            "MERGE (o:CharacterNode {id: $oid})-[v:ViewsAs]->(t:CharacterNode {id: $tid}) "
            "SET v.impression_raw = $ir, v.impression_polished = $ip, "
            "v.favorability = $f, v.trust = $tr, v.fear = $fe, "
            "v.last_update_tick = $lut, v.summary = $sm",
            {
                "oid": observer_id, "tid": target_id,
                "ir": impression_raw, "ip": impression_polished,
                "f": favorability, "tr": trust, "fe": fear,
                "lut": last_update_tick, "sm": summary,
            },
        )

    def upsert_views_group_as(
        self,
        observer_id: int,
        group_id: int,
        favorability: int = 50,
        trust: int = 50,
        last_update_tick: int = 0,
    ) -> None:
        self.add_character_node(observer_id, "")
        self.add_group_node(group_id, "")
        self._db.execute(
            "MERGE (o:CharacterNode {id: $oid})-[v:ViewsGroupAs]->(g:GroupNode {id: $gid}) "
            "SET v.favorability = $f, v.trust = $tr, v.last_update_tick = $lut",
            {"oid": observer_id, "gid": group_id, "f": favorability, "tr": trust, "lut": last_update_tick},
        )

    # ---------- 记忆宫殿边 ----------

    def add_memory_link(
        self,
        memory_a_id: int,
        memory_b_id: int,
        char_id: int,
        link_type: str = "same_scene",
        link_strength: float = 0.8,
        weight: float = 1.0,
    ) -> None:
        self._db.execute(
            "MERGE (a:MemoryNode {id: $aid})-[r:MemoryLink]->(b:MemoryNode {id: $bid}) "
            "SET r.char_id = $cid, r.link_type = $lt, r.link_strength = $ls, r.weight = $w",
            {"aid": memory_a_id, "bid": memory_b_id, "cid": char_id,
             "lt": link_type, "ls": link_strength, "w": weight},
        )

    # ---------- 10.1 社交接触边 ----------

    def upsert_frequent_contact(
        self,
        char_a_id: int,
        char_b_id: int,
        weight: float = 0.5,
        last_interaction_tick: int = 0,
        interaction_count: int = 1,
    ) -> None:
        """写 A↔B 的日常接触强度（有向，需双向写以支持双向查询）。

        weight 0-1：日常接触强度。由 character_updater 在 tick 中按"本 tick 是否互动"维护：
        互动则 weight 衰减慢（提升），长期不互动则衰减。
        """
        self.add_character_node(char_a_id, "")
        self.add_character_node(char_b_id, "")
        self._db.execute(
            "MERGE (a:CharacterNode {id: $aid})-[r:FrequentContact]->(b:CharacterNode {id: $bid}) "
            "SET r.weight = $w, r.last_interaction_tick = $lit, r.interaction_count = $ic",
            {"aid": char_a_id, "bid": char_b_id, "w": weight,
             "lit": last_interaction_tick, "ic": interaction_count},
        )

    def get_frequent_contacts(self, char_id: int, min_weight: float = 0.1) -> List[Dict[str, Any]]:
        """查某角色的高权重社交接触（传播路径候选）。"""
        return self.query(
            "MATCH (a:CharacterNode {id: $cid})-[r:FrequentContact]->(b:CharacterNode) "
            "WHERE r.weight >= $mw "
            "RETURN b.id AS target_id, b.name AS target_name, "
            "r.weight AS weight, r.last_interaction_tick AS last_tick, r.interaction_count AS count "
            "ORDER BY r.weight DESC",
            {"cid": char_id, "mw": min_weight},
        )

    # ---------- 查询 ----------

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行任意只读 Cypher 查询，返回 dict 列表。

        白名单约束：由调用方保证只传只读 MATCH，API 层会再次校验。
        """
        result = self._db.execute(cypher, params or {})
        cols = result.get_column_names()
        rows: List[Dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            rows.append({cols[i]: row[i] for i in range(len(cols))})
        return rows

    # ---------- 便捷查询 ----------

    def get_views_as(self, observer_id: int, target_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """查 A 的所有主观看法；指定 target_id 则查 A 对 B 的。"""
        if target_id is None:
            return self.query(
                "MATCH (o:CharacterNode {id: $oid})-[v:ViewsAs]->(t:CharacterNode) "
                "RETURN t.id AS target_id, t.name AS target_name, "
                "v.favorability, v.trust, v.fear, v.summary, v.last_update_tick",
                {"oid": observer_id},
            )
        return self.query(
            "MATCH (o:CharacterNode {id: $oid})-[v:ViewsAs]->(t:CharacterNode {id: $tid}) "
            "RETURN t.id AS target_id, t.name AS target_name, "
            "v.favorability, v.trust, v.fear, v.summary, v.last_update_tick",
            {"oid": observer_id, "tid": target_id},
        )

    def get_two_hop_enemies(self, char_id: int) -> List[Dict[str, Any]]:
        """A 的朋友的敌人（2 跳）：A 信任的人（favorability>70）对 C 信任度低（favorability<20）。"""
        return self.query(
            "MATCH (a:CharacterNode {id: $aid})-[v1:ViewsAs]->(f:CharacterNode)-"
            "[v2:ViewsAs]->(enemy:CharacterNode) "
            "WHERE v1.favorability > 70 AND v2.favorability < 20 "
            "RETURN DISTINCT enemy.id AS id, enemy.name AS name, v2.favorability AS enemy_favor",
            {"aid": char_id},
        )

    def expand_memory_palace(self, memory_id: int, depth: int = 3) -> List[Dict[str, Any]]:
        """以某条记忆为中心 BFS 展开关联记忆（depth 跳）。"""
        return self.query(
            "MATCH (m:MemoryNode {id: $mid})-[:MemoryLink*1.." + str(depth) + "]->(related) "
            "RETURN related.id AS memory_id, related.char_id AS char_id, related.depth AS depth",
            {"mid": memory_id},
        )

    def get_event_participants(self, event_id: int) -> List[Dict[str, Any]]:
        """查询某事件的所有参与角色。"""
        return self.query(
            "MATCH (c:CharacterNode)-[r:ParticipatedIn]->(e:EventNode {id: $eid}) "
            "RETURN c.id AS char_id, c.name AS name, r.role AS role, r.depth_hint AS depth_hint",
            {"eid": event_id},
        )


# ============================================================
# 单存档级别的激活图库引用（类似 models._ACTIVE_CONN）
# ============================================================

_ACTIVE_GRAPH: Optional[GraphStore] = None


def set_active_graph(gs: Optional[GraphStore]) -> None:
    global _ACTIVE_GRAPH
    _ACTIVE_GRAPH = gs


def _active_graph() -> GraphStore:
    if _ACTIVE_GRAPH is None:
        raise RuntimeError("无激活图库；请先 connect_for_save")
    return _ACTIVE_GRAPH
