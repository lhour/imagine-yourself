"""src.backend.agent.entity_quota — v5 统一动态实体配额检查器。

配额范围覆盖所有会占用 prompt 上下文的动态实体类型：
  character / group / setting / map / map_feature / item

每种实体类型独立三档配额：
  per_tick       — 单次 tick 上限
  per_100tick    — 最近 100 tick 累计上限
  max_total      — 存档全局累计上限
  allowed        — 玩家开关（False 时直接拒绝）

配额数据源：gameplay_options.dynamic_entity（存储在 world_meta.gameplay_options）。
计数方式：扫描 operation_log 中 op_type='create_dynamic_entity' 的记录。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# 支持的实体类型列表
ENTITY_TYPES = ("character", "group", "setting", "map", "map_feature", "item")

# 中文映射（用于提示信息）
ENTITY_TYPE_NAMES = {
    "character": "角色",
    "group": "群体",
    "setting": "设定",
    "map": "地图",
    "map_feature": "地图要素",
    "item": "物品",
}


class QuotaExceededError(Exception):
    """配额超限异常。携带超限档位信息。"""

    def __init__(self, entity_type: str, exceeded_level: str,
                 limit: int, current: int, hint: str = ""):
        self.entity_type = entity_type
        self.exceeded_level = exceeded_level
        self.limit = limit
        self.current = current
        self.hint = hint
        name = ENTITY_TYPE_NAMES.get(entity_type, entity_type)
        level_names = {
            "per_tick": "单 tick",
            "per_100tick": "100 tick 累计",
            "max_total": "全局累计",
        }
        level = level_names.get(exceeded_level, exceeded_level)
        msg = f"{level}新增{name}数({current})已达上限({limit})"
        if hint:
            msg += f"，{hint}"
        super().__init__(msg)


class EntityQuotaChecker:
    """统一动态实体配额检查器。

    使用方式：
        checker = EntityQuotaChecker(save_manager)
        checker.check("character", gameplay_options)  # 若超限抛 QuotaExceededError
    """

    def __init__(self, save_manager: Any) -> None:
        self._sm = save_manager

    def check(self, entity_type: str, options: Dict[str, Any],
              current_tick: int = 0) -> Tuple[bool, str]:
        """检查指定实体类型是否还可以新增。

        Args:
            entity_type: 实体类型（character/group/setting/map/map_feature/item）
            options: gameplay_options dict
            current_tick: 当前 tick（用于计算 100 tick 窗口）

        Returns:
            (passed, message): passed=True 表示通过；message 为拒绝理由或空串
        """
        if entity_type not in ENTITY_TYPES:
            return False, f"未知实体类型: {entity_type}"

        de_opts = options.get("dynamic_entity", {}).get(entity_type, {})

        # 1) 检查玩家开关
        if not de_opts.get("allowed", True):
            return False, f"玩家已关闭{ENTITY_TYPE_NAMES[entity_type]}的动态创建"

        # 2) 三档检查
        # 2a) per_tick
        per_tick_limit = de_opts.get("per_tick", 1)
        current_tick_count = self._sm.count_dynamic_entities(entity_type, since_tick=current_tick)
        if current_tick_count >= per_tick_limit:
            raise QuotaExceededError(
                entity_type, "per_tick", per_tick_limit, current_tick_count,
                "本 tick 已达上限，请改用既有实体"
            )

        # 2b) per_100tick
        per_100_limit = de_opts.get("per_100tick", 30)
        window_start = max(0, current_tick - 99)
        count_100 = self._sm.count_dynamic_entities(entity_type, since_tick=window_start)
        if count_100 >= per_100_limit:
            raise QuotaExceededError(
                entity_type, "per_100tick", per_100_limit, count_100,
                "近 100 tick 已达上限，请改用既有实体"
            )

        # 2c) max_total
        max_total = de_opts.get("max_total", 120)
        total = self._sm.count_dynamic_entities_total(entity_type)
        if total >= max_total:
            raise QuotaExceededError(
                entity_type, "max_total", max_total, total,
                "存档全局已达上限，请改用既有实体"
            )

        return True, ""

    def get_usage_summary(self, options: Dict[str, Any],
                          current_tick: int = 0) -> List[Dict[str, Any]]:
        """获取所有实体类型的配额使用概况（供前端展示）。"""
        summary = []
        for et in ENTITY_TYPES:
            de_opts = options.get("dynamic_entity", {}).get(et, {})
            per_tick_limit = de_opts.get("per_tick", 1)
            per_100_limit = de_opts.get("per_100tick", 30)
            max_total = de_opts.get("max_total", 120)
            allowed = de_opts.get("allowed", True)

            cur_tick = self._sm.count_dynamic_entities(et, since_tick=current_tick)
            window_start = max(0, current_tick - 99)
            cnt_100 = self._sm.count_dynamic_entities(et, since_tick=window_start)
            total = self._sm.count_dynamic_entities_total(et)

            summary.append({
                "entity_type": et,
                "name": ENTITY_TYPE_NAMES.get(et, et),
                "allowed": allowed,
                "per_tick": {"current": cur_tick, "limit": per_tick_limit},
                "per_100tick": {"current": cnt_100, "limit": per_100_limit},
                "max_total": {"current": total, "limit": max_total},
            })
        return summary


def get_default_dynamic_entity_quota() -> Dict[str, Dict[str, Any]]:
    """获取默认动态实体配额配置（供前端初始化）。"""
    return {
        et: {
            "per_tick": defaults[0],
            "per_100tick": defaults[1],
            "max_total": defaults[2],
            "allowed": True,
        }
        for et, defaults in [
            ("character",    (1, 30, 120)),
            ("group",        (1, 10, 40)),
            ("setting",      (2, 30, 100)),
            ("map",          (1, 8, 25)),
            ("map_feature",  (3, 50, 200)),
            ("item",         (2, 30, 150)),
        ]
    }
