"""Verify-only check of the last serper run for Welspun (no new scan triggered)."""
import time, json, requests, collections
from conftest import API, client_for

WELSPUN = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"
s = client_for("super_admin")

for i in range(30):
    h = s.get(f"{API}/monitoring-health", params={"tenant_id": WELSPUN}, timeout=120).json()
    row = [x for x in h if x.get("collector") == "Search/Dorking"][0]
    if row.get("status") != "running":
        break
    time.sleep(6)
print("HEALTH:", json.dumps(row, indent=1))

r = s.get(f"{API}/findings", params={"tenant_id": WELSPUN, "module": "social", "page_size": 200}, timeout=120).json()
items = r["items"]
print("total social:", r["total"])
serper = [f for f in items if (f.get("evidence") or {}).get("engine") == "serper (google)"]
print("serper findings:", len(serper))
print("engines:", collections.Counter((f.get("evidence") or {}).get("engine") for f in items))
print("platforms(serper):", collections.Counter(f["platform"] for f in serper))
print("queries:", {f["evidence"].get("query") for f in serper})
print("brands:", {f["evidence"].get("matched_brand") for f in serper})
for f in serper[:15]:
    print(" -", f["platform"], "|", f["url"][:95], "|", f["title"][:60])
print("has _id:", any("_id" in f for f in items))
