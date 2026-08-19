# Navigatte — Project State

**Last Updated**: August 2026  
**Current Phase**: Phase 2 Admin Command Center & Infrastructure Hardening Completed  
**Repository**: `psa-kingdom/Navigatte`  
**Active Working Branch**: `test` (Tracks `origin/test`; `main` is protected baseline)

---

## 1. Executive Summary

Navigatte is an enterprise technology, intelligent automation, and digital platforms consultancy platform. The platform consists of a public-facing React 19 web application (Vercel deployment) and a modular FastAPI REST API backend (Railway deployment) with MongoDB persistence.

---

## 2. Phase 1 — Foundation (COMPLETE)

### A. Backend Modularization
The backend is structured into domain-oriented packages:
- `backend/core/`: Centralized settings (`config.py`), database lifecycle (`database.py`), cryptography & JWT token management (`security.py`), and authorization dependencies (`dependencies.py`).
- `backend/models/`: MongoDB documents (`BaseDocument`, `Project`, `Enquiry`, `AdminUser`).
- `backend/schemas/`: Pydantic validation schemas.
- `backend/routers/`: API routing (`/api/auth`, `/api/projects`, `/api/enquiries`, `/api/status`).
- `backend/services/`: Seeding services (`seeder.py`).
- `backend/server.py`: Application entry point with async lifespan hooks.

### B. Security & Config Hardening
- **Strict Production Checks**: Rejects unconfigured `JWT_SECRET` in production environments.
- **Admin Seeding Security**: No fallback admin credentials seeded in production unless explicitly defined.
- **Brute-Force Protection**: 5 attempts / 15-minute lockout keyed by identifier.
- **Honeypot Bot Mitigation**: Public enquiry form silently rejects bot submissions.

### C. Projects Domain Evolution
- **Lifecycle Statuses**: `draft`, `published`, `archived`.
- **Slug Routing**: Auto-generated URL slugs with slug/ID fallback resolution.
- **Rich Case Study Fields**: Support for `client_name`, `highlights`, `gallery_urls`, `industry_slug`, `service_slug`, and `seo` metadata.
- **Backward Compatibility**: Fully preserves legacy project records and public API contracts.

### D. Enquiries / CRM Foundation
- **Public Ingestion**: `POST /api/enquiries` with email format validation and honeypot protection.
- **Status Pipeline**: Enums for `new`, `contacted`, `qualified`, `converted`, `closed`.
- **Internal Notes**: Timestamped note records appended to leads.

---

## 3. Phase 2 — Admin Command Center & Infrastructure Hardening (COMPLETE & RECONCILED)

### A. Environment-Aware CORS Architecture
- **Multi-Origin Support**: Combines explicit origins (`CORS_ORIGINS`) with a scoped regex pattern (`CORS_ORIGIN_REGEX`).
- **Production Origins**: `https://navigatte.com`, `https://www.navigatte.com`, `https://navigatte-website.vercel.app`.
- **Vercel Preview Deployments**: Scoped regex (`^https:\/\/(navigatte-website|navigatte)(-[a-z0-9-]+)?-psumanassociates-9980s-projects\.vercel\.app$`) dynamically allows preview and Git branch deployments without wildcards or arbitrary domain reflection.
- **Local Development**: `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, `http://127.0.0.1:5173`.
- **Preflight & Credentials**: `allow_credentials=True` correctly reflects the trusted requesting origin with `Access-Control-Allow-Credentials: true`.

### B. Cross-Site Cookie & Auth Architecture
- **Cookie Settings**: Uses `SameSite=None` + `Secure=True` in production/cross-site environments to allow Vercel (`.vercel.app`) to transmit session cookies to Railway (`.up.railway.app`). Uses `SameSite=Lax` + `Secure=False` in local HTTP dev.
- **Bearer Fallback**: Axios interceptor attaches `Authorization: Bearer <token>` from `localStorage` on all API requests, providing resilience in browsers with strict third-party cookie restrictions (Safari ITP / Brave).
- **Graceful Error Handling**: Distinguishes Network/CORS server connection errors from 401 invalid credentials, 429 lockout, and 500 server errors.

### C. Admin Command Center UI (`/admin/dashboard`)
- **Tab 1 — Overview**:
  - Greeting bar with formatted current date.
  - `StatsGrid`: 4 animated metric cards (`New Enquiries`, `Pipeline Active`, `Live Projects`, `Total Projects`) with click-through navigation to relevant tabs.
  - Quick-action shortcuts (`View Enquiries`, `Manage Projects`).
- **Tab 2 — Enquiries CRM**:
  - 5-stage pipeline filter tabs (`All`, `New`, `Contacted`, `Qualified`, `Converted`, `Closed`) with live counters.
  - Debounced search across name, email, and company.
  - Sortable table by name, company, status, and submission date.
  - Client-side CSV export.
  - `LeadDrawer` slide-over panel with status stepper dropdown, copy email/phone, message display, and internal note composer/timeline.
- **Tab 3 — Projects CMS**:
  - Full CRUD grid showing all lifecycle statuses (`published`, `draft`, `archived`) with status badges and slug paths.
  - `ProjectFormDialog`: Supports title, client name, description, highlights list, image URL, service tags, status dropdown (draft/published/archived), URL slug editor, and featured toggle.
- **Navigation**: Desktop header navigation + mobile bottom tab bar, persisted active tab in `sessionStorage`, and Framer Motion transitions.

### D. API Contract Reconciliation
- Both `GET /api/admin/stats` and `GET /api/admin/overview` are bound to the stats aggregate endpoint for complete contract compatibility.

---

## 4. Phase Boundary Audit

- **Phase 1 (Foundation)**: COMPLETE
- **Phase 2 (Command Center & CRM)**: COMPLETE & RECONCILED
- **Phase 3 (Communication Studio & Resend)**: NOT STARTED (Deferred to Phase 3)

---

## 5. Deployment Architecture

```
LOCAL DEVELOPMENT
├── Frontend: http://localhost:3000
├── Backend:  http://localhost:8000
└── Database: mongodb://localhost:27017/navigatte_dev

PREVIEW / STAGING (Vercel Preview → Railway Test/Staging)
├── Frontend: https://navigatte-website-*-psumanassociates-9980s-projects.vercel.app
├── Backend:  https://navigatte-website-production.up.railway.app (or staging backend)
└── CORS:     Dynamically matched by CORS_ORIGIN_REGEX with credentials & cross-site cookies

PRODUCTION
├── Frontend: https://navigatte.com (or https://navigatte-website.vercel.app)
├── Backend:  https://navigatte-website-production.up.railway.app
└── Database: MongoDB Atlas Production Cluster
```

---

## 6. Verification Status

- **Backend Tests**: 28 passed, 19 skipped (live server), 0 failed.
- **CORS / Preflight Tests**: 7 passed (production, preview regex, branch preview, local, untrusted rejection, cross-origin login flow, alias contract).
- **Frontend Build**: Craco production build compiled successfully (0 errors, 0 warnings).
- **Git Branch**: `test` (clean working tree, up to date with `origin/test`).
- **Main Branch**: Untouched.
