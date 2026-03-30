# Social Interaction Engine — Proof of Concept Design

**Status:** Design / POC
**Focus:** Social matching and connection — NOT buying or selling
**Last updated:** 2026-03-30

---

## Overview

For the proof of concept, the platform focuses entirely on **social connection** — helping people find others who share their interests and facilitating a warm introduction between their agents.

A user looking for a football partner, a guitar collaborator, a hiking buddy, or a chess opponent describes what they are looking for. Their personal agent finds compatible profiles, and two agents conduct a conversation to align on shared interests, availability, and logistics before both users are introduced.

**There is no price, no transaction, no mandate in the commercial sense.** The "alignment" is purely about shared interests and mutual willingness to connect.

---

## Core Concepts (Replacing Commercial Terms)

| Commercial Concept | Social Equivalent |
|---|---|
| Mandate | Interest Profile |
| Inventory item | User profile / Activity listing |
| Price negotiation | Interest alignment conversation |
| Accept / reject offer | Agree / decline to connect |
| Deal confirmed | Connection established |
| Escalation | Broadening the activity or availability window |
| Buyer agent | Seeker agent |
| Seller agent | Match agent |

---

## Example Use Cases

```
"I want to find someone to play 5-a-side football with on weekends in Houston."

"Looking for a guitarist to jam with — I play rhythm, need a lead player."

"Want to find a chess partner at a similar level (intermediate) for weekly games."

"Looking for a running partner — I run 5k, early mornings, South Houston area."

"Need someone to practice Spanish conversation with over video call."
```

---

## Interest Profile (Replaces Mandate)

An Interest Profile is what the personal agent captures through conversation. It answers: *Who are you looking for, and what do you want to do together?*

```python
@dataclass
class InterestProfile:
    owner_id: str

    # What they want to do
    activity: str                        # "play football", "jam on guitar", "run 5k"
    activity_category: str               # "sports", "music", "fitness", "games", "arts", "education"
    intent: str                          # "find_player", "find_collaborator", "find_mentor",
                                         # "find_student", "find_friend", "find_group"

    # Who they want to connect with
    skill_level_self: str | None         # "beginner" | "intermediate" | "advanced"
    skill_level_wanted: str | None       # what level they are looking for
    group_size: int | None               # 1-on-1 vs small group vs open group

    # When and where
    availability: list[str]              # ["weekends", "weekday_evenings", "flexible"]
    location: str | None                 # city or area
    location_type: str | None            # "in_person" | "online" | "either"

    # Soft preferences
    vibe: str | None                     # "casual", "competitive", "social", "focused"
    notes: str | None                    # free-text extra context

    # Completeness
    completeness_score: float
    is_active: bool
```

---

## Activity Listing (Replaces Inventory Item)

What a user puts out when they are open to being found. Created by the personal agent when a user says they are open to connecting with others around a specific activity.

```python
@dataclass
class ActivityListing:
    id: str
    owner_id: str

    activity: str
    activity_category: str
    skill_level: str | None
    availability: list[str]
    location: str | None
    location_type: str | None
    vibe: str | None
    about: str                          # 1-2 sentence human description
    about_embedding: list[float]        # 1024-dim for semantic search
    is_open: bool                       # whether they are currently looking to connect
    created_at: datetime
```

---

## Retrieval — Finding Compatible People

The retrieval engine searches `activity_listings` using the same pgvector pipeline, but the match criteria are purely social:

### Match Dimensions

| Dimension | Weight | Logic |
|---|---|---|
| Activity similarity | 40% | Semantic embedding match on `about` |
| Category match | 25% | Hard filter — same activity category |
| Location compatibility | 15% | Same city / online acceptable |
| Availability overlap | 10% | At least one shared availability slot |
| Skill level compatibility | 10% | Within one level of each other |

### No Escalation

There is no price escalation in the social model. If no exact match exists, the system may suggest:
- Broadening the activity (e.g., "any racket sport" instead of specifically "badminton")
- Broadening availability (e.g., adding weekday evenings)
- Broadening location (e.g., accepting online)

These are surfaced as **suggestions**, not automatic widening.

---

## Connection Thread Lifecycle

A connection thread is opened when a seeker's Interest Profile matches an Activity Listing. Two agents conduct a brief introduction conversation to confirm mutual interest and align on logistics.

```
  OPEN
    │
    │  Thread created. Seeker agent sends warm introduction.
    ▼
  SEEKER_INTRODUCING
    │
    │  Match agent responds — shares more about the potential match.
    ▼
  MATCH_RESPONDING
    │
    ├── match agent shows interest ──────────────────────────────►
    │                                                             │
    ├── match agent not interested ──────────────────────────────► DECLINED
    │
    ▼
  ALIGNING
    │
    │  Agents exchange details — availability, location, logistics.
    │  May go 2–3 rounds.
    │
    ├── both aligned ───────────────────────────────────────────►
    │                                                             │
    ├── cannot align (schedule / location conflict) ─────────────► INCOMPATIBLE
    │
    ▼
  AGREED
    │
    │  Both agents confirm the connection makes sense.
    │
    ├── autonomy = full ──► auto-connect ──────────────────────►
    │                                                            │
    └── autonomy = supervised ──► AWAITING_HUMAN_CONFIRMATION   │
                │                                               │
                ├── human confirms ──────────────────────────►  │
                └── human declines ──► DECLINED               │
                                                               ▼
                                                          CONNECTED
                                                               │
                                                               ▼
                                                           CLOSED
```

### States

```python
class ConnectionState(str, Enum):
    OPEN                        = "open"
    SEEKER_INTRODUCING          = "seeker_introducing"
    MATCH_RESPONDING            = "match_responding"
    ALIGNING                    = "aligning"
    AGREED                      = "agreed"
    AWAITING_HUMAN_CONFIRMATION = "awaiting_human_confirmation"
    CONNECTED                   = "connected"
    DECLINED                    = "declined"
    INCOMPATIBLE                = "incompatible"
    CLOSED                      = "closed"
```

### Message Types

```python
class ConnectionMessageType(str, Enum):
    INTRODUCTION    = "introduction"       # seeker agent opens
    RESPONSE        = "response"           # match agent responds
    AVAILABILITY    = "availability"       # sharing when/where
    QUESTION        = "question"           # asking for clarification
    AGREEMENT       = "agreement"          # both confirm interest
    DECLINATION     = "declination"        # polite decline
    SYSTEM          = "system"             # alignment score, state changes
```

---

## The Connection Conversation — Example

```
[SYSTEM]:       Match found — Alex's profile vs. your football search.
                Compatibility score: 71%. Starting introduction.

[seeker_agent]: Hi! I'm reaching out on behalf of Jordan, who is looking
                for someone to play 5-a-side football with on weekends
                in South Houston. Jordan plays midfield, casual to
                semi-competitive level. Would Alex be open to connecting?

[match_agent]:  Hey! Alex plays on weekends too — usually Sunday mornings
                around Memorial Park area. Alex is more of a casual player,
                mainly in it for the fun and fitness. Sounds like a good
                match so far. What kind of group size is Jordan looking for?

[seeker_agent]: Jordan is flexible — happy with a regular 2v2 pickup game
                or joining a small group. Sunday mornings work well.
                Memorial Park is about 20 minutes away — that's fine.

[match_agent]:  Perfect. Alex usually plays with one or two regulars and
                would love to expand the group. Sunday 9am is the usual
                time. Does that work for Jordan?

[seeker_agent]: Sunday 9am works great. Jordan is keen to connect.

[match_agent]:  Alex is in. Looking forward to it.

[SYSTEM]:       Both agents aligned. Compatibility score: 89%.
                Waiting for your confirmation to share contact details.

[seeker_human]: ✓ Connect
```

---

## Dual-Agent Architecture (Social Version)

```
┌──────────────────────────────────────────────────────────┐
│                  CONNECTION THREAD                       │
│                                                          │
│  ┌──────────────────┐       ┌──────────────────┐        │
│  │   SEEKER AGENT   │       │   MATCH AGENT    │        │
│  │                  │       │                  │        │
│  │ Context:         │       │ Context:         │        │
│  │ - Interest       │       │ - Activity       │        │
│  │   Profile        │       │   Listing        │        │
│  │ - User persona   │       │ - Match user     │        │
│  │ - Availability   │       │   persona        │        │
│  │ - Vibe prefs     │       │ - Their avail.   │        │
│  └────────┬─────────┘       └────────┬─────────┘        │
│           │                          │                   │
│           └─────────┬────────────────┘                   │
│                     │                                    │
│             ┌───────▼────────┐                           │
│             │  THREAD CHAT   │  ← visible to both users  │
│             └───────┬────────┘                           │
│                     │                                    │
│             ┌───────▼────────┐                           │
│             │ STATE MACHINE  │                           │
│             │ + ALIGNMENT    │                           │
│             │   SCORER       │                           │
│             └────────────────┘                           │
└──────────────────────────────────────────────────────────┘
```

---

## What Each Agent Knows

### Seeker Agent System Prompt Contains

- Seeker's Interest Profile (activity, skill level, availability, location, vibe)
- Seeker's persona from Personal Agent (name, communication style, general interests)
- Instructions to be warm, specific about the activity, and ask about availability early
- **Does NOT contain:** seeker's contact details, last name, exact address (shared only after `CONNECTED`)

### Match Agent System Prompt Contains

- Match user's Activity Listing (about, activity, availability, location, skill level)
- Match user's persona from Personal Agent (name, communication style)
- Instructions to represent the match honestly, decline gracefully if not a fit
- **Does NOT contain:** match user's contact details (shared only after `CONNECTED`)

### Privacy Rule

Neither agent shares contact information (phone, email, social handles) until the thread reaches `CONNECTED` and both humans have confirmed. Before that, communication is only via the agent thread.

---

## Alignment Score (Social Version)

Tracks how compatible the two users appear to be as the conversation develops.

```python
def compute_alignment_score(
    profile: InterestProfile,
    listing: ActivityListing,
    latest_terms: ConnectionTerms,
) -> float:
    score = 0.0

    # Activity compatibility (40%)
    # — computed from semantic similarity of about_embedding vs query_vec
    score += 0.40 * activity_similarity_score

    # Availability overlap (25%)
    overlap = set(profile.availability) & set(listing.availability)
    if overlap:
        score += 0.25

    # Location compatibility (20%)
    if location_compatible(profile.location, listing.location,
                           profile.location_type, listing.location_type):
        score += 0.20

    # Skill level compatibility (15%)
    if skill_levels_compatible(profile.skill_level_wanted, listing.skill_level):
        score += 0.15

    return round(score, 2)
```

---

## Structured Term Extraction (Social Version)

After each agent message, `TermExtractor` parses structured signals. The state machine advances based on these, not raw text.

```python
@dataclass
class ConnectionTerms:
    message_type: ConnectionMessageType
    interest_confirmed: bool | None       # has this party shown interest?
    availability_shared: list[str]        # time slots mentioned
    location_shared: str | None           # location mentioned
    skill_level_shared: str | None
    questions_asked: list[str]            # what they asked about
    declined: bool                        # explicit decline
```

---

## Autonomy Levels (Social)

Maps to `interest_profile.autonomy_level`:

| Level | Agent behaviour | Human involvement |
|---|---|---|
| `full` | Agent introduces, aligns, and connects autonomously | Notified when connected |
| `supervised` | Agent drafts each message, waits for human approval | Reviews every outbound message |
| `manual` | Agent generates suggestions only | Human writes messages |

---

## LLM Call Budget Per Connection Thread

### Per Round (one exchange)

| Call | Purpose | Max tokens |
|---|---|---|
| Seeker agent generation | Introduction / follow-up | ~400 |
| Seeker term extraction | Forced tool_use | ~128 |
| Match agent generation | Response / alignment | ~400 |
| Match term extraction | Forced tool_use | ~128 |

**Per round: 4 LLM calls, ~1,056 tokens.**
**Max 3 rounds: 12 LLM calls per connection thread** (social alignment is faster than price negotiation).

---

## Privacy Gate (Social Version)

Much simpler than the commercial privacy gate — no prices or financial data. Focus is on:

1. **Contact details withheld** until `CONNECTED` — no phone, email, or social handles in the thread
2. **Full name withheld** — agents use first name only until connected
3. **Exact address withheld** — agents share area / neighbourhood, not street address
4. **No cross-contamination** — seeker agent cannot access match user's full persona, only their Activity Listing

---

## DB Schema

### `interest_profiles`

```sql
CREATE TABLE interest_profiles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          UUID NOT NULL REFERENCES users(id),
    activity          TEXT NOT NULL,
    activity_category TEXT NOT NULL,
    intent            TEXT NOT NULL,
    skill_level_self  TEXT,
    skill_level_wanted TEXT,
    group_size        INTEGER,
    availability      TEXT[],
    location          TEXT,
    location_type     TEXT,
    vibe              TEXT,
    notes             TEXT,
    autonomy_level    TEXT NOT NULL DEFAULT 'supervised',
    completeness_score FLOAT NOT NULL DEFAULT 0.0,
    is_active         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_interest_profiles_owner    ON interest_profiles(owner_id);
CREATE INDEX idx_interest_profiles_category ON interest_profiles(activity_category);
CREATE INDEX idx_interest_profiles_active   ON interest_profiles(is_active);
```

### `activity_listings`

```sql
CREATE TABLE activity_listings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id            UUID NOT NULL REFERENCES users(id),
    activity            TEXT NOT NULL,
    activity_category   TEXT NOT NULL,
    skill_level         TEXT,
    availability        TEXT[],
    location            TEXT,
    location_type       TEXT,
    vibe                TEXT,
    about               TEXT NOT NULL,
    about_embedding     vector(1024),
    is_open             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_activity_listings_owner    ON activity_listings(owner_id);
CREATE INDEX idx_activity_listings_category ON activity_listings(activity_category);
CREATE INDEX idx_activity_listings_open     ON activity_listings(is_open);
CREATE INDEX idx_activity_listings_embedding
    ON activity_listings
    USING ivfflat (about_embedding vector_cosine_ops)
    WITH (lists = 50);
```

### `connection_threads`

```sql
CREATE TABLE connection_threads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seeker_id           UUID NOT NULL REFERENCES users(id),
    match_id            UUID NOT NULL REFERENCES users(id),
    interest_profile_id UUID NOT NULL REFERENCES interest_profiles(id),
    listing_id          UUID NOT NULL REFERENCES activity_listings(id),
    state               TEXT NOT NULL DEFAULT 'open',
    max_rounds          INTEGER NOT NULL DEFAULT 3,
    current_round       INTEGER NOT NULL DEFAULT 0,
    alignment_score     FLOAT,
    agreed_terms        JSONB,
    declined_reason     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (interest_profile_id, listing_id)
);

CREATE INDEX idx_connection_threads_seeker  ON connection_threads(seeker_id);
CREATE INDEX idx_connection_threads_match   ON connection_threads(match_id);
```

### `connection_messages`

```sql
CREATE TABLE connection_messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id         UUID NOT NULL REFERENCES connection_threads(id),
    role              TEXT NOT NULL,     -- seeker_agent|match_agent|seeker_human|match_human|system
    message_type      TEXT NOT NULL,
    content           TEXT NOT NULL,
    structured_terms  JSONB,
    alignment_score   FLOAT,
    is_draft          BOOLEAN NOT NULL DEFAULT FALSE,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approved_at       TIMESTAMPTZ,
    approved_by       UUID REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_connection_messages_thread ON connection_messages(thread_id);
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/profiles` | Create an Interest Profile via agent conversation |
| `GET` | `/profiles/{id}` | Get profile state |
| `POST` | `/profiles/{id}/search` | Find compatible Activity Listings |
| `GET` | `/listings` | Get my Activity Listings (what I put out to be found) |
| `POST` | `/listings` | Create an Activity Listing (I'm open to being found) |
| `POST` | `/connections` | Initiate connection thread for a listing match |
| `GET` | `/connections/{thread_id}` | Get thread state + full message history |
| `POST` | `/connections/{thread_id}/approve` | Approve a draft message (supervised) |
| `POST` | `/connections/{thread_id}/confirm` | Human final confirmation on AGREED |
| `POST` | `/connections/{thread_id}/decline` | Human declines the connection |
| `GET` | `/connections` | List all my connection threads |

---

## Module Structure

```
app/
  social_engine/
    __init__.py
    state_machine.py        # ConnectionState, ConnectionMessageType, TRANSITION_TABLE
    protocol.py             # ConnectionTerms, AlignmentScore, ConnectionThread models
    orchestrator.py         # ConnectionOrchestrator — manages turn-taking
    seeker_agent.py         # SeekerAgentLLM — generates seeker introductions
    match_agent.py          # MatchAgentLLM — generates match responses
    term_extractor.py       # ConnectionTermExtractor — forced tool_use parsing
    alignment_scorer.py     # AlignmentScorer — availability + activity + location
    privacy_filter.py       # Strips contact info, exact addresses until CONNECTED
  api/
    social.py               # All social engine routes
  db/
    # new tables in migration 20260329_005_social_engine.py
```

---

## Full POC User Flow

```
1. User signs up → Personal Agent collects name, city, interests

2. User says: "I want to find someone to play football with"
   → Mandate Agent (repurposed as Interest Agent) captures:
     activity = "play football"
     category = "sports"
     intent = "find_player"
     availability = ["weekends"]
     location = "Houston" (pre-filled from persona)
     skill_level_self = "casual"
     vibe = "social"

3. Interest Profile confirmed (completeness >= 0.70)

4. User posts Activity Listing:
   → "I play casual 5-a-side football, weekends in Houston.
      Looking for more players."
   → Embedding generated, stored in activity_listings

5. Retrieval Engine runs:
   → Searches activity_listings by embedding + category filter + location
   → Returns top 5 compatible profiles with alignment scores

6. User selects a match → Connection Thread initiated

7. Seeker Agent generates introduction
   → Match Agent responds (synthetic from listing, or real user's agent)
   → 2–3 rounds of alignment conversation

8. Both agree → AGREED → user confirms → CONNECTED
   → Contact details / first names exchanged
   → Thread archived

9. Users meet and play football.
```

---

## Seed Data for POC (from v2-yomi `data/agents.py`)

The 100 existing agent profiles in `data/agents.py` map directly to `activity_listings`:

```python
# v2-yomi agent profile:
{
  "name": "Marcus Johnson",
  "intent_type": "social_connection",   # ← already social!
  "activity": "guitarist",
  "about": "Passionate guitarist with 10 years experience...",
  "location_raw": "Houston, Texas, USA"
}

# Maps to ActivityListing:
ActivityListing(
  activity = "play guitar",
  activity_category = "music",
  skill_level = "advanced",
  location = "Houston",
  about = "Passionate guitarist with 10 years experience...",
  about_embedding = embedder.embed("Passionate guitarist..."),
  is_open = True
)
```

All 100 agents are already `social_connection` intent type — the v2-yomi seed data was designed for exactly this use case.

---

## What is Explicitly Absent (POC Scope)

| Feature | Status | Reason |
|---|---|---|
| Any buying / selling | Absent | Not the focus of this POC |
| Price negotiation | Absent | No commercial transactions |
| Escrow / payment | Absent | Out of scope |
| Multi-user group formation | Absent | 1-on-1 connections only in POC |
| Event scheduling | Absent | Connection only — logistics handled off-platform |
| Real-time streaming | Absent | Polling only in POC |
| Seller-side agent autonomy | Absent | Match agent is synthetic in POC |
| Trust scoring from connections | Absent | TrustEdge model exists — deferred |
