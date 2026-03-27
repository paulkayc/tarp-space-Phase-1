# ADR-0001: users.persona blob → personal_memories snippet model

- **Status:** Accepted
- **Date:** March 26, 2026
- **Decision owners:** Backend (Dev A), Frontend (Dev B)

## Context
The initial Personal Agent implementation stored inferred and explicit persona data in a single JSON blob (`users.persona`).

That approach is easy to bootstrap but weak for:
- auditability
- partial edits
- relevance-ranked retrieval
- long-lived preference history

Phase 2 introduced `personal_memories` and `personal_memory_events` as dedicated snippet storage.

## Decision
Adopt a dual-path migration from blob-only to snippet-first memory:

1. **Write path (current):**
   - keep writing `users.persona` for backward compatibility
   - also write inferred/explicit snippets into `personal_memories`
2. **Read path (current):**
   - memory-question flow prefers snippet search
   - fallback to `users.persona` reflection when snippets are empty
3. **Authoritative rule:**
   - `personal_memories` are non-authoritative personalization context
   - mandate system remains source of truth for mandate decisions

## Backfill Policy
Backfill old persona blobs into snippets in one idempotent batch job:

- Input: all users where `users.persona != {}`
- For each top-level key/value:
  - create snippet `"<key>: <value>"`
  - tags: `[key, "persona", "backfill"]`
  - source: `derived`
  - confidence: `0.6`
- Skip if equivalent active snippet already exists.

### Backfill Safety
- run in chunks (e.g., 500 users per batch)
- log counts for created/skipped/errors
- retry-safe using de-dup checks

## Dual-Read Cutoff Plan
- **Phase A (now):** dual-write + snippet-preferred read + blob fallback
- **Phase B:** after successful backfill and 2 release cycles, enable feature flag to disable blob fallback reads
- **Phase C:** keep blob writes disabled, retain blob column for rollback window
- **Phase D (future migration):** remove blob dependence from runtime, optionally retain column for legacy exports only

## Rollback Plan
If snippet retrieval fails in production:

1. Flip feature flag to re-enable blob-first read behavior.
2. Keep `personal_memories` writes enabled for data continuity.
3. Investigate index/query/runtime issue.
4. Replay missed snippet writes from event/audit logs where possible.

## Consequences
### Positive
- better retrieval granularity
- better memory editability
- event-level auditability
- cleaner path to vector/semantic ranking later

### Negative
- increased complexity during dual-path period
- temporary duplicate storage of persona information
- need migration runbooks and operational monitoring

## Operational Checklist (Local + Deploy)
1. Apply DB migrations (`make migrate` / `alembic upgrade head`).
2. Deploy backend with dual-path runtime enabled.
3. Run backfill script once environment is stable.
4. Verify snippet recall in Personal Agent conversation flows.
5. Track metrics before enabling blob fallback disable flag.
