# Navigatte — Project State

**Last Updated**: August 2026  
**Current Phase**: Phase 2C Cal.com Scheduling Integration & Provider Abstraction Foundation Completed  
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

- **Scalable Admin Navigation Architecture**: Centralized single source of truth in `adminNavigationConfig.js`, persistent slide-over `AdminNavigationDrawer.jsx` (Desktop hover/click with 280ms debounce, Mobile tap drawer, full `document.body` portal mounting).
- **Enquiries CRM & Command Center**: 5-stage pipeline, `LeadDrawer` slide-over with Radix dropdowns, note timeline, search, sorting, and CSV export.
- **Projects CMS**: Full admin CRUD table with lifecycle toggles (`draft`, `published`, `archived`), URL slugs, client names, and service tags.
- **CORS & Preview Auth Hardening**: Scoped regex matching all dynamic Vercel previews with cross-site `SameSite=None; Secure=True` cookies and `Bearer` authorization fallback.

---

## 4. Phase 2C — Cal.com Scheduling Integration & Provider Abstraction (COMPLETE)

### A. Third-Party Provider Boundary & Scheduling Contract
- **Generic Scheduling Contract (`integrations/contracts/scheduling.py`)**:
  - `SchedulingProvider` abstract base class defining `verify_webhook_signature`, `normalize_webhook`, and `sync_webhook`.
  - Normalized domain data classes: `SchedulingEvent`, `SchedulingAttendee`, `SchedulingMeeting`, `SchedulingOrganizer`, `SchedulingEventType`.
  - Guarantees that Cal.com can be replaced with any other scheduling provider without altering core CRM logic.
- **Cal.com Adapter (`integrations/cal/`)**:
  - `CalSchedulingProvider`: Concrete implementation.
  - `verifier.py`: HMAC-SHA256 signature verification computed strictly on raw request body bytes with `x-cal-signature-256` header.
  - `mapper.py`: Normalizes Cal.com nested v2 payloads (`BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`, `BOOKING_REJECTED`, `MEETING_STARTED`, `MEETING_ENDED`).
  - `client.py`: Server-side API v2 client for webhook synchronization (`/v2/webhooks`).

### B. Durable Idempotency & CRM Lead Matching
- **Idempotent Ingestion (`models/webhook_event.py` & `services/scheduling_service.py`)**:
  - Unique index on `idempotency_key` (`cal:<event_type>:<booking_uid>:<timestamp>`).
  - Retried webhooks are recognized and safely acknowledged without generating duplicate CRM records or activities.
- **Deterministic Lead Matching**:
  - Ingested bookings match existing enquiries by normalized email address.
  - Existing leads receive updated scheduling metadata and advance to `contacted` status if previously `new`.
  - Direct booking prospects without prior enquiries automatically generate a new lead with `source = "cal.com"`.
- **CRM Timeline & Separation of Concerns**:
  - Sales pipeline status (`new`, `contacted`, `qualified`, `converted`, `closed`) is kept strictly separated from scheduling status (`none`, `booked`, `rescheduled`, `cancelled`, `completed`, `no_show`).
  - Every scheduling event appends an `EnquiryActivity` to the lead's chronological activity feed.

### C. Test Lead Isolation
- The diagnostic `"Test RCA Verification Lead"` is marked with `is_test: true` in MongoDB and is cleanly excluded from dashboard business pipeline metrics.

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

PHASE 2C: Scheduling Integration & Provider Abstraction (COMPLETE)
├── Generic Third-Party Scheduling Contract (SchedulingProvider & SchedulingEvent)
├── Cal.com v2 Webhook Ingestion & HMAC-SHA256 Signature Verification
├── Durable Database-Backed Idempotency (IntegrationWebhookEvent)
├── Deterministic CRM Lead Matching & Independent Scheduling Status
├── Interactive Activity Timeline & Scheduled Consultation Cards
└── Diagnostic Test Record Classification (is_test flag)

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

- **Backend Pytest Suite**: **37 passed / 0 failed / 19 skipped** (100% pass rate across auth, security, projects, enquiries, CORS, and Cal.com webhooks).
- **Frontend Build**: **Compiled successfully** (`npx craco build` — 0 errors, 0 warnings, 376 kB gzipped JS).
- **Deployment Smoke Test**: **PASS** (CORS preflights, authenticated session flows, and webhook ingestion).
- **Git State**: Clean working tree on `main` branch, synced with `origin/main` and `origin/test`.
