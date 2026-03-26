"""
Gap analysis — ARCHITECTURE.md Section 3.1
Rule-based (no LLM). Runs after extraction pass.
Computes completeness score and identifies highest-priority unfilled field.

Priority order (from ARCHITECTURE.md):
  1. intent_type
  2. vertical
  3. category
  4. price / budget
  5. location
  6. condition
  7. timing
  8. style / aesthetic
  9. dealbreakers
  10. autonomy_level  (never extracted — always explicitly set)
"""
# TODO: implement in Phase 1 conversation sprint
