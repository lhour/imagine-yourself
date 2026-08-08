"""src.backend.knowledge — 独立知识库模块。

提供：
- SQLite 存储（knowledge.db）
- 关键词检索 + 向量检索
- 分页/随机输出
- 分类管理
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backend.env import BACKEND_DIR

KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_DIR", str(BACKEND_DIR / "knowledge")))
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DB = KNOWLEDGE_DIR / "knowledge.db"

SCHEMA: List[Tuple[str, List[str], List[str]]] = [
    ("kb_category", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL UNIQUE",
        "description TEXT",
        "item_count INTEGER DEFAULT 0",
        "created_at TEXT NOT NULL",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_kb_cat_name ON kb_category(name)",
    ]),

    ("knowledge_item", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "category_id INTEGER REFERENCES kb_category(id)",
        "title TEXT NOT NULL",
        "content TEXT NOT NULL",
        "keywords TEXT DEFAULT '[]'",         # JSON 数组，用于关键词匹配
        "tags TEXT DEFAULT '[]'",              # JSON 数组，标签
        "source TEXT DEFAULT 'manual'",        # manual/script/api
        "importance INTEGER DEFAULT 3",         # 0-5
        "vector BLOB",                          # 可选的 embedding
        "vector_model TEXT",
        "created_at TEXT NOT NULL",
        "updated_at TEXT NOT NULL",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_kb_item_cat ON knowledge_item(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_kb_item_title ON knowledge_item(title)",
        "CREATE INDEX IF NOT EXISTS idx_kb_item_importance ON knowledge_item(importance)",
    ]),

    ("kb_operation_log", [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "op_type TEXT NOT NULL",              # search/add/update/delete
        "query_text TEXT",
        "item_id INTEGER",
        "results_count INTEGER DEFAULT 0",
        "actor TEXT DEFAULT 'model'",
        "created_at TEXT NOT NULL",
    ], [
        "CREATE INDEX IF NOT EXISTS idx_kb_op_type ON kb_operation_log(op_type)",
        "CREATE INDEX IF NOT EXISTS idx_kb_op_time ON kb_operation_log(created_at)",
    ]),
]


class KnowledgeStore:
    """独立知识库存储与检索引擎。"""

    _instance: Optional["KnowledgeStore"] = None

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or KNOWLEDGE_DB
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    @classmethod
    def instance(cls) -> "KnowledgeStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---------- 数据库初始化 ----------

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        for table_name, columns, indexes in SCHEMA:
            cols_def = ", ".join(columns)
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_def})")
            for idx_sql in indexes:
                self._conn.execute(idx_sql)
        self._conn.commit()
        self._ensure_default_categories()

    def _ensure_default_categories(self) -> None:
        """确保存在默认分类。"""
        default_cats = [
            ("武器法宝", "仙侠/玄幻类武器、法宝、灵器等设定"),
            ("武功武学", "各类武学、心法、招式等设定"),
            ("人物外貌", "角色外貌描写参考（外貌特征、服饰、气质）"),
            ("人物性格", "角色性格类型、心理特征描写参考"),
            ("场景地点", "各类场景、地点、建筑描写参考"),
            ("种族生物", "各类种族、生物、怪物设定"),
            ("势力组织", "各类门派、家族、组织设定"),
            ("剧情套路", "常见剧情桥段、冲突结构参考"),
            ("物品道具", "日常物品、特殊道具等设定"),
            ("其他设定", "其他杂项设定"),
        ]
        for name, desc in default_cats:
            exists = self._conn.execute(
                "SELECT 1 FROM kb_category WHERE name = ?", [name]
            ).fetchone()
            if not exists:
                self._conn.execute(
                    "INSERT INTO kb_category (name, description, created_at) VALUES (?, ?, ?)",
                    [name, desc, time.strftime("%Y-%m-%dT%H:%M:%S")]
                )
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---------- 分类管理 ----------

    def list_categories(self) -> List[Dict[str, Any]]:
        """列出所有分类。"""
        rows = self._conn.execute(
            "SELECT * FROM kb_category ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def create_category(self, name: str, description: str = "") -> Dict[str, Any]:
        """创建新分类。"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        cur = self._conn.execute(
            "INSERT INTO kb_category (name, description, created_at) VALUES (?, ?, ?)",
            [name, description, now]
        )
        self._conn.commit()
        return {"id": cur.lastrowid, "name": name, "description": description}

    def update_category(self, category_id: int, name: str, description: str = "") -> bool:
        """更新分类。"""
        self._conn.execute(
            "UPDATE kb_category SET name = ?, description = ? WHERE id = ?",
            [name, description, category_id]
        )
        self._conn.commit()
        return True

    def delete_category(self, category_id: int) -> bool:
        """删除分类（同时删除该分类下的所有条目）。"""
        self._conn.execute("DELETE FROM knowledge_item WHERE category_id = ?", [category_id])
        self._conn.execute("DELETE FROM kb_category WHERE id = ?", [category_id])
        self._conn.commit()
        return True

    # ---------- 条目管理 ----------

    def add_item(
        self,
        title: str,
        content: str,
        category_id: int = 0,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source: str = "manual",
        importance: int = 3,
    ) -> Dict[str, Any]:
        """添加知识库条目（自动生成 embedding）。"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        kw_json = json.dumps(keywords or [], ensure_ascii=False)
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        # 生成 embedding
        vector_blob = None
        vector_model = None
        try:
            from src.backend.deepseek_client import embed
            import struct
            text = f"{title} {content}"
            vec = embed(text)
            if vec:
                vector_blob = struct.pack(f"{len(vec)}f", *vec)
                vector_model = "deepseek-v4-flash"
        except Exception:
            pass

        # category_id=0 表示未分类，存为 NULL
        cat_val = category_id if category_id and category_id > 0 else None

        cur = self._conn.execute(
            "INSERT INTO knowledge_item (category_id, title, content, keywords, tags, "
            "source, importance, vector, vector_model, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [cat_val, title, content, kw_json, tags_json, source, importance,
             vector_blob, vector_model, now, now]
        )
        item_id = cur.lastrowid
        self._conn.commit()

        # 更新分类计数（仅当有有效分类时）
        if cat_val:
            self._update_category_count(cat_val)

        self._log_operation("add", item_id=item_id)
        return {"id": item_id, "title": title, "has_vector": vector_blob is not None}

    def update_item(
        self,
        item_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category_id: Optional[int] = None,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """更新知识库条目。"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        updates: List[str] = []
        params: List[Any] = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category_id is not None:
            updates.append("category_id = ?")
            # category_id=0 表示移至未分类
            cat_val = category_id if category_id > 0 else None
            params.append(cat_val)
        if keywords is not None:
            updates.append("keywords = ?")
            params.append(json.dumps(keywords, ensure_ascii=False))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(now)
        params.append(item_id)

        self._conn.execute(
            f"UPDATE knowledge_item SET {', '.join(updates)} WHERE id = ?",
            params
        )
        self._conn.commit()

        # 更新分类计数
        item = self.get_item(item_id)
        if item and item.get("category_id"):
            self._update_category_count(item["category_id"])

        self._log_operation("update", item_id=item_id)
        return True

    def delete_item(self, item_id: int) -> bool:
        """删除知识库条目。"""
        item = self.get_item(item_id)
        self._conn.execute("DELETE FROM knowledge_item WHERE id = ?", [item_id])
        self._conn.commit()
        if item and item.get("category_id"):
            self._update_category_count(item["category_id"])
        self._log_operation("delete", item_id=item_id)
        return True

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """获取单个条目。"""
        row = self._conn.execute(
            "SELECT * FROM knowledge_item WHERE id = ?", [item_id]
        ).fetchone()
        if row:
            item = dict(row)
            try:
                item["keywords"] = json.loads(item.get("keywords", "[]") or "[]")
            except Exception:
                item["keywords"] = []
            try:
                item["tags"] = json.loads(item.get("tags", "[]") or "[]")
            except Exception:
                item["tags"] = []
            item.pop("vector", None)
            item.pop("vector_model", None)
            return item
        return None

    def list_items(
        self,
        category_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页列出条目。

        category_id=None 或 0: 返回所有条目（含未分类）
        category_id>0: 仅返回指定分类的条目
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        sql = "SELECT * FROM knowledge_item WHERE 1=1"
        count_sql = "SELECT COUNT(*) as cnt FROM knowledge_item WHERE 1=1"
        params: List[Any] = []

        if category_id is not None and category_id > 0:
            sql += " AND category_id = ?"
            count_sql += " AND category_id = ?"
            params.append(category_id)

        total = self._conn.execute(count_sql, params).fetchone()["cnt"]
        total_pages = max(1, (total + page_size - 1) // page_size)

        sql += " ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?"
        rows = self._conn.execute(sql, params + [page_size, offset]).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            item["keywords"] = json.loads(item.get("keywords", "[]") or "[]")
            item["tags"] = json.loads(item.get("tags", "[]") or "[]")
            # 排除向量二进制数据，避免 JSON 序列化失败
            item.pop("vector", None)
            item.pop("vector_model", None)
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_random_items(
        self,
        category_id: Optional[int] = None,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """随机获取 N 个条目。"""
        count = max(1, min(count, 50))
        sql = "SELECT * FROM knowledge_item WHERE 1=1"
        params: List[Any] = []
        if category_id is not None and category_id > 0:
            sql += " AND category_id = ?"
            params.append(category_id)
        sql += " ORDER BY RANDOM() LIMIT ?"
        rows = self._conn.execute(sql, params + [count]).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            item["keywords"] = json.loads(item.get("keywords", "[]") or "[]")
            item["tags"] = json.loads(item.get("tags", "[]") or "[]")
            item.pop("vector", None)
            item.pop("vector_model", None)
            items.append(item)
        return items

    # ---------- 检索 ----------

    def search(
        self,
        query: str,
        category_id: Optional[int] = None,
        top_k: int = 10,
        mode: str = "keyword",
    ) -> List[Dict[str, Any]]:
        """检索知识库。

        Args:
            query: 查询文本
            category_id: 限定分类
            top_k: 返回数量
            mode: keyword（关键词匹配）/ vector（向量检索）/ hybrid（混合检索）

        Returns:
            匹配条目列表，含 score 字段
        """
        query = query.strip()
        if not query:
            return []

        results: List[Dict[str, Any]] = []

        if mode == "vector":
            results = self._vector_search(query, category_id, top_k)
        elif mode == "hybrid":
            keyword_results = self._keyword_search(query, category_id, top_k)
            vector_results = self._vector_search(query, category_id, top_k)
            # 混合：合并结果，按分数排序
            merged: Dict[int, Dict[str, Any]] = {}
            for r in keyword_results:
                r["score"] = r.get("score", 0) * 0.6  # 关键词权重 0.6
                merged[r["id"]] = r
            for r in vector_results:
                r["score"] = r.get("score", 0) * 0.4  # 向量权重 0.4
                if r["id"] in merged:
                    merged[r["id"]]["score"] += r["score"]
                else:
                    merged[r["id"]] = r
            results = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]
        else:  # keyword
            results = self._keyword_search(query, category_id, top_k)

        self._log_operation("search", query_text=query, results_count=len(results))
        return results

    def _vector_search(
        self,
        query: str,
        category_id: Optional[int],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索。"""
        try:
            from src.backend.deepseek_client import embed
            import struct
            import math

            query_vec = embed(query)
            if not query_vec:
                return []

            # 获取所有有向量的条目
            conditions = ["vector IS NOT NULL"]
            params: List[Any] = []
            if category_id is not None and category_id > 0:
                conditions.append("category_id = ?")
                params.append(category_id)

            where_clause = " AND ".join(conditions)
            rows = self._conn.execute(
                f"SELECT * FROM knowledge_item WHERE {where_clause}",
                params
            ).fetchall()

            # 计算余弦相似度
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for r in rows:
                item = dict(r)
                if item["vector"]:
                    stored_vec = list(struct.unpack(f"{len(item['vector'])//4}f", item["vector"]))
                    # 余弦相似度
                    dot = sum(a * b for a, b in zip(query_vec, stored_vec))
                    norm_a = math.sqrt(sum(x * x for x in query_vec))
                    norm_b = math.sqrt(sum(x * x for x in stored_vec))
                    if norm_a > 0 and norm_b > 0:
                        similarity = dot / (norm_a * norm_b)
                        scored.append((similarity, item))

            # 排序取 top_k
            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, item in scored[:top_k]:
                item["score"] = round(score * 100, 2)  # 转换为 0-100 分
                item["keywords"] = json.loads(item.get("keywords", "[]"))
                item["tags"] = json.loads(item.get("tags", "[]"))
                # 清除向量数据，避免返回过大
                item.pop("vector", None)
                results.append(item)

            return results
        except Exception:
            return []

    def _keyword_search(
        self,
        query: str,
        category_id: Optional[int],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """关键词匹配检索。"""
        # 分词：按空格和标点拆分
        terms = [t.strip() for t in query.replace(",", " ").replace("，", " ").split() if t.strip()]
        if not terms:
            terms = [query]

        # 构建 WHERE 子句：title LIKE + content LIKE + keywords 包含
        conditions = []
        params: List[Any] = []

        if category_id is not None and category_id > 0:
            conditions.append("category_id = ?")
            params.append(category_id)

        # 每个 term 生成 OR 条件
        term_conditions = []
        for term in terms:
            like_pattern = f"%{term}%"
            term_conditions.extend([
                "title LIKE ?",
                "content LIKE ?",
                "keywords LIKE ?",
                "tags LIKE ?",
            ])
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        if term_conditions:
            conditions.append("(" + " OR ".join(term_conditions) + ")")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = self._conn.execute(
            f"SELECT * FROM knowledge_item WHERE {where_clause} "
            f"ORDER BY importance DESC, created_at DESC LIMIT ?",
            params + [top_k * 3]  # 多取一些用于去重和评分
        ).fetchall()

        # 评分：根据匹配位置加权
        scored: List[Tuple[float, Dict[str, Any]]] = []
        seen_ids: set = set()

        for r in rows:
            item = dict(r)
            if item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])

            title_lower = item["title"].lower()
            content_lower = item["content"].lower()
            kw_str = " ".join(json.loads(item.get("keywords", "[]"))).lower()

            score = 0.0
            for term in terms:
                term_lower = term.lower()
                if term_lower in title_lower:
                    score += 10.0  # 标题匹配权重高
                if term_lower in kw_str:
                    score += 5.0
                if term_lower in content_lower:
                    score += 2.0

            score += item.get("importance", 3) * 0.5
            scored.append((score, item))

        # 排序取 top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:top_k]:
            item["score"] = round(score, 2)
            item["keywords"] = json.loads(item.get("keywords", "[]"))
            item["tags"] = json.loads(item.get("tags", "[]"))
            results.append(item)

        return results

    # ---------- 辅助方法 ----------

    def _update_category_count(self, category_id: int) -> None:
        """更新分类的条目计数。"""
        count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_item WHERE category_id = ?",
            [category_id]
        ).fetchone()["cnt"]
        self._conn.execute(
            "UPDATE kb_category SET item_count = ? WHERE id = ?",
            [count, category_id]
        )
        self._conn.commit()

    def _log_operation(
        self,
        op_type: str,
        item_id: Optional[int] = None,
        query_text: str = "",
        results_count: int = 0,
        actor: str = "model",
    ) -> None:
        """记录操作日志。"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._conn.execute(
            "INSERT INTO kb_operation_log (op_type, query_text, item_id, results_count, actor, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [op_type, query_text, item_id, results_count, actor, now]
        )
        self._conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息。"""
        total_items = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_item"
        ).fetchone()["cnt"]
        total_cats = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_category"
        ).fetchone()["cnt"]
        recent_searches = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM kb_operation_log WHERE op_type = 'search'"
        ).fetchone()["cnt"]

        return {
            "total_items": total_items,
            "total_categories": total_cats,
            "total_searches": recent_searches,
            "db_size_bytes": self._db_path.stat().st_size if self._db_path.exists() else 0,
        }
