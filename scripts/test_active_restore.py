"""测试 active_save 持久化与自动恢复。

流程：
1. 切换到 urban_test2（应写入 .active_save 文件）
2. 检查 /api/saves/active 返回 urban_test2
3. 提示手动重启后端后再跑一次，检查是否自动恢复
"""
import json
import os
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
SAVES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saves")
ACTIVE_FILE = os.path.join(SAVES_DIR, ".active_save")


def get(path):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
    return json.loads(resp.read())


def post(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


mode = sys.argv[1] if len(sys.argv) > 1 else "switch"

if mode == "switch":
    # 阶段1：切换存档，验证 .active_save 文件被写入
    print("=== 阶段1: 切换存档 ===")
    r = post("/api/saves/urban_test2/switch")
    print(f"  switch 返回: {r}")

    active = get("/api/saves/active")
    print(f"  /api/saves/active: {active}")

    file_exists = os.path.exists(ACTIVE_FILE)
    file_content = ""
    if file_exists:
        with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
            file_content = f.read().strip()
    print(f"  .active_save 文件存在: {file_exists}")
    print(f"  .active_save 内容: '{file_content}'")

    if file_exists and file_content == "urban_test2":
        print("\n  ✅ .active_save 文件已正确写入")
        print("  现在请重启后端，然后运行: python scripts/test_active_restore.py restore")
    else:
        print("\n  ❌ .active_save 文件未正确写入")

elif mode == "restore":
    # 阶段2：后端重启后，检查是否自动恢复
    print("=== 阶段2: 重启后自动恢复检查 ===")
    active = get("/api/saves/active")
    print(f"  /api/saves/active: {active}")

    if active.get("active_save") == "urban_test2":
        print("\n  ✅ 后端重启后自动恢复了活跃存档！")
        # 验证 meta 也能正常读取
        meta = get("/api/saves/meta")
        print(f"  /api/saves/meta: tick={meta.get('tick_num')} game_time={meta.get('game_time')}")
    else:
        print(f"\n  ❌ 未自动恢复，active_save={active.get('active_save')}")
        file_exists = os.path.exists(ACTIVE_FILE)
        print(f"  .active_save 文件存在: {file_exists}")
