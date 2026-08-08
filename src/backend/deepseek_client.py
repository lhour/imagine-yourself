"""src.backend.deepseek_client — DeepSeek LLM 客户端（基于 OpenAI SDK）。

DeepSeek 兼容 OpenAI Chat Completions API，因此直接用 openai SDK。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from src.backend.env import load_backend_env
from src.backend.agent import trace

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


# ---------- Prompt prefix 缓存（适配 DeepSeek 缓存机制） ----------
# DeepSeek 对「完全相同的前缀 token 序列」会自动复用缓存，
# 因此我们在客户端记录「上一次 system_prompt 的 hash 与长度」，
# 若连续两次请求的前缀完全一致，则命中 cache。
# 这使 pipeline 各 skill 在 A/B 段稳定时享受缓存命中。
_last_prefix_key: Optional[str] = None
_last_prefix_len: int = 0


def _make_prefix_key(system_prompt: str, user_prompt: str) -> str:
    """基于 system 前缀（前 512 字符）构造 cache key。

    只取 system 前缀是因为 DeepSeek 的 prefix cache 仅对开头相同的段生效；
    user_prompt 经常变化，不适合拿来做 key。
    """
    head = system_prompt[:512]
    h = hashlib.md5(head.encode("utf-8")).hexdigest()
    return f"{len(system_prompt)}:{len(user_prompt)}:{h}"


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
        mock_resp = _mock_response(system_prompt, user_prompt, tools)
        with trace.span(f"model_call#1", "model_call",
                        system_prompt=system_prompt, user_prompt=user_prompt,
                        temperature=temperature, max_tokens=max_tokens, model="mock") as ms:
            ms.record(output=mock_resp.get("content"), think=mock_resp.get("reasoning_content"),
                      usage=mock_resp.get("usage"), mock=True)
        return {**mock_resp, "mock": True, "tool_results": [], "rounds": 1,
                "llm_rounds": [{
                    "round": 1, "mock": True,
                    "prompt": {"system": system_prompt, "user": user_prompt},
                    "think": mock_resp.get("reasoning_content"),
                    "output": mock_resp.get("content"),
                    "tool_calls_requested": [],
                }]}

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

    # ---- Prompt prefix cache 跟踪 ----
    global _last_prefix_key
    prefix_key = _make_prefix_key(system_prompt, user_prompt)
    prefix_hit = (_last_prefix_key is not None and _last_prefix_key == prefix_key)
    _last_prefix_key = prefix_key

    t0 = time.time()
    all_tool_calls: List[Dict[str, Any]] = []
    all_tool_results: List[Dict[str, Any]] = []
    total_usage = {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0,
    }
    last_resp = None
    rounds = 0
    llm_rounds: List[Dict[str, Any]] = []

    while rounds < max_tool_rounds:
        rounds += 1
        with trace.span(f"model_call#{rounds}", "model_call",
                        system_prompt=system_prompt, user_prompt=user_prompt,
                        temperature=temperature, max_tokens=max_tokens,
                        model=kwargs.get("model")) as ms:
            resp = client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
            last_resp = resp
            msg = resp.choices[0].message

            # 累计 usage
            if resp.usage:
                total_usage["prompt_tokens"] += resp.usage.prompt_tokens
                total_usage["completion_tokens"] += resp.usage.completion_tokens
                total_usage["total_tokens"] += resp.usage.total_tokens
                # 缓存命中统计（DeepSeek 扩展字段）
                total_usage["prompt_cache_hit_tokens"] += getattr(resp.usage, "prompt_cache_hit_tokens", 0) or 0
                total_usage["prompt_cache_miss_tokens"] += getattr(resp.usage, "prompt_cache_miss_tokens", 0) or 0

            round_think = getattr(msg, "reasoning_content", None)
            round_output = msg.content or ""
            round_tool_reqs = [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (msg.tool_calls or [])
            ]
            ms.record(think=round_think, output=round_output,
                      usage=dict(resp.usage) if resp.usage else None,
                      tool_calls_requested=round_tool_reqs)
            llm_rounds.append({
                "round": rounds,
                "prompt": {"system": system_prompt, "user": user_prompt},
                "think": round_think,
                "output": round_output,
                "tool_calls_requested": round_tool_reqs,
            })

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

                # 执行工具（记录为 tool_call span）
                with trace.span(f"tool:{tc_name}", "tool_call", arguments=tc_args) as ts:
                    tool_result_value: Any = None
                    if tool_executor is not None:
                        try:
                            tool_result_value = tool_executor(tc_name, tc_args)
                        except Exception as ex:
                            tool_result_value = {"error": f"{type(ex).__name__}: {ex}"}
                    else:
                        tool_result_value = {"_skipped": "no tool_executor provided"}
                    ts.record(result=tool_result_value)

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

    # ---- 兜底：若 LLM 仍未产出文本，再发一次无工具的请求强制输出。
    # 覆盖两种空 content 场景：
    #   1) 只调工具不回复（all_tool_results 非空）→ 基于工具结果合成
    #   2) 推理模型把全部 completion token 耗在 reasoning_content 上、
    #      实际 content 为空（all_tool_results 可能为空）→ 给更多 token
    #      并提示「直接输出、勿过度推理」让模型产出文本。
    if not final_content and client is not None:
        if all_tool_results:
            synth_user = ("（工具调用阶段已结束）请基于以上工具调用获取的信息，"
                          "直接输出最终结果。不要再调用任何工具，直接以文本形式回复。")
        else:
            synth_user = ("你刚才的回复因推理过长耗尽了输出 token，导致实际内容为空。"
                          "请基于你已有的思考，直接以文本形式输出最终结果，"
                          "不要再过度推理，简明扼要地给出答案。")
        messages.append({"role": "user", "content": synth_user})
        # 合成调用放宽 max_tokens，给推理模型留出 reasoning + content 的空间。
        # 推理模型会把大量 token 花在 reasoning_content 上（实测 4096 全耗在推理），
        # 因此至少给 8192，确保推理完毕后还有余量输出实际内容。
        synth_max_tokens = max(max_tokens + 4096, 8192)
        final_kwargs = {
            "model": kwargs.get("model"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": synth_max_tokens,
            # 不传 tools，强制纯文本回复
        }
        with trace.span(f"model_call#final", "model_call",
                        system_prompt=system_prompt, user_prompt="(synthesis)",
                        temperature=temperature, max_tokens=synth_max_tokens,
                        model=final_kwargs["model"]) as ms:
            synth_resp = client.chat.completions.create(**final_kwargs)
            last_resp = synth_resp
            final_msg = synth_resp.choices[0].message
            final_content = final_msg.content or ""
            reasoning_content = getattr(final_msg, "reasoning_content", None)
            if synth_resp.usage:
                total_usage["prompt_tokens"] += synth_resp.usage.prompt_tokens
                total_usage["completion_tokens"] += synth_resp.usage.completion_tokens
                total_usage["total_tokens"] += synth_resp.usage.total_tokens
            ms.record(think=reasoning_content, output=final_content,
                      usage=dict(synth_resp.usage) if synth_resp.usage else None,
                      tool_calls_requested=[])
            llm_rounds.append({
                "round": rounds + 1,
                "prompt": {"system": system_prompt, "user": synth_user},
                "think": reasoning_content,
                "output": final_content,
                "tool_calls_requested": [],
            })
            rounds += 1
        elapsed_ms = int((time.time() - t0) * 1000)

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
        "llm_rounds": llm_rounds,
        "prefix_hit": prefix_hit,
        "prefix_key": prefix_key,
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
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": len(system_prompt) // 3,
        },
        "elapsed_ms": 0,
        "mock": True,
        "rounds": 1,
    }


# ============================================================
# Embedding 接口（供 vector_store / knowledge 模块调用）
# ============================================================

_DEFAULT_EMBEDDING_MODEL = os.environ.get(
    "DEEPSEEK_EMBEDDING_MODEL", "text-embedding-3-small"
)
_DEFAULT_EMBEDDING_DIM = int(os.environ.get("DEEPSEEK_EMBEDDING_DIM", "1536"))


def embed(
    text: str,
    *,
    model: Optional[str] = None,
    dim: Optional[int] = None,
) -> List[float]:
    """调用 embedding 接口把文本转为向量。

    - 无 API key / mock 模式下返回伪随机向量（hash-based，便于本地调试）。
    - 生产环境走 DeepSeek Embeddings API（兼容 openai 格式）。
    """
    text = (text or "").strip()
    target_dim = dim or _DEFAULT_EMBEDDING_DIM
    if not text:
        return [0.0] * target_dim

    if is_mock_mode():
        return _fake_embedding(text, target_dim)

    client = _get_client()
    if client is None:
        return _fake_embedding(text, target_dim)

    emb_model = model or _DEFAULT_EMBEDDING_MODEL
    try:
        resp = client.embeddings.create(model=emb_model, input=text)
        if resp and resp.data:
            vec = resp.data[0].embedding
            out = [float(v) for v in vec]
            if len(out) != target_dim:
                # 维度对齐（截断或补零）
                if len(out) > target_dim:
                    out = out[:target_dim]
                else:
                    out = out + [0.0] * (target_dim - len(out))
            return out
    except Exception:
        # 失败时降级为伪随机，避免阻断上层
        pass
    return _fake_embedding(text, target_dim)


def _fake_embedding(text: str, dim: int) -> List[float]:
    """基于 hash 的伪随机 embedding，保证同文本稳定。"""
    h = hashlib.md5(text.encode("utf-8")).digest()
    vec: List[float] = []
    while len(vec) < dim:
        h = hashlib.md5(h).digest()
        vec.extend(((b / 255.0) - 0.5) * 2.0 for b in h)
    return vec[:dim]


def embed_batch(
    texts: List[str],
    *,
    model: Optional[str] = None,
    dim: Optional[int] = None,
) -> List[List[float]]:
    """批量 embedding。mock 模式下对每条单独走 embed() 即可。"""
    if not texts:
        return []
    if is_mock_mode():
        return [embed(t, model=model, dim=dim) for t in texts]

    client = _get_client()
    if client is None:
        return [embed(t, model=model, dim=dim) for t in texts]

    emb_model = model or _DEFAULT_EMBEDDING_MODEL
    try:
        resp = client.embeddings.create(model=emb_model, input=texts)
        if resp and resp.data:
            # 按 index 排序（SDK 返回可能乱序）
            data = sorted(resp.data, key=lambda d: d.index)
            target_dim = dim or _DEFAULT_EMBEDDING_DIM
            out: List[List[float]] = []
            for d in data:
                vec = [float(v) for v in d.embedding]
                if len(vec) != target_dim:
                    if len(vec) > target_dim:
                        vec = vec[:target_dim]
                    else:
                        vec = vec + [0.0] * (target_dim - len(vec))
                out.append(vec)
            return out
    except Exception:
        pass
    return [embed(t, model=model, dim=dim) for t in texts]


# ============ 兼容层：get_llm_client ============

class _LLMClientWrapper:
    """兼容 drama_generator.py 的 LLM 客户端包装器。"""

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        """简化版 chat_completion，返回字符串内容。"""
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            elif msg.get("role") == "user":
                user_prompt = msg.get("content", "")

        result = chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )
        return result.get("content", "")


def get_llm_client() -> _LLMClientWrapper:
    """获取 LLM 客户端（兼容旧版 API）。"""
    return _LLMClientWrapper()
