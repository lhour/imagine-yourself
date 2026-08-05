"""端到端验证：导入 sample 剧本 + 调用真实 DeepSeek V4 Flash 推进一个 tick。"""
import sys, time, json, requests
sys.path.insert(0, r'D:\Desktop\projecct')

BASE = "http://localhost:8000/api"

print("=" * 60)
print("DeepSeek V4 Flash 真实管线验证")
print("=" * 60)

# 1. 检查 LLM 是否真实可用
print("\n[1] 检查 LLM 客户端模式 ...")
import os
from src.backend.env import load_backend_env
load_backend_env()
from src.backend import deepseek_client
print(f"    mock_mode = {deepseek_client.is_mock_mode()}  (期望 False)")
assert not deepseek_client.is_mock_mode(), "LLM 仍处于 mock 模式，.env 未生效"

# 2. 用一个全新存档名（不预创建，避免 Windows 文件锁）
import time as _time
SAVE = f"llm_verify_{int(_time.time())}"
print(f"\n[2] 用全新存档名 {SAVE}（init_drama 会自动创建）...")

# 3. 导入 sample 剧本
print("\n[3] 导入 sample 剧本 ...")
t0 = _time.time()
r = requests.post(f"{BASE}/dramas/sample/init", json={"save_name": SAVE, "overwrite": False})
print(f"    init -> {r.status_code}, 耗时 {_time.time()-t0:.1f}s")
if r.status_code != 200:
    print(f"    body: {r.text[:300]}")
    sys.exit(1)
data = r.json()
stats = data.get("stats", {})
print(f"    stats: 角色={stats.get('characters',0)} 群体={stats.get('groups',0)} 事件={stats.get('events',0)}")

# 4. 切换到新存档
print("\n[4] 切换到新存档 ...")
r = requests.post(f"{BASE}/saves/{SAVE}/switch")
print(f"    switch -> {r.status_code}")

# 4. 检查世界状态
print("\n[4] 世界状态 ...")
r = requests.get(f"{BASE}/saves/meta").json()
print(f"    tick={r.get('tick_num')} time={r.get('game_time')} script={r.get('script_name')}")

# 5. 触发一次真实 LLM tick
print("\n[5] 触发一次真实 LLM tick (max_actors=2，调用 7 步管线) ...")
print("    注意：DeepSeek V4 Flash 默认开启 reasoning，每步 2-5 秒，整体约 30-60 秒")
t0 = time.time()
try:
    r = requests.post(f"{BASE}/agent/tick", json={"seconds": 60, "max_actors": 2}, timeout=180)
    elapsed = time.time() - t0
    print(f"    tick -> {r.status_code}, 耗时 {elapsed:.1f}s")
    if r.status_code == 200:
        result = r.json()
        print(f"    返回字段: {list(result.keys())}")
        print(f"    mock_mode = {result.get('mock_mode')}")
        print(f"    tick = {result.get('tick')}, game_time = {result.get('game_time')}")
        events_created = result.get("events_created", [])
        decisions = result.get("decisions", [])
        print(f"    生成事件 IDs: {events_created}")
        print(f"    NPC 决策数: {len(decisions)}")
        for d in decisions[:3]:
            content = (d.get("decision") or "")[:120] if isinstance(d.get("decision"), str) else str(d.get("decision"))[:120]
            print(f"      - {d.get('char_name')}: {content}")
        # 打印每步 trace（打印完整字段）
        print(f"    管线 trace:")
        for t in result.get("trace", []):
            print(f"      {json.dumps(t, ensure_ascii=False, default=str)}")
        # 查最新事件
        ev_list = requests.get(f"{BASE}/world/events", params={"limit": 5}).json()
        print(f"    最新事件（取自 /world/events）:")
        for ev in ev_list.get("items", [])[:3]:
            content = ev.get("content_polished") or ev.get("content_raw", "")
            print(f"      [{ev.get('tick_num')}] {ev.get('event_type')} ({ev.get('importance')}★): {content[:100]}")
    else:
        print(f"    ERROR: {r.text[:300]}")
except requests.Timeout:
    print(f"    ⚠ 超时（{time.time()-t0:.0f}s）— V4 Flash reasoning 可能较慢")
except Exception as e:
    print(f"    ⚠ 异常: {e}")

# 6. 清理
print("\n[6] 清理测试存档 ...")
r = requests.delete(f"{BASE}/saves/{SAVE}")
print(f"    delete -> {r.status_code}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
