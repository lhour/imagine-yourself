"""测试 retrieve_memories 的概率抽样行为。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def retrieve(char_id):
    req = urllib.request.Request(
        f"{BASE}/api/memory/retrieve",
        data=json.dumps({"char_id": char_id, "max_count": 30, "expand_palace": True}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


# 调用 10 次，看记忆数分布
counts = []
for i in range(10):
    r = retrieve(1)
    mems = r.get("memories", [])
    counts.append(len(mems))
    if i == 0:
        print(f"  第1次: outline={len(r.get('outline',[]))} memories={len(mems)} expanded={len(r.get('expanded',[]))}")
        for m in mems[:3]:
            print(f"    id={m.get('id')} depth={m.get('depth')} source={m.get('source_event_id')}")

print(f"\n10 次调用 memories 数量分布: {counts}")
print(f"  平均: {sum(counts)/len(counts):.1f}")
print(f"  出现 0 的次数: {counts.count(0)}")
