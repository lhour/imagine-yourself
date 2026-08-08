"""检查指定 trace 的 span 树，定位空 narrative 根因。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def flatten(node, depth=0, out=None):
    if out is None:
        out = []
    out.append((depth, node))
    for c in node.get("children", []) or []:
        flatten(c, depth + 1, out)
    return out


def main(trace_id: str):
    r = urllib.request.urlopen(f"{BASE}/api/traces/{trace_id}", timeout=30)
    d = json.loads(r.read())
    print(f"=== TRACE {trace_id} ===")
    print(f"name={d.get('name')} type={d.get('type')} status={d.get('status')} "
          f"duration={d.get('duration_ms')}ms")

    nodes = flatten(d)
    print(f"总节点数: {len(nodes)}")

    # 打印所有 span 的概要（带缩进）
    print("\n--- SPAN TREE ---")
    for depth, s in nodes:
        if depth == 0:
            continue  # 跳过根
        name = s.get("name", "")
        stype = s.get("type", "")
        status = s.get("status", "")
        data = s.get("data", {}) or {}
        out = str(data.get("output", "") or "")
        out_len = len(out)
        indent = "  " * depth
        print(f"{indent}[{stype:12}] {name:42} status={status:8} out_len={out_len}")

    # 找所有 model_call，打印输出
    print("\n--- MODEL_CALL OUTPUTS ---")
    for depth, s in nodes:
        if s.get("type") != "model_call":
            continue
        name = s.get("name", "")
        data = s.get("data", {}) or {}
        out = str(data.get("output", "") or "")
        think = str(data.get("think", "") or "")
        tool_reqs = data.get("tool_calls_requested", []) or []
        print(f"\n## {name} out_len={len(out)} think_len={len(think)} tool_reqs={len(tool_reqs)}")
        if out:
            print(f"  OUTPUT: {out[:500]}")
        if tool_reqs:
            print(f"  TOOLS: {[t.get('name') for t in tool_reqs]}")

    # 找所有 skill_call
    print("\n--- SKILL_CALL ---")
    for depth, s in nodes:
        if s.get("type") != "skill_call":
            continue
        name = s.get("name", "")
        data = s.get("data", {}) or {}
        out = str(data.get("output", "") or "")
        print(f"\n## SKILL: {name} output_len={len(out)}")
        if out:
            print(f"  OUTPUT: {out[:300]}")


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "26112ddf7e8b"
    main(tid)
