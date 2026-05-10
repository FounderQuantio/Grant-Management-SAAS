# GovGuard™ Enterprise Platform

**Grant Compliance & Fraud Prevention SaaS**

> A multi-tenant SaaS platform for federal grant compliance and fraud detection, built to FedRAMP Moderate standards.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind CSS, SWR, Zustand |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async |
| Database | PostgreSQL 17 (with RLS multi-tenancy) |
| Cache | Redis 7 |
| Search | OpenSearch 2.x |
| ML | scikit-learn (IsolationForest), SHAP |
| Auth | AWS Cognito (FedRAMP Moderate) |
| Jobs | Celery + Redis |
| Cloud | AWS GovCloud |

## Quick Start (Local Development)

### Prerequisites
- Docker Desktop (or Docker + Docker Compose)
- Node.js 20+ (for frontend dev)
- Python 3.12+ (for backend dev without Docker)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/grant-fraud-detection-system.git
cd grant-fraud-detection-system
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

### 2. Start all services

```bash
docker compose up -d
```

Services will start at:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Flower** (Celery monitor): http://localhost:5555

### 3. Run database migrations

```bash
docker compose exec postgres psql -U govguard_app -d govguard -f /docker-entrypoint-initdb.d/01-schema.sql
docker compose exec postgres psql -U govguard_app -d govguard -f /docker-entrypoint-initdb.d/02-seed.sql
```

### 4. Development without Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Celery Worker:**
```bash
cd backend
celery -A workers.celery_app.celery_app worker --loglevel=info
```

## Project Structure

```
govguard/
├── backend/                    # Python FastAPI backend
│   ├── core/                   # Config, DB, Auth, Cache, S3
│   ├── modules/                # Feature modules (compliance, transactions, etc.)
│   ├── ml/                     # IsolationForest risk scorer + SHAP
│   ├── workers/                # Celery tasks
│   ├── database/               # SQL schema + seed data
│   └── tests/                  # pytest test suite
├── frontend/                   # Next.js 14 frontend
│   ├── app/                    # App Router pages
│   ├── components/             # React components
│   ├── lib/                    # API client, stores, hooks
│   └── types/                  # TypeScript interfaces
├── infra/                      # Terraform (AWS GovCloud)
├── .github/workflows/          # CI/CD pipeline
└── docker-compose.yml
```

## Running Tests

```bash
# Backend
cd backend
pytest tests/ -v --cov=. --cov-report=term-missing

# Frontend
cd frontend
npm run type-check
npm run lint
```

## API Documentation

Available at http://localhost:8000/api/docs (Swagger UI) in development.
All endpoints require `Authorization: Bearer <token>` header.

## Security

- All tenant data isolated via PostgreSQL Row-Level Security
- JWT RS256 tokens validated against Cognito JWKS
- All mutating operations logged to immutable `audit_events` table
- PII fields stored as HMAC-SHA256 hashes
- S3 objects encrypted at rest with KMS

## Architecture

See `GovGuard_Implementation_Blueprint.docx` for the full system specification.
