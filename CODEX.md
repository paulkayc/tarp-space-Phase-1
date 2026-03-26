# CODEX.md

## Purpose
This file is a working guide for contributors and coding agents operating in `tarp-space-phase-1`.
It documents what is implemented, what is scaffolded, and how to run and verify the project.

## Repository Layout
- `backend/`: FastAPI app, SQLAlchemy models, tests, Dockerfile.
- `frontend/`: Next.js 14 app scaffold, minimal UI, API client wrapper.
- `db/`: Alembic environment and SQL migrations.
- `docs/postman_collection.json`: local dev auth + mock mandate API collection.
- `ARCHITECTURE.md`: target architecture and service behavior spec.
- `CONTRACTS.md`: API contracts by phase.

## Current State (March 2026)
This codebase is an early Phase 1 scaffold, not full feature-complete implementation.

Implemented backend routes:
- `GET /health`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `GET /api/v1/agents/me`
- `GET /api/v1/mandates`
- `POST /api/v1/mandates`
- `GET /api/v1/mandates/{mandate_id}`
- `POST /api/v1/mandates/{mandate_id}/confirm` (currently returns fixed 422 validation payload)
- `POST /api/v1/mandates/{mandate_id}/search` (currently returns fixed mock payload)

Scaffolded but not implemented (TODO placeholders):
- Conversation extraction/gap/reflector services
- Mandate CRUD/scoring/schema/audit services
- Matching filter/ranker/escalation services
- Privacy gate
- Explanation/questioner services
- Signal processor/refiner services
- Observability event logger persistence
- Inventory, search, conversation, and activity API modules
- Seed script (`db/seeds/houston_furniture.py`)

## Backend Overview
- Framework: FastAPI
- ORM: SQLAlchemy 2.x
- DB: PostgreSQL + PostGIS + pgvector
- Migrations: Alembic with raw SQL migration files in `db/migrations/`
- Settings: `backend/app/core/config.py` via environment variables
- Auth mode in dev: `X-Dev-User-Id` header must be present and valid UUID

Important behavior:
- Auth dependency auto-creates a local user on first request by `X-Dev-User-Id`.
- User and mandate ownership checks are enforced in implemented mandate routes.
- A custom `HTTPException` handler wraps non-dict details into a standard error object.

## Frontend Overview
- Framework: Next.js 14 + React 18 + TypeScript + Tailwind
- Current UI: single static landing page (`frontend/src/app/page.tsx`)
- API client: Axios wrapper in `frontend/src/lib/api.ts`
- `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`

## Data Model Notes
- Main ORM models are in `backend/app/db/models.py`.
- Initial schema is large and includes:
  - users, mandates, mandate_fields, mandate_versions
  - conversations, messages
  - inventory, search_runs, search_results, signals
  - activity_log, trust_edges, onboarding tables
- Migration `20260308_002_add_auth_fields.py` renamed `dev_user_id` to `external_user_id` and added `clerk_id` + `verified_at`.

## Known Inconsistencies to Resolve
- Auth provider direction is inconsistent across docs/config:
  - `ARCHITECTURE.md` references Supabase
  - `CONTRACTS.md` references Clerk
  - `.env.example` includes both and asks to pick one
- Some architecture/contracts describe routes and behaviors not yet implemented in code.

## Local Development
From repo root:

```bash
make up
make migrate
make test
```

Other useful commands:

```bash
make seed      # currently prints TODO placeholder
make logs
make psql
make shell
make down
```

Direct docker compose equivalents are defined in `Makefile`.

## Testing
- Current tests are in `backend/tests/test_dev_auth_and_mandates.py`.
- Tests use a fake in-memory session override (`backend/tests/conftest.py`), not a real Postgres instance.
- Existing coverage focuses on:
  - dev auth header validation
  - user auto-creation
  - mandate ownership enforcement
  - mandate create response shape

## Conventions for Future Changes
- Keep owner identity derived from auth dependency, never request body.
- Preserve mandate ownership checks on every mandate-scoped route.
- Maintain error payload consistency (`error`, `message`, optional `details`).
- When implementing TODO service modules, align with formulas/rules documented in `ARCHITECTURE.md`.
- If implementing CONTRACTS.md endpoints ahead of full backend logic, return explicit temporary mock responses and label them clearly.

## Suggested Implementation Order
1. Implement mandate domain services (`schema`, `scoring`, `crud`, `audit`) and wire into `mandates.py`.
2. Implement conversation APIs + extraction/gap analysis flow.
3. Implement matching pipeline (`privacy gate` -> `filter` -> `ranker` -> `escalation`).
4. Implement signals ingestion/refinement.
5. Implement observability event writer and activity API.
6. Replace seed placeholder with working inventory seed data.
7. Expand tests from fake session to integration tests against Postgres in Docker.

## Key Files
- `backend/app/main.py`
- `backend/app/core/auth.py`
- `backend/app/core/config.py`
- `backend/app/api/users.py`
- `backend/app/api/agents.py`
- `backend/app/api/mandates.py`
- `backend/app/db/models.py`
- `backend/tests/test_dev_auth_and_mandates.py`
- `db/migrations/20260301_001_initial_schema.py`
- `db/migrations/20260308_002_add_auth_fields.py`
- `frontend/src/app/page.tsx`
- `frontend/src/lib/api.ts`
