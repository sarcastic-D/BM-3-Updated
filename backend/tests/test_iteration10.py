"""Iteration 10: username/entities extraction, screenshot capture, pagination config, regression."""
import os
import re
import sys
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

WELSPUN_TID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"

CREDS = {
    "super_admin": ("admin@brandshield.io", "Admin@123"),
    "tenant_admin": ("tadmin@brandshield.io", "Tenant@123"),
    "analyst": ("analyst@brandshield.io", "Analyst@123"),
    "viewer": ("viewer@brandshield.io", "Viewer@123"),
}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_token():
    return _login(*CREDS["super_admin"])


@pytest.fixture(scope="session")
def admin(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def welspun_social(admin):
    out, page = [], 1
    while True:
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": WELSPUN_TID, "module": "social", "page": page, "page_size": 100},
                      timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        items = d.get("items") or d.get("findings") or []
        out.extend(items)
        total = d.get("total", len(out))
        if len(out) >= total or not items:
            break
        page += 1
    return out


# ----------------------------- ROLE LOGINS -----------------------------------
class TestAuthRoles:
    @pytest.mark.parametrize("role", list(CREDS))
    def test_login_all_roles(self, role):
        email, pwd = CREDS[role]
        tok = _login(email, pwd)
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("role") == role or r.json().get("user", {}).get("role") == role


# --------------------- USERNAME / ENTITY EXTRACTION --------------------------
class TestWelspunEntities:
    def test_total_and_no_duplicate_urls(self, welspun_social):
        assert len(welspun_social) >= 200, f"only {len(welspun_social)} social findings"
        urls = [f["url"] for f in welspun_social]
        dupes = {u for u in urls if urls.count(u) > 1}
        assert not dupes, f"duplicate URLs: {list(dupes)[:5]}"

    def test_every_finding_has_username_and_content_type(self, welspun_social):
        bad = []
        for f in welspun_social:
            e = f.get("entities") or {}
            if not e.get("username"):
                bad.append((f["url"], "missing username"))
            if e.get("content_type") not in ("profile", "post", "video"):
                bad.append((f["url"], f"content_type={e.get('content_type')}"))
        assert not bad, f"{len(bad)} problems e.g. {bad[:8]}"

    def test_username_is_not_raw_last_segment_for_posts(self, welspun_social):
        """For post/video URLs the username must not be the marker segment."""
        markers = {"p", "reel", "reels", "status", "watch", "shorts", "posts", "pulse", "comments", "video"}
        bad = []
        for f in welspun_social:
            e = f.get("entities") or {}
            u = (e.get("username") or "").lower()
            if u in markers:
                bad.append(f["url"])
        assert not bad, f"username is a URL marker for: {bad[:8]}"

    def test_platform_specific_rules(self, welspun_social):
        errs = []
        checked = {"profile": 0, "post": 0, "video": 0}
        for f in welspun_social:
            e = f.get("entities") or {}
            url, plat = f["url"], f.get("platform")
            uname, ctype = e.get("username"), e.get("content_type")
            p = urlparse(url)
            parts = [x for x in p.path.split("/") if x]
            low = [x.lower() for x in parts]
            checked[ctype] = checked.get(ctype, 0) + 1
            if plat == "LinkedIn" and low[:1] and low[0] in ("company", "in", "school") and len(parts) > 1:
                if uname != parts[1]:
                    errs.append(f"LinkedIn {url} -> {uname} (expected {parts[1]})")
                if ctype != "profile":
                    errs.append(f"LinkedIn {url} ctype={ctype}")
            elif plat == "Reddit" and len(parts) >= 2 and low[0] in ("r", "u", "user"):
                exp = ("r/" if low[0] == "r" else "u/") + parts[1]
                if uname != exp:
                    errs.append(f"Reddit {url} -> {uname} (expected {exp})")
            elif plat == "YouTube":
                if low[:1] == ["watch"]:
                    vid = parse_qs(p.query).get("v", [None])[0]
                    if ctype != "video":
                        errs.append(f"YT {url} ctype={ctype}")
                    if vid and uname != vid:
                        errs.append(f"YT {url} -> {uname} (expected {vid})")
                elif low[:1] and low[0] in ("channel", "c", "user") and len(parts) > 1:
                    if uname != parts[1]:
                        errs.append(f"YT {url} -> {uname} (expected {parts[1]})")
            elif plat in ("Instagram", "X", "Twitter", "Facebook", "TikTok", "Threads"):
                if len(parts) == 1 and low[0] not in ("p", "reel", "reels"):
                    if uname.lstrip("@") != parts[0].lstrip("@"):
                        errs.append(f"{plat} {url} -> {uname} (expected {parts[0]})")
                    if ctype != "profile":
                        errs.append(f"{plat} {url} ctype={ctype} (expected profile)")
                elif len(parts) >= 2 and low[0] in ("p", "reel", "reels"):
                    if ctype != "post":
                        errs.append(f"{plat} {url} ctype={ctype} (expected post)")
                    if uname != parts[1]:
                        errs.append(f"{plat} {url} -> {uname} (expected shortcode {parts[1]})")
        print("content_type distribution:", checked)
        assert not errs, f"{len(errs)} entity errors e.g. {errs[:10]}"

    def test_account_name_is_handle_for_profiles(self, welspun_social):
        bad = [f["url"] for f in welspun_social
               if (f.get("entities") or {}).get("content_type") == "profile"
               and (f["entities"].get("account_name") != f["entities"].get("username"))]
        assert not bad, f"account_name != username for profiles: {bad[:8]}"

    def test_brand_relevance(self, welspun_social):
        bad = []
        for f in welspun_social:
            hay = (f.get("title", "") + " " + f.get("url", "") + " " +
                   ((f.get("evidence") or {}).get("snippet") or "")).lower()
            hay = re.sub(r"[^a-z0-9]", "", hay)
            if "welspun" not in hay:
                bad.append(f["url"])
        assert not bad, f"non brand-relevant findings: {bad[:8]}"


# ------------- DEFECTS FOUND (expected to FAIL until main agent fixes) -------
class TestHandleExtractionDefects:
    """Documents real garbage handles still produced by _extract_handle."""

    NON_HANDLE = {"hashtag", "popular", "explore", "feed", "jobs", "search",
                  "tags", "results", "share", "pulse"}

    def test_no_navigation_segment_used_as_handle(self, welspun_social):
        bad = []
        for f in welspun_social:
            e = f.get("entities") or {}
            if (e.get("username") or "").lower() in self.NON_HANDLE:
                bad.append((f["platform"], e.get("username"), e.get("content_type"), f["url"]))
        assert not bad, (f"{len(bad)} findings use a navigation/keyword URL segment as the "
                         f"username (and most are mislabelled content_type=profile): {bad[:20]}")

    def test_linkedin_post_author_handle(self):
        sys.path.insert(0, "/app/backend")
        from collectors import _extract_handle
        cases = [
            ("https://www.linkedin.com/posts/welspunworld_welspun-welspunworld-activity-7197100608196120576-Bf_2", "welspunworld"),
            ("https://www.linkedin.com/posts/welspun-living-limited_independenceday-welspunliving-activity-7494", "welspun-living-limited"),
            ("https://www.linkedin.com/posts/rakhi-shukla-16043522_welspuntextilecomplex-activity-716489200", "rakhi-shukla-16043522"),
        ]
        wrong = []
        for url, exp in cases:
            h, c = _extract_handle(url, "LinkedIn")
            if h != exp:
                wrong.append(f"{url} -> {h!r} (expected author {exp!r})")
        assert not wrong, ("LinkedIn /posts/ handle should be the author slug before the first "
                           "'_' , not split('-')[0]: " + "; ".join(wrong))


# ------------------------------- SCREENSHOT ---------------------------------
class TestScreenshot:
    def _pick(self, welspun_social, hosts):
        for f in welspun_social:
            if any(h in f["url"] for h in hosts):
                return f
        return None

    @pytest.mark.parametrize("hosts", [("x.com", "twitter.com"), ("youtube.com",)])
    def test_capture(self, admin, welspun_social, hosts):
        f = self._pick(welspun_social, hosts)
        if not f:
            pytest.skip(f"no finding for {hosts}")
        r = admin.post(f"{BASE_URL}/api/findings/{f['id']}/screenshot", timeout=120)
        assert r.status_code in (200, 502), f"{r.status_code} {r.text[:300]}"
        if r.status_code == 502:
            assert "detail" in r.json()
            pytest.skip(f"clean 502 for {f['url']}: {r.json()['detail']}")
        surl = r.json()["screenshot_url"]
        assert surl == f"/api/media/screenshots/{f['id']}.png"
        g = requests.get(f"{BASE_URL}{surl}", timeout=60)
        assert g.status_code == 200
        assert g.headers.get("content-type", "").startswith("image/png")
        assert len(g.content) > 1000, f"tiny png {len(g.content)} bytes"
        # persisted on the finding
        d = admin.get(f"{BASE_URL}/api/findings/{f['id']}", timeout=30)
        assert d.status_code == 200
        assert (d.json().get("entities") or {}).get("screenshot_url") == surl

    def test_viewer_forbidden(self, welspun_social):
        f = welspun_social[0]
        tok = _login(*CREDS["viewer"])
        r = requests.post(f"{BASE_URL}/api/findings/{f['id']}/screenshot",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=90)
        assert r.status_code == 403, f"viewer got {r.status_code}"

    def test_unknown_finding_404(self, admin):
        r = admin.post(f"{BASE_URL}/api/findings/does-not-exist-123/screenshot", timeout=60)
        assert r.status_code == 404


# ---------------------------- PAGINATION CONFIG ------------------------------
class TestPaginationConfig:
    def test_collect_search_dork_defaults(self):
        sys.path.insert(0, "/app/backend")
        import inspect
        import collectors
        sig = inspect.signature(collectors.collect_search_dork)
        assert sig.parameters["serper_pages"].default == 13, sig
        src = inspect.getsource(collectors.collect_search_dork)
        assert "t0 + 300" in src, "deadline should be 300s"
        assert "range(1, serper_pages + 1)" in src

    @pytest.mark.parametrize("url,platform,exp_handle,exp_ctype", [
        ("https://www.instagram.com/welspungroup/", "Instagram", "welspungroup", "profile"),
        ("https://x.com/WelspunWorld", "X", "WelspunWorld", "profile"),
        ("https://in.linkedin.com/company/welspun-living-limited", "LinkedIn", "welspun-living-limited", "profile"),
        ("https://www.youtube.com/channel/UCabc123", "YouTube", "UCabc123", "profile"),
        ("https://www.youtube.com/@WelspunGroup", "YouTube", "@WelspunGroup", "profile"),
        ("https://www.reddit.com/r/india/comments/abc/title/", "Reddit", "r/india", "post"),
        ("https://www.instagram.com/p/XXXYYY/", "Instagram", "XXXYYY", "post"),
        ("https://www.youtube.com/watch?v=VID12345", "YouTube", "VID12345", "video"),
    ])
    def test_extract_handle_unit(self, url, platform, exp_handle, exp_ctype):
        sys.path.insert(0, "/app/backend")
        from collectors import _extract_handle
        h, c = _extract_handle(url, platform)
        assert (h, c) == (exp_handle, exp_ctype), f"{url} -> {(h, c)}"


# ------------------------------- REGRESSION ---------------------------------
class TestStripeRegression:
    @pytest.fixture(scope="class")
    def stripe_id(self, admin):
        r = admin.get(f"{BASE_URL}/api/tenants", timeout=30)
        assert r.status_code == 200
        body = r.json()
        items = body.get("items") if isinstance(body, dict) else body
        for t in items:
            if t.get("code") == "TEN-0001" or "Stripe" in (t.get("name") or ""):
                return t["id"]
        pytest.fail("Stripe tenant not found")

    def test_social_count_69(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social", "page": 1, "page_size": 20}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 69, f"total={d['total']}"
        assert len(d["items"]) == 20

    def test_pagination_and_search(self, admin, stripe_id):
        p1 = admin.get(f"{BASE_URL}/api/findings",
                       params={"tenant_id": stripe_id, "module": "social", "page": 1, "page_size": 10}, timeout=60).json()
        p2 = admin.get(f"{BASE_URL}/api/findings",
                       params={"tenant_id": stripe_id, "module": "social", "page": 2, "page_size": 10}, timeout=60).json()
        assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})
        s = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social", "search": "stripe"}, timeout=60)
        assert s.status_code == 200
        assert s.json()["total"] > 0

    def test_severity_filter(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings",
                      params={"tenant_id": stripe_id, "module": "social", "severity": "high"}, timeout=60)
        assert r.status_code == 200
        for i in r.json()["items"]:
            assert i["severity"] == "high"

    def test_csv_export(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings/export",
                      params={"tenant_id": stripe_id, "module": "social"}, timeout=90)
        assert r.status_code == 200, r.text[:200]
        assert "text/csv" in r.headers.get("content-type", "")
        assert len(r.text.splitlines()) > 1

    def test_report_pdf(self, admin, stripe_id):
        r = admin.get(f"{BASE_URL}/api/findings/report.pdf",
                      params={"tenant_id": stripe_id}, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"

    def test_overlapping_run_guard(self, admin, stripe_id):
        # 'dns' collector only — must NOT trigger serper/search_dork
        r1 = admin.post(f"{BASE_URL}/api/tenants/{stripe_id}/run",
                        params={"collector": "dns"}, timeout=60)
        assert r1.status_code == 200, f"{r1.status_code} {r1.text[:200]}"
        r2 = admin.post(f"{BASE_URL}/api/tenants/{stripe_id}/run",
                        params={"collector": "dns"}, timeout=60)
        assert r2.status_code == 200
        msgs = [r1.json().get("message"), r2.json().get("message")]
        assert any("already running" in (m or "").lower() for m in msgs), msgs
