"""src.backend.http.routers.entities — 19 类实体通用 CRUD。

通用端点：
- GET    /api/entities/_slugs
- GET    /api/entities/{slug}?where=&like=&order_by=&limit=&offset=&fields=
- GET    /api/entities/{slug}/{id}
- GET    /api/entities/{slug}/count
- POST   /api/entities/{slug}
- POST   /api/entities/{slug}/_bulk_create
- POST   /api/entities/{slug}/_bulk_update
- POST   /api/entities/{slug}/_bulk_delete
- PATCH  /api/entities/{slug}/{id}
- DELETE /api/entities/{slug}/{id}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.storage import models
from src.backend.storage.connection import SaveManager

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.get("/_slugs")
def list_slugs(sm: SaveManager = Depends(require_active_save)):
    """列出所有实体 slug。"""
    return {"slugs": sorted(models.SLUG_TO_MODEL.keys()), "count": len(models.SLUG_TO_MODEL)}


def _get_model(slug: str):
    m = models.SLUG_TO_MODEL.get(slug)
    if m is None:
        raise HTTPException(404, f"未知实体 slug: {slug}")
    return m


@router.get("/{slug}/count")
def count(
    slug: str,
    where: Optional[str] = Query(None, description="SQL WHERE 片段，使用 ? 占位符"),
    params: Optional[str] = Query(None, description="JSON 数组，与 where 占位符一一对应"),
    sm: SaveManager = Depends(require_active_save),
):
    """统计记录数。"""
    m = _get_model(slug)
    p = json.loads(params) if params else None
    return {"count": m.count(where or "", p)}


@router.get("/{slug}")
def filter(
    slug: str,
    where: Optional[str] = Query(None),
    params: Optional[str] = Query(None),
    like: Optional[str] = Query(None, description="对 name 字段做 LIKE 模糊匹配"),
    order_by: str = Query("id ASC"),
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    fields: Optional[str] = Query(None, description="逗号分隔的返回字段；不传返回全字段"),
    sm: SaveManager = Depends(require_active_save),
):
    """查询列表：精确过滤 + like 模糊 + 排序 + 分页 + 字段裁剪。"""
    m = _get_model(slug)
    where_clause = where or ""
    p: List[Any] = []
    if params:
        p = json.loads(params)
    if like:
        # 默认对 name 字段模糊
        if where_clause:
            where_clause += " AND "
        where_clause += "name LIKE ?"
        p.append(f"%{like}%")
    items = m.list(where=where_clause, params=p, order_by=order_by, limit=limit, offset=offset)
    out = [it.to_dict() for it in items]
    if fields:
        keep = set(fields.split(","))
        keep.add("id")
        out = [{k: v for k, v in d.items() if k in keep} for d in out]
    return {"items": out, "count": len(out), "total": m.count(where_clause, p)}


@router.get("/{slug}/{item_id}")
def get_one(slug: str, item_id: int, sm: SaveManager = Depends(require_active_save)):
    """按 ID 获取。"""
    m = _get_model(slug)
    obj = m.get(item_id)
    if not obj:
        raise HTTPException(404, f"{slug} id={item_id} 不存在")
    return obj.to_dict()


@router.post("/{slug}")
def create_one(slug: str, payload: Dict[str, Any], sm: SaveManager = Depends(require_active_save)):
    """创建单条。"""
    m = _get_model(slug)
    try:
        obj = m.create(**payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return obj.to_dict()


@router.post("/{slug}/_bulk_create")
def bulk_create(slug: str, items: List[Dict[str, Any]],
                sm: SaveManager = Depends(require_active_save)):
    """批量创建。"""
    m = _get_model(slug)
    try:
        objs = m.bulk_create(items)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"created": len(objs), "items": [o.to_dict() for o in objs]}


@router.post("/{slug}/_bulk_update")
def bulk_update(slug: str, updates: List[Dict[str, Any]],
                sm: SaveManager = Depends(require_active_save)):
    """批量更新。每项需带 id。"""
    m = _get_model(slug)
    n = m.bulk_update(updates)
    return {"updated": n}


@router.post("/{slug}/_bulk_delete")
def bulk_delete(slug: str, ids: List[int], sm: SaveManager = Depends(require_active_save)):
    """批量删除。"""
    m = _get_model(slug)
    n = m.bulk_delete(ids)
    return {"deleted": n}


@router.patch("/{slug}/{item_id}")
def update_one(slug: str, item_id: int, payload: Dict[str, Any],
               sm: SaveManager = Depends(require_active_save)):
    """按 ID 更新。"""
    m = _get_model(slug)
    obj = m.update(item_id, **payload)
    if not obj:
        raise HTTPException(404, f"{slug} id={item_id} 不存在")
    return obj.to_dict()


@router.delete("/{slug}/{item_id}")
def delete_one(slug: str, item_id: int, sm: SaveManager = Depends(require_active_save)):
    """按 ID 删除。"""
    m = _get_model(slug)
    if not m.delete(item_id):
        raise HTTPException(404, f"{slug} id={item_id} 不存在")
    return {"deleted": True, "id": item_id}
