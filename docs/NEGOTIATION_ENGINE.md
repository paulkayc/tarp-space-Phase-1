# Negotiation Engine — LLM-Driven Design

**Status:** Design / Phase 3
**Last updated:** 2026-03-30

---

## Overview

The Negotiation Engine manages agent-to-agent deal-making between a buyer and a seller after a retrieval match is returned. It uses LLM agents to generate natural language offers and counter-offers, with a state machine enforcing legal transitions and a privacy gate ensuring neither side leaks private constraints.

**Core principle:** LLM is the voice. State machine is the enforcer. Privacy gate is the boundary.

---

## The Fundamental Shift from Deterministic Protocol

| Old Design | New Design |
|---|---|
| User sends signals (accept / reject) | LLM agents exchange natural language messages |
| One signal per turn | Multi-round conversation between two agents |
| Deterministic protocol only | LLM proposes, state machine validates |
| User interacts via signal buttons | User reads chat thread and optionally intervenes |
| Single party (buyer only) | Two parties — buyer agent + seller agent |
| No visible conversation | Full conversation thread visible to both parties |

---

## The Thread as a Chat

The primary UX is a visible conversation between two AI agents, one per party. Users observe in real time and can intervene based on their autonomy setting.

```
[SYSTEM]:       Match found — Guitar listing vs. your instrument mandate.
                Alignment score: 62%. Starting negotiation.

[buyer_agent]:  Hi, I'm interested in the Gibson Les Paul you listed.
                I'm looking for something in excellent condition for home
                studio use. Would you consider $1,100?

[seller_agent]: Thanks for reaching out! The guitar is in excellent condition
                with original case. I was thinking closer to $1,400.
                Could you go up to $1,350?

[buyer_agent]:  I appreciate the condition. I can move to $1,200,
                but that would be my upper end given the market.

[seller_agent]: Let me check... I can meet you at $1,275.

[buyer_agent]:  $1,250 and we have a deal.

[seller_agent]: Agreed at $1,250.

[SYSTEM]:       Terms agreed. Alignment score: 94%.
                Awaiting your confirmation to proceed.

[buyer_human]:  ✓ Confirmed
```

---

## Dual-Agent Architecture

Each negotiation thread has two LLM agents operating in **separate, isolated context windows**.

```
┌─────────────────────────────────────────────────────────┐
│                  NEGOTIATION THREAD                     │
│                                                         │
│  ┌──────────────────┐        ┌──────────────────┐      │
│  │   BUYER AGENT    │        │   SELLER AGENT   │      │
│  │                  │        │                  │      │
│  │ Context:         │        │ Context:         │      │
│  │ - Mandate        │        │ - Inventory item │      │
│  │   (sanitized)    │        │   (full details) │      │
│  │ - Autonomy level │        │ - Seller prefs   │      │
│  │ - Thread history │        │ - Thread history │      │
│  │ - Privacy rules  │        │ - Privacy rules  │      │
│  └────────┬─────────┘        └────────┬─────────┘      │
│           │                           │                 │
│           └──────────┬────────────────┘                 │
│                      │                                  │
│              ┌───────▼────────┐                         │
│              │  THREAD CHAT   │  ← visible to both      │
│              │  (messages)    │    parties + user        │
│              └───────┬────────┘                         │
│                      │                                  │
│              ┌───────▼────────┐                         │
│              │ STATE MACHINE  │  ← validates every      │
│              │ + PRIVACY GATE │    transition            │
│              └────────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

**Key isolation rule:** The buyer agent never sees the seller's floor price. The seller agent never sees the buyer's ceiling. Each agent only knows what the other side chose to say in the thread.

---

## Thread Lifecycle / State Machine

### States

```
OPEN
  │
  │  Thread created, buyer agent generates opening offer
  ▼
BUYER_TURN ◄────────────────────────────────────────────────┐
  │                                                          │
  │  (if autonomy = supervised)                             │
  ├──► AWAITING_BUYER_APPROVAL                              │
  │         │  human approves / edits / rejects draft        │
  │         └──► back to BUYER_TURN or continue             │
  │                                                          │
  │  buyer agent message sent                               │
  ▼                                                          │
SELLER_TURN                                                  │
  │                                                          │
  │  (if seller supervised)                                  │
  ├──► AWAITING_SELLER_APPROVAL                             │
  │                                                          │
  │  seller agent message sent                              │
  ▼                                                          │
  ├── seller countered ──────────────────────────────────►──┘
  │
  ├── seller accepted ─────────────────────────────────────►
  │                                                         │
  ▼                                                         ▼
AGREED                                                   FAILED
  │
  │  (if autonomy_level = "full")
  ├──► auto-confirm → CONFIRMED → CLOSED
  │
  │  (if autonomy_level = "supervised")
  └──► AWAITING_HUMAN_CONFIRMATION
            │
            ├── human confirms ──► CONFIRMED ──► CLOSED
            └── human rejects ──► back to BUYER_TURN or FAILED
```

### State Enum

```python
class ThreadState(str, Enum):
    OPEN                        = "open"
    BUYER_TURN                  = "buyer_turn"
    AWAITING_BUYER_APPROVAL     = "awaiting_buyer_approval"
    SELLER_TURN                 = "seller_turn"
    AWAITING_SELLER_APPROVAL    = "awaiting_seller_approval"
    AGREED                      = "agreed"
    AWAITING_HUMAN_CONFIRMATION = "awaiting_human_confirmation"
    FAILED                      = "failed"
    CONFIRMED                   = "confirmed"
    CLOSED                      = "closed"
```

### Message Types

```python
class NegotiationMessageType(str, Enum):
    OPENING_OFFER  = "opening_offer"
    COUNTER_OFFER  = "counter_offer"
    ACCEPTANCE     = "acceptance"
    REJECTION      = "rejection"
    QUESTION       = "question"
    INFORMATION    = "information"
    SYSTEM         = "system"      # state change notifications, alignment updates
```

### Hard Limits (Enforced by State Machine, Not LLM)

| Rule | Enforcement |
|---|---|
| Max rounds (default 5) | `current_round >= max_rounds → FAILED` — state machine |
| Price ceiling never exceeded | Privacy gate strips exact ceiling from LLM context; TermExtractor validates `proposed_price <= ceiling` |
| Dealbreaker enforcement | If `dealbreakers_triggered` non-empty → buyer agent must reject |
| State transition validity | State machine validates every transition before committing |
| ZOPA pre-check | No LLM call made if buyer ceiling < seller floor |
| Seller identity hidden pre-agreement | Privacy filter strips seller name / contact until `CONFIRMED` |

---

## Autonomy Levels

Maps directly to the existing `mandate.autonomy_level` field.

| Level | Buyer agent behaviour | Human involvement |
|---|---|---|
| `full` | Negotiates and accepts autonomously | Notified of outcome only |
| `supervised` | Drafts each message, waits for human approval | Approves every outbound message |
| `manual` | Generates suggestions only | Human writes the actual messages |

---

## Privacy Model — What Each Agent Sees

### Buyer Agent System Prompt Contains

- Mandate category, intent, condition requirements
- Price as a **behavioural instruction**, never an exact value:
  > *"Your comfortable range is $900–$1,100. You have flexibility beyond this but must not state any upper limit. Start at the low end and negotiate up only under pressure."*
- Soft preferences (style, timing)
- Dealbreakers as boolean rules:
  > *"Reject anything that requires shipping — local pickup only."*
- Negotiation persona derived from `user.persona.deal_sensitivity`:
  - `price_first` → anchor low, concede slowly
  - `quality_first` → accept higher price for confirmed condition
  - `convenience_first` → prioritise timing and location flexibility

### Seller Agent System Prompt Contains

- Full inventory item public fields
- Seller's acceptable floor as a **behavioural instruction**:
  > *"Your target is $1,300. You can go as low as $1,050 if necessary. Never state your minimum. Start high and concede only when buyer demonstrates commitment."*
- Seller's flexibility preferences

### What Neither Agent Sees

- The other party's exact floor or ceiling
- The full mandate or full inventory before agreement
- The computed ZOPA (Zone of Possible Agreement)

---

## ZOPA Detection (Pre-Negotiation Gate)

Computed deterministically before any LLM call. No agents are invoked if there is no viable price overlap.

```python
@dataclass
class ZOPAResult:
    viable: bool
    overlap: float | None    # positive = overlap amount
    gap: float | None        # positive = shortfall amount

def compute_zopa(
    buyer_ceiling: float,
    seller_floor: float
) -> ZOPAResult:
    diff = buyer_ceiling - seller_floor
    if diff < 0:
        return ZOPAResult(viable=False, overlap=None, gap=abs(diff))
    return ZOPAResult(viable=True, overlap=diff, gap=None)
```

If `viable=False` → thread immediately moves to `FAILED` with `failed_reason = "no_price_overlap"`.

---

## Structured Term Extraction

Every LLM-generated message is parsed via a separate forced `tool_use` call to extract structured terms. **The state machine operates only on `NegotiationTerms`, never on raw text.** This keeps the protocol deterministic even though the content is LLM-generated.

```python
@dataclass
class NegotiationTerms:
    proposed_price: float | None
    condition_acceptable: bool | None
    timing: str | None
    location_ok: bool | None
    message_type: NegotiationMessageType
    dealbreakers_triggered: list[str]
```

### Example

```
LLM generates:  "I can meet you at $1,275 if pickup is this weekend."
                         ↓  TermExtractor (forced tool_use)
NegotiationTerms: {
  proposed_price: 1275,
  timing: "this_weekend",
  message_type: "counter_offer",
  dealbreakers_triggered: []
}
```

---

## Alignment Score

A continuously updated metric showing how close the two parties are. Computed deterministically from structured terms — never by LLM.

```python
def compute_alignment_score(
    mandate: SanitizedMandate,
    latest_terms: NegotiationTerms,
) -> float:
    score = 0.0

    # Price convergence (40%)
    if latest_terms.proposed_price and buyer_range > 0:
        gap_pct = abs(latest_terms.proposed_price - buyer_midpoint) / buyer_range
        score += 0.40 * max(0.0, 1.0 - gap_pct)

    # Condition match (25%)
    if latest_terms.condition_acceptable is True:
        score += 0.25

    # Location / timing (20%)
    if latest_terms.location_ok is True:
        score += 0.20

    # No dealbreakers triggered (15%)
    if not latest_terms.dealbreakers_triggered:
        score += 0.15

    return round(score, 2)
```

Displayed in the chat thread as system messages:

```
[SYSTEM]:  Alignment score: 78% ↑  (was 54%)
```

---

## LLM Call Budget Per Negotiation

### Per Round (one exchange)

| Call | Purpose | Max tokens |
|---|---|---|
| Buyer agent generation | Natural language offer / counter | ~500 |
| Buyer term extraction | Forced tool_use on buyer message | ~128 |
| Seller agent generation | Natural language response | ~500 |
| Seller term extraction | Forced tool_use on seller message | ~128 |

**Per round: 4 LLM calls, ~1,256 tokens.**
**Max 5 rounds: 20 LLM calls per negotiation thread.**

This cost must be surfaced to the user before negotiation starts.

---

## Module Structure

```
app/negotiation_engine/
  __init__.py
  state_machine.py        # ThreadState, NegotiationMessageType, TRANSITION_TABLE
  protocol.py             # NegotiationMessage, NegotiationTerms, ZOPAResult,
  │                       # AlignmentScore, EscalationOffer
  orchestrator.py         # NegotiationOrchestrator — manages turn-taking loop
  buyer_agent.py          # BuyerAgentLLM — generates buyer messages
  seller_agent.py         # SellerAgentLLM — generates seller messages
  term_extractor.py       # TermExtractor — forced tool_use structured parsing
  alignment_scorer.py     # AlignmentScorer — deterministic convergence metric
  zopa.py                 # ZOPADetector — pre-negotiation viability check
  signal_handler.py       # Human intervention handling
  privacy_filter.py       # Outbound message sanitization (strips private values)
```

---

## DB Schema

### `negotiation_threads` (extended)

```sql
CREATE TABLE negotiation_threads (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id         UUID NOT NULL REFERENCES users(id),
    mandate_id       UUID NOT NULL REFERENCES mandates(id),
    search_result_id UUID NOT NULL REFERENCES search_results(id),
    state            TEXT NOT NULL DEFAULT 'open',
    max_rounds       INTEGER NOT NULL DEFAULT 5,
    current_round    INTEGER NOT NULL DEFAULT 0,
    alignment_score  FLOAT,
    agreed_terms     JSONB,          -- final agreed NegotiationTerms on AGREED
    failed_reason    TEXT,           -- reason string if FAILED
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (mandate_id, search_result_id)
);

CREATE INDEX idx_negotiation_threads_owner   ON negotiation_threads(owner_id);
CREATE INDEX idx_negotiation_threads_mandate ON negotiation_threads(mandate_id);
```

### `negotiation_messages` (new)

```sql
CREATE TABLE negotiation_messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id        UUID NOT NULL REFERENCES negotiation_threads(id),
    role             TEXT NOT NULL,   -- buyer_agent|seller_agent|buyer_human|seller_human|system
    message_type     TEXT NOT NULL,   -- opening_offer|counter_offer|acceptance|rejection|question|system
    content          TEXT NOT NULL,   -- natural language (LLM-generated or human-written)
    structured_terms JSONB,           -- extracted NegotiationTerms
    alignment_score  FLOAT,           -- score at time of this message
    is_draft         BOOLEAN NOT NULL DEFAULT FALSE,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approved_at      TIMESTAMPTZ,
    approved_by      UUID REFERENCES users(id),
    visible_to_buyer  BOOLEAN NOT NULL DEFAULT TRUE,
    visible_to_seller BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_negotiation_messages_thread ON negotiation_messages(thread_id);
CREATE INDEX idx_negotiation_messages_role   ON negotiation_messages(thread_id, role);
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/mandates/{id}/negotiations` | Initiate negotiation thread for a search result |
| `GET` | `/negotiations/{thread_id}` | Get thread state + full message history |
| `GET` | `/negotiations/{thread_id}/messages` | Stream or poll messages |
| `POST` | `/negotiations/{thread_id}/approve` | Approve a draft message (supervised mode) |
| `POST` | `/negotiations/{thread_id}/edit` | Edit + approve a draft (supervised mode) |
| `POST` | `/negotiations/{thread_id}/confirm` | Human final confirmation on AGREED |
| `POST` | `/negotiations/{thread_id}/abort` | Human terminates thread → FAILED |
| `GET` | `/mandates/{id}/negotiations` | List all threads for a mandate |

---

## Privacy Gate Checkpoints

### Checkpoint 1 — Before buyer agent generates a message

Buyer agent's system prompt is constructed from `SanitizedMandate`, not raw `Mandate`. Exact `negotiation_range` values are replaced with behavioural instructions.

### Checkpoint 2 — Before any message crosses the thread boundary

`privacy_filter.py` scans the generated message for patterns that could reveal private values (e.g., exact price matches, contact information) before it is written to `negotiation_messages`.

```python
def filter_outbound_message(
    content: str,
    structured_terms: NegotiationTerms,
    sender_role: str,
    private_values: list[float | str]   # buyer ceiling, seller floor, etc.
) -> str:
    # Redacts any private_values found literally in content
    # Raises PrivacyLeakDetected if structured_terms.proposed_price > ceiling
```

### Checkpoint 3 — Before seller identity is revealed

Seller name, contact, and exact location are withheld until thread reaches `CONFIRMED`.

---

## What Remains Deterministic (Never LLM Decisions)

| Decision | Enforced by |
|---|---|
| Is this transition valid? | `NegotiationStateMachine.transition()` |
| Has max rounds been reached? | `orchestrator.py` — hard counter check |
| Is there price overlap? | `ZOPADetector.compute_zopa()` |
| Did a dealbreaker trigger? | `TermExtractor` + rule check in `orchestrator.py` |
| Is the proposed price within ceiling? | `privacy_filter.py` post-generation validation |
| What alignment score is displayed? | `AlignmentScorer.compute()` — pure function |
| When to snapshot mandate version? | State machine on `CONFIRMED` — always |

---

## UI Features Enabled

| Feature | Description |
|---|---|
| **Live chat panel** | User watches agents negotiate (SSE or WebSocket) |
| **Alignment meter** | Visual progress bar updating per message |
| **Intervention button** | "Take over" drops user into thread as `buyer_human` |
| **Draft approval panel** | In supervised mode, user sees and approves drafts |
| **Thread archive** | Every negotiation thread stored and browsable |
| **Outcome card** | On `CONFIRMED`, shows agreed terms and full chat history |

---

## Open Design Questions

1. **Who is the seller agent?**
   Is the seller a Tarpspace user with their own personal agent, or is the seller agent a synthetic persona generated from the inventory listing? If sellers are real users, seller agents have full personas. If inventory is passive data, the seller agent is a synthetic construct.

2. **Realtime vs async delivery?**
   Does the buyer see seller agent responses appear in real time? Realtime requires WebSocket / SSE infrastructure not yet present in Phase 1.

3. **When does negotiation start?**
   Automatically on every confirmed match, or only when the user explicitly initiates? Explicit initiation is safer for LLM cost control.

4. **Transaction completion layer?**
   After `CONFIRMED`, what happens? Escrow, meeting scheduler, contact exchange? This is fully absent from the current architecture and represents the largest missing layer beyond Phase 3.

5. **Trust weight updates?**
   `TrustEdge` model exists. Should a completed negotiation that results in `CONFIRMED` + a successful transaction update the trust weight between buyer and seller? Deferred to Phase 4+.

---

## What is Explicitly Absent (Phase 3 Scope)

| Feature | Status | Reason |
|---|---|---|
| Autonomous seller users | Absent | Phase 3 — seller agent is synthetic |
| Realtime streaming | Absent | Phase 3 — polling only |
| Multi-item bundle negotiation | Absent | Out of scope |
| Dispute resolution | Absent | Post-Phase 3 |
| Trust weight updates from negotiation | Absent | Phase 4+ |
| Escrow / payment | Absent | Out of scope for Phase 1–3 |
| Cross-mandate negotiation | Absent | One mandate ↔ one listing only |
