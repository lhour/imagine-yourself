"""src.backend.http.routers.knowledge — 知识库管理 API。

提供分类管理、条目 CRUD、检索、统计等接口。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.knowledge.store import KnowledgeStore

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _get_store() -> KnowledgeStore:
    """获取知识库存储实例（每次请求创建新连接以避免线程问题）。"""
    return KnowledgeStore()  # 每次创建新实例，内部会初始化新的 SQLite 连接


# ============ 请求模型 ============

class CategoryCreateReq(BaseModel):
    name: str
    description: str = ""


class CategoryUpdateReq(BaseModel):
    name: str
    description: str = ""


class ItemCreateReq(BaseModel):
    title: str
    content: str
    category_id: int = 0
    keywords: List[str] = []
    tags: List[str] = []
    source: str = "manual"
    importance: int = 3


class ItemUpdateReq(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category_id: Optional[int] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    importance: Optional[int] = None


class SearchReq(BaseModel):
    query: str
    category_id: int = 0
    top_k: int = 10
    mode: str = "keyword"


# ============ 分类管理 ============

@router.get("/categories")
def list_categories():
    """列出所有分类。"""
    store = _get_store()
    return {"categories": store.list_categories()}


@router.post("/categories")
def create_category(req: CategoryCreateReq):
    """创建新分类。"""
    store = _get_store()
    return store.create_category(req.name, req.description)


@router.put("/categories/{category_id}")
def update_category(category_id: int, req: CategoryUpdateReq):
    """更新分类。"""
    store = _get_store()
    ok = store.update_category(category_id, req.name, req.description)
    if not ok:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"success": True}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int):
    """删除分类。"""
    store = _get_store()
    ok = store.delete_category(category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"success": True}


# ============ 条目管理 ============

@router.get("/items")
def list_items(
    category_id: int = 0,
    page: int = 1,
    page_size: int = 20,
):
    """分页列出条目。"""
    store = _get_store()
    return store.list_items(
        category_id=category_id or None,
        page=page,
        page_size=page_size,
    )


@router.get("/items/{item_id}")
def get_item(item_id: int):
    """获取单个条目。"""
    store = _get_store()
    item = store.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return item


@router.post("/items")
def create_item(req: ItemCreateReq):
    """创建新条目。"""
    store = _get_store()
    return store.add_item(
        title=req.title,
        content=req.content,
        category_id=req.category_id,
        keywords=req.keywords,
        tags=req.tags,
        source=req.source,
        importance=req.importance,
    )


@router.put("/items/{item_id}")
def update_item(item_id: int, req: ItemUpdateReq):
    """更新条目。"""
    store = _get_store()
    ok = store.update_item(
        item_id,
        title=req.title,
        content=req.content,
        category_id=req.category_id,
        keywords=req.keywords,
        tags=req.tags,
        importance=req.importance,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="条目不存在或无更新")
    return {"success": True}


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    """删除条目。"""
    store = _get_store()
    ok = store.delete_item(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"success": True}


# ============ 检索 ============

@router.post("/search")
def search(req: SearchReq):
    """检索知识库。"""
    store = _get_store()
    results = store.search(
        query=req.query,
        category_id=req.category_id or None,
        top_k=min(req.top_k, 30),
        mode=req.mode,
    )
    return {"results": results, "total": len(results)}


@router.get("/items/random")
def get_random(
    category_id: int = 0,
    count: int = 5,
):
    """随机获取条目。"""
    store = _get_store()
    items = store.get_random_items(
        category_id=category_id or None,
        count=min(count, 20),
    )
    return {"items": items}


# ============ 统计 ============

@router.get("/stats")
def get_stats():
    """获取知识库统计。"""
    store = _get_store()
    return store.get_stats()


# ============ 批量导入 ============

@router.post("/items/batch")
def batch_import(items: List[ItemCreateReq]):
    """批量导入条目。"""
    store = _get_store()
    created = []
    for item in items:
        result = store.add_item(
            title=item.title,
            content=item.content,
            category_id=item.category_id,
            keywords=item.keywords,
            tags=item.tags,
            source=item.source,
            importance=item.importance,
        )
        created.append(result)
    return {"created": len(created), "items": created}
