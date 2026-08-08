"""src.backend.agent.tool.dynamic_tools — v5 动态实体创建工具。

包含：
- entity_quota_check: 统一配额检查器（供所有动态创建工具前置调用）
- character_create_dynamic / group_create_dynamic / map_create_dynamic /
  map_feature_create_dynamic / item_create_dynamic: 动态实体创建工具
- setting_append_dynamic: 追加式设定工具（不可删除/覆盖初始设定）
- world_meta_append_note: 追加式世界设定补充

所有工具在执行前都会通过 entity_quota_check 检查配额，
并通过 operation_log 记录操作审计。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.backend.agent.tool.base import tool, ToolSpec

# 工具名清单
DYNAMIC_TOOL_NAMES: List[str] = []


def _get_save_manager() -> Any:
    """获取当前 SaveManager 实例。"""
    from src.backend.storage.connection import default_save_manager
    return default_save_manager()


def _check_and_log(entity_type: str, tool_name: str,
                   args: Dict[str, Any], actor: str = "model") -> Optional[str]:
    """统一配额检查 + 审计日志写入。

    Returns:
        None if pass, or error message string if fail
    """
    sm = _get_save_manager()
    try:
        options = sm.get_gameplay_options()
    except Exception:
        return "无法获取玩法选项，配额检查失败"

    from src.backend.agent.entity_quota import EntityQuotaChecker, QuotaExceededError
    checker = EntityQuotaChecker(sm)

    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 0)

    try:
        checker.check(entity_type, options, current_tick=cur_tick)
    except QuotaExceededError as e:
        sm.log_operation(
            op_type="create_dynamic_entity",
            op_entity_type=entity_type,
            op_entity_id=None,
            actor=actor,
            tool=tool_name,
            args=args,
            result={"error": str(e)},
            success=False,
            error_msg=str(e),
        )
        return str(e)

    return None


# ============================================================
# 工具实现
# ============================================================

@tool(
    name="entity_quota_check",
    desc="检查指定实体类型的动态创建配额",
)
def entity_quota_check(entity_type: str) -> str:
    """检查指定实体类型的动态创建配额。

    用于在创建新角色/群体/设定/地图之前检查是否还可以新增。
    配额分三档：1 tick 上限、100 tick 累计上限、全局累计上限。

    Args:
        entity_type: 实体类型 (character/group/setting/map/map_feature/item)

    Returns:
        JSON string with {passed: bool, message: str, usage: dict}
    """
    sm = _get_save_manager()
    options = sm.get_gameplay_options()
    meta = sm.get_meta()
    cur_tick = meta.get("tick_num", 0)

    from src.backend.agent.entity_quota import EntityQuotaChecker, QuotaExceededError
    checker = EntityQuotaChecker(sm)

    try:
        checker.check(entity_type, options, current_tick=cur_tick)
        usage = checker.get_usage_summary(options, cur_tick)
        return json.dumps({
            "passed": True,
            "message": f"{entity_type} 配额检查通过",
            "usage": usage,
        }, ensure_ascii=False)
    except QuotaExceededError as e:
        return json.dumps({
            "passed": False,
            "message": str(e),
            "usage": checker.get_usage_summary(options, cur_tick),
        }, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("entity_quota_check")


@tool(
    name="character_create_dynamic",
    desc="动态创建新角色（事件中提到即完整创建）",
)
def character_create_dynamic(
    char_name: str,
    appearance_raw: str,
    personality_raw: str,
    gender: str = "",
    age: int = 0,
    status: str = "",
    location_map_id: int = 0,
    groups: str = "[]",
    importance: int = 3,
    custom_attrs: str = "{}",
) -> str:
    """动态创建新角色（事件中提到即完整创建）。

    必须提供角色名、外貌、性格。
    配额：每 tick ≤ 配置上限，超限时拒绝并提示改用既有角色。

    Args:
        char_name: 角色名称（必填，唯一）
        appearance_raw: 外貌关键文本（必填）
        personality_raw: 性格关键文本（必填）
        gender: 性别
        age: 年龄
        status: 状态
        location_map_id: 初始地图 ID
        groups: 所属群体 ID 列表 (JSON 数组字符串)
        importance: 重要度 0-5
        custom_attrs: 自定义属性 (JSON 对象字符串)

    Returns:
        JSON string with {success: bool, char_id: int, message: str}
    """
    # 1) 配额检查
    err = _check_and_log("character", "character_create_dynamic", {
        "char_name": char_name
    })
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    sm = _get_save_manager()
    try:
        # 2) 名称唯一性检查
        conn = sm._conn
        existing = conn.execute(
            "SELECT id FROM characters WHERE name = ?", [char_name]
        ).fetchone()
        if existing:
            sm.log_operation(
                "create_dynamic_entity", "character_create_dynamic",
                op_entity_type="character", op_entity_id=existing["id"],
                args={"char_name": char_name},
                result={"error": f"角色名 {char_name} 已存在"},
                success=False,
                error_msg=f"角色名 {char_name} 已存在",
            )
            return json.dumps({
                "success": False,
                "message": f"角色名 {char_name} 已存在，请使用既有角色或换名",
            }, ensure_ascii=False)

        # 3) 创建角色
        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)
        conn.execute(
            "INSERT INTO characters (name, appearance_raw, personality_raw, "
            "gender, age, status, importance, custom_attrs, created_at_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [char_name, appearance_raw, personality_raw,
             gender, age, status, importance,
             custom_attrs, cur_tick]
        )
        char_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 4) 创建位置记录（若指定了地图）
        if location_map_id and location_map_id > 0:
            conn.execute(
                "INSERT INTO character_locations (char_id, map_id, last_update_tick) "
                "VALUES (?, ?, ?)",
                [char_id, location_map_id, cur_tick]
            )

        # 5) 加入群体（若指定）
        if groups and groups != "[]":
            try:
                group_ids = json.loads(groups)
                for gid in group_ids:
                    conn.execute(
                        "INSERT INTO character_group_relations "
                        "(char_id, group_id, join_tick, importance_in_group) "
                        "VALUES (?, ?, ?, ?)",
                        [char_id, gid, cur_tick, importance]
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        conn.commit()

        # 6) 写操作日志
        sm.log_operation(
            "create_dynamic_entity", "character_create_dynamic",
            op_entity_type="character", op_entity_id=char_id,
            args={
                "char_name": char_name, "appearance_raw": appearance_raw,
                "personality_raw": personality_raw, "gender": gender,
                "age": age, "status": status,
                "location_map_id": location_map_id, "groups": groups,
                "importance": importance,
            },
            result={"char_id": char_id, "message": f"角色 {char_name} 已创建"},
        )

        return json.dumps({
            "success": True,
            "char_id": char_id,
            "message": f"角色 {char_name} 已完整创建（ID={char_id}）",
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"创建角色失败: {str(e)}",
        }, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("character_create_dynamic")


@tool(
    name="group_create_dynamic",
    desc="动态创建新群体",
)
def group_create_dynamic(
    name: str,
    desc_raw: str,
    group_type: str = "crowd",
    leader_id: int = 0,
    primary_map_id: int = 0,
    importance: int = 3,
    custom_attrs: str = "{}",
) -> str:
    """动态创建新群体。

    Args:
        name: 群体名称（必填）
        desc_raw: 群体描述（必填）
        group_type: 类型 (residence/military/organization/monster/crowd/custom)
        leader_id: 领导人角色 ID
        primary_map_id: 主要活动地图 ID
        importance: 重要度 0-5
        custom_attrs: 自定义属性

    Returns:
        JSON string with group info
    """
    err = _check_and_log("group", "group_create_dynamic", {"name": name})
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    sm = _get_save_manager()
    try:
        conn = sm._conn
        existing = conn.execute(
            "SELECT id FROM groups WHERE name = ?", [name]
        ).fetchone()
        if existing:
            return json.dumps({
                "success": False,
                "message": f"群体名 {name} 已存在",
            }, ensure_ascii=False)

        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)
        conn.execute(
            "INSERT INTO groups (name, desc_raw, group_type, leader_id, "
            "primary_map_id, importance, custom_attrs, created_at_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [name, desc_raw, group_type, leader_id or None,
             primary_map_id or None, importance, custom_attrs, cur_tick]
        )
        gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        sm.log_operation(
            "create_dynamic_entity", "group_create_dynamic",
            op_entity_type="group", op_entity_id=gid,
            args={"name": name, "group_type": group_type},
            result={"group_id": gid},
        )

        return json.dumps({
            "success": True, "group_id": gid,
            "message": f"群体 {name} 已创建（ID={gid}）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("group_create_dynamic")


@tool(
    name="map_create_dynamic",
    desc="动态创建新地图",
)
def map_create_dynamic(
    name: str,
    desc_raw: str,
    map_type: str = "city",
    parent_map_id: int = 0,
    bbox_w: float = 100.0,
    bbox_h: float = 100.0,
    importance: int = 3,
    custom_attrs: str = "{}",
) -> str:
    """动态创建新地图。

    Args:
        name: 地图名称（必填）
        desc_raw: 地图描述（必填）
        map_type: 类型 (city/district/building/dungeon/custom)
        parent_map_id: 上级地图 ID
        bbox_w: 宽度
        bbox_h: 高度
        importance: 重要度 0-5
        custom_attrs: 自定义属性

    Returns:
        JSON string with map info
    """
    err = _check_and_log("map", "map_create_dynamic", {"name": name})
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    sm = _get_save_manager()
    try:
        conn = sm._conn
        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)
        conn.execute(
            "INSERT INTO maps (name, desc_raw, map_type, parent_map_id, "
            "bbox_w, bbox_h, importance, custom_attrs, created_at_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [name, desc_raw, map_type, parent_map_id or None,
             bbox_w, bbox_h, importance, custom_attrs, cur_tick]
        )
        mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        sm.log_operation(
            "create_dynamic_entity", "map_create_dynamic",
            op_entity_type="map", op_entity_id=mid,
            args={"name": name, "map_type": map_type},
            result={"map_id": mid},
        )

        return json.dumps({
            "success": True, "map_id": mid,
            "message": f"地图 {name} 已创建（ID={mid}）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("map_create_dynamic")


@tool(
    name="map_feature_create_dynamic",
    desc="动态创建新地图要素（建筑/地标等）",
)
def map_feature_create_dynamic(
    map_id: int,
    name: str,
    feature_type: str = "building",
    shape: str = "rectangle",
    geometry: str = "{}",
    desc_raw: str = "",
    importance: int = 3,
    custom_attrs: str = "{}",
) -> str:
    """动态创建新地图要素（建筑/地标等）。

    Args:
        map_id: 所属地图 ID（必填）
        name: 要素名称（必填）
        feature_type: 类型 (building/landmark/terrain/point_of_interest)
        shape: 形状 (rectangle/circle/polygon/point)
        geometry: 几何数据 (JSON)
        desc_raw: 描述
        importance: 重要度 0-5
        custom_attrs: 自定义属性

    Returns:
        JSON string with feature info
    """
    err = _check_and_log("map_feature", "map_feature_create_dynamic",
                         {"map_id": map_id, "name": name})
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    sm = _get_save_manager()
    try:
        conn = sm._conn
        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)
        conn.execute(
            "INSERT INTO map_features (map_id, name, feature_type, shape, "
            "geometry, desc_raw, importance, custom_attrs, created_at_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [map_id, name, feature_type, shape, geometry,
             desc_raw, importance, custom_attrs, cur_tick]
        )
        fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        sm.log_operation(
            "create_dynamic_entity", "map_feature_create_dynamic",
            op_entity_type="map_feature", op_entity_id=fid,
            args={"map_id": map_id, "name": name},
            result={"feature_id": fid},
        )

        return json.dumps({
            "success": True, "feature_id": fid,
            "message": f"地图要素 {name} 已创建（ID={fid}）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("map_feature_create_dynamic")


@tool(
    name="item_create_dynamic",
    desc="动态创建新物品",
)
def item_create_dynamic(
    name: str,
    desc_raw: str,
    item_type: str = "misc",
    rarity: int = 1,
    importance: int = 3,
    custom_attrs: str = "{}",
) -> str:
    """动态创建新物品。

    Args:
        name: 物品名称（必填）
        desc_raw: 物品描述（必填）
        item_type: 类型 (weapon/armor/consumable/material/misc)
        rarity: 稀有度 1-5
        importance: 重要度 0-5
        custom_attrs: 自定义属性

    Returns:
        JSON string with item info
    """
    err = _check_and_log("item", "item_create_dynamic", {"name": name})
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    sm = _get_save_manager()
    try:
        conn = sm._conn
        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)
        conn.execute(
            "INSERT INTO items (name, desc_raw, item_type, rarity, importance, "
            "custom_attrs, created_at_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [name, desc_raw, item_type, rarity, importance,
             custom_attrs, cur_tick]
        )
        iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        sm.log_operation(
            "create_dynamic_entity", "item_create_dynamic",
            op_entity_type="item", op_entity_id=iid,
            args={"name": name, "item_type": item_type},
            result={"item_id": iid},
        )

        return json.dumps({
            "success": True, "item_id": iid,
            "message": f"物品 {name} 已创建（ID={iid}）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("item_create_dynamic")


@tool(
    name="setting_append_dynamic",
    desc="追加新设定（append-only，不可删除/覆盖初始设定）",
)
def setting_append_dynamic(
    category: str,
    title: str,
    desc_raw: str,
    desc_polished: str = "",
    importance: int = 3,
    parent_setting_id: int = 0,
    append_note: str = "",
    custom_attrs: str = "{}",
) -> str:
    """追加新设定（append-only，不可删除/覆盖初始设定）。

    玩家初始设定（source=drama/human, immutable=1）不可被修改或删除。
    此工具仅能追加新设定条目，或在既有设定基础上做补充说明。

    Args:
        category: 设定分类 (如 world/character/item/plot)
        title: 设定标题（必填）
        desc_raw: 设定描述（必填）
        desc_polished: 润色描述
        importance: 重要度 0-5
        parent_setting_id: 追加到哪条既有设定（0=独立条目）
        append_note: 追加理由/补充说明
        custom_attrs: 自定义属性

    Returns:
        JSON string with setting info
    """
    sm = _get_save_manager()
    options = sm.get_gameplay_options()

    # 检查 world_modify_allowed
    if not options.get("world_modify_allowed", False):
        return json.dumps({
            "success": False,
            "message": "玩家未开启设定追加权限 (world_modify_allowed=false)，"
                       "无法在叙事中追加新设定。",
        }, ensure_ascii=False)

    # 配额检查
    err = _check_and_log("setting", "setting_append_dynamic",
                         {"category": category, "title": title})
    if err:
        return json.dumps({"success": False, "message": err}, ensure_ascii=False)

    try:
        conn = sm._conn

        # 若指定了 parent_setting_id，验证父设定存在且不可变
        if parent_setting_id and parent_setting_id > 0:
            parent = conn.execute(
                "SELECT id, immutable, title FROM settings WHERE id = ?",
                [parent_setting_id]
            ).fetchone()
            if not parent:
                return json.dumps({
                    "success": False,
                    "message": f"父设定 ID={parent_setting_id} 不存在",
                }, ensure_ascii=False)

        meta = sm.get_meta()
        cur_tick = meta.get("tick_num", 0)

        # 以 source=model 写入，immutable=0（模型追加的设定可被后续追加，但不可删除）
        conn.execute(
            "INSERT INTO settings (category, title, desc_raw, desc_polished, "
            "importance, custom_attrs, source, immutable, parent_setting_id, "
            "append_note, created_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, 'model', 0, ?, ?, ?)",
            [category, title, desc_raw, desc_polished,
             importance, custom_attrs,
             parent_setting_id or None, append_note, cur_tick]
        )
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        sm.log_operation(
            "append_setting", "setting_append_dynamic",
            op_entity_type="setting", op_entity_id=sid,
            args={"category": category, "title": title,
                  "parent_setting_id": parent_setting_id,
                  "append_note": append_note},
            result={"setting_id": sid},
        )

        return json.dumps({
            "success": True, "setting_id": sid,
            "message": f"设定「{title}」已追加（ID={sid}，source=model）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("setting_append_dynamic")


@tool(
    name="world_meta_append_note",
    desc="追加世界设定补充说明（仅追加，不可删除/覆盖初始内容）",
)
def world_meta_append_note(note: str) -> str:
    """追加世界设定补充说明（仅追加，不可删除/覆盖初始内容）。

    只能在已有背景基础上追加补充说明，不可修改或删除任何既有内容。

    Args:
        note: 补充说明文本（必填）

    Returns:
        JSON string with update info
    """
    sm = _get_save_manager()
    options = sm.get_gameplay_options()

    if not options.get("world_modify_allowed", False):
        return json.dumps({
            "success": False,
            "message": "玩家未开启设定追加权限，无法补充世界背景。",
        }, ensure_ascii=False)

    try:
        meta = sm.get_meta()
        existing = meta.get("world_background_polished") or meta.get("world_background_raw") or ""
        separator = "\n\n---\n\n" if existing else ""
        new_value = existing + separator + f"【模型补充·tick {meta.get('tick_num', 0)}】{note}"

        sm.update_meta(world_background_polished=new_value)
        # bump version
        current_ver = meta.get("stable_context_version", 0)
        sm.update_meta(stable_context_version=current_ver + 1)

        sm.log_operation(
            "append_world_note", "world_meta_append_note",
            op_entity_type="world", op_entity_id=None,
            args={"note": note},
            result={"new_version": current_ver + 1},
        )

        return json.dumps({
            "success": True,
            "new_version": current_ver + 1,
            "message": f"世界背景补充说明已追加（version={current_ver + 1}）",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)}, ensure_ascii=False)


DYNAMIC_TOOL_NAMES.append("world_meta_append_note")


# ============================================================
# 导出
# ============================================================

__all__ = [
    "DYNAMIC_TOOL_NAMES",
    "entity_quota_check",
    "character_create_dynamic",
    "group_create_dynamic",
    "map_create_dynamic",
    "map_feature_create_dynamic",
    "item_create_dynamic",
    "setting_append_dynamic",
    "world_meta_append_note",
]
