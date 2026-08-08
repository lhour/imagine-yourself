"""src.backend.agent.context_packager — v5 上下文分层打包器。

把「几乎不变的信息」组装进对应 skill，分为三层：
  A 稳定前缀：系统身份、全局规则、文明/科技/时代背景
  B 稳定中段：主角能力、世界观核心设定（settings essential）、主城建筑总览
  C 动态尾段：当前 tick 场景、在场角色、活跃锚点、玩家动作

动态实体注入受 context_budget 约束，超预算时按重要度截断。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_stable_context(save_manager: Any) -> Dict[str, str]:
    """构建恒定上下文 A+B 段（供各 skill 注入的变量）。

    Args:
        save_manager: SaveManager 实例

    Returns:
        dict with keys: world_background, stable_context, stable_context_version
    """
    meta = save_manager.get_meta()
    parts = []

    # --- A 段：世界背景 ---
    wb = meta.get("world_background_polished") or meta.get("world_background_raw") or ""
    if wb:
        parts.append(f"【世界背景】{wb}")

    cs = meta.get("civilization_summary") or ""
    if cs:
        parts.append(f"【文明形态】{cs}")

    # --- B 段：基础设定 ---
    try:
        conn = save_manager._conn
        if conn:
            rows = conn.execute(
                "SELECT title, desc_raw FROM settings "
                "WHERE setting_type = 'essential' "
                "ORDER BY importance DESC LIMIT 30"
            ).fetchall()
            if rows:
                setting_lines = [f"  · {r['title']}：{r['desc_raw'][:120]}" for r in rows]
                parts.append("【核心设定】\n" + "\n".join(setting_lines))
    except Exception:
        pass

    # 版本号
    version = meta.get("stable_context_version", 0)

    return {
        "world_background": wb,
        "stable_context": "\n\n".join(parts) if parts else "",
        "stable_context_version": str(version),
    }


def build_dynamic_entity_list(
    save_manager: Any,
    gameplay_options: Dict[str, Any],
    entity_types: Optional[List[str]] = None,
) -> str:
    """构建动态实体注入文本（C 段的一部分），受 context_budget 约束。

    从 operation_log 中取最近创建的动态实体，按 importance/tick 排序，
    超预算时只保留前 max_dynamic_entities_per_prompt 个。

    Args:
        save_manager: SaveManager 实例
        gameplay_options: 玩法选项（含 context_budget）
        entity_types: 要包含的实体类型列表，None=全部

    Returns:
        注入文本（可能为空）
    """
    budget = gameplay_options.get("context_budget", {})
    max_entities = budget.get("max_dynamic_entities_per_prompt", 40)

    try:
        conn = save_manager._conn
        if not conn:
            return ""

        et_filter = ""
        params: List[Any] = []
        if entity_types:
            placeholders = ",".join("?" * len(entity_types))
            et_filter = f" AND op_entity_type IN ({placeholders})"
            params.extend(entity_types)

        rows = conn.execute(
            "SELECT op_entity_type, op_entity_id, MAX(id) as max_id "
            "FROM operation_log "
            f"WHERE op_type = 'create_dynamic_entity' AND success = 1{et_filter} "
            "GROUP BY op_entity_type, op_entity_id "
            "ORDER BY max_id DESC "
            f"LIMIT ?",
            params + [max_entities]
        ).fetchall()

        if not rows:
            return ""

        # 按类型分组
        entities_by_type: Dict[str, List[int]] = {}
        for r in rows:
            et = r["op_entity_type"]
            eid = r["op_entity_id"]
            if et and eid:
                entities_by_type.setdefault(et, []).append(eid)

        parts = []
        name_map = {
            "character": "角色", "group": "群体", "setting": "设定",
            "map": "地图", "map_feature": "地图要素", "item": "物品"
        }

        for et, ids in entities_by_type.items():
            type_name = name_map.get(et, et)
            # 查询实体名称
            id_list = ",".join(str(i) for i in ids)
            if et == "character":
                db_rows = conn.execute(
                    f"SELECT id, name FROM characters WHERE id IN ({id_list})"
                ).fetchall()
            elif et == "group":
                db_rows = conn.execute(
                    f"SELECT id, name FROM groups WHERE id IN ({id_list})"
                ).fetchall()
            elif et == "setting":
                db_rows = conn.execute(
                    f"SELECT id, title as name FROM settings WHERE id IN ({id_list})"
                ).fetchall()
            elif et == "map":
                db_rows = conn.execute(
                    f"SELECT id, name FROM maps WHERE id IN ({id_list})"
                ).fetchall()
            elif et == "map_feature":
                db_rows = conn.execute(
                    f"SELECT id, name FROM map_features WHERE id IN ({id_list})"
                ).fetchall()
            elif et == "item":
                db_rows = conn.execute(
                    f"SELECT id, name FROM items WHERE id IN ({id_list})"
                ).fetchall()
            else:
                db_rows = []

            if db_rows:
                names = [r["name"] for r in db_rows]
                parts.append(f"【动态{type_name}】{', '.join(names)}")

        return "\n".join(parts)

    except Exception:
        return ""


def pack_context_for_skill(
    save_manager: Any,
    gameplay_options: Dict[str, Any],
    skill_name: str,
    extra_variables: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """为指定 skill 组装完整的变量字典（含恒定段 + 动态段 + 选项指令）。

    这是 context_packager 的主入口，供 pipeline 各节点调用。

    Args:
        save_manager: SaveManager 实例
        gameplay_options: 玩法选项
        skill_name: skill 名（决定注入哪些变量）
        extra_variables: 额外变量（如当前 tick 信息、玩家动作等）

    Returns:
        变量 dict，可直接传给 prompt/skill loader 的 _inject 方法
    """
    from src.backend.agent.option_processor import (
        build_gameplay_style_block,
        build_entity_quota_block,
    )

    # 1) 恒定上下文（A+B）
    stable = build_stable_context(save_manager)

    # 2) 玩法选项指令块
    style_block = build_gameplay_style_block(gameplay_options)
    quota_block = build_entity_quota_block(gameplay_options)

    # 3) 动态实体列表
    dynamic_entities = build_dynamic_entity_list(save_manager, gameplay_options)

    # 4) 组装变量
    variables: Dict[str, str] = {}
    variables.update(stable)  # world_background, stable_context, stable_context_version
    variables["gameplay_style_block"] = style_block
    variables["entity_quota_block"] = quota_block
    variables["dynamic_entities"] = dynamic_entities

    if extra_variables:
        variables.update(extra_variables)

    return variables
