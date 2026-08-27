"""Iteration 9 — unit-level verification of collectors._platform_for_url host
boundary matching (exact-or-subdomain) + DB verification that the 3 previously
mis-mapped non-social URLs are gone. READ-ONLY (no collector runs)."""
import os
import sys

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")
from collectors import _platform_for_url  # noqa: E402

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
WID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"


# --- module: collectors._platform_for_url -----------------------------------
@pytest.mark.parametrize("url,expected", [
    # exact hosts
    ("https://x.com/welspunone/status/123", "X"),
    ("https://twitter.com/welspun", "Twitter"),
    ("https://www.instagram.com/welspun/", "Instagram"),
    ("https://t.me/welspunchannel", "Telegram"),
    ("https://threads.net/@welspun", "Threads"),
    # subdomains must still map
    ("https://in.linkedin.com/company/welspun", "LinkedIn"),
    ("https://de.linkedin.com/company/welspun-flooring?trk", "LinkedIn"),
    ("https://m.facebook.com/welspunworld", "Facebook"),
    ("https://www.youtube.com/watch?v=abc", "YouTube"),
    ("https://old.reddit.com/r/india/comments/x", "Reddit"),
    # NON-social lookalikes that the naive substring match wrongly matched
    ("https://upstox.com/stocks/welspun-corp-share-price/", None),
    ("https://www.ambitionbox.com/reviews/welspun-reviews", None),
    ("https://notx.com/foo", None),
    ("https://fakelinkedin.com/company/welspun", None),
    ("https://example.com/x.com/welspun", None),
    ("https://mytiktok.com/welspun", None),
    ("https://t.me.evil.com/welspun", None),
])
def test_platform_for_url_host_boundary(url, expected):
    got = _platform_for_url(url)
    assert (got[0] if got else None) == expected, f"{url} -> {got}"


# --- DB: previously mis-mapped findings removed ------------------------------
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@brandshield.io", "password": "Admin@123"},
                      timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()["token"]


def test_bad_hosts_absent_from_welspun_social(token):
    r = requests.get(f"{BASE_URL}/api/findings",
                     params={"tenant_id": WID, "module": "social", "page_size": 300},
                     headers={"Authorization": f"Bearer {token}"}, timeout=60)
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert body["total"] == 232, f"expected 232 social findings, got {body['total']}"
    bad = [f["url"] for f in items
           if "upstox.com" in f["url"] or "ambitionbox.com" in f["url"]]
    assert not bad, f"non-social URLs still present: {bad}"


def test_search_snippet_coverage(token):
    """search='welspun' must now match snippet-only findings too (232, not 213)."""
    r = requests.get(f"{BASE_URL}/api/findings",
                     params={"tenant_id": WID, "module": "social",
                             "search": "welspun", "page_size": 1},
                     headers={"Authorization": f"Bearer {token}"}, timeout=60)
    assert r.status_code == 200
    assert r.json()["total"] == 232, f"search total = {r.json()['total']} (expected 232)"
