"""默认玩法配置常量，供剧本级与存档级共用。"""
from typing import Any, Dict


def get_default_gameplay_options() -> Dict[str, Any]:
    """默认玩法选项（剧本级与存档级共用）。"""
    return {
        "player_sexuality": "异主角",
        "death_likelihood": 3,
        "favorability_bias": 0,
        "luck_bias": 0,
        "challenge_bias": 0,
        "writing_style": "直白",
        "dynamic_entity": {
            "character": {"per_tick": 1, "per_100tick": 30, "max_total": 120, "allowed": True},
            "group": {"per_tick": 1, "per_100tick": 10, "max_total": 40, "allowed": True},
            "setting": {"per_tick": 2, "per_100tick": 30, "max_total": 100, "allowed": True},
            "map": {"per_tick": 1, "per_100tick": 8, "max_total": 25, "allowed": True},
            "map_feature": {"per_tick": 3, "per_100tick": 50, "max_total": 200, "allowed": True},
            "item": {"per_tick": 2, "per_100tick": 30, "max_total": 150, "allowed": True},
        },
        "context_budget": {
            "max_dynamic_entities_per_prompt": 40,
            "max_static_bytes": 12000,
            "over_budget_policy": "recency+importance",
        },
        "world_modify_allowed": False,
    }
