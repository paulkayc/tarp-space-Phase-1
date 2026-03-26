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

---

## 11) Non-goals (to prevent scope creep)
- Building full Open WebUI product inside Tarp-Space
- Channels/community features
- Full plugin marketplace
- Generic multi-workspace admin parity
- Agent-to-agent network protocol (Phase 2 concern)
