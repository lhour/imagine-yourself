"""src.backend.agent.option_processor — v5 玩法选项 → prompt 写作指令处理器。

核心规则：玩家选项绝不直接拼进 prompt，而是由这里翻译成**具体的写作指令文本**，
注入到对应 skill 的 system prompt 固定位置。

翻译规则：每个选项枚举值对应一段中文指令模板，按场景（叙事/对话/描写）拼接。
"""

from __future__ import annotations

from typing import Any, Dict, List


# ============ 翻译映射表 ============

# writing_style → 写作指令（按用户给出的示例规范）
WRITING_STYLE_MAP = {
    "直白": (
        "【叙事笔法·直白】描绘角色动作神态时应该用直白的写法，"
        "不要用环境或其他物体指代，例如：嘴角流出一抹鲜血；皮肤粉嫩洁白如玉。"
    ),
    "隐晦": (
        "【叙事笔法·隐晦】用环境、光影、物件侧面烘托情绪与状态，"
        "不明写结果，让读者自行体会。例如：窗外雷声阵阵，茶已凉透，他仍沉默不语。"
    ),
    "写意": (
        "【叙事笔法·写意】以诗意、留白、意象化的语言，重意境轻细节，"
        "追求画面感与氛围感，让读者在想象中补全。例如：月色如水，剑光一闪，胜负已分。"
    ),
    "克制": (
        "【叙事笔法·克制】语言简练中性，情绪不外露，用动作而非心理描写推动，"
        "以冷静客观的叙述呈现事件。例如：他转身，关门，脚步声沿走廊远去。"
    ),
}

# 死亡/好感/运气/挑战 → 叙事倾向指令
BIAS_DESCRIPTIONS = {
    "death_likelihood": {
        0: "死亡事件极其罕见，角色有极强的生存运气。",
        1: "死亡事件很少发生，通常有惊无险。",
        2: "死亡事件偶发，需要极端条件触发。",
        3: "死亡事件按正常概率发生。",
        4: "死亡事件较频繁，危险时刻常伴随伤亡。",
        5: "死亡事件频繁且残酷，角色随时面临生命危险。",
    },
    "favorability_bias": {
        -5: "角色间极难产生好感，关系冷淡甚至敌对。",
        -3: "角色间好感增长困难，信任需要长期积累。",
        -1: "角色间好感略偏保守，不会轻易亲近。",
        0: "角色间好感正常发展，无特殊偏向。",
        1: "角色间好感略偏积极，容易建立善意。",
        3: "角色间好感较容易增长，信任建立较快。",
        5: "角色间好感极易增长，人际氛围温暖融洽。",
    },
    "luck_bias": {
        -5: "主角持续走背运，几乎事事不顺。",
        -3: "主角经常遭遇小挫折，好运很少。",
        -1: "主角运气略差，偶有不顺。",
        0: "主角运气正常，好坏参半。",
        1: "主角运气略好，偶有意外收获。",
        3: "主角经常获得好运，贵人相助。",
        5: "主角持续走好运，几乎心想事成。",
    },
    "challenge_bias": {
        -5: "主角几乎无挑战，事事顺利。",
        -3: "主角挑战较少，困难很快解决。",
        -1: "主角挑战略少，多为常规难度。",
        0: "主角面临正常难度的挑战。",
        1: "主角挑战略多，偶有棘手情况。",
        3: "主角面临较多高难度挑战。",
        5: "主角持续面临极限挑战，危机四伏。",
    },
}

# 性取向 → 叙事视角指令
SEXUALITY_DESCRIPTIONS = {
    "男": "主角对男性角色抱有情感/ romantic 视角。",
    "女": "主角对女性角色抱有情感/ romantic 视角。",
    "同主角": "主角的性取向与自身性别相同。",
    "异主角": "主角的性取向与自身性别相反。",
}


def build_gameplay_style_block(options: Dict[str, Any]) -> str:
    """把 gameplay_options 翻译为一段稳定的「叙事风格指令块」文本。

    这是注入各 skill system prompt 的固定段落，应保持逐字稳定以命中缓存。

    Args:
        options: gameplay_options dict（含 writing_style、death_likelihood 等）

    Returns:
        多行指令文本，带统一前缀便于识别
    """
    lines: List[str] = []

    # 1) 写作笔法
    style = options.get("writing_style", "直白")
    style_instr = WRITING_STYLE_MAP.get(style, WRITING_STYLE_MAP["直白"])
    lines.append(style_instr)

    # 2) 死亡概率
    dl = options.get("death_likelihood", 3)
    dl_desc = BIAS_DESCRIPTIONS["death_likelihood"].get(dl, "")
    if dl_desc:
        lines.append(f"【死亡事件】{dl_desc}")

    # 3) 好感倾向
    fb = options.get("favorability_bias", 0)
    fb_desc = BIAS_DESCRIPTIONS["favorability_bias"].get(fb, "")
    if fb_desc:
        lines.append(f"【人际好感】{fb_desc}")

    # 4) 运气倾向
    lb = options.get("luck_bias", 0)
    lb_desc = BIAS_DESCRIPTIONS["luck_bias"].get(lb, "")
    if lb_desc:
        lines.append(f"【运气倾向】{lb_desc}")

    # 5) 挑战倾向
    cb = options.get("challenge_bias", 0)
    cb_desc = BIAS_DESCRIPTIONS["challenge_bias"].get(cb, "")
    if cb_desc:
        lines.append(f"【挑战强度】{cb_desc}")

    # 6) 主角性取向
    sx = options.get("player_sexuality", "异主角")
    sx_desc = SEXUALITY_DESCRIPTIONS.get(sx, "")
    if sx_desc:
        lines.append(f"【主角视角】{sx_desc}")

    # 7) 动态实体配额提示
    de = options.get("dynamic_entity", {})
    quota_lines = []
    for et, q in de.items():
        if not q.get("allowed", True):
            continue
        name_map = {
            "character": "角色", "group": "群体", "setting": "设定",
            "map": "地图", "map_feature": "地图要素", "item": "物品"
        }
        name = name_map.get(et, et)
        pt = q.get("per_tick", 1)
        quota_lines.append(f"每 tick 最多引入 {pt} 个新{name}")
    if quota_lines:
        lines.append("【动态实体配额】" + "；".join(quota_lines) + "。")

    # 8) 世界变更权限
    wm = options.get("world_modify_allowed", False)
    if wm:
        lines.append("【设定追加】允许在叙事中追加新的世界设定（不可删除初始设定）。")
    else:
        lines.append("【设定追加】模型不可修改或删除既有设定，也不可追加新设定。")

    return "\n".join(lines)


def build_entity_quota_block(options: Dict[str, Any]) -> str:
    """构建简短的实体配额提示块（用于 coordinator skill）。

    Returns:
        简短文本，列出各类型 per_tick 限制
    """
    de = options.get("dynamic_entity", {})
    parts = []
    name_map = {
        "character": "角色", "group": "群体", "setting": "设定",
        "map": "地图", "map_feature": "地图要素", "item": "物品"
    }
    for et in ["character", "group", "setting", "map", "map_feature", "item"]:
        q = de.get(et, {})
        if not q.get("allowed", True):
            parts.append(f"{name_map[et]}：禁止新增")
        else:
            pt = q.get("per_tick", 1)
            parts.append(f"{name_map[et]}：每 tick ≤ {pt}")
    return "【本 tick 动态实体配额】" + "，".join(parts) + "。"
