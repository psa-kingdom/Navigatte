# Navigatte — Project State

**Last Updated**: August 2026  
**Current Phase**: Phase 2A Admin Platform Foundation & Scalable Navigation Architecture Completed  
**Repository**: `psa-kingdom/Navigatte`  
**Active Working Branch**: `main` (Production Baseline & Deployment Synced)

---

## 1. Executive Summary

Navigatte is an enterprise technology, intelligent automation, and digital platforms consultancy platform. It combines a high-performance marketing website with an internal **Admin Command Center** for managing client portfolio case studies, customer enquiries/leads, and enterprise services.

The platform is deployed as a decoupled monorepo:
- **Frontend**: React 19 SPA deployed on Vercel with CRACO, Tailwind CSS, Radix UI, Framer Motion.
- **Backend**: FastAPI modular ASGI API deployed on Railway with Motor AsyncIO MongoDB driver, PyJWT, and Bcrypt.
- **Database**: MongoDB Atlas Production Cluster.

---

## 2. Phase 1 — Foundation (COMPLETE)

- **Backend Modularization**: Decoupled into `core/`, `models/`, `schemas/`, `routers/`, `services/`, and `tests/`.
- **Security & Config Hardening**: Environment validation, brute-force lockout (5 attempts / 15 min), honeypot spam protection, secure password hashing.
- **Projects Domain Evolution**: `draft`/`published`/`archived` lifecycle, automatic URL slug generation, case study highlights and taxonomy.
- **Enquiries / CRM Foundation**: Public lead ingestion (`POST /api/enquiries`), 5-stage status pipeline, internal timestamped notes.

---

## 3. Phase 2A — Admin Platform Foundation & Navigation Architecture (COMPLETE)

### A. Scalable Admin Navigation Architecture
- **Single Source of Truth (`adminNavigationConfig.js`)**:
  - Centralized registry of all admin modules grouped into *Operations*, *Content & Growth*, and *Platform*.
  - Configurable module status (`active` vs. `coming-soon`), badges (`CRM`, `CMS`, `Phase 3`, `Phase 2B`), icons, and route descriptions.
- **Persistent Trigger & Slide-Over Drawer (`AdminNavigationDrawer.jsx`)**:
  - **Desktop**: Compact persistent trigger in the header with hover/click open triggers, a 280ms mouse-leave debounce bridge to prevent accidental dismissals, click-outside / backdrop dismiss, and Escape key dismissal.
  - **Mobile**: Tap-to-open drawer overlay with smooth backdrop blur, keyboard accessibility, and ARIA attributes (`aria-expanded`, `aria-label`, `role="navigation"`).
- **Admin Layout Shell (`AdminShell.jsx`)**:
  - Replaces section-heavy header tab strips with a scalable top application bar (Trigger + Brand + Active Section Breadcrumb + User Profile + Logout).
  - Encapsulates layout, responsive padding, and drawer overlay.

### B. Enquiries CRM & Command Center
- **Overview Dashboard**: Animated 4-card `StatsGrid` connected to `GET /api/admin/stats` & `GET /api/admin/overview`.
- **5-Stage Pipeline CRM**: Filterable by `All`, `New`, `Contacted`, `Qualified`, `Converted`, `Closed` with debounced search, sortable table, and client-side CSV export.
- **Lead Drawer**: Slide-over panel with status stepper, message preview, quick copy email/phone, and internal note timeline/composer.
- **Projects CMS**: Full admin CRUD table supporting status toggles (`draft`, `published`, `archived`), URL slugs, client names, and service tags.

### C. CORS & Cross-Site Authentication
- **Scoped `CORS_ORIGIN_REGEX`**: `^https:\/\/(navigatte-website|navigatte)(-[a-z0-9-]+)?-psumanassociates-9980s-projects\.vercel\.app$` dynamically permits changing Vercel Preview URLs without wildcards.
- **Cross-Site Cookies**: `SameSite=None; Secure=True; HttpOnly=True; Path=/` in production/staging environments.
- **Dual Authentication Layer**: HttpOnly session cookies + `Authorization: Bearer <token>` fallback in `localStorage`.

---

## 4. Enquiries Data RCA (0-Enquiry Situation)

| Dimension | Finding |
|---|---|
| **Root Cause** | **EXPECTED (Fresh Database State)**: The production MongoDB cluster was initialized without fake lead submissions. The demo seeder (`seeder.py`) seeds 8 showcase projects but intentionally avoids fabricating fake customer enquiries. |
| **Ingestion Pipeline** | Verified live on Railway: `POST /api/enquiries` validates input, detects honeypots, and successfully inserts documents into the `enquiries` collection with `status: "new"`. |
| **Query & Aggregation** | Verified: `GET /api/admin/enquiries` and `GET /api/admin/stats` correctly retrieve persisted records and update metric cards in real time. |
| **Integrity Policy** | Zero enquiries is genuine and correct for a newly deployed database. No artificial mock leads were injected into production. |

---

## 5. Master Roadmap & Dependency Hierarchy

```
PHASE 1: Foundation (COMPLETE)
└── Backend modularization, JWT/cookies, MongoDB models, seeder, test harness.

PHASE 2A: Admin Platform Foundation (COMPLETE)
├── Admin Shell & Scalable Navigation Architecture (adminNavigationConfig)
├── Persistent Navigation Drawer & Trigger (Desktop & Mobile)
├── Command Center Overview & Stats Aggregate (/api/admin/stats & /api/admin/overview)
├── Enquiries CRM & 5-Stage Pipeline (LeadDrawer, Notes, CSV export)
├── Projects CMS (Lifecycle statuses, slug management, client names)
└── Durable CORS & Cross-Site Cookie Architecture

PHASE 2B: Admin UX Evolution (BACKLOG / PLANNED)
├── [Task A] Global Admin Action/Search Bar (kokonutui action-search-bar reference)
│   └── Dependencies: adminNavigationConfig, searchable entity schemas, permissions
├── [Task B] Restrained Flow Field Background System (kokonutui flow-field reference)
│   └── Dependencies: foreground contrast audit, prefers-reduced-motion support
├── [Task C] Bento-Grid Command Center (kokonutui bento-grid reference)
│   └── Dependencies: Phase 2A metrics, modular card components
└── [Task D] Spotlight Module Cards (kokonutui spotlight-cards reference)
    └── Dependencies: Bento layout, design token alignment

PHASE 3: Communications Studio & Email Delivery (DEFERRED / NOT STARTED)
├── Resend Provider Adapter & Delivery Service
├── Email Template Engine & Campaign Outbox
├── Webhook Processor (Delivery, Bounce, Open tracking)
└── Audience & Subscriber Management
```

---

## 6. Verification Summary

- **Backend Pytest Suite**: **28 passed / 0 failed / 19 skipped** (100% pass rate on unit, integration, and CORS tests).
- **Frontend Build**: **Compiled successfully** (`npx craco build` — 0 errors, 0 warnings).
- **Deployment Smoke Test**: **PASS** (100% checks passed against live Railway backend and local test server).
- **Git State**: Clean working tree on `main` branch, synced with `origin/main` at commit `7b9c93c`.
