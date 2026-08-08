"""清理 urban_test2 存档中的重复记忆和重复事件参与者。

去重规则：
- memories: 按 (char_id, source_event_id) 去重，保留 id 最小的一条
- event_participants: 按 (event_id, participant_type, participant_id) 去重，保留 id 最小的一条

用法（.venv 环境）：
    python scripts/cleanup_duplicates.py [save_name]
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# 默认清理 urban_test2
save_name = sys.argv[1] if len(sys.argv) > 1 else "urban_test2"

# 定位存档数据库
backend_dir = Path(__file__).resolve().parent.parent / "src" / "backend"
saves_dir = Path(os.environ.get("SAVES_DIR", str(backend_dir / "saves")))
db_path = saves_dir / f"{save_name}.db"

if not db_path.exists():
    print(f"✗ 存档数据库不存在: {db_path}")
    sys.exit(1)

print(f"清理存档: {save_name}")
print(f"数据库: {db_path}")

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# ============================================================
# 1. 清理重复记忆：按 (char_id, source_event_id) 去重
# ============================================================
print("\n=== 1. 清理重复 memories ===")
rows = conn.execute("""
    SELECT char_id, source_event_id, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
    FROM memories
    WHERE source_event_id IS NOT NULL
    GROUP BY char_id, source_event_id
    HAVING cnt > 1
""").fetchall()

total_mem_deleted = 0
for r in rows:
    ids = [int(x) for x in r["ids"].split(",")]
    keep_id = min(ids)  # 保留 id 最小的
    delete_ids = [i for i in ids if i != keep_id]
    placeholders = ",".join("?" * len(delete_ids))
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", delete_ids)
    total_mem_deleted += len(delete_ids)
    print(f"  char_id={r['char_id']} source_event={r['source_event_id']}: "
          f"保留 id={keep_id}, 删除 {len(delete_ids)} 条 {delete_ids}")

# 也清理 source_event_id 为 NULL 但 char_id+memory_raw 相同的重复
rows2 = conn.execute("""
    SELECT char_id, memory_raw, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
    FROM memories
    WHERE source_event_id IS NULL AND memory_raw != ''
    GROUP BY char_id, memory_raw
    HAVING cnt > 1
""").fetchall()
for r in rows2:
    ids = [int(x) for x in r["ids"].split(",")]
    keep_id = min(ids)
    delete_ids = [i for i in ids if i != keep_id]
    placeholders = ",".join("?" * len(delete_ids))
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", delete_ids)
    total_mem_deleted += len(delete_ids)
    print(f"  char_id={r['char_id']} (无source_event): 保留 id={keep_id}, 删除 {len(delete_ids)} 条")

print(f"  记忆去重完成: 删除 {total_mem_deleted} 条重复记忆")

# ============================================================
# 2. 清理重复事件参与者：按 (event_id, participant_type, participant_id) 去重
# ============================================================
print("\n=== 2. 清理重复 event_participants ===")
rows = conn.execute("""
    SELECT event_id, participant_type, participant_id, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
    FROM event_participants
    GROUP BY event_id, participant_type, participant_id
    HAVING cnt > 1
""").fetchall()

total_ep_deleted = 0
for r in rows:
    ids = [int(x) for x in r["ids"].split(",")]
    keep_id = min(ids)
    delete_ids = [i for i in ids if i != keep_id]
    placeholders = ",".join("?" * len(delete_ids))
    conn.execute(f"DELETE FROM event_participants WHERE id IN ({placeholders})", delete_ids)
    total_ep_deleted += len(delete_ids)
    print(f"  event={r['event_id']} type={r['participant_type']} id={r['participant_id']}: "
          f"保留 ep_id={keep_id}, 删除 {len(delete_ids)} 条")

print(f"  参与者去重完成: 删除 {total_ep_deleted} 条重复参与者")

conn.commit()

# 统计清理后的状态
mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
ep_count = conn.execute("SELECT COUNT(*) FROM event_participants").fetchone()[0]
print(f"\n=== 清理后统计 ===")
print(f"  memories 总数: {mem_count}")
print(f"  event_participants 总数: {ep_count}")

# 验证主角记忆
print(f"\n=== 主角(id=1)记忆 ===")
proto_mems = conn.execute(
    "SELECT id, char_id, source_event_id, depth, substr(memory_raw,1,60) as raw FROM memories WHERE char_id=1 ORDER BY source_event_id"
).fetchall()
for m in proto_mems:
    print(f"  id={m['id']} source={m['source_event_id']} depth={m['depth']} raw={m['raw']}")

conn.close()
print("\n清理完成。")
