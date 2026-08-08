"""src.backend.knowledge.tool — 知识库工具（供 LLM 调用）。

提供 knowledge_search / knowledge_add / knowledge_list_categories 等工具。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import tool, ToolSpec
from src.backend.knowledge.store import KnowledgeStore

KNOWLEDGE_TOOL_NAMES: List[str] = []


@tool(
    name="knowledge_search",
    desc="从知识库检索相关设定（武器/武功/外貌/性格/地点等）",
)
def knowledge_search(
    query: str,
    category_id: int = 0,
    top_k: int = 10,
) -> str:
    """从知识库检索相关设定（武器/武功/外貌/性格/地点等）。

    当需要参考小说设定时使用此工具。例如需要一个仙侠武器，
    可以搜索 "仙侠 武器"，返回匹配的设定条目。

    Args:
        query: 搜索关键词（可以多个词，用空格分隔）
        category_id: 可选，限定分类 ID（0=全部分类）
        top_k: 返回结果数，默认 10

    Returns:
        JSON string with {results: [...], total: int}
    """
    store = KnowledgeStore.instance()
    results = store.search(
        query=query,
        category_id=category_id or None,
        top_k=min(top_k, 30),
        mode="keyword",
    )
    # 精简输出，去掉向量等冗余字段
    simplified = []
    for r in results:
        simplified.append({
            "id": r["id"],
            "title": r["title"],
            "content": r["content"][:300],  # 截断内容
            "keywords": r.get("keywords", []),
            "importance": r.get("importance", 3),
            "score": r.get("score", 0),
        })
    return json.dumps({
        "results": simplified,
        "total": len(simplified),
        "query": query,
    }, ensure_ascii=False)


KNOWLEDGE_TOOL_NAMES.append("knowledge_search")


@tool(
    name="knowledge_add",
    desc="向知识库添加新条目",
)
def knowledge_add(
    title: str,
    content: str,
    category_id: int = 0,
    keywords: str = "[]",
    tags: str = "[]",
    importance: int = 3,
) -> str:
    """向知识库添加新条目。

    当发现有价值的设定、描述、剧情结构时，可以存入知识库供后续参考。

    Args:
        title: 条目标题（简洁明确）
        content: 条目内容（完整描述）
        category_id: 分类 ID（0=其他设定）
        keywords: 关键词列表（JSON 数组字符串，如 ["仙侠","武器"]）
        tags: 标签列表（JSON 数组字符串）
        importance: 重要度 0-5

    Returns:
        JSON string with {success: bool, item_id: int}
    """
    store = KnowledgeStore.instance()
    try:
        kw = json.loads(keywords) if keywords else []
        tg = json.loads(tags) if tags else []
    except (json.JSONDecodeError, TypeError):
        kw = []
        tg = []

    result = store.add_item(
        title=title,
        content=content,
        category_id=category_id or 0,
        keywords=kw,
        tags=tg,
        source="model",
        importance=importance,
    )
    return json.dumps({
        "success": True,
        "item_id": result["id"],
        "message": f"知识库条目「{title}」已添加",
    }, ensure_ascii=False)


KNOWLEDGE_TOOL_NAMES.append("knowledge_add")


@tool(
    name="knowledge_list_categories",
    desc="列出知识库中的所有分类",
)
def knowledge_list_categories() -> str:
    """列出知识库中的所有分类。

    Returns:
        JSON string with {categories: [...]}
    """
    store = KnowledgeStore.instance()
    cats = store.list_categories()
    return json.dumps({
        "categories": [
            {"id": c["id"], "name": c["name"], "description": c.get("description", ""), "item_count": c.get("item_count", 0)}
            for c in cats
        ],
    }, ensure_ascii=False)


KNOWLEDGE_TOOL_NAMES.append("knowledge_list_categories")


@tool(
    name="knowledge_get_random",
    desc="从知识库随机获取 N 个条目",
)
def knowledge_get_random(
    category_id: int = 0,
    count: int = 5,
) -> str:
    """从知识库随机获取 N 个条目。

    用于获取灵感或随机参考。

    Args:
        category_id: 分类 ID（0=全部分类）
        count: 获取数量，默认 5

    Returns:
        JSON string with {items: [...]}
    """
    store = KnowledgeStore.instance()
    items = store.get_random_items(
        category_id=category_id or None,
        count=min(count, 20),
    )
    simplified = []
    for r in items:
        simplified.append({
            "id": r["id"],
            "title": r["title"],
            "content": r["content"][:200],
            "importance": r.get("importance", 3),
        })
    return json.dumps({"items": simplified}, ensure_ascii=False)


KNOWLEDGE_TOOL_NAMES.append("knowledge_get_random")


__all__ = [
    "KNOWLEDGE_TOOL_NAMES",
    "knowledge_search",
    "knowledge_add",
    "knowledge_list_categories",
    "knowledge_get_random",
]
