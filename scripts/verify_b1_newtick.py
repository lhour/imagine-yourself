"""B1 验证补充：多跑几次 tick（带 player_action）直到产生 narrative 事件，验证新记忆无重复。"""
import json
import urllib.request
from collections import Counter

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


# 确保存档已切换
meta = get("/api/saves/meta")
proto_id = meta.get("protagonist_id")
print(f"当前 tick={meta['tick_num']} proto_id={proto_id}")

# tick 前的记忆数
mems_before = get("/api/entities/memory?limit=1000")
before_count = len(mems_before.get("items", [])) if isinstance(mems_before, dict) else 0
print(f"tick 前记忆数: {before_count}")

# 最多跑 3 次 tick，直到有 narrative 事件
for attempt in range(3):
    print(f"\n--- tick 尝试 {attempt+1} ---")
    action = "陆沉决定利用刚刚觉醒的异能，尝试短暂夺舍路边一个路人，确认能力是否真的有效" if attempt == 0 else None
    tick = post("/api/agent/tick", {"seconds": 60, "max_actors": 5, "player_action": action})
    narr = tick.get("narrative", "")
    events = tick.get("events_created", [])
    print(f"  tick={tick.get('tick')} events={events} narrative={len(narr)}字 mock={tick.get('mock_mode')}")

    if narr and events:
        print(f"  ✅ 产生 narrative 事件!")
        print(f"  narrative 前200字: {narr[:200]}")

        # 检查新记忆
        mems_after = get("/api/entities/memory?limit=1000")
        items_after = mems_after.get("items", []) if isinstance(mems_after, dict) else []
        print(f"\n  tick 后记忆数: {len(items_after)} (新增 {len(items_after) - before_count})")

        # 检查重复
        pairs = [(m.get("char_id"), m.get("source_event_id")) for m in items_after]
        dupes = {k: v for k, v in Counter(pairs).items() if v > 1 and k[1] is not None}
        if dupes:
            print(f"  ⚠️ 仍有重复: {dupes}")
        else:
            print(f"  ✅ 无重复记忆")

        # 显示新事件对应的记忆
        print(f"\n  新事件 {events} 对应的记忆:")
        for m in items_after:
            if m.get("source_event_id") in events:
                print(f"    mem_id={m.get('id')} char_id={m.get('char_id')} "
                      f"depth={m.get('depth')} person_ids={m.get('person_ids')}")

        # 测试 retrieve_memories 确定性
        if proto_id:
            counts = []
            for i in range(3):
                r = post("/api/memory/retrieve", {"char_id": proto_id, "max_count": 30})
                counts.append(len(r.get("memories", [])))
            print(f"\n  retrieve_memories 3次: {counts} {'✅确定性' if len(set(counts))==1 else '⚠️不一致'}")

        break
    else:
        print(f"  未产生 narrative，继续...")

print("\n验证完成。")
