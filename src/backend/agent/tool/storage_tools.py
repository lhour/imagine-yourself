"""src.backend.agent.tool.storage_tools — 存档管理工具（高层 API）。

提供给 LLM 使用的存档/元信息/主角管理工具。
"""

from __future__ import annotations

from src.backend.agent.tool.base import ToolManager, tool
from src.backend.storage.connection import default_save_manager


# ============================================================
# 存档管理工具
# ============================================================

@tool(
    name="storage_list_saves",
    desc="列出所有存档名称",
)
def storage_list_saves() -> dict:
    sm = default_save_manager()
    return {"saves": sm.list_saves()}


@tool(
    name="storage_create_save",
    desc="创建新存档（独立 SQLite 数据库，自动建好所有表与元数据行）并设为激活",
    params={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "存档名（仅字母/数字/下划线/连字符）"},
        },
        "required": ["name"],
    },
)
def storage_create_save(name: str) -> dict:
    sm = default_save_manager()
    try:
        return {"created": sm.create_save(name), "active": sm.active_save}
    except (ValueError, FileExistsError) as e:
        return {"error": str(e)}


@tool(
    name="storage_switch_save",
    desc="切换当前激活存档",
    params={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def storage_switch_save(name: str) -> dict:
    sm = default_save_manager()
    try:
        return {"active": sm.switch_save(name)}
    except FileNotFoundError as e:
        return {"error": str(e)}


@tool(
    name="storage_get_active_save",
    desc="查询当前激活存档名",
)
def storage_get_active_save() -> dict:
    return {"active_save": default_save_manager().active_save}


@tool(
    name="storage_get_meta",
    desc="获取当前激活存档的元信息（tick/game_time/era/protagonist 等）",
)
def storage_get_meta() -> dict:
    sm = default_save_manager()
    if not sm.active_save:
        return {"error": "无激活存档"}
    return sm.get_meta()


@tool(
    name="storage_update_meta",
    desc="更新当前存档的元信息字段（仅传需要更新的字段）",
    params={
        "type": "object",
        "properties": {
            "tick_num": {"type": "integer"},
            "game_time": {"type": "string"},
            "era_name": {"type": "string"},
            "description": {"type": "string"},
        },
    },
)
def storage_update_meta(**fields) -> dict:
    sm = default_save_manager()
    if not sm.active_save:
        return {"error": "无激活存档"}
    return sm.update_meta(**fields)


@tool(
    name="storage_create_snapshot",
    desc="为当前激活存档创建快照（VACUUM INTO）",
)
def storage_create_snapshot() -> dict:
    sm = default_save_manager()
    try:
        fname = sm.create_snapshot()
        return {"created": fname}
    except RuntimeError as e:
        return {"error": str(e)}


@tool(
    name="storage_get_protagonist",
    desc="获取主角信息",
)
def storage_get_protagonist() -> dict:
    sm = default_save_manager()
    p = sm.get_protagonist()
    return {"protagonist": p}


@tool(
    name="storage_set_protagonist",
    desc="设置主角（按 character.id）",
    params={
        "type": "object",
        "properties": {"char_id": {"type": "integer"}},
        "required": ["char_id"],
    },
)
def storage_set_protagonist(char_id: int) -> dict:
    sm = default_save_manager()
    return sm.set_protagonist(char_id)


# 暴露给 storage 包的总工具列表
SAVE_TOOLS = [
    "storage_list_saves", "storage_create_save", "storage_switch_save",
    "storage_get_active_save", "storage_get_meta", "storage_update_meta",
    "storage_create_snapshot", "storage_get_protagonist", "storage_set_protagonist",
]
