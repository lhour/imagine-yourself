"""B1 修复验证：跑 tick 后确认无重复记忆 + retrieve_memories 确定性返回。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())


def post(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    resp = urllib.request.urlopen(req, timeout=300)
    return json.loads(resp.read())


# 1. 切换存档
print("=== 1. 切换存档 ===")
r = post("/api/saves/urban_test2/switch")
print(f"  active: {r.get('active')}")

meta = get("/api/saves/meta")
proto_id = meta.get("protagonist_id")
print(f"  tick={meta['tick_num']} proto_id={proto_id}")

# 2. 统计 tick 前的记忆数
print("\n=== 2. tick 前记忆统计 ===")
mems_before = get("/api/entities/memory?limit=1000")
items_before = mems_before.get("items", []) if isinstance(mems_before, dict) else mems_before
print(f"  总记忆数: {len(items_before)}")

# 检查现有重复
from collections import Counter
pairs = [(m.get("char_id"), m.get("source_event_id")) for m in items_before]
dupes = {k: v for k, v in Counter(pairs).items() if v > 1 and k[1] is not None}
if dupes:
    print(f"  ⚠️ 仍有重复: {dupes}")
else:
    print(f"  ✅ 无重复记忆")

# 3. 跑一次 tick
print("\n=== 3. 触发 tick ===")
tick = post("/api/agent/tick", {"seconds": 60, "max_actors": 5})
print(f"  tick={tick.get('tick')} events_created={tick.get('events_created')}")
print(f"  narrative 长度: {len(tick.get('narrative',''))} 字")
new_event_ids = tick.get("events_created", [])

# 4. 统计 tick 后的记忆数
print("\n=== 4. tick 后记忆统计 ===")
mems_after = get("/api/entities/memory?limit=1000")
items_after = mems_after.get("items", []) if isinstance(mems_after, dict) else mems_after
print(f"  总记忆数: {len(items_after)} (新增 {len(items_after) - len(items_before)})")

# 检查新记忆是否有重复
pairs_after = [(m.get("char_id"), m.get("source_event_id")) for m in items_after]
dupes_after = {k: v for k, v in Counter(pairs_after).items() if v > 1 and k[1] is not None}
if dupes_after:
    print(f"  ⚠️ 仍有重复: {dupes_after}")
else:
    print(f"  ✅ 无重复记忆")

# 检查新事件对应的记忆
if new_event_ids:
    print(f"\n  新事件 {new_event_ids} 对应的记忆:")
    for m in items_after:
        if m.get("source_event_id") in new_event_ids:
            print(f"    mem_id={m.get('id')} char_id={m.get('char_id')} "
                  f"source={m.get('source_event_id')} depth={m.get('depth')} "
                  f"person_ids={m.get('person_ids')}")

# 5. 测试 retrieve_memories 确定性
print("\n=== 5. 测试 retrieve_memories（确定性） ===")
if proto_id:
    counts = []
    for i in range(5):
        r = post("/api/memory/retrieve", {"char_id": proto_id, "max_count": 30, "expand_palace": True})
        mems = r.get("memories", [])
        counts.append(len(mems))
    print(f"  5 次调用主角记忆数: {counts}")
    if len(set(counts)) == 1:
        print(f"  ✅ 确定性返回: 每次都是 {counts[0]} 条")
    else:
        print(f"  ⚠️ 非确定性: 数量不一致")

    # 显示主角记忆详情
    r = post("/api/memory/retrieve", {"char_id": proto_id, "max_count": 30, "expand_palace": True})
    mems = r.get("memories", [])
    print(f"\n  主角记忆详情 ({len(mems)} 条):")
    for m in mems:
        print(f"    id={m.get('id')} source={m.get('source_event_id')} "
              f"depth={m.get('depth')} raw={(m.get('memory_raw') or '')[:60]}")

print("\n验证完成。")
