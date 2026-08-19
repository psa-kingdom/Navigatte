# Navigatte

**Navigatte** is an enterprise technology, intelligent automation, and digital platforms consultancy platform. It combines a high-performance marketing website with an internal **Admin Command Center** for managing client portfolio case studies, customer enquiries/leads, and enterprise services.

---

## 🏛️ Architecture Overview

The project is structured as a clean, decoupled monorepo:

```
Navigatte/
├── frontend/             # React 19 SPA (Vercel deployment)
│   ├── src/
│   │   ├── components/   # UI primitives (Radix UI/shadcn) & feature blocks
│   │   ├── pages/        # Public pages & Admin views
│   │   ├── context/      # Admin auth context & state
│   │   └── data/         # Centralized marketing site content (siteData.js)
│   └── public/           # Static assets, manifests, and icons
│
├── backend/              # Python FastAPI REST API (Railway deployment)
│   ├── core/             # Centralized config, database lifecycle, security & dependencies
│   ├── models/           # MongoDB document models (BaseDocument, Projects, Enquiries, AdminUser)
│   ├── schemas/          # Pydantic request/response validation schemas
│   ├── routers/          # API routers (/api/auth, /api/projects, /api/enquiries, /api/status)
│   ├── services/         # Seeding and background domain services
│   ├── tests/            # Automated pytest test suites
│   └── server.py         # Top-level ASGI application entry point
│
└── docs/                 # System documentation and project state snapshots
```

---

## 🚀 Tech Stack

- **Frontend**: React 19, React Router v7, Tailwind CSS 3.4, Radix UI, Framer Motion, Axios, CRACO.
- **Backend**: Python 3.10+, FastAPI 0.110, Uvicorn, Motor (AsyncIO MongoDB driver), Pydantic v2, PyJWT, Bcrypt.
- **Database**: MongoDB (MongoDB Atlas in production / local MongoDB in dev).
- **Deployment**: Vercel (Frontend SPA) + Railway (Backend API).

---

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ (with Yarn or npm)
- MongoDB instance (local or Atlas URI)

### 1. Backend Setup

```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run FastAPI backend server (http://localhost:8000)
uvicorn server:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
yarn install  # or npm install

# Run React dev server (http://localhost:3000)
yarn start    # or npm start
```

---

## 🧪 Testing

Run automated backend tests using pytest:

```bash
cd backend
python -m pytest -v
```

---

## 🔒 Security

- **Authentication**: JWT access tokens (12h expiration) and refresh tokens stored in `httpOnly` secure cookies with fallback Authorization header.
- **Brute-Force Protection**: Automatic 15-minute account lockout after 5 consecutive failed login attempts.
- **Spam Mitigation**: Public lead capture forms feature honeypot bot detection and strict Pydantic input validation.

---

## 📄 License & Ownership
Copyright © 2026 Navigatte. All rights reserved.
