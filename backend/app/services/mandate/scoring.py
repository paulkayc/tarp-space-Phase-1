"""
Completeness score — ARCHITECTURE.md Section 3.2

Formula:
  completeness_score =
    0.35 × (intent_type AND vertical AND category filled)
    + 0.20 × price_range_filled
    + 0.15 × location_filled
    + 0.075 × condition_filled
    + 0.075 × timing_filled
    + 0.10 × (len(soft_preferences) > 0)
    + 0.05 × (len(dealbreakers) >= 0)   # always contributes

Minimum to activate mandate: 0.7 (COMPLETENESS_THRESHOLD env var)
"""
# TODO: implement in Phase 1 mandate sprint
