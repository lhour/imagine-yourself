"""src.backend.http.routers/v5 — v5 新功能路由（玩法选项 + 操作日志 + 配额查询）。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save

router = APIRouter(prefix="/api/v5", tags=["v5"])


# ============ 玩法选项 ============

class GameplayOptionsUpdateReq(BaseModel):
    options: Dict[str, Any]


class GameplayOptionsPatchReq(BaseModel):
    patch: Dict[str, Any]


@router.get("/gameplay_options")
def get_gameplay_options(sm=Depends(require_active_save)):
    """获取当前存档的玩法选项（含默认值合并）。"""
    options = sm.get_gameplay_options()
    # 附带配额使用概况
    from src.backend.agent.entity_quota import EntityQuotaChecker
    meta = sm.get_meta()
    checker = EntityQuotaChecker(sm)
    usage = checker.get_usage_summary(options, meta.get("tick_num", 0))
    return {
        "gameplay_options": options,
        "quota_usage": usage,
    }


@router.put("/gameplay_options")
def set_gameplay_options(req: GameplayOptionsUpdateReq, sm=Depends(require_active_save)):
    """完整覆盖玩法选项。"""
    result = sm.set_gameplay_options(req.options)
    return {"gameplay_options": result}


@router.patch("/gameplay_options")
def patch_gameplay_options(req: GameplayOptionsPatchReq, sm=Depends(require_active_save)):
    """部分更新玩法选项（深度合并）。"""
    result = sm.patch_gameplay_options(req.patch)
    return {"gameplay_options": result}


# ============ 动态实体配额 ============

@router.get("/entity_quota")
def get_entity_quota(sm=Depends(require_active_save)):
    """获取所有实体类型的配额使用概况。"""
    options = sm.get_gameplay_options()
    meta = sm.get_meta()
    from src.backend.agent.entity_quota import EntityQuotaChecker
    checker = EntityQuotaChecker(sm)
    usage = checker.get_usage_summary(options, meta.get("tick_num", 0))
    return {"quota_usage": usage}


@router.get("/entity_quota/{entity_type}")
def check_entity_quota(entity_type: str, sm=Depends(require_active_save)):
    """检查指定实体类型的配额。"""
    options = sm.get_gameplay_options()
    meta = sm.get_meta()
    from src.backend.agent.entity_quota import EntityQuotaChecker, QuotaExceededError
    checker = EntityQuotaChecker(sm)
    try:
        checker.check(entity_type, options, current_tick=meta.get("tick_num", 0))
        return {"entity_type": entity_type, "passed": True}
    except QuotaExceededError as e:
        return {"entity_type": entity_type, "passed": False, "message": str(e)}


# ============ 操作日志 ============

@router.get("/operation_log")
def query_operation_log(
    op_type: str = "",
    actor: str = "",
    op_entity_type: str = "",
    limit: int = 50,
    sm=Depends(require_active_save),
):
    """查询操作日志。"""
    logs = sm.query_operations(
        op_type=op_type, actor=actor,
        op_entity_type=op_entity_type, limit=limit,
    )
    return {"logs": logs, "count": len(logs)}


@router.get("/operation_log/summary")
def get_operation_log_summary(sm=Depends(require_active_save)):
    """操作日志摘要（按类型统计）。"""
    from collections import Counter
    logs = sm.query_operations(limit=500)
    type_counts = Counter(l["op_type"] for l in logs)
    entity_counts = Counter(
        f"{l.get('op_entity_type', 'unknown')}_{l.get('op_entity_id', '?')}"
        for l in logs if l.get("op_entity_type")
    )
    # 最近动态实体
    dynamic_entities = [
        l for l in logs
        if l["op_type"] == "create_dynamic_entity" and l.get("success")
    ][-20:]  # 最近 20 条

    return {
        "total": len(logs),
        "by_type": dict(type_counts),
        "dynamic_entities": [
            {
                "entity_type": l.get("op_entity_type"),
                "entity_id": l.get("op_entity_id"),
                "tool": l.get("tool"),
                "tick": l.get("tick_num"),
                "created_at": l.get("created_at"),
            }
            for l in reversed(dynamic_entities)
        ],
    }


# ============ 世界背景 ============

class WorldBackgroundUpdateReq(BaseModel):
    world_background_raw: Optional[str] = None
    world_background_polished: Optional[str] = None
    civilization_summary: Optional[str] = None


@router.get("/world_background")
def get_world_background(sm=Depends(require_active_save)):
    """获取世界背景设定。"""
    meta = sm.get_meta()
    return {
        "world_background_raw": meta.get("world_background_raw", ""),
        "world_background_polished": meta.get("world_background_polished", ""),
        "civilization_summary": meta.get("civilization_summary", ""),
        "stable_context_version": meta.get("stable_context_version", 0),
    }


@router.put("/world_background")
def set_world_background(req: WorldBackgroundUpdateReq, sm=Depends(require_active_save)):
    """更新世界背景设定（同时 bump stable_context_version）。"""
    updates = {}
    if req.world_background_raw is not None:
        updates["world_background_raw"] = req.world_background_raw
    if req.world_background_polished is not None:
        updates["world_background_polished"] = req.world_background_polished
    if req.civilization_summary is not None:
        updates["civilization_summary"] = req.civilization_summary
    if not updates:
        raise HTTPException(status_code=400, detail="无更新内容")
    # bump version
    meta = sm.get_meta()
    updates["stable_context_version"] = meta.get("stable_context_version", 0) + 1
    result = sm.update_meta(**updates)
    return {"world_background": result}


# ============ 上下文打包（供调试） ============

@router.get("/packed_context")
def get_packed_context(sm=Depends(require_active_save), sm_dep=Depends(require_active_save)):
    """获取当前打包后的上下文（供调试）。"""
    options = sm.get_gameplay_options()
    from src.backend.agent.context_packager import (
        build_stable_context,
        build_dynamic_entity_list,
    )
    from src.backend.agent.option_processor import (
        build_gameplay_style_block,
        build_entity_quota_block,
    )
    stable = build_stable_context(sm)
    style_block = build_gameplay_style_block(options)
    quota_block = build_entity_quota_block(options)
    dynamic_entities = build_dynamic_entity_list(sm, options)

    return {
        "stable_context": stable,
        "gameplay_style_block": style_block,
        "entity_quota_block": quota_block,
        "dynamic_entities": dynamic_entities,
    }
