"""验证 v4 管线 A1-A4 效果：列出角色 → 设主角（若缺） → 触发 tick → 检查 narrative/记忆。

用法（.venv 环境）：
    python scripts/verify_v4_frontend.py
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
TIMEOUT = 180


def _get(path: str):
    resp = urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT)
    return json.loads(resp.read())


def _post(path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"} if data else {},
    )
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    return json.loads(resp.read())


def main() -> int:
    # 1. 确认激活存档
    active = _get("/api/saves/active").get("active_save")
    print(f"[1] 当前激活存档: {active}")
    if not active:
        print("  ✗ 无激活存档，请先 switch。")
        return 1

    meta = _get("/api/saves/meta")
    print(f"    tick={meta.get('tick_num')} game_time={meta.get('game_time')} "
          f"proto_id={meta.get('protagonist_id')} "
          f"vec_ready={meta.get('vector_store_ready')} "
          f"graph_ready={meta.get('graph_store_ready')}")

    # 2. 列出角色
    chars_resp = _get("/api/entities/character?limit=20")
    items = chars_resp.get("items", []) if isinstance(chars_resp, dict) else chars_resp
    print(f"[2] 角色数量: {len(items)}")
    for c in items[:10]:
        print(f"    id={c.get('id')} name={c.get('name')} importance={c.get('importance')} status={c.get('status','')!r}")

    # 3. 若无主角，设置第一个角色为主角
    proto_id = meta.get("protagonist_id")
    if not proto_id and items:
        proto_id = items[0].get("id")
        print(f"[3] 未设置主角，尝试设置 id={proto_id} 为主角")
        try:
            # set_protagonist 通过 query param char_id
            req = urllib.request.Request(
                f"{BASE}/api/saves/protagonist?char_id={proto_id}", method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
            print(f"    设置结果: {json.loads(resp.read())}")
        except Exception as e:
            print(f"    ✗ 设置主角失败: {e}")
    else:
        print(f"[3] 主角已设置: {proto_id}")

    # 4. 触发一次 tick（v4 管线）— 路径为 /api/agent/tick
    print("[4] 触发 v4 tick（seconds=60, max_actors=5）...")
    try:
        tick = _post("/api/agent/tick", {"seconds": 60, "max_actors": 5})
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    ✗ tick 失败 HTTP {e.code}: {body[:1500]}")
        return 1

    print(f"    tick_num={tick.get('tick')} game_time={tick.get('game_time')}")
    print(f"    mock_mode={tick.get('mock_mode')}")
    print(f"    events_created={tick.get('events_created')}")
    print(f"    decisions 数={len(tick.get('decisions', []))}")
    narr = tick.get("narrative")
    if narr:
        print(f"    narrative ({len(narr)} 字):")
        print("    " + narr.replace("\n", "\n    ")[:1200])
    else:
        print("    ✗ 无 narrative 字段！")
        print("    原始返回 keys:", list(tick.keys()))

    # 5. 检查最新事件 & 记忆
    print("[5] 检查最新事件与记忆...")
    try:
        events = _get("/api/entities/event?limit=3&_order=id DESC")
        ev_items = events.get("items", []) if isinstance(events, dict) else events
        print(f"    最近事件 {len(ev_items)} 条:")
        for e in ev_items[:3]:
            print(f"      id={e.get('id')} type={e.get('event_type')} tick={e.get('tick_num')} "
                  f"content={(e.get('content_raw') or '')[:80]}")
    except Exception as e:
        print(f"    查询事件失败: {e}")

    try:
        if proto_id:
            mems = _get(f"/api/memory/{proto_id}/recent?limit=5")
            mem_items = mems.get("items", []) if isinstance(mems, dict) else mems
            print(f"    主角最近记忆 {len(mem_items)} 条:")
            for m in mem_items[:5]:
                print(f"      id={m.get('id')} depth={m.get('depth')} "
                      f"person_ids={m.get('person_ids')} "
                      f"raw={(m.get('memory_raw') or '')[:80]}")
    except Exception as e:
        print(f"    查询记忆失败（可能接口路径不同）: {e}")

    # 6. 检查向量库是否真正可用
    print("[6] 向量库就绪状态:", meta.get("vector_store_ready"))
    print("\n验证完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
