"""检查 v3 存档中角色/群体/事件/任务数量，评估数据状态。

用法：
    python scripts/check_db_state.py [save_name]

如果不传 save_name，使用当前激活存档。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backend.storage.connection import default_save_manager  # noqa: E402
from src.backend.storage import models  # noqa: E402


def main():
    sm = default_save_manager()

    # 如果命令行传了存档名，切换到该存档
    if len(sys.argv) > 1:
        save_name = sys.argv[1]
        if save_name not in sm.list_saves():
            print(f"存档 {save_name} 不存在。可用存档: {sm.list_saves()}")
            return
        sm.switch_save(save_name)

    if not sm.active_save:
        print("无激活存档。用法: python scripts/check_db_state.py <save_name>")
        print(f"可用存档: {sm.list_saves()}")
        return

    print(f"=== 存档: {sm.active_save} ===\n")

    # --- 世界元信息 ---
    meta = sm.get_meta()
    print("--- 世界元信息 ---")
    print(f"  tick_num: {meta.get('tick_num')}")
    print(f"  game_time: {meta.get('game_time')}")
    print(f"  era_name: {meta.get('era_name')}")
    print(f"  script_name: {meta.get('script_name')}")
    protag_id = meta.get("protagonist_id")
    if protag_id:
        protag = models.Character.get(protag_id)
        protag_name = protag.name if protag else f"#{protag_id}(缺失)"
        print(f"  protagonist: {protag_name} (id={protag_id})")
    print()

    # --- 角色 ---
    chars = models.Character.list(limit=10000)
    print(f"--- 角色 (共 {len(chars)}) ---")
    for threshold in [5, 4, 3, 2, 1]:
        count = sum(1 for c in chars if (c.importance or 0) >= threshold)
        print(f"  importance>={threshold}: {count}")
    # 活跃角色（未死亡）
    alive = [c for c in chars if c.dead_at_tick is None]
    print(f"  存活: {len(alive)} / 死亡: {len(chars) - len(alive)}")
    print()

    # --- 群体 ---
    groups = models.Group.list(limit=1000)
    print(f"--- 群体 (共 {len(groups)}) ---")
    for g in groups:
        leader = models.Character.get(g.leader_id) if g.leader_id else None
        leader_name = leader.name if leader else "无"
        print(f"  #{g.id} {g.name} (type={g.group_type}, leader={leader_name}, imp={g.importance})")
    print()

    # --- 事件 ---
    events = models.Event.list(limit=10000, order_by="tick_num DESC")
    print(f"--- 事件 (共 {len(events)}) ---")
    if events:
        tick_range = f"tick {events[-1].tick_num} ~ {events[0].tick_num}"
        print(f"  时间范围: {tick_range}")
        for threshold in [5, 4, 3]:
            count = sum(1 for e in events if (e.importance or 0) >= threshold)
            print(f"  importance>={threshold}: {count}")
        # 按事件类型统计
        type_counts: dict = {}
        for e in events:
            t = e.event_type or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"  按类型:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {t}: {c}")
    print()

    # --- 任务 ---
    quests = models.CharacterQuest.list(limit=10000)
    print(f"--- 任务 (共 {len(quests)}) ---")
    if quests:
        status_counts: dict = {}
        type_counts: dict = {}
        for q in quests:
            s = q.status or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1
            t = q.quest_type or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"  按状态:")
        for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"    {s}: {c}")
        print(f"  按类型:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {t}: {c}")
    print()

    # --- 地图 ---
    maps = models.Map.list(limit=1000)
    print(f"--- 地图 (共 {len(maps)}) ---")
    for m in maps:
        parent = models.Map.get(m.parent_map_id) if m.parent_map_id else None
        parent_name = parent.name if parent else "无"
        print(f"  #{m.id} {m.name} (type={m.map_type}, parent={parent_name})")
    print()

    # --- 记忆 ---
    mems = models.Memory.list(limit=10000)
    print(f"--- 记忆 (共 {len(mems)}) ---")
    if mems:
        avg_depth = sum(m.depth or 0 for m in mems) / len(mems)
        avg_correctness = sum(m.correctness or 0 for m in mems) / len(mems)
        print(f"  平均深度: {avg_depth:.1f}")
        print(f"  平均正确性: {avg_correctness:.1f}%")
        false_count = sum(1 for m in mems if m.is_false)
        print(f"  虚假记忆: {false_count}")
    print()

    print("=== 检查完毕 ===")


if __name__ == "__main__":
    main()
