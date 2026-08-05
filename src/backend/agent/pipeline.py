"""src.backend.agent.pipeline — LLM 管线编排。

正常 tick 管线（7 步）：
1. 黑词过滤（content_filter）
2. 记忆衰减（memory_decayer）
3. 任务/纲领检测（quest_monitor + agenda_monitor）
4. NPC 决策（actor_decide，对每个活跃角色）
5. 世界反应合成事件（world_react）
6. 事件编码 + 记忆生成（memory_encoder）
7. 事件润色展示（event_polisher）
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.backend import deepseek_client
from src.backend.agent.skill.loader import render_skill
from src.backend.agent.tool.base import ToolManager
from src.backend.env import load_backend_env
from src.backend.service import memory_service, world_service
from src.backend.storage import models
from src.backend.storage.connection import default_save_manager

load_backend_env()


# ============================================================
# 变量注入：从存档元信息 + 全局配置构造 variables
# ============================================================

def _build_variables() -> Dict[str, Any]:
    sm = default_save_manager()
    if not sm.active_save:
        return {}
    meta = sm.get_meta()
    return {
        "tick_num": meta.get("tick_num", 0),
        "game_time": meta.get("game_time", ""),
        "era_name": meta.get("era_name", ""),
        "script_name": meta.get("script_name", ""),
        "role_name": (sm.get_protagonist() or {}).get("name", ""),
        "polish_length": os.environ.get("POLISH_LENGTH", "medium"),
        "gore_enabled": os.environ.get("GORE_ENABLED", "0"),
        "adult_content_enabled": os.environ.get("ADULT_CONTENT_ENABLED", "0"),
    }


# ============================================================
# 单 skill 调用封装
# ============================================================

def call_skill(
    skill_name: str,
    user_prompt: str = "",
    variables: Optional[Dict[str, Any]] = None,
    extra_tools: Optional[List[str]] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """调用一个 skill：渲染 system_prompt + 注入变量 + 调 LLM。

    自动把 skill 配置的 tools + extra_tools 暴露给 LLM。
    若 LLM 返回 tool_calls，自动执行并把结果回填。
    """
    variables = {**_build_variables(), **(variables or {})}

    # 渲染 skill system prompt
    system_prompt = render_skill(skill_name, variables)

    # 收集工具 schema
    from src.backend.agent.skill.loader import get_skill
    fs = get_skill(skill_name)
    tool_names: List[str] = []
    if fs:
        tool_names.extend(fs.tools)
    if extra_tools:
        tool_names.extend(extra_tools)
    tools_schema = ToolManager.schemas_for(tool_names)

    # 调 LLM（启用完整 tool calling 循环：LLM 调工具→拿结果→再推理→直到产出最终回答）
    def _tool_executor(name: str, args: Dict[str, Any]) -> Any:
        """LLM 工具执行回调：把工具调用委托给 ToolManager。"""
        return ToolManager.execute(name, args)

    resp = deepseek_client.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt or "(无 user prompt，按 system 指令执行)",
        tools=tools_schema if tools_schema else None,
        temperature=temperature,
        max_tokens=max_tokens,
        max_tool_rounds=5,
        tool_executor=_tool_executor if tools_schema else None,
    )

    # tool_results 由 deepseek_client 内部已执行并收集
    tool_results: List[Dict[str, Any]] = resp.get("tool_results", [])

    # 尝试解析 content 为 JSON
    content = resp.get("content", "")
    parsed = None
    if content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 容错：尝试提取 JSON 块
            import re
            m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass

    return {
        "skill": skill_name,
        "content": content,
        "parsed": parsed,
        "tool_calls": resp.get("tool_calls"),
        "tool_results": tool_results,
        "usage": resp.get("usage"),
        "elapsed_ms": resp.get("elapsed_ms"),
        "rounds": resp.get("rounds", 1),
        "mock": deepseek_client.is_mock_mode(),
    }


# ============================================================
# 正常 tick 管线（7 步）
# ============================================================

def tick_once(seconds: int = 60, max_actors: int = 5) -> Dict[str, Any]:
    """推进 1 tick 的完整管线。

    步骤：
    1. 元信息推进（tick +1, game_time += seconds）
    2. 记忆衰减（对所有有记忆的角色）
    3. 任务/纲领监控
    4. NPC 决策（对 max_actors 个活跃角色）
    5. 世界反应合成事件
    6. 事件编码为记忆
    7. 事件润色

    返回每步的执行摘要。
    """
    sm = default_save_manager()
    if not sm.active_save:
        raise RuntimeError("无激活存档")

    variables = _build_variables()
    trace: List[Dict[str, Any]] = []

    # ---- Step 1: 推进元信息 ----
    meta = world_service.tick_once(seconds)
    trace.append({"step": 1, "name": "advance_tick", "meta": meta})

    # ---- Step 2: 记忆衰减 ----
    # 取所有有记忆的角色
    sm_db = sm._conn  # type: ignore[union-attr]
    char_ids_with_mem = [
        row["char_id"] for row in sm_db.execute(
            "SELECT DISTINCT char_id FROM memories LIMIT 100"
        ).fetchall()
    ]
    decayed_total = 0
    for cid in char_ids_with_mem[:20]:  # 限制每 tick 处理的角色数
        r = memory_service.decay_memories(cid, ticks_passed=1)
        decayed_total += r["decayed_count"]
    trace.append({"step": 2, "name": "memory_decay", "chars": len(char_ids_with_mem), "decayed": decayed_total})

    # ---- Step 3: 任务/纲领监控 ----
    qm_result = call_skill("quest_monitor", user_prompt="检查所有 in_progress 任务")
    trace.append({"step": 3, "name": "quest_monitor", "mock": qm_result["mock"], "tool_calls": len(qm_result.get("tool_results", []))})

    am_result = call_skill("agenda_monitor", user_prompt="检查所有 active 纲领")
    trace.append({"step": 3.1, "name": "agenda_monitor", "mock": am_result["mock"]})

    # ---- Step 4: NPC 决策 ----
    # 取活跃角色（有位置的 + 非死亡的）
    active_chars = models.Character.list(
        where="dead_at_tick IS NULL", order_by="importance DESC", limit=max_actors
    )
    decisions: List[Dict[str, Any]] = []
    for c in active_chars:
        scene_vars = {**variables, "role_name": c.name, "scene_description": c.status or "正常"}
        decision = call_skill(
            "actor_decide",
            user_prompt=f"角色：{c.name}\n状态：{c.status or '正常'}\n请决策本 tick 行动。",
            variables=scene_vars,
        )
        decisions.append({"char_id": c.id, "char_name": c.name, "decision": decision.get("parsed") or decision.get("content")})
    trace.append({"step": 4, "name": "actor_decide", "actors": len(decisions), "decisions": decisions})

    # ---- Step 5: 世界反应合成事件 ----
    decisions_json = json.dumps(decisions, ensure_ascii=False, default=str)
    wr_result = call_skill(
        "world_react",
        user_prompt=f"本 tick 角色决策列表：\n{decisions_json}\n请合成世界事件。",
    )
    events_created: List[int] = []

    # 5a. 新模式：LLM 通过 world_create_event 工具直接创建事件
    for tr in wr_result.get("tool_results", []):
        if tr.get("tool") == "world_create_event":
            result = tr.get("result", {})
            if isinstance(result, dict):
                # create_event 返回 {"id": ..., ...}；失败时返回 {"error": ...}
                if result.get("id"):
                    events_created.append(result["id"])
                elif result.get("error"):
                    trace.append({"step": 5, "error": f"world_create_event 失败: {result['error']}"})

    # 5b. 兼容旧模式：LLM 在 content 中返回 JSON {"events": [...]}
    if wr_result.get("parsed") and isinstance(wr_result["parsed"], dict):
        for ev in wr_result["parsed"].get("events", []):
            try:
                e = world_service.create_event(
                    event_type=ev.get("event_type", "narrative"),
                    content_raw=ev.get("content_raw", ""),
                    content_polished=ev.get("content_polished"),
                    location_map_id=ev.get("location_map_id"),
                    importance=ev.get("importance", 3),
                    participants=ev.get("participants"),
                )
                events_created.append(e["id"])
            except Exception as ex:
                trace.append({"step": 5, "error": f"事件创建失败: {ex}"})
    trace.append({
        "step": 5, "name": "world_react",
        "events_created": events_created,
        "mock": wr_result["mock"],
        "tool_results_count": len(wr_result.get("tool_results", [])),
        "rounds": wr_result.get("rounds", 1),
    })

    # ---- Step 6: 事件编码为记忆 ----
    encoded_total = 0
    for eid in events_created:
        try:
            mems = memory_service.encode_event_to_memories(eid)
            encoded_total += len(mems)
        except Exception:
            pass
    trace.append({"step": 6, "name": "memory_encode", "encoded": encoded_total})

    # ---- Step 7: 事件润色 ----
    # 大部分情况下，LLM 在 step 5 通过 world_create_event 工具创建事件时
    # 已经传入了 content_polished 字段，这里只对未润色的事件做兜底。
    polished = 0
    for eid in events_created:
        ev = models.Event.get(eid)
        if ev and not ev.content_polished:
            ep_result = call_skill(
                "event_polisher",
                user_prompt=f"事件 raw：{ev.content_raw}\n请润色为 polished 文本。",
            )
            # 7a. 优先使用 LLM 在 content 中的回复
            polished_text = ep_result.get("content", "").strip()
            # 去掉 markdown 代码块包裹
            if polished_text.startswith("```"):
                import re
                m = re.search(r"```(?:\w+)?\s*([\s\S]+?)\s*```", polished_text)
                if m:
                    polished_text = m.group(1).strip()
            if polished_text:
                models.Event.update(eid, content_polished=polished_text)
                polished += 1
            else:
                # 7b. LLM 可能通过 world_polish_event 工具直接润色了
                for tr in ep_result.get("tool_results", []):
                    if tr.get("tool") == "world_polish_event":
                        polished += 1
                        break
    # 统计事件创建时已经带 polished 的数量
    pre_polished = sum(
        1 for eid in events_created
        if (ev := models.Event.get(eid)) and ev.content_polished
    )
    trace.append({"step": 7, "name": "event_polisher", "polished": polished, "pre_polished": pre_polished})

    return {
        "tick": meta["tick_num"],
        "game_time": meta["game_time"],
        "trace": trace,
        "events_created": events_created,
        "decisions": decisions,
        "mock_mode": deepseek_client.is_mock_mode(),
    }
