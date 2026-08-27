"""Iteration 8 — platform mapping correctness using HOST-BOUNDARY matching.

_platform_for_url does a naive substring check (`host in url`), so e.g.
'x.com' matches 'upstox.com' and 'ambitionbox.com'. This test asserts the
platform host is the URL's actual registered host (or a subdomain of it).
"""
import os
import sys
from collections import Counter
from urllib.parse import urlparse

import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")
from collectors import DORK_TARGETS  # noqa: E402

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
WID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"


def _items(tenant_id=WID):
    tok = requests.post(f"{BASE_URL}/api/auth/login",
                        json={"email": "admin@brandshield.io", "password": "Admin@123"},
                        timeout=30).json()["token"]
    r = requests.get(f"{BASE_URL}/api/findings",
                     params={"tenant_id": tenant_id, "module": "social", "page_size": 300},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    return r.json()["items"]


def _host_matches(url, host):
    h = (urlparse(url).hostname or "").lower()
    return h == host or h.endswith("." + host)


def _tenant_id(code):
    tok = requests.post(f"{BASE_URL}/api/auth/login",
                        json={"email": "admin@brandshield.io", "password": "Admin@123"},
                        timeout=30).json()["token"]
    body = requests.get(f"{BASE_URL}/api/tenants", params={"page_size": 100},
                        headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    items = body.get("items", body) if isinstance(body, dict) else body
    return next(t["id"] for t in items if t["tenant_id"] == code)


def test_platform_host_boundary_stripe():
    items = _items(_tenant_id("TEN-0001"))
    bad = [(f["platform"], urlparse(f["url"]).hostname, f["url"]) for f in items
           if not _host_matches(f.get("url") or "",
                                (DORK_TARGETS.get(f.get("platform")) or ("",))[0] or "\x00")]
    print(f"STRIPE MIS-MAPPED: {len(bad)}/{len(items)} -> {bad[:5]}")
    assert not bad


def test_platform_host_boundary():
    items = _items()
    bad = []
    for f in items:
        plat = f.get("platform")
        host = (DORK_TARGETS.get(plat) or ("",))[0]
        if not host or not _host_matches(f.get("url") or "", host):
            bad.append((plat, urlparse(f["url"]).hostname, f["url"]))
    print(f"MIS-MAPPED: {len(bad)}/{len(items)}")
    for b in bad:
        print("  ", b[0], "<-", b[1], b[2][:110])
    print("by platform:", dict(Counter(b[0] for b in bad)))
    assert not bad, f"{len(bad)} findings mapped to the wrong platform (naive substring host match)"
