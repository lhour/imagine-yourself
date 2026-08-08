"""综合验证：记忆去重 + 确定性加载 + coordinator narrative + vector_id 回填。"""
import json
import urllib.request
from collections import Counter

BASE = "http://127.0.0.1:8000"


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())


def post(path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


results = {}

# === 0. 切换存档 ===
print("=== 0. 切换存档 ===")
r = post("/api/saves/urban_test2/switch")
print(f"  active: {r.get('active')}")
meta = get("/api/saves/meta")
proto_id = meta.get("protagonist_id")
print(f"  tick={meta['tick_num']} proto_id={proto_id}")

# === 1. 记忆去重检查 ===
print("\n=== 1. 记忆去重检查 ===")
mems = get("/api/entities/memory?limit=1000")
items = mems.get("items", []) if isinstance(mems, dict) else mems
pairs = [(m.get("char_id"), m.get("source_event_id")) for m in items]
dupes = {k: v for k, v in Counter(pairs).items() if v > 1 and k[1] is not None}
if dupes:
    print(f"  ⚠️ 仍有重复: {dupes}")
    results["dedup"] = False
else:
    print(f"  ✅ 无重复记忆（共 {len(items)} 条）")
    results["dedup"] = True

# === 2. retrieve_memories 确定性 ===
print("\n=== 2. retrieve_memories 确定性 ===")
if proto_id:
    counts = []
    for _ in range(3):
        r = post("/api/memory/retrieve", {"char_id": proto_id, "max_count": 30}, timeout=30)
        counts.append(len(r.get("memories", [])))
    if len(set(counts)) == 1:
        print(f"  ✅ 确定性返回: 每次都是 {counts[0]} 条")
        results["deterministic"] = True
    else:
        print(f"  ⚠️ 非确定性: {counts}")
        results["deterministic"] = False

# === 3. 带 player_action 跑 tick（验证 coordinator narrative）===
print("\n=== 3. 带 player_action 跑 tick ===")
mems_before = len(items)
tick = post("/api/agent/tick", {
    "seconds": 60, "max_actors": 5,
    "player_action": "陆沉深吸一口气，集中精神尝试夺舍路边一个看手机的外卖骑手，验证异能是否有效",
})
narrative = tick.get("narrative", "") or ""
events_created = tick.get("events_created", []) or []
print(f"  tick={tick.get('tick')} events_created={events_created}")
print(f"  narrative 长度: {len(narrative)} 字")
if narrative:
    print(f"  narrative 预览: {narrative[:200]}")
    results["narrative"] = True
else:
    print("  ⚠️ narrative 仍为空")
    results["narrative"] = False

# === 4. 记忆去重（tick 后）===
print("\n=== 4. tick 后记忆去重检查 ===")
mems2 = get("/api/entities/memory?limit=1000")
items2 = mems2.get("items", []) if isinstance(mems2, dict) else mems2
print(f"  总记忆数: {mems_before} → {len(items2)}（新增 {len(items2) - mems_before}）")
pairs2 = [(m.get("char_id"), m.get("source_event_id")) for m in items2]
dupes2 = {k: v for k, v in Counter(pairs2).items() if v > 1 and k[1] is not None}
if dupes2:
    print(f"  ⚠️ tick 后有重复: {dupes2}")
    results["dedup_after"] = False
else:
    print(f"  ✅ tick 后无重复记忆")
    results["dedup_after"] = True

# === 5. vector_id 回填检查 ===
print("\n=== 5. vector_id 回填检查 ===")
new_mems = [m for m in items2 if m.get("source_event_id") in events_created]
print(f"  新事件 {events_created} 对应的记忆数: {len(new_mems)}")
filled = sum(1 for m in new_mems if m.get("vector_id"))
print(f"  vector_id 已回填: {filled}/{len(new_mems)}")
if new_mems and filled == len(new_mems):
    print("  ✅ vector_id 全部回填")
    results["vector_id"] = True
elif new_mems and filled > 0:
    print(f"  ⚠️ vector_id 部分回填: {filled}/{len(new_mems)}")
    results["vector_id"] = False
elif not new_mems:
    print("  ⚠️ 无新记忆可检查（events_created 为空）")
    results["vector_id"] = None
else:
    print("  ⚠️ vector_id 全部未回填")
    results["vector_id"] = False
    # 打印新记忆详情帮助排查
    for m in new_mems[:3]:
        print(f"    mem_id={m.get('id')} vector_id={m.get('vector_id')} "
              f"raw={str(m.get('memory_raw',''))[:50]}")

# === 汇总 ===
print("\n" + "=" * 50)
print("验证汇总:")
for k, v in results.items():
    status = "✅" if v else ("⚠️" if v is None else "❌")
    print(f"  {status} {k}: {v}")
