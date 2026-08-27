"""Relevance spot-check: does the substring brand match create false positives?"""
import re, requests, collections
from conftest import API, client_for

s = client_for("super_admin")
tenants = s.get(f"{API}/tenants", timeout=60).json()
for t in tenants:
    print(t["id"], t.get("tenant_code"), t.get("name"), t.get("brand_names"), t.get("all_domains"))

def norm(x):
    return "".join(c for c in (x or "").lower() if c.isalnum())

for t in tenants:
    r = s.get(f"{API}/findings", params={"tenant_id": t["id"], "module": "social", "page_size": 200}, timeout=120).json()
    serper = [f for f in r["items"] if (f.get("evidence") or {}).get("engine") == "serper (google)"]
    if not serper:
        continue
    print(f"\n=== {t['name']} serper={len(serper)} platforms={collections.Counter(f['platform'] for f in serper)}")
    terms = sorted({norm(b) for b in (t.get("brand_names") or [])} | {norm(str(d).split('.')[0]) for d in (t.get('all_domains') or [])})
    print("brand terms:", [x for x in terms if x])
    for f in serper:
        hay = norm(f["title"] + " " + (f["evidence"].get("snippet") or "") + " " + f["url"])
        hits = [x for x in terms if x and x in hay]
        # word-boundary style check on raw text
        raw = (f["title"] + " " + (f["evidence"].get("snippet") or "") + " " + f["url"]).lower()
        strong = any(re.search(r"\b" + re.escape(h) + r"\b", raw) for h in hits) if hits else False
        if not strong:
            print(" WEAK-MATCH:", f["platform"], "|", f["url"][:80], "|", f["title"][:70], "| hits:", hits)
