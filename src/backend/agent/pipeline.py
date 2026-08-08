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
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from src.backend import deepseek_client
from src.backend.agent import trace
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

# 模块级缓存：stable_context_version → (stable_vars_dict, stable_hash)
# 用于跨 skill 调用复用 A/B 段文本，最大化命中 DeepSeek prefix cache
_stable_context_cache: Dict[str, Tuple[Dict[str, str], str]] = {}


def _build_variables() -> Dict[str, Any]:
    sm = default_save_manager()
    if not sm.active_save:
        return {}
    meta = sm.get_meta()
    # 从全局配置读取润色偏好（与 UI 一致），而非环境变量
    from src.backend.http.deps import get_global_config
    sim = get_global_config().get("simulation", {})

    # 基础变量（保留旧字段以兼容旧 prompt 模板）
    basic: Dict[str, Any] = {
        "tick_num": meta.get("tick_num", 0),
        "game_time": meta.get("game_time", ""),
        "era_name": meta.get("era_name", ""),
        "script_name": meta.get("script_name", ""),
        "role_name": (sm.get_protagonist() or {}).get("name", ""),
        "polish_mode": sim.get("polish_mode", "none"),
    }

    # v5：拼装分层上下文（A/B 稳定段 + 玩法指令块 + 动态实体列表）
    try:
        gameplay_options = sm.get_gameplay_options()
        version_key = str(meta.get("stable_context_version", 0))
        cache_key = f"{sm.active_save}:{version_key}:{meta.get('tick_num', 0) // 100}"

        cached = _stable_context_cache.get(cache_key)
        if cached is not None:
            stable_vars, stable_hash = cached
        else:
            from src.backend.agent.context_packager import pack_context_for_skill
            stable_vars = pack_context_for_skill(sm, gameplay_options, "_pipeline_")
            # 计算稳定段 hash，供 DeepSeek prefix cache 识别
            import hashlib
            stable_text = stable_vars.get("stable_context", "")
            stable_hash = hashlib.md5(
                (stable_text + stable_vars.get("gameplay_style_block", "")).encode("utf-8")
            ).hexdigest()[:16]
            _stable_context_cache[cache_key] = (stable_vars, stable_hash)
            # 控制缓存大小
            if len(_stable_context_cache) > 32:
                # 清除最旧的
                oldest = next(iter(_stable_context_cache))
                _stable_context_cache.pop(oldest, None)

        basic.update(stable_vars)
        basic["_stable_hash"] = stable_hash
    except Exception as ex:
        # D2 修订：分层注入失败时降级为基础变量，但不再静默——告警 + 指标上报
        # （沿用降级行为，但让运维感知到打包异常，便于排查"上下文丢失"类问题）
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "stable_context 打包失败，降级为基础变量: %s", ex, exc_info=False
        )
        try:
            # 上报指标到 trace（若有活跃 trace）
            from src.backend.agent import trace as _trace
            _trace.add_root_data(stable_context_pack_failed=True, pack_error=str(ex)[:200])
        except Exception:
            pass

    return basic


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

    with trace.span(f"skill:{skill_name}", "skill_call", skill_name=skill_name) as ss:
        resp = deepseek_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt or "(无 user prompt，按 system 指令执行)",
            tools=tools_schema if tools_schema else None,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_rounds=5,
            tool_executor=_tool_executor if tools_schema else None,
        )
        usage = resp.get("usage") or {}
        ss.record(
            rounds=resp.get("rounds", 1),
            mock=deepseek_client.is_mock_mode(),
            usage=usage,
            prefix_hit=resp.get("prefix_hit", False),
            prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens", 0),
            prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens", 0),
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
# 润色风格选择（每个风格独立成一个 polisher_<style> skill）
# ============================================================

_POLISH_STYLES = {
    "default", "poetic", "grimdark", "warm", "epic",
    "humorous", "concise", "horror", "classical", "cyberpunk",
}


def _select_polish_style(content: str) -> str:
    """由模型判断当前文案最适合的润色风格 key。"""
    try:
        r = call_skill(
            "polish_style_selector",
            user_prompt=f"事件原文：\n{content}",
            temperature=0.2,
            max_tokens=64,
        )
        parsed = r.get("parsed")
        if isinstance(parsed, dict):
            s = str(parsed.get("style", "")).strip()
            if s:
                return s
    except Exception:
        pass
    return "default"


# ============================================================
# 正常 tick 管线（7 步）
# ============================================================

def tick_once(seconds: int = 60, max_actors: int = 5, player_action: Optional[str] = None) -> Dict[str, Any]:
    """推进 1 tick 的完整管线（v3 7 步，**已弃用**）。

    .. deprecated::
        v3 管线已被 C 阶段 orchestrator（pipeline_orchestrator.tick_once_orchestrated）
        + v4 五节点管线（pipeline_v4.tick_once_v4）取代。
        本函数保留仅为兼容旧测试 / 回放，新代码应调 orchestrator 入口。
        内部已委托到 v4 + orchestrator，不再跑 v3 7 步逻辑。

    返回每步的执行摘要。
    """
    # D1 修订：v3 7 步管线已弃用，统一委托到 orchestrator（v4 + 编排层）
    import logging as _log
    _log.getLogger(__name__).warning(
        "pipeline.tick_once (v3) 已弃用，委托到 pipeline_orchestrator；"
        "请改用 /api/agent/tick（已自动走 orchestrator）或直接调 "
        "pipeline_orchestrator.tick_once_orchestrated"
    )
    from src.backend.agent import pipeline_orchestrator as _orch
    return _orch.tick_once_orchestrated(seconds, max_actors, player_action)

    variables = _build_variables()
    steps: List[Dict[str, Any]] = []
    events_created: List[int] = []  # 前移到开头，Step 1.5 / Step 5 都会写入本列表

    def _run_parallel(fns: List[Any], max_workers: int = 8) -> List[Any]:
        """并发执行一批无参函数，返回结果（保持提交顺序）。

        使用 trace.capture_context() 确保 ContextVar 在子线程中正确传播。
        """
        if len(fns) <= 1:
            return [f() for f in fns]
        # 捕获当前 ContextVar 上下文
        ctx = trace.capture_context()
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(trace.run_in_context, ctx, f) for f in fns]
            return [f.result() for f in futures]

    # ---- Step 1: 推进元信息 ----
    with trace.span("advance_tick", "step", step=1):
        meta = world_service.tick_once(seconds)
    steps.append({"step": 1, "name": "advance_tick", "meta": meta})

    # ---- Step 1.5: 玩家瞬间动作（可选）—— 先用 player_action skill 推演，再落盘 ----
    player_event_id: Optional[int] = None
    player_action_result: Optional[Dict[str, Any]] = None
    if player_action and player_action.strip():
        with trace.span("player_action", "step", step=1.5):
            proto = sm.get_protagonist()
            proto_name = proto.get("name", "主角") if proto else "主角"
            scene_vars = {
                **variables,
                "role_name": proto_name,
                "scene_description": (proto or {}).get("status") or "正常",
            }
            # 调用 player_action skill 推演动作影响
            pa_result = call_skill(
                "player_action",
                user_prompt=(
                    f"角色：{proto_name}\n状态：{(proto or {}).get('status') or '正常'}\n"
                    f"玩家瞬间动作：{player_action.strip()}\n"
                    f"请基于该动作推演本 tick 主角的行动与影响，并在 possible_events 中给出可直接写入世界的事件候选。"
                ),
                variables=scene_vars,
            )
            player_action_result = pa_result
            parsed = pa_result.get("parsed") or {}

            # 1.5a 优先写入 skill 提供的 possible_events（LLM 已综合考虑场景影响）
            proto_id_val = proto.get("id") if proto else None
            for ev in parsed.get("possible_events", []) or []:
                try:
                    # participants 兜底：如果没指定，默认加上主角（作为 first_hand 直接参与者）
                    ev_parts = ev.get("participants")
                    if (not ev_parts) and proto_id_val:
                        ev_parts = [{"type": "character", "id": proto_id_val, "role": "first_hand", "perception": ev.get("content_raw", "")}]
                    pe = world_service.create_event(
                        event_type=ev.get("event_type", "narrative"),
                        content_raw=ev.get("content_raw", ""),
                        content_polished=ev.get("content_polished"),
                        location_map_id=ev.get("location_map_id"),
                        importance=ev.get("importance", 5),
                        participants=ev_parts,
                    )
                    if pe.get("id"):
                        if player_event_id is None:
                            player_event_id = pe["id"]
                        events_created.append(pe["id"])
                except Exception as ex:
                    steps.append({"step": 1.5, "error": f"possible_event 创建失败: {ex}"})

            # 1.5b 兜底：如果 skill 没给出任何 possible_events，创建一条最基础的 player_action 事件
            if player_event_id is None:
                action_summary = parsed.get("action_summary") or player_action.strip()
                default_parts = [{"type": "character", "id": proto_id_val, "role": "first_hand", "perception": action_summary}] if proto_id_val else None
                pe = world_service.create_event(
                    event_type="player_action",
                    content_raw=action_summary,
                    importance=5,
                    participants=default_parts,
                )
                player_event_id = pe["id"]
                events_created.append(pe["id"])

        steps.append({
            "step": 1.5,
            "name": "player_action",
            "event_id": player_event_id,
            "action_summary": (player_action_result.get("parsed") or {}).get("action_summary"),
            "scene_beats": (player_action_result.get("parsed") or {}).get("scene_beats"),
            "possible_events_count": len((player_action_result.get("parsed") or {}).get("possible_events", []) or []),
            "mock": player_action_result.get("mock"),
        })

    # ---- Step 2: 记忆衰减 —— 先走纯代码基础衰减（保证性能），再调用 skill 精细处理极端失真与完全遗忘 ----
    sm_db = sm._conn  # type: ignore[union-attr]
    char_ids_with_mem = [
        row["char_id"] for row in sm_db.execute(
            "SELECT DISTINCT char_id FROM memories LIMIT 100"
        ).fetchall()
    ]
    target_char_ids = char_ids_with_mem[:20]
    decayed_total = 0
    distorted_total = 0
    forgotten_total = 0
    md_skill_mock = False
    with trace.span("memory_decay", "step", step=2, chars=len(target_char_ids)):
        # Step 2a: 基础衰减（纯代码，对所有角色 memory_decay correctness/forget_prob）
        for cid in target_char_ids:
            r = memory_service.decay_memories(cid, ticks_passed=1)
            decayed_total += r["decayed_count"]

        # Step 2b: 调用 memory_decayer skill，精细处理极端失真（correctness<30）与完全遗忘
        # 只在有角色满足极端失真条件时才调 skill，省 token
        need_distort = sm_db.execute(
            "SELECT COUNT(*) AS c FROM memories WHERE correctness < 30 AND char_id IN ({})".format(
                ",".join("?" * len(target_char_ids))
            ),
            target_char_ids,
        ).fetchone()["c"]
        if need_distort or target_char_ids:
            md_user_prompt = (
                f"当前 tick：{meta.get('tick_num')}\n"
                f"目标角色 id 列表（共 {len(target_char_ids)} 个）：{target_char_ids}\n"
                f"满足极端失真阈值（correctness<30）的记忆条数：{need_distort}\n"
                "请执行衰减规则：\n"
                "1. 对 correctness<30 的记忆，挑选 1-3 条调用 memory_distort 工具做失真改写（不要全改，避免 token 爆炸）\n"
                "2. 对 forget_prob>0.95 且 depth<=2 的记忆，可视为完全遗忘（后续不召回）\n"
                "3. 返回 JSON 格式的统计结果，与 skill.md 一致。\n"
            )
            md_result = call_skill(
                "memory_decayer",
                user_prompt=md_user_prompt,
                temperature=0.3,
            )
            md_skill_mock = md_result.get("mock", False)
            md_parsed = md_result.get("parsed") or {}
            distorted_total += int(md_parsed.get("distorted_count", 0) or 0)
            forgotten_total += int(md_parsed.get("forgotten_count", 0) or 0)
            # 兜底：如果 skill 没有通过 tool 调用 memory_distort，按 skill 返回的 distorted_count 至少保证 decayed_count 正确
            distorted_total = max(distorted_total, sum(
                1 for tr in (md_result.get("tool_results") or [])
                if tr.get("tool") == "memory_distort"
            ))
    steps.append({
        "step": 2,
        "name": "memory_decay",
        "chars": len(target_char_ids),
        "decayed": decayed_total,
        "distorted": distorted_total,
        "forgotten": forgotten_total,
        "skill_used": bool(need_distort or target_char_ids),
        "mock": md_skill_mock,
    })

    # ---- Step 3: 任务/纲领监控（并发）----
    with trace.span("monitors", "step", step=3):
        mon_results = _run_parallel([
            lambda: call_skill("quest_monitor", user_prompt="检查所有 in_progress 任务"),
            lambda: call_skill("agenda_monitor", user_prompt="检查所有 active 纲领"),
        ])
    qm_result = mon_results[0] if mon_results else {}
    am_result = mon_results[1] if len(mon_results) > 1 else {}
    steps.append({"step": 3, "name": "quest_monitor", "mock": qm_result.get("mock"), "tool_calls": len(qm_result.get("tool_results", []))})
    steps.append({"step": 3.1, "name": "agenda_monitor", "mock": am_result.get("mock")})

    # ---- Step 4: NPC 决策（并发）----
    active_chars = models.Character.list(
        where="dead_at_tick IS NULL", order_by="importance DESC", limit=max_actors
    )
    proto = sm.get_protagonist()
    proto_id = proto.get("id") if proto else None

    def _decide(c: Any) -> Dict[str, Any]:
        scene_vars = {**variables, "role_name": c.name, "scene_description": c.status or "正常"}
        # 主角如果有 player_action，在 Step 1.5 已经调过 player_action skill 并落盘了，这里改为调 actor_decide
        # 来让主角也做本 tick 的普通决策（与其他 NPC 一致），避免重复计算玩家动作
        decision = call_skill(
            "actor_decide",
            user_prompt=(
                f"角色：{c.name}\n状态：{c.status or '正常'}\n"
                + (f"（已在 Step 1.5 处理了玩家瞬间动作：{player_action.strip()}，请在不重复该动作的前提下决策本 tick 其他行动）\n" if (player_action and c.id == proto_id) else "")
                + "请决策本 tick 行动。"
            ),
            variables=scene_vars,
        )
        return {"char_id": c.id, "char_name": c.name, "decision": decision.get("parsed") or decision.get("content")}

    decisions: List[Dict[str, Any]] = []
    if active_chars:
        with trace.span("actor_decide", "step", step=4, actors=len(active_chars)):
            decisions = _run_parallel([lambda c=c: _decide(c) for c in active_chars])
    steps.append({"step": 4, "name": "actor_decide", "actors": len(decisions), "decisions": decisions})

    # ---- Step 5: 世界反应合成事件 ----
    decisions_json = json.dumps(decisions, ensure_ascii=False, default=str)
    wr_result = call_skill(
        "world_react",
        user_prompt=f"本 tick 角色决策列表：\n{decisions_json}\n请合成世界事件。",
    )
    # events_created 在函数开头已声明并在 Step 1.5 可能写入了内容，这里不重新初始化，
    # 避免覆盖掉 player_action skill 产出的事件。

    # 5a. 新模式：LLM 通过 world_create_event 工具直接创建事件
    for tr in wr_result.get("tool_results", []):
        if tr.get("tool") == "world_create_event":
            result = tr.get("result", {})
            if isinstance(result, dict):
                # create_event 返回 {"id": ..., ...}；失败时返回 {"error": ...}
                if result.get("id"):
                    if result["id"] not in events_created:  # 避免 Step 1.5 已写入的事件被重复追加
                        events_created.append(result["id"])
                elif result.get("error"):
                    steps.append({"step": 5, "error": f"world_create_event 失败: {result['error']}"})

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
                if e["id"] not in events_created:  # 去重
                    events_created.append(e["id"])
            except Exception as ex:
                steps.append({"step": 5, "error": f"事件创建失败: {ex}"})
    steps.append({
        "step": 5, "name": "world_react",
        "events_created": events_created,
        "mock": wr_result["mock"],
        "tool_results_count": len(wr_result.get("tool_results", [])),
        "rounds": wr_result.get("rounds", 1),
    })

    # ---- Step 6: 事件编码为记忆 —— 先调用 skill 精细覆盖（视角偏差/情绪），再用纯代码批量落盘兜底 ----
    encoded_total = 0
    encoded_by_skill = 0
    me_skill_mock = False
    with trace.span("memory_encode", "step", step=6):
        if events_created:
            # Step 6a: 加载事件与参与人信息，给 skill 做精细判断依据
            events_for_skill: List[Dict[str, Any]] = []
            for eid in events_created:
                ev = models.Event.get(eid)
                if not ev:
                    continue
                parts = models.EventParticipant.list(
                    where="event_id = ?", params=[eid],
                )
                events_for_skill.append({
                    "id": eid,
                    "event_type": ev.event_type,
                    "content_raw": ev.content_raw,
                    "content_polished": ev.content_polished,
                    "importance": ev.importance,
                    "participants": [
                        {
                            "id": p.id,
                            "type": p.participant_type,
                            "obj_id": p.participant_id,
                            "role": p.role_raw,
                            "perception": p.perception_raw,
                        } for p in parts
                    ],
                })

            # Step 6b: 调用 memory_encoder skill，请求精细编码结果
            me_user_prompt = (
                f"当前 tick：{meta.get('tick_num')}\n"
                f"新事件列表（共 {len(events_for_skill)} 条）：\n"
                f"{json.dumps(events_for_skill, ensure_ascii=False, default=str)}\n\n"
                "请执行以下操作：\n"
                "1. 对每条事件及其参与人，按 role 分配 depth/correctness（参考 skill.md 规则）\n"
                "2. 对每条记忆补充 perspective_bias（视角偏差）与 mood（情绪）字段\n"
                "3. 对部分需要更精细的参与人（主角/核心参与人），可手动覆盖 correctness 或 depth\n"
                "4. 若需要调用 memory_encode_event 工具完成持久化，可调用；否则返回 JSON 格式的 memories 数组，结构与 skill.md 输出格式一致。\n"
            )
            me_result = call_skill(
                "memory_encoder",
                user_prompt=me_user_prompt,
                temperature=0.4,
            )
            me_skill_mock = me_result.get("mock", False)

            # Step 6c: 统计 skill 中真正通过 memory_encode_event 工具写入的条数
            encoded_by_skill = sum(
                len((tr.get("result") or {}).get("memories", []))
                for tr in (me_result.get("tool_results") or [])
                if tr.get("tool") == "memory_encode_event"
            )

            # Step 6d: 解析 skill 返回的 JSON memories 数组 —— 注意：
            # 精细覆盖已经由 skill 的 memory_encode_event 工具完成（Step 6c 已统计），
            # 这里不需要重复写。若 memory_encode_event 工具未覆盖，兜底用 6e 写默认值即可。

            # Step 6e: 兜底纯代码编码 —— 对那些 skill 没覆盖到的事件（或 skill 解析失败的事件）再走一次纯 service
            for eid in events_created:
                try:
                    existing = sm_db.execute(
                        "SELECT COUNT(*) AS c FROM memories WHERE event_id = ?",
                        [eid]
                    ).fetchone()["c"]
                    if existing == 0:
                        mems = memory_service.encode_event_to_memories(eid)
                        encoded_total += len(mems)
                except Exception:
                    pass
    steps.append({
        "step": 6,
        "name": "memory_encode",
        "encoded_fallback": encoded_total,
        "encoded_by_skill_tool": encoded_by_skill,
        "events": len(events_created),
        "mock": me_skill_mock,
    })

    # ---- Step 7: 事件润色（独立节点，受 polish_mode 控制，与主管线解耦）----
    polish_mode = variables.get("polish_mode", "none")
    polished = 0
    pre_polished = 0
    if polish_mode == "none":
        # 无润色：不调用模型，content_polished 直接写原文
        with trace.span("event_polisher", "step", step=7, mode="none"):
            for eid in events_created:
                ev = models.Event.get(eid)
                if ev:
                    models.Event.update(eid, content_polished=ev.content_raw)
        pre_polished = len(events_created)
        steps.append({"step": 7, "name": "event_polisher", "mode": "none", "pre_polished": pre_polished})
    else:
        # 润色：先由模型选风格，再调用对应 polisher_<style> skill 回填 content_polished（并发）
        def _polish(eid: int) -> int:
            ev = models.Event.get(eid)
            if not ev or ev.content_polished:
                return 0
            style_key = _select_polish_style(ev.content_raw)
            if style_key not in _POLISH_STYLES:
                style_key = "default"
            ep_result = call_skill(
                "event_polisher",
                user_prompt=(
                    f"事件 raw：{ev.content_raw}\n"
                    f"请按当前润色模式（{polish_mode}）润色为 polished 文本。"
                ),
                variables={"polish_style": style_key},
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
                return 1
            # 7b. LLM 可能通过 world_polish_event 工具直接润色了
            for tr in ep_result.get("tool_results", []):
                if tr.get("tool") == "world_polish_event":
                    return 1
            return 0

        with trace.span("event_polisher", "step", step=7, mode=polish_mode):
            if events_created:
                polished = sum(_run_parallel([lambda e=eid: _polish(e) for eid in events_created]))
        # 统计事件创建时已经带 polished 的数量
        pre_polished = sum(
            1 for eid in events_created
            if (ev := models.Event.get(eid)) and ev.content_polished
        )
        steps.append({"step": 7, "name": "event_polisher", "mode": polish_mode, "polished": polished, "pre_polished": pre_polished})

    return {
        "tick": meta["tick_num"],
        "game_time": meta["game_time"],
        "trace": steps,
        "events_created": events_created,
        "decisions": decisions,
        "mock_mode": deepseek_client.is_mock_mode(),
    }
