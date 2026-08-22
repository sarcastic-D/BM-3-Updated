"""Iteration 3: PDF export regression sweep (reportlab paraparser markup crash check)."""
import pytest
from conftest import API


@pytest.fixture(scope="module")
def tenants(admin):
    r = admin.get(f"{API}/tenants", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return r.json()


MODULES = [None, "social", "fake_website", "domain_intel", "mobile_app"]


class TestPdfExport:
    def test_pdf_all_tenants_all_modules(self, admin):
        r = admin.get(f"{API}/findings/report.pdf", timeout=180)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        assert r.content[:4] == b"%PDF", r.content[:20]

    def test_pdf_per_tenant_per_module(self, admin, tenants):
        failures = []
        for t in tenants:
            for m in MODULES:
                params = {"tenant_id": t["id"]}
                if m:
                    params["module"] = m
                r = admin.get(f"{API}/findings/report.pdf", params=params, timeout=180)
                if r.status_code != 200 or r.content[:4] != b"%PDF":
                    failures.append(f"{t['name']}/{m or 'all'} -> {r.status_code} {r.text[:120]}")
        assert not failures, "PDF export failed for: " + "; ".join(failures)
