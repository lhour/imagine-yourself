"""验证 coordinator 空 narrative 修复：带 player_action 跑 tick，确认 narrative 非空。"""
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
    resp = urllib.request.urlopen(req, timeout=600)
    return json.loads(resp.read())


# 1. 切换存档
print("=== 1. 切换存档 ===")
r = post("/api/saves/urban_test2/switch")
print(f"  active: {r.get('active')}")
meta = get("/api/saves/meta")
print(f"  tick={meta['tick_num']} game_time={meta.get('game_time')}")

# 2. 带 player_action 跑 tick
print("\n=== 2. 带 player_action 跑 tick ===")
tick = post("/api/agent/tick", {
    "seconds": 60,
    "max_actors": 5,
    "player_action": "陆沉深吸一口气，集中精神尝试夺舍路边一个看手机的外卖骑手，验证异能是否有效",
})
narrative = tick.get("narrative", "") or ""
events_created = tick.get("events_created", []) or []
print(f"  tick={tick.get('tick')} events_created={events_created}")
print(f"  narrative 长度: {len(narrative)} 字")
if narrative:
    print(f"  narrative 预览: {narrative[:300]}")
    print("\n  ✅ narrative 非空，coordinator 修复生效！")
else:
    print("\n  ⚠️ narrative 仍为空，需进一步排查")

# 3. 检查最新 trace 的 coordinator 是否触发了 model_call#final
print("\n=== 3. 检查最新 trace ===")
traces = get("/api/traces?limit=1")
items = traces.get("items", [])
if items:
    tid = items[0]["id"]
    print(f"  最新 trace: {tid} model_rounds={items[0].get('model_rounds')} "
          f"tool_calls={items[0].get('tool_calls')}")
    # 拉详情看 coordinator
    detail = get(f"/api/traces/{tid}")

    def flatten(node, depth=0, out=None):
        if out is None:
            out = []
        out.append((depth, node))
        for c in node.get("children", []) or []:
            flatten(c, depth + 1, out)
        return out

    nodes = flatten(detail)
    in_coord = False
    coord_final_triggered = False
    coord_outputs = []
    for depth, s in nodes:
        name = s.get("name", "")
        if name == "coordinator" and depth == 1:
            in_coord = True
            continue
        if depth == 1 and name != "coordinator":
            in_coord = False
            continue
        if in_coord and s.get("type") == "model_call":
            data = s.get("data", {}) or {}
            out = str(data.get("output", "") or "")
            coord_outputs.append((name, len(out)))
            if "final" in name:
                coord_final_triggered = True
    print(f"  coordinator model_calls: {coord_outputs}")
    print(f"  coordinator 触发 model_call#final: {coord_final_triggered}")

print("\n验证完成。")
