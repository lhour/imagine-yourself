"""端到端 HTTP 服务器验证。

启动 uvicorn → 等待就绪 → 调用关键端点 → 关闭。
"""
import os
import sys
import time
import subprocess
import httpx
import signal

sys.path.insert(0, os.path.abspath('.'))

# 用一个临时存档目录避免污染
tmp_saves = os.path.abspath("logs/v3_e2e_saves")
os.makedirs(tmp_saves, exist_ok=True)
os.environ["SAVES_DIR"] = tmp_saves
os.environ["PORT"] = "8011"
os.environ["RELOAD"] = "0"

# 启动 uvicorn
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.backend.http.app:app",
     "--host", "127.0.0.1", "--port", "8011"],
    cwd=os.path.abspath('.'),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    env={**os.environ, "PYTHONPATH": os.path.abspath('.')},
)

try:
    # 等待服务就绪
    base = "http://127.0.0.1:8011"
    ok = False
    for _ in range(30):
        try:
            r = httpx.get(f"{base}/api/health", timeout=1.0)
            if r.status_code == 200:
                ok = True
                break
        except Exception:
            time.sleep(0.5)
    if not ok:
        out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
        print("FAIL: 服务未就绪")
        print(out[-3000:])
        sys.exit(1)

    print("=== 1. /api/health ===")
    r = httpx.get(f"{base}/api/health")
    print(r.json())

    print("\n=== 2. 创建存档 ===")
    r = httpx.post(f"{base}/api/saves", json={"name": "e2e"})
    print(r.json())

    print("\n=== 3. 切换 + 列出 slug ===")
    httpx.post(f"{base}/api/saves/e2e/switch")
    r = httpx.get(f"{base}/api/entities/_slugs")
    data = r.json()
    print(f"count={data['count']}")
    print(f"slugs={data['slugs']}")

    print("\n=== 4. 创建地图+要素+算距离 ===")
    r = httpx.post(f"{base}/api/entities/map", json={
        "name": "长安", "desc_raw": "唐都", "map_type": "city",
        "coord_system": "cartesian_2d", "scale_unit": "m",
        "bbox_w": 10000, "bbox_h": 10000,
    })
    map_id = r.json()["id"]
    print(f"map_id={map_id}")
    r = httpx.post(f"{base}/api/entities/map_feature", json={
        "map_id": map_id, "name": "A", "feature_type": "building",
        "shape": "point", "geometry": {"x": 0, "y": 0}, "layer_z": 2,
    })
    f1 = r.json()["id"]
    r = httpx.post(f"{base}/api/entities/map_feature", json={
        "map_id": map_id, "name": "B", "feature_type": "building",
        "shape": "point", "geometry": {"x": 300, "y": 400}, "layer_z": 2,
    })
    f2 = r.json()["id"]
    r = httpx.post(f"{base}/api/maps/distance", json={
        "from": {"type": "feature", "id": f1},
        "to": {"type": "feature", "id": f2},
    })
    print(f"distance: {r.json()}")

    print("\n=== 5. 创建角色 + 事件 + 记忆 ===")
    r = httpx.post(f"{base}/api/entities/character", json={
        "name": "小红", "appearance_raw": "x", "personality_raw": "y"
    })
    cid = r.json()["id"]
    r = httpx.post(f"{base}/api/world/events", json={
        "event_type": "narrative", "content_raw": "小红亲了小明",
        "participants": [{"type": "character", "id": cid, "role": "protagonist"}]
    })
    eid = r.json()["id"]
    r = httpx.post(f"{base}/api/memory/encode_event/{eid}")
    print(f"memories: {len(r.json()['memories'])}")
    r = httpx.post(f"{base}/api/memory/retrieve", json={"char_id": cid})
    print(f"retrieved: {len(r.json()['memories'])}")

    print("\n=== 6. /docs Swagger ===")
    r = httpx.get(f"{base}/docs", follow_redirects=True)
    print(f"docs status={r.status_code}")

    print("\n=== ALL E2E CHECKS PASSED ===")
finally:
    # 终止服务
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
