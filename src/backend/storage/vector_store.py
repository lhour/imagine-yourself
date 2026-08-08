"""src.backend.storage.vector_store — sqlite-vec 向量库封装。

挂载在主 SQLite 内的虚拟表，提供记忆/事件/设定的 ANN 语义召回。

虚拟表：
  vec_memories   (memory_id, embedding FLOAT[768])
  vec_events     (event_id,   embedding FLOAT[768])
  vec_settings   (setting_id, embedding FLOAT[768])

维度由 embedding 模型决定（默认 768，可在 init_database 时覆盖）。

用法：
  vs = VectorStore.load(conn)     # 从已有 sqlite3.Connection 加载扩展 + 建虚拟表
  vs.upsert_memory(memory_id, text)
  ids = vs.search_memories(query_text, top_k=10, char_id=1)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
from typing import Any, Dict, List, Optional


def _pack_vec(vec: List[float]) -> bytes:
    """把 float 列表打包为 sqlite-vec 期望的 float32 little-endian blob。

    注意：不能用 sqlite3.serialize —— 那是 Python 3.11+ 用于序列化整个数据库的 API，
    接收 Connection 而非 list，传 list 会抛 AttributeError/TypeError。
    """
    return struct.pack(f"{len(vec)}f", *vec)

try:
    import sqlite_vec  # type: ignore[import-not-found]
    _SQLITE_VEC_AVAILABLE = True
except ImportError:  # pragma: no cover - 可选依赖
    sqlite_vec = None  # type: ignore[assignment]
    _SQLITE_VEC_AVAILABLE = False


DEFAULT_DIM = 768


class VectorStoreUnavailable(RuntimeError):
    """sqlite-vec 未安装时抛出。"""


class VectorStore:
    """sqlite-vec 扩展封装（依附于关系库的 sqlite3.Connection）。

    当 sqlite_vec 不可用时，所有方法都会抛出 VectorStoreUnavailable，
    便于上层降级为纯关键词 + 关系库的混合检索。
    """

    def __init__(self, conn: sqlite3.Connection, dim: int = DEFAULT_DIM) -> None:
        self._conn = conn
        self._dim = dim
        self._available = _SQLITE_VEC_AVAILABLE
        if self._available:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)

    def _require_vec(self) -> None:
        if not self._available:
            raise VectorStoreUnavailable("sqlite-vec 不可用，请先 pip install sqlite-vec")

    # ---------- 初始化 ----------

    def init_database(self) -> None:
        """幂等：创建 vec_memories / vec_events / vec_settings 三张虚拟表。"""
        if not self._available:
            return  # 不可用时静默跳过
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories "
            f"USING vec0(memory_id INTEGER PRIMARY KEY, embedding FLOAT[{self._dim}])"
        )
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_events "
            f"USING vec0(event_id INTEGER PRIMARY KEY, embedding FLOAT[{self._dim}])"
        )
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_settings "
            f"USING vec0(setting_id INTEGER PRIMARY KEY, embedding FLOAT[{self._dim}])"
        )
        self._conn.commit()

    # ---------- Embedding 接口 ----------

    def _embed(self, text: str) -> List[float]:
        """把文本转为 embedding 向量。

        默认实现：复用 deepseek_client 的 embedding 接口；若失败则生成伪随机向量
        （仅便于开发阶段调试）。生产环境必须覆盖此方法。
        """
        # 延迟 import 避免循环依赖
        try:
            from src.backend import deepseek_client
            vec = deepseek_client.embed(text)
            if isinstance(vec, list) and vec:
                # 若外部 embedding 维度与本实例配置不一致，记录告警但不阻断
                if len(vec) != self._dim:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        "embed 维度 mismatch: got %d, expected %d; 自动截断到目标维度",
                        len(vec), self._dim,
                    )
                    vec = vec[: self._dim]
                return [float(v) for v in vec]
        except Exception:
            pass
        # 伪随机 fallback（仅用于 mock 模式或失败降级）
        import hashlib
        h = hashlib.md5(text.encode()).digest()
        vec: List[float] = []
        while len(vec) < self._dim:
            h = hashlib.md5(h).digest()
            vec.extend(((b / 255.0) - 0.5) * 2.0 for b in h)
        return vec[: self._dim]

    def set_embed_fn(self, fn) -> None:
        """外部注入自定义 embedding 函数：fn(text: str) -> List[float]。"""
        self._embed = fn  # type: ignore[assignment]

    # ---------- 写入 ----------

    def upsert_memory(self, memory_id: int, text: str) -> int:
        """生成 embedding 并写入 vec_memories，返回本次写入的 rowid（= memory_id）。"""
        self._require_vec()
        vec = self._embed(text)
        blob = _pack_vec(vec)
        self._conn.execute(
            "INSERT OR REPLACE INTO vec_memories (memory_id, embedding) VALUES (?, ?)",
            [memory_id, blob],
        )
        self._conn.commit()
        return memory_id

    def upsert_event(self, event_id: int, text: str) -> int:
        self._require_vec()
        vec = self._embed(text)
        blob = _pack_vec(vec)
        self._conn.execute(
            "INSERT OR REPLACE INTO vec_events (event_id, embedding) VALUES (?, ?)",
            [event_id, blob],
        )
        self._conn.commit()
        return event_id

    def upsert_setting(self, setting_id: int, text: str) -> int:
        self._require_vec()
        vec = self._embed(text)
        blob = _pack_vec(vec)
        self._conn.execute(
            "INSERT OR REPLACE INTO vec_settings (setting_id, embedding) VALUES (?, ?)",
            [setting_id, blob],
        )
        self._conn.commit()
        return setting_id

    # ---------- 删除 ----------

    def delete_memory(self, memory_id: int) -> None:
        self._conn.execute("DELETE FROM vec_memories WHERE memory_id = ?", [memory_id])
        self._conn.commit()

    def delete_event(self, event_id: int) -> None:
        self._conn.execute("DELETE FROM vec_events WHERE event_id = ?", [event_id])
        self._conn.commit()

    # ---------- 检索 ----------

    def search_memories(
        self,
        query_text: str,
        top_k: int = 10,
        char_id: Optional[int] = None,
        depth_weight: bool = True,
    ) -> List[Dict[str, Any]]:
        """语义召回角色记忆。

        返回字段：memory_id, char_id, depth, correctness, score（负距离，越大越好）。
        若 depth_weight=True，返回列表已按 score*depth 加权排序。
        """
        self._require_vec()
        q_vec = self._embed(query_text)
        q_blob = _pack_vec(q_vec)

        sql = """
            SELECT m.id AS memory_id, m.char_id, m.depth, m.correctness,
                   v.distance
            FROM vec_memories v
            JOIN memories m ON m.id = v.memory_id
            WHERE v.matching = ?
        """
        params: List[Any] = [q_blob]
        if char_id is not None:
            sql += " AND m.char_id = ?"
            params.append(char_id)
        sql += f" ORDER BY v.distance LIMIT {top_k * 2}"  # 多取一些供加权

        cur = self._conn.execute(sql, params)
        rows: List[Dict[str, Any]] = []
        for r in cur:
            d = r["distance"]
            score = -d  # 负距离作相似度
            depth = r["depth"] or 3
            rows.append({
                "memory_id": r["memory_id"],
                "char_id": r["char_id"],
                "depth": depth,
                "correctness": r["correctness"],
                "distance": d,
                "score": score,
                "weighted_score": score * (depth / 5.0) if depth_weight else score,
            })
        if depth_weight:
            rows.sort(key=lambda x: x["weighted_score"], reverse=True)
        return rows[:top_k]

    def search_events(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        q_vec = self._embed(query_text)
        q_blob = _pack_vec(q_vec)
        cur = self._conn.execute(
            "SELECT e.id AS event_id, e.tick_num, v.distance "
            "FROM vec_events v JOIN events e ON e.id = v.event_id "
            "WHERE v.matching = ? ORDER BY v.distance LIMIT ?",
            [q_blob, top_k],
        )
        return [dict(r) for r in cur]

    def search_settings(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        q_vec = self._embed(query_text)
        q_blob = _pack_vec(q_vec)
        cur = self._conn.execute(
            "SELECT s.id AS setting_id, s.title, v.distance "
            "FROM vec_settings v JOIN settings s ON s.id = v.setting_id "
            "WHERE v.matching = ? ORDER BY v.distance LIMIT ?",
            [q_blob, top_k],
        )
        return [dict(r) for r in cur]

    # ---------- 与关系库协作的混合检索 ----------

    def search_memories_mixed(
        self,
        query_text: str,
        char_id: int,
        person_filter: Optional[List[int]] = None,
        location_filter: Optional[List[int]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """语义 + 精确混合检索：先按向量召回，再用 person_ids/location_ids JSON 数组精确过滤。"""
        semantic = self.search_memories(query_text, top_k=top_k * 3, char_id=char_id)
        if not person_filter and not location_filter:
            return semantic[:top_k]

        filtered: List[Dict[str, Any]] = []
        for row in semantic:
            mem_id = row["memory_id"]
            mem_row = self._conn.execute(
                "SELECT person_ids, location_ids FROM memories WHERE id = ?", [mem_id]
            ).fetchone()
            if not mem_row:
                continue
            person_ids = json.loads(mem_row["person_ids"] or "[]")
            location_ids = json.loads(mem_row["location_ids"] or "[]")

            ok = True
            if person_filter:
                if not any(pid in person_ids for pid in person_filter):
                    ok = False
            if location_filter and ok:
                if not any(lid in location_ids for lid in location_filter):
                    ok = False
            if ok:
                filtered.append(row)
            if len(filtered) >= top_k:
                break
        return filtered


# ============================================================
# 模块级便捷函数
# ============================================================


def load_for_connection(conn: sqlite3.Connection, dim: int = DEFAULT_DIM) -> VectorStore:
    """从已有 sqlite3.Connection 加载向量扩展并返回 VectorStore 实例。"""
    return VectorStore(conn, dim=dim)
