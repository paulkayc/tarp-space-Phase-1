# CONTRACTS.md
## Tarp-Space — API Contracts Between Dev A (Backend) and Dev B (Frontend)

> **Version:** 1.0  
> **Purpose:** This file is the source of truth for every interface between backend and frontend. Dev B must not make assumptions about API shape. Dev A must not change a contract without updating this file and notifying Dev B.  
> **Last Updated:** March 2026

---

## How This File Works

- **Dev A owns:** all entries under "Backend provides"
- **Dev B consumes:** all entries under "Frontend calls"
- When a contract changes, Dev A updates this file and adds `[CHANGED - Week X]` to the entry
- Dev B reviews changes before implementing
- All endpoints require JWT auth header unless marked `[PUBLIC]`
- All responses are JSON. All request bodies are JSON unless noted.
- All timestamps are ISO 8601 UTC: `2026-03-15T14:22:00Z`
- All IDs are UUID v4 strings

---

## Base URL

```
Development:  http://localhost:8000
Staging:      https://api-staging.tarpspace.com
Production:   https://api.tarpspace.com
```

---

## Auth Header

Every request (except `[PUBLIC]` endpoints and `/health`) must include:
```
Authorization: Bearer <clerk_jwt_token>
```
Failure returns:
```json
{ "error": "unauthorized", "message": "Valid JWT required" }
```
HTTP status: `401`

---

## WebSocket Connection

```
Development:  ws://localhost:8000/ws/agent-activity
Staging:      wss://api-staging.tarpspace.com/ws/agent-activity
Production:   wss://api.tarpspace.com/ws/agent-activity
```

Auth: JWT in `Authorization` header on connection upgrade.  
Scope: Only events for the authenticated owner's agents are pushed — no cross-user events.

---

## Standard Error Response

All errors return this shape:
```json
{
  "error": "error_code_snake_case",
  "message": "Human readable message",
  "details": {}
}
```

Common error codes:
| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `unauthorized` | 401 | Missing or invalid JWT |
| `forbidden` | 403 | Valid JWT, but not owner of this resource |
| `not_found` | 404 | Resource does not exist |
| `validation_error` | 422 | Request body failed schema validation |
| `rate_limited` | 429 | Too many requests |
| `server_error` | 500 | Unexpected backend error |

---

## Phase 1 Contracts — Foundation & Auth
*Available by end of Week 4*

---

### C1.1 — Health Check `[PUBLIC]`

```
GET /health
```

**Response 200:**
```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "version": "1.0.0"
}
```

**Dev B uses this for:** App startup check. Show maintenance screen if `status != "ok"`.

---

### C1.2 — Get Current User

```
GET /users/me
```

**Response 200:**
```json
{
  "id": "uuid",
  "clerk_id": "clerk_user_abc123",
  "email": "user@example.com",
  "phone": "+17135550100",
  "display_name": "Alex Rivera",
  "verified_at": "2026-03-15T14:22:00Z",
  "identity_confidence": 0.95,
  "onboarding_status": "mandate_confirmed",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:22:00Z"
}
```

**`onboarding_status` values:**
| Value | Meaning | Dev B routing |
|-------|---------|---------------|
| `account_created` | User created, no mandate yet | Show onboarding step 1 |
| `mandate_draft` | Has a mandate in draft | Show onboarding step 2 |
| `mandate_confirmed` | Has a confirmed mandate | Show agent console |

**Response 404:** User does not exist yet (Clerk webhook may be delayed). Retry after 2s.

**Dev B uses this for:** App load routing. Always call this first on app open.

---

### C1.3 — Update Current User

```
PATCH /users/me
```

**Request body:**
```json
{
  "display_name": "Alex Rivera",
  "phone": "+17135550100"
}
```
All fields optional. Only include fields to update.

**Response 200:** Same as C1.2.

**Response 422:**
```json
{
  "error": "validation_error",
  "message": "Phone number format invalid",
  "details": { "field": "phone", "expected": "E.164 format" }
}
```

---

### C1.4 — Get Current Agent

```
GET /agents/me
```

**Response 200:**
```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "status": "inactive",
  "reputation_score": 0.5,
  "active_mandate_count": 0,
  "completed_negotiation_count": 0,
  "created_at": "2026-03-15T14:00:00Z"
}
```

**`status` values:**
| Value | Meaning |
|-------|---------|
| `inactive` | No confirmed mandate. Agent does nothing. |
| `active` | Has at least one confirmed mandate. Agent is operational. |
| `identity_review` | Account flagged — cannot enter network. |
| `suspended` | Account suspended. |

**Dev B uses this for:** Showing agent status indicator in console header.

---

### C1.5 — Register Device Token (Push Notifications)

```
POST /devices/register
```

**Request body:**
```json
{
  "token": "ExponentPushToken[xxxxxx]",
  "platform": "ios"
}
```

**`platform` values:** `ios` | `android` | `web`

**Response 200:**
```json
{ "registered": true }
```

**Dev B calls this after:** User grants notification permission. Silently — no UI needed on success.

---

## Phase 2 Contracts — The Agent & Mandate
*Available by end of Week 10*

---

### C2.1 — List Mandates

```
GET /mandates
```

**Query params:**
| Param | Type | Values | Default |
|-------|------|--------|---------|
| `status` | string | `draft`, `active`, `paused`, `completed`, `all` | `all` |
| `limit` | int | 1–50 | 20 |
| `cursor` | string | cursor from previous response | none |

**Response 200:**
```json
{
  "mandates": [
    {
      "id": "uuid",
      "intent_type": "buy",
      "vertical": "goods",
      "category": "furniture",
      "description": "Looking for a mid-century modern sofa in good condition...",
      "completeness_score": 0.85,
      "status": "active",
      "autonomy_level": "escalate_key_points",
      "confirmed_at": "2026-03-15T14:22:00Z",
      "created_at": "2026-03-15T14:00:00Z",
      "updated_at": "2026-03-15T14:22:00Z"
    }
  ],
  "next_cursor": "cursor_string_or_null",
  "total": 3
}
```

---

### C2.2 — Create Mandate

```
POST /mandates
```

**Request body:**
```json
{
  "intent_type": "buy",
  "vertical": "goods",
  "category": "furniture"
}
```

All fields optional. Agent will elicit through conversation. Providing them just pre-fills state machine.

**Response 201:**
```json
{
  "id": "uuid",
  "intent_type": "buy",
  "vertical": "goods",
  "category": "furniture",
  "description": null,
  "hard_constraints": [],
  "negotiation_range": {},
  "soft_preferences": [],
  "dealbreakers": [],
  "escalation_triggers": [],
  "autonomy_level": "escalate_key_points",
  "completeness_score": 0.15,
  "source_flags": {
    "intent_type": "explicit",
    "vertical": "explicit",
    "category": "explicit"
  },
  "confirmed_at": null,
  "status": "draft",
  "version": 1,
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:00:00Z"
}
```

---

### C2.3 — Get Mandate Detail

```
GET /mandates/{mandate_id}
```

**Response 200:** Full mandate object (same as C2.2 response).

**Response 403:** Caller is not the owner of this mandate.

---

### C2.4 — Send Elicitation Message

```
POST /mandates/{mandate_id}/message
```

**Request body:**
```json
{
  "content": "I'm looking for something around $400 to $600"
}
```

**Response 200:**
```json
{
  "agent_message": {
    "id": "uuid",
    "role": "agent",
    "content": "Got it — budget between $400 and $600. Are you flexible on condition, or do you need it to be in excellent shape?",
    "dimension": "condition_quality",
    "created_at": "2026-03-15T14:05:00Z"
  },
  "mandate_updated": {
    "completeness_score": 0.55,
    "source_flags": {
      "budget_price": "explicit"
    }
  },
  "elicitation_complete": false
}
```

**When `elicitation_complete: true`:**
```json
{
  "agent_message": {
    "id": "uuid",
    "role": "agent",
    "content": "Here's what I know about your search. You're looking for a mid-century modern sofa, used condition acceptable, between $400–$600, in the Heights neighborhood of Houston, needed within 2 weeks. Does this look right?",
    "dimension": "confirmation",
    "created_at": "2026-03-15T14:10:00Z"
  },
  "mandate_updated": {
    "completeness_score": 0.90
  },
  "elicitation_complete": true
}
```

**Response 429:** Too many messages (> 30/hour). Retry-After header included.

**Dev B:** Show typing indicator immediately after send. Display `agent_message.content` when response arrives. Update completeness bar using `mandate_updated.completeness_score`.

---

### C2.5 — Get Conversation History

```
GET /mandates/{mandate_id}/conversation
```

**Response 200:**
```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "agent",
      "content": "Hi! I'm your Tarp-Space agent. What are you looking to buy, sell, or find today?",
      "dimension": "intent_type",
      "created_at": "2026-03-15T14:00:00Z"
    },
    {
      "id": "uuid",
      "role": "owner",
      "content": "I need a sofa",
      "dimension": null,
      "created_at": "2026-03-15T14:01:00Z"
    }
  ],
  "total": 12
}
```

---

### C2.6 — Confirm Mandate

```
POST /mandates/{mandate_id}/confirm
```

No request body.

**Response 200:**
```json
{
  "id": "uuid",
  "status": "active",
  "confirmed_at": "2026-03-15T14:22:00Z",
  "completeness_score": 0.90
}
```

**Response 422:**
```json
{
  "error": "validation_error",
  "message": "Mandate completeness score too low to confirm",
  "details": {
    "current_score": 0.55,
    "required_score": 0.70
  }
}
```

---

### C2.7 — Update Mandate Field

```
PATCH /mandates/{mandate_id}/fields/{field_name}
```

**`field_name` values:** `intent_type`, `vertical`, `category`, `negotiation_range`, `hard_constraints`, `soft_preferences`, `dealbreakers`, `autonomy_level`

**Request body:**
```json
{
  "value": 500.00
}
```

Value type varies by field:
| Field | Value type |
|-------|-----------|
| `intent_type` | `"buy"` \| `"sell"` \| `"request_service"` \| `"offer_service"` \| `"discover"` |
| `vertical` | `"goods"` \| `"services"` |
| `category` | string |
| `negotiation_range` | `{ "floor": 300, "ceiling": 600, "opening": 500 }` |
| `autonomy_level` | `"supervised"` \| `"escalate_key_points"` \| `"fully_autonomous"` |
| `hard_constraints` | array of constraint objects |
| `soft_preferences` | array of preference objects |
| `dealbreakers` | array of string conditions |

**Response 200:**
```json
{
  "field": "negotiation_range",
  "new_value": { "floor": 300, "ceiling": 600, "opening": 500 },
  "source_flag": "explicit",
  "completeness_score": 0.88,
  "version": 3,
  "confirmed_at": null
}
```

Note: Updating a field on an active mandate clears `confirmed_at`. Owner must re-confirm.

---

### C2.8 — Get Mandate Audit Log

```
GET /mandates/{mandate_id}/audit
```

**Response 200:**
```json
{
  "fields": {
    "intent_type": {
      "current_value": "buy",
      "source_flag": "explicit",
      "history": [
        { "value": "buy", "source": "explicit", "version": 1, "set_at": "2026-03-15T14:01:00Z" }
      ]
    },
    "negotiation_range": {
      "current_value": { "floor": 300, "ceiling": 600 },
      "source_flag": "inferred",
      "history": [
        { "value": { "floor": 400, "ceiling": 700 }, "source": "inferred", "version": 1, "set_at": "2026-03-15T14:05:00Z" },
        { "value": { "floor": 300, "ceiling": 600 }, "source": "explicit", "version": 3, "set_at": "2026-03-15T14:20:00Z" }
      ]
    }
  },
  "current_version": 3,
  "completeness_score": 0.88
}
```

---

### C2.9 — Pause / Resume Mandate

```
POST /mandates/{mandate_id}/pause
POST /mandates/{mandate_id}/resume
```

No request body.

**Response 200:**
```json
{ "id": "uuid", "status": "paused" }
```

---

### C2.10 — Get Agent Activity Log

```
GET /agents/me/activity
```

**Query params:** `limit` (default 20), `cursor`, `type` (filter by action type)

**Response 200:**
```json
{
  "activities": [
    {
      "id": "uuid",
      "type": "mandate_confirmed",
      "mandate_id": "uuid",
      "description": "Mandate for furniture confirmed and agent activated",
      "created_at": "2026-03-15T14:22:00Z"
    },
    {
      "id": "uuid",
      "type": "search_run",
      "mandate_id": "uuid",
      "description": "Agent searched marketplace — 8 matches found",
      "metadata": { "match_count": 8, "top_score": 0.87 },
      "created_at": "2026-03-15T18:00:00Z"
    }
  ],
  "next_cursor": "cursor_or_null"
}
```

**`type` values:** `mandate_created`, `mandate_confirmed`, `mandate_refined`, `search_run`, `match_found`, `escalation_triggered`, `escalation_resolved`, `introduction_proposed`, `chat_created`, `negotiation_started`, `negotiation_state_changed`, `alignment_reached`

---

## Phase 3 Contracts — Browse & Match
*Available by end of Week 18*

---

### C3.1 — Trigger Agent Search

```
POST /mandates/{mandate_id}/search
```

No request body. Agent runs match ranking against all active listings.

**Response 200:**
```json
{
  "search_id": "uuid",
  "match_count": 6,
  "matches": [
    {
      "id": "uuid",
      "listing_id": "uuid",
      "listing": {
        "id": "uuid",
        "title": "Mid-Century Modern Sofa — Excellent Condition",
        "category": "furniture",
        "price": 450.00,
        "condition": "excellent",
        "location_text": "The Heights, Houston TX",
        "photos": ["https://cdn.tarpspace.com/photos/uuid.jpg"],
        "seller_display_name": "Jordan M."
      },
      "total_score": 0.87,
      "score_components": {
        "semantic": 0.91,
        "trust": 0.30,
        "constraint_satisfied": true,
        "price_overlap": 0.85,
        "location_proximity": 0.72,
        "reliability": 0.50
      },
      "trust_connection_label": "no_connection",
      "explanation": "Strong semantic match — mid-century style, excellent condition, within your $400–$600 range, and just 2.1km from your location.",
      "is_cold_start": true,
      "owner_decision": null,
      "created_at": "2026-03-15T18:00:00Z"
    }
  ]
}
```

**`trust_connection_label` values:** `direct_connection` | `second_connection` | `community_member` | `no_connection`

**`is_cold_start: true`** means trust score was replaced by community overlap fallback (user has < 3 trust edges).

---

### C3.2 — Get Match Results

```
GET /mandates/{mandate_id}/matches
```

**Query params:** `limit` (default 20), `cursor`, `decision` (`accepted`, `rejected`, `pending`)

**Response 200:** Same shape as matches array in C3.1.

---

### C3.3 — Record Match Decision

```
POST /matches/{match_id}/decision
```

**Request body:**
```json
{
  "decision": "rejected",
  "rejection_reason": "too_expensive"
}
```

**`decision` values:** `accepted` | `rejected`

**`rejection_reason` values** (only when `decision: rejected`):
`too_expensive` | `wrong_location` | `wrong_condition` | `not_what_i_wanted` | `seller_unresponsive` | `other`

**Response 200:**
```json
{
  "match_id": "uuid",
  "decision": "rejected",
  "mandate_refined": true,
  "refinement_note": "Agent noted price sensitivity — will weight price more in future searches"
}
```

---

### C3.4 — Get Pending Escalations

```
GET /mandates/{mandate_id}/escalations
```

**Response 200:**
```json
{
  "escalations": [
    {
      "id": "uuid",
      "question": "A listing matched everything except it's in Midtown rather than the Heights. Is location within 5km acceptable to you?",
      "context": {
        "listing_title": "Mid-Century Sofa — Great Condition",
        "blocking_dimension": "location",
        "listing_value": "Midtown, Houston",
        "mandate_value": "The Heights, Houston"
      },
      "created_at": "2026-03-15T18:30:00Z"
    }
  ]
}
```

---

### C3.5 — Answer Escalation

```
POST /escalations/{escalation_id}/answer
```

**Request body:**
```json
{
  "answer": "yes"
}
```

**`answer` values:** `yes` | `no`

**Response 200:**
```json
{
  "escalation_id": "uuid",
  "answer": "yes",
  "mandate_updated": true,
  "updated_field": "location",
  "updated_value": "5km radius from Heights, Houston"
}
```

---

### C3.6 — Create Listing (Seller)

```
POST /listings
```

**Request body (multipart/form-data):**
```
title: "Mid-Century Modern Sofa"
category: "furniture"
vertical: "goods"
price: 450.00
condition: "excellent"
description: "Gorgeous MCM sofa, no tears, pick up only"
location_text: "The Heights, Houston TX"
location_lat: 29.7838
location_lng: -95.4052
photos: [file1, file2, file3]   (max 5, each max 10MB)
```

**Response 201:**
```json
{
  "id": "uuid",
  "title": "Mid-Century Modern Sofa",
  "category": "furniture",
  "price": 450.00,
  "condition": "excellent",
  "status": "active",
  "photos": ["https://cdn.tarpspace.com/photos/uuid.jpg"],
  "created_at": "2026-03-15T14:00:00Z"
}
```

---

### C3.7 — Get My Listings (Seller)

```
GET /listings/mine
```

**Query params:** `status` (`active`, `sold`, `removed`, `all`), `limit`, `cursor`

**Response 200:**
```json
{
  "listings": [
    {
      "id": "uuid",
      "title": "Mid-Century Modern Sofa",
      "category": "furniture",
      "price": 450.00,
      "status": "active",
      "view_count": 14,
      "match_count": 3,
      "photos": ["https://cdn.tarpspace.com/photos/uuid.jpg"],
      "created_at": "2026-03-15T14:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

## Phase 4 Contracts — Trust & Community
*Available by end of Week 28*

---

### C4.1 — Get Trust Profile

```
GET /trust/me
```

**Response 200:**
```json
{
  "trust_score": 0.72,
  "connection_count": 8,
  "vouched_by_count": 3,
  "vouched_for_count": 5,
  "community_count": 2,
  "is_cold_start": false
}
```

---

### C4.2 — List Trust Connections

```
GET /trust/connections
```

**Response 200:**
```json
{
  "connections": [
    {
      "user_id": "uuid",
      "display_name": "Jordan M.",
      "edge_type": "TRANSACTION",
      "weight": 0.9,
      "created_at": "2026-03-10T10:00:00Z"
    },
    {
      "user_id": "uuid",
      "display_name": "Sam K.",
      "edge_type": "VOUCHED",
      "weight": 0.6,
      "can_revoke": true,
      "created_at": "2026-03-12T10:00:00Z"
    }
  ]
}
```

---

### C4.3 — Get Trust Score to Specific User

```
GET /trust/score/{user_id}
```

**Response 200:**
```json
{
  "from_user_id": "uuid",
  "to_user_id": "uuid",
  "trust_score": 0.72,
  "connection_label": "direct_connection",
  "path_description": "You completed a transaction with this person",
  "hop_count": 1
}
```

---

### C4.4 — Vouch for a User

```
POST /vouches
```

**Request body:**
```json
{
  "user_id": "uuid"
}
```

**Response 201:**
```json
{
  "from_user_id": "uuid",
  "to_user_id": "uuid",
  "edge_type": "VOUCHED",
  "weight": 0.6,
  "created_at": "2026-03-15T14:00:00Z"
}
```

**Response 422 — cannot vouch for yourself:**
```json
{ "error": "validation_error", "message": "You cannot vouch for yourself" }
```

---

### C4.5 — Revoke Vouch

```
DELETE /vouches/{user_id}
```

No request body.

**Response 200:**
```json
{ "revoked": true, "user_id": "uuid" }
```

---

### C4.6 — Search Users (for Vouch)

```
GET /users/search
```

**Query params:** `q` (search term — name or email), `limit` (default 10)

**Response 200:**
```json
{
  "users": [
    {
      "id": "uuid",
      "display_name": "Jordan M.",
      "trust_connection": "community_member",
      "already_vouched": false
    }
  ]
}
```

---

### C4.7 — List Communities

```
GET /communities
```

**Response 200:**
```json
{
  "communities": [
    {
      "id": "uuid",
      "name": "The Heights Neighborhood",
      "type": "neighborhood",
      "member_count": 142,
      "is_member": false,
      "requires_verification": true
    }
  ]
}
```

---

### C4.8 — Join Community

```
POST /communities/{community_id}/join
```

No request body.

**Response 200:**
```json
{
  "community_id": "uuid",
  "user_id": "uuid",
  "verified_at": "2026-03-15T14:00:00Z",
  "trust_edges_created": 3
}
```

---

### C4.9 — List Introductions

```
GET /mandates/{mandate_id}/introductions
```

**Response 200:**
```json
{
  "introductions": [
    {
      "id": "uuid",
      "status": "pending",
      "listing": {
        "id": "uuid",
        "title": "Mid-Century Modern Sofa",
        "price": 450.00,
        "photos": ["https://cdn.tarpspace.com/photos/uuid.jpg"]
      },
      "match_score": 0.91,
      "trust_connection_label": "community_member",
      "alignment_summary": "Matched on price, location, and condition. Seller is a community member.",
      "created_at": "2026-03-15T18:00:00Z"
    }
  ]
}
```

---

### C4.10 — Accept Introduction

```
POST /introductions/{introduction_id}/accept
```

No request body.

**Response 200:**
```json
{
  "introduction_id": "uuid",
  "chat_id": "uuid",
  "chat_created": true
}
```

**Dev B:** On success, navigate directly to the chat screen using `chat_id`.

---

### C4.11 — Decline Introduction

```
POST /introductions/{introduction_id}/decline
```

**Request body:**
```json
{
  "reason": "not_ready"
}
```

**`reason` values:** `not_ready` | `price_not_right` | `found_alternative` | `other`

**Response 200:**
```json
{ "introduction_id": "uuid", "declined": true }
```

---

### C4.12 — Get Owner Chat

```
GET /chats/{chat_id}
```

**Response 200:**
```json
{
  "id": "uuid",
  "status": "active",
  "alignment_snapshot": {
    "aligned_dimensions": ["price", "location", "category", "condition"],
    "agreed_position": 425.00,
    "open_items": ["pickup scheduling"],
    "trust_connection": "Community member — The Heights Neighborhood"
  },
  "counterparty": {
    "display_name": "Jordan M.",
    "trust_score": 0.72,
    "connection_label": "community_member"
  },
  "created_at": "2026-03-15T19:00:00Z"
}
```

---

### C4.13 — Get Chat Messages

```
GET /chats/{chat_id}/messages
```

**Query params:** `limit` (default 50), `cursor`

**Response 200:**
```json
{
  "messages": [
    {
      "id": "uuid",
      "sender_id": "uuid",
      "sender_name": "Jordan M.",
      "is_mine": false,
      "content": "Hey! I saw your agent matched with mine. Are you still looking for a sofa?",
      "created_at": "2026-03-15T19:05:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### C4.14 — Send Chat Message

```
POST /chats/{chat_id}/messages
```

**Request body:**
```json
{
  "content": "Yes! I'm still looking. When could I come take a look?"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "sender_id": "uuid",
  "content": "Yes! I'm still looking. When could I come take a look?",
  "created_at": "2026-03-15T19:10:00Z"
}
```

---

### C4.15 — Record Transaction Outcome

```
POST /chats/{chat_id}/outcome
```

**Request body:**
```json
{
  "outcome": "completed",
  "rating": 5,
  "review": "Great seller, sofa was exactly as described. Highly recommend!"
}
```

**`outcome` values:** `completed` | `cancelled` | `disputed`

**Response 200:**
```json
{
  "chat_id": "uuid",
  "outcome": "completed",
  "trust_edge_created": true,
  "trust_edge_weight": 0.7
}
```

---

### C4.16 — Generate Referral Link

```
POST /referrals
```

No request body.

**Response 201:**
```json
{
  "code": "ALEX-X7K2",
  "url": "https://tarpspace.com/join?ref=ALEX-X7K2",
  "created_at": "2026-03-15T14:00:00Z"
}
```

---

### C4.17 — Get My Referrals

```
GET /referrals/mine
```

**Response 200:**
```json
{
  "referrals": [
    {
      "code": "ALEX-X7K2",
      "invitee_name": "Sam K.",
      "status": "completed",
      "trust_edge_weight": 0.7,
      "created_at": "2026-03-10T14:00:00Z"
    }
  ],
  "total_sent": 3,
  "total_completed": 1
}
```

---

## Phase 5 Contracts — Agent-to-Agent Network
*Available by end of Week 42*

---

### C5.1 — Get Active Negotiation Threads

```
GET /mandates/{mandate_id}/threads
```

**Response 200:**
```json
{
  "threads": [
    {
      "id": "uuid",
      "state": "NEGOTIATING",
      "sequence": 4,
      "convergence_score": 0.73,
      "gap_dimension": null,
      "counterparty_category": "furniture",
      "time_in_state_seconds": 142,
      "created_at": "2026-03-15T19:00:00Z",
      "updated_at": "2026-03-15T19:02:00Z"
    },
    {
      "id": "uuid",
      "state": "ESCALATING",
      "sequence": 2,
      "convergence_score": 0.55,
      "gap_dimension": "location",
      "counterparty_category": "furniture",
      "escalation_question": "Counterparty is 8km away. Is this acceptable?",
      "time_in_state_seconds": 320,
      "created_at": "2026-03-15T19:00:00Z",
      "updated_at": "2026-03-15T19:05:00Z"
    }
  ],
  "active_count": 2,
  "max_allowed": 10
}
```

**`state` values:** `SEEKING` | `PROBING` | `NEGOTIATING` | `ESCALATING` | `ALIGNED` | `ALIGNED_PENDING_HANDOFF` | `CLOSED_SUCCESS` | `CLOSED_NO_MATCH` | `ABANDONED`

**`convergence_score`:** 0.0–1.0. How close to alignment. 1.0 = aligned.

**`gap_dimension`:** Only present when state is `ESCALATING` or thread is stalled. Name of the dimension preventing progress.

---

### C5.2 — Get Thread Detail

```
GET /threads/{thread_id}
```

**Response 200:**
```json
{
  "id": "uuid",
  "state": "NEGOTIATING",
  "sequence": 4,
  "convergence_score": 0.73,
  "gap_dimension": null,
  "counterparty_category": "furniture",
  "state_history": [
    { "state": "SEEKING", "entered_at": "2026-03-15T19:00:00Z", "duration_seconds": 2 },
    { "state": "PROBING", "entered_at": "2026-03-15T19:00:02Z", "duration_seconds": 8 },
    { "state": "NEGOTIATING", "entered_at": "2026-03-15T19:00:10Z", "duration_seconds": 142 }
  ],
  "created_at": "2026-03-15T19:00:00Z",
  "updated_at": "2026-03-15T19:02:00Z"
}
```

---

### C5.3 — Approve Negotiation Step (Supervised Mode)

```
POST /threads/{thread_id}/approve
```

**Request body:**
```json
{
  "approved": true
}
```

**Response 200:**
```json
{
  "thread_id": "uuid",
  "approved": true,
  "next_state": "NEGOTIATING",
  "agent_action": "Sending position signal: $425"
}
```

---

### C5.4 — Answer Thread Escalation

```
POST /threads/{thread_id}/escalation/answer
```

**Request body:**
```json
{
  "answer": "yes"
}
```

**Response 200:**
```json
{
  "thread_id": "uuid",
  "answer": "yes",
  "thread_resumed": true,
  "mandate_updated_field": "location",
  "new_state": "NEGOTIATING"
}
```

---

### C5.5 — Abandon Thread

```
POST /threads/{thread_id}/abandon
```

**Request body:**
```json
{
  "reason": "changed_my_mind"
}
```

**Response 200:**
```json
{ "thread_id": "uuid", "state": "ABANDONED" }
```

---

### C5.6 — Get Agent Network Status (for Visualization)

```
GET /agents/me/network-status
```

**Response 200:**
```json
{
  "agent_id": "uuid",
  "active_threads": 3,
  "seeking_count": 1,
  "probing_count": 1,
  "negotiating_count": 1,
  "pending_escalations": 1,
  "network_density": {
    "furniture_houston": 0.62,
    "services_houston": 0.38
  }
}
```

---

### C5.7 — Get Agent Reputation

```
GET /agents/me/reputation
```

**Response 200:**
```json
{
  "agent_id": "uuid",
  "reputation_score": 0.78,
  "completed_negotiations": 12,
  "total_negotiations": 15,
  "owner_follow_through_rate": 0.91,
  "avg_response_time_seconds": 45,
  "fully_autonomous_unlocked": false,
  "negotiations_until_unlock": 3
}
```

---

## WebSocket Events Reference

All events pushed from server to client over the authenticated WebSocket connection.

### Event: `negotiation_state_changed`
```json
{
  "event": "negotiation_state_changed",
  "thread_id": "uuid",
  "mandate_id": "uuid",
  "from_state": "PROBING",
  "to_state": "NEGOTIATING",
  "convergence_score": 0.61,
  "gap_dimension": null,
  "timestamp": "2026-03-15T19:00:10Z"
}
```

### Event: `alignment_reached`
```json
{
  "event": "alignment_reached",
  "thread_id": "uuid",
  "mandate_id": "uuid",
  "aligned_dimensions": ["price", "location", "category"],
  "timestamp": "2026-03-15T19:05:00Z"
}
```

### Event: `escalation_triggered`
```json
{
  "event": "escalation_triggered",
  "thread_id": "uuid",
  "mandate_id": "uuid",
  "escalation_id": "uuid",
  "question": "Counterparty is 8km away instead of 5km. Is this acceptable?",
  "gap_dimension": "location",
  "timestamp": "2026-03-15T19:03:00Z"
}
```

### Event: `owner_chat_created`
```json
{
  "event": "owner_chat_created",
  "thread_id": "uuid",
  "chat_id": "uuid",
  "mandate_id": "uuid",
  "alignment_summary": "Matched on price, location, and category",
  "timestamp": "2026-03-15T19:06:00Z"
}
```

### Event: `introduction_proposed`
```json
{
  "event": "introduction_proposed",
  "introduction_id": "uuid",
  "mandate_id": "uuid",
  "match_score": 0.91,
  "trust_connection_label": "community_member",
  "listing_title": "Mid-Century Modern Sofa",
  "timestamp": "2026-03-15T18:00:00Z"
}
```

### Event: `match_found`
```json
{
  "event": "match_found",
  "mandate_id": "uuid",
  "match_id": "uuid",
  "total_score": 0.87,
  "listing_title": "Mid-Century Modern Sofa",
  "timestamp": "2026-03-15T18:00:00Z"
}
```

### Event: `new_chat_message`
```json
{
  "event": "new_chat_message",
  "chat_id": "uuid",
  "message_id": "uuid",
  "sender_name": "Jordan M.",
  "is_mine": false,
  "content_preview": "Hey! Are you still looking...",
  "timestamp": "2026-03-15T19:05:00Z"
}
```

### Event: `mandate_refined`
```json
{
  "event": "mandate_refined",
  "mandate_id": "uuid",
  "refined_field": "soft_preferences",
  "trigger": "rejection_feedback",
  "new_completeness_score": 0.91,
  "timestamp": "2026-03-15T18:30:00Z"
}
```

---

## Contract Change Log

| Date | Contract | Change | Dev A | Dev B |
|------|----------|--------|-------|-------|
| March 2026 | All | Initial version | ✅ | ✅ |

**Instructions for changes:**
1. Dev A edits the contract entry and adds `[CHANGED - Week X]` to the section title
2. Dev A adds a row to this change log
3. Dev A notifies Dev B via Slack/message
4. Dev B acknowledges and updates frontend before the next week's sprint

---

*Tarp-Space CONTRACTS.md v1.0 · Confidential · March 2026*
