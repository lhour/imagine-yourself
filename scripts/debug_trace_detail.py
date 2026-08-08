"""检查 render 正确性 + trace 中 pre_analyzer 的实际 LLM 输出。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=15)
    return json.loads(resp.read())


# 1. render 用正确 key
print("=== pre_analyzer render (correct key) ===")
r = get("/api/agent/skills/pre_analyzer/render")
rendered = r.get("rendered", "")
print(f"  rendered len: {len(rendered)}")
print(f"  rendered 前 200 字: {rendered[:200]}")

# 2. 获取最新 trace 的完整详情
print("\n=== 最新 trace 详情 ===")
traces = get("/api/traces?limit=1")
items = traces.get("items", []) if isinstance(traces, dict) else traces
if items:
    tid = items[0].get("trace_id") or items[0].get("id")
    detail = get(f"/api/traces/{tid}")
    print(f"  trace_id: {tid}")
    print(f"  top keys: {list(detail.keys())}")

    # 递归找所有 span
    def find_spans(obj, depth=0):
        spans = []
        if isinstance(obj, dict):
            if obj.get("type") in ("skill_call", "model_call", "tool_call"):
                spans.append(obj)
            for v in obj.values():
                spans.extend(find_spans(v, depth+1))
        elif isinstance(obj, list):
            for item in obj:
                spans.extend(find_spans(item, depth+1))
        return spans

    all_spans = find_spans(detail)
    print(f"  总 span 数: {len(all_spans)}")

    for s in all_spans:
        stype = s.get("type", "?")
        name = s.get("name", s.get("skill_name", "?"))
        if stype == "skill_call":
            print(f"\n  --- skill_call: {name} ---")
            print(f"    mock: {s.get('mock')}, rounds: {s.get('rounds')}")
            # 找子 model_call
            for c in find_spans(s):
                if c.get("type") == "model_call" and c is not s:
                    output = c.get("output", "")
                    print(f"    model_call output ({len(str(output))} 字):")
                    print(f"    {str(output)[:600]}")
