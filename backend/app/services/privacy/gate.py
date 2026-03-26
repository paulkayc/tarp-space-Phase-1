"""
Privacy Gate — ARCHITECTURE.md Section 3.3
Owner: Dev B

Pure function: gate(mandate) → sanitized_signal
No side effects other than logging. Never calls an LLM.
Runs BEFORE any mandate data is passed to the matching engine.

Hard rules (Phase 1):
  - negotiation_range ceiling/floor → stripped to positional signal
  - dealbreakers → boolean satisfaction signal only (never raw)
  - hard_constraints → boolean satisfaction signal only (never raw)
  - opening position must not equal ceiling or floor
  - location → fuzzy bounding box (exact coords only after introduction in Phase 2)

Every gate decision logged as privacy_gate_decision event regardless of outcome.
"""
# TODO: implement in Phase 1 privacy/matching sprint
