"""src.backend.http.routers.dramas — 剧本管理（阶段七：校验 + 生成 + 导出）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.backend.http.deps import get_save_manager
from src.backend.service import drama_service
from src.backend.service.drama_generator import (
    generate_drama_10step,
    generate_step,
    get_generate_status,
    DRAMA_GENERATE_STEPS,
)

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


class GenerateDramaBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    name: Optional[str] = None
    skip_steps: Optional[str] = None  # 逗号分隔：1,3,5
    only_steps: Optional[str] = None  # 逗号分隔：1-3,5,7


class GenerateStepBody(BaseModel):
    step: int = Field(..., ge=1, le=10)


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


@router.get("/{name}/validate")
def validate_drama(name: str, sm=Depends(get_save_manager)):
    """**严格 9+1 校验**：文件齐全 + 字段完整 + 引用一致性。
    返回 {ok, errors, warnings, info}。
    """
    return drama_service.validate_drama(name)


@router.get("/{name}/preview")
def preview_drama(name: str, sm=Depends(get_save_manager)):
    """9+1 文件在线预览（前端卡片化查看用）。"""
    try:
        return drama_service.preview(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{name}/export")
def export_drama(name: str, sm=Depends(get_save_manager)):
    """**导出 zip**：将剧本 10 个核心文件打包下载。"""
    try:
        zbytes = drama_service.export_drama_zip(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    import io
    headers = {
        "Content-Disposition": f'attachment; filename="{name}.zip"',
    }
    return StreamingResponse(
        io.BytesIO(zbytes),
        media_type="application/zip",
        headers=headers,
    )


@router.post("/{name}/init")
def init_drama(name: str, body: InitDramaBody, sm=Depends(get_save_manager)):
    """导入剧本：严格校验通过后写入新存档并激活。"""
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
    """**原子写** 单个剧本文件（管理员模式：编辑剧本）。
    写临时文件 → os.replace 原子替换，失败不破坏原文件。
    """
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
# 一键生成（阶段七：接入 10 步 LLM 管线）
# ============================================================

@router.post("/_generate")
async def generate_drama(body: GenerateDramaBody, sm=Depends(get_save_manager)):
    """一键 AI 生成剧本：10 步 LLM 管线（可分步骤）。
    - skip_steps / only_steps 逗号分隔步骤号
    - 返回 { ok, name, step_results: [...], validate: {...} }
    """
    try:
        skip: List[int] = []
        only: Optional[List[int]] = None
        if body.skip_steps:
            skip = [int(x) for x in body.skip_steps.split(",") if x.strip().isdigit()]
        if body.only_steps:
            only = []
            for x in body.only_steps.split(","):
                x = x.strip()
                if not x:
                    continue
                if "-" in x:
                    a, b = x.split("-", 1)
                    only.extend(range(int(a), int(b) + 1))
                elif x.isdigit():
                    only.append(int(x))
        result = await generate_drama_10step(
            prompt=body.prompt,
            name=body.name,
            skip_steps=skip,
            only_steps=only,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"生成失败：{e}")


@router.post("/{name}/_generate_step")
def generate_one_step(name: str, body: GenerateStepBody, sm=Depends(get_save_manager)):
    """单独执行生成管线中的某一步（用于断点续跑 / 手工重跑）。"""
    try:
        return generate_step(name, body.step)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{name}/_generate_status")
def generate_status(name: str, sm=Depends(get_save_manager)):
    """查询剧本的生成管线状态：哪些步骤已完成、生成耗时、校验结果。"""
    return get_generate_status(name)
