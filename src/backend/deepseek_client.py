"""src.backend.deepseek_client — DeepSeek LLM 客户端（基于 OpenAI SDK）。

DeepSeek 兼容 OpenAI Chat Completions API，因此直接用 openai SDK。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from src.backend.env import load_backend_env

load_backend_env()

# 懒加载 OpenAI 客户端（避免无 API key 时 import 失败）
_client = None
_mock_mode = False


def _get_client():
    """获取 OpenAI 客户端。若无 API Key，进入 mock 模式。"""
    global _client, _mock_mode
    if _client is not None:
        return _client
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key or api_key.startswith("sk-xxx"):
        _mock_mode = True
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        return _client
    except ImportError:
        _mock_mode = True
        return None


def is_mock_mode() -> bool:
    """是否处于 mock 模式（无 API Key 或未安装 openai）。"""
    _get_client()
    return _mock_mode


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """同步调用 LLM。

    返回:
        {
            "content": str,                  # LLM 文本回复
            "tool_calls": List[Dict] | None, # 工具调用列表
            "raw": Any,                       # 原始响应
            "usage": Dict | None,             # token 统计
            "elapsed_ms": int,                # 耗时
            "mock": bool,                     # 是否为 mock 响应
        }
    """
    # 先调 is_mock_mode() 触发 _get_client() 初始化 _mock_mode 标志
    # （避免首次调用时 _mock_mode 还是 False 但 client 为 None 的竞态）
    if is_mock_mode():
        return {**_mock_response(system_prompt, user_prompt, tools), "mock": True}

    client = _get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: Dict[str, Any] = {
        "model": model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

    t0 = time.time()
    resp = client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
    elapsed_ms = int((time.time() - t0) * 1000)

    msg = resp.choices[0].message
    tool_calls = None
    if msg.tool_calls:
        tool_calls = []
        for tc in msg.tool_calls:
            args = tc.function.arguments
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                pass
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": args,
            })
    return {
        "content": msg.content or "",
        "tool_calls": tool_calls,
        "raw": resp,
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "total_tokens": resp.usage.total_tokens if resp.usage else 0,
        },
        "elapsed_ms": elapsed_ms,
        "mock": False,
    }


def _mock_response(
    system_prompt: str, user_prompt: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """无 API Key 时的模拟响应，便于开发测试。

    Mock 策略：识别 user_prompt 中的关键词，返回预设结构化结果。
    """
    content = ""
    tool_calls = None

    # 模拟 event_polisher
    if "润色" in user_prompt or "polish" in user_prompt.lower():
        content = f"（mock 润色）{user_prompt[:50]}...的优美版本"

    # 模拟 actor_decide：返回 JSON 决策
    elif "决策" in user_prompt or "decide" in user_prompt.lower():
        content = json.dumps({
            "action": "观察四周",
            "target": None,
            "intent": "保持警惕",
            "speech": "……",
            "private_thought": "此处似有不寻常",
        }, ensure_ascii=False)

    # 模拟 world_react：返回事件列表
    elif "事件" in user_prompt or "react" in user_prompt.lower():
        content = json.dumps({
            "events": [{
                "event_type": "narrative",
                "content_raw": "时间静静流逝",
                "importance": 1,
            }],
            "summary": "（mock）无事发生",
        }, ensure_ascii=False)

    # 模拟 memory_encoder
    elif "记忆" in user_prompt or "encode" in user_prompt.lower():
        content = json.dumps({
            "memory_raw": user_prompt[:100],
            "depth": 3,
            "correctness": 80,
            "perspective_bias": "（mock）",
        }, ensure_ascii=False)

    # 模拟 time_skip_summarizer
    elif "时间跨越" in user_prompt or "time_skip" in user_prompt.lower():
        content = json.dumps({
            "summary": f"（mock）这段时间过去了，世界继续运转。",
            "milestones": [
                {"tick_offset": 0, "content": "起点"},
                {"tick_offset": 1, "content": "中点"},
                {"tick_offset": 2, "content": "终点"},
            ],
        }, ensure_ascii=False)

    else:
        content = f"（mock 模式）未识别请求类型。system_prompt 长度={len(system_prompt)}, user_prompt 前80字符：{user_prompt[:80]}"

    return {
        "content": content,
        "tool_calls": tool_calls,
        "raw": None,
        "usage": {
            "prompt_tokens": len(system_prompt) // 3,
            "completion_tokens": len(content) // 3,
            "total_tokens": (len(system_prompt) + len(content)) // 3,
        },
        "elapsed_ms": 0,
    }
