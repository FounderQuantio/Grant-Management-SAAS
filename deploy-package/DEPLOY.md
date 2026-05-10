# GovGuard™ — One-Click Deployment Guide

> Deploy a live grant compliance SaaS in under 30 minutes.

---

## Architecture (5-line summary)

- **Frontend + API** → Vercel (Next.js 14 with API Routes — zero separate backend)
- **Database** → Neon (serverless PostgreSQL, free tier available)
- **Auth** → Auth0 (free tier, 7,500 MAU included)
- **All services connect** via environment variables in Vercel dashboard
- **Total cost at zero scale**: $0/month (all free tiers)

---

## 30-Minute Deploy Checklist

### ⏱ Minute 0–5: Database Setup (Neon)

1. Go to **https://console.neon.tech** → Sign up (free)
2. Click **"New Project"** → Name it `govguard` → Region: `US East`
3. Copy the **Connection String** (looks like `postgresql://user:pass@ep-xxx.neon.tech/govguard?sslmode=require`)
4. Click **"SQL Editor"** in the left panel
5. Paste the entire contents of `infra/schema.sql` → Click **Run**
6. ✅ You now have a live PostgreSQL database with all tables and seed data

### ⏱ Minute 5–15: Auth0 Setup

1. Go to **https://manage.auth0.com** → Sign up (free)
2. Click **"Create Application"** → Name: `GovGuard` → Type: **Regular Web Application**
3. In Settings tab, copy:
   - **Domain** → `AUTH0_ISSUER_BASE_URL = https://{your-domain}.auth0.com`
   - **Client ID** → `AUTH0_CLIENT_ID`
   - **Client Secret** → `AUTH0_CLIENT_SECRET`
4. Under **Allowed Callback URLs**, add: `https://your-app.vercel.app/api/auth/callback`
5. Under **Allowed Logout URLs**, add: `https://your-app.vercel.app`
6. Under **Allowed Web Origins**, add: `https://your-app.vercel.app`
7. Click **Save Changes**
8. Go to **APIs** → **Create API** → Name: `GovGuard API`, Identifier: `https://govguard-api`
9. Generate `AUTH0_SECRET`:
   ```bash
   openssl rand -hex 32
   ```
10. ✅ Auth0 is configured

### ⏱ Minute 15–25: Vercel Deploy

**Option A: GitHub (recommended)**
1. Push this repo to GitHub
2. Go to **https://vercel.com** → **Add New Project**
3. Import your GitHub repo
4. Set **Root Directory** to `frontend`
5. Framework: **Next.js** (auto-detected)

**Option B: Vercel CLI (fastest)**
```bash
cd frontend
npm install -g vercel
vercel --yes
```

### ⏱ Minute 25–30: Environment Variables

In Vercel Dashboard → Project → Settings → **Environment Variables**, add ALL variables from the table below.

Click **Redeploy** after adding all variables.

---

## Environment Variables

| Variable | Where to Get It | Example |
|----------|----------------|---------|
| `DATABASE_URL` | Neon Console → Connection String | `postgresql://user:pass@ep-xxx.neon.tech/govguard?sslmode=require` |
| `AUTH0_SECRET` | Run `openssl rand -hex 32` | `a1b2c3d4...` (32 chars) |
| `AUTH0_BASE_URL` | Your Vercel deployment URL | `https://govguard.vercel.app` |
| `AUTH0_ISSUER_BASE_URL` | Auth0 Dashboard → Domain | `https://yourtenant.us.auth0.com` |
| `AUTH0_CLIENT_ID` | Auth0 Dashboard → Client ID | `abc123...` |
| `AUTH0_CLIENT_SECRET` | Auth0 Dashboard → Client Secret | `xyz789...` |
| `AUTH0_AUDIENCE` | Auth0 API identifier you created | `https://govguard-api` |
| `NEXT_PUBLIC_APP_URL` | Your Vercel URL | `https://govguard.vercel.app` |

---

## Post-Deploy Validation

After deploy, test these URLs:

| Check | URL | Expected |
|-------|-----|----------|
| App loads | `https://your-app.vercel.app` | Redirects to login |
| Login works | Click "Sign In" | Auth0 login page, then dashboard |
| API health | `/api/dashboard/kpis?period=30d` | JSON with KPI data |
| DB connected | Dashboard shows 0 grants | No error, empty state |

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid redirect_uri` | Auth0 callback URL mismatch | Add exact Vercel URL to Auth0 Allowed Callbacks |
| `DATABASE_URL not set` | Missing env var | Add to Vercel environment variables |
| `Cannot read properties of null` | Auth0 session missing | Check `AUTH0_SECRET` is set and 32+ chars |
| `SSL connection required` | Neon requires SSL | Ensure `?sslmode=require` at end of DATABASE_URL |
| `relation does not exist` | Schema not applied | Re-run `infra/schema.sql` in Neon SQL Editor |
| Build fails: `Module not found` | Missing package | Run `npm install` locally, commit `package-lock.json` |
| 500 on API calls | Auth0 claims missing | Add role claims via Auth0 Actions (see below) |

---

## Add Role Claims to Auth0 JWT (Required)

In Auth0 Dashboard → **Actions** → **Library** → **Create Action** → **Login / Post Login**:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = "https://govguard.app";
  
  // Default values — update based on your user metadata
  api.idToken.setCustomClaim(`${namespace}/role`, event.user.app_metadata?.role || "compliance_officer");
  api.idToken.setCustomClaim(`${namespace}/tenant_id`, event.user.app_metadata?.tenant_id || "00000000-0000-0000-0000-000000000001");
  api.idToken.setCustomClaim(`${namespace}/user_id`, event.user.user_id);
  
  api.accessToken.setCustomClaim(`${namespace}/role`, event.user.app_metadata?.role || "compliance_officer");
  api.accessToken.setCustomClaim(`${namespace}/tenant_id`, event.user.app_metadata?.tenant_id || "00000000-0000-0000-0000-000000000001");
};
```

Deploy the action → Attach to **Login Flow**.

---

## Project Structure

```
govguard-deploy/
├── frontend/                    ← Deploy this to Vercel
│   ├── app/
│   │   ├── (app)/               ← Authenticated pages
│   │   │   ├── dashboard/       ← KPI dashboard
│   │   │   ├── grants/          ← Grant management
│   │   │   ├── audit/           ← CAP tracking
│   │   │   └── fraud/pre-award/ ← Fraud screening
│   │   ├── api/                 ← Next.js API Routes (backend)
│   │   │   ├── auth/            ← Auth0 routes
│   │   │   ├── dashboard/       ← KPI endpoints
│   │   │   ├── transactions/    ← Transaction CRUD + risk scoring
│   │   │   ├── grants/          ← Grant management
│   │   │   ├── compliance/      ← Control checklist
│   │   │   ├── fraud/           ← Pre-award screening
│   │   │   └── audit/           ← CAP management
│   │   ├── login/               ← Login page
│   │   └── layout.tsx           ← Root layout
│   ├── lib/
│   │   ├── db.ts                ← Neon database client
│   │   └── auth.ts              ← Auth0 helpers + RBAC
│   ├── middleware.ts             ← Route protection
│   ├── vercel.json              ← Vercel configuration
│   └── package.json
└── infra/
    └── schema.sql               ← Run this in Neon SQL Editor
```

---

## Upgrading to Full GovGuard Production Stack

Once you need FedRAMP Moderate compliance or the Python ML backend:

1. Replace Neon with **AWS RDS PostgreSQL in GovCloud**
2. Add the **Python FastAPI backend** from `GovGuard_Codebase.zip`  
3. Replace Auth0 with **AWS Cognito** (FedRAMP authorized)
4. Add Redis (ElastiCache) for caching + Celery jobs
5. Deploy to **ECS Fargate** on AWS GovCloud

The database schema and API contracts are identical — it's a swap, not a rewrite.
