# Navigatte — Project State

**Last Updated**: February 2026  
**Current Phase**: Phase 1 Foundation Completed  
**Repository**: `psa-kingdom/Navigatte`  
**Active Working Branch**: `test` (Tracks `origin/test`; `main` is protected baseline)

---

## 1. Executive Summary

Navigatte is a digital consultancy platform delivering enterprise technology, automation, and digital platforms. The platform consists of a public-facing React 19 web application and a modular FastAPI REST API backend with MongoDB persistence.

---

## 2. Completed in Phase 1 (Foundation)

### A. Backend Modularization
The backend has been modularized from a single monolithic file into domain-oriented modules:
- `backend/core/`: Centralized settings (`config.py`), database client & indexes (`database.py`), cryptography & JWT token management (`security.py`), and authorization dependencies (`dependencies.py`).
- `backend/models/`: Domain MongoDB documents (`BaseDocument`, `Project`, `Enquiry`, `AdminUser`).
- `backend/schemas/`: Pydantic validation schemas for requests and responses.
- `backend/routers/`: API routing divided into `/api/auth`, `/api/projects`, `/api/enquiries`, and `/api/status`.
- `backend/services/`: Seeding services for initial admin and showcase projects (`seeder.py`).
- `backend/server.py`: Clean application factory with async lifespan management and CORS middleware.

### B. Security & Config Hardening
- **Strict Production Checks**: Startup rejects unconfigured `JWT_SECRET` in production.
- **Admin Seeding Security**: No fallback admin credentials created in production environments unless explicitly defined in environment variables.
- **Brute-Force Protection**: 5 attempts / 15-minute lockout keyed by email.
- **Honeypot Bot Mitigation**: Public enquiry form rejects bot spam without database pollution.

### C. Projects Domain Evolution
- **Lifecycle Statuses**: Support for `draft`, `published`, and `archived` states.
- **Slug Routing**: Auto-generates URL slugs from project titles; API supports lookup by ObjectId or slug.
- **Rich Case Study Fields**: Support for `highlights`, `gallery_urls`, `industry_slug`, `service_slug`, and `seo` metadata (`meta_title`, `meta_description`).
- **Backward Compatibility**: Fully preserves existing project records and API endpoints.

### D. Enquiries / CRM Foundation
- **Public Ingestion**: `POST /api/enquiries` with email format validation, length constraints, and honeypot protection.
- **Status Pipeline**: Enums for `new`, `contacted`, `qualified`, `converted`, `closed`.
- **Internal Notes**: Support for appending timestamped notes to lead records.
- **Admin Endpoints**: `GET /api/admin/enquiries` (filtering/search), `PATCH /api/admin/enquiries/{id}/status`, `POST /api/admin/enquiries/{id}/notes`.

### E. Test Harness
- Comprehensive pytest test suite in `backend/tests/` covering:
  - Auth login, logout, profile, and brute-force lockout.
  - Project CRUD, slug lookup, and draft/published visibility filtering.
  - Enquiry submission, validation, honeypot rejection, and status progression.
  - In-memory mock database (`mock_db.py`) allowing tests to run rapidly in any environment.

---

## 3. Database Schema Overview

| Collection | Key Fields | Indexes |
| :--- | :--- | :--- |
| `admin_users` | `_id`, `email`, `password_hash`, `role`, `created_at`, `last_login_at` | `email` (unique) |
| `login_attempts` | `_id`, `identifier`, `count`, `locked_until` | `identifier` (unique) |
| `projects` | `_id`, `slug`, `title`, `description`, `image_url`, `tags`, `highlights`, `status`, `featured`, `order`, `seo`, `created_at`, `updated_at` | `[status, featured, order]`, `slug` |
| `enquiries` | `_id`, `name`, `email`, `phone`, `company`, `service_interest`, `message`, `source`, `status`, `notes`, `created_at`, `updated_at` | `[status, created_at]`, `email` |
| `status_checks` | `id`, `client_name`, `timestamp` | — |

---

## 4. API Endpoints Map

### Public Endpoints
- `GET  /api/` — Root status
- `GET  /api/status` — Health checks
- `GET  /api/tags` — Distinct project taxonomy tags
- `GET  /api/projects` — List published projects (filters: `featured`, `tag`, `industry`)
- `GET  /api/projects/{id_or_slug}` — Get project by ID or slug
- `POST /api/enquiries` — Ingest client enquiry / consultation request

### Admin Endpoints (Guarded by `get_current_admin`)
- `POST /api/auth/login` — Authenticate and receive JWT cookie & token
- `POST /api/auth/logout` — Clear session
- `GET  /api/auth/me` — Verify authenticated admin
- `GET  /api/admin/projects` — List all projects across all statuses
- `POST /api/admin/projects` — Create project
- `PUT  /api/admin/projects/{id}` — Update project
- `PATCH/api/admin/projects/{id}/status` — Update project status
- `DELETE /api/admin/projects/{id}` — Delete project
- `GET  /api/admin/enquiries` — List and search leads
- `GET  /api/admin/enquiries/{id}` — Get lead details with notes
- `PATCH/api/admin/enquiries/{id}/status` — Advance lead in CRM pipeline
- `POST /api/admin/enquiries/{id}/notes` — Append internal note

---

## 5. Roadmap & Deferred Scope

### Phase 2: Core Admin Command Center & CRM UI
- **Admin Overview Dashboard**: Unified 4-card metric overview (`New Enquiries`, `Pipeline`, `Projects`, `Health`) with quick actions.
- **Enquiries CRM UI**: 5-stage pipeline filter tabs, slide-over lead detail drawer, one-click copy email/phone, and CSV export.
- **Projects CMS UI Enhancements**: Draft/publish toggle, slug editor, rich highlights repeater.
- **Image Upload Integration**: Direct media upload instead of URL-only paste.

### Phase 3: Communication Studio & Email Integration
- **Resend Provider Adapter**: Abstracted email delivery service.
- **Email Templates & Campaign Outbox**: Test mode vs. production mode dispatching.
- **Webhook Ingestion**: Svix-verified webhook processor for delivery, bounce, and open tracking.

---

## 6. Verification Status
- **Backend Tests**: 19 passing tests in `backend/tests/` (100% pass rate).
- **Git Branch**: Working cleanly on `test`; `main` untouched.
- **Backward Compatibility**: Fully verified against existing frontend contracts and database models.
