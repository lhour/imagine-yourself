"""src.backend.knowledge — 独立知识库模块。

提供 SQLite 存储、关键词/向量检索、CRUD 接口。
"""

from src.backend.knowledge.store import KnowledgeStore  # noqa: F401
from src.backend.knowledge.tool import (  # noqa: F401
    KNOWLEDGE_TOOL_NAMES,
    knowledge_search,
    knowledge_add,
    knowledge_list_categories,
    knowledge_get_random,
)
