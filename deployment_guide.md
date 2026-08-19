# Production & Staging Deployment Guide

This guide describes how to deploy the **Navigatte** application across staging and production using **MongoDB Atlas** for the database, **Railway** for the backend, and **Vercel** for the frontend.

---

## 1. MongoDB Atlas Setup

1. **Sign Up / Log In**: Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and log in.
2. **Create a Cluster**: Create a new shared/serverless cluster for production and staging (or use separate databases `navigatte_production` and `navigatte_staging`).
3. **Database Access (User)**:
   - Create a database user (e.g., `navigatte-admin`).
   - Copy and secure the password.
4. **Network Access (IP Whitelist)**:
   - Add a rule to allow connections from anywhere (`0.0.0.0/0`) since Railway servers do not have static public IPs by default.
5. **Get Connection String**:
   - Format: `mongodb+srv://<username>:<password>@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority`
   - Replace `<password>` with your database user's password.

---

## 2. Backend Deployment on Railway

### A. Environment Branches
- **Staging / Test Backend**: Connect to the `test` branch of the GitHub repository.
- **Production Backend**: Connect to the `main` branch of the GitHub repository.

### B. Configure Service
1. **Root Directory**: Set to `/backend` in Service Settings -> General.
2. **Build**: Railway automatically detects `backend/requirements.txt` via Nixpacks.
3. **Environment Variables**:
   - `MONGO_URL` = `<your-mongodb-atlas-connection-string>`
   - `DB_NAME` = `navigatte_production` (or `navigatte_staging`)
   - `JWT_SECRET` = `<a-long-random-secure-string>` (Required in production)
   - `ENVIRONMENT` = `production` (or `development` / `staging`)
   - `CORS_ORIGINS` = `https://navigatte.com,https://www.navigatte.com,https://navigatte-website.vercel.app`
   - `CORS_ORIGIN_REGEX` = `^https:\/\/(navigatte-website|navigatte)(-[a-z0-9-]+)?-psumanassociates-9980s-projects\.vercel\.app$` (Auto-configured by default)
   - `ADMIN_EMAIL` = `admin@navigatte.com` (optional initial admin seed)
   - `ADMIN_PASSWORD` = `<your-secure-admin-password>` (optional initial admin seed)

---

## 3. Frontend Deployment on Vercel

1. **Root Directory**: Set to `frontend`.
2. **Framework Preset**: Create React App (via CRACO).
3. **Environment Variables**:
   - `REACT_APP_BACKEND_URL`:
     - **Production Environment**: `https://navigatte-website-production.up.railway.app`
     - **Preview Environment**: Point to staging backend (or production backend if shared)
4. **Automatic Preview CORS**:
   - Vercel Previews generated from the `test` branch or PRs under the `psumanassociates-9980s-projects` namespace automatically match the backend's `CORS_ORIGIN_REGEX` without requiring manual variable updates on every commit.
