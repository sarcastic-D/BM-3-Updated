"""
Phase 1 POC: Prove the free (no-paid-API) monitoring collectors return REAL data
in this environment. Covers:
  1. crt.sh  - Certificate Transparency subdomain enumeration
  2. RDAP    - Domain registration intelligence
  3. DNS     - Record snapshot (A/AAAA/MX/NS/TXT)
  4. Typosquat generator + DNS resolution check
  5. Search / Dorking via DuckDuckGo (site: queries) -> social/pastebin/reddit/youtube

Run:  python test_core.py
Output: prints results + writes poc_results.json
"""
import json
import time
import socket
import traceback
from datetime import datetime

import httpx
import dns.resolver

RESULTS = {}

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# 1. crt.sh — Certificate Transparency
# ---------------------------------------------------------------------------
def test_crtsh(domain: str):
    print(f"\n[1] crt.sh CT enumeration for %.{domain}")
    out = {"ok": False, "count": 0, "sample": [], "error": None}
    try:
        data = None
        last_err = None
        # crt.sh is frequently flaky (502/timeout); retry with backoff.
        for attempt in range(4):
            try:
                url = f"https://crt.sh/?q=%25.{domain}&output=json"
                with httpx.Client(timeout=45, headers={"User-Agent": DEFAULT_UA}) as c:
                    r = c.get(url)
                    r.raise_for_status()
                    text = r.text.strip()
                    if not text:
                        raise ValueError("empty response")
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        data = [json.loads(line) for line in text.splitlines() if line.strip()]
                    break
            except Exception as e:
                last_err = e
                print(f"    (crt.sh attempt {attempt+1} failed: {e}; retrying...)")
                time.sleep(3 * (attempt + 1))
        if data is None:
            raise last_err or RuntimeError("crt.sh unavailable")
        names = set()
        issuers = set()
        for row in data:
            for nm in str(row.get("name_value", "")).splitlines():
                nm = nm.strip().lstrip("*.").lower()
                if nm:
                    names.add(nm)
            if row.get("issuer_name"):
                issuers.add(row["issuer_name"])
        out["ok"] = len(names) > 0
        out["count"] = len(names)
        out["sample"] = sorted(names)[:15]
        out["issuers_sample"] = sorted(issuers)[:5]
        print(f"    -> {len(names)} unique names. sample: {out['sample'][:5]}")
    except Exception as e:
        out["error"] = str(e)
        print(f"    !! ERROR: {e}")
    RESULTS["crtsh"] = out
    return out


# ---------------------------------------------------------------------------
# 2. RDAP — domain registration
# ---------------------------------------------------------------------------
def test_rdap(domain: str):
    print(f"\n[2] RDAP lookup for {domain}")
    out = {"ok": False, "error": None, "data": {}}
    try:
        url = f"https://rdap.org/domain/{domain}"
        with httpx.Client(timeout=30, headers={"User-Agent": DEFAULT_UA}, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.json()
        events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
        registrar = None
        for ent in data.get("entities", []):
            roles = ent.get("roles", [])
            if "registrar" in roles:
                # vcardArray parse
                try:
                    for item in ent.get("vcardArray", [None, []])[1]:
                        if item[0] == "fn":
                            registrar = item[3]
                except Exception:
                    pass
        parsed = {
            "handle": data.get("handle"),
            "status": data.get("status"),
            "registrar": registrar,
            "registered": events.get("registration"),
            "expiration": events.get("expiration"),
            "last_changed": events.get("last changed"),
            "nameservers": [ns.get("ldhName") for ns in data.get("nameservers", [])],
        }
        out["ok"] = bool(parsed.get("handle") or parsed.get("registered") or parsed.get("nameservers"))
        out["data"] = parsed
        print(f"    -> registrar={registrar} registered={parsed['registered']} status={parsed['status']}")
    except Exception as e:
        out["error"] = str(e)
        print(f"    !! ERROR: {e}")
    RESULTS["rdap"] = out
    return out


# ---------------------------------------------------------------------------
# 3. DNS — record snapshot
# ---------------------------------------------------------------------------
def test_dns(domain: str):
    print(f"\n[3] DNS records for {domain}")
    out = {"ok": False, "records": {}, "error": None}
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        resolver.timeout = 5
        resolver.lifetime = 8
        records = {}
        for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
            try:
                ans = resolver.resolve(domain, rtype)
                records[rtype] = [r.to_text() for r in ans]
            except Exception as e:
                records[rtype] = []
        out["records"] = records
        out["ok"] = any(records.values())
        print(f"    -> A={records.get('A')} NS={records.get('NS')}")
    except Exception as e:
        out["error"] = str(e)
        print(f"    !! ERROR: {e}")
    RESULTS["dns"] = out
    return out


# ---------------------------------------------------------------------------
# 4. Typosquat generation + resolution check
# ---------------------------------------------------------------------------
def generate_typosquats(domain: str):
    name, _, tld = domain.rpartition(".")
    if not name:
        name, tld = domain, "com"
    candidates = set()
    chars = "abcdefghijklmnopqrstuvwxyz"
    # character omission
    for i in range(len(name)):
        candidates.add(name[:i] + name[i + 1:])
    # character duplication
    for i in range(len(name)):
        candidates.add(name[:i] + name[i] + name[i] + name[i + 1:])
    # adjacent swap
    for i in range(len(name) - 1):
        candidates.add(name[:i] + name[i + 1] + name[i] + name[i + 2:])
    # character replacement (limited)
    for i in range(len(name)):
        for ch in chars:
            candidates.add(name[:i] + ch + name[i + 1:])
    # homoglyph-lite
    homo = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4", "s": "5"}
    for i, ch in enumerate(name):
        if ch in homo:
            candidates.add(name[:i] + homo[ch] + name[i + 1:])
    # different TLDs
    tld_variants = {f"{name}.{t}" for t in ["net", "org", "co", "io", "xyz", "info"]}
    candidates.discard(name)
    result = {f"{c}.{tld}" for c in candidates if c} | tld_variants
    return sorted(result)


def test_typosquat(domain: str, max_check: int = 40):
    print(f"\n[4] Typosquat generation + resolution for {domain}")
    out = {"ok": False, "generated": 0, "resolving": [], "error": None}
    try:
        cands = generate_typosquats(domain)
        out["generated"] = len(cands)
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        resolver.timeout = 3
        resolver.lifetime = 4
        resolving = []
        for cand in cands[:max_check]:
            try:
                ans = resolver.resolve(cand, "A")
                ips = [r.to_text() for r in ans]
                resolving.append({"domain": cand, "ips": ips})
            except Exception:
                pass
        out["resolving"] = resolving
        out["ok"] = len(cands) > 0
        print(f"    -> generated {len(cands)} candidates, {len(resolving)} resolve (checked {min(max_check,len(cands))})")
        for r in resolving[:5]:
            print(f"       LIVE: {r['domain']} -> {r['ips']}")
    except Exception as e:
        out["error"] = str(e)
        traceback.print_exc()
        print(f"    !! ERROR: {e}")
    RESULTS["typosquat"] = out
    return out


# ---------------------------------------------------------------------------
# 5. Search / Dorking via DuckDuckGo
# ---------------------------------------------------------------------------
def test_search_dork(brand: str):
    print(f"\n[5] Search/dorking for brand='{brand}'")
    out = {"ok": False, "queries": {}, "total_hits": 0, "error": None}
    dorks = {
        "instagram": ("instagram.com", f'{brand} site:instagram.com'),
        "x": ("x.com", f'{brand} site:x.com'),
        "pastebin": ("pastebin.com", f'{brand} site:pastebin.com'),
        "reddit": ("reddit.com", f'{brand} site:reddit.com'),
        "youtube": ("youtube.com", f'{brand} site:youtube.com'),
        "scribd": ("scribd.com", f'{brand} site:scribd.com'),
    }
    total = 0
    try:
        from ddgs import DDGS
        for label, (host, q) in dorks.items():
            hits = []
            try:
                with DDGS() as ddgs:
                    for res in ddgs.text(q, max_results=8):
                        url = res.get("href") or res.get("url") or ""
                        # post-filter: keep only results actually on the target host
                        if host in url:
                            hits.append({
                                "title": res.get("title"),
                                "url": url,
                                "snippet": (res.get("body") or "")[:160],
                            })
                time.sleep(1.5)
            except Exception as e:
                out["queries"][label] = {"error": str(e), "hits": []}
                print(f"    [{label}] query error: {e}")
                continue
            out["queries"][label] = {"query": q, "hits": hits}
            total += len(hits)
            print(f"    [{label}] {len(hits)} on-site hits" + (f" e.g. {hits[0]['url']}" if hits else ""))
        out["total_hits"] = total
        out["ok"] = total > 0
    except Exception as e:
        out["error"] = str(e)
        traceback.print_exc()
        print(f"    !! ERROR: {e}")
    RESULTS["search_dork"] = out
    return out


def main():
    brand = "PayPal"
    domain = "paypal.com"
    print("=" * 70)
    print(f"BRAND MONITORING POC  brand={brand} domain={domain}")
    print("=" * 70)

    test_crtsh(domain)
    test_rdap(domain)
    test_dns(domain)
    test_typosquat(domain)
    test_search_dork(brand)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    summary = {}
    for k, v in RESULTS.items():
        status = "PASS" if v.get("ok") else "FAIL"
        summary[k] = status
        print(f"  {k:14s} : {status}  {'' if v.get('ok') else '('+str(v.get('error'))+')'}")

    with open("poc_results.json", "w") as f:
        json.dump({"generated_at": datetime.utcnow().isoformat(), "results": RESULTS}, f, indent=2, default=str)
    print("\nWrote poc_results.json")

    passed = sum(1 for v in RESULTS.values() if v.get("ok"))
    print(f"\nOVERALL: {passed}/{len(RESULTS)} collectors returned real data")


if __name__ == "__main__":
    main()
