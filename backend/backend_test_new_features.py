import requests
import sys
import time
from datetime import datetime

class BrandMonitoringTester:
    def __init__(self, base_url="https://brand-shield-admin.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = None
        self.analyst_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.welspun_tenant_id = None
        self.test_finding_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
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

    def test_login(self, email, password, role_name):
        """Test login and get token"""
        success, response = self.run_test(
            f"Login as {role_name}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'token' in response:
            print(f"   Token obtained for {role_name}")
            return response['token']
        return None

    def test_analyze_domain(self):
        """Test GET /api/tools/analyze-domain?domain=welspun.com"""
        success, response = self.run_test(
            "Auto-detect: Analyze Domain (welspun.com)",
            "GET",
            "tools/analyze-domain",
            200,
            token=self.admin_token,
            params={"domain": "welspun.com"}
        )
        if success:
            brand_names = response.get('brand_names', [])
            products = response.get('products', [])
            print(f"   Brand names: {brand_names}")
            print(f"   Products count: {len(products)}")
            print(f"   Products: {products[:5]}")
            
            # Verify Welspun is in brand names
            if 'Welspun' in brand_names or any('welspun' in b.lower() for b in brand_names):
                print(f"   ✓ 'Welspun' found in brand names")
            else:
                print(f"   ⚠️  'Welspun' not found in brand names")
            
            # Verify products list is not empty
            if len(products) > 0:
                print(f"   ✓ Products list is non-empty")
            else:
                print(f"   ⚠️  Products list is empty")
                
        return success

    def test_get_tenants(self):
        """Get all tenants and find Welspun"""
        success, response = self.run_test(
            "Get Tenants (find Welspun)",
            "GET",
            "tenants",
            200,
            token=self.admin_token
        )
        if success:
            for tenant in response:
                if tenant.get('name') == 'Welspun':
                    self.welspun_tenant_id = tenant.get('id')
                    print(f"   Found Welspun tenant ID: {self.welspun_tenant_id}")
                    print(f"   Domain: {tenant.get('primary_domain')}")
                    print(f"   Findings count: {tenant.get('findings_count', 0)}")
                    break
            if not self.welspun_tenant_id:
                print(f"   ⚠️  Welspun tenant not found")
        return success

    def test_stricter_matching_fake_website(self):
        """Test stricter matching for fake_website module"""
        if not self.welspun_tenant_id:
            print("⚠️  Skipping - Welspun tenant ID not found")
            return False
            
        success, response = self.run_test(
            "Stricter Matching: Fake Website Findings",
            "GET",
            "findings",
            200,
            token=self.admin_token,
            params={"tenant_id": self.welspun_tenant_id, "module": "fake_website"}
        )
        if success:
            findings = response.get('items', [])
            print(f"   Total fake_website findings: {len(findings)}")
            
            # Check if findings are close look-alikes
            close_lookalikes = []
            unrelated = []
            for f in findings[:10]:  # Check first 10
                domain = f.get('domain', '')
                title = f.get('title', '')
                print(f"   - {title} (domain: {domain})")
                
                # Check if it's a close look-alike of 'welspun'
                if 'welspun' in domain.lower() or 'welsun' in domain.lower() or 'wilspun' in domain.lower():
                    close_lookalikes.append(domain)
                elif 'wesley' in domain.lower() or len(domain.split('.')[0]) < 4:
                    unrelated.append(domain)
            
            print(f"   Close look-alikes: {len(close_lookalikes)}")
            print(f"   Potentially unrelated: {len(unrelated)}")
            
            if len(unrelated) > 0:
                print(f"   ⚠️  Found potentially unrelated domains: {unrelated}")
            else:
                print(f"   ✓ All checked domains appear to be close look-alikes")
                
        return success

    def test_stricter_matching_social(self):
        """Test stricter matching for social module"""
        if not self.welspun_tenant_id:
            print("⚠️  Skipping - Welspun tenant ID not found")
            return False
            
        success, response = self.run_test(
            "Stricter Matching: Social Findings",
            "GET",
            "findings",
            200,
            token=self.admin_token,
            params={"tenant_id": self.welspun_tenant_id, "module": "social"}
        )
        if success:
            findings = response.get('items', [])
            print(f"   Total social findings: {len(findings)}")
            
            # Check if findings reference Welspun brand
            brand_references = 0
            for f in findings[:10]:  # Check first 10
                title = f.get('title', '').lower()
                snippet = f.get('entities', {}).get('description', '').lower()
                url = f.get('url', '').lower()
                
                if 'welspun' in title or 'welspun' in snippet or 'welspun' in url:
                    brand_references += 1
                    print(f"   ✓ {f.get('title', '')[:60]} - references Welspun")
                else:
                    print(f"   ? {f.get('title', '')[:60]} - brand reference unclear")
            
            print(f"   Brand references found: {brand_references}/{min(len(findings), 10)}")
                
        return success

    def test_social_page_data(self):
        """Test that social findings have new fields: account_name, username, description, profile_url"""
        if not self.welspun_tenant_id:
            print("⚠️  Skipping - Welspun tenant ID not found")
            return False
            
        success, response = self.run_test(
            "Social Data: Check New Fields",
            "GET",
            "findings",
            200,
            token=self.admin_token,
            params={"tenant_id": self.welspun_tenant_id, "module": "social", "page_size": 5}
        )
        if success:
            findings = response.get('items', [])
            print(f"   Checking {len(findings)} social findings for new fields...")
            
            for f in findings:
                entities = f.get('entities', {})
                account_name = entities.get('account_name')
                username = entities.get('username')
                description = entities.get('description')
                profile_url = entities.get('profile_url')
                
                print(f"\n   Finding: {f.get('title', '')[:50]}")
                print(f"     - Account Name: {account_name[:50] if account_name else 'MISSING'}")
                print(f"     - Username: {username[:50] if username else 'MISSING'}")
                print(f"     - Description: {description[:50] if description else 'MISSING'}...")
                print(f"     - Profile URL: {profile_url[:60] if profile_url else 'MISSING'}")
                
                # Store first finding ID for screenshot test
                if not self.test_finding_id and f.get('id'):
                    self.test_finding_id = f.get('id')
                    print(f"     - Stored finding ID for screenshot test: {self.test_finding_id}")
                
        return success

    def test_screenshot_capture(self):
        """Test POST /api/findings/{id}/screenshot"""
        if not self.test_finding_id:
            print("⚠️  Skipping - No finding ID available for screenshot test")
            return False
            
        print(f"   Note: Screenshot capture takes ~10s, please wait...")
        success, response = self.run_test(
            "Screenshot: Capture Finding Screenshot",
            "POST",
            f"findings/{self.test_finding_id}/screenshot",
            200,
            token=self.admin_token
        )
        if success:
            screenshot_url = response.get('screenshot_url')
            print(f"   Screenshot URL: {screenshot_url}")
            
            if screenshot_url:
                # Try to fetch the screenshot
                full_url = f"{self.base_url}{screenshot_url}"
                print(f"   Verifying screenshot is accessible at: {full_url}")
                try:
                    img_response = requests.get(full_url)
                    if img_response.status_code == 200:
                        print(f"   ✓ Screenshot accessible (size: {len(img_response.content)} bytes)")
                        if img_response.headers.get('content-type', '').startswith('image/'):
                            print(f"   ✓ Content-Type is image: {img_response.headers.get('content-type')}")
                        else:
                            print(f"   ⚠️  Content-Type is not image: {img_response.headers.get('content-type')}")
                    else:
                        print(f"   ⚠️  Screenshot not accessible: {img_response.status_code}")
                except Exception as e:
                    print(f"   ⚠️  Error fetching screenshot: {str(e)}")
            else:
                print(f"   ⚠️  No screenshot_url in response")
                
        return success

    def test_dashboard_loads(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test(
            "Regression: Dashboard Stats",
            "GET",
            "dashboard/stats",
            200,
            token=self.admin_token
        )
        if success:
            cards = response.get('cards', {})
            print(f"   Total findings: {cards.get('total', 0)}")
            print(f"   Critical: {cards.get('critical', 0)}, High: {cards.get('high', 0)}")
        return success

def main():
    print("=" * 70)
    print("BRAND MONITORING - NEW FEATURES TEST SUITE")
    print("Testing: Auto-detect, Stricter Matching, Social Data, Screenshots")
    print("=" * 70)
    
    tester = BrandMonitoringTester()

    # Step 1: Authentication
    print("\n" + "=" * 70)
    print("STEP 1: AUTHENTICATION")
    print("=" * 70)
    
    tester.admin_token = tester.test_login("admin@brandshield.io", "Admin@123", "Super Admin")
    if not tester.admin_token:
        print("❌ Super Admin login failed, stopping tests")
        return 1

    tester.analyst_token = tester.test_login("analyst@brandshield.io", "Analyst@123", "Analyst")

    # Step 2: Auto-detect feature
    print("\n" + "=" * 70)
    print("STEP 2: AUTO-DETECT FEATURE (Backend)")
    print("=" * 70)
    tester.test_analyze_domain()

    # Step 3: Get Welspun tenant
    print("\n" + "=" * 70)
    print("STEP 3: FIND WELSPUN TENANT")
    print("=" * 70)
    tester.test_get_tenants()

    # Step 4: Stricter matching tests
    print("\n" + "=" * 70)
    print("STEP 4: STRICTER MATCHING (Data Quality)")
    print("=" * 70)
    tester.test_stricter_matching_fake_website()
    tester.test_stricter_matching_social()

    # Step 5: Social data fields
    print("\n" + "=" * 70)
    print("STEP 5: SOCIAL DATA (New Fields)")
    print("=" * 70)
    tester.test_social_page_data()

    # Step 6: Screenshot capture
    print("\n" + "=" * 70)
    print("STEP 6: SCREENSHOT CAPTURE")
    print("=" * 70)
    tester.test_screenshot_capture()

    # Step 7: Regression - Dashboard
    print("\n" + "=" * 70)
    print("STEP 7: REGRESSION TESTS")
    print("=" * 70)
    tester.test_dashboard_loads()

    # Print results
    print("\n" + "=" * 70)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    print("=" * 70)
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
