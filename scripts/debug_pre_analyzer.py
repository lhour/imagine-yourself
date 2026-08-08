"""调试 pre_analyzer 返回空的原因：检查 trace 中的 skill_call span。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=15)
    return json.loads(resp.read())


def post(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


# 1. 获取最近 traces
traces = get("/api/traces?limit=3")
items = traces.get("items", []) if isinstance(traces, dict) else traces
print(f"最近 {len(items)} 条 trace")

if items:
    # 取最新一条完整 trace
    tid = items[0].get("trace_id") or items[0].get("id")
    print(f"最新 trace_id: {tid}")
    detail = get(f"/api/traces/{tid}")

    # 找 pre_analyzer 和 coordinator 相关的 span
    spans = detail.get("spans", detail.get("children", []))
    if not spans and isinstance(detail, dict):
        # 可能是嵌套结构
        for k, v in detail.items():
            if isinstance(v, list):
                spans = v
                break

    print(f"\nspan 总数: {len(spans)}")
    for s in spans:
        name = s.get("name", "?")
        stype = s.get("type", "?")
        # 找 skill_call 类型
        if stype == "skill_call" or "pre_analyzer" in str(name) or "coordinator" in str(name):
            print(f"\n=== span: {name} (type={stype}) ===")
            print(f"  mock: {s.get('mock')}")
            print(f"  rounds: {s.get('rounds')}")
            # 找 model_call 子 span 的 output
            children = s.get("children", s.get("spans", []))
            for c in (children if isinstance(children, list) else []):
                if c.get("type") == "model_call":
                    output = c.get("output", "")
                    print(f"  model_call output ({len(str(output))} 字): {str(output)[:500]}")
                elif c.get("type") == "tool_call":
                    print(f"  tool_call: {c.get('name','?')} → {str(c.get('result',''))[:200]}")

# 2. 直接渲染 pre_analyzer skill 看看 prompt
print("\n=== pre_analyzer skill render ===")
try:
    r = get("/api/agent/skills/pre_analyzer/render")
    sp = r.get("system_prompt", "")
    print(f"  system_prompt 长度: {len(sp)} 字")
    print(f"  前 300 字: {sp[:300]}")
except Exception as e:
    print(f"  失败: {e}")
