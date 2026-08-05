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
    max_tool_rounds: int = 5,
    tool_executor: Optional[Any] = None,
) -> Dict[str, Any]:
    """同步调用 LLM。

    支持完整的 tool calling 循环：
    1. 调用 LLM
    2. 若返回 tool_calls，用 tool_executor 执行每个工具
    3. 把 tool 结果作为 tool message 加入 messages
    4. 再次调用 LLM
    5. 重复直到 LLM 不再返回 tool_calls 或达到 max_tool_rounds

    Args:
        tools: OpenAI function schema 列表
        tool_choice: "auto" / "none" / "required"
        max_tool_rounds: 最大工具调用轮次（防死循环）
        tool_executor: 可调用对象 tool_executor(name, args) -> result，
                       若为 None 则不执行工具（只返回 raw tool_calls）

    返回:
        {
            "content": str,                  # 最终 LLM 文本回复（最后一轮）
            "reasoning_content": str | None, # 思考过程（V4 Flash 特有）
            "tool_calls": List[Dict] | None, # 累计工具调用列表
            "tool_results": List[Dict],      # 工具执行结果（每项 {name, arguments, result}）
            "raw": Any,                       # 最后一次原始响应
            "usage": Dict | None,            # 累计 token 统计
            "elapsed_ms": int,                # 总耗时
            "mock": bool,                     # 是否为 mock 响应
            "rounds": int,                    # 实际调用 LLM 的轮数
        }
    """
    # 先调 is_mock_mode() 触发 _get_client() 初始化 _mock_mode 标志
    # （避免首次调用时 _mock_mode 还是 False 但 client 为 None 的竞态）
    if is_mock_mode():
        return {**_mock_response(system_prompt, user_prompt, tools), "mock": True, "tool_results": [], "rounds": 1}

    client = _get_client()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: Dict[str, Any] = {
        "model": model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

    t0 = time.time()
    all_tool_calls: List[Dict[str, Any]] = []
    all_tool_results: List[Dict[str, Any]] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    last_resp = None
    rounds = 0

    while rounds < max_tool_rounds:
        rounds += 1
        resp = client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
        last_resp = resp
        msg = resp.choices[0].message

        # 累计 usage
        if resp.usage:
            total_usage["prompt_tokens"] += resp.usage.prompt_tokens
            total_usage["completion_tokens"] += resp.usage.completion_tokens
            total_usage["total_tokens"] += resp.usage.total_tokens

        # 若无 tool_calls，已经得到最终回答，退出循环
        if not msg.tool_calls:
            break

        # 有 tool_calls：执行并把结果加入 messages
        # 1) 把 assistant 的 tool_calls 消息加入历史
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        # 2) 执行每个工具，加入对应的 tool 消息
        for tc in msg.tool_calls:
            tc_name = tc.function.name
            try:
                tc_args = tc.function.arguments
                tc_args = json.loads(tc_args) if isinstance(tc_args, str) else tc_args
            except json.JSONDecodeError:
                tc_args = {}

            all_tool_calls.append({"id": tc.id, "name": tc_name, "arguments": tc_args})

            # 执行工具
            tool_result_value: Any = None
            if tool_executor is not None:
                try:
                    tool_result_value = tool_executor(tc_name, tc_args)
                except Exception as ex:
                    tool_result_value = {"error": f"{type(ex).__name__}: {ex}"}
            else:
                tool_result_value = {"_skipped": "no tool_executor provided"}

            all_tool_results.append({
                "tool": tc_name,
                "arguments": tc_args,
                "result": tool_result_value,
            })

            # 把工具结果作为 tool role 消息加入对话
            # OpenAI 格式要求 tool role 的 content 是字符串
            try:
                tool_content = json.dumps(tool_result_value, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                tool_content = str(tool_result_value)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_content,
            })

        # 更新 messages 给下一轮（已就地修改 messages）
        kwargs["messages"] = messages
        # 下一轮不再需要显式 tool_choice（让模型自主决定）
        if "tool_choice" in kwargs and tool_choice != "required":
            kwargs.pop("tool_choice", None)

    elapsed_ms = int((time.time() - t0) * 1000)

    # 取最后一轮的 message 作为最终回答
    final_msg = last_resp.choices[0].message if last_resp else None
    final_content = (final_msg.content if final_msg and final_msg.content else "") or ""
    reasoning_content = getattr(final_msg, "reasoning_content", None) if final_msg else None

    return {
        "content": final_content,
        "reasoning_content": reasoning_content,
        "tool_calls": all_tool_calls or None,
        "tool_results": all_tool_results,
        "raw": last_resp,
        "usage": total_usage,
        "elapsed_ms": elapsed_ms,
        "mock": False,
        "rounds": rounds,
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
        "reasoning_content": None,
        "tool_calls": tool_calls,
        "tool_results": [],
        "raw": None,
        "usage": {
            "prompt_tokens": len(system_prompt) // 3,
            "completion_tokens": len(content) // 3,
            "total_tokens": (len(system_prompt) + len(content)) // 3,
        },
        "elapsed_ms": 0,
        "mock": True,
        "rounds": 1,
    }
