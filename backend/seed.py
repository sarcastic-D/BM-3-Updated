"""Seed users, demo tenants, presets. Idempotent."""
import uuid
from datetime import datetime, timezone

import bcrypt


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def nid():
    return str(uuid.uuid4())


DEFAULT_MONITORING = {
    "social": {"instagram": True, "facebook": True, "youtube": True, "linkedin": True,
               "x": True, "pinterest": False, "quora": False, "telegram": False},
    "domains": {"dorking": True, "certificate_transparency": True, "rdap": True,
                "dns": True, "content_monitoring": True, "typosquat": True},
    "mobile_apps": {"google_play": True, "apple_app_store": True, "apk_stores": True,
                    "signature_analysis": True},
    "meta_ads": True, "executive_monitoring": True, "email_impersonation": True,
}
DEFAULT_RISK = {"critical_threshold": 80, "high_threshold": 60, "medium_threshold": 35,
                "similarity_threshold": 80, "alert_on_severity": "High"}


async def seed_all(db):
    # ---- Users ----
    if await db.users.count_documents({}) == 0:
        users = [
            ("admin@brandshield.io", "Sarah Chen", "Admin@123", "super_admin", []),
            ("tadmin@brandshield.io", "Marcus Lee", "Tenant@123", "tenant_admin", []),
            ("analyst@brandshield.io", "Priya Raman", "Analyst@123", "analyst", []),
            ("viewer@brandshield.io", "Tom Baker", "Viewer@123", "viewer", []),
        ]
        for email, name, pw, role, tids in users:
            await db.users.insert_one({
                "id": nid(), "email": email, "name": name, "password_hash": _hash(pw),
                "role": role, "tenant_ids": tids, "status": "Active", "created_at": now_iso(),
            })

    # ---- Tenants ----
    if await db.tenants.count_documents({}) == 0:
        demo = [
            ("Stripe Payments", "stripe.com", ["stripe.network"], ["Stripe"], ["Payments API", "Checkout"], "Financial Services", "United States", "America/New_York"),
            ("Netflix Media", "netflix.com", [], ["Netflix"], ["Streaming"], "Media & Entertainment", "United States", "America/Los_Angeles"),
        ]
        seq = 0
        tenant_ids = []
        for name, pd, ad, brands, products, industry, country, tz in demo:
            seq += 1
            tid = nid()
            tenant_ids.append(tid)
            await db.tenants.insert_one({
                "id": tid, "tenant_id": f"TEN-{seq:04d}", "name": name,
                "primary_domain": pd, "additional_domains": ad,
                "all_domains": [pd] + ad, "brand_names": brands, "products": products,
                "industry": industry, "country": country, "timezone": tz, "status": "Active",
                "monitoring_config": DEFAULT_MONITORING, "risk_policy": DEFAULT_RISK,
                "notifications": {"email": "", "webhook": "", "alert_severity": "High"},
                "schedule": {"interval_hours": 24, "enabled": True},
                "monitoring_enabled": True, "wizard_step": 12, "wizard_complete": True,
                "created_at": now_iso(), "updated_at": now_iso(),
            })
        # scope tenant_admin / analyst / viewer to these tenants
        await db.users.update_many(
            {"role": {"$in": ["tenant_admin", "analyst", "viewer"]}},
            {"$set": {"tenant_ids": tenant_ids}})

    # ---- Presets ----
    if await db.presets.count_documents({}) == 0:
        presets = [
            ("findings", "Critical Monitoring", {"severity": "Critical", "status": "Open"}),
            ("findings", "New Domains (7d)", {"module": "fake_website"}),
            ("findings", "High Risk", {"risk_min": 70}),
        ]
        for screen, name, cond in presets:
            await db.presets.insert_one({"id": nid(), "screen": screen, "name": name,
                                         "conditions": cond, "is_global": True, "created_at": now_iso()})
