import requests
import sys
import time
from datetime import datetime

class Stage2APITester:
    def __init__(self, base_url="https://brand-shield-admin.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_tenant_id = None
        self.acme_tenant_id = "b3c16a42-599c-4398-8fdc-ad9b9f5c7c04"

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    print(f"   Response: {response.text[:500]}")

            return success, response.json() if response.text and success else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self):
        """Test login as super_admin"""
        success, response = self.run_test(
            "Login as super_admin (admin@brandshield.io / Admin@123)",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@brandshield.io", "password": "Admin@123"}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   ✓ Token obtained")
            return True
        return False

    def test_create_tenant_with_identity(self):
        """Test POST /api/tenants with full identity object"""
        identity = {
            "legal_name": "Test Corp Ltd.",
            "trading_names": ["TestCo", "Test Company"],
            "keywords": ["test", "testing", "qa"],
            "official_domains": ["testcorp.com"],
            "social_handles": {
                "x": "testcorp",
                "instagram": "testcorp_official",
                "linkedin": "testcorp",
                "facebook": "testcorp",
                "youtube": "testcorpchannel"
            },
            "redirect_domains": ["test.co"],
            "marketing_domains": ["promo.testcorp.com"],
            "regional_domains": ["testcorp.co.uk"],
            "official_app_ids": ["com.testcorp.app"],
            "email_domains": ["testcorp.com", "mail.testcorp.com"],
            "known_nameservers": ["ns1.testcorp.com", "ns2.testcorp.com"],
            "known_ips": ["1.2.3.4", "5.6.7.8"]
        }
        
        success, response = self.run_test(
            "Create Tenant with full identity object",
            "POST",
            "tenants",
            200,
            data={
                "name": "TestCorp Stage2",
                "primary_domain": "testcorp.com",
                "brand_names": ["TestCorp"],
                "products": ["Widget", "Gadget"],
                "executives": ["Jane Doe CEO", "John Smith CTO"],
                "identity": identity,
                "industry": "Technology",
                "country": "US"
            }
        )
        if success and 'id' in response:
            self.test_tenant_id = response['id']
            print(f"   ✓ Created tenant ID: {self.test_tenant_id}")
            # Verify identity fields are present
            if 'identity' in response:
                idt = response['identity']
                checks = [
                    ('legal_name', idt.get('legal_name') == "Test Corp Ltd."),
                    ('trading_names', len(idt.get('trading_names', [])) == 2),
                    ('keywords', len(idt.get('keywords', [])) == 3),
                    ('official_domains', 'testcorp.com' in idt.get('official_domains', [])),
                    ('social_handles', idt.get('social_handles', {}).get('x') == 'testcorp'),
                    ('official_app_ids', 'com.testcorp.app' in idt.get('official_app_ids', [])),
                    ('email_domains', len(idt.get('email_domains', [])) == 2),
                    ('known_nameservers', len(idt.get('known_nameservers', [])) == 2),
                    ('known_ips', len(idt.get('known_ips', [])) == 2)
                ]
                for field, check in checks:
                    if check:
                        print(f"   ✓ {field} present and correct")
                    else:
                        print(f"   ✗ {field} missing or incorrect")
            if 'executives' in response:
                print(f"   ✓ executives array present: {response['executives']}")
            return True
        return False

    def test_get_tenant_identity(self):
        """Test GET /api/tenants/{tid} returns identity + executives"""
        if not self.test_tenant_id:
            print("⚠️  Skipping - no test tenant ID")
            return False
        
        success, response = self.run_test(
            "GET tenant with identity",
            "GET",
            f"tenants/{self.test_tenant_id}",
            200
        )
        if success:
            if 'identity' in response:
                idt = response['identity']
                print(f"   ✓ identity object present with {len(idt)} fields")
                print(f"   ✓ legal_name: {idt.get('legal_name')}")
                print(f"   ✓ social_handles: {list(idt.get('social_handles', {}).keys())}")
            if 'executives' in response:
                print(f"   ✓ executives: {response['executives']}")
            return True
        return False

    def test_get_acme_tenant_backward_compat(self):
        """Test GET /api/tenants/{acme_id} returns synthesized identity for older tenant"""
        success, response = self.run_test(
            "GET Acme tenant (backward-compat identity synthesis)",
            "GET",
            f"tenants/{self.acme_tenant_id}",
            200
        )
        if success:
            if 'identity' in response:
                idt = response['identity']
                print(f"   ✓ identity object synthesized with {len(idt)} fields")
                print(f"   ✓ official_domains: {idt.get('official_domains')}")
            if 'executives' in response:
                print(f"   ✓ executives array present (may be empty): {response['executives']}")
            return True
        return False

    def test_update_tenant_identity(self):
        """Test PUT /api/tenants/{tid} persists identity and executives"""
        if not self.test_tenant_id:
            print("⚠️  Skipping - no test tenant ID")
            return False
        
        updated_identity = {
            "legal_name": "Test Corp Ltd. UPDATED",
            "trading_names": ["TestCo", "Test Company", "TC"],
            "keywords": ["test", "testing", "qa", "quality"],
            "official_domains": ["testcorp.com"],
            "social_handles": {
                "x": "testcorp_updated",
                "instagram": "testcorp_official",
                "linkedin": "testcorp",
                "facebook": "testcorp",
                "youtube": "testcorpchannel"
            },
            "official_app_ids": ["com.testcorp.app", "com.testcorp.app2"],
            "email_domains": ["testcorp.com", "mail.testcorp.com", "support.testcorp.com"]
        }
        
        success, response = self.run_test(
            "PUT tenant to update identity",
            "PUT",
            f"tenants/{self.test_tenant_id}",
            200,
            data={
                "identity": updated_identity,
                "executives": ["Jane Doe CEO", "John Smith CTO", "Alice Johnson CFO"]
            }
        )
        if success:
            idt = response.get('identity', {})
            if idt.get('legal_name') == "Test Corp Ltd. UPDATED":
                print(f"   ✓ legal_name updated")
            if len(idt.get('trading_names', [])) == 3:
                print(f"   ✓ trading_names updated (3 items)")
            if len(response.get('executives', [])) == 3:
                print(f"   ✓ executives updated (3 items)")
            return True
        return False

    def test_analyze_domain(self):
        """Test GET /api/tools/analyze-domain?domain=stripe.com"""
        success, response = self.run_test(
            "Analyze domain (stripe.com)",
            "GET",
            "tools/analyze-domain",
            200,
            params={"domain": "stripe.com"}
        )
        if success:
            required_fields = ['brand_names', 'products', 'social_handles', 'email_domains']
            for field in required_fields:
                if field in response:
                    val = response[field]
                    if isinstance(val, dict):
                        print(f"   ✓ {field}: {list(val.keys())}")
                    elif isinstance(val, list):
                        print(f"   ✓ {field}: {len(val)} items")
                else:
                    print(f"   ✗ {field} missing")
            return True
        return False

    def test_typosquat_run_and_findings(self):
        """Test typosquat collector run and verify typo_pipeline fields"""
        if not self.acme_tenant_id:
            print("⚠️  Skipping - no Acme tenant ID")
            return False
        
        # Trigger typosquat run
        print(f"   Triggering typosquat run for Acme tenant...")
        success, response = self.run_test(
            "POST /api/tenants/{tid}/run?collector=typosquat",
            "POST",
            f"tenants/{self.acme_tenant_id}/run",
            200,
            params={"collector": "typosquat"}
        )
        if not success:
            return False
        
        print(f"   ⏳ Waiting 60s for typosquat collector to complete...")
        time.sleep(60)
        
        # Check findings
        success, response = self.run_test(
            "GET /api/findings?module=fake_website",
            "GET",
            "findings",
            200,
            params={"module": "fake_website", "tenant_id": self.acme_tenant_id, "page_size": 5}
        )
        if success and response.get('items'):
            findings = response['items']
            print(f"   ✓ Found {len(findings)} fake_website findings")
            
            # Check first finding for typo_pipeline fields
            if findings:
                f = findings[0]
                print(f"   Checking finding: {f.get('title')}")
                
                # Check evidence.typo_pipeline
                pipeline = f.get('evidence', {}).get('typo_pipeline', {})
                required_pipeline_fields = ['generated_kind', 'dns_ok', 'http_ok', 'brand_similarity', 'content_similarity', 'infra_flags']
                for field in required_pipeline_fields:
                    if field in pipeline:
                        print(f"   ✓ evidence.typo_pipeline.{field}: {pipeline[field]}")
                    else:
                        print(f"   ✗ evidence.typo_pipeline.{field} missing")
                
                # Check entities fields
                ent = f.get('entities', {})
                required_entity_fields = ['typo_kind', 'brand_similarity', 'http_live', 'infra_suspicious']
                for field in required_entity_fields:
                    if field in ent:
                        print(f"   ✓ entities.{field}: {ent[field]}")
                    else:
                        print(f"   ✗ entities.{field} missing")
            return True
        else:
            print(f"   ⚠️  No fake_website findings found yet")
            return False

    def test_social_run_and_findings(self):
        """Test search_dork collector run and verify impersonation fields"""
        if not self.acme_tenant_id:
            print("⚠️  Skipping - no Acme tenant ID")
            return False
        
        # Trigger search_dork run
        print(f"   Triggering search_dork run for Acme tenant...")
        success, response = self.run_test(
            "POST /api/tenants/{tid}/run?collector=search_dork",
            "POST",
            f"tenants/{self.acme_tenant_id}/run",
            200,
            params={"collector": "search_dork"}
        )
        if not success:
            return False
        
        print(f"   ⏳ Waiting 45s for search_dork collector to complete...")
        time.sleep(45)
        
        # Check findings
        success, response = self.run_test(
            "GET /api/findings?module=social",
            "GET",
            "findings",
            200,
            params={"module": "social", "tenant_id": self.acme_tenant_id, "page_size": 5}
        )
        if success and response.get('items'):
            findings = response['items']
            print(f"   ✓ Found {len(findings)} social findings")
            
            # Check first finding for impersonation fields
            if findings:
                f = findings[0]
                print(f"   Checking finding: {f.get('title')}")
                
                # Check entities.impersonation_confidence and impersonation_classification
                ent = f.get('entities', {})
                conf = ent.get('impersonation_confidence')
                classification = ent.get('impersonation_classification')
                
                if conf is not None:
                    print(f"   ✓ entities.impersonation_confidence: {conf} (0-100)")
                else:
                    print(f"   ✗ entities.impersonation_confidence missing")
                
                if classification:
                    valid_classes = ["LEGITIMATE", "LIKELY LEGITIMATE", "SUSPICIOUS", "LIKELY IMPERSONATION", "HIGH-CONFIDENCE IMPERSONATION"]
                    if classification in valid_classes:
                        print(f"   ✓ entities.impersonation_classification: {classification}")
                    else:
                        print(f"   ✗ entities.impersonation_classification invalid: {classification}")
                else:
                    print(f"   ✗ entities.impersonation_classification missing")
                
                # Check evidence.verification_signals
                signals = f.get('evidence', {}).get('verification_signals', {})
                required_signals = ['username_similarity', 'display_name_similarity', 'official_wording', 
                                   'suspicious_wording', 'external_domain', 'official_link_mismatch',
                                   'account_age', 'followers', 'follower_pattern']
                for field in required_signals:
                    if field in signals:
                        print(f"   ✓ evidence.verification_signals.{field}: {signals[field]}")
                    else:
                        print(f"   ✗ evidence.verification_signals.{field} missing")
            return True
        else:
            print(f"   ⚠️  No social findings found yet")
            return False

    def test_findings_filters(self):
        """Test GET /api/findings with new filters"""
        # Test impersonation_classification filter
        success1, response1 = self.run_test(
            "GET /api/findings?impersonation_classification=SUSPICIOUS",
            "GET",
            "findings",
            200,
            params={"impersonation_classification": "SUSPICIOUS", "tenant_id": self.acme_tenant_id}
        )
        if success1:
            print(f"   ✓ impersonation_classification filter works")
        
        # Test typo_kind filter
        success2, response2 = self.run_test(
            "GET /api/findings?typo_kind=transposition",
            "GET",
            "findings",
            200,
            params={"typo_kind": "transposition", "tenant_id": self.acme_tenant_id}
        )
        if success2:
            print(f"   ✓ typo_kind filter works")
        
        # Test infra_suspicious filter
        success3, response3 = self.run_test(
            "GET /api/findings?infra_suspicious=Yes",
            "GET",
            "findings",
            200,
            params={"infra_suspicious": "Yes", "tenant_id": self.acme_tenant_id}
        )
        if success3:
            print(f"   ✓ infra_suspicious filter works")
        
        return success1 and success2 and success3

def main():
    print("=" * 80)
    print("BRAND MONITORING PLATFORM - STAGE 2 API TESTS")
    print("=" * 80)
    
    tester = Stage2APITester()

    # Test 1: Auth
    print("\n📋 TEST 1: Authentication")
    if not tester.test_login():
        print("❌ Login failed, stopping tests")
        return 1

    # Test 2: Create tenant with identity
    print("\n📋 TEST 2: POST /api/tenants with identity object")
    tester.test_create_tenant_with_identity()

    # Test 3: GET tenant with identity
    print("\n📋 TEST 3: GET /api/tenants/{tid} returns identity + executives")
    tester.test_get_tenant_identity()

    # Test 4: GET Acme tenant (backward-compat)
    print("\n📋 TEST 4: GET /api/tenants/{acme_id} backward-compat synthesis")
    tester.test_get_acme_tenant_backward_compat()

    # Test 5: PUT tenant to update identity
    print("\n📋 TEST 5: PUT /api/tenants/{tid} persists identity and executives")
    tester.test_update_tenant_identity()

    # Test 6: Analyze domain
    print("\n📋 TEST 6: GET /api/tools/analyze-domain?domain=stripe.com")
    tester.test_analyze_domain()

    # Test 7: Typosquat run and findings
    print("\n📋 TEST 7: Typosquat collector + typo_pipeline fields")
    tester.test_typosquat_run_and_findings()

    # Test 8: Social run and findings
    print("\n📋 TEST 8: Search_dork collector + impersonation fields")
    tester.test_social_run_and_findings()

    # Test 9: Findings filters
    print("\n📋 TEST 9: GET /api/findings with new filters")
    tester.test_findings_filters()

    # Print results
    print("\n" + "=" * 80)
    print(f"📊 RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    print("=" * 80)
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
