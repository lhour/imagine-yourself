"""src/backend/tests/test_drama_import.py — 示例剧本导入 + config + 记忆印象测试。"""

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
    # 清掉 config.json（如果被测试写了），以及临时 saves dir
    from src.backend.http.deps import CONFIG_FILE
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
    except Exception:
        pass
    # 重置缓存
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
    # patch
    r = client.patch("/api/config", json={
        "ui_defaults": {"theme": "light", "show_debug_info": True},
        "simulation": {"tps_default": 5.0},
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["updated_keys"] == ["ui_defaults", "simulation"]
    # 读取验证
    r2 = client.get("/api/config")
    assert r2.status_code == 200
    cfg = r2.json()["config"]
    assert cfg["ui_defaults"]["theme"] == "light"
    assert cfg["simulation"]["tps_default"] == 5.0
    # 没改的字段保持默认
    assert cfg["memory"]["palace_default_depth"] == 2
    # reset
    r3 = client.post("/api/config/_reset")
    assert r3.status_code == 200


# ============================================================
# Dramas 路由（list / preview / init）
# ============================================================

def test_list_dramas_has_sample(client):
    r = client.get("/api/dramas")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    names = [d["name"] for d in items]
    assert "sample" in names, f"期望 sample 剧本出现在列表中，实际为 {names}"
    sample = next(d for d in items if d["name"] == "sample")
    assert sample["protagonist_default"] == "艾兰·暮色"


def test_preview_drama_sample(client):
    r = client.get("/api/dramas/sample/preview")
    assert r.status_code == 200, r.text
    data = r.json()
    for f in ["meta.txt", "characters.txt", "groups.txt", "group_hierarchies.txt",
              "items.txt", "maps.txt", "map_features.txt", "events.txt",
              "settings.txt", "plot_planning.txt"]:
        assert data.get(f) is not None, f"{f} 缺失"
    # 字符数：艾兰应存在
    char_names = {c["name"] for c in data["characters.txt"]}
    assert "艾兰·暮色" in char_names


def test_preview_unknown_drama_404(client):
    r = client.get("/api/dramas/不存在的剧本/preview")
    assert r.status_code == 404


def test_drama_init_and_full_stats(client):
    """端到端：导入 sample 剧本 → 验证 stats → 验证生成的存档有数据。"""
    save_name = "drama_init_test"
    # 先清掉旧的
    sm = conn_mod._default_sm or conn_mod.default_save_manager()
    if save_name in sm.list_saves():
        sm.close_active()
        sm.delete_save(save_name)
        conn_mod._default_sm = None

    r = client.post("/api/dramas/sample/init", json={
        "save_name": save_name, "overwrite": False,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["save"] == save_name
    stats = j["stats"]
    # 关键数据必须写入
    assert stats["characters"] >= 5
    assert stats["groups"] >= 2
    assert stats["maps"] == 3
    assert stats["map_features"] >= 10
    assert stats["events"] == 5
    assert stats["settings"] == 5
    assert stats["plot_planning"] == 4
    # 主角被正确解析
    assert stats["protagonist"] == "艾兰·暮色"

    # 切换到该存档后，API 应该能读到数据
    client.post(f"/api/saves/{save_name}/switch")

    # world status: tick 应 = max(event tick) = 1（events 中最大 tick）
    r = client.get("/api/world/status")
    assert r.status_code == 200, r.text
    meta = r.json()["meta"]
    assert meta["tick_num"] >= 1  # 至少推进到有事件的地方
    assert meta["script_name"] == "sample"
    assert meta["protagonist_id"] is not None

    # character list: 至少 5 个
    r = client.get("/api/entities/character?limit=100")
    assert r.status_code == 200
    chars = r.json()["items"]
    char_names = {c["name"] for c in chars}
    for n in ["艾兰·暮色", "米蕾娅·观星者", "卡戎·灰烬使者", "老卢卡", "莉娜·灰烬"]:
        assert n in char_names, f"{n} 未写入存档"

    # group list: 2 个
    r = client.get("/api/entities/group?limit=20")
    assert r.json()["count"] >= 2
    group_names = {g["name"] for g in r.json()["items"]}
    assert "银城学派" in group_names
    assert "灰烬会" in group_names

    # events：tick=1 的那个相遇事件应存在
    r = client.get("/api/world/events?tick_from=1&tick_to=1&limit=10")
    assert r.status_code == 200
    evts = r.json()["items"]
    assert len(evts) >= 1
    # 检查 event participant 包含 item (星核碎片)
    target = evts[0]
    eid = target["id"]
    from src.backend.storage import models as M
    parts = M.EventParticipant.list(where="event_id = ?", params=[eid], limit=20)
    part_types = {(p.participant_type, p.participant_id) for p in parts}
    # 至少含两个 character (艾兰 + 莉娜)
    char_count = sum(1 for t, _ in part_types if t == "character")
    assert char_count >= 2, f"期望至少 2 个角色参与者，实际 {char_count}"

    # protagonist 主角位置应在学徒宿舍所在的 map
    protag_id = meta["protagonist_id"]
    r = client.get(f"/api/entities/character/{protag_id}")
    assert r.json()["name"] == "艾兰·暮色"
    # character_location 通用接口需要 where 精确过滤
    r = client.get("/api/entities/character_location",
                   params={"where": "char_id = ?", "params": f"[{protag_id}]"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1
    # 所有 5 个角色都有位置记录
    r2 = client.get("/api/entities/character_location?limit=100")
    assert r2.json()["count"] == 5

    # 推进 tick
    r = client.post("/api/world/tick", json={"seconds": 3600})
    assert r.status_code == 200
    meta2 = r.json()["meta"]
    assert meta2["tick_num"] > meta["tick_num"]

    # 再写入一条印象：艾兰 对 莉娜
    # 先找到莉娜的 id
    lina = next(c for c in chars if c["name"] == "莉娜·灰烬")
    r = client.post(f"/api/memory/impressions/{protag_id}", json={
        "target_char_id": lina["id"],
        "impression_raw": "深夜潜入我宿舍的、琥珀色眼睛的女孩，她有机会却没有杀我。",
        "valence": 0.3,
        "arousal": 0.8,
        "weight": 0.8,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["created"] is True
    assert j["impression"]["target_char_id"] == lina["id"]

    # 读取印象列表
    r = client.get(f"/api/memory/impressions/{protag_id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1

    # 清理存档
    sm2 = conn_mod.default_save_manager()
    sm2.close_active()
    sm2.delete_save(save_name)


def test_drama_init_overwrite_conflict(client):
    """overwrite=False 时重复创建应 409。"""
    save_name = "drama_conflict_test"
    sm = conn_mod.default_save_manager()
    if save_name in sm.list_saves():
        sm.close_active()
        sm.delete_save(save_name)
        conn_mod._default_sm = None
    r = client.post("/api/dramas/sample/init", json={"save_name": save_name})
    assert r.status_code == 200
    # 不 overwrite → 409
    r2 = client.post("/api/dramas/sample/init", json={"save_name": save_name, "overwrite": False})
    assert r2.status_code == 409
    # 允许 overwrite → 200
    r3 = client.post("/api/dramas/sample/init", json={"save_name": save_name, "overwrite": True})
    assert r3.status_code == 200
    # 清理
    sm2 = conn_mod.default_save_manager()
    sm2.close_active()
    sm2.delete_save(save_name)
