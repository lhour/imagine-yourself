"""src.backend.agent.tool.entity_tools — 实体 CRUD 工具工厂。

按 v3 设计：每个实体自动生成 5 个工具：
  {slug}_filter / {slug}_bulk_create / {slug}_bulk_update / {slug}_bulk_delete / {slug}_count

由 STORAGE_TOOLS 列表暴露给 ToolManager。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.storage import models
from src.backend.storage.models import BaseEntity


def _make_filter_tool(model_cls: type) -> None:
    slug = model_cls.SLUG
    name = f"{slug}_filter"

    @tool(
        name=name,
        desc=f"过滤查询{model_cls.TABLE}记录，支持 where/params/like/order_by/limit/offset",
        params={
            "type": "object",
            "properties": {
                "where": {"type": "string", "description": "SQL WHERE 片段（用 ? 占位符）"},
                "params": {"type": "array", "description": "与 where 占位符一一对应的值"},
                "like": {"type": "string", "description": "对 name 字段模糊匹配"},
                "order_by": {"type": "string", "description": "排序，如 'id ASC'"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
        },
    )
    def _filter(
        where: str = "",
        params: List[Any] = None,
        like: str = "",
        order_by: str = "id ASC",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        m = model_cls
        w = where or ""
        p: List[Any] = params or []
        if like:
            if w:
                w += " AND "
            w += "name LIKE ?"
            p.append(f"%{like}%")
        items = m.list(where=w, params=p, order_by=order_by, limit=limit, offset=offset)
        return {"items": [i.to_dict() for i in items], "count": len(items)}

    _filter.__name__ = name


def _make_count_tool(model_cls: type) -> None:
    slug = model_cls.SLUG
    name = f"{slug}_count"

    @tool(
        name=name,
        desc=f"统计{model_cls.TABLE}记录数",
        params={
            "type": "object",
            "properties": {
                "where": {"type": "string"},
                "params": {"type": "array"},
            },
        },
    )
    def _count(where: str = "", params: List[Any] = None) -> dict:
        return {"count": model_cls.count(where, params or [])}

    _count.__name__ = name


def _make_bulk_create_tool(model_cls: type) -> None:
    slug = model_cls.SLUG
    name = f"{slug}_bulk_create"

    @tool(
        name=name,
        desc=f"批量创建{model_cls.TABLE}记录（传 1 条即单创建）",
        params={
            "type": "object",
            "properties": {
                "items": {"type": "array", "description": "字段 dict 数组"},
            },
            "required": ["items"],
        },
    )
    def _bulk_create(items: List[Dict[str, Any]]) -> dict:
        try:
            objs = model_cls.bulk_create(items)
            return {"created": len(objs), "items": [o.to_dict() for o in objs]}
        except (ValueError, Exception) as e:
            return {"error": f"{type(e).__name__}: {e}"}

    _bulk_create.__name__ = name


def _make_bulk_update_tool(model_cls: type) -> None:
    slug = model_cls.SLUG
    name = f"{slug}_bulk_update"

    @tool(
        name=name,
        desc=f"批量更新{model_cls.TABLE}记录（每项需带 id）",
        params={
            "type": "object",
            "properties": {
                "updates": {"type": "array", "description": "[{id: 1, field: val}, ...]"},
            },
            "required": ["updates"],
        },
    )
    def _bulk_update(updates: List[Dict[str, Any]]) -> dict:
        return {"updated": model_cls.bulk_update(updates)}

    _bulk_update.__name__ = name


def _make_bulk_delete_tool(model_cls: type) -> None:
    slug = model_cls.SLUG
    name = f"{slug}_bulk_delete"

    @tool(
        name=name,
        desc=f"批量删除{model_cls.TABLE}记录（按 ID）",
        params={
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "integer"}}},
            "required": ["ids"],
        },
    )
    def _bulk_delete(ids: List[int]) -> dict:
        return {"deleted": model_cls.bulk_delete(ids)}

    _bulk_delete.__name__ = name


def register_all_entity_tools() -> List[str]:
    """注册所有实体的 CRUD 工具，返回工具名列表。"""
    names: List[str] = []
    for model_cls in models.ENTITIES:
        for maker in [
            _make_filter_tool, _make_count_tool, _make_bulk_create_tool,
            _make_bulk_update_tool, _make_bulk_delete_tool,
        ]:
            maker(model_cls)
            names.append(f"{model_cls.SLUG}_{maker.__name__.split('_make_')[1]}")
    return names


# 模块 import 时自动注册
ENTITY_TOOL_NAMES = register_all_entity_tools()


# 工具名清单（供 skill 引用）
STORAGE_TOOLS = ENTITY_TOOL_NAMES
