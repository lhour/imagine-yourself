"""src.backend.http.deps — FastAPI 依赖注入 + 全局配置。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict

from fastapi import Depends, HTTPException

from src.backend.env import BACKEND_DIR
from src.backend.storage.connection import SaveManager, default_save_manager

# ============================================================
# 全局配置（与存档无关：UI 默认、TPS、AI 参数等）
# ============================================================

CONFIG_FILE = BACKEND_DIR / "config.json"

DEFAULT_GLOBAL_CONFIG: Dict[str, Any] = {
    "ui_defaults": {
        "default_tps": 1.0,
        "default_era_display_mode": "polished",
        "default_heatmap_opacity": 0.55,
        "default_map_zoom": 1.0,
        "event_importance_threshold": 0,
        "show_debug_info": False,
        "theme": "dark",
    },
    "simulation": {
        "tps_default": 1.0,
        "tps_min": 0.0,
        "tps_max": 240.0,
        "max_events_per_tick": 20,
        "memory_decay_per_tick": 0.01,
        "heatmap_update_interval_ticks": 10,
    },
    "memory": {
        "retrieve_max_default": 30,
        "palace_default_depth": 2,
        "index_sampling_rate": 1.0,
    },
    "llm_pipeline": {
        "enabled": False,
        "provider": "stub",
        "model": "",
        "api_base": "",
        "api_key": "",
        "max_tokens_per_request": 2048,
    },
    "privacy": {
        "allow_data_collection": False,
        "saves_store_path": "",
        "retention_days": 0,
    },
}

_config_lock = RLock()
_cached_config: Dict[str, Any] | None = None


def _ensure_config_file() -> None:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_GLOBAL_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def get_global_config() -> Dict[str, Any]:
    """读全局配置（带惰性初始化 + 内存缓存）。"""
    global _cached_config
    with _config_lock:
        if _cached_config is not None:
            return json.loads(json.dumps(_cached_config))  # 浅副本防外部修改
        _ensure_config_file()
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        # 与 DEFAULT 合并（补新增字段，不破坏旧配置）
        merged = _deep_merge(json.loads(json.dumps(DEFAULT_GLOBAL_CONFIG)), loaded)
        _cached_config = merged
        return json.loads(json.dumps(merged))


def set_global_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    """局部更新全局配置（深 merge + 写回文件 + 失效缓存）。"""
    global _cached_config
    with _config_lock:
        current = get_global_config()
        merged = _deep_merge(current, patch)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _cached_config = merged
        return json.loads(json.dumps(merged))


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


# ============================================================
# 存档依赖
# ============================================================

def get_save_manager() -> SaveManager:
    return default_save_manager()


def require_active_save(sm: SaveManager = Depends(get_save_manager)) -> SaveManager:
    """要求激活存档；否则 400。"""
    if not sm.active_save:
        raise HTTPException(
            status_code=400,
            detail="无激活存档；请先 POST /api/saves 创建或 POST /api/saves/{name}/switch 切换"
        )
    return sm
