import urllib.request, json
resp = urllib.request.urlopen("http://127.0.0.1:8000/api/saves/batch-meta", timeout=15)
d = json.loads(resp.read())
metas = d.get("metas", [])
print("count:", len(metas))
if metas:
    print("keys:", list(metas[0].keys()))
    print("first:", json.dumps(metas[0], ensure_ascii=False)[:400])
for m in metas:
    name = m.get("name") or m.get("save_name") or m.get("save") or "?"
    print(f"{name}: tick={m.get('tick_num')} proto={m.get('protagonist_id')}")
