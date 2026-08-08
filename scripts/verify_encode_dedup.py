"""直接测试 encode_event_to_memories 的去重逻辑。

对已有记忆的事件 27 再次调用 encode，确认不会创建重复记忆。
"""
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
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


# 1. 记录 encode 前的记忆数
mems_before = get("/api/entities/memory?limit=1000")
items_before = mems_before.get("items", []) if isinstance(mems_before, dict) else []
print(f"encode 前记忆数: {len(items_before)}")

# 2. 对 event 27 调用 encode（它已有记忆）
print("\n调用 POST /api/memory/encode_event/27 ...")
result = post("/api/memory/encode_event/27")
print(f"  返回: 新建记忆数={len(result) if isinstance(result, list) else 'N/A'}")
if isinstance(result, list):
    for m in result:
        print(f"    mem_id={m.get('id')} char_id={m.get('char_id')}")

# 3. 记录 encode 后的记忆数
mems_after = get("/api/entities/memory?limit=1000")
items_after = mems_after.get("items", []) if isinstance(mems_after, dict) else []
print(f"\nencode 后记忆数: {len(items_after)} (差值: {len(items_after) - len(items_before)})")

# 4. 检查重复
pairs = [(m.get("char_id"), m.get("source_event_id")) for m in items_after]
dupes = {k: v for k, v in Counter(pairs).items() if v > 1 and k[1] is not None}
if dupes:
    print(f"⚠️ 有重复: {dupes}")
else:
    print("✅ 无重复记忆 — 去重逻辑生效！")

# 5. 再次调用，确认幂等
print("\n再次调用 encode_event/27 ...")
result2 = post("/api/memory/encode_event/27")
mems_after2 = get("/api/entities/memory?limit=1000")
items_after2 = mems_after2.get("items", []) if isinstance(mems_after2, dict) else []
print(f"  第二次 encode 后记忆数: {len(items_after2)} (差值: {len(items_after2) - len(items_after)})")
if len(items_after2) == len(items_after):
    print("✅ 幂等：重复调用不产生新记忆")
else:
    print("⚠️ 非幂等：重复调用产生了新记忆")
