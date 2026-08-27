"""Iteration 3: paced DuckDuckGo-first search_dork collector.
Covers: fast background /run response, overlapping-run guard, degraded health with
human-readable error, expanded DORK_TARGETS platform list, no backend crash.
"""
import os
import sys
import time
import pytest
from conftest import API

sys.path.insert(0, "/app/backend")

ERR_LOG = "/var/log/supervisor/backend.err.log"


def _read_log_size():
    try:
        return os.path.getsize(ERR_LOG)
    except OSError:
        return 0


def _new_log_text(offset):
    try:
        with open(ERR_LOG, errors="ignore") as f:
            f.seek(offset)
            return f.read()
    except OSError:
        return ""


@pytest.fixture(scope="module")
def tenants(admin):
    r = admin.get(f"{API}/tenants", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return {t["name"]: t for t in r.json()}


@pytest.fixture(scope="module")
def aig_id(tenants):
    t = tenants.get("AIG Hospital") or tenants.get("AIG Hospitals")
    if not t:
        pytest.fail(f"AIG Hospital tenant missing. Have: {list(tenants)}")
    return t["id"]


# ------------------------------------------------- collector config (unit level)
class TestCollectorConfig:
    def test_ddg_backends_duckduckgo_first(self):
        import collectors
        assert collectors.DDG_BACKENDS[0] == "duckduckgo", collectors.DDG_BACKENDS
        for b in ["bing", "google", "brave", "yahoo", "mullvad_google"]:
            assert b in collectors.DDG_BACKENDS, f"{b} missing from DDG_BACKENDS"

    def test_dork_targets_expanded_13_platforms(self):
        import collectors
        expected = {"Instagram", "Facebook", "X", "Twitter", "YouTube", "LinkedIn",
                    "TikTok", "Threads", "Pinterest", "Telegram", "Reddit",
                    "Pastebin", "Scribd"}
        assert expected == set(collectors.DORK_TARGETS), \
            f"DORK_TARGETS mismatch: {sorted(collectors.DORK_TARGETS)}"
        assert len(collectors.DORK_TARGETS) == 13


# ------------------------------------------------- run endpoint + guard
class TestRunNowGuard:
    state = {}

    def test_run_returns_fast(self, admin, aig_id):
        TestRunNowGuard.state["log_offset"] = _read_log_size()
        t0 = time.time()
        r = admin.post(f"{API}/tenants/{aig_id}/run?collector=search_dork", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        body = r.json()
        assert body.get("ok") is True, body
        assert (body.get("tenant") or "").startswith("AIG Hospital"), body
        assert elapsed < 5, f"run endpoint took {elapsed:.1f}s (should return immediately)"
        TestRunNowGuard.state["started"] = body.get("message") == "Monitoring run started"

    def test_overlapping_run_is_guarded(self, admin, aig_id):
        if not TestRunNowGuard.state.get("started"):
            pytest.skip("first run did not start (already in flight)")
        t0 = time.time()
        r = admin.post(f"{API}/tenants/{aig_id}/run?collector=search_dork", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        body = r.json()
        assert body.get("ok") is True, body
        assert body.get("message") == "A scan is already running for this tenant", body
        assert elapsed < 5, f"guarded run took {elapsed:.1f}s"

    def test_running_row_has_display_name(self, admin, aig_id):
        r = admin.get(f"{API}/monitoring-health", params={"tenant_id": aig_id}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        row = next((x for x in r.json() if x.get("collector_key") == "search_dork"), None)
        assert row is not None, "no search_dork row in monitoring-health"
        assert row.get("collector") == "Search/Dorking", row

    def test_health_degraded_with_message_after_run(self, admin, aig_id):
        row, deadline = None, time.time() + 330
        while time.time() < deadline:
            r = admin.get(f"{API}/monitoring-health", params={"tenant_id": aig_id}, timeout=60)
            assert r.status_code == 200, r.text[:300]
            row = next((x for x in r.json() if x.get("collector_key") == "search_dork"), None)
            if row and row.get("status") not in (None, "running", "queued"):
                break
            time.sleep(10)
        assert row is not None, "no search_dork row"
        assert row.get("status") != "running", "run did not finish within 330s"
        assert row.get("status") in ("healthy", "degraded"), row
        if row["status"] == "degraded":
            err = row.get("error") or ""
            assert len(err) > 20, f"degraded row must carry an explanatory error, got: {err!r}"
            low = err.lower()
            assert any(k in low for k in ["search engine", "blocked", "no results",
                                          "brand-relevant", "datacenter",
                                          "monthly request limit"]), err
        assert isinstance(row.get("items_found"), int)
        assert isinstance(row.get("duration_ms"), int)
        TestRunNowGuard.state["duration_ms"] = row.get("duration_ms")

    def test_no_traceback_in_backend_log_during_run(self):
        offset = TestRunNowGuard.state.get("log_offset")
        if offset is None:
            pytest.skip("log offset not captured")
        new = _new_log_text(offset)
        bad = [l for l in new.splitlines()
               if "Traceback" in l or "Internal Server Error" in l
               or "Task exception was never retrieved" in l]
        assert not bad, f"new backend errors during run: {bad[-5:]}"

    def test_guard_released_after_completion(self, admin, aig_id):
        # once the scan is done, a fresh run must be accepted again
        r = admin.post(f"{API}/tenants/{aig_id}/run?collector=search_dork", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("message") == "Monitoring run started", r.json()

    def test_run_unknown_tenant_404(self, admin):
        r = admin.post(f"{API}/tenants/does-not-exist/run?collector=search_dork", timeout=30)
        assert r.status_code == 404, f"{r.status_code} {r.text[:200]}"

    def test_run_forbidden_for_viewer(self, viewer, aig_id):
        r = viewer.post(f"{API}/tenants/{aig_id}/run?collector=search_dork", timeout=30)
        assert r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}"
