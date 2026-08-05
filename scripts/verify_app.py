"""验证 src.backend.http.app 可正常 import。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.backend.http.app import app
print("App routes count:", len(app.routes))
print("All routes:")
for r in app.routes:
    if hasattr(r, 'path'):
        methods = sorted(getattr(r, 'methods', set()) or [])
        print(f"  {','.join(methods):20s} {r.path}")
print("OK")
