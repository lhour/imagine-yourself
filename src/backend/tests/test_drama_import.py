"""src/backend/tests/test_drama_import — 示例剧本导入 + config + 记忆印象测试。"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from fastapi.testclient import TestClient

# 独立 SAVES_DIR 避免和其他测试串味
_tmp = tempfile.mkdtemp(prefix="v3_dramatest_")
os.environ["SAVES_DIR"] = _tmp

# 重置默认 sm 单例，避免其他测试的缓存影响
import src.backend.storage.connection as conn_mod
conn_mod._default_sm = None
from src.backend.storage import models
models.set_active_connection(None)

from src.backend.http.app import app
from src.backend.service import drama_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp(request):
    yield
    from src.backend.http.deps import CONFIG_FILE
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
    except Exception:
        pass
    import src.backend.http.deps as _deps
    _deps._cached_config = None
    shutil.rmtree(_tmp, ignore_errors=True)


# ============================================================
# Config 路由
# ============================================================

def test_config_get_defaults(client):
    r = client.get("/api/config")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "config" in d
    assert "defaults" in d
    assert d["config"]["ui_defaults"]["theme"] == "dark"
    assert d["config"]["simulation"]["tps_default"] == 1.0


def test_config_patch_and_reset(client):
    r = client.patch("/api/config", json={
        "ui_defaults": {"theme": "light", "show_debug_info": True},
        "simulation": {"tps_default": 5.0},
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["updated_keys"] == ["ui_defaults", "simulation"]
    r2 = client.get("/api/config")
    assert r2.status_code == 200
    cfg = r2.json()["config"]
    assert cfg["ui_defaults"]["theme"] == "light"
    assert cfg["simulation"]["tps_default"] == 5.0
    assert cfg["memory"]["palace_default_depth"] == 2
    r3 = client.post("/api/config/_reset")
    assert r3.status_code == 200


# ============================================================
# Dramas 路由（list / preview / init）
# ============================================================

# 使用当前项目中真实存在的剧本
DRAMA_NAME = "urban_fantasy"
EXPECTED_PROTAGONIST = "陆沉"


def test_list_dramas_has_urban_fantasy(client):
    r = client.get("/api/dramas")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    names = [d["name"] for d in items]
    assert DRAMA_NAME in names, f"期望 {DRAMA_NAME} 剧本出现在列表中，实际为 {names}"
    drama = next(d for d in items if d["name"] == DRAMA_NAME)
    assert drama["protagonist_default"] == EXPECTED_PROTAGONIST


def test_preview_drama(client):
    r = client.get(f"/api/dramas/{DRAMA_NAME}/preview")
    assert r.status_code == 200, r.text
    data = r.json()
    for f in ["meta.txt", "characters.txt", "groups.txt",
              "maps.txt", "map_features.txt", "items.txt",
              "events.txt", "settings.txt", "plot_planning.txt"]:
        assert data.get(f) is not None, f"{f} 缺失"
    char_names = {c["name"] for c in data["characters.txt"]}
    assert EXPECTED_PROTAGONIST in char_names


def test_preview_unknown_drama_404(client):
    r = client.get("/api/dramas/不存在的剧本/preview")
    assert r.status_code == 404


def test_drama_init_and_full_stats(client):
    save_name = "drama_init_test"
    sm = conn_mod.default_save_manager()
    if save_name in sm.list_saves():
        sm.close_active()
        sm.delete_save(save_name)
        conn_mod._default_sm = None

    r = client.post(f"/api/dramas/{DRAMA_NAME}/init", json={
        "save_name": save_name, "overwrite": False,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["save"] == save_name
    stats = j["stats"]
    assert stats["characters"] >= 5
    assert stats["groups"] >= 2
    assert stats["maps"] >= 3
    assert stats["map_features"] >= 5
    assert stats["events"] >= 1
    assert stats["settings"] >= 1
    assert stats["plot_planning"] >= 1
    assert stats["protagonist"] == EXPECTED_PROTAGONIST

    client.post(f"/api/saves/{save_name}/switch")
    r = client.get("/api/world/status")
    assert r.status_code == 200, r.text
    meta = r.json()["meta"]
    assert meta["tick_num"] >= 0
    assert meta["script_name"] == DRAMA_NAME
    assert meta["protagonist_id"] is not None

    r = client.get("/api/entities/character?limit=100")
    assert r.status_code == 200
    chars = r.json()["items"]
    char_names = {c["name"] for c in chars}
    assert EXPECTED_PROTAGONIST in char_names

    r = client.get("/api/entities/group?limit=20")
    assert r.json()["count"] >= 2

    protag_id = meta["protagonist_id"]
    r = client.get(f"/api/entities/character/{protag_id}")
    assert r.json()["name"] == EXPECTED_PROTAGONIST

    # 推进 tick
    r = client.post("/api/world/tick", json={"seconds": 3600})
    assert r.status_code == 200
    meta2 = r.json()["meta"]
    assert meta2["tick_num"] > meta["tick_num"]

    # 清理
    sm2 = conn_mod.default_save_manager()
    sm2.close_active()
    sm2.delete_save(save_name)


def test_drama_init_overwrite_conflict(client):
    save_name = "drama_conflict_test"
    sm = conn_mod.default_save_manager()
    if save_name in sm.list_saves():
        sm.close_active()
        sm.delete_save(save_name)
        conn_mod._default_sm = None
    r = client.post(f"/api/dramas/{DRAMA_NAME}/init", json={"save_name": save_name})
    assert r.status_code == 200
    r2 = client.post(f"/api/dramas/{DRAMA_NAME}/init", json={"save_name": save_name, "overwrite": False})
    assert r2.status_code == 409
    r3 = client.post(f"/api/dramas/{DRAMA_NAME}/init", json={"save_name": save_name, "overwrite": True})
    assert r3.status_code == 200
    sm2 = conn_mod.default_save_manager()
    sm2.close_active()
    sm2.delete_save(save_name)
