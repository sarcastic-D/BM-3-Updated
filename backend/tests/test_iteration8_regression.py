"""Iteration 8 — regression + config/security checks."""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

CREDS = [("admin@brandshield.io", "Admin@123"),
         ("tadmin@brandshield.io", "Tenant@123"),
         ("analyst@brandshield.io", "Analyst@123"),
         ("viewer@brandshield.io", "Viewer@123")]


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    return r


@pytest.fixture(scope="module")
def admin():
    r = _login(*CREDS[0])
    assert r.status_code == 200, r.text[:200]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def stripe_id(admin):
    r = admin.get(f"{BASE_URL}/api/tenants", params={"page_size": 100}, timeout=30)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items", body) if isinstance(body, dict) else body
    t = next((x for x in items if x.get("tenant_id") == "TEN-0001"), None)
    assert t, "Stripe TEN-0001 not found"
    return t["id"]


# ── Role logins ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("email,pwd", CREDS)
def test_all_role_logins(email, pwd):
    r = _login(email, pwd)
    assert r.status_code == 200, f"{email}: {r.status_code} {r.text[:200]}"
    d = r.json()
    assert d.get("token") and d.get("user", {}).get("email") == email


def test_login_bad_password():
    r = _login("admin@brandshield.io", "wrong")
    assert r.status_code == 401


# ── Stripe social regression ────────────────────────────────────────────────
class TestStripeRegression:
    def test_social_count_and_pagination(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social", "page_size": 300}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        total = d.get("total")
        print("stripe social total:", total)
        assert total >= 69, f"expected >=69 seeded social findings, got {total}"
        seen, page = set(), 1
        while len(seen) < total and page <= 10:
            rp = admin.get(f"{BASE_URL}/api/findings",
                           params={"tenant_id": stripe_id, "module": "social",
                                   "page": page, "page_size": 25}, timeout=60)
            assert rp.status_code == 200
            batch = rp.json().get("items", [])
            if not batch:
                break
            seen.update(f["id"] for f in batch)
            page += 1
        assert len(seen) == total

    def test_platform_filter(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social",
                              "platform": "instagram", "page_size": 300}, timeout=60)
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert all((f.get("platform") or "").lower() == "instagram" for f in items)

    def test_search(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social",
                              "search": "stripe", "page_size": 50}, timeout=60)
        assert r.status_code == 200
        assert r.json().get("total", 0) > 0

    def test_finding_detail(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social", "page_size": 1}, timeout=60)
        fid = r.json()["items"][0]["id"]
        d = admin.get(f"{BASE_URL}/api/findings/{fid}", timeout=30)
        assert d.status_code == 200
        body = d.json()
        assert body["id"] == fid and "_id" not in body

    def test_csv_export(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings/export",
                      params={"tenant_id": stripe_id, "module": "social"}, timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert "text/csv" in r.headers.get("content-type", "")
        lines = r.text.strip().splitlines()
        print("csv rows:", len(lines) - 1)
        assert len(lines) > 10

    def test_report_pdf(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings/report.pdf",
                      params={"tenant_id": stripe_id}, timeout=120)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF", r.content[:20]


# ── Welspun CSV export ──────────────────────────────────────────────────────
def test_welspun_csv_export(admin):
    wid = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"
    r = admin.get(f"{BASE_URL}/api/findings/export",
                  params={"tenant_id": wid, "module": "social"}, timeout=90)
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    print("welspun csv rows:", len(lines) - 1)
    assert len(lines) - 1 >= 200
    assert "welspun" in r.text.lower()


# ── Monitoring health ───────────────────────────────────────────────────────
def test_monitoring_health(admin):
    wid = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"
    r = admin.get(f"{BASE_URL}/api/monitoring-health", params={"tenant_id": wid}, timeout=60)
    assert r.status_code == 200
    print("health:", str(r.json())[:500])


# ── Config / security: keys must come from env, not hardcoded ───────────────
def test_keys_not_hardcoded():
    offenders = []
    env = dotenv_values("/app/backend/.env")
    secrets = [v for k, v in env.items() if k in ("SERPER_KEY", "SCRAPE_DO_KEY") and v]
    assert secrets, "SERPER_KEY/SCRAPE_DO_KEY missing from backend/.env"
    for p in Path("/app/backend").rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        txt = p.read_text(errors="ignore")
        for s in secrets:
            if s in txt:
                offenders.append(str(p))
    assert not offenders, f"secret literal found in: {offenders}"


def test_frontend_no_hardcoded_backend_url():
    bad = []
    for p in Path("/app/frontend/src").rglob("*.js"):
        txt = p.read_text(errors="ignore")
        if re.search(r"https?://[a-z0-9.-]*preview\.emergentagent\.com", txt):
            bad.append(str(p))
    assert not bad, f"hardcoded backend URL in: {bad}"


# ── Run Now overlapping guard (uses Stripe, no serper cost concern? -> skip
#    external providers by targeting a module-less run is not possible, so we
#    only assert the guard message on a second immediate call) ──────────────
def test_run_now_guard(admin, stripe_id):
    """Overlapping Run Now must be rejected. Uses the cheap 'dns' collector only
    (no serper/scrape.do quota spend)."""
    r1 = admin.post(f"{BASE_URL}/api/tenants/{stripe_id}/run", params={"collector": "dns"}, timeout=60)
    assert r1.status_code == 200, r1.text[:200]
    assert "started" in r1.json().get("message", "").lower()
    r2 = admin.post(f"{BASE_URL}/api/tenants/{stripe_id}/run", params={"collector": "dns"}, timeout=60)
    assert r2.status_code == 200
    msg = r2.json().get("message", "")
    print("second run-now:", msg)
    assert msg == "A scan is already running for this tenant", msg


def test_run_now_forbidden_for_viewer(stripe_id):
    r = _login("viewer@brandshield.io", "Viewer@123")
    tok = r.json()["token"]
    rr = requests.post(f"{BASE_URL}/api/tenants/{stripe_id}/run",
                       headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    assert rr.status_code == 403, rr.status_code


def test_findings_requires_auth():
    r = requests.get(f"{BASE_URL}/api/findings", timeout=30)
    assert r.status_code in (401, 403)
