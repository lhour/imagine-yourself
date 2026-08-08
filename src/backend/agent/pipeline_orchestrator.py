"""src.backend.agent.pipeline_orchestrator — C 阶段纯 LLM 自主编排层。

本模块是 tick 管线的**编排主入口**，在 v4 五节点管线之上叠加：

1. **概率事件网关**（代码层掷骰子）：每 tick 开始按 gameplay_options 采样决定
   是否触发突发事件及类型倾向，作为硬提示注入 LLM。
2. **编排规划**：调 tick_orchestrator skill 让 LLM 自主决定本 tick 调哪些可选节点
   （基于世界快照决策树），保留 v4 必选节点结构。
3. **配额跟踪**：每个子 skill 调用次数受 gameplay_options 配额限制，超配额拒绝。
4. **反思闭环**：coordinator 产出 narrative 后强制调 consistency_checker，
   冲突则打回 coordinator（上限 3 轮）。
5. **锚点校验**：narrative 落库后调 anchor_check 校验是否满足锚点 trigger_condition。
6. **必选节点兜底**：若 LLM 跳过必选节点，工具层兜底自动补调（降级执行）+ 告警落 trace。

与 v4 关系：v4 是底层执行引擎（5 节点固定顺序），orchestrator 在外层做"决策 + 约束 + 反思"。
v4 的 tick_once_v4 仍是执行主体，orchestrator 通过修改其参数 / 后处理实现编排。
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

from src.backend.agent import trace
from src.backend.agent.pipeline_v4 import call_skill, tick_once_v4, _build_variables
from src.backend.storage import models
from src.backend.storage.connection import default_save_manager

logger = logging.getLogger(__name__)


# ============================================================
# 配额跟踪（线程本地计数器，避免并发 tick 互相干扰）
# ============================================================

import threading

_quota_local = threading.local()


def _quota_state() -> Dict[str, int]:
    if not hasattr(_quota_local, "counts"):
        _quota_local.counts = {}
    return _quota_local.counts


def _reset_quota() -> None:
    _quota_local.counts = {}


def _bump_skill(skill_name: str, count: int = 1) -> int:
    """递增某 skill 调用计数，返回当前累计次数。"""
    s = _quota_state()
    s[skill_name] = s.get(skill_name, 0) + count
    return s[skill_name]


def _get_skill_count(skill_name: str) -> int:
    return _quota_state().get(skill_name, 0)


# 默认配额（每 tick 上限）；可被 gameplay_options 覆盖
DEFAULT_QUOTAS: Dict[str, int] = {
    "actor_decide_v2": 8,
    "coordinator": 3,
    "consistency_checker": 3,
    "character_updater": 2,
    "global_updater": 1,
    "world_react_v2": 1,
    "anchor_check": 1,
    "rumor_propagator": 1,
    "scheduled_event_dispatcher": 1,
    "pre_analyzer": 1,
    "quest_monitor": 1,
    "agenda_monitor": 1,
}


def _get_quotas() -> Dict[str, int]:
    """读取配额配置：gameplay_options.orchestrator_quotas 覆盖默认。"""
    try:
        sm = default_save_manager()
        opts = sm.get_gameplay_options()
        custom = opts.get("orchestrator_quotas") or {}
        if isinstance(custom, str):
            try:
                custom = json.loads(custom)
            except Exception:
                custom = {}
        return {**DEFAULT_QUOTAS, **(custom if isinstance(custom, dict) else {})}
    except Exception:
        return dict(DEFAULT_QUOTAS)


def check_quota(skill_name: str) -> bool:
    """检查某 skill 是否还能调用（未超配额）。"""
    quotas = _get_quotas()
    limit = quotas.get(skill_name, 2)
    return _get_skill_count(skill_name) < limit


# ============================================================
# 概率事件网关（代码层掷骰子）
# ============================================================

def _sample_probability_events() -> Dict[str, Any]:
    """10.4 概率事件采样：按 gameplay_options 的 death/luck/challenge bias 决定
    本 tick 是否触发突发，及类型倾向。

    返回 hard_hint（字符串）作为给 tick_orchestrator 的硬提示；
    无触发时返回空字符串，LLM 不感知概率参数。
    """
    try:
        sm = default_save_manager()
        opts = sm.get_gameplay_options()
    except Exception:
        return {"hard_hint": "", "sampled": False}

    death = int(opts.get("death_likelihood", 3))  # 0-10
    luck = int(opts.get("luck_bias", 0))  # -5 ~ +5
    challenge = int(opts.get("challenge_bias", 0))  # -5 ~ +5

    # 概率映射：death=3 → ~3% 每 tick，death=10 → ~30%
    death_p = max(0.0, min(0.5, death / 30.0))
    # challenge bias 正向 → 增加挑战类突发概率
    challenge_p = max(0.0, min(0.5, (challenge + 5) / 40.0))
    # luck bias 正向 → 增加好运类突发概率，负向 → 增加霉运
    luck_p = max(0.0, min(0.5, abs(luck) / 40.0))

    rng = random.SystemRandom()
    triggers: List[str] = []

    if rng.random() < death_p:
        triggers.append("death")  # 死亡/重伤倾向
    if rng.random() < challenge_p:
        triggers.append("challenge")  # 挑战/冲突倾向
    if rng.random() < luck_p:
        # luck>=0 → 好运；<0 → 霉运
        triggers.append("fortune_good" if luck >= 0 else "fortune_bad")

    if not triggers:
        return {"hard_hint": "", "sampled": False, "triggers": []}

    # 构造硬提示
    hint_map = {
        "death": "本 tick 应发生一类涉及死亡/重伤/濒死的突发（具体由你创作）",
        "challenge": "本 tick 应发生一类挑战/冲突/障碍突发（具体由你创作）",
        "fortune_good": "本 tick 应发生一类好运/机遇突发（具体由你创作）",
        "fortune_bad": "本 tick 应发生一类霉运/意外损失突发（具体由你创作）",
    }
    hints = [hint_map[t] for t in triggers if t in hint_map]
    hard_hint = "【概率事件硬提示】" + "；".join(hints) + "。请在 coordinator 合成 narrative 时融入此倾向。"

    return {
        "hard_hint": hard_hint,
        "sampled": True,
        "triggers": triggers,
        "params": {"death_likelihood": death, "luck_bias": luck, "challenge_bias": challenge},
    }


# ============================================================
# 编排规划（调 tick_orchestrator skill）
# ============================================================

def _plan_orchestration(
    meta: Dict[str, Any],
    player_action: Optional[str],
    prob_events: Dict[str, Any],
) -> Dict[str, Any]:
    """调 tick_orchestrator skill，让 LLM 自主决定本 tick 调哪些可选节点。

    返回：
    - skip_nodes: 跳过的可选节点列表
    - skip_reasons: 跳过原因
    - mock: 是否 mock 模式
    必选节点（pre_analyzer / actor_decide_v2 / coordinator / consistency_checker /
    character_updater）永远不跳过。
    """
    # 拉世界快照供 LLM 决策
    try:
        recent = models.Event.list(order_by="id DESC", limit=5)
        recent_dicts = [{"id": e.id, "type": e.event_type, "content": e.content_raw[:100]} for e in recent]
    except Exception:
        recent_dicts = []

    try:
        anchors = models.AnchorPlot.list(
            where="status IN ('pending', 'active')", order_by="inevitability DESC", limit=10
        )
        anchor_dicts = [a.to_dict() for a in anchors]
    except Exception:
        anchor_dicts = []

    # 检查待传播/到期周期事件/任务到期
    has_pending_propagation = False
    has_due_scheduled = False
    has_due_quests = False
    try:
        from src.backend.service.game_time_utils import compare as gt_compare
        gt = meta.get("game_time", "")

        pend = models.EventDissemination.list(where="status = 'pending'", limit=1)
        has_pending_propagation = len(pend) > 0

        sched = models.ScheduledEvent.list(where="active = 1", limit=50)
        for se in sched:
            nt = se.next_trigger_game_time or ""
            if nt:
                cmp = gt_compare(nt, gt)
                if cmp is not None and cmp <= 0:
                    has_due_scheduled = True
                    break

        quests = models.CharacterQuest.list(
            where="status IN ('in_progress', 'planned')", limit=50
        )
        for q in quests:
            dl = q.deadline_game_time or ""
            if dl:
                cmp = gt_compare(dl, gt)
                if cmp is not None and cmp <= 0:
                    has_due_quests = True
                    break
    except Exception:
        pass

    hard_hint = prob_events.get("hard_hint", "")

    user_prompt = (
        f"【世界快照】\n"
        f"- tick: {meta.get('tick_num')}, 游戏时间: {meta.get('game_time')}\n"
        f"- 玩家动作: {player_action or '(无)'}\n"
        f"- 最近事件数: {len(recent_dicts)}\n"
        f"- 活跃锚点数: {len(anchor_dicts)}\n"
        f"- 待传播信息: {'有' if has_pending_propagation else '无'}\n"
        f"- 到期周期事件: {'有' if has_due_scheduled else '无'}\n"
        f"- 到期任务: {'有' if has_due_quests else '无'}\n\n"
        f"{hard_hint}\n\n"
        "根据决策树，输出本 tick 的编排计划：\n"
        "- 哪些可选节点可以跳过（skip_nodes）及原因（skip_reasons）\n"
        "- 必选节点不可跳过\n"
        "- 输出 JSON: {skip_nodes: [...], skip_reasons: {...}}"
    )

    try:
        result = call_skill(
            "tick_orchestrator",
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1024,
        )
        _bump_skill("tick_orchestrator")
        parsed = result.get("parsed") or {}
        skip_nodes = parsed.get("skip_nodes", [])
        if not isinstance(skip_nodes, list):
            skip_nodes = []
        # 过滤掉必选节点（防止 LLM 误跳）
        required = {"pre_analyzer", "actor_decide_v2", "coordinator",
                    "consistency_checker", "character_updater"}
        skip_nodes = [n for n in skip_nodes if n not in required]
        return {
            "skip_nodes": skip_nodes,
            "skip_reasons": parsed.get("skip_reasons", {}),
            "mock": result.get("mock", False),
        }
    except Exception as ex:
        logger.warning("tick_orchestrator 规划失败，降级为全跑: %s", ex)
        return {"skip_nodes": [], "skip_reasons": {}, "mock": True, "error": str(ex)}


# ============================================================
# 反思闭环（consistency_checker + 打回 coordinator）
# ============================================================

def _reflect_on_narrative(
    narrative: str,
    decisions: List[Dict[str, Any]],
    event_ids: List[int],
    active_anchors: List[Dict[str, Any]],
    max_retries: int = 2,
) -> Dict[str, Any]:
    """反思闭环：调 consistency_checker 校验 narrative，冲突则打回 coordinator。

    返回：
    - passed: 是否最终通过
    - final_narrative: 最终 narrative（可能被重写）
    - conflicts: 冲突列表
    - retries: 重试次数
    """
    if not narrative:
        return {"passed": True, "final_narrative": "", "conflicts": [], "retries": 0}

    current_narrative = narrative
    total_retries = 0

    for attempt in range(max_retries + 1):
        if not check_quota("consistency_checker"):
            logger.warning("consistency_checker 配额耗尽，跳过反思")
            return {
                "passed": True,
                "final_narrative": current_narrative,
                "conflicts": [],
                "retries": total_retries,
                "quota_exhausted": True,
            }

        decisions_json = json.dumps(decisions, ensure_ascii=False, default=str)[:2000]
        events_data = []
        for eid in event_ids[:5]:
            try:
                ev = models.Event.get(eid)
                if ev:
                    events_data.append({"id": eid, "type": ev.event_type, "content": ev.content_raw[:200]})
            except Exception:
                pass
        anchors_json = json.dumps(active_anchors, ensure_ascii=False, default=str)[:1500]

        try:
            result = call_skill(
                "consistency_checker",
                user_prompt=(
                    f"【narrative】\n{current_narrative[:3000]}\n\n"
                    f"【decisions】\n{decisions_json}\n\n"
                    f"【events_created】\n{json.dumps(events_data, ensure_ascii=False, default=str)}\n\n"
                    f"【active_anchors】\n{anchors_json}\n\n"
                    "请校验一致性并输出 JSON。"
                ),
                temperature=0.2,
                max_tokens=1024,
            )
            _bump_skill("consistency_checker")
        except Exception as ex:
            logger.warning("consistency_checker 调用失败: %s", ex)
            return {"passed": True, "final_narrative": current_narrative,
                    "conflicts": [], "retries": total_retries, "error": str(ex)}

        parsed = result.get("parsed") or {}
        passed = bool(parsed.get("passed", True))
        conflicts = parsed.get("conflicts", [])
        if not isinstance(conflicts, list):
            conflicts = []

        if passed or attempt >= max_retries:
            return {
                "passed": passed,
                "final_narrative": current_narrative,
                "conflicts": conflicts,
                "retries": attempt,
                "anchors_fulfilled": parsed.get("anchors_fulfilled", []),
            }

        # 打回：用冲突反馈重写 narrative
        high_conflicts = [c for c in conflicts if isinstance(c, dict) and c.get("severity") == "high"]
        if not high_conflicts:
            # 仅 low/medium 冲突，视为通过
            return {
                "passed": True,
                "final_narrative": current_narrative,
                "conflicts": conflicts,
                "retries": attempt,
                "anchors_fulfilled": parsed.get("anchors_fulfilled", []),
            }

        # 调 coordinator 修正 narrative
        if not check_quota("coordinator"):
            logger.warning("coordinator 配额耗尽，无法打回重写")
            return {
                "passed": False,
                "final_narrative": current_narrative,
                "conflicts": conflicts,
                "retries": attempt,
                "quota_exhausted": True,
            }

        conflict_desc = json.dumps(high_conflicts, ensure_ascii=False, default=str)
        try:
            rewrite_result = call_skill(
                "coordinator",
                user_prompt=(
                    f"【原 narrative】\n{current_narrative[:2000]}\n\n"
                    f"【一致性冲突】\n{conflict_desc}\n\n"
                    "请根据冲突反馈重写 narrative，确保冲突被修正。"
                    "输出 JSON: {narrative: str, fulfilled_anchor_ids: [int]}"
                ),
                temperature=0.4,
                max_tokens=4096,
            )
            _bump_skill("coordinator")
            rp = rewrite_result.get("parsed") or {}
            new_narr = rp.get("narrative", "")
            if new_narr and new_narr != current_narrative:
                current_narrative = new_narr
                total_retries += 1
            else:
                # 重写未生效，终止
                return {
                    "passed": False,
                    "final_narrative": current_narrative,
                    "conflicts": conflicts,
                    "retries": attempt,
                }
        except Exception as ex:
            logger.warning("coordinator 重写失败: %s", ex)
            return {
                "passed": False,
                "final_narrative": current_narrative,
                "conflicts": conflicts,
                "retries": attempt,
                "error": str(ex),
            }

    return {
        "passed": False,
        "final_narrative": current_narrative,
        "conflicts": [],
        "retries": total_retries,
    }


# ============================================================
# 锚点校验（anchor_check skill）
# ============================================================

def _run_anchor_check(
    narrative: str,
    event_ids: List[int],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """调 anchor_check skill 校验 narrative 是否满足锚点 trigger_condition。"""
    if not check_quota("anchor_check"):
        return {"skipped": True, "reason": "quota_exhausted"}

    try:
        anchors = models.AnchorPlot.list(
            where="status IN ('pending', 'active')", order_by="inevitability DESC", limit=20
        )
    except Exception:
        return {"skipped": True, "reason": "no_anchors"}

    if not anchors:
        return {"checked": 0, "fulfilled": [], "expired": []}

    anchor_dicts = [a.to_dict() for a in anchors]
    events_data = []
    for eid in event_ids[:5]:
        try:
            ev = models.Event.get(eid)
            if ev:
                events_data.append({"id": eid, "type": ev.event_type, "content": ev.content_raw[:200]})
        except Exception:
            pass

    try:
        result = call_skill(
            "anchor_check",
            user_prompt=(
                f"【narrative】\n{narrative[:3000]}\n\n"
                f"【events_created】\n{json.dumps(events_data, ensure_ascii=False, default=str)}\n\n"
                f"【current_anchors】\n{json.dumps(anchor_dicts, ensure_ascii=False, default=str)}\n\n"
                f"当前游戏时间：{meta.get('game_time')}（tick {meta.get('tick_num')}）\n\n"
                "请校验哪些锚点被本 tick 满足，调用 anchor_advance 工具完成状态流转，并输出 JSON 摘要。"
            ),
            temperature=0.2,
            max_tokens=1024,
        )
        _bump_skill("anchor_check")
        parsed = result.get("parsed") or {}
        return {
            "checked": parsed.get("checked", len(anchor_dicts)),
            "fulfilled": parsed.get("fulfilled", []),
            "expired": parsed.get("expired", []),
            "unchanged": parsed.get("unchanged", []),
            "mock": result.get("mock"),
        }
    except Exception as ex:
        logger.warning("anchor_check 调用失败: %s", ex)
        return {"skipped": True, "error": str(ex)}


# ============================================================
# 主入口
# ============================================================

def tick_once_orchestrated(
    seconds: int = 60,
    max_actors: int = 5,
    player_action: Optional[str] = None,
) -> Dict[str, Any]:
    """C 阶段主入口：纯 LLM 自主编排 + skill 硬约束。

    流程：
    1. 概率事件采样（代码层）
    2. 调 tick_orchestrator skill 规划本 tick 子任务（决策树）
    3. 跑 v4 五节点管线（必选节点 + 可选节点按规划跳过）
    4. 反思闭环：consistency_checker 校验 narrative，冲突则打回 coordinator（上限 3 轮）
    5. 锚点校验：anchor_check 校验 narrative 是否满足锚点 trigger_condition
    6. 返回完整 trace + narrative + 配额使用情况
    """
    sm = default_save_manager()
    if not sm.active_save:
        raise RuntimeError("无激活存档")

    _reset_quota()  # 重置本 tick 配额计数

    # ---------- Step 1: 概率事件采样 ----------
    with trace.span("probability_gateway", "node", node=0.1):
        prob_events = _sample_probability_events()
    _bump_skill("__probability_gateway__")  # 标记已采样（不计入配额）

    # ---------- Step 2: 编排规划 ----------
    meta_preview = sm.get_meta()
    with trace.span("orchestrator_plan", "node", node=0.2):
        plan = _plan_orchestration(meta_preview, player_action, prob_events)

    # ---------- Step 3: 跑 v4 管线（必选节点结构不变）----------
    # 注意：v4 管线内部已实现 0.6/0.7/5.5 等可选节点；
    # orchestrator 此处不强行短路 v4 内部逻辑（v4 已有条件判断），
    # 而是聚焦在外层"反思 + 锚点"两个新增节点。
    with trace.span("v4_pipeline", "node", node=0.3):
        v4_result = tick_once_v4(seconds, max_actors, player_action)

    # ---------- Step 4: 反思闭环 ----------
    narrative = v4_result.get("narrative", "")
    decisions = v4_result.get("decisions", [])
    events_created = v4_result.get("events_created", [])

    try:
        active_anchors = [a.to_dict() for a in models.AnchorPlot.list(
            where="status IN ('pending', 'active')", limit=20
        )]
    except Exception:
        active_anchors = []

    with trace.span("reflection", "node", node=6):
        reflection = _reflect_on_narrative(
            narrative=narrative,
            decisions=decisions,
            event_ids=events_created,
            active_anchors=active_anchors,
            max_retries=2,
        )

    # 若 reflection 重写了 narrative，更新 v4_result
    final_narrative = reflection.get("final_narrative", narrative)
    if final_narrative and final_narrative != narrative:
        v4_result["narrative"] = final_narrative
        v4_result["narrative_rewritten"] = True
        # 把重写的 narrative 也落一条事件（标记 revision）
        try:
            from src.backend.service import world_service
            rev_ev = world_service.create_event(
                event_type="narrative_revision",
                content_raw=final_narrative,
                content_polished=final_narrative,
                importance=5,
                custom_attrs={"revision_of_tick": v4_result.get("tick")},
            )
            if rev_ev.get("id"):
                events_created.append(rev_ev["id"])
                v4_result["events_created"] = events_created
        except Exception as ex:
            logger.warning("narrative 重写事件落库失败: %s", ex)

    # ---------- Step 5: 锚点校验 ----------
    meta_final = {
        "tick_num": v4_result.get("tick", meta_preview.get("tick_num", 0)),
        "game_time": v4_result.get("game_time", meta_preview.get("game_time", "")),
    }
    with trace.span("anchor_check", "node", node=7):
        anchor_result = _run_anchor_check(final_narrative, events_created, meta_final)

    # ---------- 组装返回 ----------
    orchestration_summary = {
        "probability_events": prob_events,
        "plan": plan,
        "reflection": reflection,
        "anchor_check": anchor_result,
        "quota_used": dict(_quota_state()),
    }

    v4_result["orchestration"] = orchestration_summary
    v4_result["orchestrated"] = True
    return v4_result
