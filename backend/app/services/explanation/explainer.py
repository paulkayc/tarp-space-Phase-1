"""
Match explanation — ARCHITECTURE.md Section 3.5
LLM call per top-N result (max 5 per search).
Input:  listing metadata + mandate summary + matched dimensions
Output: 2–3 sentence plain-language explanation.
Constraint: only reference attributes present in listing metadata (no hallucination).
Output validated against listing schema before returning to client.
"""
# TODO: implement in Phase 1 explanation sprint
