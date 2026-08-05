"""src/backend/tests/test_api.py — 端到端 API 测试。"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from fastapi.testclient import TestClient

# 在 import app 之前覆盖 SAVES_DIR
_tmp = tempfile.mkdtemp(prefix="v3_test_")
os.environ["SAVES_DIR"] = _tmp

from src.backend.http.app import app
from src.backend.storage.connection import default_save_manager

# 重置单例（因为 SAVES_DIR 改了）
import src.backend.storage.connection as conn_mod
conn_mod._default_sm = None
# 还要重置 models 的 active conn
from src.backend.storage import models
models.set_active_connection(None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def save_name():
    # 每个测试用独立的 sm 单例，避免状态串味
    import src.backend.storage.connection as conn_mod
    conn_mod._default_sm = None
    sm = default_save_manager()
    # 确保 saves_dir 存在
    sm.saves_dir.mkdir(parents=True, exist_ok=True)
    name = "apitest"
    if name in sm.list_saves():
        sm.delete_save(name)
    sm.create_save(name)
    yield name
    sm.close_active()
    sm.delete_save(name)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp(request):
    """session 结束时清理临时目录。"""
    yield
    shutil.rmtree(_tmp, ignore_errors=True)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_active_save_400_without_save(client):
    # 重置 sm 状态
    sm = default_save_manager()
    sm.close_active()
    r = client.get("/api/world/status")
    assert r.status_code == 400


def test_create_save_and_slugs(client):
    r = client.post("/api/saves", json={"name": "slugtest"})
    assert r.status_code == 200, r.text
    # 切换到该存档（create_save 自动激活，但 TestClient 无状态）
    r = client.post("/api/saves/slugtest/switch")
    assert r.status_code == 200
    r = client.get("/api/entities/_slugs")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 19
    assert "character" in data["slugs"]
    assert "map_feature" in data["slugs"]
    assert "memory" in data["slugs"]
    # 清理
    client.delete("/api/saves/slugtest")


def test_character_crud(client, save_name):
    # 切换到存档
    client.post(f"/api/saves/{save_name}/switch")
    # 创建角色
    r = client.post("/api/entities/character", json={
        "name": "沈默", "appearance_raw": "黑发", "personality_raw": "沉默", "importance": 5
    })
    assert r.status_code == 200, r.text
    char_id = r.json()["id"]
    # 查询
    r = client.get(f"/api/entities/character/{char_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "沈默"
    # 模糊查询
    r = client.get("/api/entities/character?like=沈")
    assert r.json()["count"] == 1
    # 更新
    r = client.patch(f"/api/entities/character/{char_id}", json={"status": "受伤"})
    assert r.json()["status"] == "受伤"
    # 删除
    r = client.delete(f"/api/entities/character/{char_id}")
    assert r.status_code == 200


def test_map_and_distance(client, save_name):
    client.post(f"/api/saves/{save_name}/switch")
    # 建一张大地图
    r = client.post("/api/entities/map", json={
        "name": "长安城", "desc_raw": "唐都", "map_type": "city",
        "coord_system": "cartesian_2d", "scale_unit": "m", "scale_per_unit": 1.0,
        "bbox_w": 10000, "bbox_h": 10000,
    })
    map_id = r.json()["id"]
    # 建两个要素
    r = client.post("/api/entities/map_feature", json={
        "map_id": map_id, "name": "高楼A", "feature_type": "building",
        "shape": "point", "geometry": {"x": 100, "y": 100}, "layer_z": 2,
    })
    f1 = r.json()["id"]
    r = client.post("/api/entities/map_feature", json={
        "map_id": map_id, "name": "高楼B", "feature_type": "building",
        "shape": "point", "geometry": {"x": 400, "y": 500}, "layer_z": 2,
    })
    f2 = r.json()["id"]
    # 算距离
    r = client.post("/api/maps/distance", json={
        "from": {"type": "feature", "id": f1},
        "to": {"type": "feature", "id": f2},
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["meters"] is not None
    # 预期距离 = sqrt(300^2 + 400^2) = 500
    assert abs(d["meters"] - 500.0) < 1.0
    assert "km" in d["display"] or "m" in d["display"]
    assert "步行" in d["semantic"]


def test_event_and_memory(client, save_name):
    client.post(f"/api/saves/{save_name}/switch")
    # 建角色
    r = client.post("/api/entities/character", json={
        "name": "小红", "appearance_raw": "x", "personality_raw": "y"
    })
    char_id = r.json()["id"]
    # 建事件（小红亲了小明）
    r = client.post("/api/world/events", json={
        "event_type": "narrative",
        "content_raw": "小红亲了小明一口",
        "importance": 4,
        "participants": [
            {"type": "character", "id": char_id, "role": "protagonist"},
        ],
    })
    assert r.status_code == 200, r.text
    event_id = r.json()["id"]
    # 事件 → 记忆
    r = client.post(f"/api/memory/encode_event/{event_id}")
    assert r.status_code == 200
    mems = r.json()["memories"]
    assert len(mems) == 1
    assert mems[0]["depth"] == 5  # protagonist
    mem_id = mems[0]["id"]
    # 加载记忆
    r = client.post("/api/memory/retrieve", json={"char_id": char_id, "max_count": 5})
    assert r.status_code == 200
    data = r.json()
    # outline 应该空（没建印象），memories 应该有 1 条
    assert len(data["memories"]) >= 1
    # 记忆宫殿
    r = client.get(f"/api/memory/palace/{mem_id}?depth=1")
    assert r.status_code == 200


def test_heatmap(client, save_name):
    client.post(f"/api/saves/{save_name}/switch")
    # 建地图
    r = client.post("/api/entities/map", json={
        "name": "M", "desc_raw": "x", "map_type": "city",
        "coord_system": "cartesian_2d", "scale_unit": "m",
        "bbox_w": 1000, "bbox_h": 1000,
    })
    map_id = r.json()["id"]
    # 建群体
    r = client.post("/api/entities/group", json={
        "name": "居民", "desc_raw": "x", "group_type": "city_residents",
        "primary_map_id": map_id, "center_x": 500, "center_y": 500,
    })
    group_id = r.json()["id"]
    # 建几个角色 + 位置
    for x, y in [(100, 100), (200, 200), (300, 300), (900, 900)]:
        r = client.post("/api/entities/character", json={
            "name": "c", "appearance_raw": "x", "personality_raw": "y"
        })
        cid = r.json()["id"]
        client.post("/api/entities/character_group_relation", json={
            "char_id": cid, "group_id": group_id, "role_raw": "member"
        })
        client.post("/api/entities/character_location", json={
            "char_id": cid, "map_id": map_id, "x": x, "y": y
        })
    # 刷新热力图
    r = client.post(f"/api/groups/{group_id}/refresh_heatmap")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_chars"] == 4
    # 取热力图
    r = client.get(f"/api/groups/{group_id}/heatmap")
    assert r.status_code == 200
    grid = r.json()["heatmap_grid"]
    assert grid is not None
    assert len(grid["cells"]) == 16  # default resolution


def test_world_tick(client, save_name):
    client.post(f"/api/saves/{save_name}/switch")
    # 推进 1 tick = 60 秒
    r = client.post("/api/world/tick", json={"seconds": 60})
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert meta["tick_num"] == 2  # 从 1 推进到 2
    # 时间跳跃
    r = client.post("/api/world/time_jump", json={"seconds": 86400 * 365})  # 1 年
    assert r.status_code == 200
    j = r.json()
    assert j["to_time"] != j["from_time"]
