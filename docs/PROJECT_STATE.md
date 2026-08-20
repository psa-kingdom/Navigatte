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

### H. Admin System Health & Integrations Centre (Operational Control Plane)
- **Backend System Health Router (`GET /api/admin/system/health`, `POST /api/admin/system/health/cal/test`, `POST /api/admin/system/health/database/test`)**:
  - Live diagnostic evaluation across MongoDB Atlas, Cal.com API/Webhooks, Resend, Railway container, and Vercel.
  - Multi-state semantic health (`HEALTHY`, `DEGRADED`, `ERROR`, `NOT_CONFIGURED`, `MONITORING_UNAVAILABLE`).
  - Progressive disclosure of latency, recent failure timestamps, affected capabilities, and actionable remedies.
- **Frontend Operational Settings View (`AdminSettingsView.jsx`)**:
  - **System Health**: Telemetry cards, latency gauges, live test actions, incident callouts, and real-time audit feed.
  - **Integrations**: Configuration status cards for Cal.com, Resend (`updates.navigatte.com`), MongoDB Atlas, and Railway.
  - **Appearance**: Interactive dual-theme switcher (**Obsidian** vs **Editorial**).
  - **General & Security**: Admin credential context and session security status.

### I. Dual-Theme Semantic Design Token System
- **Intentionally Designed Visual Aesthetics**:
  - **Obsidian Theme**: Space-black (`#08080C`), graphite surfaces (`#14141E`), elevated luminance, iris glow.
  - **Editorial Theme**: High-contrast porcelain (`#FBFBFD`), pure-white card surfaces (`#FFFFFF`), charcoal typography (`#0A0A10`), royal indigo accents.
- **Semantic CSS Token System**: `--app-bg`, `--surface-card`, `--surface-elevated`, `--surface-muted`, `--border-subtle`, `--text-primary`, `--text-secondary`, `--status-healthy`, `--status-degraded`, `--status-error`.
### J. Communications Studio & Outbox Engine (Phase 3 Complete)
- **Database & Domain Models (`models/communications.py`)**:
  - `EmailTemplateModel`: System templates with variable schemas (`enquiry_acknowledgement`, `consultation_booking_confirmation`, `consultation_rescheduled`, `consultation_cancelled`).
  - `OutboxItemModel`: Durable outbox records with status progression (`queued`, `sending`, `sent`, `delivered`, `bounced`, `failed`, `opened`, `clicked`).
- **Transactional Dispatch & Inbound Webhooks (`services/communications_service.py`)**:
  - `send_transactional_email`: Queues outbox item, renders variables, dispatches via `ResendCommunicationsProvider`, and correlates with CRM Enquiry timeline.
  - `process_resend_webhook`: Ingests Svix-signed Resend delivery events (`email.delivered`, `email.bounced`, `email.opened`), updates Outbox status, and appends concise timeline activities to matched leads.
- **Admin Communications Centre UI (`CommunicationsCentre.jsx`)**:
  - Overview KPI metrics (Total Dispatches, Delivery Rate, Open Rate, Bounces).
  - Outbox inspection table with search, status filtering, and rendered HTML preview modal.
  - Template library with variable schemas.
  - Direct live test email sender (`POST /api/admin/communications/send-test`).

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

PHASE 2B: Admin UX & Control Centre Evolution (COMPLETE)
├── [P1 / Task A] Global Admin Action/Search Bar (COMPLETE — commit 4e1387b)
├── [P1 / Control Centre] Admin System Health & Integrations Centre (COMPLETE — AdminSettingsView)
├── [P1 / Test Actions] Real Diagnostic & Webhook Verification Test Actions (COMPLETE)
└── [P2 / Tokens] Dual-Theme Semantic Design Token Foundation (COMPLETE)

PHASE 3: Communications Studio & Email Engine (COMPLETE)
├── [P1] Communications Provider Contract & Resend Adapter (COMPLETE — commit a5366ea)
├── [P1] Transactional Outbox & Template Library (COMPLETE — CommunicationsService)
├── [P1] Resend Inbound Webhook Ingestion & Delivery Tracking (COMPLETE — POST /api/webhooks/resend)
├── [P1] CRM ↔ Communications Activity Timeline Sync (COMPLETE)
└── [P1] Communications Studio Admin UI (COMPLETE — CommunicationsCentre.jsx)

PHASE: UI/UX + VISUAL DESIGN SYSTEM (EXPLICITLY DEFERRED / FUTURE PHASE)
├── Dual-Theme Appearance Toggle Refinement (Obsidian & Editorial)
├── Restrained Flow Field Background System
├── Bento Grid Command Center Layout
├── Spotlight Module Cards
└── Systematic Spacing, Typography & Motion Audit
```

---

## 6. Verification Summary

- **Backend Pytest Suite**: **55 passed / 0 failed / 19 skipped** (100% pass rate across auth, security, projects, enquiries, CORS, Cal.com webhooks, qualification flows, startup isolation, global search, Resend adapter, system health, and communications outbox engine).
- **Frontend Build**: **Compiled successfully** (`npx craco build` — 0 errors, 0 warnings, 392.33 kB gzipped JS).
- **Deployment Smoke Test**: **PASS** (CORS preflights, authenticated session flows, search endpoints, communications overview, and webhook ingestion).
- **Git State**: Clean working tree on `main` branch, synced with `origin/main` and `origin/test`.
