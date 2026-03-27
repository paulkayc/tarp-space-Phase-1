# CLAUDE.md — Tarp-Space Phase 1

## Project Overview

Tarp-Space is a marketplace platform with a Personal Agent system. The backend is a FastAPI (Python 3.11) app; the frontend is Next.js 14 (TypeScript). PostgreSQL 16 with `pgvector` and `postgis` is the only data store. Development is containerized via Docker Compose.

---

## Common Commands

```bash
# Start all services
make up

# Apply database migrations
make migrate

# Run backend tests
make test
# or directly:
cd backend && PYTHONPATH=. pytest -q

# Tail backend logs
make logs

# Open psql shell
make psql

# Open backend shell
make shell

# Seed the database
make seed
```

Frontend runs on `http://localhost:3000`, backend on `http://localhost:8000`.
API docs (Swagger): `http://localhost:8000/docs`

---

## Architecture

```
backend/app/
├── agents/personal_agent/   # Agent runtime, tool executor, memory service
├── api/                     # FastAPI route handlers
├── core/                    # config.py (settings), auth.py (dev header auth)
├── db/                      # models.py, session.py
├── observability/           # Structured event logging
├── security/                # ACL policies
└── services/
    ├── conversation/        # LLM-based message extraction
    ├── mandate/             # Mandate CRUD and validation
    ├── matching/            # Filter → rank → escalate pipeline
    └── privacy/gate.py      # Hard privacy gate (runs before any LLM call)
```

Key principles (see `docs/ARCHITECTURE.md`):
- **LLM is reasoning, not source of truth.** All facts come from retrieved/validated context.
- **Privacy gate is hard.** It runs before any LLM processing, no exceptions.
- **Two LLM calls max per request.** Extraction + explanation only. Matching is rule-based.
- **Postgres-first.** No separate vector store — `pgvector` handles embeddings.
- **Observability first-class.** Every significant decision is logged as a structured event.

---

## Auth (Local Dev)

All requests require the header:
```
X-Dev-User-Id: <any-valid-uuid>
```

Users are auto-created on first request. Admin endpoints additionally require:
```
X-Agent-Admin-Key: admin-local
```

There is no session/JWT auth yet. Clerk and Supabase are candidates for cloud auth but not yet chosen.

---

## Environment Setup

Copy `.env.example` to `backend/.env` and `frontend/.env.local`, then fill in:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `ANTHROPIC_API_KEY` | Required for LLM features in production |
| `ADMIN_API_KEY` | Secret for `X-Agent-Admin-Key` header |

The Docker Compose setup uses defaults from `.env.example` automatically.

---

## Database & Migrations

- Tool: **Alembic** with raw SQL migrations
- Migration files: `db/migrations/` — named `YYYYMMDD_NNN_description.py`
- Apply: `make migrate` (runs `alembic upgrade head` inside the backend container)
- Never use `autogenerate` — write migrations by hand in raw SQL

Current migrations:
1. `20260301_001` — Initial schema (all tables, extensions)
2. `20260308_002` — Auth fields (`external_user_id`, `clerk_id`)
3. `20260326_003` — Personal memory tables

---

## Testing

Tests live in `backend/tests/`. The test suite uses `FastAPI.TestClient` with an in-memory fake DB session (`conftest.py`).

```bash
cd backend
PYTHONPATH=. pytest -q                        # all tests
PYTHONPATH=. pytest tests/test_personal_agent_api.py -v   # one file
PYTHONPATH=. pytest --cov=app tests/          # with coverage
```

Write tests for all new API routes and services. Use the existing `conftest.py` fixtures — don't reach out to a real database in unit tests.

---

## Code Conventions

- **Python:** Type-annotated throughout. Use `pydantic` models for request/response shapes. Async SQLAlchemy sessions. `structlog` for all logging.
- **Error responses:** Always return `{"error": "code", "message": "...", "details": {...}}`.
- **TypeScript:** Strict mode. Use the `api.ts` client in `frontend/src/lib/` for all backend calls.
- **Migrations:** Raw SQL only in Alembic migration files.
- **No new vector stores.** Use `pgvector` columns in PostgreSQL.

---

## Key Files

| Purpose | Path |
|---------|------|
| App settings | `backend/app/core/config.py` |
| Dev auth dependency | `backend/app/core/auth.py` |
| ORM models | `backend/app/db/models.py` |
| Personal Agent runtime | `backend/app/agents/personal_agent/runtime.py` |
| Tool executor | `backend/app/agents/personal_agent/tools/executor.py` |
| Memory service | `backend/app/agents/personal_agent/memory/service.py` |
| Personal Agent routes | `backend/app/api/personal_agent.py` |
| Privacy gate | `backend/app/services/privacy/gate.py` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Alembic env | `db/env.py` |

---

## API Base URL

`http://localhost:8000/api/v1`

Notable endpoints:
- `GET /health`
- `GET/PATCH /users/me`
- `GET/POST /mandates`
- `POST /personal-agent/sessions`
- `POST /personal-agent/sessions/{id}/messages`
- `GET /personal-agent/sessions/{id}/memories`
- `POST /personal-agent/admin/tools/reload` (requires admin key)

---

## Docs

- `docs/ARCHITECTURE.md` — System design and data flow
- `docs/CONTRACTS.md` — API contract specs
- `docs/CODEX.md` — Developer guide and conventions
- `docs/PHASE1-5_SUMMARY.md` — Per-phase implementation notes
- `postman_collection.json` — Importable API collection with dev auth pre-configured
