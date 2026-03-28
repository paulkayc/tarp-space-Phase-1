# tarp-space-Phase-1

Phase 1 of Tarp Space — Personal + Mandate Agent foundation.

## What this repository contains

- **Personal Agent**: captures reusable user context (for example home city and communication style).
- **Mandate Agent**: collects transaction-specific intent and constraints (buy/sell/service, budget, location, condition, timing, and preferences).
- **Backend + Frontend**: API services and web UI for interacting with both agents.

## Mandate Agent: specific follow-up question behavior

The Mandate Agent is designed to ask **one focused question at a time** and to request
more specific details when a request is too broad.

### Example

If a user says:

> “I want to buy a car.”

the agent should ask a targeted clarification such as:

> “Do you have a specific car in mind, or should I focus on a body style like sedan or SUV?”

This helps transform a broad mandate into a usable one for matching and ranking.

## Recommended approach for richer mandate detail

1. **Detect broad categories** early (e.g., car, vehicle, automobile).
2. **Ask a category-specific clarifier** before moving on to generic fields like budget/location.
3. **Capture subtype detail explicitly** (for example sedan/SUV or make/model) as structured preference data.
4. **Resume normal gap collection** after subtype detail is captured.
5. **Keep mandate and persona data separate** (do not ask onboarding/personal profile questions in mandate flow).

## Future improvements

- Expand targeted follow-up prompts to more categories (e.g., laptop, couch, apartment).
- Add first-class `subcategory` support for cleaner analytics and ranking signals.
- Add end-to-end conversation tests that assert specific clarification prompts in full runtime responses.
