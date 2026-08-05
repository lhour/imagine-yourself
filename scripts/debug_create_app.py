"""Debug create_app router 注册。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))

from src.backend.http.app import create_app
app = create_app()
print(f"Total routes: {len(app.routes)}")
print("All routes with path:")
for r in app.routes:
    p = getattr(r, 'path', None)
    if p:
        methods = sorted(getattr(r, 'methods', set()) or [])
        print(f"  {','.join(methods):20s} {p}")
    else:
        print(f"  (no path) type={type(r).__name__}  name={getattr(r, 'name', '?')}")
