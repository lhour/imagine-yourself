"""专门检查 coordinator 节点的 model_call 详情。"""
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
    nodes = flatten(d)

    # 找 coordinator 节点下的所有 model_call
    in_coord = False
    print("=== coordinator 相关 model_call ===")
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
            think = str(data.get("think", "") or "")
            tool_reqs = data.get("tool_calls_requested", []) or []
            usage = data.get("usage", {}) or {}
            print(f"\n## {name}")
            print(f"  out_len={len(out)} think_len={len(think)} tool_reqs={len(tool_reqs)}")
            print(f"  usage={usage}")
            print(f"  THINK: {think[:600]}")
            print(f"  OUTPUT: {out[:600] if out else '(empty)'}")
            if tool_reqs:
                for t in tool_reqs:
                    print(f"  TOOL: {t.get('name')} args={str(t.get('arguments'))[:200]}")

    # 也看看 actor_decide 最后的 model_call#final 是否被触发
    print("\n=== 所有 model_call#final ===")
    for depth, s in nodes:
        if s.get("type") == "model_call" and "final" in s.get("name", ""):
            data = s.get("data", {}) or {}
            out = str(data.get("output", "") or "")
            print(f"  {s.get('name')}: out_len={len(out)} preview={out[:200]}")


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "26112ddf7e8b"
    main(tid)
