"""src/backend/tests/test_agent.py — 阶段二 LLM 管线测试。"""
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.mkdtemp(prefix="v3_agent_test_")
os.environ["SAVES_DIR"] = _tmp
os.environ["DEEPSEEK_API_KEY"] = ""  # 强制 mock 模式

from src.backend.http.app import app
from src.backend.storage.connection import default_save_manager
import src.backend.storage.connection as conn_mod
from src.backend.storage import models
from src.backend import deepseek_client
from src.backend.agent.skill.loader import get_skill, _clear_cache as _clear_skill_cache
from src.backend.env import BACKEND_DIR

SKILLS_DIR = BACKEND_DIR / "agent" / "conf" / "skills"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def save_with_data():
    conn_mod._default_sm = None
    sm = default_save_manager()
    sm.saves_dir.mkdir(parents=True, exist_ok=True)
    name = "agenttest"
    if name in sm.list_saves():
        sm.delete_save(name)
    sm.create_save(name)
    # 建一张地图 + 角色
    m = models.Map.create(
        name="酒馆", desc_raw="x", map_type="building",
        coord_system="cartesian_2d", scale_unit="m", bbox_w=100, bbox_h=100
    )
    c = models.Character.create(
        name="沈默", appearance_raw="x", personality_raw="沉默", importance=5
    )
    sm.set_protagonist(c.id)
    yield name
    sm.close_active()
    sm.delete_save(name)


@pytest.fixture(scope="session", autouse=True)
def _cleanup(request):
    yield
    shutil.rmtree(_tmp, ignore_errors=True)


# ============================================================
# Mock 模式验证
# ============================================================

def test_mock_mode_active():
    """无 API key 时应进入 mock 模式。"""
    assert deepseek_client.is_mock_mode(), "应处于 mock 模式"


def test_mock_chat_completion():
    """mock chat_completion 应返回结构化响应。"""
    r = deepseek_client.chat_completion(
        system_prompt="test",
        user_prompt="请润色：小红亲了小明",
    )
    assert r["content"]  # mock 应返回非空
    assert "mock" in r["content"] or "润色" in r["content"]
    assert r["mock"] is True


# ============================================================
# Skill / Tool 配置查询
# ============================================================

def test_list_skills_endpoint(client, save_with_data):
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 18
    names = [s["name"] for s in data["items"]]
    # D1 修订：actor_decide/world_react v1 已删，统一用 v2
    assert "actor_decide_v2" in names
    assert "world_react_v2" in names
    assert "time_skip_summarizer" in names
    assert "memory_encoder" in names
    assert "player_action" in names
    # 润色已整合为单一 event_polisher skill（风格由 polish_style 变量指定）
    assert "polish_style_selector" in names
    assert "event_polisher" in names
    # C 阶段新增 skill
    assert "tick_orchestrator" in names
    assert "consistency_checker" in names
    assert "anchor_check" in names


def test_get_skill_version(client, save_with_data):
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills/actor_decide_v2/versions/v0")
    assert r.status_code == 200
    sp = r.json()["system_prompt"]
    assert "actor_decide" in sp
    assert "${role_name}" in sp  # 变量未渲染


def test_render_skill_endpoint(client, save_with_data):
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills/actor_decide_v2/render")
    assert r.status_code == 200
    rendered = r.json()["rendered"]
    # role_name / game_time / tick_num 来自存档元信息，应被替换
    assert "沈默" in rendered
    assert "${role_name}" not in rendered
    assert "${game_time}" not in rendered
    assert "${tick_num}" not in rendered
    # scene_description 来自调用上下文，未提供时保留占位符（设计如此）
    # assert "${scene_description}" not in rendered


def test_list_tools_endpoint(client, save_with_data):
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/tools")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 100
    tool_names = [t["name"] for t in data["tools"]]
    assert "character_filter" in tool_names, f"character_filter not in {tool_names[:20]}... total={data['count']}"
    assert "memory_retrieve" in tool_names
    assert "map_distance" in tool_names


def test_get_variables(client, save_with_data):
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/variables")
    assert r.status_code == 200
    vars = r.json()["variables"]
    assert "role_name" in vars
    assert "game_time" in vars
    assert "polish_mode" in vars


# ============================================================
# Tick 管线端到端
# ============================================================

def test_tick_pipeline_mock(client, save_with_data):
    """完整 tick 管线（mock 模式）应能跑通。

    C 阶段后 /api/agent/tick 走 orchestrator（v4 + 编排层），
    trace 结构与 v3 不同：保留 advance_tick / actor_decide / coordinator 等核心节点。
    """
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.post("/api/agent/tick", json={"seconds": 60, "max_actors": 3})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tick"] == 2  # 推进 1 tick
    assert "源石纪元" in data["game_time"]
    assert data["mock_mode"] is True
    # orchestrator 应返回 orchestration 摘要
    assert data.get("orchestrated") is True
    orch = data.get("orchestration", {})
    assert "probability_events" in orch
    assert "plan" in orch
    assert "reflection" in orch
    assert "anchor_check" in orch
    # v4 五节点 trace
    steps = [t["name"] for t in data["trace"]]
    assert "advance_tick" in steps
    assert "actor_decide" in steps  # v4 step name 仍为 actor_decide
    assert "coordinator" in steps
    assert "character_updater" in steps


def test_time_jump_pipeline_mock(client, save_with_data):
    """时间跨越管线（mock 模式）。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.post("/api/agent/time_jump", json={"seconds": 86400 * 365})  # 1 年
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["span_type"] in ("short", "medium", "long", "ultra_long", "epochal")
    assert data["to_time"] != data["from_time"]
    assert data["mock_mode"] is True


def test_call_skill_endpoint(client, save_with_data):
    """直接调 skill。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.post("/api/agent/skills/event_polisher/call", json={
        "skill_name": "event_polisher",
        "user_prompt": "事件 raw：小红亲了小明\n请润色。",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["skill"] == "event_polisher"
    assert data["mock"] is True
    assert data["content"]  # 应有 mock 返回


# ============================================================
# Skill 版本管理
# ============================================================

def test_list_skill_versions_endpoint(client, save_with_data):
    """列出某 skill 的所有版本。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills/actor_decide_v2/versions")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "actor_decide_v2"
    assert "v0" in data["versions"]
    assert data["count"] >= 1


def test_get_skill_version_detail_endpoint(client, save_with_data):
    """取某版本详情。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills/actor_decide_v2/versions/v0")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "actor_decide_v2"
    assert data["version"] == "v0"
    # API 字段名为 system_prompt（保留 LLM 通用术语），skill_md 为文件字段名
    assert "actor_decide" in data["system_prompt"]
    assert "actor_decide" in data["skill_md"]


def test_get_skill_version_not_found(client, save_with_data):
    """取不存在的版本应返回 404。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/skills/actor_decide_v2/versions/v99")
    assert r.status_code == 404


def test_create_update_setactive_skill_version(client, save_with_data):
    """端到端（文件存储）：创建 v1 → 更新内容 → 设为激活 → 验证 → 清理。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    name = "actor_decide_v2"
    v1_dir = SKILLS_DIR / name / "v1"
    config_path = SKILLS_DIR / name / "config.json"

    # 记录原始 default_version 以便恢复（utf-8-sig 兼容 BOM）
    orig_default = json.loads(config_path.read_text(encoding="utf-8-sig"))["default_version"]
    orig_content = config_path.read_bytes()

    try:
        # 1. 创建 v1（从 v0 copytree）
        r = client.post(f"/api/agent/skills/{name}/versions", json={
            "new_version": "v1",
            "from_version": "v0",
        })
        assert r.status_code == 200, r.text
        assert r.json()["created"] is True
        assert v1_dir.is_dir()

        # 2. 重复创建应 400
        r = client.post(f"/api/agent/skills/{name}/versions", json={
            "new_version": "v1", "from_version": "v0",
        })
        assert r.status_code == 400

        # 3. 非法版本号应 400
        r = client.post(f"/api/agent/skills/{name}/versions", json={
            "new_version": "bad_version", "from_version": "v0",
        })
        assert r.status_code == 400

        # 4. 更新 v1 内容
        new_md = "# 测试 v1 内容\n这是测试用的新 skill.md。"
        r = client.put(f"/api/agent/skills/{name}/versions/v1", json={"skill_md": new_md})
        assert r.status_code == 200
        assert r.json()["updated"] is True

        # 验证更新生效
        r = client.get(f"/api/agent/skills/{name}/versions/v1")
        assert r.status_code == 200
        # API 字段名为 system_prompt（保留 LLM 通用术语）
        assert r.json()["system_prompt"] == new_md
        assert r.json()["skill_md"] == new_md

        # 5. 设为激活
        r = client.put(f"/api/agent/skills/{name}/active", json={"version": "v1"})
        assert r.status_code == 200
        assert r.json()["active_version"] == "v1"

        # 验证 config.json 已重写
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        assert cfg["default_version"] == "v1"

        # 验证 GET /skills/{name} 反映新激活版本
        r = client.get(f"/api/agent/skills/{name}")
        assert r.json()["default_version"] == "v1"

        # 6. 设不存在版本应 404
        r = client.put(f"/api/agent/skills/{name}/active", json={"version": "v99"})
        assert r.status_code == 404

    finally:
        # 清理：删 v1 目录 + 完全恢复 config.json 原始字节
        _clear_skill_cache(name)
        if v1_dir.is_dir():
            shutil.rmtree(v1_dir, ignore_errors=True)
        config_path.write_bytes(orig_content)
        _clear_skill_cache(name)


# ============================================================
# 实体工具 slug 清单
# ============================================================

def test_list_entity_tool_slugs(client, save_with_data):
    """GET /api/agent/tools/_slugs 返回每实体 5 个工具。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/tools/_slugs")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 19  # 至少 19 个实体
    slugs = [s["slug"] for s in data["slugs"]]
    assert "character" in slugs
    assert "map" in slugs
    assert "memory" in slugs
    # 每实体 5 个工具
    for s in data["slugs"]:
        assert len(s["tools"]) == 5
        assert s["tools"][0] == f"{s['slug']}_filter"


def test_get_tool_endpoint(client, save_with_data):
    """GET /api/agent/tools/{name} 返回单个工具详情。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/tools/character_filter")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "character_filter"
    assert "parameters" in data
    assert "schema" in data


def test_get_tool_not_found(client, save_with_data):
    """GET /api/agent/tools/{name} 不存在工具应 404。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/tools/nonexistent_tool_xyz")
    assert r.status_code == 404


# ============================================================
# Prompt 版本管理（无配置时也应正常响应）
# ============================================================

def test_list_prompts_endpoint(client, save_with_data):
    """GET /api/agent/prompts 返回列表（可能为空）。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/prompts")
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_prompt_not_found(client, save_with_data):
    """不存在的 prompt 应 404。"""
    client.post(f"/api/saves/{save_with_data}/switch")
    r = client.get("/api/agent/prompts/nonexistent_prompt_xyz")
    assert r.status_code == 404
