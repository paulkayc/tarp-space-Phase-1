# Open WebUI Feature Analysis for Tarp-Space

## Scope
This document maps Open WebUI capabilities to the Tarp-Space Phase 1 and architecture goals, with focus on:
- **Personal Agent** (owner-facing conversational layer + memory)
- **Mandate Agent** (structured mandate, controlled autonomy, matching workflow)

## Tarp-Space Requirements Recap (from project docs)

### Personal Agent Requirements
- Structured conversational onboarding (extract first, ask gaps)
- Persistent memory across sessions
- Versioned preference/mandate updates with auditability
- Explainable responses and selective escalation
- Owner controls over autonomy and corrections

### Mandate Agent Requirements
- Schema-driven mandate object (constraints, preferences, negotiation ranges)
- Confirmation gate before activation
- Privacy-preserving downstream signaling
- Matching workflow + feedback loop
- High observability and traceability

## Open WebUI Features Most Relevant to Tarp-Space

### 1) Model Presets as Agent Containers (High Fit)
Open WebUI "Models" act as wrappers/presets around base LLMs, allowing attachment of:
- system prompts
- tools
- knowledge bases
- skills
- default feature toggles

**Tarp-Space use:**
- Build **Personal Agent** as one model preset (onboarding + memory behavior)
- Build **Mandate Agent** as another preset (strict schema behavior, constrained tool use)
- Swap/compare multiple model backends while keeping behavior wrappers consistent

### 2) Native Tool Calling / Agentic Mode (High Fit)
Open WebUI’s native function-calling mode enables autonomous multi-step tool use.

**Tarp-Space use:**
- Personal Agent can call memory/notes/knowledge tools to gather history before asking questions
- Mandate Agent can call only specific scoped tools (e.g., read mandate snapshot, write structured update proposal, trigger search)
- Better for orchestration than prompt-only tool emulation

### 3) Built-in Memory System (Very High Fit for Personal Agent)
Open WebUI includes account-scoped memory primitives:
- `add_memory`
- `search_memories`
- `replace_memory_content`

**Tarp-Space use:**
- Persist durable owner preferences (style, flexibility traits, recurring constraints)
- Convert repeated acceptance/rejection patterns into long-term preference snippets
- Retrieve prior behavior to reduce repeated elicitation questions

**Important:** memory is snippet-based, not a strict typed mandate schema. You still need a dedicated mandate data model in your backend.

### 4) Knowledge Bases + File Search (High Fit for Mandate Context)
Knowledge can be attached per model and accessed with tool calls:
- `query_knowledge_bases`
- `search_knowledge_bases`
- `search_knowledge_files`
- `view_knowledge_file`

**Tarp-Space use:**
- Attach vertical/domain playbooks (furniture norms, service checklists, negotiation templates)
- Attach policy docs to keep mandate interpretation consistent
- Separate global organizational knowledge from owner-private memory

### 5) Skills (High Fit for Behavioral Control)
Skills are markdown instruction sets with lazy loading via `view_skill`.

**Tarp-Space use:**
- Create reusable "Mandate Elicitation Skill" enforcing one-question-per-turn
- Create "Escalation Discipline Skill" enforcing binary, contextual escalation prompts
- Create "Privacy Guardrail Skill" describing what must never be disclosed in replies

**Benefit:** behavior composition becomes modular; you can iterate instructions without editing code-heavy tool implementations.

### 6) Notes Workspace + Note Tools (Medium-High Fit)
Notes can be searched/read/written by models:
- `search_notes`, `view_note`, `write_note`, `replace_note_content`

**Tarp-Space use:**
- Store negotiation logs and human-readable mandate summaries
- Keep owner-facing “working memory” artifacts
- Maintain curated escalation rationale history

### 7) Functions (Pipe / Filter / Action) (Very High Fit)
Functions are Python plugins:
- **Pipe**: expose custom agent/model workflows
- **Filter**: transform inbound/outbound content
- **Action**: add UI button-triggered operations

**Tarp-Space use:**
- Pipe for deterministic “Mandate Build Pipeline” (extract → validate → score)
- Filter for schema validation and unsafe-output blocking
- Action buttons for owner confirmations (“Approve mandate”, “Reject inferred field”, “Escalate now”)

### 8) External Tool Integrations via OpenAPI/MCP (Very High Fit)
Open WebUI can connect external servers/tools via OpenAPI and MCP.

**Tarp-Space use:**
- Keep critical business logic outside LLM UI layer:
  - mandate schema service
  - privacy gate service
  - matching/ranking service
  - trust/reputation service
- Let agents call these services as tools, while preserving strong backend control

### 9) RBAC, Groups, ACLs (High Fit for Multi-Agent Safety)
Open WebUI supports roles, permissions, groups, and resource ACLs with additive policy model.

**Tarp-Space use:**
- Restrict who can manage tools/functions/skills
- Isolate private knowledge/memory resources between users and cohorts
- Gate experimental mandate policies to specific internal groups

### 10) Channels (Medium Fit for Introduction/Handoff)
Channels provide shared, persistent multi-user/multi-model timelines.

**Tarp-Space use:**
- Post-negotiation handoff room where buyer/seller + selected models collaborate with context
- Keep audit trail of “agent alignment → human introduction” events

## Feature Mapping: Personal Agent vs Mandate Agent

| Capability | Personal Agent | Mandate Agent | Open WebUI Feature |
|---|---|---|---|
| Conversational elicitation | Core | Supports | Model preset + Skills + Tools |
| Long-term owner memory | Core | Secondary | Memory tools |
| Structured mandate storage | Secondary view | Core | External backend via OpenAPI/MCP tool |
| Gap detection flow | Core | Core | Pipe function + validation filter |
| Confirmation checkpoints | Core | Core | Action functions + custom tool calls |
| Privacy-safe downstream signaling | Secondary | Core | External privacy-gate tool + filter safeguards |
| Matching/ranking execution | Observer | Core | External matching tool service |
| Explainable outputs | Core | Core | Prompt/skill + notes artifacts |
| Escalation management | Core | Core | Action functions + policy skill |
| Access controls | Core ops requirement | Core ops requirement | RBAC + Groups + ACL |

## Recommended Implementation Pattern in Tarp-Space

### A. What to adopt directly from Open WebUI
1. **Agent shell and UI orchestration**
   - model presets for Personal Agent and Mandate Agent
   - chat UX, tool routing, and multi-model switching
2. **Memory and Knowledge primitives**
   - user memory snippets for personalization
   - knowledge collections for vertical/domain context
3. **Extensibility layer**
   - tools/functions for deterministic hooks and UI actions
4. **Security baseline**
   - RBAC + group-scoped resource sharing

### B. What must remain custom in Tarp-Space backend
1. **Mandate schema system of record**
2. **Completeness scoring and versioning logic**
3. **Privacy gate deterministic enforcement**
4. **Matching engine and escalation threshold logic**
5. **Negotiation state machine and mutual exclusivity controls**

## Key Gaps / Risks If Using Open WebUI Naively

1. **Memory ≠ typed mandate store**
   - Open WebUI memory is useful but insufficient for strict transactional negotiation mandates.
2. **Tool/plugin security risk**
   - Functions/tools run Python on host; strong admin controls are mandatory.
3. **Native function-calling model quality dependency**
   - Poor models can fail tool protocol and produce unreliable orchestration.
4. **Need strict backend policy enforcement**
   - Prompting alone cannot guarantee mandate privacy constraints.

## Practical Build Blueprint (Phase 1-Aligned)

1. **Create two model presets**
   - `personal-agent-v1`
   - `mandate-agent-v1`
2. **Attach skills**
   - elicitation policy
   - escalation policy
   - explanation policy
3. **Expose backend microservices as tools**
   - `create_or_update_mandate`
   - `score_mandate_completeness`
   - `privacy_gate_transform`
   - `search_seeded_inventory`
   - `submit_signal`
4. **Use memory tools only for non-authoritative user personalization**
5. **Use action buttons for explicit owner confirmations**
6. **Use RBAC/groups for strict environment separation (dev/test/prod cohorts)**

## Bottom Line
Open WebUI is a **strong orchestration and agent UX layer** for Tarp-Space, especially for the **Personal Agent** and the interaction shell of the **Mandate Agent**. 

However, Tarp-Space’s core differentiators—typed mandate state, privacy gate guarantees, deterministic matching, and negotiation state control—should remain in custom backend services that Open WebUI calls through tools.

In short:
- **Use Open WebUI as the agent operating surface.**
- **Keep mandate truth, privacy, and matching logic in Tarp-Space core services.**

## Embedded-Only Option (No Separate Open WebUI App)

If Tarp-Space does not want to run Open WebUI as a separate app, the recommended approach is to **extract only minimal subsystems** and embed them directly:
- chat orchestration loop
- tool registry + dispatcher
- memory snippet service
- skills/pipeline abstractions (pipe/filter/action behavior)
- minimal ACL controls for agent configuration

Do **not** embed full Open WebUI product surfaces. Keep only agent runtime primitives, then connect them to Tarp-Space’s authoritative mandate/privacy/matching services.
