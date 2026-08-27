"""LIVE serper.dev run against Welspun TEN-0006 (consumes serper free quota).

Enabled only with RUN_SERPER_LIVE=1 to avoid burning quota on regression runs.
"""
import os
import time
import pytest
import requests
from conftest import API, client_for

WELSPUN = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SERPER_LIVE") != "1",
    reason="live serper run disabled (set RUN_SERPER_LIVE=1)")


@pytest.fixture(scope="module")
def admin():
    return client_for("super_admin")


def test_live_serper_run_produces_social_findings(admin):
    before = admin.get(f"{API}/findings", params={"tenant_id": WELSPUN, "module": "social",
                                                  "page_size": 200}, timeout=120)
    assert before.status_code == 200
    n_before = before.json()["total"]

    t0 = time.time()
    r = admin.post(f"{API}/tenants/{WELSPUN}/run", params={"collector": "search_dork"}, timeout=120)
    assert r.status_code == 200, r.text[:400]
    assert time.time() - t0 < 15, "run endpoint must return fast (background task)"

    health = None
    for _ in range(20):
        time.sleep(6)
        h = admin.get(f"{API}/monitoring-health", params={"tenant_id": WELSPUN}, timeout=120)
        assert h.status_code == 200
        rows = [x for x in h.json() if x.get("collector") == "Search/Dorking"]
        health = rows[0] if rows else None
        if health and health.get("status") != "running":
            break
    print("HEALTH:", health)
    assert health, "no Search/Dorking health row"
    assert health["status"] == "healthy", health
    assert health["items_found"] > 0, health

    fr = admin.get(f"{API}/findings", params={"tenant_id": WELSPUN, "module": "social",
                                              "page_size": 200}, timeout=120)
    assert fr.status_code == 200
    items = fr.json()["items"]
    assert fr.json()["total"] >= n_before

    serper = [f for f in items if (f.get("evidence") or {}).get("engine") == "serper (google)"]
    print(f"total social={fr.json()['total']} serper={len(serper)}")
    assert serper, "no findings carry evidence.engine == 'serper (google)'"

    queries = {f["evidence"]["query"] for f in serper}
    print("QUERIES:", queries)
    assert len(queries) == 1, queries
    q = queries.pop()
    assert "site:" not in q and " OR " not in q
    assert q.lower().startswith("welspun")
    for kw in ["instagram", "twitter", "facebook", "linkedin", "youtube"]:
        assert kw in q

    assert {f["evidence"].get("matched_brand") for f in serper} == {"Welspun"}

    hosts = {"Instagram": "instagram.com", "X": "x.com", "Twitter": "twitter.com",
             "YouTube": "youtube.com", "Facebook": "facebook.com", "LinkedIn": "linkedin.com",
             "TikTok": "tiktok.com", "Threads": "threads.net", "Pinterest": "pinterest.com",
             "Telegram": "t.me", "Reddit": "reddit.com", "Pastebin": "pastebin.com",
             "Scribd": "scribd.com"}
    plats = {}
    for f in serper:
        p = f["platform"]
        plats[p] = plats.get(p, 0) + 1
        assert hosts[p] in f["url"].lower(), f"platform/url mismatch: {p} {f['url']}"
        assert "_id" not in f
    print("PLATFORMS:", plats)
    assert len(plats) >= 3, f"expected multiple platforms, got {plats}"


def test_no_unhandled_errors_in_backend_log():
    log = "/var/log/supervisor/backend.err.log"
    if not os.path.exists(log):
        pytest.skip("no backend err log")
    tail = open(log, errors="ignore").read()[-40000:]
    assert "ScrapeDoQuotaError" not in tail or "Traceback" not in tail.split("ScrapeDoQuotaError")[0][-2000:]
