"""BM1 Brand Monitoring — backend smoke/regression suite."""
import csv
import io
import time

import pytest
import requests

from conftest import API, CREDS


# ---------------- Auth module ----------------
class TestAuth:
    def test_login_all_roles(self, anon):
        for role, (email, pwd) in CREDS.items():
            r = anon.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=60)
            assert r.status_code == 200, f"{role}: {r.status_code} {r.text[:200]}"
            d = r.json()
            assert isinstance(d.get("token"), str) and len(d["token"]) > 20
            assert d["user"]["email"] == email
            assert d["user"]["role"] == role

    def test_login_bad_password(self, anon):
        r = anon.post(f"{API}/auth/login",
                      json={"email": "admin@brandshield.io", "password": "wrong"}, timeout=60)
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_login_unknown_user(self, anon):
        r = anon.post(f"{API}/auth/login",
                      json={"email": "nobody@nowhere.io", "password": "x"}, timeout=60)
        assert r.status_code == 401

    def test_me(self, admin):
        r = admin.get(f"{API}/auth/me", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "super_admin"
        assert "password_hash" not in d
        assert "_id" not in d

    def test_me_requires_auth(self, anon):
        r = anon.get(f"{API}/auth/me", timeout=60)
        assert r.status_code == 401

    def test_invalid_token_rejected(self, anon):
        r = anon.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"}, timeout=60)
        assert r.status_code == 401


# ---------------- Tenants module ----------------
class TestTenants:
    def test_list_tenants_seeded(self, admin):
        r = admin.get(f"{API}/tenants", timeout=60)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 2
        names = [t["name"] for t in items]
        assert "Stripe Payments" in names
        assert "Netflix Media" in names
        for t in items:
            assert "_id" not in t
            assert "id" in t

    def test_get_tenant_detail(self, admin, tenant_ids):
        r = admin.get(f"{API}/tenants/{tenant_ids[0]}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == tenant_ids[0]
        assert "identity" in d
        assert "_id" not in d

    def test_get_tenant_404(self, admin):
        r = admin.get(f"{API}/tenants/does-not-exist", timeout=60)
        assert r.status_code == 404

    def test_tenant_scope_for_viewer(self, viewer):
        r = viewer.get(f"{API}/tenants", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_tenant_crud_super_admin(self, admin):
        payload = {"name": "TEST_QA Tenant", "industry": "Technology",
                   "primary_domain": "test-qa-tenant.example",
                   "brand_names": ["TEST_QA"], "products": [],
                   "additional_domains": []}
        c = admin.post(f"{API}/tenants", json=payload, timeout=120)
        assert c.status_code in (200, 201), c.text[:300]
        t = c.json()
        tid = t["id"]
        try:
            assert t["name"] == payload["name"]
            g = admin.get(f"{API}/tenants/{tid}", timeout=60)
            assert g.status_code == 200
            assert g.json()["name"] == payload["name"]

            u = admin.put(f"{API}/tenants/{tid}", json={"industry": "Finance"}, timeout=60)
            assert u.status_code == 200, u.text[:300]
            g2 = admin.get(f"{API}/tenants/{tid}", timeout=60)
            assert g2.json()["industry"] == "Finance"
        finally:
            d = admin.delete(f"{API}/tenants/{tid}", timeout=60)
            assert d.status_code in (200, 204)
            assert admin.get(f"{API}/tenants/{tid}", timeout=60).status_code == 404


# ---------------- Findings + filter engine ----------------
class TestFindings:
    def test_list_findings(self, admin):
        r = admin.get(f"{API}/findings", params={"page": 1, "page_size": 10}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert set(["total", "page", "page_size", "items"]).issubset(d)
        assert isinstance(d["items"], list)
        assert len(d["items"]) <= 10
        for it in d["items"]:
            assert "_id" not in it

    def test_filter_by_severity(self, admin):
        r = admin.get(f"{API}/findings", params={"severity": "High", "page_size": 25}, timeout=90)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["severity"] == "High"

    def test_filter_by_module_and_risk_range(self, admin):
        r = admin.get(f"{API}/findings",
                      params={"module": "Fake Websites", "risk_min": 50, "risk_max": 100},
                      timeout=90)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["module"] == "Fake Websites"
            assert 50 <= it["risk_score"] <= 100

    def test_filter_by_tenant(self, admin, tenant_ids):
        r = admin.get(f"{API}/findings", params={"tenant_id": tenant_ids[0]}, timeout=90)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["tenant_id"] == tenant_ids[0]

    def test_search_filter(self, admin):
        r = admin.get(f"{API}/findings", params={"search": "stripe"}, timeout=90)
        assert r.status_code == 200

    def test_sort_by_severity(self, admin):
        r = admin.get(f"{API}/findings", params={"sort_by": "severity", "sort_dir": "desc"},
                      timeout=90)
        assert r.status_code == 200
        order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        vals = [order.get(i.get("severity"), 0) for i in r.json()["items"]]
        assert vals == sorted(vals, reverse=True)

    def test_facets(self, admin):
        r = admin.get(f"{API}/findings/facets", timeout=90)
        assert r.status_code == 200
        f = r.json()
        for k in ["source", "platform", "category", "registrar", "tld"]:
            assert k in f and isinstance(f[k], list)

    def test_finding_detail_and_update(self, admin):
        lst = admin.get(f"{API}/findings", params={"page_size": 1}, timeout=90).json()
        if not lst["items"]:
            pytest.skip("no findings seeded")
        fid = lst["items"][0]["id"]
        g = admin.get(f"{API}/findings/{fid}", timeout=60)
        assert g.status_code == 200
        assert g.json()["id"] == fid
        original = g.json().get("status")

        u = admin.put(f"{API}/findings/{fid}", json={"status": "Investigating"}, timeout=60)
        assert u.status_code == 200, u.text[:300]
        assert admin.get(f"{API}/findings/{fid}", timeout=60).json()["status"] == "Investigating"
        admin.put(f"{API}/findings/{fid}", json={"status": original or "New"}, timeout=60)

    def test_finding_404(self, admin):
        r = admin.get(f"{API}/findings/nope-123", timeout=60)
        assert r.status_code == 404

    def test_findings_requires_auth(self, anon):
        assert anon.get(f"{API}/findings", timeout=60).status_code == 401


# ---------------- CSV export + PDF report ----------------
class TestExport:
    HEADER = ["Title", "Category", "Module", "Source", "Platform", "Severity",
              "Risk Score", "Status", "Domain", "URL", "First Seen", "Last Seen"]

    def test_csv_export(self, admin):
        r = admin.get(f"{API}/findings/export", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert "text/csv" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "")
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == self.HEADER

    def test_csv_export_filtered(self, admin):
        r = admin.get(f"{API}/findings/export", params={"severity": "High"}, timeout=120)
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == self.HEADER
        for row in rows[1:]:
            assert row[5] == "High"

    def test_pdf_report(self, admin):
        r = admin.get(f"{API}/findings/report.pdf", timeout=180)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:4] == b"%PDF"


# ---------------- Dashboard / monitoring health ----------------
class TestDashboard:
    def test_stats(self, admin):
        r = admin.get(f"{API}/dashboard/stats", timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert isinstance(d, dict) and len(d) > 0

    def test_stats_scoped_to_tenant(self, admin, tenant_ids):
        r = admin.get(f"{API}/dashboard/stats", params={"tenant_id": tenant_ids[0]}, timeout=90)
        assert r.status_code == 200

    def test_monitoring_health(self, admin):
        r = admin.get(f"{API}/monitoring-health", timeout=90)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert "_id" not in row


# ---------------- Scheduler / Run Now ----------------
class TestRunNow:
    def test_run_now_super_admin(self, admin, tenant_ids):
        r = admin.post(f"{API}/tenants/{tenant_ids[0]}/run",
                       params={"collector": "typosquat"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True

    def test_run_now_findings_visible_after_run(self, admin, tenant_ids):
        before = admin.get(f"{API}/findings", params={"tenant_id": tenant_ids[0]},
                           timeout=90).json()["total"]
        r = admin.post(f"{API}/tenants/{tenant_ids[0]}/run", timeout=120)
        assert r.status_code == 200
        time.sleep(25)
        after = admin.get(f"{API}/findings", params={"tenant_id": tenant_ids[0]},
                          timeout=90).json()["total"]
        assert after >= before
        health = admin.get(f"{API}/monitoring-health",
                           params={"tenant_id": tenant_ids[0]}, timeout=90).json()
        assert isinstance(health, list)

    def test_run_now_unknown_tenant(self, admin):
        r = admin.post(f"{API}/tenants/no-such-tenant/run", timeout=60)
        assert r.status_code == 404

    def test_run_now_viewer_forbidden(self, viewer, tenant_ids):
        r = viewer.post(f"{API}/tenants/{tenant_ids[0]}/run", timeout=60)
        assert r.status_code == 403

    def test_schedules_list(self, admin):
        r = admin.get(f"{API}/schedules", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Saved filters / presets ----------------
class TestSavedFilters:
    def test_saved_filter_crud(self, admin):
        body = {"name": "TEST_QA filter", "screen": "all_findings",
                "conditions": {"severity": "High"}}
        c = admin.post(f"{API}/saved-filters", json=body, timeout=60)
        assert c.status_code in (200, 201), c.text[:300]
        sid = c.json()["id"]
        try:
            lst = admin.get(f"{API}/saved-filters", params={"screen": "all_findings"},
                            timeout=60)
            assert lst.status_code == 200
            got = [f for f in lst.json() if f["id"] == sid]
            assert got, "saved filter not returned by GET"
            assert got[0]["conditions"]["severity"] == "High"
        finally:
            d = admin.delete(f"{API}/saved-filters/{sid}", timeout=60)
            assert d.status_code in (200, 204)
            remaining = admin.get(f"{API}/saved-filters", timeout=60).json()
            assert all(f["id"] != sid for f in remaining)

    def test_presets_list(self, admin):
        r = admin.get(f"{API}/presets", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Cases module ----------------
class TestCases:
    def test_case_lifecycle(self, analyst, tenant_ids, admin):
        lst = admin.get(f"{API}/findings", params={"tenant_id": tenant_ids[0], "page_size": 1},
                        timeout=90).json()
        fids = [i["id"] for i in lst["items"]]
        body = {"title": "TEST_QA Case", "tenant_id": tenant_ids[0],
                "severity": "High", "finding_ids": fids}
        c = analyst.post(f"{API}/cases", json=body, timeout=60)
        assert c.status_code in (200, 201), c.text[:300]
        cid = c.json()["id"]
        assert c.json()["title"] == "TEST_QA Case"

        g = analyst.get(f"{API}/cases/{cid}", timeout=60)
        assert g.status_code == 200
        assert g.json()["id"] == cid

        u = analyst.put(f"{API}/cases/{cid}", json={"status": "In Progress",
                                                   "note": "QA note"}, timeout=60)
        assert u.status_code == 200, u.text[:300]
        assert analyst.get(f"{API}/cases/{cid}", timeout=60).json()["status"] == "In Progress"

    def test_cases_list(self, admin):
        r = admin.get(f"{API}/cases", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_case_create_viewer_forbidden(self, viewer, tenant_ids):
        r = viewer.post(f"{API}/cases", json={"title": "TEST_QA nope",
                                              "tenant_id": tenant_ids[0]}, timeout=60)
        assert r.status_code == 403


# ---------------- RBAC ----------------
ADMIN_ONLY_GET = ["/intelligence-sources", "/detection-config", "/notifications-config",
                  "/system-settings"]


class TestRBAC:
    @pytest.mark.parametrize("path", ADMIN_ONLY_GET)
    def test_admin_config_readable_by_super_admin(self, admin, path):
        r = admin.get(f"{API}{path}", timeout=60)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"

    @pytest.mark.parametrize("path", ADMIN_ONLY_GET)
    def test_admin_config_blocked_for_viewer(self, viewer, path):
        r = viewer.get(f"{API}{path}", timeout=60)
        assert r.status_code == 403, f"{path} viewer got {r.status_code}"

    @pytest.mark.parametrize("path", ADMIN_ONLY_GET)
    def test_admin_config_write_blocked_for_viewer(self, viewer, path):
        r = viewer.put(f"{API}{path}", json={"x": 1}, timeout=60)
        assert r.status_code == 403, f"{path} viewer PUT got {r.status_code}"

    @pytest.mark.parametrize("path", ADMIN_ONLY_GET)
    def test_admin_config_blocked_for_analyst(self, analyst, path):
        assert analyst.get(f"{API}{path}", timeout=60).status_code == 403

    def test_viewer_cannot_create_tenant(self, viewer):
        r = viewer.post(f"{API}/tenants", json={"name": "TEST_QA bad",
                                                "primary_domain": "x.example"}, timeout=60)
        assert r.status_code == 403

    def test_viewer_cannot_list_users(self, viewer):
        assert viewer.get(f"{API}/users", timeout=60).status_code == 403

    def test_viewer_cannot_update_finding(self, viewer, admin):
        lst = admin.get(f"{API}/findings", params={"page_size": 1}, timeout=90).json()
        if not lst["items"]:
            pytest.skip("no findings")
        fid = lst["items"][0]["id"]
        assert viewer.put(f"{API}/findings/{fid}", json={"status": "Resolved"},
                          timeout=60).status_code == 403

    def test_viewer_can_read_findings(self, viewer):
        r = viewer.get(f"{API}/findings", timeout=90)
        assert r.status_code == 200

    def test_audit_logs_rbac(self, admin, viewer):
        assert admin.get(f"{API}/audit-logs", timeout=60).status_code == 200
        assert viewer.get(f"{API}/audit-logs", timeout=60).status_code == 403

    def test_tenant_admin_cannot_touch_admin_config(self, tadmin):
        for path in ADMIN_ONLY_GET:
            assert tadmin.get(f"{API}{path}", timeout=60).status_code == 403


# ---------------- Users module ----------------
class TestUsers:
    def test_user_crud(self, admin):
        body = {"name": "TEST_QA User", "email": "test_qa_user@brandshield.io",
                "password": "QaPass@123", "role": "viewer", "tenant_ids": []}
        admin.delete(f"{API}/users/none", timeout=30)
        c = admin.post(f"{API}/users", json=body, timeout=60)
        assert c.status_code in (200, 201), c.text[:300]
        uid = c.json()["id"]
        try:
            assert c.json()["email"] == body["email"]
            assert "password_hash" not in c.json()
            lst = admin.get(f"{API}/users", timeout=60)
            assert lst.status_code == 200
            assert any(u["id"] == uid for u in lst.json())

            # new user can log in
            lr = requests.post(f"{API}/auth/login",
                               json={"email": body["email"], "password": body["password"]},
                               timeout=60)
            assert lr.status_code == 200, lr.text[:200]

            u = admin.put(f"{API}/users/{uid}", json={"name": "TEST_QA Renamed"}, timeout=60)
            assert u.status_code == 200
            assert any(x["id"] == uid and x["name"] == "TEST_QA Renamed"
                       for x in admin.get(f"{API}/users", timeout=60).json())
        finally:
            d = admin.delete(f"{API}/users/{uid}", timeout=60)
            assert d.status_code in (200, 204)
            assert all(u["id"] != uid for u in admin.get(f"{API}/users", timeout=60).json())

    def test_duplicate_email_rejected(self, admin):
        r = admin.post(f"{API}/users", json={"name": "dup", "email": "admin@brandshield.io",
                                             "password": "X@12345", "role": "viewer"}, timeout=60)
        assert r.status_code in (400, 409), f"expected 4xx got {r.status_code}"


# ---------------- Audit logs ----------------
class TestAuditLogs:
    def test_audit_logs_list(self, admin):
        r = admin.get(f"{API}/audit-logs", timeout=60)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, (list, dict))
