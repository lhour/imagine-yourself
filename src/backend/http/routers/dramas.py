"""src.backend.http.routers.dramas — 剧本管理（阶段四完成版）。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.http.deps import get_save_manager
from src.backend.service import drama_service

router = APIRouter(prefix="/api/dramas", tags=["dramas"])


# ============================================================
# Pydantic 入参
# ============================================================

class InitDramaBody(BaseModel):
    save_name: str
    overwrite: bool = False


class PatchDramaFileBody(BaseModel):
    file_name: str
    content: str


# ============================================================
# 路由
# ============================================================

@router.get("")
def list_dramas(sm=Depends(get_save_manager)):
    return {"items": drama_service.list_dramas()}


@router.get("/{name}")
def get_drama(name: str, sm=Depends(get_save_manager)):
    d = drama_service.get_drama(name)
    if not d:
        raise HTTPException(404, f"剧本 {name} 不存在")
    return d


@router.get("/{name}/preview")
def preview_drama(name: str, sm=Depends(get_save_manager)):
    """9+1 文件在线预览（前端 8 分屏查看用）。"""
    try:
        return drama_service.preview(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{name}/init")
def init_drama(name: str, body: InitDramaBody, sm=Depends(get_save_manager)):
    """导入剧本：生成新存档并激活。"""
    try:
        return drama_service.init_drama(name, body.save_name, body.overwrite)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/{name}")
def patch_drama_file(
    name: str,
    body: PatchDramaFileBody,
    sm=Depends(get_save_manager),
):
    """覆写单个剧本文件（管理员模式：编辑剧本）。"""
    try:
        drama_service.patch_drama_file(name, body.file_name, body.content)
        return {"ok": True, "name": name, "file_name": body.file_name}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.delete("/{name}")
def delete_drama(name: str, sm=Depends(get_save_manager)):
    """删除剧本目录。"""
    ok = drama_service.delete_drama(name)
    if not ok:
        raise HTTPException(404, f"剧本 {name} 不存在")
    return {"ok": True, "name": name}


# ============================================================
# 工具/内部：一键生成（占位骨架，留给 LLM 管线阶段实现）
# ============================================================

class GenerateDramaBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    name: Optional[str] = None


@router.post("/_generate")
def generate_drama_stub(body: GenerateDramaBody, sm=Depends(get_save_manager)):
    """占位：一键 AI 生成剧本（正式阶段接入 LLM 管线）。"""
    return {
        "ok": False,
        "stub": True,
        "message": "一键生成功能将在阶段五接入 LLM 管线，请先手工编写剧本或使用 sample 示例。",
    }
