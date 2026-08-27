"""Unit tests for the serper.dev provider path in collectors.collect_search_dork.

Covers: provider ordering (scrape.do -> serper -> ddgs), the ONE combined
keyword query, pagination 1..6, dedupe by URL, brand selection (not tagline),
region (gl), host filtering + brand relevance, and engine label.
All external HTTP is stubbed - no live API quota is consumed.
"""
import os
import pytest

import collectors as C


WELSPUN = {
    "id": "t-welspun",
    "name": "Welspun",
    "brand_names": ["Globally recognized leaders in Home Textiles and Line Pipes", "Welspun"],
    "all_domains": ["welspun.com"],
    "country": "India",
}


def _mk(url, title=None, body=""):
    return {"href": url, "title": title or f"Welspun page {url}", "body": body}


@pytest.fixture
def serper_only(monkeypatch):
    monkeypatch.delenv("SCRAPE_DO_KEY", raising=False)
    monkeypatch.setenv("SERPER_KEY", "test-serper-key")


# ── module: _serper_search ────────────────────────────────────────────────────
class TestSerperSearch:
    def test_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("SERPER_KEY", raising=False)
        assert C._serper_search("welspun instagram") is None

    @pytest.mark.parametrize("code", [401, 402, 429])
    def test_quota_codes_raise(self, monkeypatch, code):
        monkeypatch.setenv("SERPER_KEY", "k")

        class R:
            status_code = code
            text = "Not enough credits"

        monkeypatch.setattr(C.httpx, "post", lambda *a, **k: R())
        with pytest.raises(C.ScrapeDoQuotaError):
            C._serper_search("q")

    def test_parses_organic_and_sends_headers(self, monkeypatch):
        monkeypatch.setenv("SERPER_KEY", "k")
        captured = {}

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"organic": [
                    {"link": "https://instagram.com/welspun", "title": "Welspun", "snippet": "s"},
                    {"title": "no link"},
                ]}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured.update({"url": url, "headers": headers, "json": json})
            return R()

        monkeypatch.setattr(C.httpx, "post", fake_post)
        out = C._serper_search("welspun instagram", page=3, gl="in")
        assert captured["url"] == "https://google.serper.dev/search"
        assert captured["headers"]["X-API-KEY"] == "k"
        assert captured["json"]["page"] == 3 and captured["json"]["gl"] == "in"
        assert out == [{"href": "https://instagram.com/welspun", "title": "Welspun", "body": "s"}]


# ── module: collect_search_dork (serper fallback path) ───────────────────────
class TestSerperCollector:
    def test_combined_keyword_query_pagination_and_findings(self, serper_only, monkeypatch):
        calls = []
        pages = {
            1: [_mk("https://instagram.com/welspunindia"), _mk("https://facebook.com/WelspunGroup")],
            2: [_mk("https://www.linkedin.com/company/welspun"), _mk("https://youtube.com/@welspun")],
            3: [_mk("https://x.com/welspun"), _mk("https://instagram.com/welspunindia")],  # dupe URL
            4: [_mk("https://example.com/welspun-news"),  # non-social -> filtered
                _mk("https://reddit.com/r/random", title="unrelated topic")],  # no brand -> filtered
            5: [_mk("https://t.me/welspunofficial")],
            6: [_mk("https://pinterest.com/welspun")],
        }

        def fake(query, page=1, gl="us", hl="en"):
            calls.append((query, page, gl))
            return pages.get(page, [])

        monkeypatch.setattr(C, "_serper_search", fake)
        findings, health = C.collect_search_dork(WELSPUN)

        # ONE combined keyword query, identical across pages
        queries = {q for q, _, _ in calls}
        assert len(queries) == 1, f"expected a single combined query, got {queries}"
        q = queries.pop()
        assert "site:" not in q and " OR " not in q
        assert q.startswith("Welspun "), q
        for kw in ["instagram", "twitter", "facebook", "linkedin", "youtube",
                   "tiktok", "threads", "pinterest", "telegram", "reddit"]:
            assert kw in q, f"{kw} missing from combined query: {q}"

        # pagination pages 1..6, region India
        assert [p for _, p, _ in calls] == [1, 2, 3, 4, 5, 6]
        assert {g for _, _, g in calls} == {"in"}

        # findings: deduped, host-filtered, brand-relevant
        urls = [f["url"] for f in findings]
        assert len(urls) == len(set(urls))
        assert not any("example.com" in u for u in urls)
        assert not any("reddit.com/r/random" in u for u in urls)
        plats = {f["platform"] for f in findings}
        assert {"Instagram", "Facebook", "LinkedIn", "YouTube", "X"} <= plats
        assert all(f["evidence"]["engine"] == "serper (google)" for f in findings)
        assert all(f["evidence"]["query"] == q for f in findings)
        assert all(f["evidence"]["matched_brand"] == "Welspun" for f in findings)
        assert all(f["module"] == "social" and f["source"] == "Search/Dorking" for f in findings)
        assert health["status"] == "healthy" and health["items_found"] == len(findings) > 0

    def test_stops_early_on_empty_page(self, serper_only, monkeypatch):
        calls = []

        def fake(query, page=1, gl="us", hl="en"):
            calls.append(page)
            return [_mk("https://instagram.com/welspun")] if page == 1 else []

        monkeypatch.setattr(C, "_serper_search", fake)
        findings, health = C.collect_search_dork(WELSPUN)
        assert calls == [1, 2]
        assert health["status"] == "healthy" and len(findings) == 1

    def test_quota_error_is_graceful(self, serper_only, monkeypatch):
        def fake(query, page=1, gl="us", hl="en"):
            raise C.ScrapeDoQuotaError("serper request rejected (429): rate limited")

        monkeypatch.setattr(C, "_serper_search", fake)
        findings, health = C.collect_search_dork(WELSPUN)
        assert findings == []
        assert health["status"] == "degraded" and health["error"]

    def test_scrapedo_preferred_then_serper_on_quota(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_DO_KEY", "sd")
        monkeypatch.setenv("SERPER_KEY", "sp")
        order = []

        def sd(query, num=20, start=0, gl="us", hl="en"):
            order.append("scrape.do")
            raise C.ScrapeDoQuotaError("scrape.do request rejected (401): quota")

        def sp(query, page=1, gl="us", hl="en"):
            order.append("serper")
            return [_mk("https://instagram.com/welspun")] if page == 1 else []

        monkeypatch.setattr(C, "_scrape_do_search", sd)
        monkeypatch.setattr(C, "_serper_search", sp)
        findings, health = C.collect_search_dork(WELSPUN)
        assert order[0] == "scrape.do" and "serper" in order
        assert order.count("scrape.do") == 1, "quota must short-circuit top-ups"
        assert len(findings) == 1
        assert findings[0]["evidence"]["engine"] == "serper (google)"
        assert health["status"] == "healthy"

    def test_scrapedo_success_skips_serper(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_DO_KEY", "sd")
        monkeypatch.setenv("SERPER_KEY", "sp")
        used = []

        def sd(query, num=20, start=0, gl="us", hl="en"):
            used.append("scrape.do")
            return [_mk("https://instagram.com/welspun")] if start == 0 else []

        def sp(query, page=1, gl="us", hl="en"):
            used.append("serper")
            return []

        monkeypatch.setattr(C, "_scrape_do_search", sd)
        monkeypatch.setattr(C, "_serper_search", sp)
        findings, health = C.collect_search_dork(WELSPUN)
        assert "serper" not in used, "serper must not run when scrape.do returned findings"
        assert findings[0]["evidence"]["engine"] == "scrape.do (google)"

    def test_ddgs_only_when_no_keys(self, monkeypatch):
        monkeypatch.delenv("SCRAPE_DO_KEY", raising=False)
        monkeypatch.delenv("SERPER_KEY", raising=False)
        hits = []

        def ddg(q, host=None, max_results=25, deadline=None):
            hits.append(q)
            return [], True

        monkeypatch.setattr(C, "_ddg_search_multi", ddg)
        monkeypatch.setattr(C.time, "sleep", lambda *a: None)
        C.collect_search_dork(WELSPUN, platforms=["Instagram"])
        assert hits and "site:instagram.com" in hits[0]


# ── config/security: keys come from env, not source ─────────────────────────
def test_keys_not_hardcoded():
    src = open(os.path.join(os.path.dirname(C.__file__), "collectors.py")).read()
    assert 'os.environ.get("SERPER_KEY")' in src
    assert 'os.environ.get("SCRAPE_DO_KEY")' in src
    env_vals = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env_vals[k] = v
    assert env_vals.get("SERPER_KEY"), "SERPER_KEY missing from backend/.env"
    for k in ("SERPER_KEY", "SCRAPE_DO_KEY"):
        val = env_vals.get(k, "")
        if val:
            assert val not in src, f"{k} value appears hardcoded in collectors.py"
