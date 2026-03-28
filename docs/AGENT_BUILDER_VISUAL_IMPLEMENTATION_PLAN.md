# Tarp-Space Visual Agent Builder — Brainstorm + Implementation Plan

## 1) Product Goal
Build a **visual Agent Builder** for Tarp-Space that lets developers and operator teams:
- design agent workflows on a canvas (nodes + edges),
- configure agent behavior (instructions, model, tools, guardrails, state),
- validate flows before publishing,
- auto-generate backend/frontend config + runtime wiring files,
- import generated agents directly into an existing Tarp-Space project.

The builder should feel similar to OpenAI’s agent builder UX while remaining native to Tarp-Space architecture and constraints.

---

## 2) Design Principles (Tarp-Space aligned)
1. **Architecture-native generation**
   - Generated artifacts must map cleanly to existing Tarp-Space runtime modules (`agents/personal_agent`, service layers, API routes).
2. **Hard safety before model calls**
   - Guardrails and privacy gate checks are deterministic runtime steps, not prompt-only instructions.
3. **Schema-first, typed contracts**
   - Node inputs/outputs, tool schemas, and edge conditions are validated with Pydantic/JSON Schema.
4. **Portable + Git-friendly**
   - Builder output is deterministic files in repo, easy to diff/review/rollback.
5. **Two-way lifecycle**
   - Create in visual builder → export files.
   - Also import existing files/manifests back into visual builder.

---

## 3) What Users Should Be Able To Build

### Core Node Types
- **Start / End**
- **Agent Call** (instructions + model + reasoning + tool policy)
- **Classifier** (route by class label/confidence)
- **If/Else Condition** (expression over state/output)
- **Tool Call** (single tool, deterministic)
- **Guardrail** (input/output moderation, policy checks)
- **Transform** (map output -> normalized state)
- **Set State** (write state key/value)
- **User Approval** (human-in-the-loop gate)
- **Loop/Retry** (bounded retries with stop conditions)

### Configurable Components
- **Tools**: local functions, HTTP tools, MCP tools (with schema and auth metadata)
- **Guardrails**: safety policy packs, PII filters, jailbreak resistance checks, output schema enforcers
- **Memory options**: none/session/long-term summaries
- **Observability hooks**: event names, span labels, redaction rules

---

## 4) Proposed System Architecture

## 4.1 Builder Frontend (Next.js)
- Canvas editor (React Flow or similar)
- Left palette: core nodes, tool nodes, logic nodes, data nodes
- Right inspector: properties panel for selected node
- Validation panel: graph errors/warnings
- Diff panel: generated artifacts preview
- Test panel: run simulation with sample input

## 4.2 Builder Backend (FastAPI)
- Graph CRUD APIs (draft/version/published)
- Validation API (static checks + schema checks)
- Codegen API (graph -> files)
- Import API (existing files -> graph)
- Run Simulation API (test execute with mocked tools or sandbox mode)

## 4.3 Runtime Contract Layer (new shared package)
A canonical “agent graph spec” package used by builder and runtime:
- `AgentGraphSpec` (versioned schema)
- Node/Edge definitions
- Tool/guardrail references
- Validation + migration helpers

This becomes the source of truth preventing drift between visual config and runtime behavior.

---

## 5) Canonical File Generation Strategy

Generated output per agent (example):

```text
backend/app/agents/generated/<agent_slug>/
  agent.manifest.json
  workflow.graph.json
  tools.registry.json
  guardrails.policy.json
  prompts/
    system.md
    classifier.md
  runtime_adapter.py
  tests/
    test_workflow_happy_path.py
    test_guardrails.py
frontend/src/agents/generated/<agent_slug>/
  metadata.json
```

### Why split this way
- **manifest**: high-level entrypoint metadata
- **graph**: canonical visual flow
- **registry/policy**: explicit contracts for tools and guardrails
- **runtime adapter**: thin typed wiring into existing execution engine
- **tests**: generated baseline tests to reduce regression risk

---

## 6) Graph Validation Rules (MVP)
1. Exactly one `Start` and at least one reachable `End`.
2. Every node (except End) has a valid outgoing edge.
3. No unbounded loops (loop nodes require max iterations).
4. All `If/Else` nodes must define fallback path.
5. `Classifier` labels must map to explicit routes.
6. Tool calls require declared schema + timeout + failure policy.
7. Guardrail nodes are required:
   - at least one input-side check before first LLM node,
   - at least one output-side check before terminal response.
8. Privacy-sensitive tools require explicit redaction mapping.
9. Generated graph must be topologically executable with runtime state typing.

---

## 7) Data Model Draft (Builder)

### Tables / Models
- `agent_builder_projects`
- `agent_builder_graph_versions`
- `agent_builder_runs` (simulation and test runs)
- `agent_builder_publish_events`
- `agent_builder_import_events`

### Key fields
- `status`: draft | validated | published | archived
- `schema_version`
- `runtime_target_version`
- `generated_artifact_hash`
- `created_by`, `updated_by`

---

## 8) End-to-End User Flow
1. User creates new agent project in builder.
2. User drags nodes, connects edges, configures tools/guardrails.
3. Builder runs live validation and highlights issues.
4. User runs simulation with sample input and inspects traces.
5. User clicks “Generate” -> backend produces deterministic files.
6. User reviews artifact diff.
7. User clicks “Publish/Import into project”.
8. Runtime adapter auto-registers agent in Tarp-Space agent registry.

---

## 9) Phased Implementation Plan

## Phase 0 — Discovery + Contracts (1–2 weeks)
- Confirm exact runtime adapter points in `backend/app/agents/personal_agent`.
- Finalize `AgentGraphSpec v1` JSON schema.
- Define codegen template conventions + naming.
- Write ADR: “Visual Builder Contract as Source of Truth”.

Deliverables:
- `docs/ADR_xxxx_visual_builder_contract.md`
- `docs/AGENT_GRAPH_SPEC_V1.md`

## Phase 1 — Builder MVP Editor + Save/Load (2–3 weeks)
- Canvas UI with Start/End/Agent/If/Else/Tool nodes.
- Property inspector and graph persistence.
- Draft versioning + API.

Deliverables:
- Builder route in frontend
- CRUD endpoints for graph draft/version

## Phase 2 — Validation Engine + Simulation (2–3 weeks)
- Static graph validator and schema validator.
- Simulation runner with mock tool mode.
- Trace viewer (node-by-node execution log).

Deliverables:
- `/validate` and `/simulate` APIs
- UI validation + trace panels

## Phase 3 — Code Generation + Import (2–3 weeks)
- Deterministic file generator from `AgentGraphSpec`.
- Artifact preview and diff.
- Import into runtime registry and hot-reload endpoint.

Deliverables:
- `/generate` + `/import` APIs
- Generated adapter + manifest + tests

## Phase 4 — Guardrails + Tooling Packs (2 weeks)
- Guardrail node library (moderation, schema, pii redaction).
- Tool templates (HTTP, DB safe query wrapper, MCP).
- Policy composition UI.

Deliverables:
- guardrail policy files
- reusable tool templates

## Phase 5 — Production Hardening (2 weeks)
- RBAC for who can publish/import.
- Audit logs for graph changes and publish actions.
- Snapshot rollback and compatibility migrations.
- CI checks for generated artifacts.

Deliverables:
- audit trail + rollback endpoints
- CI job validating generated agents

---

## 10) Suggested API Surface (Draft)
- `POST /api/v1/agent-builder/projects`
- `GET /api/v1/agent-builder/projects/{id}`
- `POST /api/v1/agent-builder/projects/{id}/versions`
- `POST /api/v1/agent-builder/versions/{id}/validate`
- `POST /api/v1/agent-builder/versions/{id}/simulate`
- `POST /api/v1/agent-builder/versions/{id}/generate`
- `POST /api/v1/agent-builder/versions/{id}/import`
- `POST /api/v1/agent-builder/versions/{id}/publish`
- `GET  /api/v1/agent-builder/runs/{run_id}`

---

## 11) Frontend IA / UX Blueprint
- **Left rail**: nodes (Core, Tools, Logic, Data, Guardrails)
- **Center canvas**: zoom/pan, snap lines, minimap
- **Top bar**: validate, simulate, generate, publish
- **Right panel**: node inspector + tool/guardrail config
- **Bottom drawer**: execution traces, generation diff, lint results

Minimum UX safeguards:
- Show red “blocking errors” vs yellow “warnings”.
- Inline fix suggestions (e.g., “Add output guardrail before End”).
- “Generate disabled” until zero blocking errors.

---

## 12) Technical Risks + Mitigations
1. **Spec/runtime drift**
   - Mitigation: single shared schema package + schema version migration scripts.
2. **Unsafe generated code**
   - Mitigation: generate declarative configs + thin adapters only, no arbitrary user code.
3. **Tool execution security**
   - Mitigation: strict allowlist, secrets vault refs only, timeout + rate limits.
4. **Complexity explosion in canvas**
   - Mitigation: node templates, subflows, and progressive advanced mode.
5. **Import conflicts with existing agents**
   - Mitigation: slug namespace + explicit conflict resolution UI.

---

## 13) Success Metrics
- Time to create first working agent < 15 minutes.
- >80% of generated agents run without manual file edits.
- Publish rollback < 2 minutes.
- 100% publish events have auditable graph + artifact hash.
- Reduction in handcrafted agent boilerplate by >60%.

---

## 14) Immediate Next Steps (This Week)
1. Approve `AgentGraphSpec` scope and node taxonomy.
2. Build low-fidelity UI wireframes for canvas + inspector + trace.
3. Implement backend draft graph CRUD with version table.
4. Implement first validator pass (start/end/connectivity/loop bounds).
5. Generate first sample agent package from a hardcoded graph.

---

## 15) Example MVP Template Agent to Ship First
Create a `commerce-query-router` template that mirrors your reference image pattern:
- Input guardrail
- Domain classifier
- If/Else branch by domain
- Specialized agent nodes per domain
- Output guardrail
- End

This template proves routing, tools, guardrails, simulation, and codegen in one end-to-end path.
