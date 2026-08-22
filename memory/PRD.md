# PRD — BM1 Brand Monitoring / Digital Risk Protection Platform

## Original Problem Statement
Clone `https://github.com/sarcastic-D/BM1.git` and deploy AS-IS on the Emergent platform. Multi-tenant SaaS Digital Risk Protection app that detects brand impersonation (typosquat domains, cert-transparency/subdomain intel, RDAP/DNS snapshots, social impersonation scoring). Only boot-critical config changed; no feature/seed changes. User confirmed: deploy exactly as-is, run seed script, adjust boot config only.

## Architecture
- Frontend: React (CRA + craco), Tailwind, shadcn/ui, react-router, axios. `frontend/src/lib/api.js` uses `REACT_APP_BACKEND_URL + /api`, token in localStorage `bm_token`.
- Backend: FastAPI, all routes under `/api`. `backend/server.py` (routes), `auth.py` (JWT + RBAC), `collectors.py` (typosquat/crt.sh/RDAP/DNS/DuckDuckGo), `seed.py` (idempotent seed on startup).
- DB: MongoDB via `MONGO_URL` / `DB_NAME` (env only).
- Env set for boot: `JWT_SECRET` (backend/.env), `CORS_ORIGINS="*"`, `REACT_APP_BACKEND_URL` (frontend/.env).

## User Personas
Brand security / SOC analysts and admins. Roles: Super Admin, Tenant Admin, Analyst, Viewer (server-side tenant isolation).

## Core Requirements (static)
- JWT auth + 4-role RBAC, tenant isolation
- Admin portal: tenants, 12-step config wizard, scheduler "Run Now", monitoring health, users/RBAC, audit logs, settings
- Tenant view: dashboard, All Findings + module pages, Cases, Reports
- Reusable filter engine, saved filters, finding detail drawer, CSV + PDF export
- Collectors: typosquat generator, crt.sh, RDAP, DNS, DuckDuckGo dorking

## Implemented (2026-06)
- Repo cloned and deployed unchanged into `/app` (backend + frontend), boot config wired to platform env.
- Backend deps installed (ddgs, beautifulsoup4, python-whois, dnspython, google-play-scraper, reportlab, lxml, fake-useragent).
- Seed ran: 4 demo users, 2 tenants (Stripe Payments TEN-0001, Netflix Media TEN-0002), 3 presets.
- Smoke test PASSED (testing agent iteration_1): login all 4 roles, admin portal (12 pages), tenant view (11 pages), 12-step wizard, Run Now scan, All Findings + filters + saved filters, CSV export (36KB), finding drawer, RBAC (viewer restricted). 61/62 backend tests pass.
- Bug fix: `GET /api/findings/report.pdf` was 500ing on scraped titles containing `<`/`&` (reportlab paraparser). XML-escaped title/category/platform/tenant/filter strings — PDF export now 200 for all tenants.

## Known / Accepted (as-is)
- Public seed super-admin creds shipped (admin@brandshield.io / Admin@123) — intentional per user; recommend rotating before real/public use.
- Free-scraper modules (DuckDuckGo, crt.sh) may show "degraded"/empty on fresh server IP — expected.
- Paid-API modules (Mobile Apps, Executive, Telegram, Meta Ads) empty by design.

## Backlog (not requested; do only if user asks)
- P1: Rotate/remove public super-admin seed creds; move JWT_SECRET off any default.
- P2: Split server.py routers into modules; add DialogTitle to finding drawer (a11y warning).
