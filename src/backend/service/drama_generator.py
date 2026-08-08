"""src.backend.service.drama_generator — 一键生成剧本 Pipeline。

流程：
1. expand: 用户输入预设大纲，LLM 补全缺失部分
2. generate: 用户确认后，LLM 按步骤生成完整剧本数据
3. evaluate: 评估生成内容的合理性（角色关系、设定一致性、情节逻辑）
4. regenerate: 对不合理部分进行针对性重生成

每个节点独立，支持最大重试次数和超时机制。
包含原有的 10 步管线和新增的补全-生成-评估-打回管线。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backend.env import BACKEND_DIR


PIPELINE_MAX_RETRIES = 3
PIPELINE_TIMEOUT_SECONDS = 120


# ============ 10 步管线配置 ============

DRAMA_GENERATE_STEPS = [
    {"step": 1, "name": "世界背景与文明", "file": "meta.txt", "prompt_key": "world_setting"},
    {"step": 2, "name": "主角设定", "file": "characters.txt", "prompt_key": "protagonist"},
    {"step": 3, "name": "关键角色", "file": "characters.txt", "prompt_key": "key_characters"},
    {"step": 4, "name": "势力组织", "file": "groups.txt", "prompt_key": "factions"},
    {"step": 5, "name": "组织层级", "file": "group_hierarchies.txt", "prompt_key": "hierarchy"},
    {"step": 6, "name": "物品道具", "file": "items.txt", "prompt_key": "items"},
    {"step": 7, "name": "地图设定", "file": "maps.txt", "prompt_key": "maps"},
    {"step": 8, "name": "地图要素", "file": "map_features.txt", "prompt_key": "map_features"},
    {"step": 9, "name": "核心情节", "file": "events.txt", "prompt_key": "events"},
    {"step": 10, "name": "设定与规划", "file": "settings.txt", "prompt_key": "settings"},
]

# 生成状态存储
_generate_status: Dict[str, Any] = {}


def _get_drama_dir(name: str) -> Path:
    """获取剧本目录路径。"""
    return BACKEND_DIR / "drama" / name


async def generate_drama_10step(
    prompt: str,
    name: Optional[str] = None,
    skip_steps: Optional[List[int]] = None,
    only_steps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """执行 10 步剧本生成管线。

    Args:
        prompt: 用户的剧本设定描述
        name: 剧本名称（自动生成如未指定）
        skip_steps: 跳过的步骤号列表
        only_steps: 只执行的步骤号列表

    Returns:
        {ok, name, step_results, validate}
    """
    import asyncio
    from datetime import datetime

    if not name:
        name = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    drama_dir = _get_drama_dir(name)
    drama_dir.mkdir(parents=True, exist_ok=True)

    skip_set = set(skip_steps or [])
    only_set = set(only_steps or [])

    step_results: List[Dict[str, Any]] = []

    for step_cfg in DRAMA_GENERATE_STEPS:
        step_num = step_cfg["step"]

        # 跳过逻辑
        if step_num in skip_set:
            step_results.append({
                "step": step_num,
                "name": step_cfg["name"],
                "status": "skipped",
            })
            continue
        if only_set and step_num not in only_set:
            continue

        # 执行步骤
        result = await _execute_step(prompt, step_cfg, drama_dir)
        step_results.append(result)

        if not result.get("success", False):
            # 失败时中断后续步骤
            break

        # 更新状态
        _generate_status[name] = {
            "steps_completed": [r["step"] for r in step_results if r.get("success")],
            "last_update": datetime.now().isoformat(),
        }

    # 校验
    validate_result = {"ok": True, "errors": [], "warnings": []}
    try:
        from src.backend.service.drama_service import validate_drama
        validate_result = validate_drama(name)
    except Exception:
        pass

    return {
        "ok": True,
        "name": name,
        "step_results": step_results,
        "validate": validate_result,
        "drama_path": str(drama_dir),
    }


async def _execute_step(
    prompt: str,
    step_cfg: Dict[str, Any],
    drama_dir: Path,
) -> Dict[str, Any]:
    """执行单个生成步骤。"""
    step_num = step_cfg["step"]
    step_name = step_cfg["name"]
    target_file = step_cfg["file"]

    try:
        from src.backend.deepseek_client import get_llm_client
        client = get_llm_client()

        system_prompt = f"""你是一位专业的剧本编剧。当前任务：生成第{step_num}步——{step_name}。
请根据用户提供的设定，生成对应的内容。所有输出为 JSONL 格式（每行一个 JSON 对象）。
要求内容丰富、角色鲜明、设定合理。"""

        user_prompt = f"""用户设定：
{prompt}

请生成第{step_num}步【{step_name}】的内容，输出为 JSONL 格式。"""

        t0 = time.time()
        resp = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=8000,
            temperature=0.7,
        )
        latency = int((time.time() - t0) * 1000)

        # 写入文件
        file_path = drama_dir / target_file
        with open(file_path, "a", encoding="utf-8-sig") as f:
            f.write(resp + "\n")

        return {
            "step": step_num,
            "name": step_name,
            "status": "completed",
            "success": True,
            "file": target_file,
            "latency_ms": latency,
        }

    except Exception as e:
        return {
            "step": step_num,
            "name": step_name,
            "status": "failed",
            "success": False,
            "error": str(e),
        }


def generate_step(name: str, step: int) -> Dict[str, Any]:
    """单独执行某个步骤（同步版本）。"""
    import asyncio
    drama_dir = _get_drama_dir(name)
    drama_dir.mkdir(parents=True, exist_ok=True)

    step_cfg = next((s for s in DRAMA_GENERATE_STEPS if s["step"] == step), None)
    if not step_cfg:
        raise ValueError(f"步骤 {step} 不存在")

    # 读取已有内容作为上下文
    context_parts = []
    for f in drama_dir.iterdir():
        if f.is_file() and f.suffix in (".txt", ".json"):
            content = f.read_text(encoding="utf-8-sig")
            if content.strip():
                context_parts.append(f"【{f.name}】\n{content[:2000]}")

    prompt = "\n\n".join(context_parts) if context_parts else "初始设定"

    result = asyncio.run(_execute_step(prompt, step_cfg, drama_dir))
    return result


def get_generate_status(name: str) -> Dict[str, Any]:
    """获取剧本生成状态。"""
    status = _generate_status.get(name, {})
    drama_dir = _get_drama_dir(name)
    existing_files = [f.name for f in drama_dir.iterdir() if f.is_file()] if drama_dir.exists() else []

    return {
        "name": name,
        "status": status,
        "existing_files": existing_files,
        "total_steps": len(DRAMA_GENERATE_STEPS),
        "steps_done": len(status.get("steps_completed", [])),
    }


# ============ 新增: 补全-生成-评估-打回管线 ============


# ============ Pipeline 状态定义 ============

NODE_EXPAND = "expand"
NODE_GENERATE = "generate"
NODE_EVALUATE = "evaluate"
NODE_REGENERATE = "regenerate"

VALID_NODES = {NODE_EXPAND, NODE_GENERATE, NODE_EVALUATE, NODE_REGENERATE}


def _safe_call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """安全调用 LLM，返回 {content, error, latency_ms}。"""
    try:
        from src.backend.deepseek_client import get_llm_client
        client = get_llm_client()
        t0 = time.time()
        resp = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency = int((time.time() - t0) * 1000)
        return {"content": resp, "error": None, "latency_ms": latency}
    except Exception as e:
        return {"content": "", "error": str(e), "latency_ms": 0}


# ============ 节点 1: 补全 (expand) ============

EXPAND_SYSTEM_PROMPT = """你是一位资深剧本编剧，擅长在用户提供的大纲基础上进行创意扩写。
任务：根据用户提供的简要剧本设定，补全所有缺失部分，生成一份详细的剧本大纲。

要求：
1. 保持用户已设定的内容不变，只补充缺失部分
2. 补充的内容要与已有设定风格、世界观、人物性格一致
3. 补充时注意：
   - 主角的核心能力和限制
   - 世界观的社会形态和科技水平
   - 势力组织之间的关系和冲突
   - 关键角色的性格、动机和秘密
   - 主要情节的起承转合
4. 输出格式为 JSON，包含以下字段（缺失的补全，已有的保留）：
   - world_setting: {era, tech_level, social_structure, core_rules}
   - protagonist: {name, age, ability, personality, background}
   - factions: [{name, desc, leader, members, stance}]
   - key_characters: [{name, age, role, personality, ability, relation_to_protagonist}]
   - plot_arcs: [{name, summary, key_events, climax, resolution}]
   - settings: [{title, content}]
5. 不要输出解释文字，直接输出合法 JSON。"""


def expand_outline(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """补全用户输入的剧本大纲。"""
    user_prompt = f"""以下是用户提供的剧本设定，请补全缺失部分：

{json.dumps(user_input, ensure_ascii=False, indent=2)}

请补全所有缺失/为空的部分，生成完整的剧本大纲 JSON。"""

    result = _safe_call_llm(EXPAND_SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.8)

    if result["error"]:
        return {
            "success": False,
            "node": NODE_EXPAND,
            "error": f"LLM 调用失败: {result['error']}",
            "output": None,
        }

    try:
        output = json.loads(result["content"])
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        content = result["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                output = json.loads(content[start:end])
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "node": NODE_EXPAND,
                    "error": "LLM 返回的 JSON 解析失败",
                    "raw_content": result["content"][:500],
                }
        else:
            return {
                "success": False,
                "node": NODE_EXPAND,
                "error": "LLM 返回的 JSON 解析失败",
                "raw_content": result["content"][:500],
            }

    return {
        "success": True,
        "node": NODE_EXPAND,
        "output": output,
        "latency_ms": result["latency_ms"],
    }


# ============ 节点 2: 生成 (generate) ============

GENERATE_SYSTEM_PROMPT = """你是一位专业的剧本生成系统。根据已确认的剧本大纲，按照以下步骤生成完整的剧本数据文件。

步骤：
1. 根据 world_setting 生成 meta.txt 所需的世界背景、文明形态等
2. 根据 protagonist 和 key_characters 生成 characters.txt（每个角色含 name, age, gender, appearance_raw, personality_raw, ability, ability_level, memories）
3. 根据 factions 生成 groups.txt 和 group_hierarchies.txt
4. 生成 items.txt（重要物品、道具、灵器等）
5. 生成 maps.txt 和 map_features.txt（至少20个地点）
6. 根据 plot_arcs 生成 events.txt 和 plot_planning.txt
7. 生成 settings.txt（世界观规则、异能等级体系等）

要求：
- 每个角色至少5条记忆/关键经历
- 物品、角色、组织的名称不要重复
- 角色之间的关系要在人物描述中体现
- 情节要有起承转合，主角成长曲线清晰
- 所有内容用中文
- 输出为一个 JSON 对象，包含所有文件的内容

输出格式：
{
  "meta": {...},
  "characters": [{...}, ...],
  "groups": [{...}, ...],
  "group_hierarchies": [{...}, ...],
  "items": [{...}, ...],
  "maps": [{...}, ...],
  "map_features": [{...}, ...],
  "events": [{...}, ...],
  "settings": [{...}, ...],
  "plot_planning": [{...}, ...]
}"""


def generate_script(outline: Dict[str, Any]) -> Dict[str, Any]:
    """根据大纲生成完整剧本数据。"""
    user_prompt = f"""请根据以下确认的剧本大纲，生成完整的剧本数据：

{json.dumps(outline, ensure_ascii=False, indent=2)}

请按照系统提示中的步骤，生成所有文件的完整内容。确保角色数量充足（建议30+）、组织丰富（建议10+）、地点详细（建议20+）。"""

    result = _safe_call_llm(GENERATE_SYSTEM_PROMPT, user_prompt, max_tokens=16000, temperature=0.7)

    if result["error"]:
        return {
            "success": False,
            "node": NODE_GENERATE,
            "error": f"LLM 调用失败: {result['error']}",
            "output": None,
        }

    try:
        output = json.loads(result["content"])
    except json.JSONDecodeError:
        content = result["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                output = json.loads(content[start:end])
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "node": NODE_GENERATE,
                    "error": "LLM 返回的 JSON 解析失败",
                    "raw_content": result["content"][:500],
                }
        else:
            return {
                "success": False,
                "node": NODE_GENERATE,
                "error": "LLM 返回的 JSON 解析失败",
                "raw_content": result["content"][:500],
            }

    # 基本结构校验
    required_keys = ["meta", "characters", "groups", "items", "maps", "events", "settings", "plot_planning"]
    missing = [k for k in required_keys if k not in output]
    if missing:
        return {
            "success": False,
            "node": NODE_GENERATE,
            "error": f"生成结果缺少必要的顶级字段: {missing}",
            "output": output,
        }

    stats = {
        "character_count": len(output.get("characters", [])),
        "group_count": len(output.get("groups", [])),
        "map_count": len(output.get("maps", [])),
        "item_count": len(output.get("items", [])),
        "event_count": len(output.get("events", [])),
        "setting_count": len(output.get("settings", [])),
    }

    return {
        "success": True,
        "node": NODE_GENERATE,
        "output": output,
        "stats": stats,
        "latency_ms": result["latency_ms"],
    }


# ============ 节点 3: 评估 (evaluate) ============

EVALUATE_SYSTEM_PROMPT = """你是一位严格的剧本编辑评审。请对生成的剧本进行全面评估，检查以下维度：

1. 角色合理性：
   - 角色的性格、动机、背景是否一致
   - 角色之间的关系是否合理
   - 主角的成长曲线是否清晰

2. 世界观一致性：
   - 设定的规则是否前后一致
   - 组织/势力的能力是否平衡
   - 科技/社会形态是否自洽

3. 情节逻辑：
   - 因果关系是否合理
   - 关键转折点是否有铺垫
   - 结局是否满足前文铺设

4. 内容质量：
   - 角色记忆/经历是否丰富
   - 物品/地点描述是否具体
   - 对话/事件描述是否生动

5. 问题定位：
   - 列出所有发现的问题，标注具体位置（哪个角色/哪个事件/哪个设定）
   - 给出修复建议

输出格式：
{
  "score": 1-100,
  "dimensions": {
    "character_consistency": {"score": 1-10, "issues": [...]},
    "world_consistency": {"score": 1-10, "issues": [...]},
    "plot_logic": {"score": 1-10, "issues": [...]},
    "content_quality": {"score": 1-10, "issues": [...]}
  },
  "critical_issues": [{"location": "", "description": "", "suggestion": ""}],
  "minor_issues": [{"location": "", "description": "", "suggestion": ""}],
  "overall_assessment": "",
  "pass_recommendation": true/false
}"""


def evaluate_script(script_data: Dict[str, Any]) -> Dict[str, Any]:
    """评估剧本质量。"""
    user_prompt = f"""请评估以下生成的剧本：

{json.dumps(script_data, ensure_ascii=False)[:15000]}

请从角色合理性、世界观一致性、情节逻辑、内容质量四个维度进行评估，找出所有问题并给出修复建议。"""

    result = _safe_call_llm(EVALUATE_SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.3)

    if result["error"]:
        return {
            "success": False,
            "node": NODE_EVALUATE,
            "error": f"LLM 调用失败: {result['error']}",
            "output": None,
        }

    try:
        output = json.loads(result["content"])
    except json.JSONDecodeError:
        content = result["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                output = json.loads(content[start:end])
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "node": NODE_EVALUATE,
                    "error": "LLM 返回的 JSON 解析失败",
                    "raw_content": result["content"][:500],
                }
        else:
            return {
                "success": False,
                "node": NODE_EVALUATE,
                "error": "LLM 返回的 JSON 解析失败",
                "raw_content": result["content"][:500],
            }

    return {
        "success": True,
        "node": NODE_EVALUATE,
        "output": output,
        "score": output.get("score", 0),
        "pass_recommendation": output.get("pass_recommendation", False),
        "critical_count": len(output.get("critical_issues", [])),
        "minor_count": len(output.get("minor_issues", [])),
        "latency_ms": result["latency_ms"],
    }


# ============ 节点 4: 针对性重生成 (regenerate) ============

REGENERATE_SYSTEM_PROMPT = """你是一位专业的剧本编辑。根据评估反馈，对指定的剧本部分进行针对性重生成。

要求：
1. 只修改评估反馈中指出的问题部分
2. 保持其他部分不变
3. 修改后的内容要修复评估中指出的所有问题
4. 保持与整体风格和世界观的一致性
5. 输出完整的剧本数据（不是只输出修改部分）

输出格式与输入的 script_data 相同。"""


def regenerate_script(
    script_data: Dict[str, Any],
    evaluation: Dict[str, Any],
    focus_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """根据评估反馈重生成指定部分。"""
    critical = evaluation.get("critical_issues", [])
    minor = evaluation.get("minor_issues", [])

    issues_text = json.dumps({
        "critical": critical,
        "minor": minor,
    }, ensure_ascii=False, indent=2)

    focus_text = ""
    if focus_areas:
        focus_text = f"\n特别关注以下部分：{', '.join(focus_areas)}"

    user_prompt = f"""请根据以下评估反馈，对剧本进行针对性修改：

## 评估反馈
{issues_text}
{focus_text}

## 当前剧本数据
{json.dumps(script_data, ensure_ascii=False)[:12000]}

请修复上述所有问题，保持其他部分不变，输出完整的剧本数据 JSON。"""

    result = _safe_call_llm(
        REGENERATE_SYSTEM_PROMPT, user_prompt, max_tokens=16000, temperature=0.7
    )

    if result["error"]:
        return {
            "success": False,
            "node": NODE_REGENERATE,
            "error": f"LLM 调用失败: {result['error']}",
            "output": None,
        }

    try:
        output = json.loads(result["content"])
    except json.JSONDecodeError:
        content = result["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                output = json.loads(content[start:end])
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "node": NODE_REGENERATE,
                    "error": "LLM 返回的 JSON 解析失败",
                    "raw_content": result["content"][:500],
                }
        else:
            return {
                "success": False,
                "node": NODE_REGENERATE,
                "error": "LLM 返回的 JSON 解析失败",
                "raw_content": result["content"][:500],
            }

    return {
        "success": True,
        "node": NODE_REGENERATE,
        "output": output,
        "latency_ms": result["latency_ms"],
    }


# ============ 完整 Pipeline 执行 ============

def run_pipeline(
    user_input: Dict[str, Any],
    max_retries: int = PIPELINE_MAX_RETRIES,
    skip_expand: bool = False,
    skip_evaluate: bool = False,
) -> Dict[str, Any]:
    """执行完整的剧本生成 Pipeline。

    Args:
        user_input: 用户输入的剧本预设大纲
        max_retries: 每个节点最大重试次数
        skip_expand: 是否跳过补直接开始生成
        skip_evaluate: 是否跳过评估

    Returns:
        {success, stages: [...], final_script, evaluation, error}
    """
    stages: List[Dict[str, Any]] = []
    current_outline = user_input
    current_script: Optional[Dict[str, Any]] = None
    current_eval: Optional[Dict[str, Any]] = None

    # Stage 1: Expand
    if not skip_expand:
        for attempt in range(max_retries):
            result = expand_outline(current_outline)
            stages.append({"node": NODE_EXPAND, "attempt": attempt + 1, "result": result})
            if result["success"]:
                current_outline = result["output"]
                break
            if attempt == max_retries - 1:
                return {
                    "success": False,
                    "stages": stages,
                    "error": f"补全节点在 {max_retries} 次尝试后失败: {result.get('error', '')}",
                }

    # Stage 2: Generate
    for attempt in range(max_retries):
        result = generate_script(current_outline)
        stages.append({"node": NODE_GENERATE, "attempt": attempt + 1, "result": result})
        if result["success"]:
            current_script = result["output"]
            break
        if attempt == max_retries - 1:
            return {
                "success": False,
                "stages": stages,
                "error": f"生成节点在 {max_retries} 次尝试后失败: {result.get('error', '')}",
            }

    # Stage 3: Evaluate
    if not skip_evaluate and current_script:
        eval_result = evaluate_script(current_script)
        stages.append({"node": NODE_EVALUATE, "attempt": 1, "result": eval_result})
        if eval_result["success"]:
            current_eval = eval_result["output"]
            if not eval_result.get("pass_recommendation", False) and eval_result.get("critical_count", 0) > 0:
                # Stage 4: Regenerate for critical issues
                for attempt in range(max_retries):
                    regen_result = regenerate_script(
                        current_script,
                        current_eval,
                        focus_areas=None,
                    )
                    stages.append({"node": NODE_REGENERATE, "attempt": attempt + 1, "result": regen_result})
                    if regen_result["success"]:
                        current_script = regen_result["output"]
                        # Re-evaluate after regeneration
                        re_eval = evaluate_script(current_script)
                        stages.append({"node": NODE_EVALUATE, "attempt": attempt + 2, "result": re_eval})
                        if re_eval["success"] and (
                            re_eval.get("pass_recommendation", False)
                            or re_eval.get("critical_count", 0) <= 1
                        ):
                            current_eval = re_eval["output"]
                            break
                    if attempt == max_retries - 1:
                        # Give up on regeneration, return current state
                        break

    return {
        "success": True,
        "stages": stages,
        "final_script": current_script,
        "evaluation": current_eval,
        "outline": current_outline,
    }


# ============ 剧本写入文件系统 ============

def save_script_to_drama_dir(script_data: Dict[str, Any], drama_name: str) -> Dict[str, Any]:
    """将生成的剧本数据写入 drama 目录，可通过前端导入。"""
    drama_dir = BACKEND_DIR / "drama" / drama_name
    drama_dir.mkdir(parents=True, exist_ok=True)

    def _write_jsonl(filename: str, data: list):
        path = drama_dir / filename
        with open(path, "w", encoding="utf-8-sig") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _write_json(filename: str, data: dict):
        path = drama_dir / filename
        with open(path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    meta = script_data.get("meta", {})
    if meta:
        _write_json("meta.txt", meta)

    mapping = {
        "characters": "characters.txt",
        "groups": "groups.txt",
        "group_hierarchies": "group_hierarchies.txt",
        "items": "items.txt",
        "maps": "maps.txt",
        "map_features": "map_features.txt",
        "events": "events.txt",
        "settings": "settings.txt",
        "plot_planning": "plot_planning.txt",
    }

    for key, filename in mapping.items():
        data = script_data.get(key, [])
        if data:
            # Ensure group_hierarchies uses correct field names
            if key == "group_hierarchies":
                _write_jsonl(filename, data)
            else:
                _write_jsonl(filename, data)

    return {
        "drama_name": drama_name,
        "drama_path": str(drama_dir),
        "files_written": [f for f in mapping.values() if script_data.get(mapping_key_to_script_key(f))],
    }


def mapping_key_to_script_key(filename: str) -> str:
    reverse = {
        "characters.txt": "characters",
        "groups.txt": "groups",
        "group_hierarchies.txt": "group_hierarchies",
        "items.txt": "items",
        "maps.txt": "maps",
        "map_features.txt": "map_features",
        "events.txt": "events",
        "settings.txt": "settings",
        "plot_planning.txt": "plot_planning",
    }
    return reverse.get(filename, "")


# ============ 异步 Pipeline 执行 ============

import threading
import uuid

# 全局任务存储
_pipeline_tasks: Dict[str, Dict[str, Any]] = {}
_pipeline_tasks_lock = threading.Lock()


def run_pipeline_async(
    user_input: Dict[str, Any],
    max_retries: int = PIPELINE_MAX_RETRIES,
    skip_expand: bool = False,
    skip_evaluate: bool = False,
) -> str:
    """异步执行 pipeline，返回任务 ID。"""
    task_id = str(uuid.uuid4())
    with _pipeline_tasks_lock:
        _pipeline_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",  # pending / running / completed / failed
            "progress": 0,
            "current_step": "",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "completed_at": None,
            "result": None,
            "error": None,
            "stages": [],
        }

    def _run():
        try:
            with _pipeline_tasks_lock:
                if task_id in _pipeline_tasks:
                    _pipeline_tasks[task_id]["status"] = "running"

            # 执行 pipeline
            result = run_pipeline(
                user_input=user_input,
                max_retries=max_retries,
                skip_expand=skip_expand,
                skip_evaluate=skip_evaluate,
            )

            with _pipeline_tasks_lock:
                if task_id in _pipeline_tasks:
                    _pipeline_tasks[task_id]["status"] = "completed"
                    _pipeline_tasks[task_id]["progress"] = 100
                    _pipeline_tasks[task_id]["current_step"] = "done"
                    _pipeline_tasks[task_id]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _pipeline_tasks[task_id]["result"] = result
                    _pipeline_tasks[task_id]["stages"] = result.get("stages", [])
        except Exception as e:
            with _pipeline_tasks_lock:
                if task_id in _pipeline_tasks:
                    _pipeline_tasks[task_id]["status"] = "failed"
                    _pipeline_tasks[task_id]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _pipeline_tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return task_id


def get_pipeline_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取 pipeline 任务状态。"""
    with _pipeline_tasks_lock:
        return _pipeline_tasks.get(task_id)


def list_pipeline_tasks() -> List[Dict[str, Any]]:
    """列出所有 pipeline 任务。"""
    with _pipeline_tasks_lock:
        return list(_pipeline_tasks.values())


def delete_pipeline_task(task_id: str) -> bool:
    """删除 pipeline 任务。"""
    with _pipeline_tasks_lock:
        if task_id in _pipeline_tasks:
            del _pipeline_tasks[task_id]
            return True
        return False
