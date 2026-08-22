"""
Focused Backend Test for Welspun Tenant Bug Fix
Tests that welspun tenant (TEN-0004) has findings and APIs return correct data.
"""
import requests
import sys
import json

BASE_URL = "https://brand-shield-admin.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@brandshield.io"
ADMIN_PASSWORD = "Admin@123"

def log(msg, level="INFO"):
    prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
    print(f"{prefix.get(level, '•')} {msg}")

def main():
    log("="*70)
    log("WELSPUN TENANT BUG FIX - BACKEND API TESTS")
    log("="*70)
    
    # Login as Super Admin
    log("\n[1] Logging in as Super Admin...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code != 200:
        log(f"Login failed: {resp.status_code} {resp.text}", "FAIL")
        return 1
    
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    log("Login successful", "PASS")
    
    # Get all tenants and find welspun
    log("\n[2] Finding welspun tenant (TEN-0004)...")
    resp = requests.get(f"{BASE_URL}/tenants", headers=headers)
    if resp.status_code != 200:
        log(f"Get tenants failed: {resp.status_code}", "FAIL")
        return 1
    
    tenants = resp.json()
    welspun = next((t for t in tenants if t.get("tenant_id") == "TEN-0004" or t.get("name", "").lower() == "welspun"), None)
    
    if not welspun:
        log("Welspun tenant (TEN-0004) not found!", "FAIL")
        log(f"Available tenants: {[t.get('name') for t in tenants]}", "INFO")
        return 1
    
    welspun_id = welspun["id"]
    log(f"Found welspun tenant: {welspun['name']} (ID: {welspun_id}, tenant_id: {welspun.get('tenant_id')})", "PASS")
    
    # Test GET /api/findings?tenant_id=<welspun id>
    log(f"\n[3] Testing GET /api/findings?tenant_id={welspun_id}...")
    resp = requests.get(f"{BASE_URL}/findings", headers=headers, params={"tenant_id": welspun_id, "page_size": 50})
    if resp.status_code != 200:
        log(f"Get findings failed: {resp.status_code} {resp.text}", "FAIL")
        return 1
    
    findings_data = resp.json()
    total_findings = findings_data.get("total", 0)
    items = findings_data.get("items", [])
    
    log(f"Total findings for welspun: {total_findings}", "INFO")
    log(f"Items returned: {len(items)}", "INFO")
    
    if total_findings == 0:
        log("CRITICAL: Welspun has 0 findings! Expected ~29+", "FAIL")
        return 1
    elif total_findings < 20:
        log(f"WARNING: Welspun has only {total_findings} findings, expected ~29+", "WARN")
    else:
        log(f"Welspun has {total_findings} findings (expected ~29+)", "PASS")
    
    # Check module breakdown
    if items:
        modules = {}
        for item in items:
            mod = item.get("module", "unknown")
            modules[mod] = modules.get(mod, 0) + 1
        log(f"Module breakdown: {modules}", "INFO")
        
        # Expected: fake_website=5, social=23
        fake_website_count = modules.get("fake_website", 0)
        social_count = modules.get("social", 0)
        log(f"  fake_website: {fake_website_count} (expected ~5)", "INFO")
        log(f"  social: {social_count} (expected ~23)", "INFO")
    
    # Test GET /api/dashboard/stats?tenant_id=<welspun id>
    log(f"\n[4] Testing GET /api/dashboard/stats?tenant_id={welspun_id}...")
    resp = requests.get(f"{BASE_URL}/dashboard/stats", headers=headers, params={"tenant_id": welspun_id, "days": 30})
    if resp.status_code != 200:
        log(f"Get dashboard stats failed: {resp.status_code} {resp.text}", "FAIL")
        return 1
    
    stats = resp.json()
    cards = stats.get("cards", {})
    
    log(f"Dashboard stats for welspun:", "INFO")
    log(f"  Total: {cards.get('total', 0)}", "INFO")
    log(f"  Critical: {cards.get('critical', 0)}", "INFO")
    log(f"  High: {cards.get('high', 0)} (expected ~6)", "INFO")
    log(f"  Medium: {cards.get('medium', 0)} (expected ~19)", "INFO")
    log(f"  Low: {cards.get('low', 0)}", "INFO")
    
    if cards.get("total", 0) == 0:
        log("CRITICAL: Dashboard shows 0 total findings for welspun!", "FAIL")
        return 1
    
    if cards.get("high", 0) == 0 and cards.get("medium", 0) == 0:
        log("WARNING: Dashboard shows 0 high and medium findings, expected high=6, medium=19", "WARN")
    else:
        log("Dashboard stats look reasonable", "PASS")
    
    # Test filtering by module
    log(f"\n[5] Testing module-specific queries for welspun...")
    
    # Fake websites
    resp = requests.get(f"{BASE_URL}/findings", headers=headers, params={"tenant_id": welspun_id, "module": "fake_website"})
    if resp.status_code == 200:
        fake_count = resp.json().get("total", 0)
        log(f"  fake_website findings: {fake_count} (expected ~5)", "INFO")
    
    # Social media
    resp = requests.get(f"{BASE_URL}/findings", headers=headers, params={"tenant_id": welspun_id, "module": "social"})
    if resp.status_code == 200:
        social_count = resp.json().get("total", 0)
        log(f"  social findings: {social_count} (expected ~23)", "INFO")
    
    # Test other tenants for comparison
    log(f"\n[6] Testing other tenants for comparison...")
    
    stripe_tenant = next((t for t in tenants if "Stripe" in t.get("name", "")), None)
    if stripe_tenant:
        resp = requests.get(f"{BASE_URL}/findings", headers=headers, params={"tenant_id": stripe_tenant["id"], "page_size": 10})
        if resp.status_code == 200:
            stripe_findings = resp.json().get("total", 0)
            log(f"  Stripe Payments: {stripe_findings} findings", "INFO")
    
    # All tenants
    resp = requests.get(f"{BASE_URL}/findings", headers=headers, params={"page_size": 10})
    if resp.status_code == 200:
        all_findings = resp.json().get("total", 0)
        log(f"  All Tenants: {all_findings} findings", "INFO")
    
    log("\n" + "="*70)
    log("BACKEND TESTS COMPLETED SUCCESSFULLY", "PASS")
    log("="*70)
    
    # Save results
    results = {
        "welspun_tenant_id": welspun_id,
        "welspun_tenant_code": welspun.get("tenant_id"),
        "total_findings": total_findings,
        "dashboard_stats": cards,
        "module_breakdown": modules if items else {},
        "status": "PASS" if total_findings > 0 else "FAIL"
    }
    
    with open("/app/backend/welspun_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    log(f"\n📄 Results saved to /app/backend/welspun_test_results.json")
    
    return 0 if total_findings > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
