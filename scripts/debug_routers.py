"""逐个 router 排查 import 错误。"""
import sys, os, traceback
sys.path.insert(0, os.path.abspath('.'))

mods = [
    "src.backend.http.routers.saves",
    "src.backend.http.routers.entities",
    "src.backend.http.routers.memory",
    "src.backend.http.routers.maps",
    "src.backend.http.routers.groups",
    "src.backend.http.routers.world",
    "src.backend.http.routers.dramas",
]
for mn in mods:
    try:
        m = __import__(mn, fromlist=["router"])
        r = getattr(m, "router")
        print(f"OK  {mn}  routes={len(r.routes)}")
        for rt in r.routes:
            if hasattr(rt, 'path'):
                print(f"     {sorted(getattr(rt, 'methods', set()) or [])}  {rt.path}")
    except Exception as e:
        print(f"FAIL {mn}: {e}")
        traceback.print_exc()
