import os
import requests
import pytest
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "super_admin": ("admin@brandshield.io", "Admin@123"),
    "tenant_admin": ("tadmin@brandshield.io", "Tenant@123"),
    "analyst": ("analyst@brandshield.io", "Analyst@123"),
    "viewer": ("viewer@brandshield.io", "Viewer@123"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"Login failed for {email}: {r.status_code} {r.text[:300]}")
    tok = r.json().get("token")
    if not tok:
        pytest.fail(f"No token in login response for {email}")
    return tok


def client_for(role):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {_login(*CREDS[role])}"})
    return s


@pytest.fixture(scope="session")
def api_base():
    return API


@pytest.fixture(scope="session")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin():
    return client_for("super_admin")


@pytest.fixture(scope="session")
def tadmin():
    return client_for("tenant_admin")


@pytest.fixture(scope="session")
def analyst():
    return client_for("analyst")


@pytest.fixture(scope="session")
def viewer():
    return client_for("viewer")


@pytest.fixture(scope="session")
def tenant_ids(admin):
    r = admin.get(f"{API}/tenants", timeout=60)
    assert r.status_code == 200, r.text[:300]
    return [t["id"] for t in r.json()]
