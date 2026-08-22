"""Welspun scrape.do search/dorking verification + regression tests (iteration 4)."""
import os
import re
import time
from urllib.parse import urlparse

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = ("admin@brandshield.io", "Admin@123")
ROLES = [
    ("admin@brandshield.io", "Admin@123"),
    ("tadmin@brandshield.io", "Tenant@123"),
    ("analyst@brandshield.io", "Analyst@123"),
    ("viewer@brandshield.io", "Viewer@123"),
]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=60)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_headers():
    return {"Authorization": f"Bearer {_login(*ADMIN)}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def welspun_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/tenants", headers=admin_headers, timeout=60)
    assert r.status_code == 200
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    cands = [t for t in items if t.get("name") == "Welspun"]
    assert cands, "Welspun tenant missing"
    # pick the one with the most social findings (duplicates exist in DB)
    best, best_n = None, -1
    for t in cands:
        fr = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                          params={"tenant_id": t["id"], "module": "social", "page_size": 1}, timeout=60)
        n = fr.json().get("total", 0)
        if n > best_n:
            best, best_n = t["id"], n
    return best


# ── Security/config: key must come from env, never source ──────────────────
class TestConfigSecurity:
    def test_scrape_do_key_in_env_not_source(self):
        env = dotenv_values("/app/backend/.env")
        key = env.get("SCRAPE_DO_KEY")
        assert key, "SCRAPE_DO_KEY missing from backend/.env"
        src = ""
        for root, _dirs, files in os.walk("/app/backend"):
            if "tests" in root or "__pycache__" in root or "node_modules" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    src += open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
        assert key not in src, "scrape.do key is hardcoded in backend source!"
        assert "os.environ" in src


# ── PRIMARY: fresh search_dork run for Welspun ─────────────────────────────
class TestWelspunSearchRun:
    def test_trigger_run_and_health_healthy(self, admin_headers, welspun_id):
        before = requests.get(f"{BASE_URL}/api/monitoring-health", headers=admin_headers,
                              params={"tenant_id": welspun_id}, timeout=60).json()
        prev = next((r for r in before if r.get("collector_key") == "search_dork"), {})
        prev_run = prev.get("last_run")

        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/tenants/{welspun_id}/run",
                          headers=admin_headers, params={"collector": "search_dork"}, timeout=60)
        assert r.status_code == 200, f"run -> {r.status_code} {r.text[:300]}"
        assert time.time() - t0 < 15, "run endpoint should return fast (background task)"

        # overlap guard
        r2 = requests.post(f"{BASE_URL}/api/tenants/{welspun_id}/run",
                           headers=admin_headers, params={"collector": "search_dork"}, timeout=60)
        assert r2.status_code in (200, 409), f"overlap -> {r2.status_code}"
        assert "already running" in r2.text.lower(), f"expected overlap message, got {r2.text[:300]}"

        row = None
        for _ in range(40):
            time.sleep(5)
            hs = requests.get(f"{BASE_URL}/api/monitoring-health", headers=admin_headers,
                              params={"tenant_id": welspun_id}, timeout=60).json()
            row = next((x for x in hs if x.get("collector_key") == "search_dork"), None)
            if row and row.get("last_run") and row.get("last_run") != prev_run:
                break
        assert row, "no search_dork health row"
        assert row.get("last_run") != prev_run, f"run never completed: {row}"
        assert row.get("status") == "healthy", f"status={row.get('status')} error={row.get('error')}"
        assert row.get("items_found", 0) > 0, f"items_found={row.get('items_found')}"
        print("HEALTH ROW:", row)


# ── PRIMARY: social findings quality ───────────────────────────────────────
EXPECTED_HOSTS = ["instagram.com", "x.com", "twitter.com", "facebook.com", "linkedin.com",
                  "youtube.com", "tiktok.com", "threads.net", "threads.com", "pinterest.com",
                  "t.me", "reddit.com", "scribd.com"]


@pytest.fixture(scope="session")
def social_findings(admin_headers, welspun_id):
    r = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                     params={"tenant_id": welspun_id, "module": "social", "page_size": 100}, timeout=90)
    assert r.status_code == 200, r.text[:300]
    return r.json()


class TestWelspunSocialFindings:
    def test_no_mongo_id_leak(self, social_findings):
        for it in social_findings.get("items", []):
            assert "_id" not in it

    def test_count_and_platform_spread(self, social_findings):
        items = social_findings.get("items", [])
        assert social_findings.get("total", 0) >= 20, f"total={social_findings.get('total')}"
        plats = {}
        for it in items:
            plats[it.get("platform")] = plats.get(it.get("platform"), 0) + 1
        print("PLATFORMS:", plats, "TOTAL:", social_findings.get("total"))
        assert len(plats) >= 5, f"only {len(plats)} platforms: {plats}"

    def test_urls_point_to_social_hosts(self, social_findings):
        bad = []
        for it in social_findings.get("items", []):
            host = (urlparse(it.get("url") or "").netloc or "").lower()
            if not any(h in host for h in EXPECTED_HOSTS):
                bad.append(it.get("url"))
        assert not bad, f"non-social URLs: {bad[:10]}"

    def test_brand_relevance(self, social_findings):
        bad = []
        for it in social_findings.get("items", []):
            hay = ((it.get("title") or "") + (it.get("url") or "") +
                   str((it.get("evidence") or {}).get("snippet") or "")).lower().replace(" ", "")
            if "welspun" not in hay:
                bad.append(it.get("title"))
        assert not bad, f"irrelevant findings: {bad[:10]}"

    def test_accounts_and_posts_present(self, social_findings):
        urls = [(it.get("url") or "") for it in social_findings.get("items", [])]
        posts = [u for u in urls if re.search(r"/(p|reel|posts|status|watch|shorts|video|comments)/", u)]
        profiles = [u for u in urls if len(urlparse(u).path.strip("/").split("/")) == 1 and urlparse(u).path.strip("/")]
        print("POSTS:", len(posts), "PROFILES:", len(profiles))
        assert posts, "no post-style URLs found"
        assert profiles, "no profile/account-style URLs found"

    def test_entities_populated(self, social_findings):
        items = social_findings.get("items", [])
        with_cls = [i for i in items if (i.get("entities") or {}).get("impersonation_classification")]
        assert len(with_cls) == len(items), "some findings missing impersonation_classification"
        assert all((i.get("entities") or {}).get("username") for i in items)

    def test_platform_filter_narrows(self, admin_headers, welspun_id):
        r = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                         params={"tenant_id": welspun_id, "module": "social",
                                 "platform": "Instagram", "page_size": 100}, timeout=60)
        assert r.status_code == 200
        items = r.json().get("items", [])
        if items:
            assert all("instagram" in (i.get("platform") or "").lower() or
                       "instagram.com" in (i.get("url") or "") for i in items), "platform filter leaks"
        print("instagram filtered:", len(items))

    def test_search_q_filter(self, admin_headers, welspun_id):
        r = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                         params={"tenant_id": welspun_id, "module": "social", "q": "welspun", "page_size": 20}, timeout=60)
        assert r.status_code == 200
        assert r.json().get("total", 0) > 0


# ── REGRESSION ─────────────────────────────────────────────────────────────
class TestRegression:
    @pytest.mark.parametrize("email,pwd", ROLES)
    def test_all_role_logins(self, email, pwd):
        assert _login(email, pwd)

    def test_stripe_social_findings_intact(self, admin_headers):
        ts = requests.get(f"{BASE_URL}/api/tenants", headers=admin_headers, timeout=60).json()
        items = ts if isinstance(ts, list) else ts.get("items", [])
        sid = next(t["id"] for t in items if t["name"] == "Stripe Payments")
        r = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                         params={"tenant_id": sid, "module": "social", "page_size": 25}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d.get("total") == 69, f"expected 69 seeded stripe social findings, got {d.get('total')}"
        assert len(d.get("items", [])) == 25, "page_size not honoured"
        p2 = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers,
                          params={"tenant_id": sid, "module": "social", "page": 2, "page_size": 25}, timeout=60).json()
        assert len(p2.get("items", [])) == 25
        assert {i["id"] for i in d["items"]}.isdisjoint({i["id"] for i in p2["items"]}), "pagination overlap"

    def test_report_pdf(self, admin_headers, welspun_id):
        r = requests.get(f"{BASE_URL}/api/findings/report.pdf", headers=admin_headers,
                         params={"tenant_id": welspun_id}, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF", r.content[:20]

    def test_csv_export_contains_welspun_social_rows(self, admin_headers, welspun_id):
        r = requests.get(f"{BASE_URL}/api/findings/export", headers=admin_headers,
                         params={"tenant_id": welspun_id, "module": "social"}, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        text = r.text
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) > 20, f"only {len(lines)} csv lines"
        assert "welspun" in text.lower()
        assert any(h in text for h in ("instagram.com", "linkedin.com", "reddit.com"))
