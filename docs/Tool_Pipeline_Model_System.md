# Tool/Pipeline Model System for Tarpspace

## 1. Overview

The Tool/Pipeline Model is a lightweight agent runtime architecture for Tarpspace's Personal Agent. It introduces a structured way to let the system:

- expose capabilities as tools,
- process each message through repeatable runtime stages,
- apply behavioral rules consistently,
- log what happened during a turn, and
- evolve cleanly as the product grows.

This model is especially important for Tarpspace because Tarpspace is not just a chat UI. It is moving toward a persistent personal agent that:

- remembers user preferences,
- retrieves and updates memory over time,
- applies conversation policy,
- keeps the interaction understandable and inspectable.

Without this model, the runtime tends to become one large file with mixed concerns. With this model, Tarpspace gets the first real foundation for agent-grade orchestration.

---

## 2. What the Tool/Pipeline Model Actually Is

At a high level, the model separates the Personal Agent runtime into three layers:

### A. Tools
Tools are named capabilities the runtime can invoke.

Examples:
- `memory_add`
- `memory_search`
- `memory_update`

A tool is not the whole agent. It is one operation the agent can perform.

### B. Pipeline
The pipeline defines the order and structure of how each user turn is processed.

Examples of pipeline stages:
- retrieve context
- generate draft response
- enforce policy
- log actions
- return final result

### C. Runtime integration
The runtime is the orchestrator. It ties tools and pipeline primitives into the actual per-message execution flow.

---

## 3. Why This Exists

As Tarpspace grows, the Personal Agent must do more than answer messages. It must:

- remember important user facts,
- recall them correctly,
- update them when newer truth appears,
- ask controlled follow-up questions,
- behave consistently across sessions,
- remain debuggable.

A hardcoded runtime can work early on, but over time it creates problems:

- logic gets mixed together,
- policy checks become inconsistent,
- adding new features becomes harder,
- testing becomes brittle,
- debugging becomes difficult.

The Tool/Pipeline Model solves that by introducing structure before the runtime becomes unmanageable.

---

## 4. Detailed Breakdown of the Tooling Layer

The tooling layer includes:

- `tools/registry.py`
- `tools/executor.py`
- `tools/builtin.py`

### 4.1 Tool Registry

The registry is the central catalog of tools available to the Personal Agent.

Its job is to:
- register tools by name,
- store metadata such as descriptions,
- allow lookup by tool name,
- allow the runtime to inspect available tools.

#### Mental picture
Think of the registry as a toolbox inventory.

Instead of the runtime remembering every capability manually, it can ask:
- What tools do I have?
- What is the tool called?
- What does it do?

#### Example

A registry may contain entries like:

- `memory_add`: store a new memory snippet
- `memory_search`: search relevant prior memory
- `memory_update`: correct or replace an existing memory

#### Why it matters
Without a registry, tool logic usually becomes a pile of conditionals inside the runtime. For example:

- if the action is memory search, do this
- else if the action is memory add, do that
- else if the action is memory update, do something else

That approach gets messy quickly. The registry makes the capability layer explicit and expandable.

### 4.2 Tool Executor

The executor is responsible for actually running a tool.

Its job is to:
- accept a tool name,
- accept arguments,
- look up the tool in the registry,
- execute it,
- return a standardized result.

#### Why the executor matters
It centralizes execution behavior so the runtime does not directly call tool functions in scattered ways.

That gives Tarpspace a clean place to later add:
- better validation,
- tracing,
- retries,
- permissions,
- timeouts,
- standardized errors.

#### Example

Instead of the runtime doing this directly:

- call memory service search function
- call memory add function

it can do this conceptually:

- execute `memory_search` with `owner_id` and `query`
- execute `memory_add` with a snippet and metadata

That shift looks small, but architecturally it is important.

### 4.3 Builtin Tools

Builtins are the default tools included with the Personal Agent.

In this phase, the builtins are memory-oriented:

#### `memory_add`
Stores a memory snippet.

Example use:
User says: "I only want remote fintech jobs in Canada."

The agent can store a memory like:
- remote preference
- fintech domain preference
- Canada location preference

#### `memory_search`
Searches prior memory for relevant context.

Example use:
Later the user asks: "What kinds of opportunities should I send you?"

The runtime can search memory and retrieve the stored preferences.

#### `memory_update`
Updates an existing memory when the user corrects or changes it.

Example use:
Old memory says: "prefers Houston roles"
New user message says: "I am relocating to Toronto next month"

The runtime can update or replace the relevant memory rather than duplicating conflicting facts.

---

## 5. Detailed Breakdown of the Pipeline Layer

The pipeline layer includes:

- `pipeline/pipe.py`
- `pipeline/filter.py`
- `pipeline/action.py`

This layer defines how a message turn moves through runtime stages.

### 5.1 Pipe: Composition of steps

The `Pipeline` primitive lets the runtime compose processing stages in a defined order.

Instead of one giant function doing everything inline, the runtime can use a staged flow.

Examples of stages:
- collect inputs
- search memory
- build prompt context
- call model
- filter output
- log actions
- return response

#### Why this matters
Pipelines make the system easier to:
- reason about,
- extend,
- test,
- debug.

As Tarpspace grows, new steps can be inserted without rewriting the whole runtime.

Examples of future steps Tarpspace may add:
- mandate extraction,
- confidence scoring,
- freshness ranking,
- trust prioritization,
- moderation,
- caching,
- analytics hooks.

### 5.2 Filter: Policy enforcement

The filter layer applies behavioral guards.

In this phase, one major filter was introduced:
- `enforce_one_question`

#### What it does
It ensures the Personal Agent asks at most one question per turn.

#### Why that matters for Tarpspace
Tarpspace appears to rely on structured elicitation and progressive profile collection. If the system asks many questions at once, the user experience becomes noisy and extraction quality drops.

Examples of problems without this filter:
- user gets overwhelmed,
- multiple details arrive at once in inconsistent form,
- follow-up logic becomes harder,
- memory updates become less clean.

#### Example
Without the filter:

"What role are you targeting, what is your budget, where are you located, and how soon do you want to move?"

With the filter:

"What role are you targeting?"

This makes the conversation more controlled and predictable.

### 5.3 Action: Runtime side-effect logging

The action hook in this phase includes:
- `append_action_log`

#### What it does
It records what happened during the turn.

Examples of actions that may be logged:
- memory searched
- memory added
- memory updated
- filter applied
- final response produced

#### Why action logging matters
Action logs make the system inspectable.

That helps Tarpspace with:
- debugging,
- auditing memory behavior,
- understanding why an answer looked a certain way,
- building future tracing or agent-observability tools.

Without logging, the runtime becomes much more of a black box.

---

## 6. Runtime Integration: How It All Works Together

The runtime integration ties tools and pipeline primitives into the per-message flow.

The updated runtime now does the following:

- initializes the tool registry,
- registers builtin memory tools,
- uses `ToolExecutor` for memory search/add operations,
- applies `enforce_one_question`,
- invokes a pipeline action step per processed turn,
- exposes `list_tools` for inspection.

That means the Personal Agent no longer handles everything as raw inline logic. It now processes each turn through a more structured runtime path.

---

## 7. Simple Mental Model

A simple way to think about this model:

### Before
One smart employee does everything in their head.

They:
- remember things,
- decide what to do,
- perform the work,
- check their own output,
- keep notes if they remember to.

This is fast at first, but messy over time.

### After
Now the system has:

- a **tool shelf**: the registry
- a **worker using the tools**: the executor
- a **checklist**: the pipeline
- a **quality rule**: the filter
- a **work log**: the action hook

This is not just a chat flow anymore. It is an operational system.

---

## 8. Step-by-Step Message Lifecycle for Tarpspace

Below is a simple message lifecycle showing how a user message moves through the architecture.

### Step 1: User sends a message
Example:
"I want remote contract React roles in fintech, preferably in Canada."

### Step 2: Frontend sends request to backend runtime
The Personal Agent API receives the session ID, owner ID, and user message.

### Step 3: Runtime initializes turn context
The runtime creates the turn context, attaches session metadata, and prepares to process the message.

### Step 4: Runtime uses `ToolExecutor` to search memory
The runtime executes something conceptually like:
- `memory_search(owner_id, query)`

The executor:
- looks up the tool in the registry,
- runs it,
- returns retrieved snippets.

Possible retrieved snippets:
- user prefers remote work
- user likes fintech opportunities
- user prefers Canada-based options

### Step 5: Runtime determines whether new memory should be added or updated
From the new user input, the runtime may identify fresh preference signals.

Examples:
- contract preference
- React preference

It may call:
- `memory_add(...)`
or
- `memory_update(...)`

through the executor.

### Step 6: Runtime builds model input
The runtime combines:
- current user message,
- retrieved memory,
- system instructions,
- session context,
- response policy constraints.

This becomes the model input or prompt context.

### Step 7: Runtime generates a draft response
The model or response generation logic produces a draft answer.

Example draft:
"Got it. I will prioritize remote contract React roles in fintech for Canada. Do you also want full-time options, and what salary range are you targeting?"

### Step 8: Filter applies one-question policy
The `enforce_one_question` filter checks the draft.

The draft contains two questions:
- Do you also want full-time options?
- What salary range are you targeting?

The filter reduces this to one question.

Possible final version:
"Got it. I will prioritize remote contract React roles in fintech for Canada. What salary range are you targeting?"

### Step 9: Action log is appended
The runtime records actions such as:
- memory searched
- memory added
- one-question filter applied
- response finalized

### Step 10: Runtime stores response + metadata
The assistant message, action trace, and related metadata are saved.

### Step 11: Backend returns response to frontend
The frontend receives the final message payload.

### Step 12: User sees the response
The user sees a grounded, policy-compliant, memory-aware response.

---

## 9. Example: With vs Without This Model

### Scenario
User says:
"I prefer remote data roles in healthcare and I do not want startup companies."

### Without the model
A direct runtime may:
- search memory inline,
- write memory inline,
- generate response inline,
- sometimes apply policy,
- sometimes forget to log,
- mix business logic with response logic.

Likely outcome:
- harder to debug,
- harder to enforce policy consistently,
- harder to add more capabilities later.

### With the model
The runtime can:
- search memory through the executor,
- add/update preference memory through tools,
- run response through filters,
- log what happened,
- keep the lifecycle structured.

Likely outcome:
- more consistent behavior,
- easier debugging,
- easier future extension,
- better foundation for agent evolution.

---

## 10. Benefits for Tarpspace

### 10.1 Modularity
New capabilities can be added as tools without rewriting the whole runtime.

Examples:
- `profile_extract`
- `job_match_search`
- `dealbreaker_add`
- `email_draft`
- `calendar_lookup`

### 10.2 Better policy control
Filters provide named, reusable rules rather than scattered inline checks.

### 10.3 Easier testing
You can test:
- tool registration,
- tool execution,
- filters,
- action logs,
- pipeline behavior.

### 10.4 Better observability
Action logs make the agent easier to audit and debug.

### 10.5 Better future tool-calling support
If Tarpspace later allows the model to choose tools dynamically, this structure is already a strong base.

### 10.6 Clearer separation of concerns
- tools = capability
- pipeline = execution flow
- filters = policy
- action hooks = observability
- runtime = orchestration

That separation is a major improvement.

---

## 11. Limitations of the Current Minimal Version

This phase is a foundation, not a full agent platform.

What is still likely missing:
- strict tool schema validation,
- typed tool outputs,
- ACL and permission checks for tools,
- timeout and retry behavior,
- branching pipelines,
- priority rules between memory vs fresh input vs mandate truth,
- memory confidence and freshness ranking,
- richer event tracing,
- dynamic model-driven tool planning.

So the right way to describe this phase is:

It does not make Tarpspace fully agentic.
It makes Tarpspace structurally ready for agentic evolution.

---

## 12. Recommendations

### Recommendation 1: Add explicit tool schemas
Every tool should define:
- name,
- description,
- input schema,
- output schema,
- failure modes.

This will make tool execution safer and easier to expose to model-driven tool selection later.

### Recommendation 2: Add structured tool result envelopes
Standardize tool outputs into a predictable result shape.

Suggested fields:
- success
- data
- error_code
- error_message
- trace_id
- tool_name

This will simplify downstream runtime handling.

### Recommendation 3: Add trust ordering for context sources
Tarpspace should explicitly define a precedence model for conflicting information.

Suggested priority order:
1. fresh user message
2. explicit mandate / verified truth
3. confirmed stored memory
4. inferred or derived memory

Without this, memory can become misleading.

### Recommendation 4: Expand filter library
In addition to one-question enforcement, add filters such as:
- no unsupported claims,
- no multi-intent overload,
- memory grounding requirement,
- concise-answer mode,
- safety/compliance filters.

### Recommendation 5: Add traceable event model
Move beyond simple action logging into structured event tracing.

Examples:
- turn_started
- memory_search_started
- memory_search_completed
- tool_called
- tool_failed
- filter_applied
- turn_completed

This will help monitoring and debugging significantly.

### Recommendation 6: Make pipeline stages explicit in runtime docs
Document the full order of operations so contributors understand exactly where logic belongs.

### Recommendation 7: Add test coverage around policy and tool use
Priority tests should include:
- one-question enforcement,
- memory use in answer generation,
- memory update on corrected user facts,
- fallback behavior on tool failure,
- action trace completeness.

### Recommendation 8: Prepare for LLM-directed tool calling carefully
If Tarpspace later allows the model to choose tools:
- keep the registry authoritative,
- require schema-based validation,
- enforce policy before and after tool execution,
- log every tool decision.

Do not jump straight into fully free-form autonomous tool use.

---

## 13. Future Implementations

### 13.1 Tool schema and validation layer
Add strict schema-driven tool definitions, ideally with typed arguments and return values.

### 13.2 Tool permissions and ACL
Some tools should only be callable in certain contexts or by certain roles.

Examples:
- read-only tools for normal user flow
- privileged config mutation tools for admins only

### 13.3 Memory ranking and freshness scoring
Search results should be ranked not only by relevance but also by:
- recency,
- confidence,
- source quality,
- whether the memory was explicitly confirmed.

### 13.4 Conflict resolution engine
If memory conflicts with current input, the system should decide whether to:
- replace,
- deprecate,
- merge,
- request clarification.

### 13.5 Pipeline branching
Not every message should follow the exact same path.

Future branching examples:
- simple recall question path,
- profile-elicitation path,
- mandate update path,
- task execution path.

### 13.6 Memory visibility layer in the UI
Let users inspect and correct what Tarpspace remembers.

This increases trust and improves data quality.

### 13.7 Explanation / trace panel
Show a compact explanation of what happened in a turn.

Example:
- searched memory
- found 3 relevant preferences
- updated 1 memory
- applied one-question rule

This could become a powerful debugging and trust feature.

### 13.8 More builtin tools
Future builtin tools might include:
- `profile_extract`
- `mandate_update`
- `job_match_search`
- `note_add`
- `summary_generate`
- `draft_reply`

### 13.9 Better orchestration state object
Introduce a formal turn-state object that tracks:
- retrieved memories,
- selected tools,
- filters applied,
- decisions made,
- output reasoning summary safe for logs.

### 13.10 Reliability features
Add:
- retries,
- circuit breakers,
- timeout handling,
- fallback strategies,
- partial-failure recovery.

---

## 14. Suggested Next Step for Tarpspace

The most practical next step is to formalize the turn lifecycle in code and documentation.

A strong next increment would be:
1. standardize tool schemas,
2. add richer event tracing,
3. define context trust priority,
4. expand policy filters,
5. add memory conflict resolution rules.

That would move Tarpspace from a minimal orchestration foundation to a far more reliable personal-agent runtime.

---

## 15. Final Summary

The Tool/Pipeline Model gives Tarpspace a structured runtime architecture for the Personal Agent.

It introduces:
- tools as named capabilities,
- an executor to run them consistently,
- pipeline primitives to structure turn flow,
- filters to enforce policy,
- action hooks to record what happened.

In practical terms, this changes Tarpspace from a chat flow with inline logic into the early form of an actual agent system.

That matters because Tarpspace needs:
- memory persistence,
- policy control,
- explainability,
- scalability of capabilities,
- future readiness for richer orchestration.

This phase is not the finish line, but it is the correct foundation for building a trustworthy and extensible personal agent.
