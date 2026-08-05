"""端到端测试：直接调用 /api/world/tick 验证 v3 时间推进流程。

用法：
    python scripts/test_tick.py                          # 推进 1 小时（3600 秒）
    python scripts/test_tick.py 86400                    # 推进 1 天
    python scripts/test_tick.py 3600 drama_init_test     # 指定存档名

前提：需要先用 init_drama 导入过 sample 剧本。
"""
import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from src.backend.http.app import app  # noqa: E402


def main():
    # 解析参数
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    save_name = sys.argv[2] if len(sys.argv) > 2 else None

    c = TestClient(app)

    # 1. 切换激活存档
    if save_name:
        r = c.post(f"/api/saves/{save_name}/switch")
        print(f"[switch] status={r.status_code} save={save_name}")
        if r.status_code != 200:
            print(f"切换存档失败: {r.text[:200]}")
            return
    else:
        r = c.get("/api/saves/active")
        active = r.json().get("active_save")
        if not active:
            print("无激活存档。用法: python scripts/test_tick.py <seconds> <save_name>")
            print("或先切换存档: POST /api/saves/{name}/switch")
            return
        print(f"[active] save={active}")

    # 2. 查询当前状态
    r = c.get("/api/world/status")
    print(f"[status] {r.status_code}")
    if r.status_code != 200:
        print(f"查询状态失败: {r.text[:200]}")
        return
    meta_before = r.json()["meta"]
    print(f"  tick_num: {meta_before['tick_num']}")
    print(f"  game_time: {meta_before['game_time']}")
    if meta_before.get("protagonist_id"):
        print(f"  protagonist_id: {meta_before['protagonist_id']}")

    # 3. 推进 tick
    print(f"\n=== 推进 {seconds} 秒 ({seconds / 3600:.1f} 小时) ===")
    r = c.post("/api/world/tick", json={"seconds": seconds})
    print(f"[tick] status={r.status_code}")
    if r.status_code != 200:
        print(f"返回: {r.text[:300]}")
        return

    data = r.json()
    meta_after = data.get("meta", {})
    print(f"  tick_num: {meta_before['tick_num']} → {meta_after.get('tick_num')}")
    print(f"  game_time: {meta_after.get('game_time')}")

    # 4. 查看最新事件
    r = c.get(f"/api/world/events?limit=5&order_by=tick_num%20DESC")
    if r.status_code == 200:
        events = r.json().get("items", [])
        print(f"\n--- 最新 {len(events)} 个事件 ---")
        for e in events:
            stars = "★" * (e.get("importance", 0)) + "☆" * (5 - e.get("importance", 0))
            content = (e.get("content_raw") or "")[:80]
            print(f"  [{stars}] tick={e.get('tick_num')} type={e.get('event_type')} | {content}")

    # 5. 查看实体计数
    print(f"\n--- 实体计数 ---")
    for slug in ["character", "group", "event", "memory", "character_quest"]:
        r = c.get(f"/api/entities/{slug}/count")
        if r.status_code == 200:
            print(f"  {slug}: {r.json()['count']}")


if __name__ == "__main__":
    main()
