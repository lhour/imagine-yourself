"""快速烟雾测试：建存档 + CRUD + 元信息。"""
import os
import sys
import tempfile

# 调整 import 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from src.backend.storage.connection import SaveManager
from src.backend.storage import models


def make_sm(tmp_path):
    return SaveManager(saves_dir=tmp_path)


def test_create_and_crud_character(tmp_path):
    sm = make_sm(tmp_path)
    sm.create_save("test1")
    assert sm.active_save == "test1"

    # 创建角色
    c = models.Character.create(
        name="沈默",
        appearance_raw="黑发青年",
        personality_raw="沉默寡言",
        importance=5,
    )
    assert c.id is not None
    assert c.name == "沈默"

    # 查询
    fetched = models.Character.get(c.id)
    assert fetched.name == "沈默"

    # 更新
    models.Character.update(c.id, status="受伤")
    assert models.Character.get(c.id).status == "受伤"

    # 列表
    chars = models.Character.list(where="name LIKE ?", params=["沈%"])
    assert len(chars) == 1

    # count
    assert models.Character.count() == 1

    # 删除
    assert models.Character.delete(c.id)
    assert models.Character.count() == 0


def test_meta_and_snapshot(tmp_path):
    sm = make_sm(tmp_path)
    sm.create_save("s1")

    meta = sm.get_meta()
    assert meta["tick_num"] == 1
    assert "源石纪元" in meta["game_time"]

    # 更新元信息
    sm.update_meta(tick_num=5, game_time="源石纪元1年1月1日12时00分00秒")
    assert sm.get_meta()["tick_num"] == 5

    # 创建角色并设为主角
    c = models.Character.create(name="主角", appearance_raw="x", personality_raw="y")
    sm.set_protagonist(c.id)
    assert sm.get_protagonist()["name"] == "主角"

    # 快照
    fname = sm.create_snapshot()
    snaps = sm.list_snapshots("s1")
    assert len(snaps) == 1
    assert snaps[0]["file"] == fname


def test_map_and_feature(tmp_path):
    sm = make_sm(tmp_path)
    sm.create_save("m1")

    # 创建地图
    m = models.Map.create(
        name="长安城",
        desc_raw="唐都",
        map_type="city",
        coord_system="cartesian_2d",
        scale_unit="m",
        bbox_w=12000,
        bbox_h=8000,
    )

    # 创建地形要素
    f = models.MapFeature.create(
        map_id=m.id,
        name="中央高楼",
        feature_type="building",
        shape="polygon",
        geometry={"points": [[6000, 4000], [6050, 4000], [6050, 4030], [6000, 4030]]},
        layer_z=2,
        color_hint="灰白",
        visual_raw="30层玻璃幕墙高楼",
    )
    assert f.id is not None
    # geometry 应被自动 JSON 序列化
    fetched = models.MapFeature.get(f.id)
    assert isinstance(fetched.geometry, dict)
    assert len(fetched.geometry["points"]) == 4


def test_migration_idempotent(tmp_path):
    """switch_save 两次不应报错，列应齐。"""
    sm = make_sm(tmp_path)
    sm.create_save("mig1")
    sm.switch_save("mig1")
    sm.switch_save("mig1")
    # 仍可正常建角色
    c = models.Character.create(name="x", appearance_raw="y", personality_raw="z")
    assert c.id is not None
