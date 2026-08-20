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

### D. Railway Deployment Hardening & Dependency Isolation
- **Railway Crash Root Cause**: Production crash on Railway caused by `ModuleNotFoundError: No module named 'httpx'` due to missing dependency declarations in `backend/requirements.txt`.
- **Resolution**:
  - Explicitly added `httpx>=0.27.0` and `python-dateutil>=2.9.0` to `backend/requirements.txt`.
  - Replaced `dateutil` in `mapper.py` with standard library `datetime.fromisoformat()` for zero-dependency ISO-8601 parsing.
  - Hardened `CAL_API_KEY` in `config.py` with fallback resolution (`CAL_API_KEY` or `CAL_COM_API` or `CALCOM_API_KEY`).
  - Added test coverage ensuring FastAPI boots cleanly when Cal.com credentials are unset or disabled.

### E. Public "Book A Call" Qualification Flow & Admin Profile UI
- **Public "Book A Call" Flow (`BookCallModal.jsx`)**:
  - Replaced raw external Cal.com links with a high-contrast qualification modal mounted via `createPortal`.
  - **Step 1**: Ingests prospect name, work email, company, service focus, and project goal into Navigatte CRM (`POST /api/enquiries`), creating a persistent lead (`status: "new"`).
  - **Step 2**: Transitions smoothly to Cal.com scheduling with prefilled parameters (`?name=...&email=...&notes=...`), preserving lead ownership even if the visitor abandons the calendar step.
- **Admin Profile UI (`AdminProfileDropdown.jsx`)**:
  - Replaced static text with an accessible Radix `DropdownMenu` profile badge with avatar initials, role display (`Administrator`), session state, and accessible logout trigger.

### F. Global Admin Action & Search Bar (Phase 2B — Task A)
- **Backend Search Endpoint (`GET /api/admin/search`)**:
  - Scoped, authenticated, low-latency search across CRM enquiries (name, email, company, service interest) and projects (title, client, slug, tags).
  - Strictly isolates `is_test: true` diagnostic leads and bounds result sizes.
- **Global Command Overlay (`GlobalAdminSearch.jsx`)**:
  - Inspired by KokonutUI Action Search Bar with `Cmd/Ctrl + K` global hotkey and keyboard navigation.
  - Multi-entity grouping: Navigation modules, Quick Actions, CRM Enquiries, and Projects CMS.
- **Header Trigger (`AdminSearchTrigger.jsx`)**:
  - Responsive search trigger integrated into `AdminShell.jsx` (desktop shortcut badge and mobile icon trigger).

### G. Communications Provider Boundary & Resend Architecture (Phase 3 Foundation)
- **Generic Communications Contract (`integrations/contracts/communications.py`)**:
  - `CommunicationsProvider` ABC with `send_email`, `verify_webhook_signature`, and `normalize_webhook`.
  - Normalized domain data classes: `EmailMessage`, `EmailRecipient`, `EmailDeliveryResult`, `CommunicationWebhookEvent`, `CommunicationEventType`.
  - Guarantees zero tight coupling between CRM and vendor-specific email services.
- **Resend Adapter (`integrations/resend/`)**:
  - `ResendCommunicationsProvider`: Concrete adapter calling Resend API v1 using standard library / `httpx` (zero additional external packages).
  - `verifier.py`: Svix HMAC-SHA256 signature verification computed on raw request bytes.
  - `mapper.py`: Normalizes Resend delivery events (`email.sent`, `email.delivered`, `email.bounced`, `email.complained`, `email.opened`, `email.clicked`).
  - `client.py`: High-performance asynchronous REST client.

---

## 5. Master Roadmap & Priority Hierarchy

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
├── Diagnostic Test Record Classification (is_test flag)
├── Production Dependency Hardening & Startup Isolation (httpx in requirements.txt)
├── Public "Book A Call" Lead Qualification Modal Flow (BookCallModal)
└── Admin Profile Dropdown Component (AdminProfileDropdown)

PHASE 2B: Admin UX & Design System Evolution (IN PROGRESS)
├── [P1 / Task A] Global Admin Action/Search Bar (COMPLETE — GlobalAdminSearch & GET /api/admin/search)
├── [P2 / Task B] Dual-Theme Design Token System (NEXT FOUNDATION)
│   └── High-contrast Dark Obsidian & Editorial Light semantic CSS custom properties
├── [P3 / Task C] Restrained Flow Field Background System (PLANNED)
│   └── Dependencies: Task B Theme Tokens, foreground contrast audit, prefers-reduced-motion
├── [P3 / Task D] Bento-Grid Command Center (PLANNED)
│   └── Dependencies: Task B Theme Tokens, Phase 2A metrics, modular card components
└── [P3 / Task E] Spotlight Module Cards (PLANNED)
    └── Dependencies: Task D Bento layout, design token alignment

PHASE 3: Communications Studio & Email Engine (FOUNDATION ESTABLISHED)
├── [P1] Communications Provider Contract & Resend Adapter (COMPLETE — zero new deps)
├── [P3] Email Template Engine & Transactional Outbox (PLANNED)
├── [P3] Webhook Ingestion Router & Delivery Tracking (PLANNED)
└── [P4] Audience & Subscriber Campaign Management (PLANNED)
```

---

## 6. Verification Summary

- **Backend Pytest Suite**: **46 passed / 0 failed / 19 skipped** (100% pass rate across auth, security, projects, enquiries, CORS, Cal.com webhooks, qualification flows, startup isolation, global search, and Resend provider boundary).
- **Frontend Build**: **Compiled successfully** (`npx craco build` — 0 errors, 0 warnings, 381.61 kB gzipped JS).
- **Deployment Smoke Test**: **PASS** (CORS preflights, authenticated session flows, search endpoints, and webhook ingestion).
- **Git State**: Clean working tree on `main` branch, synced with `origin/main` and `origin/test`.
