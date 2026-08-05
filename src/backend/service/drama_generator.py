"""src.backend.service.drama_generator — 10 步 LLM 剧本生成管线。

10 步生成顺序（有依赖）：
    1. meta            世界观元数据：start_game_time / era_name / protagonist_default ...
    2. characters      角色列表（名称/人设/重要性），后续步骤引用角色名
    3. groups          群体列表（名称/类型/leader_name → characters）
    4. group_hierarchies 群体层级（parent → child groups）
    5. items           物品列表（名称/类型/稀有度/持有者）
    6. maps            地图列表（世界→区域→城镇，含层级 parent_map_name）
    7. map_features    地图特征/地标（关联 maps / features）
    8. events          初始事件（历史事件：角色/群体/物品/地图引用）
    9. settings        基础设定（世界观规则：魔法等级/科技水平等）
   10. plot_planning   剧情规划表（主线节点：title/plot/estimated_time）

每一步：
    - 前置步骤的输出作为 system_prompt 的 context 注入
    - user_prompt 包含用户原始 prompt 和当前步骤指令
    - LLM 输出：JSON（meta）或 JSONL（其他 9 个文件）
    - 解析结果写入 drama/{name}/{file}.txt（原子写，复用 drama_service.patch_drama_file）
    - 写 _generate_status.json 记录进度（用于断点续跑）
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.backend.env import BACKEND_DIR
from src.backend.deepseek_client import chat_completion, is_mock_mode
from src.backend.service import drama_service

DRAMA_DIR = BACKEND_DIR / "drama"

DRAMA_GENERATE_STEPS: List[Dict[str, Any]] = [
    {
        "step": 1,
        "name": "meta",
        "file": "meta.txt",
        "format": "json",
        "desc": "世界观元信息（meta JSON）",
        "requires": [],
    },
    {
        "step": 2,
        "name": "characters",
        "file": "characters.txt",
        "format": "jsonl",
        "desc": "角色列表（JSONL，每行一个角色）",
        "requires": [1],
    },
    {
        "step": 3,
        "name": "groups",
        "file": "groups.txt",
        "format": "jsonl",
        "desc": "群体列表（JSONL）",
        "requires": [1, 2],
    },
    {
        "step": 4,
        "name": "group_hierarchies",
        "file": "group_hierarchies.txt",
        "format": "jsonl",
        "desc": "群体层级关系（JSONL）",
        "requires": [1, 3],
    },
    {
        "step": 5,
        "name": "items",
        "file": "items.txt",
        "format": "jsonl",
        "desc": "物品列表（JSONL）",
        "requires": [1, 2],
    },
    {
        "step": 6,
        "name": "maps",
        "file": "maps.txt",
        "format": "jsonl",
        "desc": "地图列表（JSONL，含 parent_map_name 层级）",
        "requires": [1],
    },
    {
        "step": 7,
        "name": "map_features",
        "file": "map_features.txt",
        "format": "jsonl",
        "desc": "地图特征/地标（JSONL，引用 map_name）",
        "requires": [1, 6],
    },
    {
        "step": 8,
        "name": "events",
        "file": "events.txt",
        "format": "jsonl",
        "desc": "初始历史事件（JSONL，角色/群体/地图/物品）",
        "requires": [1, 2, 3, 5, 6],
    },
    {
        "step": 9,
        "name": "settings",
        "file": "settings.txt",
        "format": "jsonl",
        "desc": "基础设定（魔法/科技/政治/经济/文化规则）",
        "requires": [1],
    },
    {
        "step": 10,
        "name": "plot_planning",
        "file": "plot_planning.txt",
        "format": "jsonl",
        "desc": "剧情规划表（主线节点）",
        "requires": [1, 2, 8],
    },
]


# ============================================================
# 内部：状态文件 + 上下文收集
# ============================================================

_STATUS_FNAME = "_generate_status.json"


def _status_path(name: str) -> Path:
    return DRAMA_DIR / name / _STATUS_FNAME


def _read_status(name: str) -> Dict[str, Any]:
    p = _status_path(name)
    if not p.is_file():
        return {"step_results": {}, "start_time": None, "end_time": None}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {"step_results": {}, "start_time": None, "end_time": None}


def _write_status(name: str, status: Dict[str, Any]) -> None:
    p = _status_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写
    import os, tempfile
    fd, tmp = tempfile.mkstemp(prefix=f".{_STATUS_FNAME}.tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(p))
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def _collect_context(name: str, requires: List[int]) -> str:
    """根据 requires 步骤号收集已生成文件内容作为上下文。"""
    parts: List[str] = []
    for step_num in requires:
        meta = next((s for s in DRAMA_GENERATE_STEPS if s["step"] == step_num), None)
        if not meta:
            continue
        fp = DRAMA_DIR / name / meta["file"]
        if not fp.is_file():
            continue
        content = fp.read_text(encoding="utf-8-sig").strip()
        if not content:
            continue
        parts.append(f"# ===== {meta['file']}（step {step_num}: {meta['name']}）=====\n{content}")
    return "\n\n".join(parts) if parts else "（无前置上下文）"


# ============================================================
# 内部：Prompt 模板（每步一个）
# ============================================================

def _build_prompts(
    step_meta: Dict[str, Any],
    user_prompt_raw: str,
    context_str: str,
    existing_content: Optional[str] = None,
) -> tuple[str, str]:
    """构建 system_prompt + user_prompt。
    关键约束：
    - 只输出 JSON/JSONL，不要额外解释文本
    - 字段命名要与 drama_service 期望一致（name/desc_raw/importance 等）
    - name→ID 引用在 JSONL 中用 xxx_name 字段（如 leader_name, parent_map_name）
    """
    step = step_meta["step"]
    fmt = step_meta["format"]

    general_rules = """【输出规则（必须严格遵守）】
1. 只输出结构化数据，不要开头/结尾解释、不要 Markdown 代码块、不要注释。
2. 所有字符串使用 UTF-8 中文（或用户指定语言），不要用英文填充，除非是专有名词。
3. importance 字段必须在 0-5 之间整数（0=无关紧要，5=核心关键），默认 3。
4. 引用实体一律使用 *_name 字段（如 leader_name / parent_map_name / location_map_name / participant_name / holder_name），后续由 drama_service 自动解析为 ID。
5. game_time 字段使用格式：「{纪元}{年}年{月}月{日}日{时}时{分}分{秒}秒」，例如：源石纪元13年9月1日08时00分00秒。
6. status 字段是字符串，可写多个状态用 / 分隔，例如 "受伤/暴怒"。
"""

    # 每步的 schema 示例（直接给 JSON，防止 LLM 猜字段）
    schema_examples = {
        1: {
            "name": "示例剧本名",
            "summary_raw": "用户给的世界观一句话摘要",
            "summary_polished": "润色后的 2-3 句简介（有文学性）",
            "era_name": "源石纪元",
            "start_game_time": "源石纪元13年9月1日08时00分00秒",
            "protagonist_name_default": "沈默",
            "genre": "古风玄幻",
            "tone": "严肃写实",
            "description_raw": "完整世界观设定概要",
        },
        2: {
            "name": "沈默",
            "appearance_raw": "年龄约 25 岁，身高 183cm，黑发束冠，着青色长衫，左眉有一道细疤",
            "personality_raw": "外表冷静克制，内心重情义，有正义感，但处事谨慎，偶有狠辣",
            "gender": "男",
            "age": 25,
            "status": "健康",
            "importance": 5,
            "location_map_name": "青阳城",
            "x": 120.5,
            "y": 88.3,
            "groups_member": [
                {"group_name": "天机阁", "role_raw": "核心弟子", "join_tick": 0, "importance_in_group": 5}
            ],
            "custom_attrs": {"灵根": "雷灵根（变异）", "修为": "金丹后期"},
        },
        3: {
            "name": "天机阁",
            "desc_raw": "正道三大宗门之一，擅长推演卦象与雷法",
            "group_type": "sect",
            "leader_name": "玄机子",
            "importance": 4,
            "primary_map_name": "青云山",
            "center_x": 500.0,
            "center_y": 420.0,
            "spread_radius": 300,
            "members": [
                {"char_name": "沈默", "role_raw": "核心弟子"},
                {"char_name": "玄机子", "role_raw": "掌门"},
            ],
        },
        4: {
            "child_group": "天机阁·外门",
            "parent_group": "天机阁",
            "relation_raw": "subset（外门属天机阁下属）",
            "weight": 0.9,
        },
        5: {
            "name": "青霜剑",
            "desc_raw": "古剑，剑身长三尺二寸，通体幽蓝，挥之有寒气，据传为上古仙人遗物",
            "item_type": "weapon",
            "rarity": 5,
            "importance": 4,
            "holder_name": "沈默",
            "quantity": 1,
            "is_stackable": 0,
            "custom_attrs": {"攻击力": 120, "属性": "冰", "被动": "20%概率冻结"},
        },
        6: {
            "name": "青阳城",
            "desc_raw": "大楚王朝南部重镇，水陆交通便利，商业发达，人口约五十万",
            "map_type": "town",
            "parent_map_name": "大楚南疆",
            "coord_system": "cartesian_2d",
            "scale_unit": "m",
            "scale_per_unit": 1.0,
            "bbox_x": 0, "bbox_y": 0, "bbox_w": 8000, "bbox_h": 6000,
            "default_zoom": 1.2,
            "default_center_x": 4000,
            "default_center_y": 3000,
            "importance": 4,
        },
        7: {
            "map_name": "青阳城",
            "name": "城主府",
            "feature_type": "building",
            "shape": "polygon",
            "geometry": {"type": "Polygon", "coordinates": [[[100,100],[300,100],[300,250],[100,250]]]},
            "layer_z": 0,
            "color_hint": "#8b4513",
            "is_obstacle": 1,
            "size_value": 1500,
            "size_unit_override": "m^2",
        },
        8: {
            "tick_num": -730,
            "game_time": "源石纪元11年9月1日08时00分00秒",
            "event_type": "background",
            "content_raw": "沈默父母在魔教入侵中丧生，被路过的天机阁长老救下并收入门下",
            "content_polished": "那一日，血色染红了青阳镇的牌坊。沈默蜷在灶下的柴堆里，听着外面熟悉的声音一个接一个熄灭……当玄机子长老推开碎裂的木门，看见的是一个咬着牙、眼里却没有一滴泪的孩子。",
            "location_map_name": "青阳城旧址",
            "importance": 5,
            "participants": [
                {"participant_type": "character", "participant_name": "沈默", "role_raw": "victim_child", "perception_raw": "恐惧→愤怒→无助"},
                {"participant_type": "character", "participant_name": "玄机子", "role_raw": "savior"},
            ],
        },
        9: {
            "category": "cultivation",
            "title": "修炼境界划分",
            "desc_raw": "凡间修士境界：炼气→筑基→金丹→元婴→化神→合体→大乘→渡劫。每一境界分初、中、后、大圆满四期。",
            "setting_type": "essential",
            "importance": 5,
            "custom_attrs": {"各境界寿命": {"炼气": 120, "筑基": 200, "金丹": 500, "元婴": 1000, "化神": 2000}},
        },
        10: {
            "tick_num": 0,
            "estimated_time_raw": "源石纪元13年9月 上旬（约 3 天）",
            "title": "卷一·初入江湖：青阳突变",
            "plot": "沈默接到天机阁密令，下山调查青阳城近期连续失踪案。在城门口与女扮男装的楚玥相遇，二人因误会发生冲突，后发现线索指向城外的废弃矿洞。",
            "plot_polished": "（润色版：从沈默接密令的场景切入，交待动机→路上见闻→与楚玥的初次交锋→废弃矿洞的悬念收尾）",
            "importance": 5,
            "success_condition_raw": "沈默与楚玥联手解决失踪案，揭露幕后黑手的身份（魔教余孽）。",
        },
    }

    example = schema_examples.get(step, {})
    fmt_desc = "JSON 对象（meta.txt 专用，整个文件是一个 JSON）" if fmt == "json" else (
        "JSONL，每行一个独立 JSON 对象（不要数组包裹！！！不要逗号！！！一行一个对象！！！）"
    )
    example_str = json.dumps(example, ensure_ascii=False, indent=2) if fmt == "json" else (
        json.dumps(example, ensure_ascii=False) + "\n" +
        "（再一行示例：）\n" +
        json.dumps({k: (v + "_示例2" if isinstance(v, str) else v) for k, v in example.items()}, ensure_ascii=False)
    )

    system_prompt = (
        "你是一位资深的世界观架构师 + 剧情策划 + 小说作家。"
        "你擅长构建逻辑自洽、细节丰满、人物鲜活的中文架空世界。\n\n"
        f"{general_rules}\n\n"
        f"【当前步骤】STEP {step}: {step_meta['name']} — {step_meta['desc']}\n"
        f"【输出格式】{fmt_desc}\n\n"
        f"【Schema 示例（请根据实际内容调整字段值，字段名保持一致；可额外加 custom_attrs）】：\n{example_str}\n\n"
    )

    existing_hint = ""
    if existing_content:
        existing_hint = (
            "\n\n【现有文件内容（已有结果，用户要求在此基础上修改或精细化）】\n"
            f"{existing_content[:3000]}\n请在保留核心信息的前提下，输出完整的新内容。\n"
        )

    user_prompt = (
        "【用户原始 Prompt】\n"
        f"{user_prompt_raw}\n\n"
        f"【前置步骤已生成的上下文（供你保持一致性）】\n{context_str}\n\n"
        f"【你现在的任务】生成 STEP {step}（{step_meta['name']}）的完整 {fmt.upper()} 数据：\n"
        "- 请严格遵守上方「输出规则」和示例字段命名\n"
        "- 数量要足够（角色/群体/物品/地图按用户 prompt 规模决定，不要只有几个）\n"
        "- 内容要丰富，有细节，不要敷衍\n"
        "- 所有引用必须来自「前置上下文」里出现过的实体名（不要瞎编不存在的人/地/物名）\n"
        f"{existing_hint}\n\n"
        "现在请直接输出最终数据，不要任何解释文本。"
    )
    return system_prompt, user_prompt


# ============================================================
# 内部：解析 LLM 输出
# ============================================================

_JSON_OR_JSONL_BLOCK_RE = re.compile(
    r"```(?:json|JSON)?\s*([\s\S]*?)\s*```", re.MULTILINE
)


def _clean_and_parse(step_meta: Dict[str, Any], raw_text: str) -> Any:
    """从 LLM 原始输出中提取并解析 JSON / JSONL。
    容错：
    - 去掉 markdown 代码块包裹
    - 去掉首尾解释文本（找到第一个 { 或 [ 开始解析）
    - JSONL：逐行 load，跳过空行与非对象行
    - 最后兜底：正则提取所有 { } 块
    """
    fmt = step_meta["format"]
    text = raw_text.strip()

    # 去代码块
    m = _JSON_OR_JSONL_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()
    # 去开头/结尾的废话
    if fmt == "json":
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 兜底：找最外层第一个完整块
            depth = 0
            start = -1
            for i, ch in enumerate(text):
                if ch == "{":
                    if depth == 0: start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            start = -1
            raise
    else:
        # JSONL：逐行尝试
        results: List[Any] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                # 有时候 LLM 会输出数组包裹，尝试拆
                try:
                    arr = json.loads(line)
                    if isinstance(arr, list):
                        results.extend(arr)
                        continue
                except json.JSONDecodeError:
                    pass
            if line.startswith("{"):
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    # 兜底：一行里有多个对象？
                    objs = _extract_objects(line)
                    results.extend(objs)
        if results:
            return results
        # 最后兜底：整个文本中提取所有顶层对象
        all_objs = _extract_objects(text)
        if not all_objs:
            raise ValueError("无法从 LLM 输出中解析出任何 JSON 对象")
        return all_objs


def _extract_objects(text: str) -> List[Any]:
    """从任意文本中提取所有顶层 {...} JSON 对象。"""
    out: List[Any] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    out.append(json.loads(text[start:i+1]))
                except json.JSONDecodeError:
                    pass
                start = -1
    return out


def _dump_data(step_meta: Dict[str, Any], data: Any) -> str:
    """把解析后的数据序列化成写入文件的字符串。"""
    fmt = step_meta["format"]
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    # JSONL
    if isinstance(data, list):
        lines = [json.dumps(r, ensure_ascii=False) for r in data]
        return "\n".join(lines) + "\n"
    return json.dumps(data, ensure_ascii=False) + "\n"


# ============================================================
# 主 API：单步 & 10 步全流程
# ============================================================

def generate_step(name: str, step_num: int, user_prompt_raw: Optional[str] = None) -> Dict[str, Any]:
    """**同步** 执行生成管线某一步。
    用于：前端断点续跑 / 单独重跑某一步。
    返回 { step, ok, file, latency_ms, tokens, mock, error?, parsed_count? }
    """
    step_meta = next((s for s in DRAMA_GENERATE_STEPS if s["step"] == step_num), None)
    if not step_meta:
        raise ValueError(f"步骤 {step_num} 不存在，有效范围 1-10")

    # 状态
    status = _read_status(name)
    step_results: Dict[str, Any] = status.setdefault("step_results", {})
    if status.get("start_time") is None:
        status["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # 前置校验
    for req in step_meta["requires"]:
        req_res = step_results.get(str(req))
        if not req_res or not req_res.get("ok"):
            raise ValueError(
                f"STEP {step_num} 依赖 STEP {req}，但该步骤未成功完成。请先执行 STEP {req}。"
            )

    # 如果用户未传 prompt，从 meta 中读（如果是步骤1就报错）
    if not user_prompt_raw:
        user_prompt_raw = _load_stored_prompt(name) or "按默认世界观生成"

    # 上下文
    context_str = _collect_context(name, step_meta["requires"])
    sys_p, usr_p = _build_prompts(step_meta, user_prompt_raw, context_str)

    t0 = time.time()
    mock = is_mock_mode()
    try:
        # 调 LLM
        llm_res = chat_completion(
            sys_p,
            usr_p,
            temperature=0.8,
            max_tokens=16384,
        )
        content = llm_res.get("content") or ""
        usage = llm_res.get("usage") or {}
        mock = llm_res.get("mock", mock)

        if not content.strip():
            raise ValueError("LLM 返回空内容")

        # 解析
        parsed = _clean_and_parse(step_meta, content)
        dump = _dump_data(step_meta, parsed)

        # 原子写
        drama_service.patch_drama_file(name, step_meta["file"], dump)

        # 统计
        parsed_count = 1 if step_meta["format"] == "json" else (len(parsed) if isinstance(parsed, list) else 1)

        result = {
            "step": step_num,
            "name": step_meta["name"],
            "file": step_meta["file"],
            "ok": True,
            "latency_ms": int((time.time() - t0) * 1000),
            "tokens": usage,
            "mock": mock,
            "parsed_count": parsed_count,
        }
        step_results[str(step_num)] = result
        # 如果全部 10 步都 ok，写 end_time
        if all(step_results.get(str(s["step"]), {}).get("ok") for s in DRAMA_GENERATE_STEPS):
            status["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        # 附加最后一步的验证
        if step_num == 10 and all(step_results.get(str(s["step"]), {}).get("ok") for s in DRAMA_GENERATE_STEPS):
            vr = drama_service.validate_drama(name)
            result["validate"] = {
                "ok": vr["ok"],
                "error_count": len(vr["errors"]),
                "warning_count": len(vr["warnings"]),
                "info": vr["info"],
            }
            status["validate"] = result["validate"]
        _write_status(name, status)
        # 存一份 prompt 供后续步骤读取
        _store_prompt(name, user_prompt_raw)
        return result
    except Exception as e:
        result = {
            "step": step_num,
            "name": step_meta["name"],
            "file": step_meta["file"],
            "ok": False,
            "latency_ms": int((time.time() - t0) * 1000),
            "mock": mock,
            "error": str(e),
        }
        step_results[str(step_num)] = result
        _write_status(name, status)
        raise ValueError(f"STEP {step_num} 生成失败：{e}") from e


async def generate_drama_10step(
    prompt: str,
    name: Optional[str] = None,
    skip_steps: Optional[List[int]] = None,
    only_steps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """**异步** 执行完整 10 步生成管线。
    - prompt: 用户的原始创作需求（如「古风玄幻，主角沈默，上海市...」）
    - name: 剧本目录名，不填则自动生成（如 drama_20260806_1530）
    - skip_steps: 跳过这些步骤号（结果从已生成文件读取并标 ok）
    - only_steps: 只执行这些步骤号（其余若已完成则 ok，否则 pending）

    返回:
        { ok, name, prompt, step_results: {step_num: {...}}, total_latency_ms, validate, mock }
    """
    # 生成名字
    if not name:
        name = f"drama_{time.strftime('%Y%m%d_%H%M%S')}"
    # 清理非法字符
    name = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name).strip("_") or "drama"

    # 创建目录
    (DRAMA_DIR / name).mkdir(parents=True, exist_ok=True)
    _store_prompt(name, prompt)

    # 初始化状态
    status = _read_status(name)
    status["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    status["prompt"] = prompt
    _write_status(name, status)

    skip = set(skip_steps or [])
    only = set(only_steps) if only_steps else None

    t0 = time.time()
    results: Dict[str, Any] = {}
    any_mock = False

    try:
        for step_meta in DRAMA_GENERATE_STEPS:
            sn = step_meta["step"]
            if skip and sn in skip:
                # 标 ok（基于已有文件），不执行
                fp = DRAMA_DIR / name / step_meta["file"]
                results[str(sn)] = {
                    "step": sn,
                    "name": step_meta["name"],
                    "file": step_meta["file"],
                    "ok": fp.is_file(),
                    "skipped": True,
                    "note": "用户指定跳过，沿用已有文件（若存在）",
                }
                status.setdefault("step_results", {})[str(sn)] = results[str(sn)]
                _write_status(name, status)
                continue
            if only is not None and sn not in only:
                # 只执行指定步骤，其他不碰
                fp = DRAMA_DIR / name / step_meta["file"]
                if fp.is_file():
                    results[str(sn)] = {
                        "step": sn, "name": step_meta["name"], "file": step_meta["file"],
                        "ok": True, "skipped": False, "only_mode": True,
                        "note": "仅指定步骤模式：该文件已存在，跳过执行",
                    }
                    status.setdefault("step_results", {})[str(sn)] = results[str(sn)]
                else:
                    results[str(sn)] = {
                        "step": sn, "name": step_meta["name"], "file": step_meta["file"],
                        "ok": False, "skipped": False, "only_mode": True,
                        "note": "仅指定步骤模式：该步骤未被选择且文件不存在，后续依赖可能失败",
                    }
                    status.setdefault("step_results", {})[str(sn)] = results[str(sn)]
                continue
            # 真正执行（同步函数包装成线程，避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            try:
                r = await loop.run_in_executor(None, lambda n=sn: generate_step(name, n, prompt))
                results[str(sn)] = r
                if r.get("mock"):
                    any_mock = True
            except ValueError as e:
                results[str(sn)] = {
                    "step": sn,
                    "name": step_meta["name"],
                    "file": step_meta["file"],
                    "ok": False,
                    "error": str(e),
                }
                # 不 raise，继续后续步骤？ — 如果有 requires，后续步骤会自己失败，这里让它继续
                # 所以也 break 一下更好，减少无意义调用
                break
        # 全部跑完后最终 validate
        vr = drama_service.validate_drama(name)
        status = _read_status(name)
        status["validate"] = {
            "ok": vr["ok"],
            "error_count": len(vr["errors"]),
            "warning_count": len(vr["warnings"]),
            "errors": vr["errors"][:20],
            "warnings": vr["warnings"][:30],
            "info": vr["info"],
        }
        status["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_status(name, status)

        return {
            "ok": vr["ok"],
            "name": name,
            "prompt": prompt,
            "step_results": results,
            "total_latency_ms": int((time.time() - t0) * 1000),
            "validate": status["validate"],
            "mock": any_mock,
            "stub": False,
        }
    except Exception as e:
        status = _read_status(name)
        status["error"] = f"生成流程异常终止：{e}"
        status["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_status(name, status)
        raise


def get_generate_status(name: str) -> Dict[str, Any]:
    """查询生成管线状态 + validate 摘要 + 进度百分比。"""
    status = _read_status(name)
    results = status.get("step_results", {})
    done_count = sum(1 for r in results.values() if r.get("ok"))
    total = len(DRAMA_GENERATE_STEPS)
    progress_pct = int(done_count / total * 100) if total else 0

    step_status: List[Dict[str, Any]] = []
    for sm in DRAMA_GENERATE_STEPS:
        r = results.get(str(sm["step"]), {})
        step_status.append({
            **sm,
            "status": "done" if r.get("ok") else ("failed" if r.get("error") else "pending"),
            "error": r.get("error"),
            "latency_ms": r.get("latency_ms"),
            "parsed_count": r.get("parsed_count"),
            "mock": r.get("mock"),
        })

    # 目录是否存在
    drama_path = DRAMA_DIR / name
    exists = drama_path.is_dir()

    # validate（若目录存在且不是刚生成过就重算一次，很快）
    validate = status.get("validate")
    if exists and not validate:
        validate = drama_service.validate_drama(name)

    return {
        "name": name,
        "exists": exists,
        "start_time": status.get("start_time"),
        "end_time": status.get("end_time"),
        "progress_pct": progress_pct,
        "steps_completed": done_count,
        "steps_total": total,
        "steps": step_status,
        "validate": validate,
        "prompt": status.get("prompt"),
        "global_error": status.get("error"),
    }


# ============================================================
# Prompt 持久化（用于后续步骤读取用户原始创作指令）
# ============================================================

_PROMPT_FNAME = "_prompt.txt"


def _store_prompt(name: str, prompt: str) -> None:
    fp = DRAMA_DIR / name / _PROMPT_FNAME
    fp.parent.mkdir(parents=True, exist_ok=True)
    try:
        if fp.read_text(encoding="utf-8-sig").strip() == prompt.strip():
            return
    except OSError:
        pass
    import os, tempfile
    fd, tmp = tempfile.mkstemp(prefix=f".{_PROMPT_FNAME}.tmp", dir=str(fp.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt.rstrip() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(fp))
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass


def _load_stored_prompt(name: str) -> Optional[str]:
    fp = DRAMA_DIR / name / _PROMPT_FNAME
    if not fp.is_file():
        return None
    return fp.read_text(encoding="utf-8-sig").strip() or None
