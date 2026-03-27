# ARCHITECTURE.md

> **Tarp-Space — Phase 1: Personal Agent Layer**
> Version: 1.0 | Status: In Review | Last Updated: March 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [System Layers](#3-system-layers)
   - 3.1 [Conversation Layer](#31-conversation-layer)
   - 3.2 [Mandate Layer](#32-mandate-layer)
   - 3.3 [Privacy Gate](#33-privacy-gate)
   - 3.4 [Matching Engine](#34-matching-engine)
   - 3.5 [Explanation Layer](#35-explanation-layer)
4. [End-to-End Data Flow](#4-end-to-end-data-flow)
5. [Service Architecture](#5-service-architecture)
6. [API Reference](#6-api-reference)
7. [LLM Call Discipline](#7-llm-call-discipline)
8. [Database Schema](#8-database-schema)
   - 8.1 [Infrastructure](#81-infrastructure)
   - 8.2 [Table Definitions](#82-table-definitions)
   - 8.3 [Indexes](#83-indexes)
   - 8.4 [Migrations Strategy](#84-migrations-strategy)
9. [Privacy & Security](#9-privacy--security)
10. [Observability](#10-observability)
11. [Configuration](#11-configuration)
12. [Stack Reference](#12-stack-reference)

---

## 1. System Overview

Tarp-Space Phase 1 is a personal agent layer that converts a user's natural language expression of a need into a structured negotiation mandate, then matches that mandate against a seeded marketplace inventory and returns ranked, explained results.

**What Phase 1 is:**
- A conversational mandate builder backed by structured extraction
- A privacy-enforced matching engine against static inventory
- An explainable result system with a feedback and refinement loop

**What Phase 1 is not:**
- A live agent-to-agent negotiation network (Phase 2)
- A real-time Tarp-Space web visualization (Phase 2)
- A trust graph with live edges (Phase 2 — schema is ready, population is not)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                              │
│              (Next.js / React Native — Web + Mobile)                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────────────┐
│                        FASTAPI BACKEND                               │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │  CONVERSATION   │  │    MANDATE      │  │   EXPLANATION      │  │
│  │     LAYER       │  │     LAYER       │  │     LAYER          │  │
│  │  (LLM-powered)  │  │  (rule-based)   │  │  (LLM-powered)     │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────┬──────────┘  │
│           │                    │                      │              │
│           └────────────────────┼──────────────────────┘             │
│                                │                                     │
│                    ┌───────────▼───────────┐                        │
│                    │    PRIVACY GATE        │                        │
│                    │   (pure function,      │                        │
│                    │    no LLM, hard rules) │                        │
│                    └───────────┬───────────┘                        │
│                                │                                     │
│                    ┌───────────▼───────────┐                        │
│                    │   MATCHING ENGINE      │                        │
│                    │   (rule-based + pgvec) │                        │
│                    └───────────┬───────────┘                        │
└────────────────────────────────┼────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                    POSTGRESQL 16 + pgvector                          │
│         (mandates, inventory, conversations, signals, logs)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Principles

These principles govern all implementation decisions in Phase 1. They are listed in priority order. When a decision conflicts with a lower-priority principle, the higher-priority principle wins.

| # | Principle | Implication |
|---|-----------|-------------|
| 1 | **The LLM is the reasoning layer, not the system of record** | All facts come from retrieved, validated, structured context — never from model weights. Every LLM output is validated against a schema before being persisted |
| 2 | **Privacy enforcement precedes LLM invocation** | The Privacy Gate is a hard code layer, not a prompt instruction. It runs before any mandate data is passed downstream |
| 3 | **Extraction first, questions second** | On every user message, extract every possible mandate field before asking any question. Ask only about gaps, never about fields already provided |
| 4 | **Observability is first-class from day one** | Every negotiation decision, mandate change, match outcome, and feedback signal is logged as a structured event. No silent failures |
| 5 | **Explainability over accuracy in Phases 0–2** | A tunable weighted score that can be audited beats an opaque embedding model. Every match score is decomposable |
| 6 | **Postgres-first** | No Neo4j, no dedicated vector store, no Redis until Postgres is confirmed as the bottleneck. pgvector handles all embedding similarity in Phase 1 |
| 7 | **Two LLM calls per request maximum** | Extraction pass + explanation generation. The matching pipeline — privacy gate, hard filter, semantic ranking — contains zero LLM calls |

---

## 3. System Layers

### 3.1 Conversation Layer

**Owner:** Dev A
**LLM:** Yes — Claude Sonnet (claude-sonnet-4-20250514)
**Responsibility:** Convert natural language user messages into structured mandate deltas. Identify gaps. Generate targeted gap-filling questions. Reflect the assembled mandate back for owner confirmation.

#### Extraction Pass

Every user message triggers an extraction pass before any question is asked. The extraction prompt receives:
- The user's raw message
- The current mandate state (which fields are already filled)
- The mandate field schema with types and examples

The LLM returns a structured JSON delta containing only newly extractable fields. All extracted fields are tagged `source: "inferred"`.

```
User: "I want a mid-century modern couch under $500 in Montrose, pet-friendly"

Extraction output:
{
  "category": "couch",
  "intent_type": "buy",
  "vertical": "goods",
  "negotiation_range": [{ "dimension": "price", "ceiling": 500 }],
  "location": "Montrose, Houston TX",
  "soft_preferences": [{ "attribute": "style", "value": "mid-century modern" },
                       { "attribute": "pet_friendly", "value": true }]
}
```

#### Gap Analysis

After extraction, the system computes the updated completeness score. If the score is below 0.7, the gap analysis identifies the highest-priority unfilled field using the dimension priority order:

```
Priority order:
1. intent_type
2. vertical
3. category          ← if missing, always ask first
4. price / budget
5. location
6. condition
7. timing
8. style / aesthetic
9. dealbreakers
10. autonomy_level   ← never extracted, always explicitly set
```

Only one gap question is asked per message turn. The question is generated by the LLM using a focused prompt: the gap dimension, the mandate context so far, and a one-question constraint.

#### Mandate Confirmation

When completeness reaches 0.7, the agent generates a plain-language mandate reflection and presents it to the owner for confirmation. The owner can:
- Confirm as-is → mandate is marked `active`, version incremented
- Correct a field inline → field updated with `source: "explicit"`, loop resumes
- Start over → mandate reset, new conversation started

No matching occurs until the owner has explicitly confirmed the mandate.

---

### 3.2 Mandate Layer

**Owner:** Dev A
**LLM:** No
**Responsibility:** Mandate CRUD, schema validation, completeness scoring, version history, and the mandate audit interface.

#### Completeness Score

Computed as a weighted sum of filled dimensions:

```
completeness_score =
  0.35 × (intent_type_filled AND vertical_filled AND category_filled)
  + 0.20 × price_range_filled
  + 0.15 × location_filled
  + 0.075 × condition_filled
  + 0.075 × timing_filled
  + 0.10 × (len(soft_preferences) > 0)
  + 0.05 × (len(dealbreakers) >= 0)   ← always contributes; 0 dealbreakers is valid
```

Minimum score to activate mandate: **0.7**

#### Version History

Every mandate write increments the version counter. The previous version is snapshotted into `mandate_versions` before the update. This enables:
- Full audit trail for any mandate field
- Rollback if owner disputes an inferred change
- Training data for the refinement loop (which inferences proved correct)

#### Source Flags

Every mandate field carries a `source` attribute:
- `"explicit"` — owner stated this directly
- `"inferred"` — agent extracted this from context
- `"defaulted"` — system applied a default value

Inferred fields are always surfaced with a visual indicator in the audit UI and can be overridden by the owner at any time.

---

### 3.3 Privacy Gate

**Owner:** Dev B
**LLM:** No — pure deterministic function
**Responsibility:** Hard enforcement of mandate privacy rules before any mandate data is passed to the matching engine or any external service.

The Privacy Gate is a pure function: `gate(mandate) → sanitized_signal`. It has no side effects other than logging. It never calls an LLM.

#### Hard Rules (Phase 1)

| Rule | Enforcement |
|------|-------------|
| `negotiation_range` ceiling and floor are never transmitted as a range | Stripped to current position + directional signal: `{ "dimension": "price", "position": 400, "direction": "flexible_up" }` |
| `dealbreakers` are never transmitted raw | Evaluated locally against each candidate. Matching engine receives `dealbreaker_satisfied: true/false` only |
| `hard_constraints` are never transmitted raw | Same pattern — boolean satisfaction signal only |
| Opening position must not equal ceiling or floor | Validated on mandate activation; mandate rejected if violated |
| Location transmitted as fuzzy bounding box in Phase 1 | Exact coordinates only after introduction (Phase 2 feature) |

#### Gate Event Logging

Every gate decision is logged as a `privacy_gate_decision` event regardless of pass/strip/block outcome. This is non-negotiable — the gate log is the audit trail for any future privacy incident review.

```json
{
  "event": "privacy_gate_decision",
  "mandate_id": "uuid",
  "field": "negotiation_range",
  "action": "strip_to_signal",
  "rule_applied": "range_never_transmitted",
  "timestamp": "2026-03-01T12:00:00Z"
}
```

---

### 3.4 Matching Engine

**Owner:** Dev B
**LLM:** No
**Responsibility:** Three-stage pipeline — hard constraint filter, semantic ranking, escalation flagging. Returns a ranked list of candidates with alignment scores.

#### Stage 1: Hard Constraint Filter

Deterministic elimination of candidates that violate any hard constraint or dealbreaker. Runs SQL — no embeddings, no scoring.

```sql
SELECT i.*
FROM inventory i
WHERE i.category = :category
  AND i.vertical = :vertical
  AND ST_DWithin(i.location_geom, :user_location, :radius_meters)
  AND i.price <= :price_ceiling
  AND i.is_active = true
  -- dealbreaker conditions appended dynamically per mandate
```

Target latency: **< 100ms** on 500 listings.

#### Stage 2: Semantic Ranking

Generates an embedding from `mandate.description` and computes cosine similarity against pre-computed listing embeddings using pgvector.

```sql
SELECT
  i.id,
  i.price,
  i.metadata,
  1 - (i.embedding <=> :mandate_embedding) AS similarity_score,
  COALESCE(te.weight, 0.0) AS trust_weight
FROM inventory i
LEFT JOIN trust_edges te
  ON te.to_user_id = i.seller_id
  AND te.from_user_id = :owner_id
WHERE i.id = ANY(:candidate_ids)
ORDER BY (similarity_score * (1 + trust_weight * 0.3)) DESC
LIMIT :top_n;
```

**Alignment score formula:**

```
alignment_score = similarity_score × (1 + trust_weight × 0.3)
```

Trust weight is `0.0` for Phase 1 (no live trust graph). The column and formula are in place for Phase 2 activation.

#### Stage 3: Escalation Flagging

Candidates that failed the hard filter only because of price (within configurable threshold) are re-evaluated and flagged:

```
escalation_threshold = mandate.price_ceiling × 1.15  (default: 15% above ceiling)

if candidate.price > mandate.price_ceiling
   AND candidate.price <= escalation_threshold
   AND candidate.similarity_score >= 0.75:
     flag as ESCALATION_CANDIDATE
```

Escalation candidates are not returned in the main results list. They are returned in a separate `escalations` array in the search response, each with a generated escalation question.

---

### 3.5 Explanation Layer

**Owner:** Dev A
**LLM:** Yes — Claude Sonnet
**Responsibility:** Generate plain-language explanations for each top-N match result and specific yes/no questions for each escalation candidate.

#### Match Explanation Prompt

Context: listing metadata + mandate summary + matched dimensions
Output: 2–3 sentence plain-language explanation of why this listing aligns with the mandate.

Constraint: **Only reference attributes present in the listing metadata.** No hallucinated attributes. Output validated against listing schema before returning to client.

```
Example output:
"Strong match: the listing describes a mid-century walnut frame confirmed in
the photos, seller notes it's in like-new condition, and it's 0.4mi from
Montrose center — $80 below your ceiling."
```

#### Escalation Question Format

```
"This listing is $[delta] above your ceiling but matches on [matched_dims].
Want me to explore it?"
```

The question is always binary (yes/no). It never asks an open-ended question. The delta and matched dimensions are injected from structured data — not generated by the LLM.

---

## 4. End-to-End Data Flow

```
User: "I want a mid-century couch under $500 in Montrose"
  │
  ▼
[POST /conversations/{id}/messages]
  │
  ├─► EXTRACTION PASS (LLM call #1)
  │     Input: user message + current mandate state
  │     Output: mandate_delta JSON
  │     Fields extracted: category, intent_type, vertical,
  │                        price_ceiling, location, style_pref
  │
  ├─► GAP ANALYSIS (rule-based)
  │     completeness_score = 0.55
  │     gaps_remaining = ["condition", "timing"]
  │     next_question = "condition" (highest priority gap)
  │
  ├─► MANDATE UPDATE
  │     Persist delta to mandate_fields
  │     Increment version, snapshot to mandate_versions
  │     Update completeness_score
  │
  └─► RESPONSE: agent question about condition
        "What condition are you looking for?"

— [user answers: "like-new or good, no major wear"] —

  ├─► EXTRACTION PASS (LLM call #1)
  │     Extracts: condition = ["like-new", "good"]
  │     completeness_score = 0.70 → threshold reached
  │
  ├─► MANDATE REFLECTION (LLM call #1)
  │     Generate plain-language summary for owner confirmation
  │
  └─► RESPONSE: mandate reflection + confirm prompt

— [user confirms] —

[POST /mandates/{id}/confirm]
  │
  ├─► Mandate marked active, version locked
  │
  └─► Triggers search automatically OR user taps "Find matches"

[POST /mandates/{id}/search]
  │
  ├─► PRIVACY GATE
  │     Strip price range → positional signal
  │     Evaluate dealbreakers locally (none set)
  │     Fuzz location to bounding box
  │     Log gate decisions
  │
  ├─► HARD CONSTRAINT FILTER (SQL)
  │     Filter: category=couch, location within 5mi,
  │             price <= 500, is_active=true
  │     500 listings → 47 candidates
  │
  ├─► SEMANTIC RANKING (pgvector)
  │     Generate embedding from mandate.description
  │     Cosine similarity vs. 47 candidate embeddings
  │     Apply trust weight (0.0 in Phase 1)
  │     Rank and return top 5
  │
  ├─► ESCALATION FLAG
  │     2 listings: price $520–$540, similarity >= 0.75
  │     Flagged as escalation candidates
  │
  ├─► EXPLANATION GENERATION (LLM — up to 5 calls)
  │     Per top-5 result: listing metadata + mandate → explanation
  │
  ├─► ESCALATION QUESTION GENERATION (LLM — up to 2 calls)
  │     Per escalation candidate: delta + matched dims → question
  │
  └─► RESPONSE: 5 results with scores + explanations
                + 2 escalation prompts

— [user rejects result #2: "leather, I wanted fabric"] —

[POST /mandates/{id}/signals]
  │
  ├─► Signal logged: signal_type=reject, result_id, reason extracted
  │
  ├─► Refinement: "leather" → new dealbreaker with source=inferred
  │
  ├─► Refinement prompt surfaced to user:
  │     "I noticed you rejected leather — add 'no leather' as a
  │      dealbreaker for this search?"
  │
  └─► On confirm: mandate updated, new search triggered
```

---

## 5. Service Architecture

All services run within a single FastAPI application in Phase 1. The internal module boundaries are designed for extraction into separate services in Phase 2 without API changes.

```
tarpspace/
├── api/
│   ├── conversations.py      # POST /conversations, POST /conversations/{id}/messages
│   ├── mandates.py           # GET/PATCH /mandates/{id}, POST /mandates/{id}/confirm
│   ├── search.py             # POST /mandates/{id}/search, POST /mandates/{id}/signals
│   ├── inventory.py          # GET/POST /inventory (admin)
│   └── activity.py           # GET /agents/{owner_id}/activity
│
├── services/
│   ├── conversation/
│   │   ├── extractor.py      # LLM extraction pass — mandate delta from user message
│   │   ├── gap_analyzer.py   # Rule-based gap detection and priority ordering
│   │   └── reflector.py      # LLM mandate reflection for owner confirmation
│   │
│   ├── mandate/
│   │   ├── schema.py         # Mandate dataclass, field validators
│   │   ├── scoring.py        # Completeness score computation
│   │   ├── crud.py           # DB read/write with version management
│   │   └── audit.py          # Version history retrieval
│   │
│   ├── privacy/
│   │   └── gate.py           # Pure function: mandate → sanitized signal
│   │
│   ├── matching/
│   │   ├── filter.py         # Hard constraint SQL filter
│   │   ├── ranker.py         # pgvector semantic ranking
│   │   └── escalation.py     # Escalation threshold flagging
│   │
│   ├── explanation/
│   │   ├── explainer.py      # LLM match explanation generation
│   │   └── questioner.py     # LLM escalation question generation
│   │
│   └── signals/
│       ├── processor.py      # Accept/reject signal ingestion
│       └── refiner.py        # Mandate delta computation from signals
│
├── db/
│   ├── models.py             # SQLAlchemy models
│   ├── migrations/           # Alembic migrations
│   └── seeds/                # Seeded Houston inventory data + embeddings
│
└── observability/
    └── events.py             # Structured event logger (all event types)
```

---

## 6. API Reference

### Authentication

All endpoints require a valid JWT from Supabase Auth. The `owner_id` is extracted from the JWT — never accepted as a request parameter. This prevents any cross-user data access.

```
Authorization: Bearer <supabase_jwt>
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/conversations` | Create new conversation session |
| `POST` | `/api/v1/conversations/{id}/messages` | Send user message, receive agent response (SSE streaming supported) |
| `GET` | `/api/v1/mandates/{mandate_id}` | Retrieve full mandate with source flags |
| `PATCH` | `/api/v1/mandates/{mandate_id}` | Explicit owner field update |
| `POST` | `/api/v1/mandates/{mandate_id}/confirm` | Owner confirms mandate — activates for matching |
| `GET` | `/api/v1/mandates/{mandate_id}/history` | Full version history |
| `POST` | `/api/v1/mandates/{mandate_id}/search` | Run match search against inventory |
| `POST` | `/api/v1/mandates/{mandate_id}/signals` | Submit accept/reject signal |
| `GET` | `/api/v1/agents/{owner_id}/activity` | Agent activity log |
| `GET` | `/api/v1/inventory` | List seeded inventory (admin) |
| `POST` | `/api/v1/inventory` | Add listing to inventory (admin) |

### Key Response Shapes

**`POST /conversations/{id}/messages`**

```json
{
  "agent_message": "What condition are you looking for?",
  "mandate_delta": {
    "category": "couch",
    "intent_type": "buy",
    "vertical": "goods",
    "negotiation_range": [{ "dimension": "price", "ceiling": 500 }],
    "location": "Montrose, Houston TX",
    "soft_preferences": [
      { "attribute": "style", "value": "mid-century modern" },
      { "attribute": "pet_friendly", "value": true }
    ]
  },
  "completeness_score": 0.55,
  "gaps_remaining": ["condition", "timing"],
  "ready_to_match": false
}
```

**`POST /mandates/{id}/search`**

```json
{
  "search_id": "uuid",
  "mandate_version": 3,
  "results": [
    {
      "listing_id": "uuid",
      "alignment_score": 0.91,
      "price": 420,
      "within_mandate": true,
      "matched_dimensions": ["style", "condition", "location", "price"],
      "explanation": "Strong match: mid-century style confirmed in listing photos, like-new condition, 0.4mi from Montrose center, $80 below your ceiling.",
      "escalation": null
    }
  ],
  "escalations": [
    {
      "listing_id": "uuid2",
      "alignment_score": 0.82,
      "price": 560,
      "within_mandate": false,
      "threshold_delta": 60,
      "question": "This listing is $60 above your ceiling but matches on style and condition. Want me to explore it?"
    }
  ]
}
```

---

## 7. LLM Call Discipline

The LLM is called in exactly three places. Every other component is deterministic. Token budgets are enforced at the call site — not advisory.

| Call | Trigger | Context Budget | Output Budget | Max Frequency |
|------|---------|---------------|---------------|---------------|
| Extraction pass | Every user message during mandate build | 600 tokens | 400 tokens (structured JSON) | 1× per message |
| Mandate reflection | When completeness reaches 0.7 | 500 tokens | 350 tokens | 1× per mandate |
| Gap question generation | When completeness < 0.7 and gaps remain | 400 tokens | 200 tokens (single question) | 1× per message turn |
| Match explanation | Per top-N result (max 5) | 700 tokens | 400 tokens | Up to 5× per search |
| Escalation question | Per escalation-flagged result (max 3) | 400 tokens | 200 tokens | Up to 3× per search |

**Cost alert threshold:** $0.05 per user per month. Alert fires to ops channel when exceeded. This is the leading indicator of runaway context or unnecessary LLM calls.

**LLM output validation:** Every LLM output that modifies a mandate field must be validated against the mandate field schema before persistence. Invalid outputs are logged and discarded — they never reach the database.

---

## 8. Database Schema

### 8.1 Infrastructure

- **Engine:** PostgreSQL 16
- **Extensions:** `pgvector` (embedding similarity), `postgis` (location queries), `uuid-ossp` (UUID generation)
- **Connection pooling:** PgBouncer in transaction mode (Phase 1 can skip if DigitalOcean managed PG is used)
- **Backups:** Daily automated snapshots via DigitalOcean managed database
- **Trust graph schema:** Neo4j-compatible from day one. When multi-hop traversal warrants a dedicated graph DB, `trust_edges` migrates without schema changes

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "postgis";
```

---

### 8.2 Table Definitions

---

#### `users`

Identity and profile. Owner of all mandates, conversations, and agent activity.

```sql
CREATE TABLE users (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email             TEXT NOT NULL UNIQUE,
  name              TEXT NOT NULL,
  phone             TEXT,
  -- Location stored as both raw string and geometry for proximity queries
  location_raw      TEXT,                            -- "Montrose, Houston TX"
  location_geom     GEOGRAPHY(POINT, 4326),          -- PostGIS point
  -- Auth
  supabase_user_id  TEXT NOT NULL UNIQUE,            -- foreign key to Supabase Auth
  verified_at       TIMESTAMPTZ,
  -- Agent configuration
  autonomy_default  TEXT NOT NULL DEFAULT 'escalate_key_points'
                    CHECK (autonomy_default IN ('supervised', 'escalate_key_points', 'fully_autonomous')),
  -- Trust graph seed
  community_ids     TEXT[],                          -- community membership strings
  -- Metadata
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `mandates`

One row per active negotiation transaction. A user may have multiple mandates (e.g. buying a couch AND selling a lamp simultaneously).

```sql
CREATE TABLE mandates (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- Core classification
  intent_type           TEXT CHECK (intent_type IN ('buy','sell','request_service','offer_service','discover')),
  vertical              TEXT CHECK (vertical IN ('goods','services')),
  category              TEXT,                        -- "couch", "plumber", "guitar lessons"
  -- Mandate content (denormalized for fast reads; authoritative in mandate_fields)
  description           TEXT,                        -- LLM-generated natural language summary
  hard_constraints      JSONB NOT NULL DEFAULT '[]',
  negotiation_range     JSONB NOT NULL DEFAULT '[]',
  soft_preferences      JSONB NOT NULL DEFAULT '[]',
  dealbreakers          JSONB NOT NULL DEFAULT '[]',
  escalation_triggers   JSONB NOT NULL DEFAULT '[]',
  -- Agent configuration
  autonomy_level        TEXT NOT NULL DEFAULT 'escalate_key_points'
                        CHECK (autonomy_level IN ('supervised','escalate_key_points','fully_autonomous')),
  -- Status
  completeness_score    NUMERIC(4,3) NOT NULL DEFAULT 0.0 CHECK (completeness_score BETWEEN 0 AND 1),
  is_active             BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE only after owner confirms
  is_archived           BOOLEAN NOT NULL DEFAULT FALSE,
  -- Versioning
  version               INTEGER NOT NULL DEFAULT 1,
  -- Timestamps
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_at          TIMESTAMPTZ,
  archived_at           TIMESTAMPTZ
);
```

---

#### `mandate_fields`

Per-field granular storage with source tracking. This is the authoritative record of how each mandate field was populated. The denormalized columns in `mandates` are derived from this table.

```sql
CREATE TABLE mandate_fields (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  mandate_id   UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
  field_name   TEXT NOT NULL,                        -- "category", "price_ceiling", etc.
  field_value  JSONB NOT NULL,                       -- typed value as JSON
  source       TEXT NOT NULL DEFAULT 'inferred'
               CHECK (source IN ('explicit', 'inferred', 'defaulted')),
  version      INTEGER NOT NULL,                     -- mandate version when this was set
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (mandate_id, field_name, version)
);
```

---

#### `mandate_versions`

Full snapshots of the mandate at each version. Enables complete audit trail and rollback.

```sql
CREATE TABLE mandate_versions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  mandate_id      UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
  version         INTEGER NOT NULL,
  snapshot        JSONB NOT NULL,                    -- full mandate state at this version
  changed_fields  TEXT[],                            -- fields that changed vs. prior version
  change_source   TEXT NOT NULL                      -- "user_message", "explicit_edit", "signal_refinement"
                  CHECK (change_source IN ('user_message', 'explicit_edit', 'signal_refinement', 'confirmation')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (mandate_id, version)
);
```

---

#### `conversations`

Session metadata. One conversation per mandate-building flow.

```sql
CREATE TABLE conversations (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mandate_id      UUID REFERENCES mandates(id) ON DELETE SET NULL,
  status          TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'confirmed', 'abandoned')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `messages`

Individual messages within a conversation. Stores agent responses alongside the mandate delta they produced.

```sql
CREATE TABLE messages (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role             TEXT NOT NULL CHECK (role IN ('user', 'agent')),
  content          TEXT NOT NULL,
  -- Structured data produced by this exchange
  mandate_delta    JSONB,                             -- fields extracted from this user message
  completeness_after NUMERIC(4,3),                   -- score after applying this delta
  gaps_remaining   TEXT[],                           -- gap dimensions still unfilled
  -- Metadata
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  token_count      INTEGER                           -- for LLM cost tracking
);
```

---

#### `inventory`

Seeded marketplace listings. Phase 1 is static (admin-populated). Phase 2 will add live seller agent entries.

```sql
CREATE TABLE inventory (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  seller_id       UUID REFERENCES users(id) ON DELETE SET NULL,
  -- Classification
  vertical        TEXT NOT NULL CHECK (vertical IN ('goods', 'services')),
  category        TEXT NOT NULL,
  -- Content
  title           TEXT NOT NULL,
  description     TEXT NOT NULL,
  metadata        JSONB NOT NULL DEFAULT '{}',       -- condition, style, dimensions, photos, etc.
  -- Pricing
  price           NUMERIC(10, 2) NOT NULL,
  price_negotiable BOOLEAN NOT NULL DEFAULT TRUE,
  -- Location
  location_raw    TEXT,
  location_geom   GEOGRAPHY(POINT, 4326),
  -- Embedding for semantic matching (pgvector)
  embedding       VECTOR(1536),                      -- dimension matches embedding model output
  -- Status
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  -- Timestamps
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `search_runs`

Metadata for each matching run. One row per call to `POST /mandates/{id}/search`.

```sql
CREATE TABLE search_runs (
  id                           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  mandate_id                   UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
  mandate_version              INTEGER NOT NULL,
  -- Result summary
  candidates_pre_filter        INTEGER,               -- inventory rows before hard filter
  candidates_post_filter       INTEGER,               -- rows surviving hard filter
  result_count                 INTEGER,               -- rows returned to user
  escalation_count             INTEGER,               -- escalation candidates flagged
  top_score                    NUMERIC(5,4),
  -- Performance
  latency_ms                   INTEGER,
  -- Timestamps
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `search_results`

Individual results within a search run, including explanation and escalation data.

```sql
CREATE TABLE search_results (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  search_run_id     UUID NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
  listing_id        UUID NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
  -- Scoring
  similarity_score  NUMERIC(5,4) NOT NULL,
  trust_weight      NUMERIC(5,4) NOT NULL DEFAULT 0.0,
  alignment_score   NUMERIC(5,4) NOT NULL,           -- final composite score
  within_mandate    BOOLEAN NOT NULL,
  matched_dimensions TEXT[],
  -- Explanation (LLM-generated)
  explanation       TEXT,
  -- Escalation (only set if within_mandate = FALSE and escalation flagged)
  is_escalation     BOOLEAN NOT NULL DEFAULT FALSE,
  escalation_delta  NUMERIC(10,2),                   -- how far above ceiling
  escalation_question TEXT,
  -- Timestamps
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `signals`

Accept/reject feedback from owners on individual search results. This is the primary training signal for mandate refinement.

```sql
CREATE TABLE signals (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  search_result_id      UUID NOT NULL REFERENCES search_results(id) ON DELETE CASCADE,
  -- Signal
  signal_type           TEXT NOT NULL CHECK (signal_type IN ('accept', 'reject', 'escalation_yes', 'escalation_no')),
  reason                TEXT,                        -- optional owner-provided reason
  -- Mandate update applied as a result of this signal
  mandate_delta_applied JSONB,                       -- null if no refinement triggered
  mandate_version_after INTEGER,                     -- version after refinement applied
  -- Timestamps
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `activity_log`

Structured event store. Every agent action, mandate change, and system event is written here. This is the primary observability surface and the training data for Phase 2 improvements.

```sql
CREATE TABLE activity_log (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id    UUID REFERENCES users(id) ON DELETE SET NULL,
  mandate_id  UUID REFERENCES mandates(id) ON DELETE SET NULL,
  event_type  TEXT NOT NULL,                         -- see Section 10 for full enum
  payload     JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### `trust_edges`

Graph adjacency table. Phase 1: populated via community membership only. Phase 2: transactions and vouching. Schema is Neo4j-compatible for future migration.

```sql
CREATE TABLE trust_edges (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  from_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  to_user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- Edge classification
  edge_type     TEXT NOT NULL
                CHECK (edge_type IN ('transaction', 'vouched', 'community', 'referral')),
  weight        NUMERIC(4,3) NOT NULL DEFAULT 0.4
                CHECK (weight BETWEEN 0 AND 1),
  -- Provenance
  source_ref    TEXT,                                -- transaction_id, community_name, etc.
  -- Lifecycle
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ,                         -- null = no expiry
  revoked_at    TIMESTAMPTZ,
  -- Constraint: no duplicate edges of same type between same pair
  UNIQUE (from_user_id, to_user_id, edge_type)
);
```

**Default weights by edge type (from PRD):**

| Edge Type | Initial Weight | Update Trigger |
|-----------|---------------|----------------|
| `transaction` | 0.7 | Positive outcome → 0.9; dispute → 0.2 |
| `vouched` | 0.6 | Revocable; revocation cascades to 0.0 |
| `community` | 0.4 | Expires if membership lapses |
| `referral` | 0.5 | Boosted to 0.7 after invitee completes first transaction |

---

### 8.3 Indexes

```sql
-- mandates: owner lookups and active mandate queries
CREATE INDEX idx_mandates_owner_id          ON mandates (owner_id);
CREATE INDEX idx_mandates_owner_active      ON mandates (owner_id) WHERE is_active = TRUE;
CREATE INDEX idx_mandates_intent_vertical   ON mandates (intent_type, vertical);

-- mandate_fields: per-mandate field lookups
CREATE INDEX idx_mandate_fields_mandate_id  ON mandate_fields (mandate_id);
CREATE INDEX idx_mandate_fields_field_name  ON mandate_fields (mandate_id, field_name);

-- mandate_versions: version history traversal
CREATE INDEX idx_mandate_versions_mandate   ON mandate_versions (mandate_id, version DESC);

-- conversations: owner conversation lookups
CREATE INDEX idx_conversations_owner_id     ON conversations (owner_id);
CREATE INDEX idx_conversations_mandate_id   ON conversations (mandate_id);

-- messages: conversation message retrieval
CREATE INDEX idx_messages_conversation_id   ON messages (conversation_id, created_at ASC);

-- inventory: core matching indexes
CREATE INDEX idx_inventory_category_vertical ON inventory (category, vertical) WHERE is_active = TRUE;
CREATE INDEX idx_inventory_price             ON inventory (price) WHERE is_active = TRUE;
CREATE INDEX idx_inventory_location          ON inventory USING GIST (location_geom);
-- pgvector IVFFlat index for approximate nearest neighbor search
-- nlist=50 appropriate for Phase 1 inventory size (~100–500 listings)
-- Rebuild with nlist=100 when inventory exceeds 10,000 rows
CREATE INDEX idx_inventory_embedding         ON inventory USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- search_results: mandate-based result retrieval
CREATE INDEX idx_search_results_run_id      ON search_results (search_run_id);
CREATE INDEX idx_search_results_listing_id  ON search_results (listing_id);

-- signals: refinement loop queries
CREATE INDEX idx_signals_owner_id           ON signals (owner_id, created_at DESC);
CREATE INDEX idx_signals_result_id          ON signals (search_result_id);

-- trust_edges: graph traversal
CREATE INDEX idx_trust_edges_from_user      ON trust_edges (from_user_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_trust_edges_to_user        ON trust_edges (to_user_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_trust_edges_type           ON trust_edges (from_user_id, edge_type) WHERE revoked_at IS NULL;

-- activity_log: owner activity feed + event type queries
CREATE INDEX idx_activity_log_owner         ON activity_log (owner_id, created_at DESC);
CREATE INDEX idx_activity_log_mandate       ON activity_log (mandate_id, created_at DESC);
CREATE INDEX idx_activity_log_event_type    ON activity_log (event_type, created_at DESC);
```

---

### 8.4 Migrations Strategy

Migrations are managed with **Alembic**. All migration scripts live in `db/migrations/`. The migration naming convention is:

```
YYYYMMDD_NNN_description.py
e.g. 20260301_001_initial_schema.py
     20260308_002_add_trust_edges.py
```

**Rules:**
- Never modify an existing migration. Always add a new one.
- Every migration must be reversible (implement `downgrade()`).
- Migrations run automatically on deploy via the FastAPI startup event in non-production environments. In production, migrations are run manually before deployment.
- The `trust_edges` table is included in the initial migration even though it is unpopulated in Phase 1. This prevents a schema migration when Phase 2 activates.

---

## 9. Privacy & Security

### Mandate Privacy

Privacy enforcement is a hard code layer, not an LLM instruction. See [Section 3.3 (Privacy Gate)](#33-privacy-gate) for full rule definitions.

### Cross-User Isolation

All database queries that access mandate, conversation, message, or signal data include an `owner_id` predicate derived from the authenticated JWT. This predicate is applied at the query layer, not the application layer:

```python
# In mandate CRUD — owner_id always injected from JWT, never from request body
def get_mandate(mandate_id: UUID, owner_id: UUID) -> Mandate:
    return db.query(Mandate).filter(
        Mandate.id == mandate_id,
        Mandate.owner_id == owner_id   # ← hard-coded scope
    ).first()
```

### Input Sanitization

All user-generated content (listing descriptions, mandate fields, chat messages) is sanitized before being injected into LLM prompts. The sanitization pipeline:
1. Strip HTML and script tags
2. Truncate to field-specific character limit
3. Wrap in XML delimiters in the prompt to prevent injection: `<user_content>...</user_content>`

### Authentication

Supabase Auth. JWTs are verified on every request via FastAPI middleware. The `owner_id` is the Supabase user UUID, linked to `users.supabase_user_id` on first login.

---

## 10. Observability

All events are emitted as structured JSON to stdout and persisted to `activity_log`. No silent failures — if an event cannot be logged, the operation raises an error.

| Event Type | Key Payload Fields |
|------------|--------------------|
| `mandate_created` | `owner_id`, `mandate_id`, `vertical`, `completeness_score`, `autonomy_level` |
| `mandate_updated` | `mandate_id`, `field_changed`, `old_value`, `new_value`, `source` |
| `extraction_completed` | `mandate_id`, `message_id`, `fields_extracted`, `fields_remaining`, `completeness_score`, `latency_ms` |
| `mandate_confirmed` | `mandate_id`, `completeness_score`, `version`, `confirmed_at` |
| `search_started` | `mandate_id`, `mandate_version`, `search_id` |
| `privacy_gate_decision` | `mandate_id`, `field`, `action`, `rule_applied` |
| `search_completed` | `search_id`, `candidate_count_pre_filter`, `candidate_count_post_filter`, `top_score`, `latency_ms` |
| `escalation_triggered` | `search_id`, `result_id`, `listing_id`, `threshold_delta`, `question_text` |
| `signal_received` | `owner_id`, `search_result_id`, `signal_type`, `reason`, `mandate_delta_applied` |
| `mandate_refined` | `mandate_id`, `field_changed`, `trigger_signal_id`, `old_value`, `new_value` |

---

## 11. Configuration

All environment-specific values are in `.env`. No secrets in code.

```env
# Application
APP_ENV=development                       # development | staging | production
APP_PORT=8000

# Database
DATABASE_URL=postgresql://user:pass@host:5432/tarpspace

# Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# LLM
ANTHROPIC_API_KEY=...
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=1000

# Matching
ESCALATION_THRESHOLD_PCT=0.15            # 15% above mandate ceiling
MATCH_TOP_N=5                            # max results returned
MATCH_RADIUS_DEFAULT_M=8046              # ~5 miles in meters
COMPLETENESS_THRESHOLD=0.7              # min score before matching

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small  # or claude-embeddings when available
EMBEDDING_DIM=1536

# Observability
LOG_LEVEL=INFO
LLM_COST_ALERT_THRESHOLD_USD=0.05       # per user per month
```

---

## 12. Stack Reference

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Backend API | FastAPI | 0.115+ | Async-native; SSE for streaming |
| LLM Orchestration | Anthropic SDK + Pydantic AI | Latest | Structured outputs for mandate schema |
| Primary Database | PostgreSQL | 16 | Managed via DigitalOcean |
| Vector Similarity | pgvector | 0.7+ | IVFFlat index; upgrade to HNSW at >10k rows |
| Location Queries | PostGIS | 3.4+ | Proximity filtering on inventory |
| Migrations | Alembic | 1.13+ | All migrations reversible |
| Web Frontend | Next.js + TypeScript | 14+ | SSR; SSE for streaming responses |
| Mobile | React Native / Expo | SDK 51+ | Shared components with web where possible |
| Auth | Supabase Auth | Latest | JWT verification middleware in FastAPI |
| Deployment | DigitalOcean App Platform | — | Staging + production environments |
| Observability | structlog + JSON | — | Structured events to stdout → DigitalOcean log sink |

---

*Tarp-Space ARCHITECTURE.md — Phase 1: Personal Agent Layer — v1.0 — Confidential — March 2026*
