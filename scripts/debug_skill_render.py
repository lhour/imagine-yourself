"""调试 skill render 返回空的原因。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=15)
    return json.loads(resp.read())


# 1. 检查 pre_analyzer skill 信息
print("=== pre_analyzer skill info ===")
r = get("/api/agent/skills/pre_analyzer")
print(json.dumps(r, ensure_ascii=False, indent=2)[:800])

# 2. 检查 render
print("\n=== pre_analyzer render ===")
r = get("/api/agent/skills/pre_analyzer/render")
print(f"  keys: {list(r.keys())}")
print(f"  system_prompt len: {len(r.get('system_prompt',''))}")
print(f"  system_prompt repr: {repr(r.get('system_prompt',''))[:300]}")

# 3. 检查版本详情
print("\n=== pre_analyzer v0 版本详情 ===")
r = get("/api/agent/skills/pre_analyzer/versions/v0")
print(f"  keys: {list(r.keys())}")
print(f"  system_prompt len: {len(r.get('system_prompt',''))}")
print(f"  skill_md len: {len(r.get('skill_md',''))}")
print(f"  system_prompt repr: {repr(r.get('system_prompt',''))[:300]}")

# 4. 对比另一个 skill (coordinator)
print("\n=== coordinator render ===")
r = get("/api/agent/skills/coordinator/render")
print(f"  system_prompt len: {len(r.get('system_prompt',''))}")
print(f"  system_prompt repr: {repr(r.get('system_prompt',''))[:300]}")
