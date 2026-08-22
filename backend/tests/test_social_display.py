"""Iteration 2: search_dork collector run + social findings DISPLAY path (pagination/filters/search/CSV/PDF)."""
import time
import pytest
import requests
from conftest import API


# ---------------------------------------------------------------- helpers
@pytest.fixture(scope="module")
def tenants(admin):
    r = admin.get(f"{API}/tenants", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return {t["name"]: t for t in r.json()}


@pytest.fixture(scope="module")
def stripe_id(tenants):
    t = tenants.get("Stripe Payments")
    if not t:
        pytest.fail(f"Stripe Payments tenant missing. Have: {list(tenants)}")
    return t["id"]


@pytest.fixture(scope="module")
def aig_id(tenants):
    t = tenants.get("AIG Hospital")
    if not t:
        pytest.fail(f"AIG Hospital tenant missing. Have: {list(tenants)}")
    return t["id"]


def get_findings(client, **params):
    r = client.get(f"{API}/findings", params=params, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    d = r.json()
    for k in ("total", "page", "page_size", "items"):
        assert k in d, f"missing key {k} in findings response"
    assert all("_id" not in it for it in d["items"]), "MongoDB _id leaked in findings response"
    return d


# ---------------------------------------------------------------- search_dork collector run
class TestSearchDorkRun:
    def test_trigger_search_dork_for_aig(self, admin, aig_id):
        r = admin.post(f"{API}/tenants/{aig_id}/run?collector=search_dork", timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        assert r.json().get("ok") is True, r.text[:300]

    def test_monitoring_health_search_dork_row(self, admin, aig_id):
        # background run may take up to ~90s; poll
        row, deadline = None, time.time() + 180
        while time.time() < deadline:
            r = admin.get(f"{API}/monitoring-health", params={"tenant_id": aig_id}, timeout=120)
            assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
            rows = r.json()
            row = next((x for x in rows if x.get("collector_key") == "search_dork"
                        or x.get("collector") == "Search/Dorking"), None)
            if row and row.get("status") not in (None, "running", "queued"):
                break
            time.sleep(10)
        assert row is not None, "no Search/Dorking row in monitoring-health for AIG"
        assert row.get("status") in ("healthy", "degraded"), f"unexpected status: {row}"
        assert isinstance(row.get("items_found", 0), int)

    def test_backend_error_log_clean(self):
        try:
            with open("/var/log/supervisor/backend.err.log", errors="ignore") as f:
                tail = f.read()[-20000:]
        except FileNotFoundError:
            pytest.skip("backend.err.log not found")
        bad = [l for l in tail.splitlines()
               if "Traceback" in l or "Internal Server Error" in l]
        assert not bad, f"errors in backend log: {bad[-5:]}"


# ---------------------------------------------------------------- social findings display path
class TestSocialDisplay:
    def test_stripe_social_total_is_69(self, admin, stripe_id):
        d = get_findings(admin, module="social", tenant_id=stripe_id, page=1, page_size=25)
        assert d["total"] == 69, f"expected 69 social findings for Stripe, got {d['total']}"
        assert len(d["items"]) == 25

    def test_pagination_returns_every_record(self, admin, stripe_id):
        ids, page = set(), 1
        while True:
            d = get_findings(admin, module="social", tenant_id=stripe_id, page=page, page_size=25)
            if not d["items"]:
                break
            ids.update(i["id"] for i in d["items"])
            if page * 25 >= d["total"]:
                break
            page += 1
        assert len(ids) == 69, f"paging returned {len(ids)} unique findings, expected 69"

    def test_large_page_size_returns_all(self, admin, stripe_id):
        d = get_findings(admin, module="social", tenant_id=stripe_id, page=1, page_size=100)
        assert d["total"] == 69
        assert len(d["items"]) == 69

    def test_all_items_have_social_module_and_entities(self, admin, stripe_id):
        d = get_findings(admin, module="social", tenant_id=stripe_id, page=1, page_size=100)
        for it in d["items"]:
            assert it["module"] == "social", it
            assert it["tenant_id"] == stripe_id
            ent = it.get("entities") or {}
            assert ent.get("account_name"), f"missing account_name: {it['id']}"
            assert ent.get("username"), f"missing username: {it['id']}"
            assert ent.get("impersonation_classification"), f"missing classification: {it['id']}"


# ---------------------------------------------------------------- filters
class TestSocialFilters:
    def test_platform_filter_scoped(self, admin, stripe_id):
        base = get_findings(admin, module="social", tenant_id=stripe_id, page_size=100)
        by_platform = {}
        for it in base["items"]:
            by_platform.setdefault(it.get("platform"), 0)
            by_platform[it["platform"]] += 1
        assert by_platform, "no platforms present"
        total_seen = 0
        for plat, cnt in by_platform.items():
            d = get_findings(admin, module="social", tenant_id=stripe_id,
                             platform=plat, page_size=100)
            assert d["total"] == cnt, f"platform={plat}: API total {d['total']} != expected {cnt}"
            assert all(i["platform"] == plat for i in d["items"])
            total_seen += d["total"]
        assert total_seen == 69, f"platform subsets sum to {total_seen}, expected 69"

    def test_category_filter_scoped(self, admin, stripe_id):
        base = get_findings(admin, module="social", tenant_id=stripe_id, page_size=100)
        cats = {}
        for it in base["items"]:
            cats[it.get("category")] = cats.get(it.get("category"), 0) + 1
        total_seen = 0
        for cat, cnt in cats.items():
            d = get_findings(admin, module="social", tenant_id=stripe_id,
                             category=cat, page_size=100)
            assert d["total"] == cnt, f"category={cat}: {d['total']} != {cnt}"
            assert all(i["category"] == cat for i in d["items"])
            total_seen += d["total"]
        assert total_seen == 69

    def test_verification_filter_scoped(self, admin, stripe_id):
        base = get_findings(admin, module="social", tenant_id=stripe_id, page_size=100)
        classes = {}
        for it in base["items"]:
            c = (it.get("entities") or {}).get("impersonation_classification")
            classes[c] = classes.get(c, 0) + 1
        total_seen = 0
        for cls, cnt in classes.items():
            d = get_findings(admin, module="social", tenant_id=stripe_id,
                             impersonation_classification=cls, page_size=100)
            assert d["total"] == cnt, f"classification={cls}: {d['total']} != {cnt}"
            total_seen += d["total"]
        assert total_seen == 69

    def test_clearing_filters_restores_69(self, admin, stripe_id):
        get_findings(admin, module="social", tenant_id=stripe_id, platform="Instagram", page_size=100)
        d = get_findings(admin, module="social", tenant_id=stripe_id,
                         platform="All", category="All", impersonation_classification="All",
                         severity="All", status="All", source="All", page_size=100)
        assert d["total"] == 69, f"clearing filters gave {d['total']}"

    def test_search_filters_without_hiding_matches(self, admin, stripe_id):
        base = get_findings(admin, module="social", tenant_id=stripe_id, page_size=100)
        # pick a token from an existing title
        title = base["items"][0]["title"]
        token = next((w for w in title.split() if len(w) > 4), None)
        if not token:
            pytest.skip("no usable search token")
        expected = [i for i in base["items"] if token.lower() in (i["title"] or "").lower()]
        d = get_findings(admin, module="social", tenant_id=stripe_id, search=token, page_size=100)
        assert d["total"] == len(expected), \
            f"search '{token}': API {d['total']} vs expected {len(expected)}"
        assert d["total"] >= 1

    def test_search_no_match_returns_zero(self, admin, stripe_id):
        d = get_findings(admin, module="social", tenant_id=stripe_id,
                         search="ZZZ_NO_SUCH_TOKEN_ZZZ", page_size=100)
        assert d["total"] == 0
        assert d["items"] == []


# ---------------------------------------------------------------- detail + exports
class TestSocialDetailAndExport:
    def test_finding_detail_has_entity_fields(self, admin, stripe_id):
        d = get_findings(admin, module="social", tenant_id=stripe_id, page_size=1)
        fid = d["items"][0]["id"]
        r = admin.get(f"{API}/findings/{fid}", timeout=60)
        assert r.status_code == 200, r.text[:300]
        f = r.json()
        assert "_id" not in f
        ent = f.get("entities") or {}
        for k in ("account_name", "username", "description",
                  "impersonation_classification", "impersonation_confidence"):
            assert k in ent, f"entity field '{k}' missing from finding detail"

    def test_csv_export_contains_social_rows(self, admin, stripe_id):
        r = admin.get(f"{API}/findings/export",
                      params={"module": "social", "tenant_id": stripe_id}, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        lines = [l for l in r.text.strip().splitlines() if l.strip()]
        assert len(lines) >= 70, f"CSV has only {len(lines)} lines (header + rows), expected >= 70"
        assert "," in lines[0]

    def test_pdf_export_social(self, admin, stripe_id):
        r = admin.get(f"{API}/findings/report.pdf",
                      params={"module": "social", "tenant_id": stripe_id}, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.content[:4] == b"%PDF"

    def test_pdf_export_all_tenants(self, admin):
        r = admin.get(f"{API}/findings/report.pdf", timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.content[:4] == b"%PDF"


# ---------------------------------------------------------------- regression
class TestRegression:
    @pytest.mark.parametrize("email,password", [
        ("admin@brandshield.io", "Admin@123"),
        ("tadmin@brandshield.io", "Tenant@123"),
        ("analyst@brandshield.io", "Analyst@123"),
        ("viewer@brandshield.io", "Viewer@123"),
    ])
    def test_all_roles_login(self, email, password):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=60)
        assert r.status_code == 200, f"{email}: {r.status_code} {r.text[:200]}"
        assert r.json().get("token")

    def test_all_findings_unfiltered(self, admin):
        d = get_findings(admin, page=1, page_size=25)
        assert d["total"] > 0
        assert len(d["items"]) == 25

    def test_facets_include_social_categories(self, admin, stripe_id):
        r = admin.get(f"{API}/findings/facets", params={"tenant_id": stripe_id}, timeout=60)
        assert r.status_code == 200
        f = r.json()
        assert f.get("category"), "category facet empty"
        assert f.get("platform"), "platform facet empty"
