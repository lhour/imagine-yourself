"""检查最新事件与主角记忆的 v4 字段填充情况。"""
import json
import urllib.request
from urllib.parse import quote

BASE = "http://127.0.0.1:8000"


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())


# 1. 查 event 27
print("=== 事件 27 ===")
try:
    ev = get("/api/entities/event/27")
    print(f"  id={ev.get('id')} type={ev.get('event_type')} tick={ev.get('tick_num')}")
    print(f"  importance={ev.get('importance')} anchor_id={ev.get('anchor_id')}")
    print(f"  content_raw: {(ev.get('content_raw') or '')[:200]}")
except Exception as e:
    print(f"  查询失败: {e}")

# 2. 查主角(陆沉 id=1)最近记忆
print("\n=== 主角(id=1)最近记忆 ===")
try:
    mems = get("/api/entities/memory?limit=5&char_id=1")
    items = mems.get("items", []) if isinstance(mems, dict) else mems
    print(f"  记忆数: {len(items)}")
    for m in items[:5]:
        print(f"  id={m.get('id')} char_id={m.get('char_id')} depth={m.get('depth')} "
              f"source_event={m.get('source_event_id')}")
        print(f"    person_ids={m.get('person_ids')}")
        print(f"    location_ids={m.get('location_ids')}")
        print(f"    emotion_tags={m.get('emotion_tags')}")
        print(f"    vector_id={m.get('vector_id')}")
        print(f"    memory_raw: {(m.get('memory_raw') or '')[:120]}")
except Exception as e:
    print(f"  查询失败: {e}")

# 3. 查 event 27 的参与者
print("\n=== 事件 27 参与者 ===")
try:
    parts = get("/api/entities/event_participant?limit=20&event_id=27")
    items = parts.get("items", []) if isinstance(parts, dict) else parts
    print(f"  参与者数: {len(items)}")
    for p in items[:10]:
        print(f"  type={p.get('participant_type')} id={p.get('participant_id')} role={p.get('role_raw')}")
except Exception as e:
    print(f"  查询失败: {e}")
