"""
Escalation flagging — ARCHITECTURE.md Section 3.4, Stage 3
No LLM. Flags candidates that failed hard filter only due to price.

Threshold: mandate.price_ceiling × (1 + ESCALATION_THRESHOLD_PCT)  [default 1.15]
Condition: candidate.price <= threshold AND similarity_score >= 0.75

Escalation candidates returned in separate 'escalations' array, not main results.
"""
# TODO: implement in Phase 1 matching sprint
