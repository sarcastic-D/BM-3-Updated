import os
import csv
import io
import re
import uuid
from xml.sax.saxutils import escape as _xml_escape
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from database import db, client
from auth import (
    get_current_user, require_roles, create_token, hash_password, verify_password,
    tenant_scope,
)
import collectors

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("brandmon")

app = FastAPI(title="Brand Monitoring Platform")
api = APIRouter(prefix="/api")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Default monitoring config template
# ---------------------------------------------------------------------------
DEFAULT_MONITORING = {
    "social": {"instagram": True, "facebook": True, "youtube": True, "linkedin": True,
               "x": True, "pinterest": False, "quora": False, "telegram": False},
    "domains": {"dorking": True, "certificate_transparency": True, "rdap": True,
                "dns": True, "content_monitoring": True, "typosquat": True},
    "mobile_apps": {"google_play": True, "apple_app_store": True, "apk_stores": True,
                    "signature_analysis": True},
    "meta_ads": True,
    "executive_monitoring": True,
    "email_impersonation": True,
}

DEFAULT_RISK_POLICY = {
    "critical_threshold": 80, "high_threshold": 60, "medium_threshold": 35,
    "similarity_threshold": 80, "alert_on_severity": "High",
}


def build_identity(brand_names, products, all_domains, existing=None):
    """Construct/normalise the Brand Identity Intelligence profile. Backward
    compatible: synthesises official_domains from the tenant's domains and keeps
    any admin-entered values."""
    idt = dict(existing or {})
    idt.setdefault("legal_name", "")
    idt.setdefault("trading_names", [])
    idt.setdefault("keywords", [])
    # official domains default to the tenant's configured domains
    if not idt.get("official_domains"):
        idt["official_domains"] = list(all_domains or [])
    idt.setdefault("redirect_domains", [])
    idt.setdefault("marketing_domains", [])
    idt.setdefault("regional_domains", [])
    sh = idt.get("social_handles") or {}
    for p in ("x", "instagram", "linkedin", "facebook", "youtube"):
        sh.setdefault(p, "")
    idt["social_handles"] = sh
    idt.setdefault("official_app_ids", [])
    idt.setdefault("email_domains", [])
    idt.setdefault("known_nameservers", [])
    idt.setdefault("known_ips", [])
    return idt


# ===========================================================================
# MODELS
# ===========================================================================
class LoginReq(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "analyst"
    tenant_ids: List[str] = []


class TenantCreate(BaseModel):
    name: str
    primary_domain: str
    additional_domains: List[str] = []
    brand_names: List[str] = []
    products: List[str] = []
    executives: List[str] = []
    industry: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = "UTC"
    status: str = "Active"
    identity: Optional[dict] = None


class CaseCreate(BaseModel):
    tenant_id: str
    title: str
    priority: str = "Medium"
    finding_ids: List[str] = []
    description: Optional[str] = ""


class SavedFilterCreate(BaseModel):
    screen: str
    name: str
    conditions: dict = {}


class PresetCreate(BaseModel):
    screen: str
    name: str
    conditions: dict = {}


# ===========================================================================
# AUDIT
# ===========================================================================
async def audit(actor, action, target="", detail=""):
    await db.audit_logs.insert_one({
        "id": new_id(), "actor": actor.get("name") if isinstance(actor, dict) else str(actor),
        "actor_email": actor.get("email") if isinstance(actor, dict) else "",
        "role": actor.get("role") if isinstance(actor, dict) else "",
        "action": action, "target": target, "detail": detail, "ts": now_iso(),
    })


# ===========================================================================
# AUTH ROUTES
# ===========================================================================
@api.post("/auth/login")
async def login(req: LoginReq):
    user = await db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") != "Active":
        raise HTTPException(status_code=403, detail="Account is inactive")
    token = create_token(user)
    await audit(user, "login", user["email"])
    safe = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    return {"token": token, "user": safe}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.get("/tools/analyze-domain")
async def analyze_domain_ep(domain: str, user: dict = Depends(require_roles("super_admin"))):
    """Fetch a domain and suggest brand aliases + products for the tenant wizard."""
    return await asyncio.to_thread(collectors.analyze_domain, domain)


# ===========================================================================
# USERS & RBAC
# ===========================================================================
@api.get("/users")
async def list_users(user: dict = Depends(require_roles("super_admin", "tenant_admin"))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


@api.post("/users")
async def create_user(body: UserCreate, user: dict = Depends(require_roles("super_admin", "tenant_admin"))):
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "id": new_id(), "email": body.email.lower(), "name": body.name,
        "password_hash": hash_password(body.password), "role": body.role,
        "tenant_ids": body.tenant_ids, "status": "Active", "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await audit(user, "create_user", body.email)
    return {k: v for k, v in doc.items() if k not in ("password_hash", "_id")}


@api.put("/users/{uid}")
async def update_user(uid: str, body: dict = Body(...), user: dict = Depends(require_roles("super_admin", "tenant_admin"))):
    upd = {k: v for k, v in body.items() if k in ("name", "role", "tenant_ids", "status")}
    if body.get("password"):
        upd["password_hash"] = hash_password(body["password"])
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit(user, "update_user", uid)
    return {"ok": True}


@api.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.users.delete_one({"id": uid})
    await audit(user, "delete_user", uid)
    return {"ok": True}


# ===========================================================================
# TENANTS
# ===========================================================================
def _tenant_public(t):
    return {k: v for k, v in t.items() if k != "_id"}


@api.get("/tenants")
async def list_tenants(
    status: Optional[str] = None, search: Optional[str] = None,
    monitoring_enabled: Optional[bool] = None,
    user: dict = Depends(get_current_user),
):
    q = {}
    scope = tenant_scope(user)
    if scope is not None:
        q["id"] = {"$in": scope}
    if status and status != "All":
        q["status"] = status
    if search:
        q["$or"] = [
            {"name": {"$regex": re.escape(search), "$options": "i"}},
            {"primary_domain": {"$regex": re.escape(search), "$options": "i"}},
            {"tenant_id": {"$regex": re.escape(search), "$options": "i"}},
        ]
    tenants = await db.tenants.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    if monitoring_enabled is not None:
        tenants = [t for t in tenants if t.get("monitoring_enabled", False) == monitoring_enabled]
    # attach lightweight counts
    for t in tenants:
        t["findings_count"] = await db.findings.count_documents({"tenant_id": t["id"]})
    return tenants


@api.post("/tenants")
async def create_tenant(body: TenantCreate, user: dict = Depends(require_roles("super_admin"))):
    tid = new_id()
    seq = await db.tenants.count_documents({}) + 1
    all_domains = [body.primary_domain] + [d for d in body.additional_domains if d]
    doc = {
        "id": tid, "tenant_id": f"TEN-{seq:04d}", "name": body.name,
        "primary_domain": body.primary_domain, "additional_domains": body.additional_domains,
        "all_domains": all_domains,
        "brand_names": body.brand_names or [body.name],
        "products": body.products, "executives": body.executives,
        "industry": body.industry, "country": body.country,
        "timezone": body.timezone, "status": body.status,
        "identity": build_identity(body.brand_names or [body.name], body.products,
                                   all_domains, body.identity),
        "monitoring_config": DEFAULT_MONITORING, "risk_policy": DEFAULT_RISK_POLICY,
        "notifications": {"email": "", "webhook": "", "alert_severity": "High"},
        "schedule": {"interval_hours": 24, "enabled": False},
        "monitoring_enabled": False, "wizard_step": 1, "wizard_complete": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.tenants.insert_one(doc)
    # Grant access to existing scoped users by default so the new tenant is
    # immediately visible to tenant admins / analysts / viewers. Admins can
    # later restrict access per-user via Users & RBAC.
    await db.users.update_many(
        {"role": {"$in": ["tenant_admin", "analyst", "viewer"]}},
        {"$addToSet": {"tenant_ids": tid}})
    await audit(user, "create_tenant", body.name)
    return _tenant_public(doc)


@api.get("/tenants/{tid}")
async def get_tenant(tid: str, user: dict = Depends(get_current_user)):
    scope = tenant_scope(user)
    if scope is not None and tid not in scope:
        raise HTTPException(status_code=403, detail="No access to tenant")
    t = await db.tenants.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # backward-compat: synthesise an identity profile for older tenants
    if not t.get("identity"):
        t["identity"] = build_identity(t.get("brand_names") or [t.get("name")],
                                       t.get("products") or [], t.get("all_domains") or [])
    t.setdefault("executives", [])
    return t


@api.put("/tenants/{tid}")
async def update_tenant(tid: str, body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    body["updated_at"] = now_iso()
    if "primary_domain" in body or "additional_domains" in body:
        t = await db.tenants.find_one({"id": tid})
        pd = body.get("primary_domain", t.get("primary_domain"))
        ad = body.get("additional_domains", t.get("additional_domains", []))
        body["all_domains"] = [pd] + [d for d in ad if d]
    if "identity" in body and isinstance(body["identity"], dict):
        body["identity"] = build_identity(
            body.get("brand_names") or [], body.get("products") or [],
            body.get("all_domains") or [], body["identity"])
    allowed = {"name", "primary_domain", "additional_domains", "all_domains", "brand_names",
               "products", "executives", "identity", "industry", "country", "timezone",
               "status", "monitoring_config", "risk_policy", "notifications", "schedule",
               "monitoring_enabled", "wizard_step", "wizard_complete"}
    upd = {k: v for k, v in body.items() if k in allowed or k == "updated_at"}
    await db.tenants.update_one({"id": tid}, {"$set": upd})
    await audit(user, "update_tenant", tid, ",".join(upd.keys()))
    t = await db.tenants.find_one({"id": tid}, {"_id": 0})
    return t


@api.post("/tenants/{tid}/activate")
async def activate_tenant(tid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.tenants.update_one({"id": tid}, {"$set": {
        "monitoring_enabled": True, "wizard_complete": True, "status": "Active",
        "updated_at": now_iso()}})
    await audit(user, "activate_tenant", tid)
    return {"ok": True}


@api.delete("/tenants/{tid}")
async def delete_tenant(tid: str, user: dict = Depends(require_roles("super_admin"))):
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0, "name": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # cascade delete all tenant-scoped data
    findings_del = (await db.findings.delete_many({"tenant_id": tid})).deleted_count
    cases_del = (await db.cases.delete_many({"tenant_id": tid})).deleted_count
    await db.collector_health.delete_many({"tenant_id": tid})
    await db.tenants.delete_one({"id": tid})
    # revoke the tenant from any users' access lists
    await db.users.update_many({"tenant_ids": tid}, {"$pull": {"tenant_ids": tid}})
    await audit(user, "delete_tenant", tenant["name"],
                f"{findings_del} findings, {cases_del} cases removed")
    return {"ok": True, "deleted_findings": findings_del, "deleted_cases": cases_del}


# ===========================================================================
# MONITORING RUN (collectors)
# ===========================================================================
async def _upsert_finding(f, tenant_id):
    existing = await db.findings.find_one({"dedupe_key": f["dedupe_key"]})
    ts = now_iso()
    if existing:
        await db.findings.update_one({"dedupe_key": f["dedupe_key"]}, {"$set": {
            "last_seen": ts, "risk_score": f["risk_score"], "severity": f["severity"],
            "evidence": f["evidence"], "entities": f["entities"]}})
        return False
    doc = {
        "id": new_id(), "tenant_id": tenant_id, "status": "Open",
        "assigned_analyst": None, "case_id": None,
        "first_seen": ts, "last_seen": ts, "created_at": ts,
        **f,
    }
    await db.findings.insert_one(doc)
    return True


COLLECTOR_NAMES = {
    "typosquat": "Typosquat", "certificate_transparency": "Certificate Transparency",
    "rdap": "RDAP", "dns": "DNS", "search_dork": "Search/Dorking",
    "app_store": "App Store", "change_watch": "Change Watch",
}

# tenants with an in-flight scan, so overlapping "Run Now" calls are skipped
# instead of piling blocking collector work onto the thread pool
_RUNNING_SCANS = set()


async def _run_collectors(tenant, which=None):
    cfg = tenant.get("monitoring_config", DEFAULT_MONITORING)
    plan = []
    dom = cfg.get("domains", {})
    if dom.get("typosquat"):
        plan.append("typosquat")
    if dom.get("certificate_transparency"):
        plan.append("certificate_transparency")
    if dom.get("rdap"):
        plan.append("rdap")
    if dom.get("dns"):
        plan.append("dns")
    if cfg.get("social") and any(cfg["social"].values()):
        plan.append("search_dork")
    if cfg.get("mobile_apps", {}).get("google_play"):
        plan.append("app_store")
    if which:
        plan = [c for c in plan if c == which]

    total_new = 0
    for cname in plan:
        fn = collectors.COLLECTOR_REGISTRY.get(cname)
        if not fn:
            continue
        await db.collector_health.update_one(
            {"tenant_id": tenant["id"], "collector_key": cname},
            {"$set": {"status": "running", "collector": COLLECTOR_NAMES.get(cname, cname),
                      "started_at": now_iso()}}, upsert=True)
        try:
            findings, health = await asyncio.to_thread(fn, tenant)
        except Exception as e:
            findings, health = [], {"collector": cname, "status": "failed", "error": str(e),
                                    "items_found": 0, "duration_ms": 0}
        new_count = 0
        for f in findings:
            if await _upsert_finding(f, tenant["id"]):
                new_count += 1
        total_new += new_count
        await db.collector_health.update_one(
            {"tenant_id": tenant["id"], "collector_key": cname},
            {"$set": {
                "tenant_id": tenant["id"], "collector_key": cname,
                "collector": health["collector"], "status": health["status"],
                "error": health.get("error"), "items_found": health.get("items_found", 0),
                "new_findings": new_count, "duration_ms": health.get("duration_ms", 0),
                "last_run": now_iso(),
                "last_success": now_iso() if health["status"] != "failed" else None,
            }}, upsert=True)
    # ---- Change Watch pass (content / DNS / certificate drift on fake sites) ----
    if (cfg.get("domains", {}).get("content_monitoring")) and (not which or which == "change_watch"):
        await _run_change_watch(tenant)

    await db.tenants.update_one({"id": tenant["id"]}, {"$set": {"last_scan": now_iso()}})
    logger.info(f"Run complete for {tenant['name']}: {total_new} new findings")
    return total_new


async def _run_change_watch(tenant, limit=20):
    t0 = datetime.now(timezone.utc)
    error, checked, changed = None, 0, 0
    await db.collector_health.update_one(
        {"tenant_id": tenant["id"], "collector_key": "change_watch"},
        {"$set": {"status": "running", "collector": "Change Watch", "started_at": now_iso()}}, upsert=True)
    try:
        findings = await db.findings.find(
            {"tenant_id": tenant["id"], "module": "fake_website"}, {"_id": 0}
        ).sort("risk_score", -1).limit(limit).to_list(limit)
        for f in findings:
            domain = f.get("domain")
            if not domain:
                continue
            new_snap = await asyncio.to_thread(collectors.snapshot_site, domain)
            checked += 1
            old_snap = f.get("snapshot")
            flags, change_list = collectors.diff_snapshot(old_snap, new_snap)
            update = {"snapshot": new_snap, "last_seen": now_iso()}
            ent = f.get("entities", {})
            ent.update(flags)
            update["entities"] = ent
            set_ops = {"$set": update}
            if change_list:
                changed += 1
                new_score = min(int(f.get("risk_score", 40)) + 10, 100)
                update["risk_score"] = new_score
                from collectors import severity_from_score
                update["severity"] = severity_from_score(new_score)
                set_ops["$push"] = {"changes": {"$each": change_list}}
            await db.findings.update_one({"id": f["id"]}, set_ops)
        status = "healthy"
    except Exception as e:
        error = str(e); status = "failed"
    dur = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    await db.collector_health.update_one(
        {"tenant_id": tenant["id"], "collector_key": "change_watch"},
        {"$set": {"tenant_id": tenant["id"], "collector_key": "change_watch",
                  "collector": "Change Watch", "status": status, "error": error,
                  "items_found": checked, "new_findings": changed, "duration_ms": dur,
                  "last_run": now_iso(), "last_success": now_iso() if status != "failed" else None}},
        upsert=True)


@api.post("/tenants/{tid}/run")
async def run_now(tid: str, collector: Optional[str] = None,
                  user: dict = Depends(require_roles("super_admin", "tenant_admin", "analyst"))):
    tenant = await db.tenants.find_one({"id": tid}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await audit(user, "run_collectors", tenant["name"], collector or "all")
    if tid in _RUNNING_SCANS:
        return {"ok": True, "message": "A scan is already running for this tenant", "tenant": tenant["name"]}
    _RUNNING_SCANS.add(tid)

    async def _bg():
        try:
            await _run_collectors(tenant, collector)
        finally:
            _RUNNING_SCANS.discard(tid)

    # run in background so the request returns quickly
    asyncio.create_task(_bg())
    return {"ok": True, "message": "Monitoring run started", "tenant": tenant["name"]}


# ===========================================================================
# FINDINGS + GLOBAL FILTER ENGINE
# ===========================================================================
SEV_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def build_findings_query(params, user):
    q = {}
    scope = tenant_scope(user)
    if scope is not None:
        q["tenant_id"] = {"$in": scope}
    p = params
    if p.get("tenant_id") and p["tenant_id"] != "All":
        if scope is not None and p["tenant_id"] not in scope:
            q["tenant_id"] = {"$in": []}
        else:
            q["tenant_id"] = p["tenant_id"]
    if p.get("module") and p["module"] != "All":
        q["module"] = p["module"]
    if p.get("category") and p["category"] != "All":
        q["category"] = p["category"]
    if p.get("source") and p["source"] != "All":
        q["source"] = p["source"]
    if p.get("platform") and p["platform"] != "All":
        # case-insensitive exact match so ?platform=instagram matches "Instagram"
        q["platform"] = {"$regex": f"^{re.escape(p['platform'])}$", "$options": "i"}
    if p.get("severity") and p["severity"] != "All":
        q["severity"] = p["severity"]
    if p.get("status") and p["status"] != "All":
        q["status"] = p["status"]
    rmin = p.get("risk_min")
    rmax = p.get("risk_max")
    if rmin is not None or rmax is not None:
        q["risk_score"] = {}
        if rmin is not None:
            q["risk_score"]["$gte"] = int(rmin)
        if rmax is not None:
            q["risk_score"]["$lte"] = int(rmax)
    if p.get("date_from") or p.get("date_to"):
        q["first_seen"] = {}
        if p.get("date_from"):
            q["first_seen"]["$gte"] = p["date_from"]
        if p.get("date_to"):
            q["first_seen"]["$lte"] = p["date_to"] + "T23:59:59"
    if p.get("assigned_analyst") and p["assigned_analyst"] != "All":
        q["assigned_analyst"] = p["assigned_analyst"]
    if p.get("has_case") == "yes":
        q["case_id"] = {"$ne": None}
    elif p.get("has_case") == "no":
        q["case_id"] = None
    # entity-level filters
    entity_map = ["registrar", "tld", "country", "domain_status", "signature_status",
                  "account_type", "certificate_issuer", "ad_type", "unauthorized",
                  "impersonation_classification", "typo_kind", "infra_suspicious"]
    for ef in entity_map:
        val = p.get(ef)
        if val and val != "All":
            q[f"entities.{ef}"] = val
    for bf in ["content_changed", "dns_changed", "certificate_changed"]:
        if p.get(bf) in ("yes", "no"):
            q[f"entities.{bf}"] = (p[bf] == "yes")
    if p.get("search"):
        rx = {"$regex": re.escape(p["search"]), "$options": "i"}
        q["$or"] = [{"title": rx}, {"url": rx}, {"domain": rx},
                    {"entities.username": rx}, {"entities.display_name": rx}]
    return q


def parse_common(request_args):
    return request_args


@api.get("/findings")
async def list_findings(
    tenant_id: Optional[str] = None, module: Optional[str] = None, category: Optional[str] = None,
    source: Optional[str] = None, platform: Optional[str] = None, severity: Optional[str] = None,
    status: Optional[str] = None, risk_min: Optional[int] = None, risk_max: Optional[int] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    assigned_analyst: Optional[str] = None, has_case: Optional[str] = None,
    registrar: Optional[str] = None, tld: Optional[str] = None, country: Optional[str] = None,
    domain_status: Optional[str] = None, signature_status: Optional[str] = None,
    account_type: Optional[str] = None, certificate_issuer: Optional[str] = None,
    unauthorized: Optional[str] = None, ad_type: Optional[str] = None,
    impersonation_classification: Optional[str] = None, typo_kind: Optional[str] = None,
    infra_suspicious: Optional[str] = None,
    content_changed: Optional[str] = None, dns_changed: Optional[str] = None,
    certificate_changed: Optional[str] = None, search: Optional[str] = None,
    sort_by: str = "first_seen", sort_dir: str = "desc",
    page: int = 1, page_size: int = 25,
    user: dict = Depends(get_current_user),
):
    params = {k: v for k, v in locals().items() if k not in ("user",)}
    q = build_findings_query(params, user)
    total = await db.findings.count_documents(q)
    direction = -1 if sort_dir == "desc" else 1
    cursor = db.findings.find(q, {"_id": 0})
    if sort_by == "severity":
        docs = await cursor.to_list(5000)
        docs.sort(key=lambda d: SEV_ORDER.get(d.get("severity"), 0), reverse=(direction == -1))
        docs = docs[(page - 1) * page_size: page * page_size]
    else:
        docs = await cursor.sort(sort_by, direction).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": docs}


@api.get("/findings/facets")
async def findings_facets(tenant_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    scope = tenant_scope(user)
    if scope is not None:
        q["tenant_id"] = {"$in": scope}
    if tenant_id and tenant_id != "All":
        q["tenant_id"] = tenant_id
    facets = {}
    for field in ["source", "platform", "category"]:
        facets[field] = await db.findings.distinct(field, q)
    for ef in ["registrar", "tld", "country", "certificate_issuer"]:
        vals = await db.findings.distinct(f"entities.{ef}", q)
        facets[ef] = [v for v in vals if v]
    return facets


@api.get("/findings/export")
async def export_findings(
    tenant_id: Optional[str] = None, module: Optional[str] = None, category: Optional[str] = None,
    source: Optional[str] = None, platform: Optional[str] = None, severity: Optional[str] = None,
    status: Optional[str] = None, risk_min: Optional[int] = None, risk_max: Optional[int] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None, search: Optional[str] = None,
    impersonation_classification: Optional[str] = None, typo_kind: Optional[str] = None,
    infra_suspicious: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    params = {k: v for k, v in locals().items() if k not in ("user",)}
    q = build_findings_query(params, user)
    docs = await db.findings.find(q, {"_id": 0}).limit(5000).to_list(5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Title", "Category", "Module", "Source", "Platform", "Severity",
                "Risk Score", "Status", "Domain", "URL", "First Seen", "Last Seen"])
    for d in docs:
        w.writerow([d.get("title"), d.get("category"), d.get("module"), d.get("source"),
                    d.get("platform"), d.get("severity"), d.get("risk_score"), d.get("status"),
                    d.get("domain"), d.get("url"), d.get("first_seen"), d.get("last_seen")])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=findings.csv"})


@api.get("/findings/report.pdf")
async def report_pdf(
    tenant_id: Optional[str] = None, module: Optional[str] = None, category: Optional[str] = None,
    source: Optional[str] = None, platform: Optional[str] = None, severity: Optional[str] = None,
    status: Optional[str] = None, risk_min: Optional[int] = None, risk_max: Optional[int] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None, search: Optional[str] = None,
    impersonation_classification: Optional[str] = None, typo_kind: Optional[str] = None,
    infra_suspicious: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    params = {k: v for k, v in locals().items() if k not in ("user",)}
    q = build_findings_query(params, user)
    docs = await db.findings.find(q, {"_id": 0}).sort("risk_score", -1).limit(500).to_list(500)

    # resolve tenant name + counts
    tname = "All Tenants"
    if tenant_id and tenant_id != "All":
        t = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "name": 1})
        tname = t["name"] if t else tenant_id
    sev_counts = {s: sum(1 for d in docs if d.get("severity") == s) for s in ["Critical", "High", "Medium", "Low"]}

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=14 * mm, rightMargin=14 * mm, title="Brand Monitoring Report")
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#0e7490")
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=brand, fontSize=20, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.5, leading=9)
    story = []

    story.append(Paragraph("BrandShield \u2014 Digital Risk Protection Report", h1))
    story.append(Paragraph(f"Tenant: <b>{_xml_escape(str(tname))}</b> &nbsp;&nbsp; Generated: {now_iso()[:19].replace('T', ' ')} UTC &nbsp;&nbsp; Prepared by: {_xml_escape(str(user['name']))}", sub))
    story.append(Spacer(1, 8))

    # filter snapshot
    applied = {k: v for k, v in params.items() if v not in (None, "", "All") and k not in ("tenant_id",)}
    fstr = ", ".join(f"{k}={v}" for k, v in applied.items()) or "None (all findings)"
    story.append(Paragraph(f"<b>Filters applied:</b> {_xml_escape(fstr)}", sub))
    story.append(Spacer(1, 10))

    # summary band
    summ = [["Total", "Critical", "High", "Medium", "Low"],
            [str(len(docs)), str(sev_counts["Critical"]), str(sev_counts["High"]), str(sev_counts["Medium"]), str(sev_counts["Low"])]]
    st = Table(summ, colWidths=[36 * mm] * 5)
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(st)
    story.append(Spacer(1, 12))

    sev_color = {"Critical": colors.HexColor("#dc2626"), "High": colors.HexColor("#ea580c"),
                 "Medium": colors.HexColor("#d97706"), "Low": colors.HexColor("#16a34a")}
    header = ["Finding", "Category", "Platform", "Sev", "Risk", "Status", "First Seen"]
    data = [header]
    for d in docs[:200]:
        data.append([
            Paragraph(_xml_escape((d.get("title") or "")[:60]), cell),
            Paragraph(_xml_escape(d.get("category") or ""), cell),
            Paragraph(_xml_escape(d.get("platform") or ""), cell),
            d.get("severity") or "", str(d.get("risk_score") or ""),
            d.get("status") or "", (d.get("first_seen") or "")[:10],
        ])
    tbl = Table(data, colWidths=[52 * mm, 26 * mm, 22 * mm, 16 * mm, 12 * mm, 18 * mm, 22 * mm], repeatRows=1)
    tstyle = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, d in enumerate(docs[:200], start=1):
        c = sev_color.get(d.get("severity"), colors.black)
        tstyle.append(("TEXTCOLOR", (3, i), (3, i), c))
        tstyle.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(tstyle))
    story.append(tbl)
    if len(docs) > 200:
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Showing top 200 of {len(docs)} findings by risk score.", sub))

    doc.build(story)
    buf.seek(0)
    await audit(user, "export_pdf_report", tname, fstr)
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=brand-monitoring-report.pdf"})



@api.get("/findings/{fid}")
async def get_finding(fid: str, user: dict = Depends(get_current_user)):
    f = await db.findings.find_one({"id": fid}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    scope = tenant_scope(user)
    if scope is not None and f["tenant_id"] not in scope:
        raise HTTPException(status_code=403, detail="No access")
    if f.get("case_id"):
        f["case"] = await db.cases.find_one({"id": f["case_id"]}, {"_id": 0})
    return f


@api.put("/findings/{fid}")
async def update_finding(fid: str, body: dict = Body(...),
                         user: dict = Depends(require_roles("super_admin", "tenant_admin", "analyst"))):
    upd = {k: v for k, v in body.items() if k in ("status", "assigned_analyst", "severity", "risk_score", "notes")}
    await db.findings.update_one({"id": fid}, {"$set": upd})
    await audit(user, "update_finding", fid, ",".join(upd.keys()))
    return await db.findings.find_one({"id": fid}, {"_id": 0})


MEDIA_ROOT = "/app/backend/media"


@api.post("/findings/{fid}/screenshot")
async def capture_finding_screenshot(fid: str,
                                     user: dict = Depends(require_roles("super_admin", "tenant_admin", "analyst"))):
    f = await db.findings.find_one({"id": fid}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    target = f.get("url")
    if not target or not target.startswith("http"):
        raise HTTPException(status_code=400, detail="No capturable URL for this finding")
    png = await asyncio.to_thread(collectors.capture_screenshot, target)
    if not png:
        raise HTTPException(status_code=502, detail="Screenshot capture failed (page may block automated access)")
    shot_dir = os.path.join(MEDIA_ROOT, "screenshots")
    os.makedirs(shot_dir, exist_ok=True)
    with open(os.path.join(shot_dir, f"{fid}.png"), "wb") as fh:
        fh.write(png)
    surl = f"/api/media/screenshots/{fid}.png"
    await db.findings.update_one({"id": fid}, {"$set": {
        "entities.screenshot_url": surl, "screenshot_captured_at": now_iso()}})
    await audit(user, "capture_screenshot", fid, target)
    return {"screenshot_url": surl}


# ===========================================================================
# CASES
# ===========================================================================
@api.get("/cases")
async def list_cases(tenant_id: Optional[str] = None, status: Optional[str] = None,
                     search: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    scope = tenant_scope(user)
    if scope is not None:
        q["tenant_id"] = {"$in": scope}
    if tenant_id and tenant_id != "All":
        q["tenant_id"] = tenant_id
    if status and status != "All":
        q["status"] = status
    if search:
        q["title"] = {"$regex": re.escape(search), "$options": "i"}
    cases = await db.cases.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return cases


@api.post("/cases")
async def create_case(body: CaseCreate, user: dict = Depends(require_roles("super_admin", "tenant_admin", "analyst"))):
    cid = new_id()
    seq = await db.cases.count_documents({}) + 1
    doc = {
        "id": cid, "case_number": f"CASE-{seq:04d}", "tenant_id": body.tenant_id,
        "title": body.title, "status": "Open", "priority": body.priority,
        "assigned_to": user["name"], "finding_ids": body.finding_ids,
        "description": body.description, "notes": [], "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.cases.insert_one(doc)
    if body.finding_ids:
        await db.findings.update_many({"id": {"$in": body.finding_ids}}, {"$set": {"case_id": cid}})
    await audit(user, "create_case", body.title)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.get("/cases/{cid}")
async def get_case(cid: str, user: dict = Depends(get_current_user)):
    c = await db.cases.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    c["findings"] = await db.findings.find({"id": {"$in": c.get("finding_ids", [])}}, {"_id": 0}).to_list(500)
    return c


@api.put("/cases/{cid}")
async def update_case(cid: str, body: dict = Body(...),
                      user: dict = Depends(require_roles("super_admin", "tenant_admin", "analyst"))):
    upd = {k: v for k, v in body.items() if k in ("status", "priority", "assigned_to", "title", "description")}
    upd["updated_at"] = now_iso()
    if body.get("note"):
        await db.cases.update_one({"id": cid}, {"$push": {"notes": {
            "author": user["name"], "text": body["note"], "ts": now_iso()}}})
    if body.get("add_finding_ids"):
        await db.cases.update_one({"id": cid}, {"$addToSet": {"finding_ids": {"$each": body["add_finding_ids"]}}})
        await db.findings.update_many({"id": {"$in": body["add_finding_ids"]}}, {"$set": {"case_id": cid}})
    await db.cases.update_one({"id": cid}, {"$set": upd})
    await audit(user, "update_case", cid)
    return await db.cases.find_one({"id": cid}, {"_id": 0})


# ===========================================================================
# DASHBOARD
# ===========================================================================
@api.get("/dashboard/stats")
async def dashboard_stats(tenant_id: Optional[str] = None, platform: Optional[str] = None,
                          severity: Optional[str] = None, days: int = 30,
                          user: dict = Depends(get_current_user)):
    base = {}
    scope = tenant_scope(user)
    if scope is not None:
        base["tenant_id"] = {"$in": scope}
    if tenant_id and tenant_id != "All":
        base["tenant_id"] = tenant_id
    if platform and platform != "All":
        base["platform"] = platform
    if severity and severity != "All":
        base["severity"] = severity
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    async def count(extra):
        q = dict(base); q.update(extra); return await db.findings.count_documents(q)

    cards = {
        "critical": await count({"severity": "Critical"}),
        "high": await count({"severity": "High"}),
        "medium": await count({"severity": "Medium"}),
        "low": await count({"severity": "Low"}),
        "new_domains": await count({"module": {"$in": ["fake_website", "domain_intel"]}, "first_seen": {"$gte": since}}),
        "fake_social": await count({"module": "social", "category": "Impersonation"}),
        "fake_apps": await count({"module": "mobile_app"}),
        "unauthorized_ads": await count({"module": "meta_ads"}),
        "executive_alerts": await count({"module": "executive"}),
        "total": await count({}),
        "open_cases": await db.cases.count_documents({**({"tenant_id": base["tenant_id"]} if "tenant_id" in base and isinstance(base["tenant_id"], str) else {}), "status": {"$ne": "Closed"}}),
    }
    # severity distribution
    sev_dist = [{"name": s, "value": await count({"severity": s})} for s in ["Critical", "High", "Medium", "Low"]]
    # by module
    mods = ["fake_website", "domain_intel", "social", "mobile_app", "executive", "telegram", "meta_ads"]
    by_module = [{"name": m, "value": await count({"module": m})} for m in mods]
    # top sources
    src_pipe = [{"$match": base}, {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 6}]
    top_sources = [{"name": r["_id"], "value": r["count"]} async for r in db.findings.aggregate(src_pipe)]
    # timeline last N days
    timeline = []
    for i in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        q = dict(base); q["first_seen"] = {"$gte": day, "$lte": day + "T23:59:59"}
        timeline.append({"date": day[5:], "count": await db.findings.count_documents(q)})
    return {"cards": cards, "severity_distribution": sev_dist, "by_module": by_module,
            "top_sources": top_sources, "timeline": timeline}


# ===========================================================================
# MONITORING HEALTH
# ===========================================================================
@api.get("/monitoring-health")
async def monitoring_health(tenant_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    scope = tenant_scope(user)
    tenants = await db.tenants.find(({"id": {"$in": scope}} if scope is not None else {}), {"_id": 0}).to_list(500)
    tmap = {t["id"]: t["name"] for t in tenants}
    if tenant_id and tenant_id != "All":
        q["tenant_id"] = tenant_id
    elif scope is not None:
        q["tenant_id"] = {"$in": scope}
    rows = await db.collector_health.find(q, {"_id": 0}).to_list(1000)
    for r in rows:
        r["tenant_name"] = tmap.get(r["tenant_id"], r["tenant_id"])
    return rows


# ===========================================================================
# SAVED FILTERS & PRESETS
# ===========================================================================
@api.get("/saved-filters")
async def get_saved_filters(screen: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"user_id": user["id"]}
    if screen:
        q["screen"] = screen
    return await db.saved_filters.find(q, {"_id": 0}).to_list(200)


@api.post("/saved-filters")
async def create_saved_filter(body: SavedFilterCreate, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "user_id": user["id"], "screen": body.screen,
           "name": body.name, "conditions": body.conditions, "created_at": now_iso()}
    await db.saved_filters.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.delete("/saved-filters/{sid}")
async def delete_saved_filter(sid: str, user: dict = Depends(get_current_user)):
    await db.saved_filters.delete_one({"id": sid, "user_id": user["id"]})
    return {"ok": True}


@api.get("/presets")
async def get_presets(screen: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if screen:
        q["screen"] = screen
    return await db.presets.find(q, {"_id": 0}).to_list(200)


@api.post("/presets")
async def create_preset(body: PresetCreate, user: dict = Depends(require_roles("super_admin"))):
    doc = {"id": new_id(), "screen": body.screen, "name": body.name,
           "conditions": body.conditions, "is_global": True, "created_at": now_iso()}
    await db.presets.insert_one(doc)
    await audit(user, "create_preset", body.name)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.delete("/presets/{pid}")
async def delete_preset(pid: str, user: dict = Depends(require_roles("super_admin"))):
    await db.presets.delete_one({"id": pid})
    return {"ok": True}


# ===========================================================================
# CONFIG SURFACES (intelligence sources, detection, notifications, system)
# ===========================================================================
async def _get_config(key, default):
    doc = await db.app_config.find_one({"key": key}, {"_id": 0})
    return doc["value"] if doc else default


@api.get("/intelligence-sources")
async def get_intel_sources(user: dict = Depends(require_roles("super_admin"))):
    return await _get_config("intelligence_sources", {
        "search_providers": {"duckduckgo": {"enabled": True, "rate_limit": 30, "status": "connected"}},
        "certificate_transparency": {"provider": "crt.sh", "enabled": True, "status": "connected"},
        "rdap": {"provider": "rdap.org", "enabled": True, "status": "connected"},
        "dns": {"resolvers": ["8.8.8.8", "1.1.1.1"], "enabled": True, "status": "connected"},
        "social_apis": {"enabled": False, "status": "not_configured"},
        "telegram_apis": {"enabled": False, "status": "not_configured"},
        "app_stores": {"provider": "Google Play (scraper)", "enabled": True, "status": "connected"},
        "meta_apis": {"enabled": False, "status": "not_configured"},
    })


@api.put("/intelligence-sources")
async def put_intel_sources(body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    await db.app_config.update_one({"key": "intelligence_sources"}, {"$set": {"key": "intelligence_sources", "value": body}}, upsert=True)
    await audit(user, "update_intelligence_sources")
    return body


@api.get("/detection-config")
async def get_detection(user: dict = Depends(require_roles("super_admin"))):
    return await _get_config("detection_config", {
        "risk_rules": [
            {"name": "New typosquat domain", "condition": "domain_age < 90d", "score": 25, "enabled": True},
            {"name": "Domain with MX records", "condition": "has_mx", "score": 15, "enabled": True},
            {"name": "Homoglyph domain", "condition": "homoglyph", "score": 12, "enabled": True},
            {"name": "Data exposure keyword", "condition": "paste_site_hit", "score": 65, "enabled": True},
        ],
        "similarity_thresholds": {"domain": 80, "brand": 80, "app": 80},
        "alert_thresholds": {"critical": 80, "high": 60, "medium": 35},
        "keyword_rules": ["login", "verify", "gift", "giveaway", "support", "free"],
        "allow_list": [],
        "ignore_list": [],
    })


@api.put("/detection-config")
async def put_detection(body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    await db.app_config.update_one({"key": "detection_config"}, {"$set": {"key": "detection_config", "value": body}}, upsert=True)
    await audit(user, "update_detection_config")
    return body


@api.get("/notifications-config")
async def get_notif(user: dict = Depends(require_roles("super_admin"))):
    return await _get_config("notifications", {
        "channels": [
            {"type": "email", "target": "", "enabled": False, "min_severity": "High"},
            {"type": "webhook", "target": "", "enabled": False, "min_severity": "Critical"},
            {"type": "slack", "target": "", "enabled": False, "min_severity": "Critical"},
        ]
    })


@api.put("/notifications-config")
async def put_notif(body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    await db.app_config.update_one({"key": "notifications"}, {"$set": {"key": "notifications", "value": body}}, upsert=True)
    await audit(user, "update_notifications")
    return body


@api.get("/system-settings")
async def get_system(user: dict = Depends(require_roles("super_admin"))):
    return await _get_config("system_settings", {
        "retention_days": 365, "default_scan_interval_hours": 24,
        "environment": "Production", "max_findings_per_run": 500,
        "data_residency": "Global",
    })


@api.put("/system-settings")
async def put_system(body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    await db.app_config.update_one({"key": "system_settings"}, {"$set": {"key": "system_settings", "value": body}}, upsert=True)
    await audit(user, "update_system_settings")
    return body


# ===========================================================================
# SCHEDULER
# ===========================================================================
@api.get("/schedules")
async def get_schedules(user: dict = Depends(require_roles("super_admin", "tenant_admin"))):
    tenants = await db.tenants.find({}, {"_id": 0, "id": 1, "name": 1, "schedule": 1, "monitoring_enabled": 1, "last_scan": 1}).to_list(500)
    return tenants


@api.put("/schedules/{tid}")
async def update_schedule(tid: str, body: dict = Body(...), user: dict = Depends(require_roles("super_admin"))):
    await db.tenants.update_one({"id": tid}, {"$set": {"schedule": body}})
    await audit(user, "update_schedule", tid)
    return {"ok": True}


# ===========================================================================
# AUDIT LOGS
# ===========================================================================
@api.get("/audit-logs")
async def get_audit_logs(action: Optional[str] = None, search: Optional[str] = None,
                         page: int = 1, page_size: int = 50,
                         user: dict = Depends(require_roles("super_admin", "tenant_admin"))):
    q = {}
    if action and action != "All":
        q["action"] = action
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        q["$or"] = [{"actor": rx}, {"target": rx}, {"action": rx}]
    total = await db.audit_logs.count_documents(q)
    docs = await db.audit_logs.find(q, {"_id": 0}).sort("ts", -1).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"total": total, "items": docs}


# ===========================================================================
# STARTUP: seed
# ===========================================================================
async def _initial_scan():
    # if no findings yet, run collectors for enabled tenants once (real data bootstrap)
    if await db.findings.count_documents({}) > 0:
        return
    tenants = await db.tenants.find({"monitoring_enabled": True}, {"_id": 0}).to_list(50)
    for t in tenants:
        try:
            await _run_collectors(t)
        except Exception as e:
            logger.error(f"Initial scan failed for {t.get('name')}: {e}")


@app.on_event("startup")
async def startup():
    from seed import seed_all
    await seed_all(db)
    asyncio.create_task(_initial_scan())


@app.on_event("shutdown")
async def shutdown():
    client.close()


os.makedirs(os.path.join(MEDIA_ROOT, "screenshots"), exist_ok=True)
app.mount("/api/media", StaticFiles(directory=MEDIA_ROOT), name="media")
app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)
