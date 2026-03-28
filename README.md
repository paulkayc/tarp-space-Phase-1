# tarp-space-Phase-1

Phase 1 of Tarp Space: a conversational app where a **Personal Agent** captures durable user context and a **Mandate Agent** turns a specific request into a structured, matchable mandate.

## App summary

This repository contains:

- **FastAPI backend** (Python 3.11, SQLAlchemy, Alembic, pgvector-compatible Postgres).  
- **Next.js frontend** (Next 14 + React 18).  
- **Conversation flows** for:
  - Personal profile onboarding (`/personal-agent`)
  - Transaction-specific mandate collection (`/mandate-agent`)
- **Matching pipeline foundations** (hard constraints + ranking flow described in architecture docs).

The backend serves API routes under `/api/v1/*` and a health endpoint at `/health`. API docs are exposed by FastAPI at `/docs` and `/redoc`.

## Core behavior: mandate specificity

The Mandate Agent asks **one question per reply** and should ask category-specific clarifiers when user intent is broad.

Example:
- User: “I want to buy a car.”
- Agent: “Do you have a specific car in mind, or should I focus on a body style like sedan or SUV?”

This ensures the system captures actionable subtype details before downstream matching.

---

## Quick start (Docker Compose)

### Prerequisites

- Docker + Docker Compose
- An API key for Anthropic if you want live LLM responses

### 1) Clone and configure

```bash
git clone <your-repo-url>
cd tarp-space-Phase-1
```

Create backend env file:

```bash
cat > backend/.env <<'EOF'
APP_ENV=development
APP_PORT=8000
DATABASE_URL=postgresql://tarpspace:tarpspace@postgres:5432/tarpspace
DEV_AUTH_TOKEN=dev-token-local
ADMIN_API_KEY=admin-local
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=
LLM_MODEL=claude-opus-4-6
LLM_MAX_TOKENS=1000
LLM_MAX_HISTORY_TURNS=10
EOF
```

Create frontend env file:

```bash
cp frontend/.env.example frontend/.env.local
```

### 2) Start services

```bash
make up
```

This starts:
- Postgres on `localhost:5432`
- Backend on `localhost:8000`
- Frontend on `localhost:3000`

### 3) Apply migrations and seed sample data

```bash
make migrate
make seed
```

### 4) Open the app

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## Useful developer commands

- `make up` — build + run all services
- `make down` — stop services
- `make migrate` — run Alembic migrations
- `make seed` — load seed inventory data
- `make test` — run backend test suite in container
- `make logs` — stream backend logs
- `make psql` — open psql shell in Postgres container
- `make shell` — open bash shell in backend container

---

## API and frontend notes

- Frontend API base URL is controlled by `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).
- Dev user identity defaults to `X-Dev-User-Id: 00000000-0000-0000-0000-000000000001` from frontend env.
- CORS allows local frontend origins on port `3000`.

---

## Deployment details (important)

This repository is currently configured for **development-oriented container deployment**:

- Backend runs with `uvicorn --reload` in the container.
- Frontend runs with `next dev`.
- Postgres data is persisted in Docker volume `postgres_data`.

For production deployment, recommended changes:

1. Build production images (no hot reload).
2. Run `next build && next start` for frontend.
3. Run backend with a production ASGI setup (e.g., uvicorn workers / process manager).
4. Provide managed secrets (do not hardcode API keys in `.env` committed to git).
5. Lock down CORS and auth settings.
6. Use managed Postgres with backups and TLS.

---

## Architecture and references

- System architecture: `docs/ARCHITECTURE.md`
- API contracts: `docs/CONTRACTS.md`
- Phase summaries: `docs/PHASE1_SUMMARY.md` through `docs/PHASE5_SUMMARY.md`

---

## Troubleshooting

- If backend tests fail with `ModuleNotFoundError: No module named 'app'` outside Docker, run with:
  - `PYTHONPATH=backend pytest ...`
- If API calls fail from frontend, verify:
  - backend is running on `:8000`
  - `NEXT_PUBLIC_API_URL` is set correctly
  - CORS origin matches your frontend URL
