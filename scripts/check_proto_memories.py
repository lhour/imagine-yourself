"""检查主角(id=1)的记忆是否存在，以及前端如何获取记忆。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())


# 1. 通过 entities API 查 char_id=1 的记忆
print("=== entities/memory?char_id=1&limit=10 ===")
try:
    r = get("/api/entities/memory?char_id=1&limit=10")
    items = r.get("items", []) if isinstance(r, dict) else r
    print(f"  count: {r.get('count') if isinstance(r, dict) else len(items)}")
    for m in items[:5]:
        print(f"  id={m.get('id')} char_id={m.get('char_id')} source_event={m.get('source_event_id')}")
except Exception as e:
    print(f"  失败: {e}")

# 2. 查所有记忆，看 char_id 分布
print("\n=== entities/memory?limit=30 (全部) ===")
try:
    r = get("/api/entities/memory?limit=30")
    items = r.get("items", []) if isinstance(r, dict) else r
    print(f"  总数: {r.get('count') if isinstance(r, dict) else len(items)}")
    char_dist = {}
    for m in items:
        cid = m.get("char_id")
        char_dist[cid] = char_dist.get(cid, 0) + 1
    print(f"  char_id 分布: {char_dist}")
    # 看看有没有 char_id=1 的
    proto_mems = [m for m in items if m.get("char_id") == 1]
    print(f"  char_id=1 的记忆数: {len(proto_mems)}")
    for m in proto_mems[:3]:
        print(f"    id={m.get('id')} source_event={m.get('source_event_id')} "
              f"raw={(m.get('memory_raw') or '')[:80]}")
except Exception as e:
    print(f"  失败: {e}")

# 3. 查 event 27 的参与者，确认 char_id=1 是否在内
print("\n=== event 27 参与者 ===")
try:
    r = get("/api/entities/event_participant?limit=20&event_id=27")
    items = r.get("items", []) if isinstance(r, dict) else r
    char1_parts = [p for p in items if p.get("participant_type") == "character" and p.get("participant_id") == 1]
    print(f"  char_id=1 参与者记录: {len(char1_parts)}")
    for p in char1_parts:
        print(f"    id={p.get('id')} role={p.get('role_raw')}")
except Exception as e:
    print(f"  失败: {e}")
