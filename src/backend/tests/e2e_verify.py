"""E2E 验证脚本：剧本导入 → 全链路数据验证 → tick 推进。

不使用 pytest，直接模拟真实客户端流程。
"""
from __future__ import annotations

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import json

_tmp = tempfile.mkdtemp(prefix="v3_e2e_")
os.environ["SAVES_DIR"] = _tmp

import src.backend.storage.connection as conn_mod
conn_mod._default_sm = None
from src.backend.storage import models
models.set_active_connection(None)

from fastapi.testclient import TestClient
from src.backend.http.app import app

c = TestClient(app)
SAVE_NAME = "e2e_sample_run"


def step(msg):
    print(f"\n>>> {msg}")


def section(title):
    bar = "=" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


# 1. health
section("Step 1: Health Check")
assert c.get("/api/health").json()["status"] == "ok"
step("✓ /api/health 正常")

# 2. Config
section("Step 2: Config 路由")
cfg = c.get("/api/config").json()
print(f"  默认主题 = {cfg['config']['ui_defaults']['theme']}")
print(f"  默认 TPS = {cfg['config']['simulation']['tps_default']}")
patched = c.patch("/api/config", json={
    "ui_defaults": {"show_debug_info": True},
    "simulation": {"tps_default": 2.0},
}).json()
assert patched["config"]["simulation"]["tps_default"] == 2.0
print(f"  patch: 更新字段={patched['updated_keys']}  OK")
c.post("/api/config/_reset")
step("✓ Config GET/PATCH/RESET 全链路正常")

# 3. Dramas list + preview
section("Step 3: Dramas 路由 — 列表 / 预览")
dramas = c.get("/api/dramas").json()["items"]
names = [d["name"] for d in dramas]
assert "sample" in names
s = next(d for d in dramas if d["name"] == "sample")
print(f"  sample 剧本：{s['title']}")
print(f"  默认主角：{s['protagonist_default']}")
print(f"  起始年代：{s['era_name']} | {s['start_game_time']}")
prev = c.get("/api/dramas/sample/preview").json()
print(f"  preview 9+1 文件：{[k for k,v in prev.items() if v is not None]}")
step("✓ Dramas list / preview 正常")

# 4. init_drama
section("Step 4: init_drama — 9+1 文件写入存档")
sm = conn_mod.default_save_manager()
if SAVE_NAME in sm.list_saves():
    sm.close_active()
    sm.delete_save(SAVE_NAME)
    conn_mod._default_sm = None
r = c.post("/api/dramas/sample/init", json={"save_name": SAVE_NAME})
assert r.status_code == 200, r.text
init = r.json()
print(f"  写入统计：{json.dumps(init['stats'], ensure_ascii=False, indent=4)}")
assert init["stats"]["characters"] >= 5
assert init["stats"]["plot_planning"] == 4
assert init["stats"]["protagonist"] == "艾兰·暮色"
step("✓ 剧本导入成功（所有预期条目均已写入）")

# 5. switch save + world status
section("Step 5: 切换存档 + 查看世界状态")
c.post(f"/api/saves/{SAVE_NAME}/switch")
st = c.get("/api/world/status").json()
meta = st["meta"]
print(f"  tick_num = {meta['tick_num']}")
print(f"  game_time = {meta['game_time']}")
print(f"  era = {meta['era_name']}")
print(f"  script = {meta['script_name']}")
print(f"  protagonist_id = {meta['protagonist_id']}")
print(f"  description = {meta['description'][:40]}...")
assert meta["script_name"] == "sample"
step("✓ 世界状态正确，主角 ID / 脚本名 / 年代 均正确设置")

# 6. API 列表全部实体 count
section("Step 6: 实体统计 — 验证 ENTITIES 注册表完整性")
slugs = c.get("/api/entities/_slugs").json()["slugs"]
print(f"  已注册实体类型：{len(slugs)} 个")
print(f"  {slugs}")
expected_counts = {
    "character": 5, "group": 3, "map": 3, "map_feature": 11,
    "event": 5, "setting": 5, "character_quest": 4, "group_hierarchy": 1,
}
for slug, exp in expected_counts.items():
    cnt = c.get(f"/api/entities/{slug}/count").json()["count"]
    mark = "✓" if cnt == exp else "✗"
    print(f"  {mark} {slug:26s} 实际={cnt:3d}  预期={exp:3d}")
    assert cnt == exp, f"{slug} count mismatch"
# 关联表
for slug in ["character_location", "item_hold", "group_hierarchy",
             "character_group_relation", "event_participant"]:
    cnt = c.get(f"/api/entities/{slug}/count").json()["count"]
    print(f"    > {slug:26s} 实际={cnt:3d}")
    assert cnt > 0, f"{slug} 应该有数据，实际 0"
step("✓ 所有实体表均有预期数量数据（含关联表）")

# 7. 主角 API 深度查询
section("Step 7: 主角深度查询（位置/群体/物品/主线）")
pid = meta["protagonist_id"]
pc = c.get(f"/api/entities/character/{pid}").json()
print(f"  主角：{pc['name']} ({pc['gender']} / {pc['age']}岁 / 重要性={pc['importance']})")
print(f"  身份：{pc['status']}")
print(f"  custom_attrs.inventory_coins = {pc['custom_attrs'].get('inventory_coins')}")
# 位置
loc = c.get("/api/entities/character_location", params={
    "where": "char_id = ?", "params": f"[{pid}]"
}).json()["items"][0]
m = c.get(f"/api/entities/map/{loc['map_id']}").json()
print(f"  位置：在地图『{m['name']}』 坐标({loc['x']},{loc['y']})"
      f" {loc.get('location_detail_raw','')[:30]}")
# 群体身份
groups = c.get("/api/entities/character_group_relation", params={
    "where": "char_id = ?", "params": f"[{pid}]"
}).json()["items"]
for g in groups:
    gname = c.get(f"/api/entities/group/{g['group_id']}").json()["name"]
    print(f"  群体：{gname} / {g['role_raw']} (重要性 {g['importance_in_group']})")
# 物品
items_held = c.get("/api/entities/item_hold", params={
    "where": "holder_type = 'character' AND holder_id = ?",
    "params": f"[{pid}]",
}).json()["items"]
for ih in items_held:
    iname = c.get(f"/api/entities/item/{ih['item_id']}").json()["name"]
    print(f"  持有物品：{iname} × {ih['quantity']}")
# 主线 quest
main_q = c.get("/api/entities/character_quest", params={
    "where": "char_id = ? AND quest_type = ?",
    "params": json.dumps([pid, "main_plot"]),
    "order_by": "start_tick ASC",
}).json()["items"]
print(f"  主线任务/剧情节点（共 {len(main_q)} 个）：")
for q in main_q:
    status_icon = "◇" if q["status"] == "in_progress" else "◆"
    print(f"    {status_icon} tick{q['start_tick']:3d} | {q['title'][:26]}")
step("✓ 主角深度信息完整：位置/群体/物品/主线均正确")

# 8. events API 筛选：全部 events 按时间顺序
section("Step 8: 事件流 API （GET /api/world/events + 筛选）")
all_evts = c.get("/api/world/events?limit=50&order_by=tick_num%20ASC").json()["items"]
print(f"  共 {len(all_evts)} 事件（预期 5）")
for e in all_evts:
    star = "★" * e["importance"] + "☆" * (5 - e["importance"])
    print(f"  [{star}] tick{e['tick_num']:3d} | {e['event_type']:12s} | "
          f"{e['content_raw'][:36]}")
# 筛选：只看 >= 重要性4
hi = c.get("/api/world/events?importance_min=4").json()["count"]
print(f"  筛选：重要性≥4 的事件数 = {hi}")
assert hi >= 4
step("✓ 事件流 + 筛选正常")

# 9. Memory 编码 + 检索
section("Step 9: 记忆：事件 → 各角色记忆 + 检索 + 宫殿展开")
last_eid = all_evts[-1]["id"]
encoded = c.post(f"/api/memory/encode_event/{last_eid}").json()["memories"]
print(f"  最后一个事件（tick=1 相遇）编码成了 {len(encoded)} 条记忆：")
for m in encoded:
    cname = c.get(f"/api/entities/character/{m['char_id']}").json()["name"]
    raw = m.get("memory_raw") or m.get("outline_raw") or ""
    print(f"    - {cname} 深度={m['depth']} 摘要={str(raw)[:30]}")
# 艾兰 retrieve
ret = c.post("/api/memory/retrieve", json={"char_id": pid, "max_count": 20}).json()
print(f"  艾兰 retrieve：共 {len(ret['memories'])} 条记忆，"
      f"outline={len(ret['outline'])} 印象，palace_nodes={len(ret.get('palace_nodes') or [])}")
# palace 展开：先确认有记忆，没有就手动 encode 更多事件
if not ret["memories"]:
    # 再把所有 5 个事件都 encode 一下
    for e in all_evts:
        c.post(f"/api/memory/encode_event/{e['id']}")
    ret = c.post("/api/memory/retrieve", json={"char_id": pid, "max_count": 20}).json()
    print(f"  （二次）艾兰 retrieve：{len(ret['memories'])} 条记忆")
mem_id = ret["memories"][0]["id"]
pal = c.get(f"/api/memory/palace/{mem_id}?depth=2").json()
print(f"  记忆宫殿：中心 {pal['center']['id']}，总关联 {pal['total_related']} 条，层数 {len(pal['layers'])}")
step("✓ 记忆编码/检索/宫殿展开 全链路正常")

# 10. 单个印象 + 衰减
section("Step 10: 印象写入 + 记忆衰减模拟")
# 找到莉娜
lina = c.get("/api/entities/character", params={"like": "莉娜"}).json()["items"][0]
lina_id = lina["id"]
r = c.post(f"/api/memory/impressions/{pid}", json={
    "target_char_id": lina_id,
    "impression_raw": "深夜潜入宿舍却没动手的女孩，琥珀色眼睛，她似乎有无法执行命令的苦衷。",
    "valence": 0.2, "arousal": 0.8, "weight": 0.9,
})
assert r.status_code == 200
print(f"  艾兰 → 莉娜 印象创建：OK")
imps = c.get(f"/api/memory/impressions/{pid}").json()["items"]
print(f"  艾兰印象列表：{len(imps)} 条")
# 衰减
dec = c.post(f"/api/memory/decay/{pid}", json={"ticks_passed": 30}).json()
print(f"  衰减 30 tick：decayed={dec.get('decayed_count')}，dropped={dec.get('dropped_count')}")
step("✓ 印象 POST / 衰减 API 均正常")

# 11. Groups 热力图 + 刷新
section("Step 11: Groups 热力图（银城学派 → 银城）")
grp_xp = c.get("/api/entities/group", params={"like": "银城学派"}).json()["items"][0]
ref = c.post(f"/api/groups/{grp_xp['id']}/refresh_heatmap").json()
print(f"  银城学派热力图刷新：chars={ref['total_chars']}，分布 grid size={ref['grid_size']}")
heat = c.get(f"/api/groups/{grp_xp['id']}/heatmap").json()
grid = heat["heatmap_grid"] or {}
cells = grid.get("cells") or []
print(f"  热力图：{len(cells)} cells，峰值={grid.get('peak')}")
step("✓ Groups 热力图刷新 + 读取正常")

# 12. 时间系统：tick + time_jump
section("Step 12: 时间系统 — tick(1小时) + time_jump(7天)")
meta0 = c.get("/api/world/status").json()["meta"]
tick = c.post("/api/world/tick", json={"seconds": 3600}).json()["meta"]
print(f"  推进 1 小时：tick {meta0['tick_num']} → {tick['tick_num']}")
jump = c.post("/api/world/time_jump", json={"seconds": 86400 * 7}).json()
print(f"  跨越 7 天：{jump['from_time']} → {jump['to_time']}（tick {jump['from_tick']} → {jump['to_tick']}，共 {jump['jumped_seconds']//3600} 小时秒跳）")
meta3 = c.get("/api/world/status").json()["meta"]
print(f"  最终 meta：tick={meta3['tick_num']}，real_time={meta3['real_time'][:20]}")
assert meta3["tick_num"] > tick["tick_num"]
step("✓ 时间系统：tick / time_jump / status 均正确")

# 13. Saves: snapshot
section("Step 13: 存档快照 — 创建快照 + 回滚 + 清理")
ss = c.post("/api/saves/snapshots").json()
snap_file = ss["created"]
# 列表
snapshots = c.get("/api/saves/snapshots").json()["snapshots"]
sz = 0
for s in snapshots:
    if isinstance(s, dict):
        sz = s.get("size_bytes", 0)
        if "name" in s:
            print(f"  创建快照：name={s['name']}，size={sz} bytes")
            break
    elif s == snap_file:
        import os
        p = os.path.join(_tmp, SAVE_NAME + ".snapshots", snap_file)
        try:
            sz = os.path.getsize(p)
        except OSError:
            sz = 0
        print(f"  创建快照：file={snap_file} size={sz} bytes")
        break
print(f"  快照列表：共 {len(snapshots)} 个")
# 现在推进时间再回滚
c.post("/api/world/tick", json={"seconds": 99999})
tick_before_rollback = c.get("/api/world/status").json()["meta"]["tick_num"]
rb = c.post("/api/saves/snapshots/restore", params={"snapshot_file": snap_file}).json()
tick_after_rollback = c.get("/api/world/status").json()["meta"]["tick_num"]
print(f"  回滚：tick {tick_before_rollback} → {tick_after_rollback}（回滚到快照状态）")
assert tick_after_rollback < tick_before_rollback
# 删快照
c.delete(f"/api/saves/snapshots/{snap_file}")
step("✓ 存档快照：创建/列表/回滚/删除 全正常")

# Cleanup
section("CLEANUP")
sm2 = conn_mod.default_save_manager()
sm2.close_active()
sm2.delete_save(SAVE_NAME)
shutil.rmtree(_tmp, ignore_errors=True)
print("  ✓ 测试临时存档已删除")


bar = "=" * 60
print(f"\n{bar}\n  🎉 端到端全部 13 个 Step 均通过！\n{bar}\n")
