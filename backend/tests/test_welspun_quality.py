"""Iteration 8 — quality checks on the existing Welspun social dataset."""
import os
from collections import Counter

import requests
from dotenv import dotenv_values

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
WID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"


def _items():
    tok = requests.post(f"{BASE_URL}/api/auth/login",
                        json={"email": "admin@brandshield.io", "password": "Admin@123"},
                        timeout=30).json()["token"]
    r = requests.get(f"{BASE_URL}/api/findings",
                     params={"tenant_id": WID, "module": "social", "page_size": 300},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    return r.json()["items"]


def test_no_duplicate_urls():
    items = _items()
    urls = [f["url"] for f in items]
    dupes = [u for u, c in Counter(urls).items() if c > 1]
    print(f"unique urls={len(set(urls))}/{len(urls)} dupes={dupes[:5]}")
    assert not dupes, f"{len(dupes)} duplicate URLs"


def test_official_accounts_present_per_platform():
    """Genuine brand assets must survive the relevance filter (no over-dropping)."""
    items = _items()
    by_plat = {}
    for f in items:
        by_plat.setdefault(f["platform"], []).append(f["url"].lower())
    expectations = {
        "Facebook": "welspun", "Instagram": "welspun", "LinkedIn": "welspun",
        "YouTube": "welspun", "X": "welspun",
    }
    for plat, needle in expectations.items():
        urls = by_plat.get(plat, [])
        hits = [u for u in urls if needle in u]
        print(f"{plat}: {len(urls)} findings, {len(hits)} with 'welspun' in URL; sample={hits[:2]}")
        assert hits, f"no brand-owned URLs kept for {plat} — possible over-dropping"


def test_severity_and_category_distribution():
    items = _items()
    print("severity:", dict(Counter(f["severity"] for f in items)))
    print("category:", dict(Counter(f["category"] for f in items)))
    print("classification:", dict(Counter((f.get("entities") or {}).get(
        "impersonation_classification") for f in items)))
    assert all(0 <= f["risk_score"] <= 100 for f in items)
