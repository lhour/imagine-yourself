"""src.backend.http.routers.config — 全局设置（UI 默认 / 模拟参数 / LLM 管线 / 隐私等）。"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.backend.http.deps import (
    DEFAULT_GLOBAL_CONFIG,
    get_global_config,
    set_global_config,
)

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigPatchBody(BaseModel):
    """任意结构；server 端会做深 merge 而不是整包替换。"""

    model_config = {"extra": "allow"}
    ui_defaults: Dict[str, Any] = Field(default_factory=dict)
    simulation: Dict[str, Any] = Field(default_factory=dict)
    memory: Dict[str, Any] = Field(default_factory=dict)
    llm_pipeline: Dict[str, Any] = Field(default_factory=dict)
    privacy: Dict[str, Any] = Field(default_factory=dict)


@router.get("")
def get_config():
    """读取全局配置：包含实际值和默认 schema，便于前端做表单。"""
    return {
        "config": get_global_config(),
        "defaults": DEFAULT_GLOBAL_CONFIG,
    }


@router.patch("")
def patch_config(body: ConfigPatchBody):
    """局部更新：深 merge，只更新传入的字段，不传入的保持不变。"""
    patch: Dict[str, Any] = {}
    for key in ["ui_defaults", "simulation", "memory", "llm_pipeline", "privacy"]:
        section = getattr(body, key)
        if section:
            patch[key] = section
    # 支持顶层任意字段（兼容未来扩展）
    extras = body.model_extra or {}
    for k, v in extras.items():
        if k not in patch and isinstance(v, dict):
            patch[k] = v
    if not patch:
        raise HTTPException(400, "请至少传入一个要更新的配置字段")
    merged = set_global_config(patch)
    return {
        "ok": True,
        "config": merged,
        "updated_keys": list(patch.keys()),
    }


@router.post("/_reset")
def reset_config():
    """重置为默认配置。"""
    import json
    from src.backend.http.deps import CONFIG_FILE, _config_lock
    global _cached_config
    with _config_lock:
        from src.backend.http import deps as _deps
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_GLOBAL_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _deps._cached_config = None
    return {"ok": True, "config": DEFAULT_GLOBAL_CONFIG}
