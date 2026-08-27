"""Iteration 8 — DATA COMPLETENESS verification for Welspun (TEN-0006).

Verifies the EXISTING findings in the DB (no new serper run) for:
  * ~235 social findings across many platforms
  * platform field matches the URL host (per DORK_TARGETS mapping)
  * brand relevance: 'welspun' appears in title/snippet/url
  * evidence.engine == 'serper (google)' for most findings
  * evidence.query is a focused per-platform query, NOT one giant combined query
  * pagination of GET /api/findings, case-insensitive platform filter, search
"""
import os
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

WELSPUN_ID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"


@pytest.fixture(scope="module")
def token():
    creds = Path("/app/memory/test_credentials.md")
    if not creds.exists():
        pytest.skip("missing test_credentials.md")
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@brandshield.io", "password": "Admin@123"},
                      timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def social(client):
    r = client.get(f"{BASE_URL}/api/findings",
                   params={"tenant_id": WELSPUN_ID, "module": "social", "page_size": 300},
                   timeout=60)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    items = data.get("items", data if isinstance(data, list) else [])
    return data, items


# ── Completeness ────────────────────────────────────────────────────────────
class TestCompleteness:
    def test_total_count(self, social):
        data, items = social
        total = data.get("total", len(items))
        print(f"total={total} returned={len(items)}")
        assert total >= 200, f"expected ~235 social findings, got {total}"
        assert len(items) == min(total, 300)

    def test_no_mongo_id_leak(self, social):
        _, items = social
        assert all("_id" not in f for f in items)

    def test_platform_spread(self, social):
        _, items = social
        counts = Counter(f.get("platform") for f in items)
        print("platform distribution:", dict(counts))
        assert len(counts) >= 7, f"expected >=7 platforms, got {dict(counts)}"

    def test_platform_matches_url_host(self, social):
        from collectors import DORK_TARGETS
        _, items = social
        bad = []
        for f in items:
            plat, url = f.get("platform"), (f.get("url") or "").lower()
            tgt = DORK_TARGETS.get(plat)
            if not tgt or tgt[0] not in url:
                bad.append((plat, url))
        print(f"mismatched platform/url: {len(bad)}; sample={bad[:5]}")
        assert not bad, f"{len(bad)} findings whose URL host != platform field"

    def test_brand_relevance(self, social):
        _, items = social
        bad = [f["url"] for f in items
               if "welspun" not in ((f.get("title") or "") + " "
                                    + (f.get("evidence", {}) or {}).get("snippet", "") + " "
                                    + (f.get("url") or "")).lower().replace(" ", "").replace("-", "")
               and "welspun" not in ((f.get("title") or "") + " "
                                     + (f.get("evidence", {}) or {}).get("snippet", "") + " "
                                     + (f.get("url") or "")).lower()]
        print(f"non-brand-relevant: {len(bad)}; sample={bad[:5]}")
        assert not bad, f"{len(bad)} findings lack 'welspun' in title/snippet/url"

    def test_evidence_engine_and_focused_query(self, social):
        _, items = social
        engines = Counter((f.get("evidence") or {}).get("engine") for f in items)
        queries = Counter((f.get("evidence") or {}).get("query") for f in items)
        print("engines:", dict(engines))
        print("queries:", dict(queries))
        serper = engines.get("serper (google)", 0)
        assert serper / max(len(items), 1) > 0.5, f"serper not dominant: {dict(engines)}"
        # focused per-platform queries must dominate; a handful of findings from
        # pre-fix runs (combined keyword dork / tagline brand) may still linger.
        focused = sum(c for q, c in queries.items()
                      if q and q.lower().startswith("welspun ") and len(q.split()) <= 3)
        legacy = sum(c for q, c in queries.items()
                     if not (q and q.lower().startswith("welspun ") and len(q.split()) <= 3))
        print(f"focused={focused} legacy(pre-fix runs)={legacy}")
        assert focused / max(len(items), 1) > 0.9, "focused per-platform queries not dominant"
        # every focused query must be '{brand} {one keyword}'
        for q in queries:
            if q and q.lower().startswith("welspun ") and len(q.split()) <= 3:
                assert re.fullmatch(r"Welspun [a-z]+", q), q

    def test_required_fields_present(self, social):
        _, items = social
        for f in items[:50]:
            assert f.get("severity") and f.get("risk_score") is not None
            ent = f.get("entities") or {}
            assert ent.get("account_name") and ent.get("username")
            assert ent.get("profile_url")


# ── API pagination / filters ────────────────────────────────────────────────
class TestFindingsApi:
    def test_pagination_covers_all(self, client, social):
        data, items = social
        total = data.get("total", len(items))
        seen, page, page_size = set(), 1, 50
        while len(seen) < total and page <= 20:
            r = client.get(f"{BASE_URL}/api/findings",
                           params={"tenant_id": WELSPUN_ID, "module": "social",
                                   "page": page, "page_size": page_size}, timeout=60)
            assert r.status_code == 200
            batch = r.json().get("items", [])
            if not batch:
                break
            seen.update(f["id"] for f in batch)
            page += 1
        print(f"paged unique ids={len(seen)} total={total}")
        assert len(seen) == total

    @pytest.mark.parametrize("plat", ["linkedin", "LINKEDIN", "Instagram", "youtube"])
    def test_platform_filter_case_insensitive(self, client, social, plat):
        _, items = social
        expected = sum(1 for f in items if (f.get("platform") or "").lower() == plat.lower())
        r = client.get(f"{BASE_URL}/api/findings",
                       params={"tenant_id": WELSPUN_ID, "module": "social",
                               "platform": plat, "page_size": 300}, timeout=60)
        assert r.status_code == 200
        got = r.json()
        print(f"{plat}: api_total={got.get('total')} expected={expected}")
        assert got.get("total") == expected
        assert all((f.get("platform") or "").lower() == plat.lower() for f in got.get("items", []))

    def test_search_filter(self, client):
        r = client.get(f"{BASE_URL}/api/findings",
                       params={"tenant_id": WELSPUN_ID, "module": "social",
                               "search": "welspun", "page_size": 300}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        print("search welspun total:", d.get("total"))
        assert d.get("total", 0) > 0

    def test_search_no_match(self, client):
        r = client.get(f"{BASE_URL}/api/findings",
                       params={"tenant_id": WELSPUN_ID, "module": "social",
                               "search": "zzzz_no_match_zzzz", "page_size": 50}, timeout=60)
        assert r.status_code == 200
        assert r.json().get("total") == 0


# ── URL reachability sample (network, tolerant of bot-blocks) ───────────────
class TestUrlSample:
    def test_sample_urls_resolve_to_platform(self, social):
        import random
        _, items = social
        random.seed(7)
        sample = random.sample(items, min(12, len(items)))
        results = []
        for f in sample:
            url = f["url"]
            code = None
            try:
                resp = requests.get(url, timeout=20, allow_redirects=True,
                                    headers={"User-Agent": "Mozilla/5.0"})
                code = resp.status_code
            except Exception as e:
                code = f"ERR {type(e).__name__}"
            results.append((f["platform"], code, url))
        for p, c, u in results:
            print(f"{p:10s} {c} {u}")
        hard_404 = [r for r in results if r[1] == 404]
        print(f"404s: {len(hard_404)}/{len(results)}")
        assert len(hard_404) <= len(results) // 3, f"too many dead URLs: {hard_404}"
