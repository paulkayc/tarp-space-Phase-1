# Tarp-Space Personal Agent — Minimal Embedded Open WebUI Extraction Plan

## 0) What changed from previous plan
You explicitly do **not** want Open WebUI as a separate app/service.

This plan therefore uses a **code-extraction approach**:
- Copy only the Open WebUI components required for Personal Agent behavior.
- Re-implement/adapt those components directly inside Tarp-Space backend/frontend.
- Keep Tarp-Space architecture authoritative for mandate, privacy gate, matching, and observability.

---

## 1) Target Outcome (Minimum Scope)
Build only what is required for the Tarp-Space Personal Agent to function in Phase 1:

1. Conversational mandate-building (extract-first, one-gap-question at a time)
2. Personal memory snippets across sessions (non-authoritative)
3. Tool-calling orchestration to invoke Tarp-Space mandate/search/signal services
4. Grounded explanation generation for results
5. Explicit confirmation/escalation actions
6. Basic role-based control for who can edit agent behavior

Everything else from Open WebUI is out of scope.

---

## 2) Minimal Feature Set to Extract from Open WebUI

### A. Keep (required)
1. **Chat orchestration primitives**
   - message loop
   - streaming response handling
   - tool-call execution bridge

2. **Tool registration + invocation model**
   - structured JSON tool schemas
   - deterministic tool dispatch

3. **Memory primitives**
   - add/search/update memory snippet APIs
   - user-scoped retrieval

4. **Knowledge retrieval primitives (optional but recommended)**
   - attach/search small policy files (negotiation guidelines, vertical playbooks)

5. **Skills/behavior templates**
   - reusable prompt modules for elicitation, escalation, grounding

6. **Function pipeline hooks (Pipe/Filter/Action concept)**
   - Pipe: run deterministic orchestration flow
   - Filter: enforce response schema/policy
   - Action: explicit UI actions (confirm, escalate)

7. **Basic ACL controls**
   - who can edit tools/functions/skills

### B. Drop (not needed for Phase 1)
- Channels / social collaboration
- Built-in image generation flows
- Realtime voice/video stack
- Full Open WebUI workspace UX parity
- Multi-tenant enterprise admin surfaces beyond minimal role gates
- Any generic marketplace features not tied to Personal Agent

---

## 2.1) Two-Agent Model (Clear Separation)

Tarp-Space should implement two cooperating agents with distinct responsibilities:

## A) Personal Agent (build first)
Primary job: **learn the user**, not the marketplace.

Responsibilities:
1. Onboarding conversation and persona elicitation
2. Long-term memory creation/update (preferences, constraints, communication style)
3. Memory summarization for context injection
4. User profile refinement over time from explicit corrections

Outputs:
- `persona_memory_profile`
- `preference_memory_snippets`
- `persona_confidence_score`

Success criteria:
- user feels understood,
- memory is accurate and editable,
- later interactions require fewer repeated questions.

## B) Mandate Agent (build second)
Primary job: **fulfill a specific user request** against marketplace supply.

Responsibilities:
1. Parse request into structured mandate intent
2. Fill mandate gaps needed for search execution
3. Trigger marketplace matching/search flow
4. Return ranked, explained results and escalation prompts

Outputs:
- `mandate_object` (authoritative in mandate service)
- `match_results`
- `refinement_signals`

Success criteria:
- high match relevance,
- clear explanations,
- controlled escalation behavior.

## C) Overlap between agents
Shared capabilities:
- conversation runtime
- tool-calling layer
- prompt builder
- response post-processing
- ACL and audit hooks

Critical boundary:
- Personal Agent owns **who the user is** (durable persona memory)
- Mandate Agent owns **what the user wants right now** (task-specific mandate)

---

## 2.2) Build Order (Personal Agent First, Testable in Isolation)

### Phase P1 — Personal Agent only (no mandate search)
Build and test:
1. Persona onboarding flow
2. Memory CRUD + retrieval
3. Contextual responses using persona memory only
4. Memory edit/override UX

Do **not** integrate marketplace search yet.

Exit tests:
- persona extraction accuracy benchmark
- memory retrieval relevance benchmark
- user correction round-trip test (edit memory and verify usage next turn)

### Phase P2 — Add Mandate Agent on top
After P1 passes, add:
1. Request-intent extraction to mandate schema
2. Mandate completeness loop
3. Privacy gate + matching integration
4. Result explanation + escalation controls

P2 depends on stable P1 memory/context primitives but does not merge authority boundaries.

---

## 2.3) Agent Interaction Flow (High-Level)

1. User talks to **Personal Agent** during onboarding and ongoing profile refinement.
2. When user submits a concrete marketplace request, Orchestrator invokes **Mandate Agent**.
3. Mandate Agent receives persona context from Personal Agent memory summary.
4. Mandate Agent executes request lifecycle (extract → search → explain → refine).
5. Post-outcome signals update:
   - mandate state (task-level) in mandate service,
   - optional durable persona memory (user-level) via Personal Agent memory policy.

---

## 3) Exact Open WebUI Modules to Extract/Port

> Goal: extract concepts and selected implementation patterns, not wholesale fork.

## 3.1 Backend modules (highest priority)

### 1) App wiring and request lifecycle
- `backend/open_webui/main.py`
- What to port:
  - router composition pattern
  - middleware ordering pattern
  - startup initialization pattern
- Tarp-Space destination:
  - `backend/app/main.py` (or equivalent FastAPI entrypoint)

### 2) Chat loop and completions
- `backend/open_webui/routers/chats.py`
- `backend/open_webui/utils/chat.py`
- What to port:
  - chat request model
  - model invocation loop
  - tool-call intercept/dispatch flow
  - streaming response behavior
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/runtime.py`
  - `backend/app/api/v1/personal_agent_chat.py`

### 3) Tooling system
- `backend/open_webui/routers/tools.py`
- `backend/open_webui/utils/tools.py`
- What to port:
  - tool schema registry
  - tool execution interfaces
  - tool call tracing hooks
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/tools/registry.py`
  - `backend/app/agents/personal_agent/tools/executor.py`

### 4) Function pipeline (Pipe/Filter/Action model)
- `backend/open_webui/routers/functions.py`
- What to port:
  - function type abstractions (pipe/filter/action)
  - execution order semantics
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/pipeline/*.py`

### 5) Memory subsystem
- `backend/open_webui/routers/memories.py`
- memory model module in `backend/open_webui/models/*memory*`
- What to port:
  - user-scoped memory CRUD
  - search semantics
  - update semantics
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/memory/service.py`
  - `backend/app/models/personal_memory.py`

### 6) Knowledge retrieval (small subset)
- `backend/open_webui/routers/knowledge.py`
- `backend/open_webui/routers/retrieval.py`
- What to port:
  - attach/search static policy files
  - retrieval helper flow
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/knowledge/service.py`

### 7) Skills abstraction
- `backend/open_webui/routers/skills.py`
- What to port:
  - skill manifest/loader pattern
  - targeted skill retrieval
- Tarp-Space destination:
  - `backend/app/agents/personal_agent/skills/*.md`
  - `backend/app/agents/personal_agent/skills/loader.py`

### 8) Minimal auth/access controls
- `backend/open_webui/utils/auth.py`
- `backend/open_webui/utils/access_control.py`
- `backend/open_webui/routers/groups.py`
- What to port:
  - role checks for behavior-edit endpoints
- Tarp-Space destination:
  - `backend/app/security/agent_admin_acl.py`

### 9) Minimal audit/log pattern
- `backend/open_webui/utils/audit.py`
- What to port:
  - structured logs around tool/function edits and execution
- Tarp-Space destination:
  - existing `activity_log` pipeline + agent-specific event wrappers

---

## 3.2 Frontend patterns to extract (minimal)

From Open WebUI frontend, extract only interaction concepts:
1. Chat surface with streaming tokens
2. Tool-call state rendering (thinking/acting/completed)
3. Explicit action buttons (confirm, escalate yes/no)
4. Memory panel (compact) for user-visible “what agent remembers”

Tarp-Space destination:
- `frontend` existing chat pages/components (add Personal Agent views only)
- no attempt to clone full Open WebUI UI shell

---

## 4) Embedded Architecture in Tarp-Space (No separate Open WebUI app)

```mermaid
flowchart LR
  U[User] --> FE[Tarp-Space Frontend\nPersonal Agent Chat]
  FE --> API[Tarp-Space FastAPI]

  API --> ORCH[Personal Agent Orchestrator\n(extracted Open WebUI patterns)]
  ORCH --> LLM[(LLM Provider)]

  ORCH --> MEM[Personal Memory Service]
  ORCH --> KNOW[Knowledge Retrieval Service]

  ORCH --> MANDATE[Mandate Service\n(authoritative)]
  ORCH --> PRIV[Privacy Gate\n(authoritative)]
  ORCH --> MATCH[Matching Engine\n(authoritative)]
  ORCH --> SIGNAL[Signal/Refinement Service]
  ORCH --> ACT[(Activity Log)]
```

### Key rule
Open WebUI-derived components only orchestrate. They do **not** become system-of-record for mandate state.

---

## 5) End-to-End Personal Agent Workflow (Embedded)

## Step 1: Session bootstrap
1. User opens Personal Agent chat in Tarp-Space UI.
2. Backend loads:
   - latest active/in-progress mandate (if exists)
   - relevant personal memories
   - relevant knowledge snippets

## Step 2: Extraction-first turn
3. User sends natural language need.
4. Orchestrator runs extraction prompt + skill constraints.
5. Structured delta is validated by filter.
6. Orchestrator calls internal mandate API `create_or_update_mandate`.

## Step 3: Gap loop
7. Mandate service returns completeness + highest-priority gaps.
8. If completeness < threshold, agent asks exactly one gap question.
9. Repeat until threshold met.

## Step 4: Explicit confirmation
10. Agent summarizes mandate.
11. UI requires explicit confirmation action.
12. On confirmation, mandate version is locked and activated.

## Step 5: Match + explain
13. Orchestrator requests search.
14. Backend applies privacy gate then matching.
15. Agent explains top results with grounded attributes only.
16. Escalation candidates get binary yes/no action.

## Step 6: Feedback/refinement
17. User accepts/rejects/escalation response.
18. Signal service applies refinement policy and increments mandate version.
19. Optional memory snippet update if policy allows.

## Step 7: Auditability
20. Every step emits structured events to `activity_log`.

---

## 6) Service Boundaries (What lives where)

## Personal Agent Orchestrator (new)
- LLM call management
- tool dispatch and sequencing
- skill/template assembly
- response filtering/validation

## Mandate Service (existing/authoritative)
- schema + versions + completeness
- explicit/inferred source flags

## Privacy Gate (existing/authoritative)
- deterministic sanitization rules

## Matching Service (existing/authoritative)
- hard filters + ranking + escalation thresholds

## Memory Service (new minimal)
- snippet CRUD/search
- user-scoped only
- non-authoritative label enforced

## Knowledge Service (new minimal)
- indexed policy/playbook retrieval
- small corpus for phase 1 only

---

## 7) Implementation Plan (Phased, minimal)

## Phase A — Extract and scaffold (Week 1)
- Create `personal_agent` package in backend.
- Port chat orchestration + tool registry abstractions.
- Add minimal DB tables for personal memory and skill references.

Deliverable:
- end-to-end hello-world chat with tool-call stub in Tarp-Space API.

## Phase B — Mandate loop integration (Weeks 2–3)
- Integrate orchestrator with mandate endpoints.
- Implement extraction filter and one-question-per-turn enforcement.
- Add confirmation action and mandate activation flow.

Deliverable:
- user can go raw request → confirmed mandate entirely inside Tarp-Space.

## Phase C — Search/explain/escalate (Weeks 3–4)
- Connect to privacy gate + matching service.
- Implement explanation grounding checks.
- Add escalation yes/no actions.

Deliverable:
- complete personal agent match loop operational.

## Phase D — Memory + knowledge (Weeks 4–5)
- Enable memory retrieval/write policy.
- Add vertical knowledge corpus retrieval.
- Ensure memory cannot overwrite mandate truth.

Deliverable:
- improved turn quality from prior-user context.

## Phase E — Hardening (Weeks 5–6)
- Add ACL for tool/function/skill edit endpoints.
- Add audit logging around all policy-sensitive actions.
- Add regression suite for extraction, grounding, and escalation.

Deliverable:
- production-safe Personal Agent core.

---

## 8) Minimal API/Tool Contracts Required

1. `create_or_update_mandate(owner_id, conversation_id, delta)`
2. `get_mandate(mandate_id)`
3. `confirm_mandate(mandate_id)`
4. `search_seeded_inventory(mandate_id, mandate_version)`
5. `submit_signal(owner_id, result_id, signal_type, reason?)`
6. `memory_add(owner_id, content, tags?)`
7. `memory_search(owner_id, query, k?)`

Contract rules:
- strict schema validation
- deterministic error responses
- idempotency key for mutating operations
- full structured event logging

---

## 9) Detailed TODO List (Only what is needed)

## Backend
- [ ] Create `personal_agent` orchestrator package
- [ ] Port tool registry and dispatcher abstractions
- [ ] Port filter pipeline abstraction
- [ ] Add memory table/model + CRUD/search service
- [ ] Add skill loader and versioned skill assets
- [ ] Add knowledge retrieval mini-service
- [ ] Wire orchestrator to mandate, privacy, matching, signal services
- [ ] Add ACL checks for agent-config mutation endpoints
- [ ] Add structured audit events for all tool calls

## Frontend
- [ ] Add Personal Agent chat route/page
- [ ] Add streaming answer renderer
- [ ] Add confirm mandate action button
- [ ] Add escalation yes/no action controls
- [ ] Add compact memory visibility panel

## Quality
- [ ] Unit tests: tool dispatch, filters, memory search
- [ ] Integration tests: message → mandate → confirm → search → signal
- [ ] Policy tests: one-question rule, grounded explanation rule
- [ ] Security tests: unauthorized config edits blocked

---

## 10) Acceptance Criteria (Phase 1 Personal Agent)
1. User can complete mandate onboarding in <= 4 turns for well-specified prompts.
2. Confirmation is explicit before any search call.
3. Matching only runs through privacy gate.
4. Explanations reference only known listing attributes.
5. Memory retrieval improves follow-up prompts but never overrides authoritative mandate fields.
6. All critical actions are auditable in structured logs.

### Additional acceptance criteria for two-agent rollout
7. Personal Agent can run independently with Mandate Agent disabled.
8. Mandate Agent consumes persona context but cannot overwrite persona memory directly.
9. Persona memory updates require Personal Agent policy gate (confidence + user confirmation rules).

---

## 11) Non-goals (to prevent scope creep)
- Building full Open WebUI product inside Tarp-Space
- Channels/community features
- Full plugin marketplace
- Generic multi-workspace admin parity
- Agent-to-agent network protocol (Phase 2 concern)

---

## 11.1) Knowledge Retrieval Mini-Service (Detailed Design)

This mini-service provides **small, high-signal contextual retrieval** for the Personal Agent (policy docs, vertical playbooks, negotiation heuristics), without becoming a general-purpose RAG platform.

### Purpose
The service answers one question:  
**“What supporting knowledge snippets should be added to this specific user turn?”**

It is intentionally scoped to:
- improve answer quality and consistency,
- reduce hallucinations,
- enforce policy grounding,
- keep latency predictable.

### What it stores
1. **Knowledge documents** (markdown/plain text/json)
   - Example types: furniture buying playbook, escalation policy, explanation style guide.
2. **Chunks** generated from documents
   - Sentence/paragraph blocks with overlap.
3. **Embeddings** for each chunk
   - Used for semantic retrieval.
4. **Metadata**
   - `domain`, `vertical`, `policy_type`, `version`, `status`, `owner_scope`, `created_at`.

### Data model (minimal)
- `knowledge_documents`
  - `id`, `title`, `source_type`, `vertical`, `version`, `status`, `tags`, `created_at`, `updated_at`
- `knowledge_chunks`
  - `id`, `document_id`, `chunk_text`, `chunk_index`, `token_count`, `embedding`, `metadata`
- `knowledge_access_rules`
  - `id`, `document_id`, `role`, `group_id`, `environment`, `can_read`

### Ingestion pipeline
1. **Document intake**
   - Admin uploads/updates a knowledge document.
2. **Normalization**
   - Strip unsupported markup, normalize whitespace, remove duplicate headings.
3. **Chunking**
   - Chunk by semantic boundaries (target ~300–600 tokens, overlap ~50–100 tokens).
4. **Embedding generation**
   - Generate vector per chunk using configured embedding model.
5. **Index write**
   - Store chunks + embeddings + metadata.
6. **Version activation**
   - New version marked `active`; previous version retained for audit/rollback.

### Retrieval request flow (per user message)
1. Orchestrator sends retrieval request:
   - `owner_id`, `conversation_id`, `vertical`, `intent_type`, `query_text`, `k`.
2. Service builds filter set:
   - active docs only,
   - matching `vertical` + allowed policy categories,
   - ACL/role/group constraints.
3. Semantic search against vector index:
   - cosine similarity over `knowledge_chunks.embedding`.
4. Re-rank and cap:
   - prioritize policy docs over generic tips when confidence is close.
5. Return top-k snippets with citations:
   - snippet text + document title + version + score.

### Ranking logic (simple + deterministic)
`final_score = semantic_similarity * 0.8 + policy_priority * 0.2`

Where:
- `semantic_similarity` = vector similarity score.
- `policy_priority` = deterministic boost for high-priority policy classes  
  (e.g., privacy/safety/escalation docs).

### Prompt integration contract
Returned snippets are inserted into Prompt Builder as a separate block:
- `SYSTEM_RULES`
- `MANDATE_STATE_SUMMARY`
- `MEMORY_SNIPPETS`
- `KNOWLEDGE_SNIPPETS`  ← from this service
- `RECENT_CONVERSATION`
- `USER_MESSAGE`

This separation ensures knowledge context is distinguishable during debugging/audits.

### Guardrails
1. **Never authoritative for mandate truth**
   - Knowledge retrieval can guide wording/strategy, but cannot mutate mandate state directly.
2. **ACL enforced before retrieval**
   - No cross-tenant or unauthorized policy leakage.
3. **Version pinning**
   - Retrieval responses include doc version for reproducibility.
4. **Token budget cap**
   - Hard cap on returned snippet tokens to protect latency/cost.
5. **Injection resistance**
   - Retrieved text is wrapped as quoted context and never executed as instructions directly.

### Caching strategy
- Cache key: `(vertical, intent_type, normalized_query_hash, role/group)` with short TTL.
- Benefits:
  - lowers repeated retrieval latency in multi-turn conversations,
  - reduces embedding/index load.
- Invalidate cache on document version changes.

### Failure behavior
If retrieval fails/timeouts:
1. Return empty snippet set.
2. Continue orchestration with memory + conversation context only.
3. Emit `knowledge_retrieval_failed` event with reason/latency.

No hard failure should block user response unless policy requires a specific document.

### API surface (minimal)
1. `POST /api/v1/knowledge/documents`
   - create/update document (admin only)
2. `POST /api/v1/knowledge/reindex/{document_id}`
   - re-chunk + re-embed + activate version
3. `POST /api/v1/knowledge/retrieve`
   - request snippets for a user turn
4. `GET /api/v1/knowledge/documents/{id}/versions`
   - audit/debug version history

### Observability events
- `knowledge_document_ingested`
- `knowledge_document_activated`
- `knowledge_retrieval_started`
- `knowledge_retrieval_completed` (with `k`, latency, score distribution)
- `knowledge_retrieval_failed`

### Performance targets (Phase 1)
- p95 retrieval latency: `< 150ms` on small corpus.
- snippet recall quality: top-3 judged relevant in >80% of eval prompts.
- zero unauthorized knowledge reads in ACL audit.

---

## 12) Detailed Sequence Diagram — Personal AI Agent Orchestrator (End-to-End)

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant FE as Frontend (Web/Mobile App)
  participant API as API Gateway / Backend Server
  participant AUTH as Authentication Service
  participant CONV as Conversation Service
  participant MEM as Memory Service
  participant VDB as Vector Database
  participant ORCH as Orchestrator / Agent Controller
  participant PB as Prompt Builder
  participant LLM as LLM Provider
  participant TOOL as Tool/Function Calling Layer
  participant POST as Response Post-Processor
  participant DB as Database

  User->>FE: Send chat message
  FE->>API: POST /personal-agent/message {message, session_id}
  API->>AUTH: Validate JWT/session
  AUTH-->>API: Auth result (owner_id, scopes)

  alt Auth invalid
    API-->>FE: 401/403 error response
    FE-->>User: Show auth error
  else Auth valid
    API->>DB: Log inbound message (raw + metadata)
    API->>CONV: Get or create conversation state
    CONV-->>API: conversation_id + recent history

    API->>MEM: Retrieve user memory/persona snippets
    MEM-->>API: Memory set (preferences, prior signals)
    Note over MEM,API: Memory is non-authoritative personalization context only.

    API->>VDB: Semantic search for relevant prior context
    VDB-->>API: Top-k contextual chunks
    Note over VDB,API: Vector recall augments context (past chats, policy docs, accepted patterns).

    API->>ORCH: Hand off request + history + memory + retrieved context
    ORCH->>ORCH: Decide plan\n- include/exclude context\n- whether tools are required\n- response strategy

    ORCH->>PB: Build prompt inputs (system + rules + memory + context + user message)
    PB-->>ORCH: Final prompt payload
    Note over PB,ORCH: Prompt composition enforces policy templates, tone, and one-question/gap logic.

    ORCH->>LLM: Chat completion request (prompt + tool schema)
    LLM-->>ORCH: Model output (direct answer OR tool call request)

    alt LLM requests tool/function call
      ORCH->>TOOL: Execute tool call(s) with validated args
      TOOL->>DB: Persist tool execution audit/event
      TOOL-->>ORCH: Tool result payload
      ORCH->>PB: Rebuild follow-up prompt with tool result
      PB-->>ORCH: Updated prompt
      ORCH->>LLM: Second completion with tool result context
      LLM-->>ORCH: Final model response
    else Direct response path
      ORCH->>ORCH: Continue without tool execution
    end

    ORCH->>POST: Apply post-processing\n(formatting + safety + tone alignment + policy checks)
    POST-->>ORCH: Final user-facing response

    ORCH->>DB: Store assistant response + metadata\n(prompt refs, context ids, tool ids, latency)
    ORCH-->>API: Final response envelope
    API-->>FE: 200 OK + response payload
    FE-->>User: Render assistant response
  end
```

### Engineering Notes
1. **Conversation state ownership:** `Conversation Service` is the state authority for chat/thread lifecycle; orchestrator is stateless between calls except for request-local planning.
2. **Memory + vector retrieval separation:** memory service returns durable user-level traits; vector DB returns query-specific semantic context.
3. **Tool branch behavior:** tool calls are only executed through validated schemas and must be audited before reuse in the second LLM pass.
4. **Post-processing gate:** final output passes through deterministic formatting/safety/tone policy before persistence and client return.

---

## 13) Detailed Implementation Breakdown by Agent

## 13.1 Personal Agent implementation (first milestone)

### Services/components
- `personal_agent_orchestrator`
- `memory_service`
- `knowledge_retrieval_service` (policy/playbook support)
- `persona_prompt_templates`

### Core endpoints
- `POST /api/v1/personal-agent/message`
- `GET /api/v1/personal-agent/memory`
- `PATCH /api/v1/personal-agent/memory/{memory_id}`

### Test plan (must pass before Mandate Agent starts)
1. Persona onboarding test corpus (profile extraction quality)
2. Memory retrieval relevance test
3. Memory edit consistency test
4. Latency and token budget test for memory-augmented prompting

## 13.2 Mandate Agent implementation (second milestone)

### Services/components
- `mandate_agent_orchestrator`
- `mandate_service` (existing authoritative)
- `privacy_gate` (existing authoritative)
- `matching_service` (existing authoritative)
- `signal_refinement_service` (existing authoritative)

### Core endpoints
- `POST /api/v1/mandate-agent/message`
- `POST /api/v1/mandates/{id}/confirm`
- `POST /api/v1/mandates/{id}/search`
- `POST /api/v1/mandates/{id}/signals`

### Test plan
1. Intent extraction to mandate schema test
2. Completeness loop behavior test
3. Privacy-gate-before-search enforcement test
4. Match explanation grounding test
5. Escalation flow correctness test

## 13.3 Overlap implementation (shared platform layer)

Build once and reuse for both agents:
- chat runtime + streaming
- tool registry/dispatcher
- prompt builder
- response post-processor
- ACL + audit logging

This gives fast delivery while preserving clean agent boundaries.

---

## 14) Practical rollout checklist (Personal first, then Mandate)

### Step 1 — Ship Personal Agent beta
- [ ] Deploy Personal Agent endpoints + UI
- [ ] Enable memory visibility/edit controls
- [ ] Run onboarding cohort and collect quality metrics

### Step 2 — Harden Personal Agent
- [ ] Improve memory ranking/chunking from observed usage
- [ ] Tune prompt budget and response quality
- [ ] Lock ACL/audit controls

### Step 3 — Introduce Mandate Agent
- [ ] Add request-to-mandate extraction flow
- [ ] Integrate privacy gate + matching
- [ ] Add result explanation + escalation

### Step 4 — Joint operation
- [ ] Pass persona summary from Personal Agent to Mandate Agent
- [ ] Keep mandate and persona updates separate with explicit policies
- [ ] Validate end-to-end two-agent quality metrics
