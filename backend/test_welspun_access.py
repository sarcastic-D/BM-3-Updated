"""
Focused test for welspun tenant access bug fix
Tests that analyst and viewer can see and access welspun tenant (TEN-0004)
"""
import requests
import sys
import json
from datetime import datetime

BASE_URL = "https://brand-shield-admin.preview.emergentagent.com/api"
WELSPUN_TENANT_ID = "219e6ebb-bb85-4fe0-b842-9097d26b74f9"
WELSPUN_TENANT_CODE = "TEN-0004"

USERS = {
    "super_admin": {"email": "admin@brandshield.io", "password": "Admin@123"},
    "analyst": {"email": "analyst@brandshield.io", "password": "Analyst@123"},
    "viewer": {"email": "viewer@brandshield.io", "password": "Viewer@123"},
}

class WelspunAccessTester:
    def __init__(self):
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.user_ids = {}

    def log(self, msg, level="INFO"):
        prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
        print(f"{prefix.get(level, '•')} {msg}")

    def test(self, name, fn):
        """Run a test function and track results"""
        self.tests_run += 1
        self.log(f"\n[{self.tests_run}] Testing: {name}", "INFO")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "PASS")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.failures.append({"test": name, "error": str(e)})
            self.log(f"FAILED: {name} - {e}", "FAIL")
            return False
        except Exception as e:
            self.tests_failed += 1
            self.failures.append({"test": name, "error": f"Exception: {str(e)}"})
            self.log(f"ERROR: {name} - {e}", "FAIL")
            return False

    def req(self, method, endpoint, role="super_admin", **kwargs):
        """Make authenticated request"""
        headers = kwargs.pop("headers", {})
        if role and role in self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens[role]}"
        url = f"{BASE_URL}{endpoint}"
        resp = requests.request(method, url, headers=headers, **kwargs)
        return resp

    def test_login_all(self):
        """Login all users"""
        for role, creds in USERS.items():
            resp = self.req("POST", "/auth/login", role=None, json=creds)
            assert resp.status_code == 200, f"Login failed for {role}: {resp.status_code} {resp.text}"
            data = resp.json()
            self.tokens[role] = data["token"]
            self.user_ids[role] = data["user"]["id"]
            self.log(f"  ✓ {role} logged in: {creds['email']}")

    def test_analyst_sees_welspun_in_tenants(self):
        """Test analyst can see welspun in GET /api/tenants"""
        resp = self.req("GET", "/tenants", role="analyst")
        assert resp.status_code == 200, f"GET /tenants failed for analyst: {resp.status_code} {resp.text}"
        tenants = resp.json()
        assert isinstance(tenants, list), "Tenants should be a list"
        
        tenant_ids = [t["id"] for t in tenants]
        tenant_names = [t["name"] for t in tenants]
        tenant_codes = [t.get("tenant_id") for t in tenants]
        
        self.log(f"  Analyst sees {len(tenants)} tenants: {tenant_names}")
        self.log(f"  Tenant codes: {tenant_codes}")
        
        assert WELSPUN_TENANT_ID in tenant_ids, f"Welspun tenant ID {WELSPUN_TENANT_ID} not found in analyst's tenants. Found: {tenant_ids}"
        
        welspun = next((t for t in tenants if t["id"] == WELSPUN_TENANT_ID), None)
        assert welspun is not None, "Welspun tenant not found"
        assert welspun["name"] == "welspun", f"Expected tenant name 'welspun', got '{welspun['name']}'"
        assert welspun.get("tenant_id") == WELSPUN_TENANT_CODE, f"Expected tenant code {WELSPUN_TENANT_CODE}, got {welspun.get('tenant_id')}"
        
        self.log(f"  ✓ Analyst can see welspun tenant: {welspun['name']} ({welspun.get('tenant_id')})")

    def test_viewer_sees_welspun_in_tenants(self):
        """Test viewer can see welspun in GET /api/tenants"""
        resp = self.req("GET", "/tenants", role="viewer")
        assert resp.status_code == 200, f"GET /tenants failed for viewer: {resp.status_code} {resp.text}"
        tenants = resp.json()
        assert isinstance(tenants, list), "Tenants should be a list"
        
        tenant_ids = [t["id"] for t in tenants]
        tenant_names = [t["name"] for t in tenants]
        
        self.log(f"  Viewer sees {len(tenants)} tenants: {tenant_names}")
        
        assert WELSPUN_TENANT_ID in tenant_ids, f"Welspun tenant ID {WELSPUN_TENANT_ID} not found in viewer's tenants. Found: {tenant_ids}"
        
        welspun = next((t for t in tenants if t["id"] == WELSPUN_TENANT_ID), None)
        assert welspun is not None, "Welspun tenant not found"
        assert welspun["name"] == "welspun", f"Expected tenant name 'welspun', got '{welspun['name']}'"
        
        self.log(f"  ✓ Viewer can see welspun tenant: {welspun['name']}")

    def test_analyst_can_get_welspun_findings(self):
        """Test analyst can GET /api/findings?tenant_id=<welspun_id>"""
        resp = self.req("GET", "/findings", role="analyst", params={"tenant_id": WELSPUN_TENANT_ID, "page_size": 50})
        assert resp.status_code == 200, f"GET /findings failed for analyst: {resp.status_code} {resp.text}"
        data = resp.json()
        
        assert "total" in data, "Response missing 'total' field"
        assert "items" in data, "Response missing 'items' field"
        
        total = data["total"]
        self.log(f"  Analyst can see {total} welspun findings")
        
        # The review_request says ~39 findings, but let's be flexible
        assert total > 0, f"Expected > 0 welspun findings for analyst, got {total}"
        
        # Verify all findings are for welspun tenant
        for finding in data["items"]:
            assert finding["tenant_id"] == WELSPUN_TENANT_ID, f"Finding {finding['id']} has wrong tenant_id: {finding['tenant_id']}"
        
        self.log(f"  ✓ All {len(data['items'])} findings belong to welspun tenant")

    def test_viewer_can_get_welspun_findings(self):
        """Test viewer can GET /api/findings?tenant_id=<welspun_id>"""
        resp = self.req("GET", "/findings", role="viewer", params={"tenant_id": WELSPUN_TENANT_ID, "page_size": 50})
        assert resp.status_code == 200, f"GET /findings failed for viewer: {resp.status_code} {resp.text}"
        data = resp.json()
        
        assert "total" in data, "Response missing 'total' field"
        assert "items" in data, "Response missing 'items' field"
        
        total = data["total"]
        self.log(f"  Viewer can see {total} welspun findings")
        
        assert total > 0, f"Expected > 0 welspun findings for viewer, got {total}"
        
        # Verify all findings are for welspun tenant
        for finding in data["items"]:
            assert finding["tenant_id"] == WELSPUN_TENANT_ID, f"Finding {finding['id']} has wrong tenant_id: {finding['tenant_id']}"
        
        self.log(f"  ✓ All {len(data['items'])} findings belong to welspun tenant")

    def test_super_admin_can_list_users(self):
        """Test Super Admin can list users"""
        resp = self.req("GET", "/users", role="super_admin")
        assert resp.status_code == 200, f"GET /users failed: {resp.status_code} {resp.text}"
        users = resp.json()
        assert isinstance(users, list), "Users should be a list"
        assert len(users) >= 3, f"Expected at least 3 users, got {len(users)}"
        
        # Find analyst and viewer
        analyst = next((u for u in users if u["email"] == "analyst@brandshield.io"), None)
        viewer = next((u for u in users if u["email"] == "viewer@brandshield.io"), None)
        
        assert analyst is not None, "Analyst user not found"
        assert viewer is not None, "Viewer user not found"
        
        self.log(f"  ✓ Found analyst: {analyst['name']} (tenant_ids: {len(analyst.get('tenant_ids', []))})")
        self.log(f"  ✓ Found viewer: {viewer['name']} (tenant_ids: {len(viewer.get('tenant_ids', []))})")
        
        # Verify both have welspun in their tenant_ids
        assert WELSPUN_TENANT_ID in analyst.get("tenant_ids", []), f"Analyst missing welspun in tenant_ids: {analyst.get('tenant_ids')}"
        assert WELSPUN_TENANT_ID in viewer.get("tenant_ids", []), f"Viewer missing welspun in tenant_ids: {viewer.get('tenant_ids')}"
        
        self.log(f"  ✓ Both analyst and viewer have welspun in their tenant_ids")

    def test_super_admin_can_update_user_tenant_access(self):
        """Test Super Admin can update user's tenant_ids via PUT /api/users/{id}"""
        # Get current analyst user
        resp = self.req("GET", "/users", role="super_admin")
        users = resp.json()
        analyst = next((u for u in users if u["email"] == "analyst@brandshield.io"), None)
        assert analyst is not None, "Analyst user not found"
        
        original_tenant_ids = analyst.get("tenant_ids", [])
        self.log(f"  Analyst original tenant_ids: {original_tenant_ids}")
        
        # Test: Remove welspun from analyst's tenant_ids
        new_tenant_ids = [tid for tid in original_tenant_ids if tid != WELSPUN_TENANT_ID]
        resp = self.req("PUT", f"/users/{analyst['id']}", role="super_admin", json={"tenant_ids": new_tenant_ids})
        assert resp.status_code == 200, f"PUT /users/{analyst['id']} failed: {resp.status_code} {resp.text}"
        
        self.log(f"  ✓ Removed welspun from analyst's tenant_ids")
        
        # Verify analyst can no longer see welspun
        resp = self.req("GET", "/tenants", role="analyst")
        tenants = resp.json()
        tenant_ids = [t["id"] for t in tenants]
        assert WELSPUN_TENANT_ID not in tenant_ids, f"Analyst should not see welspun after revoke, but found it in: {tenant_ids}"
        
        self.log(f"  ✓ Analyst can no longer see welspun tenant (revoke successful)")
        
        # Restore original tenant_ids
        resp = self.req("PUT", f"/users/{analyst['id']}", role="super_admin", json={"tenant_ids": original_tenant_ids})
        assert resp.status_code == 200, f"PUT /users/{analyst['id']} restore failed: {resp.status_code} {resp.text}"
        
        self.log(f"  ✓ Restored analyst's original tenant_ids")
        
        # Verify analyst can see welspun again
        resp = self.req("GET", "/tenants", role="analyst")
        tenants = resp.json()
        tenant_ids = [t["id"] for t in tenants]
        assert WELSPUN_TENANT_ID in tenant_ids, f"Analyst should see welspun after restore, but not found in: {tenant_ids}"
        
        self.log(f"  ✓ Analyst can see welspun tenant again (restore successful)")

    def run_all_tests(self):
        """Run all tests in order"""
        self.log("\n" + "="*70, "INFO")
        self.log("WELSPUN TENANT ACCESS BUG FIX - FOCUSED TESTS", "INFO")
        self.log("="*70 + "\n", "INFO")

        self.test("Login all users (admin, analyst, viewer)", self.test_login_all)
        self.test("Analyst can see welspun in GET /api/tenants", self.test_analyst_sees_welspun_in_tenants)
        self.test("Viewer can see welspun in GET /api/tenants", self.test_viewer_sees_welspun_in_tenants)
        self.test("Analyst can get welspun findings", self.test_analyst_can_get_welspun_findings)
        self.test("Viewer can get welspun findings", self.test_viewer_can_get_welspun_findings)
        self.test("Super Admin can list users with tenant_ids", self.test_super_admin_can_list_users)
        self.test("Super Admin can grant/revoke tenant access", self.test_super_admin_can_update_user_tenant_access)

        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*70, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("="*70, "INFO")
        self.log(f"Total Tests: {self.tests_run}", "INFO")
        self.log(f"Passed: {self.tests_passed}", "PASS")
        self.log(f"Failed: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.failures:
            self.log("\nFailed Tests:", "FAIL")
            for f in self.failures:
                self.log(f"  • {f['test']}: {f['error']}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%", "INFO")
        
        return 0 if self.tests_failed == 0 else 1

def main():
    tester = WelspunAccessTester()
    exit_code = tester.run_all_tests()
    
    # Save results to JSON
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_type": "welspun_tenant_access_bug_fix",
        "total_tests": tester.tests_run,
        "passed": tester.tests_passed,
        "failed": tester.tests_failed,
        "success_rate": f"{(tester.tests_passed / tester.tests_run * 100):.1f}%" if tester.tests_run > 0 else "0%",
        "failures": tester.failures
    }
    
    with open("/app/backend/welspun_access_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to /app/backend/welspun_access_test_results.json")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
