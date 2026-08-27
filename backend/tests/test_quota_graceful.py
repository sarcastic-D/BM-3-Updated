"""Iteration 6 — graceful scrape.do quota handling + brand-selection/region unit tests.

Covers:
  * collectors.ScrapeDoQuotaError raised on 401/402/429 (monkeypatched httpx)
  * collect_search_dork brand selection (domain-label match else fewest-word)
  * collectors._gl_for_tenant country -> Google gl mapping
  * POST /api/tenants/{welspun}/run?collector=search_dork degrades gracefully
  * GET /api/monitoring-health shows the friendly quota message, no crash
"""
import os
import sys
import time

import pytest
import requests

sys.path.insert(0, "/app/backend")
import collectors  # noqa: E402

from conftest import API  # noqa: E402

WELSPUN_ID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"
QUOTA_MSG_PARTS = [
    "scrape.do monthly request limit exceeded",
    "wait for the new monthly period or upgrade your scrape.do plan",
]

WELSPUN_TENANT = {
    "id": WELSPUN_ID,
    "name": "Welspun",
    "brand_names": ["Globally recognized leaders in Home Textiles and Line Pipes", "Welspun"],
    "all_domains": ["welspun.com"],
    "country": "India",
}


# ── unit: _gl_for_tenant ────────────────────────────────────────────────────
class TestGlForTenant:
    def test_india_maps_to_in(self):
        assert collectors._gl_for_tenant(WELSPUN_TENANT) == "in"

    def test_us_default(self):
        assert collectors._gl_for_tenant({"country": "", "all_domains": ["stripe.com"]}) == "us"

    @pytest.mark.parametrize("country,gl", [
        ("United States", "us"), ("United Kingdom", "uk"), ("Germany", "de"),
        ("UAE", "ae"), ("Singapore", "sg"),
    ])
    def test_known_countries(self, country, gl):
        assert collectors._gl_for_tenant({"country": country}) == gl

    def test_dot_in_domain_fallback(self):
        assert collectors._gl_for_tenant({"country": "Atlantis", "all_domains": ["acme.co.in"]}) == "in"


# ── unit: ScrapeDoQuotaError ────────────────────────────────────────────────
class _FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class TestScrapeDoQuotaError:
    @pytest.mark.parametrize("code", [401, 402, 429])
    def test_raises_on_quota_codes(self, monkeypatch, code):
        monkeypatch.setenv("SCRAPE_DO_KEY", "dummy")
        monkeypatch.setattr(collectors.httpx, "get",
                            lambda *a, **k: _FakeResp(code, {"Message": ["Monthly request limit exceeded"]}))
        with pytest.raises(collectors.ScrapeDoQuotaError) as e:
            collectors._scrape_do_search("x")
        assert str(code) in str(e.value)
        assert "Monthly request limit exceeded" in str(e.value)

    def test_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_DO_KEY", raising=False)
        assert collectors._scrape_do_search("x") is None


# ── unit: brand selection inside collect_search_dork ───────────────────────
class TestBrandSelection:
    def _capture(self, monkeypatch, tenant):
        """Run collect_search_dork with a quota-failing stub, capture queries."""
        seen = {"queries": []}

        def fake_search(query, num=20, start=0, gl="us", hl="en"):
            seen["queries"].append(query)
            seen["gl"] = gl
            raise collectors.ScrapeDoQuotaError(
                "scrape.do request rejected (401): Monthly request limit exceeded")

        monkeypatch.setenv("SCRAPE_DO_KEY", "dummy")
        monkeypatch.setattr(collectors, "_scrape_do_search", fake_search)
        findings, health = collectors.collect_search_dork(tenant)
        return seen, findings, health

    def test_picks_domain_matching_brand_not_tagline(self, monkeypatch):
        seen, findings, health = self._capture(monkeypatch, WELSPUN_TENANT)
        assert seen["queries"], "no query was built"
        q = seen["queries"][0]
        assert q.startswith("Welspun ("), f"expected brand 'Welspun', got query: {q}"
        assert "Globally recognized" not in q
        assert seen["gl"] == "in"

    def test_fewest_word_fallback_when_no_domain_match(self, monkeypatch):
        tenant = {"id": "t2", "name": "T2",
                  "brand_names": ["A very long marketing tagline here", "Acme"],
                  "all_domains": ["something-else.com"], "country": "United States"}
        seen, _, _ = self._capture(monkeypatch, tenant)
        assert seen["queries"][0].startswith("Acme (")
        assert seen["gl"] == "us"

    def test_quota_short_circuits_and_reports_friendly_message(self, monkeypatch):
        seen, findings, health = self._capture(monkeypatch, WELSPUN_TENANT)
        # Only ONE request attempted: pagination + top-up must both short-circuit
        assert len(seen["queries"]) == 1, f"quota did not short-circuit: {seen['queries']}"
        assert findings == []
        assert health["status"] == "degraded"
        assert health["items_found"] == 0
        for part in QUOTA_MSG_PARTS:
            assert part in health["error"], health["error"]

    def test_no_exception_leaks(self, monkeypatch):
        """collect_search_dork must never propagate ScrapeDoQuotaError."""
        _, _, health = self._capture(monkeypatch, WELSPUN_TENANT)
        assert health["collector"] == "Search/Dorking"
        assert isinstance(health["duration_ms"], int)


# ── API: live run against the real account ─────────────────────────────────
# NOTE (iteration 7): serper.dev is now the fallback provider, so a live run no
# longer ends 'degraded' — it ends 'healthy' with serper findings. These live
# tests consume serper's free monthly quota, so they are opt-in via
# RUN_SERPER_LIVE=1 (see tests/test_serper_live_welspun.py for the serper path).
@pytest.mark.skipif(os.environ.get("RUN_SERPER_LIVE") != "1",
                    reason="live search run disabled (set RUN_SERPER_LIVE=1)")
class TestLiveGracefulDegradation:
    def test_run_returns_200_fast(self, admin):
        t0 = time.time()
        r = admin.post(f"{API}/tenants/{WELSPUN_ID}/run?collector=search_dork", timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:400]
        assert elapsed < 15, f"run endpoint blocked for {elapsed:.1f}s (should be async)"
        body = r.json()
        assert body.get("ok") is True, body

    def test_health_reflects_fallback_outcome(self, admin):
        deadline = time.time() + 120
        row = None
        while time.time() < deadline:
            time.sleep(6)
            r = admin.get(f"{API}/monitoring-health?tenant_id={WELSPUN_ID}", timeout=60)
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            rows = data if isinstance(data, list) else (data.get("collectors") or data.get("items") or [])
            row = next((x for x in rows if x.get("collector") == "Search/Dorking"), None)
            if row and row.get("status") != "running":
                break
        assert row is not None, "no Search/Dorking row in monitoring-health"
        # scrape.do quota is exhausted -> serper fallback should make it healthy.
        # If serper is also exhausted the run must degrade gracefully (never fail).
        assert row["status"] in ("healthy", "degraded"), row
        if row["status"] == "healthy":
            assert row.get("items_found", 0) > 0, row
        else:
            assert row.get("error"), row

    def test_no_unhandled_quota_exception_in_backend_log(self):
        """The quota 401 must not surface as an unhandled exception."""
        path = "/var/log/supervisor/backend.err.log"
        if not os.path.exists(path):
            pytest.skip("backend.err.log missing")
        with open(path, errors="ignore") as fh:
            tail = fh.read()[-60000:]
        bad = [l for l in tail.splitlines()
               if "ScrapeDoQuotaError" in l or "HTTPStatusError" in l
               or "Internal Server Error" in l]
        assert not bad, f"unhandled scrape.do errors found: {bad[-5:]}"

    def test_backend_still_alive_after_run(self, admin):
        r = admin.get(f"{API}/tenants", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) > 0
