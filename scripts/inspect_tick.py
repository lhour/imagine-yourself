"""检查 v4 tick 完整返回，定位 narrative 为空的原因。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

# 触发 tick 并打印完整返回
req = urllib.request.Request(
    f"{BASE}/api/agent/tick",
    data=json.dumps({"seconds": 60, "max_actors": 5}).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req, timeout=300)
tick = json.loads(resp.read())

print("=== tick 完整返回 keys ===")
print(list(tick.keys()))
print()
print("coordinator_valid:", tick.get("coordinator_valid"))
print("coordinator_attempts:", tick.get("coordinator_attempts"))
print("narrative repr:", repr(tick.get("narrative"))[:500])
print("events_created:", tick.get("events_created"))
print()

print("=== decisions ===")
for d in tick.get("decisions", []):
    print(f"  char_id={d.get('char_id')} name={d.get('char_name')}")
    dec = d.get("decision")
    if isinstance(dec, dict):
        print(f"    action: {repr(dec.get('action',''))[:200]}")
        print(f"    keys: {list(dec.keys())}")
    else:
        print(f"    decision: {repr(dec)[:300]}")
print()

print("=== trace ===")
for step in tick.get("trace", []):
    print(f"  {step}")
