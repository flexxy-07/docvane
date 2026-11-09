# DocVane Production Deployment Guide

This guide covers deploying DocVane to production for **$0/month** using free tier services.

---

## Architecture Overview

- **Database**: [Supabase](https://supabase.com/) (Managed PostgreSQL 17 + `pgvector` pre-installed, Free Tier)
- **Backend API**: [Render](https://render.com/) (Docker Web Service, Free Tier with auto-deploy on git push)
- **Frontend App**: [Vercel](https://vercel.com/) (Next.js 16, Free Tier)

---

## Part 1: Database (Already Configured! ✓)

Your Supabase project is already configured with all tables, row-level security, and vector embeddings:
- **Connection URI**:
  ```text
  postgresql+asyncpg://postgres.ikarqeanmagmammklglz:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
  ```

---

## Part 2: Backend API (Render)

### Option A: 1-Click Blueprint (Recommended)
1. Log in to [render.com](https://render.com/).
2. In the top navigation, click **New +** → **Blueprint**.
3. Connect your GitHub repository: `flexxy-07/docvane`.
4. Render will automatically detect `render.yaml`.
5. When prompted for environment variables, fill in:
   - `DATABASE_URL`: Your Supabase connection string.
   - `GEMINI_API_KEY`: Your Google Gemini API key.
6. Click **Apply**.
7. Render will build the Docker container, run migrations, and assign you a live HTTPS URL:
   ```text
   https://docvane-backend.onrender.com
   ```

### Option B: Manual Web Service
1. On Render, click **New +** → **Web Service**.
2. Connect `flexxy-07/docvane`.
3. Choose **Docker** as the runtime.
4. Set **Health Check Path** to `/healthz`.
5. Under **Environment Variables**, add:
   - `DATABASE_URL`: `postgresql+asyncpg://postgres.ikarqeanmagmammklglz:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres`
   - `GEMINI_API_KEY`: your-gemini-api-key
   - `CORS_ORIGINS`: `*`
   - `S3_ENDPOINT_URL`: `local`
   - `ENVIRONMENT`: `production`
6. Click **Deploy Web Service**.

---

## Part 3: Frontend (Vercel)

1. Go to [vercel.com](https://vercel.com/) and click **Add New** → **Project**.
2. Import `flexxy-07/docvane`.
3. Set **Root Directory** to `frontend`.
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL`: Your live Render backend URL + `/api/v1` (e.g. `https://docvane-backend.onrender.com/api/v1`).
5. Click **Deploy**.

---

## Verification

Once deployed:
1. Open your live frontend URL.
2. Deposit an agreement or invoice on `/documents/upload`.
3. Inquire about the document on `/chat` and receive live citation-backed AI answers!
