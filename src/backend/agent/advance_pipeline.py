"""src.backend.agent.advance_pipeline — 统一时间推进编排。

「下一 Tick」与「时间跨越」本质都是让模型预测下一步，故合并为统一的 advance：
- 按跨度（秒数）选择不同的 skill / 管线编排剧情。

跨度路由：
- 短期（<= 1 天）：走 tick 管线（7 步），生成即时事件；若有玩家瞬间动作则注入。
- 中期及以上（> 1 天）：走 time_jump 管线，time_skip_summarizer 生成中间时段多条事件 + 目标时刻事件。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from src.backend.agent import pipeline as tick_pipeline
from src.backend.agent import time_jump_pipeline
from src.backend.deepseek_client import chat_completion
from src.backend.storage.connection import default_save_manager

# 短期与中长期的分界：1 天（秒）
TICK_SPAN_LIMIT = 86400

# 模型未能解析出动作时长时回退的默认跨度（秒）
DEFAULT_ACTION_SPAN = 60


def estimate_action_span(player_action: str) -> int:
    """由模型判断玩家瞬间动作的最短合理执行时长（秒）。

    只计算动作本身所需的最短时间（忽略等待/赶路），解析失败时回退默认值。
    """
    variables = tick_pipeline._build_variables()
    system_prompt = (
        "你是游戏时间估算器。根据玩家动作判断其从开始到完成所需的"
        "最短合理执行时长（只算动作本身，忽略等待与赶路）。"
        '只输出一个 JSON：{"seconds": <整数秒>}，不要输出其他文字。'
    )
    user_prompt = (
        f"玩家瞬间动作：{player_action}\n"
        f"当前游戏时间：{variables.get('game_time', '')}\n"
        "请判断该动作的最短合理执行时长。"
    )
    try:
        resp = chat_completion(system_prompt, user_prompt, temperature=0.0, max_tokens=64)
        content = resp.get("content") or ""
        m = re.search(r'"seconds"\s*:\s*(\d+)', content)
        if m:
            return max(1, int(m.group(1)))
        parsed = json.loads(content)
        return max(1, int(parsed["seconds"]))
    except Exception:
        return DEFAULT_ACTION_SPAN


def advance(
    seconds: int,
    player_action: Optional[str] = None,
) -> Dict[str, Any]:
    """统一推进。

    seconds: 要推进的游戏秒数；若为 0 且提供了 player_action，则由模型估算最短执行时长。
    player_action: 玩家瞬间动作（可选，短期推进时注入主角决策）。
    """
    sm = default_save_manager()
    if not sm.active_save:
        raise RuntimeError("无激活存档")

    # 玩家瞬间动作：由模型判断其最短执行时长，作为推进跨度
    if player_action and player_action.strip() and seconds <= 0:
        seconds = estimate_action_span(player_action.strip())

    if seconds <= 0:
        raise RuntimeError("推进秒数必须为正数")

    if seconds > TICK_SPAN_LIMIT:
        # 中长期：时间跨越管线，补全中间 + 目标时刻
        result = time_jump_pipeline.time_jump(seconds)
        result["advance_mode"] = "jump"
    else:
        # 短期：tick 管线即时推演
        result = tick_pipeline.tick_once(seconds, 5, player_action)
        result["span_type"] = "tick"
        result.setdefault("advance_mode", "tick")

    result["seconds"] = seconds
    return result