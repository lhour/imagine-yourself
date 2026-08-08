"""src.backend.http.routers.agent — LLM 管线调用入口。"""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.http.deps import require_active_save
from src.backend.agent import advance_pipeline, pipeline, pipeline_orchestrator, pipeline_v4, time_jump_pipeline, trace
from src.backend.agent.skill.loader import (
    list_skills, get_skill, render_skill,
    list_skill_versions, get_skill_version_detail,
    create_skill_version, update_skill_version, set_skill_active_version,
    delete_skill_version,
    create_skill, delete_skill, update_skill_config,
)
from src.backend.agent.prompt.loader import (
    list_prompts, get_prompt, render_prompt,
    list_prompt_versions, get_prompt_version_detail,
    create_prompt_version, update_prompt_version, set_prompt_active_version,
    delete_prompt_version,
)
from src.backend.agent.tool.base import ToolManager
from src.backend.agent.tool import entity_tools  # noqa: F401  触发 @tool 注册
import src.backend.agent.tool  # noqa: F401  触发所有子模块（storage/map/world/anchor/graph/dynamic/knowledge/web_fetch）注册
from src.backend.deepseek_client import chat_completion, is_mock_mode

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ============================================================
# 测试连接
# ============================================================

class TestConnectionReq(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    model: Optional[str] = None


@router.post("/_test_connection")
def test_connection(req: TestConnectionReq, sm=Depends(require_active_save)):
    """调一次 LLM 看是否通（最多 512 tokens，省 token）。
    返回 {ok, message, model, latency_ms, mock}
    """
    t0 = time.time()
    mock = is_mock_mode()
    try:
        sys_p = req.system_prompt or "You are a helpful assistant. Reply with exactly \"PONG\" in Chinese."
        usr_p = req.user_prompt or "Ping me."
        with trace.request("test_connection", action="test_connection", save=sm.active_save):
            r = chat_completion(
                sys_p, usr_p,
                model=req.model,
                temperature=0.0,
                max_tokens=512,
            )
        latency = int((time.time() - t0) * 1000)
        content = (r.get("content") or "").strip()
        usage = r.get("usage") or {}
        return {
            "ok": True,
            "mock": r.get("mock", mock),
            "model": r.get("model") or req.model or "default",
            "latency_ms": latency,
            "message": f"连接成功，LLM 回复前 60 字：{content[:60]}" if content else "（LLM 空回复）",
            "reply_excerpt": content[:200],
            "usage": usage,
            "rounds": r.get("rounds"),
        }
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "mock": mock,
            "latency_ms": latency,
            "message": f"连接失败：{e}",
        }


class TickReq(BaseModel):
    seconds: int = 60
    max_actors: int = 5
    player_action: Optional[str] = None


class AdvanceReq(BaseModel):
    seconds: int
    player_action: Optional[str] = None


class TimeJumpReq(BaseModel):
    seconds: int


class CallSkillReq(BaseModel):
    skill_name: str
    user_prompt: str = ""
    variables: Optional[Dict[str, Any]] = None
    extra_tools: Optional[list] = None
    temperature: float = 0.7
    max_tokens: int = 2048


# ============================================================
# 版本管理请求体
# ============================================================

class CreateVersionReq(BaseModel):
    new_version: str
    from_version: Optional[str] = None
    skill_md: Optional[str] = None  # skill 专用


class CreatePromptVersionReq(BaseModel):
    new_version: str
    from_version: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None


class UpdateSkillVersionReq(BaseModel):
    skill_md: Optional[str] = None


class UpdatePromptVersionReq(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None


class SetActiveReq(BaseModel):
    version: str


# ============================================================
# 管线端点
# ============================================================

@router.post("/tick")
def run_tick(req: TickReq, sm=Depends(require_active_save)):
    """执行完整 tick 管线（C 阶段：纯 LLM 自主编排 + skill 硬约束）。

    在 v4 五节点之上叠加：概率事件网关 / 编排规划 / 反思闭环 / 锚点校验。
    """
    try:
        with trace.request("tick", action="tick", save=sm.active_save):
            result = pipeline_orchestrator.tick_once_orchestrated(
                req.seconds, req.max_actors, req.player_action
            )
            result["trace_id"] = trace.current_trace_id()
            return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/advance")
def run_advance(req: AdvanceReq, sm=Depends(require_active_save)):
    """统一时间推进：按跨度自动选择 tick 或 time_jump 编排剧情。"""
    try:
        with trace.request("advance", action="advance", save=sm.active_save):
            result = advance_pipeline.advance(
                req.seconds,
                player_action=req.player_action,
            )
            result["trace_id"] = trace.current_trace_id()
            return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/time_jump")
def run_time_jump(req: TimeJumpReq, sm=Depends(require_active_save)):
    """执行时间跨越管线。"""
    try:
        with trace.request("time_jump", action="time_jump", save=sm.active_save):
            result = time_jump_pipeline.time_jump(req.seconds)
            result["trace_id"] = trace.current_trace_id()
            return result
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/skills/{name}/call")
def call_skill_endpoint(name: str, req: CallSkillReq, sm=Depends(require_active_save)):
    """直接调单个 skill（开发/调试用）。"""
    if not get_skill(name):
        raise HTTPException(404, f"skill {name} 不存在")
    with trace.request(f"call_skill:{name}", action="call_skill", save=sm.active_save, skill=name):
        result = pipeline.call_skill(
            skill_name=name,
            user_prompt=req.user_prompt,
            variables=req.variables,
            extra_tools=req.extra_tools,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        result["trace_id"] = trace.current_trace_id()
        return result


# ============================================================
# Skill / Prompt / Tool 配置查询（前端「模型管理」页用）
# 这些端点仅读写磁盘配置文件，不依赖激活存档，故不加 require_active_save。
# ============================================================

@router.get("/skills")
def list_skills_endpoint():
    items = []
    for name in list_skills():
        fs = get_skill(name)
        if fs:
            items.append({
                "name": name,
                "description": fs.description,
                "default_version": fs.default_version,
                "tools": fs.tools,
                "versions": list(fs.versions.keys()),
            })
    return {"items": items, "count": len(items)}


@router.get("/skills/{name}")
def get_skill_endpoint(name: str):
    fs = get_skill(name)
    if not fs:
        raise HTTPException(404, f"skill {name} 不存在")
    return {
        "name": name,
        "description": fs.description,
        "default_version": fs.default_version,
        "active_version": fs.default_version,
        "tools": fs.tools,
        "params": fs.params,
        "versions": list(fs.versions.keys()),
        "config": fs.config,
    }


@router.get("/skills/{name}/render")
def render_skill_endpoint(
    name: str,
    version: Optional[str] = None,
):
    """渲染 skill system_prompt（注入当前变量）。

    无激活存档时 _build_variables() 返回空 dict，仍可正常渲染。
    """
    try:
        from src.backend.agent.pipeline import _build_variables
        text = render_skill(name, _build_variables(), version)
        return {"name": name, "rendered": text}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/prompts")
def list_prompts_endpoint():
    return {"items": list_prompts()}


@router.get("/prompts/{name}")
def get_prompt_endpoint(name: str):
    fp = get_prompt(name)
    if not fp:
        raise HTTPException(404, f"prompt {name} 不存在")
    return {
        "name": name,
        "default_version": fp.default_version,
        "versions": list(fp.versions.keys()),
    }


@router.get("/variables")
def get_variables():
    """返回 variables.json 内容。"""
    import json
    from src.backend.env import BACKEND_DIR
    p = BACKEND_DIR / "agent" / "conf" / "variables.json"
    if not p.is_file():
        return {"variables": {}}
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/tools")
def list_tools():
    """列出所有已注册的工具及当前描述（含覆盖）。"""
    items = ToolManager.list_with_descriptions()
    return {"tools": items, "count": len(items)}


@router.get("/tools/_slugs")
def list_entity_tool_slugs():
    """实体 CRUD 工具的 slug 清单（每实体 5 个工具）。

    注意：必须放在 /tools/{name} 之前，否则 _slugs 会被当作 name 捕获。
    """
    slugs: List[Dict[str, Any]] = []
    for model_cls in __import__(
        "src.backend.storage.models", fromlist=["ENTITIES"]
    ).ENTITIES:
        slug = model_cls.SLUG
        slugs.append({
            "slug": slug,
            "table": model_cls.TABLE,
            "tools": [
                f"{slug}_filter", f"{slug}_count", f"{slug}_bulk_create",
                f"{slug}_bulk_update", f"{slug}_bulk_delete",
            ],
        })
    return {"slugs": slugs, "count": len(slugs)}


@router.get("/tools/{name}")
def get_tool(name: str):
    spec = ToolManager.get(name)
    if not spec:
        raise HTTPException(404, f"工具 {name} 不存在")
    return {
        "name": spec.name,
        "desc": spec.desc,
        "parameters": spec.params,
        "schema": spec.to_openai_schema(),
    }


# ============================================================
# Skill 版本管理（与 Prompt 共享版本管理 API 模式）
# ============================================================

@router.get("/skills/{name}/versions")
def list_skill_versions_endpoint(name: str):
    try:
        versions = list_skill_versions(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"name": name, "versions": versions, "count": len(versions)}


@router.get("/skills/{name}/versions/{version}")
def get_skill_version_endpoint(name: str, version: str):
    try:
        return get_skill_version_detail(name, version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/skills/{name}/versions")
def create_skill_version_endpoint(
    name: str, req: CreateVersionReq
):
    try:
        return create_skill_version(
            name=name,
            new_version=req.new_version,
            from_version=req.from_version,
            skill_md=req.skill_md,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except (FileExistsError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.put("/skills/{name}/versions/{version}")
def update_skill_version_endpoint(
    name: str, version: str, req: UpdateSkillVersionReq,
):
    try:
        return update_skill_version(name, version, req.skill_md)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.put("/skills/{name}/active")
def set_skill_active_endpoint(
    name: str, req: SetActiveReq
):
    try:
        return set_skill_active_version(name, req.version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ============================================================
# Prompt 版本管理
# ============================================================

@router.get("/prompts/{name}/versions")
def list_prompt_versions_endpoint(name: str):
    try:
        versions = list_prompt_versions(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"name": name, "versions": versions, "count": len(versions)}


@router.get("/prompts/{name}/versions/{version}")
def get_prompt_version_endpoint(name: str, version: str):
    try:
        return get_prompt_version_detail(name, version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/prompts/{name}/versions")
def create_prompt_version_endpoint(
    name: str, req: CreatePromptVersionReq
):
    try:
        return create_prompt_version(
            name=name,
            new_version=req.new_version,
            from_version=req.from_version,
            system_prompt=req.system_prompt,
            user_prompt=req.user_prompt,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except (FileExistsError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.put("/prompts/{name}/versions/{version}")
def update_prompt_version_endpoint(
    name: str, version: str, req: UpdatePromptVersionReq,
):
    try:
        return update_prompt_version(
            name, version, req.system_prompt, req.user_prompt
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.put("/prompts/{name}/active")
def set_prompt_active_endpoint(
    name: str, req: SetActiveReq
):
    try:
        return set_prompt_active_version(name, req.version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ---------- 删除版本 ----------

@router.delete("/skills/{name}/versions/{version}")
def delete_skill_version_endpoint(
    name: str, version: str
):
    try:
        return delete_skill_version(name, version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/prompts/{name}/versions/{version}")
def delete_prompt_version_endpoint(
    name: str, version: str
):
    try:
        return delete_prompt_version(name, version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ============================================================
# Skill 整体 CRUD（新增 / 删除 / 更新 config.json 元信息）
# ============================================================

class CreateSkillReq(BaseModel):
    name: str
    description: str = ""
    tools: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None
    skill_md: str = ""


@router.post("/skills")
def create_skill_endpoint(req: CreateSkillReq):
    try:
        return create_skill(
            name=req.name,
            description=req.description,
            tools=req.tools,
            params=req.params,
            skill_md=req.skill_md,
        )
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/skills/{name}")
def delete_skill_endpoint(name: str):
    try:
        return delete_skill(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


class UpdateSkillConfigReq(BaseModel):
    description: Optional[str] = None
    tools: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None
    default_version: Optional[str] = None


@router.patch("/skills/{name}/config")
def update_skill_config_endpoint(
    name: str, req: UpdateSkillConfigReq
):
    try:
        return update_skill_config(
            name=name,
            description=req.description,
            tools=req.tools,
            params=req.params,
            default_version=req.default_version,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ============================================================
# Tool 描述更新（写入 tool_descriptions.json）
# ============================================================

class UpdateToolDescReq(BaseModel):
    description: str


@router.put("/tools/{name}/description")
def update_tool_description_endpoint(
    name: str, req: UpdateToolDescReq
):
    old = ToolManager.update_description(name, req.description)
    if old is None:
        raise HTTPException(404, f"工具 {name} 不存在")
    return {"name": name, "description": req.description, "old_description": old}
