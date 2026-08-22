"""
Real, no-paid-API monitoring collectors + normalization + risk engine.
Collectors: crt.sh (CT), RDAP, DNS, typosquat, search-dorking (DuckDuckGo).
All functions are synchronous (run in a threadpool from async routes).
Each returns (findings: list[dict], health: dict).
"""
import json
import time
import ssl
import socket
import hashlib
import difflib
from datetime import datetime, timezone

import httpx
import dns.resolver

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

CHARS = "abcdefghijklmnopqrstuvwxyz"
# number / leet substitutions
NUMSUB = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4", "s": "5", "t": "7", "b": "8", "g": "9", "z": "2"}
# unicode homoglyphs (visually confusable characters) used for IDN/punycode variants
UNIHOMO = {
    "a": "\u0430",  # cyrillic a
    "e": "\u0435",  # cyrillic e
    "o": "\u043e",  # cyrillic o
    "c": "\u0441",  # cyrillic c
    "p": "\u0440",  # cyrillic p
    "x": "\u0445",  # cyrillic x
    "i": "\u0456",  # cyrillic i
    "s": "\u0455",  # cyrillic dze
    "l": "\u04cf",  # cyrillic palochka
}
# QWERTY keyboard adjacency (for fat-finger typos)
KEYADJ = {
    "q": "wa", "w": "qeas", "e": "wrsd", "r": "etdf", "t": "ryfg", "y": "tugh",
    "u": "yihj", "i": "uojk", "o": "ipkl", "p": "ol", "a": "qwsz", "s": "awedxz",
    "d": "serfcx", "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "j": "huikmn",
    "k": "jiolm", "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb",
    "b": "vghn", "n": "bhjm", "m": "njk",
}
# common phishing prefix/suffix "function" words appended/prepended to a brand
FUNCTION_WORDS = ["support", "login", "secure", "account", "verify", "help",
                  "service", "official", "online", "pay", "app", "portal"]
ALT_TLDS = ["net", "org", "co", "io", "xyz", "info", "online", "site", "app",
            "shop", "store", "live", "vip", "biz", "cc"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _dedupe_key(tenant_id, module, ident):
    raw = f"{tenant_id}|{module}|{ident}".lower()
    return hashlib.sha1(raw.encode()).hexdigest()


def severity_from_score(score: int) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def _resolver():
    r = dns.resolver.Resolver()
    r.nameservers = ["8.8.8.8", "1.1.1.1"]
    r.timeout = 3
    r.lifetime = 4
    return r


# ---------------------------------------------------------------------------
# RDAP helper (returns parsed registration data)
# ---------------------------------------------------------------------------
def rdap_lookup(domain: str) -> dict:
    try:
        with httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True) as c:
            r = c.get(f"https://rdap.org/domain/{domain}")
            r.raise_for_status()
            data = r.json()
        events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
        registrar = None
        for ent in data.get("entities", []):
            if "registrar" in ent.get("roles", []):
                try:
                    for item in ent.get("vcardArray", [None, []])[1]:
                        if item[0] == "fn":
                            registrar = item[3]
                except Exception:
                    pass
        created = events.get("registration")
        age_days = None
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - dt).days
            except Exception:
                pass
        return {
            "registrar": registrar,
            "status": data.get("status"),
            "created": created,
            "expiration": events.get("expiration"),
            "nameservers": [ns.get("ldhName") for ns in data.get("nameservers", [])],
            "age_days": age_days,
        }
    except Exception:
        return {}


def dns_snapshot(domain: str) -> dict:
    res = _resolver()
    rec = {}
    for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
        try:
            ans = res.resolve(domain, rtype)
            rec[rtype] = [r.to_text() for r in ans]
        except Exception:
            rec[rtype] = []
    return rec


def _tld(domain):
    return domain.rpartition(".")[2] if "." in domain else ""


# ---------------------------------------------------------------------------
# Typosquat generation
# ---------------------------------------------------------------------------
def _to_punycode(host: str):
    """Encode a unicode domain label to IDNA/punycode (xn--). Returns None on failure."""
    try:
        name, _, tld = host.rpartition(".")
        if not name:
            return None
        enc = name.encode("idna").decode("ascii")
        return f"{enc}.{tld}"
    except Exception:
        return None


def generate_typosquats(domain: str):
    """Advanced typo-intelligence generator. Returns {candidate_domain: kind}.
    Covers: addition, deletion, substitution, transposition, repetition,
    hyphenation, prefix/suffix, tld variation, number substitution, keyboard
    adjacency, unicode homoglyph, IDN/punycode, and brand+function combinations.
    """
    name, _, tld = domain.rpartition(".")
    if not name:
        name, tld = domain, "com"
    cands = {}          # label -> kind (label without tld)
    full = {}           # full domain -> kind (for tld/hyphen/function variants)

    n = len(name)
    # deletion (omission)
    for i in range(n):
        cands[name[:i] + name[i + 1:]] = "deletion"
    # repetition (duplicate a char)
    for i in range(n):
        cands[name[:i] + name[i] + name[i] + name[i + 1:]] = "repetition"
    # transposition (swap adjacent)
    for i in range(n - 1):
        cands[name[:i] + name[i + 1] + name[i] + name[i + 2:]] = "transposition"
    # substitution (any letter)
    for i in range(n):
        for ch in CHARS:
            if ch != name[i]:
                cands.setdefault(name[:i] + ch + name[i + 1:], "substitution")
    # addition (insert a letter)
    for i in range(n + 1):
        for ch in CHARS:
            cands.setdefault(name[:i] + ch + name[i:], "addition")
    # keyboard adjacency (fat-finger)
    for i, ch in enumerate(name):
        for adj in KEYADJ.get(ch, ""):
            cands[name[:i] + adj + name[i + 1:]] = "keyboard-adjacency"
    # number substitution (leet)
    for i, ch in enumerate(name):
        if ch in NUMSUB:
            cands[name[:i] + NUMSUB[ch] + name[i + 1:]] = "number-substitution"
    # unicode homoglyph (ascii-visible, e.g. rn -> m style handled via mapping)
    for i, ch in enumerate(name):
        if ch in UNIHOMO:
            cands[name[:i] + UNIHOMO[ch] + name[i + 1:]] = "homoglyph"

    out = {}
    for c, kind in cands.items():
        if c and c != name:
            out[f"{c}.{tld}"] = kind

    # hyphenation (insert a hyphen inside the label)
    for i in range(1, n):
        full[f"{name[:i]}-{name[i:]}.{tld}"] = "hyphenation"
    # tld variation (same label, alternate tld)
    for t in ALT_TLDS:
        if t != tld:
            full[f"{name}.{t}"] = "tld-variation"
    # brand + function combinations (prefix & suffix)
    for w in FUNCTION_WORDS:
        full[f"{name}-{w}.{tld}"] = "brand-function"
        full[f"{w}-{name}.{tld}"] = "brand-function"
        full[f"{name}{w}.{tld}"] = "brand-function"
    out.update(full)

    # IDN / punycode: encode any unicode homoglyph candidate to xn-- form
    puny = {}
    for cand, kind in list(out.items()):
        if any(ord(c) > 127 for c in cand):
            enc = _to_punycode(cand)
            if enc and enc != cand:
                puny[enc] = "idn-punycode"
    out.update(puny)
    return out


def _resolve_a(cand):
    """Return (cand, ips) if resolves else (cand, None). Own resolver per thread."""
    try:
        r = dns.resolver.Resolver()
        r.nameservers = ["8.8.8.8", "1.1.1.1"]
        r.timeout = 2.5
        r.lifetime = 3
        ans = r.resolve(cand, "A")
        return cand, [x.to_text() for x in ans]
    except Exception:
        return cand, None


def _visible_text(html: str, limit: int = 4000):
    """Very light HTML -> visible text extractor for content-similarity comparison."""
    if not html:
        return ""
    import re as _re
    txt = _re.sub(r"(?is)<(script|style|head|noscript).*?</\1>", " ", html)
    txt = _re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = _re.sub(r"\s+", " ", txt)
    return txt.strip().lower()[:limit]


def http_probe(domain: str, timeout: int = 8):
    """Check whether a live site responds; return status + title + visible text."""
    for scheme in ("https", "http"):
        try:
            with httpx.Client(timeout=timeout, headers={"User-Agent": UA},
                              follow_redirects=True, verify=False) as c:
                r = c.get(f"{scheme}://{domain}")
                body = r.text or ""
                return {
                    "ok": True,
                    "status": r.status_code,
                    "scheme": scheme,
                    "final_url": str(r.url),
                    "title": _extract_title(body),
                    "text": _visible_text(body),
                }
        except Exception:
            continue
    return {"ok": False}


def _content_similarity(a: str, b: str) -> int:
    """0-100 similarity between two visible-text blobs."""
    if not a or not b:
        return 0
    return int(difflib.SequenceMatcher(None, a[:4000], b[:4000]).ratio() * 100)


# ===========================================================================
# COLLECTOR: Typosquat -> fake websites  (enriched with RDAP + DNS)
# ===========================================================================
def collect_typosquat(tenant, max_candidates=180, max_enrich=16):
    """Advanced typosquat detection with a validation pipeline:
    Generated -> DNS exists? -> HTTP exists? -> Brand similarity? ->
    Content similarity? -> Infrastructure suspicious? -> Risk score.
    Only candidates that pass the gates (live + relevant) are persisted.
    """
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time()
    findings, error = [], None
    identity = tenant.get("identity", {}) or {}
    domains = identity.get("official_domains") or tenant.get("all_domains", [])
    known_ns = {str(x).lower().rstrip(".") for x in (identity.get("known_nameservers") or [])}
    # official content baseline (fetch primary domain once, best-effort)
    baseline_text, baseline_title = "", ""
    if domains:
        base_probe = http_probe(domains[0], timeout=6)
        if base_probe.get("ok"):
            baseline_text = base_probe.get("text") or ""
            baseline_title = (base_probe.get("title") or "").lower()
    try:
        # ---- STAGE 0: generate candidates (bounded, keep look-alikes) ----
        cand_map = {}
        for base in domains[:2]:
            base_name = base.rpartition(".")[0] or base
            for cand, kind in generate_typosquats(base).items():
                if cand in cand_map:
                    continue
                cand_name = cand.rpartition(".")[0] or cand
                # keep brand-function / tld / hyphen / homoglyph / idn always
                # (they preserve the brand token); otherwise require edit
                # distance <= 2 vs the base label to stay a genuine look-alike.
                if kind not in ("tld-variation", "homoglyph", "idn-punycode",
                                "brand-function", "hyphenation"):
                    # normalise leet back to letters for distance calc
                    norm_cand = cand_name
                    for k, v in NUMSUB.items():
                        norm_cand = norm_cand.replace(v, k)
                    if _lev(base_name, norm_cand) > 2:
                        continue
                cand_map[cand] = (kind, base)
        priority = {"homoglyph": 0, "idn-punycode": 0, "transposition": 1,
                    "deletion": 2, "substitution": 2, "brand-function": 3,
                    "tld-variation": 3, "keyboard-adjacency": 4, "addition": 5,
                    "repetition": 5, "number-substitution": 4, "hyphenation": 6}
        ordered = sorted(cand_map.items(), key=lambda kv: priority.get(kv[1][0], 9))[:max_candidates]

        # ---- STAGE 1: DNS exists? (concurrent A-record resolution) ----
        resolving = []
        with ThreadPoolExecutor(max_workers=25) as ex:
            for cand, ips in ex.map(lambda kv: _resolve_a(kv[0]), ordered):
                if ips:
                    kind, base = cand_map[cand]
                    resolving.append((cand, kind, base, ips))

        # ---- STAGES 2-5: enrich live candidates CONCURRENTLY (bounded) ----
        def _build(cand, kind, base, ips, probe, rdap, dnsrec):
            base_name = base.rpartition(".")[0] or base
            cand_name = cand.rpartition(".")[0] or cand
            norm_cand = cand_name
            for k, v in NUMSUB.items():
                norm_cand = norm_cand.replace(v, k)
            brand_sim = int(difflib.SequenceMatcher(None, base_name, norm_cand).ratio() * 100)
            csim = None
            if probe.get("ok") and baseline_text:
                csim = _content_similarity(baseline_text, probe.get("text") or "")
                if not csim and baseline_title and probe.get("title"):
                    csim = int(difflib.SequenceMatcher(
                        None, baseline_title, probe["title"].lower()).ratio() * 100)
            infra = []
            age_days = rdap.get("age_days")
            if age_days is not None and age_days < 90:
                infra.append("newly-registered (<90d)")
            elif age_days is not None and age_days < 365:
                infra.append("recently-registered (<1y)")
            if dnsrec.get("MX"):
                infra.append("mx-configured (email-capable)")
            cand_ns = {str(x).lower().rstrip(".") for x in (rdap.get("nameservers") or dnsrec.get("NS") or [])}
            if known_ns and cand_ns and not (cand_ns & known_ns):
                infra.append("nameservers differ from brand")
            pipeline = {"generated_kind": kind, "dns_ok": True,
                        "http_ok": bool(probe.get("ok")), "brand_similarity": brand_sim,
                        "content_similarity": csim, "infra_flags": infra}
            score = 30
            if kind in ("homoglyph", "idn-punycode"):
                score += 20
            elif kind in ("transposition", "deletion", "substitution", "keyboard-adjacency"):
                score += 10
            elif kind == "brand-function":
                score += 14
            if probe.get("ok"):
                score += 12
            if brand_sim >= 80:
                score += 10
            if csim is not None and csim >= 60:
                score += 18
            if "newly-registered (<90d)" in infra:
                score += 20
            elif "recently-registered (<1y)" in infra:
                score += 10
            if any("mx-configured" in f for f in infra):
                score += 12
            if any("nameservers differ" in f for f in infra):
                score += 6
            score = min(score, 100)
            evidence = {"ips": ips, "typo_kind": kind, "base_domain": base,
                        "typo_pipeline": pipeline}
            if probe.get("ok"):
                evidence["http_status"] = probe.get("status")
                evidence["page_title"] = probe.get("title")
            if dnsrec:
                evidence["dns"] = dnsrec
            return {
                "module": "fake_website", "category": "Typosquat", "source": "Typosquat",
                "platform": "Web", "title": cand,
                "url": (probe.get("final_url") if probe.get("ok") else f"http://{cand}"),
                "domain": cand, "risk_score": score, "severity": severity_from_score(score),
                "evidence": evidence,
                "entities": {
                    "registrar": rdap.get("registrar"), "tld": _tld(cand),
                    "domain_age_days": age_days,
                    "nameservers": rdap.get("nameservers") or dnsrec.get("NS"),
                    "ips": ips, "created": rdap.get("created"),
                    "expiration": rdap.get("expiration"),
                    "domain_status": (rdap.get("status") or ["active"])[0] if rdap.get("status") else "active",
                    "typo_kind": kind, "brand_similarity": brand_sim,
                    "content_similarity": csim, "http_live": bool(probe.get("ok")),
                    "infra_suspicious": "Yes" if infra else "No",
                    "content_changed": False, "dns_changed": False, "certificate_changed": False,
                },
                "dedupe_key": _dedupe_key(tenant["id"], "fake_website", cand),
            }

        def _enrich_one(item):
            cand, kind, base, ips = item
            return (item, http_probe(cand, timeout=6), rdap_lookup(cand), dns_snapshot(cand))

        to_enrich = resolving[:max_enrich]
        rest = resolving[max_enrich:max_enrich + 40]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for (cand, kind, base, ips), probe, rdap, dnsrec in ex.map(_enrich_one, to_enrich):
                findings.append(_build(cand, kind, base, ips, probe, rdap, dnsrec))
        # lightweight findings for the remaining live look-alikes (DNS only)
        for cand, kind, base, ips in rest:
            findings.append(_build(cand, kind, base, ips, {"ok": False}, {}, {}))
    except Exception as e:
        error = str(e)
    return findings, {"collector": "Typosquat", "status": "failed" if error else "healthy",
                      "error": error, "items_found": len(findings),
                      "duration_ms": int((time.time() - t0) * 1000)}


# ===========================================================================
# COLLECTOR: crt.sh -> domain intelligence (asset/subdomain discovery)
# ===========================================================================
def collect_crtsh(tenant):
    t0 = time.time()
    findings, error, status = [], None, "healthy"
    try:
        for base in tenant.get("all_domains", [])[:3]:
            data = None
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=45, headers={"User-Agent": UA}) as c:
                        r = c.get(f"https://crt.sh/?q=%25.{base}&output=json")
                        r.raise_for_status()
                        text = r.text.strip()
                        if not text:
                            raise ValueError("empty")
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            data = [json.loads(l) for l in text.splitlines() if l.strip()]
                        break
                except Exception as e:
                    error = str(e)
                    time.sleep(2 * (attempt + 1))
            if not data:
                status = "degraded"
                continue
            names, issuers = {}, {}
            for row in data:
                for nm in str(row.get("name_value", "")).splitlines():
                    nm = nm.strip().lstrip("*.").lower()
                    if nm and nm.endswith(base):
                        names[nm] = row.get("issuer_name", "")
            for nm, issuer in list(names.items())[:120]:
                score = 15
                findings.append({
                    "module": "domain_intel",
                    "category": "Suspicious Domain",
                    "source": "crt.sh",
                    "platform": "Web",
                    "title": nm,
                    "url": f"https://{nm}",
                    "domain": nm,
                    "risk_score": score,
                    "severity": severity_from_score(score),
                    "evidence": {"issuer": issuer, "base_domain": base, "discovery": "certificate-transparency"},
                    "entities": {
                        "certificate_issuer": issuer,
                        "tld": _tld(nm),
                        "domain_status": "active",
                        "content_changed": False,
                        "dns_changed": False,
                        "certificate_changed": True,
                    },
                    "dedupe_key": _dedupe_key(tenant["id"], "domain_intel", nm),
                })
        if not findings and error:
            status = "degraded"
    except Exception as e:
        error = str(e)
        status = "failed"
    return findings, {"collector": "Certificate Transparency", "status": status,
                      "error": error, "items_found": len(findings),
                      "duration_ms": int((time.time() - t0) * 1000)}


# ===========================================================================
# COLLECTOR: RDAP + DNS for primary domains -> domain intelligence records
# ===========================================================================
def collect_domain_intel(tenant):
    t0 = time.time()
    findings, error = [], None
    try:
        for base in tenant.get("all_domains", [])[:5]:
            rdap = rdap_lookup(base)
            dnsrec = dns_snapshot(base)
            findings.append({
                "module": "domain_intel",
                "category": "Suspicious Domain",
                "source": "RDAP",
                "platform": "Web",
                "title": f"{base} (owned asset)",
                "url": f"https://{base}",
                "domain": base,
                "risk_score": 5,
                "severity": "Low",
                "evidence": {"rdap": rdap, "dns": dnsrec, "owned": True},
                "entities": {
                    "registrar": rdap.get("registrar"),
                    "tld": _tld(base),
                    "domain_age_days": rdap.get("age_days"),
                    "nameservers": rdap.get("nameservers") or dnsrec.get("NS"),
                    "created": rdap.get("created"),
                    "expiration": rdap.get("expiration"),
                    "domain_status": (rdap.get("status") or ["active"])[0] if rdap.get("status") else "active",
                    "dns_record_types": [k for k, v in dnsrec.items() if v],
                    "content_changed": False,
                    "dns_changed": False,
                    "certificate_changed": False,
                },
                "dedupe_key": _dedupe_key(tenant["id"], "domain_intel", base + ":owned"),
            })
    except Exception as e:
        error = str(e)
    return findings, {"collector": "RDAP", "status": "failed" if error else "healthy",
                      "error": error, "items_found": len(findings),
                      "duration_ms": int((time.time() - t0) * 1000)}


def collect_dns(tenant):
    """Lightweight DNS heartbeat collector (health only, records folded into domain_intel)."""
    t0 = time.time()
    error = None
    ok = 0
    try:
        for base in tenant.get("all_domains", [])[:5]:
            rec = dns_snapshot(base)
            if any(rec.values()):
                ok += 1
    except Exception as e:
        error = str(e)
    return [], {"collector": "DNS", "status": "failed" if error else "healthy",
                "error": error, "items_found": ok,
                "duration_ms": int((time.time() - t0) * 1000)}


# ===========================================================================
# COLLECTOR: search-dorking -> social & data-exposure findings
# ===========================================================================
DORK_TARGETS = {
    "Instagram": ("instagram.com", "social", "Impersonation"),
    "X": ("x.com", "social", "Impersonation"),
    "YouTube": ("youtube.com", "social", "Suspicious Mention"),
    "Reddit": ("reddit.com", "social", "Suspicious Mention"),
    "Facebook": ("facebook.com", "social", "Impersonation"),
    "LinkedIn": ("linkedin.com", "social", "Impersonation"),
    "Pastebin": ("pastebin.com", "social", "Data Exposure"),
    "Scribd": ("scribd.com", "social", "Data Exposure"),
}


def _norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


import re as _re_mod

_SUSPICIOUS_WORDS = ["free", "gift", "giveaway", "support", "login", "verify",
                     "wallet", "airdrop", "bonus", "claim", "helpdesk", "recovery",
                     "customer care", "refund", "official support"]
_OFFICIAL_WORDS = ["official", "verified", "™", "official account"]
_DOMAIN_RE = _re_mod.compile(r"\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b", _re_mod.I)


def _identity(tenant):
    return tenant.get("identity", {}) or {}


def _brand_terms_all(tenant):
    """All trusted brand tokens from the identity profile (normalised, >=3 chars)."""
    idt = _identity(tenant)
    vals = []
    vals += tenant.get("brand_names") or [tenant.get("name")]
    vals += idt.get("trading_names") or []
    vals += idt.get("keywords") or []
    if idt.get("legal_name"):
        vals.append(idt["legal_name"])
    terms = {_norm(v) for v in vals if v and len(_norm(v)) >= 3}
    domains = idt.get("official_domains") or tenant.get("all_domains", [])
    for d in domains[:2]:
        lbl = _norm(str(d).split(".")[0])
        if len(lbl) >= 3:
            terms.add(lbl)
    return terms


def _official_domains(tenant):
    idt = _identity(tenant)
    doms = (idt.get("official_domains") or []) + (idt.get("marketing_domains") or []) + \
           (idt.get("regional_domains") or []) + (tenant.get("all_domains") or [])
    return {str(d).lower().lstrip("www.") for d in doms if d}


_PLATFORM_KEY = {"instagram": "instagram", "x": "x", "twitter": "x", "youtube": "youtube",
                 "facebook": "facebook", "linkedin": "linkedin"}

CONF_CLASSES = [
    (85, "HIGH-CONFIDENCE IMPERSONATION"),
    (65, "LIKELY IMPERSONATION"),
    (45, "SUSPICIOUS"),
    (25, "LIKELY LEGITIMATE"),
    (0, "LEGITIMATE"),
]


def _classify_confidence(conf):
    for threshold, label in CONF_CLASSES:
        if conf >= threshold:
            return label
    return "LEGITIMATE"


def impersonation_assessment(tenant, platform, handle, title, snippet, url, category):
    """Deterministic impersonation confidence (0-100, higher = more likely fake)
    + classification + human-readable signal breakdown. Heuristic only."""
    idt = _identity(tenant)
    handles = idt.get("social_handles", {}) or {}
    brands = [b for b in (tenant.get("brand_names") or [tenant.get("name")]) if b]
    brand = brands[0] if brands else (tenant.get("name") or "")
    text = f"{title} {snippet} {url}".lower()
    signals = {
        "username_similarity": "Unknown (no official handle configured)",
        "display_name_similarity": None,
        "official_wording": "No",
        "suspicious_wording": "No",
        "external_domain": "No",
        "official_link_mismatch": "Unknown",
        "account_age": "Unknown / not available",
        "followers": "Unknown / not available",
        "follower_pattern": "Unknown / not available",
    }

    conf = 20
    # ---- 1. username vs official handle for this platform ----
    pkey = _PLATFORM_KEY.get((platform or "").lower())
    official_handle = handles.get(pkey) if pkey else None
    if official_handle:
        uname_sim = int(difflib.SequenceMatcher(None, _norm(handle), _norm(official_handle)).ratio() * 100)
        if _norm(handle) == _norm(official_handle):
            signals["username_similarity"] = f"100% — matches official @{official_handle}"
            signals["official_link_mismatch"] = "No (verified official account)"
            return 3, "LEGITIMATE", signals
        signals["username_similarity"] = f"{uname_sim}% vs official @{official_handle}"
        conf += 28
        if uname_sim >= 70:
            conf += 18  # close look-alike handle
    # ---- 2. display-name similarity to brand ----
    dsim = int(difflib.SequenceMatcher(None, _norm(brand), _norm(title)).ratio() * 100)
    for b in brands:
        dsim = max(dsim, int(difflib.SequenceMatcher(None, _norm(b), _norm(title)).ratio() * 100))
    signals["display_name_similarity"] = f"{dsim}%"
    if dsim >= 80:
        conf += 18
    elif dsim >= 55:
        conf += 8
    # ---- 3. official wording ----
    if any(w in text for w in _OFFICIAL_WORDS):
        signals["official_wording"] = "Yes"
        if official_handle:
            conf += 15  # claims official but handle mismatched
        else:
            conf += 4
    # ---- 4. suspicious wording ----
    hits = [w for w in _SUSPICIOUS_WORDS if w in text]
    if hits:
        signals["suspicious_wording"] = ", ".join(hits[:5])
        conf += min(8 * len(hits), 22)
    # ---- 5. external domain / official link mismatch ----
    official = _official_domains(tenant)
    ext_found = []
    for m in _DOMAIN_RE.findall(f"{snippet} {url}"):
        d = m.lower().lstrip("www.")
        if d.endswith(("instagram.com", "x.com", "twitter.com", "youtube.com",
                       "facebook.com", "linkedin.com", "reddit.com", "pastebin.com",
                       "scribd.com", "youtu.be")):
            continue
        if any(d == o or d.endswith("." + o) for o in official):
            continue
        ext_found.append(d)
    if ext_found:
        signals["external_domain"] = ", ".join(sorted(set(ext_found))[:3])
        signals["official_link_mismatch"] = "Yes (links to non-official domain)"
        conf += 15
    elif official:
        signals["official_link_mismatch"] = "No external domain detected"
    # ---- 6. data-exposure category ----
    if category == "Data Exposure":
        conf += 25

    conf = max(0, min(conf, 100))
    return conf, _classify_confidence(conf), signals


# DuckDuckGo/ddgs frequently rate-limits a single backend from a fresh server
# IP (returns "No results found."). We rotate across several backends and merge
# unique results so social accounts/posts are not silently dropped.
DDG_BACKENDS = ["google", "bing", "duckduckgo", "brave", "yahoo", "mullvad_google"]


def _ddg_search_multi(query, host=None, max_results=25, target=8, deadline=None):
    """Query several ddgs backends, merge unique results (deduped by url).
    Stops early once `target` host-matched results are collected or `deadline`
    (epoch secs) passes. Returns (results, any_success)."""
    from ddgs import DDGS
    seen, any_success = {}, False
    for backend in DDG_BACKENDS:
        if deadline and time.time() > deadline:
            break
        try:
            with DDGS() as ddgs:
                res = ddgs.text(query, max_results=max_results, backend=backend)
            any_success = True
            for r in res:
                url = r.get("href") or r.get("url") or ""
                if not url or url in seen:
                    continue
                if host and host not in url:
                    continue
                seen[url] = r
        except Exception:
            pass  # this backend is rate-limited/unavailable, try the next
        if len(seen) >= target:
            break
        time.sleep(0.4)
    return list(seen.values()), any_success


def collect_search_dork(tenant, platforms=None, max_per=25):
    t0 = time.time()
    deadline = t0 + 85  # overall budget so a scan run never hangs
    findings, error, status = [], None, "healthy"
    any_backend_ok = False
    brands = [b for b in (tenant.get("brand_names") or [tenant.get("name")]) if b]
    brand = brands[0]
    # identity-aware normalized brand terms used for strict relevance matching
    brand_terms = _brand_terms_all(tenant)
    try:
        targets = DORK_TARGETS
        if platforms:
            targets = {k: v for k, v in DORK_TARGETS.items() if k in platforms}
        for platform, (host, module, category) in targets.items():
            if time.time() > deadline:
                break
            q = f'{brand} site:{host}'
            try:
                # rotate backends + merge; fall back to a broad brand+platform
                # query if the site: dork returns nothing for this platform
                results, ok = _ddg_search_multi(q, host=host, max_results=max_per, deadline=deadline)
                if not results and time.time() < deadline:
                    results, ok2 = _ddg_search_multi(
                        f'{brand} {platform}', host=host, max_results=max_per, deadline=deadline)
                    ok = ok or ok2
                any_backend_ok = any_backend_ok or ok
                for res in results:
                        url = res.get("href") or res.get("url") or ""
                        if host not in url:
                            continue
                        title = res.get("title") or url
                        snippet = (res.get("body") or "")[:280]
                        # STRICT relevance: the brand keyword must actually appear
                        # in the title, handle or snippet (normalised, space-insensitive).
                        hay = _norm(title + " " + snippet + " " + url)
                        if not any(term in hay for term in brand_terms):
                            continue
                        handle = url.rstrip("/").split("/")[-1][:60] or url
                        low = (title + snippet + url).lower()

                        # ---- Impersonation confidence + classification ----
                        conf, classification, vsignals = impersonation_assessment(
                            tenant, platform, handle, title, snippet, url, category)

                        # risk score aligned with confidence, but data-exposure stays high
                        if category == "Data Exposure":
                            score = max(65, conf)
                        else:
                            score = conf
                        score = min(max(score, 10), 100)
                        findings.append({
                            "module": module,
                            "category": category,
                            "source": "Search/Dorking",
                            "platform": platform,
                            "title": title[:180],
                            "url": url,
                            "domain": host,
                            "risk_score": score,
                            "severity": severity_from_score(score),
                            "evidence": {"query": q, "snippet": snippet, "engine": "duckduckgo",
                                         "matched_brand": brand,
                                         "verification_signals": vsignals},
                            "entities": {
                                "account_name": title[:100],
                                "username": handle,
                                "display_name": title[:80],
                                "description": snippet,
                                "profile_url": url,
                                "account_type": ("official" if any(w in low for w in ["official", "verified"]) else "unverified"),
                                "impersonation_confidence": conf,
                                "impersonation_classification": classification,
                                "keyword": brand,
                                "comments": "Full comment threads require a connected platform API",
                                "screenshot_url": None,
                            },
                            "dedupe_key": _dedupe_key(tenant["id"], module, url),
                        })
                time.sleep(0.5)
            except Exception as e:
                error = str(e)
                time.sleep(2)
    except Exception as e:
        error = str(e)
        status = "failed"
    # Status reflects whether the free scrapers were reachable at all:
    #  - healthy  : we retrieved findings
    #  - degraded : all search backends were rate-limited / returned nothing
    if status != "failed":
        if findings:
            status = "healthy"
        elif not any_backend_ok:
            status = "degraded"
            error = error or "All search backends rate-limited (no results)"
        else:
            status = "healthy"
    return findings, {"collector": "Search/Dorking", "status": status,
                      "error": error, "items_found": len(findings),
                      "duration_ms": int((time.time() - t0) * 1000)}


# ===========================================================================
# COLLECTOR: App Store (Google Play) -> look-alike mobile apps
# ===========================================================================
def _brand_terms(tenant):
    terms = set()
    for b in (tenant.get("brand_names") or [tenant.get("name")]):
        if b:
            terms.add(b.strip().lower())
    # also the primary domain label (e.g. "stripe" from stripe.com)
    for d in tenant.get("all_domains", [])[:1]:
        terms.add(d.split(".")[0].lower())
    return {t for t in terms if len(t) >= 3}


def collect_app_store(tenant, max_hits=12):
    t0 = time.time()
    findings, error, status = [], None, "healthy"
    try:
        from google_play_scraper import search
    except Exception as e:
        return [], {"collector": "Google Play", "status": "failed",
                    "error": f"scraper unavailable: {e}", "items_found": 0, "duration_ms": 0}
    brand = (tenant.get("brand_names") or [tenant.get("name")])[0]
    terms = _brand_terms(tenant)
    try:
        results = search(brand, n_hits=max_hits, lang="en", country="us")
        for r in results:
            title = (r.get("title") or "").strip()
            dev = (r.get("developer") or "").strip()
            app_id = r.get("appId")
            low_title = title.lower()
            low_dev = dev.lower()
            # only consider apps that reference the brand in the title
            if not any(term in low_title for term in terms):
                continue
            official = any(term in low_dev for term in terms)
            if official:
                score = 15  # likely first-party / authorized
                signature = "Matched"
                category = "Mobile App"
            else:
                score = 55  # brand in title but developer unrelated -> impersonation risk
                signature = "Unmatched"
                category = "Mobile App"
                low = low_title + " " + (r.get("summary") or "").lower()
                if any(w in low for w in ["wallet", "login", "bank", "pay", "free", "gift", "vip", "mod"]):
                    score += 20
            # brand-similarity ratio for evidence
            sim = int(difflib.SequenceMatcher(None, brand.lower(), low_title).ratio() * 100)
            score = min(score, 100)
            findings.append({
                "module": "mobile_app",
                "category": category,
                "source": "Google Play",
                "platform": "Google Play",
                "title": title or app_id or "Unknown app",
                "url": f"https://play.google.com/store/apps/details?id={app_id}" if app_id else "https://play.google.com",
                "domain": app_id or "",
                "risk_score": score,
                "severity": severity_from_score(score),
                "evidence": {"developer": dev, "app_id": app_id, "brand_similarity": sim,
                             "score": r.get("score"), "installs": r.get("installs"),
                             "summary": (r.get("summary") or "")[:200]},
                "entities": {
                    "app_name": title, "package_name": app_id, "developer": dev,
                    "store": "Google Play", "signature_status": signature,
                    "brand_similarity": sim, "version": r.get("version"),
                    "rating": r.get("score"), "unauthorized": "No" if official else "Yes",
                },
                "dedupe_key": _dedupe_key(tenant["id"], "mobile_app", app_id or title),
            })
    except Exception as e:
        error = str(e)
        status = "failed"
    return findings, {"collector": "Google Play", "status": status,
                      "error": error, "items_found": len(findings),
                      "duration_ms": int((time.time() - t0) * 1000)}


# ===========================================================================
# CHANGE WATCH helpers (content / DNS / certificate change detection)
# ===========================================================================
def fetch_content_hash(domain: str):
    for scheme in ("https", "http"):
        try:
            with httpx.Client(timeout=12, headers={"User-Agent": UA}, follow_redirects=True, verify=False) as c:
                r = c.get(f"{scheme}://{domain}")
                body = r.text or ""
                return {"hash": hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest(),
                        "status_code": r.status_code, "length": len(body),
                        "title": _extract_title(body)}
        except Exception:
            continue
    return None


def _extract_title(html):
    try:
        low = html.lower()
        i = low.find("<title")
        if i == -1:
            return None
        j = low.find(">", i)
        k = low.find("</title>", j)
        return html[j + 1:k].strip()[:120] if k > j else None
    except Exception:
        return None


def cert_fingerprint(domain: str):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((domain, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                der = ssock.getpeercert(binary_form=True)
                if not der:
                    return None
                return hashlib.sha256(der).hexdigest()
    except Exception:
        return None


def snapshot_site(domain: str):
    content = fetch_content_hash(domain)
    a_records = []
    try:
        res = _resolver()
        a_records = sorted([r.to_text() for r in res.resolve(domain, "A")])
    except Exception:
        pass
    return {
        "content_hash": content["hash"] if content else None,
        "content_title": content.get("title") if content else None,
        "http_status": content.get("status_code") if content else None,
        "dns_a": a_records,
        "cert_fp": cert_fingerprint(domain),
        "checked_at": now_iso(),
    }


def diff_snapshot(old, new):
    """Return dict of changed flags + human change list comparing two snapshots."""
    changes = []
    flags = {"content_changed": False, "dns_changed": False, "certificate_changed": False}
    if not old:
        return flags, changes
    if old.get("content_hash") and new.get("content_hash") and old["content_hash"] != new["content_hash"]:
        flags["content_changed"] = True
        changes.append({"type": "content", "detail": f"Page content changed (title: {new.get('content_title') or 'n/a'})", "ts": new["checked_at"]})
    if old.get("dns_a") and new.get("dns_a") and set(old["dns_a"]) != set(new["dns_a"]):
        flags["dns_changed"] = True
        changes.append({"type": "dns", "detail": f"A records {old['dns_a']} -> {new['dns_a']}", "ts": new["checked_at"]})
    if old.get("cert_fp") and new.get("cert_fp") and old["cert_fp"] != new["cert_fp"]:
        flags["certificate_changed"] = True
        changes.append({"type": "certificate", "detail": "TLS certificate rotated", "ts": new["checked_at"]})
    return flags, changes


# ===========================================================================
# Levenshtein distance (for strict typosquat matching)
# ===========================================================================
def _lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ===========================================================================
# Domain analysis -> suggest brand aliases + products
# ===========================================================================
def analyze_domain(domain: str):
    domain = (domain or "").strip().lower().replace("https://", "").replace("http://", "").strip("/")
    out = {"domain": domain, "brand_names": [], "products": [], "description": "",
           "social_handles": {}, "email_domains": [], "error": None}
    if not domain:
        out["error"] = "no domain"
        return out
    try:
        from bs4 import BeautifulSoup
        html = ""
        for scheme in ("https", "http"):
            try:
                with httpx.Client(timeout=15, headers={"User-Agent": UA}, follow_redirects=True, verify=False) as c:
                    r = c.get(f"{scheme}://{domain}")
                    html = r.text or ""
                    if html:
                        break
            except Exception:
                continue
        if not html:
            out["error"] = "could not fetch site"
            return out
        soup = BeautifulSoup(html, "html.parser")
        brands, products = [], []

        def add(lst, val, cap=8):
            val = (val or "").strip()
            if val and 2 <= len(val) <= 60 and val.lower() not in [x.lower() for x in lst] and len(lst) < cap:
                lst.append(val)

        # brand candidates
        og_site = soup.find("meta", property="og:site_name")
        if og_site:
            add(brands, og_site.get("content"))
        if soup.title and soup.title.string:
            t = soup.title.string.strip()
            # take the segment after common separators as the brand
            for sep in ["|", "-", "\u2013", "\u2014", ":"]:
                if sep in t:
                    parts = [p.strip() for p in t.split(sep) if p.strip()]
                    if parts:
                        add(brands, parts[-1])
                        add(brands, parts[0])
                    break
            else:
                add(brands, t)
        label = domain.split(".")[0]
        add(brands, label.capitalize())
        appn = soup.find("meta", attrs={"name": "application-name"})
        if appn:
            add(brands, appn.get("content"))

        # description
        md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
        if md:
            out["description"] = (md.get("content") or "")[:300]

        # product candidates derived from the description (comma / & separated)
        import re as _re
        desc = out["description"]
        if desc:
            # take the clause after words like 'provides/offers' if present
            m = _re.search(r"(?:provides|offers|manufactures|produces|special[a-z]*\s+in)\s+(.+)", desc, _re.I)
            clause = m.group(1) if m else desc
            for part in _re.split(r",|&|/| and ", clause):
                part = part.strip(" .;:")
                if 2 <= len(part) <= 40 and not part.lower().startswith(("we ", "a ", "the ", "our ")):
                    add(products, part, cap=14)

        # product candidates from nav / headings
        for h in soup.find_all(["h1", "h2"])[:20]:
            add(products, h.get_text(strip=True), cap=14)
        nav = soup.find("nav")
        anchors = (nav.find_all("a") if nav else [])[:25]
        skip = {"home", "about", "contact", "login", "sign in", "careers", "blog",
                "news", "investors", "privacy", "terms", "search", "menu", "support"}
        for a in anchors:
            txt = a.get_text(strip=True)
            if txt and txt.lower() not in skip and len(txt) <= 40:
                add(products, txt, cap=12)

        out["brand_names"] = brands
        out["products"] = products

        # ---- social handles + email domains from homepage links ----
        import re as _re2
        social_hosts = {
            "instagram": "instagram.com", "x": "x.com", "twitter": "twitter.com",
            "facebook": "facebook.com", "linkedin": "linkedin.com", "youtube": "youtube.com",
        }
        handles = {}
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            low = href.lower()
            for key, host in social_hosts.items():
                if host in low:
                    slug = low.split(host, 1)[1].strip("/").split("?")[0].split("#")[0].split("/")[0]
                    slug = slug.replace("@", "")
                    norm_key = "x" if key in ("x", "twitter") else key
                    bad = {"", "share", "sharer", "intent", "home", "login", "signup",
                           "watch", "channel", "embed", "playlist", "results", "feed",
                           "hashtag", "explore", "search", "about", "pages", "company",
                           "profile.php", "tr", "help", "privacy", "policies"}
                    if slug and slug not in bad and norm_key not in handles and 2 <= len(slug) <= 40:
                        handles[norm_key] = slug
        out["social_handles"] = handles

        # email domains from mailto links + inline text
        placeholder = {"example.com", "domain.com", "email.com", "yourdomain.com",
                       "sentry.io", "sentry-cdn.com", "w3.org", "schema.org",
                       "googleapis.com", "gstatic.com", "cloudflare.com"}
        emails = set()
        for a in soup.find_all("a", href=True):
            if a["href"].lower().startswith("mailto:"):
                addr = a["href"][7:].split("?")[0].strip()
                if "@" in addr:
                    emails.add(addr.split("@")[-1].lower())
        for m in _re2.findall(r"[\w.+-]+@([\w-]+\.[\w.-]+)", html):
            emails.add(m.lower())
        out["email_domains"] = sorted([e for e in emails if 3 <= len(e) <= 60 and e not in placeholder])[:6]
    except Exception as e:
        out["error"] = str(e)
    return out


# ===========================================================================
# Screenshot capture (Playwright headless) for social / web findings
# ===========================================================================
def capture_screenshot(url: str):
    """Return PNG bytes of the given public URL, or None on failure."""
    import os
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900},
                                        user_agent=UA)
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2500)
                png = page.screenshot(full_page=False, type="png")
                return png
            finally:
                browser.close()
    except Exception:
        return None


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================
COLLECTOR_REGISTRY = {
    "typosquat": collect_typosquat,
    "certificate_transparency": collect_crtsh,
    "rdap": collect_domain_intel,
    "dns": collect_dns,
    "search_dork": collect_search_dork,
    "app_store": collect_app_store,
}
