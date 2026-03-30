"""
Mandate refinement from signals — ARCHITECTURE.md Section 5
Computes mandate delta from accept/reject signal + reason.
Example: reject reason "leather" → new dealbreaker source="inferred".
Surfaces refinement prompt to owner before applying.

Rules (all rule-based, no LLM):
  - accept: no mandate change
  - escalation_yes: ceiling raised by threshold_delta (marked source=inferred)
  - escalation_no: ceiling constraint tightened (marked source=inferred)
  - reject with reason: reason parsed for new dealbreaker keyword
  - reject without reason: no immediate change (pattern detection after 3+)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Mandate
from app.observability.events import emit_mandate_refined

# Simple keyword list for extracting dealbreakers from rejection reasons
_DEALBREAKER_KEYWORDS = [
    "leather", "plastic", "particle board", "ikea", "assembl",
    "damaged", "broken", "scratched", "stained", "smell",
    "far", "pickup only", "cash only",
]


def compute_mandate_delta(
    signal_type: str,
    reason: str | None,
    mandate: Mandate,
) -> dict | None:
    """
    Rule-based computation of mandate changes implied by a signal.
    Returns None if no change should be applied.
    """
    if signal_type == "accept":
        # Acceptance reinforces current preferences — no structural delta
        return None

    if signal_type == "escalation_yes":
        # Owner agreed to explore above-ceiling item — relax ceiling slightly
        # We don't change the mandate here; this is tracked as a signal only.
        # Full ceiling adjustment requires explicit owner action in Phase 1.
        return None

    if signal_type == "escalation_no":
        # Owner rejected above-ceiling item — tighten ceiling preference
        # In Phase 1, logged as signal; no automatic mandate mutation.
        return None

    if signal_type == "reject":
        if not reason:
            # No reason given — no immediate mandate update
            return None

        # Extract dealbreaker keywords from reason
        reason_lower = reason.lower()
        matched_keywords = [kw for kw in _DEALBREAKER_KEYWORDS if kw in reason_lower]

        if matched_keywords:
            # Propose adding matched keywords as inferred dealbreakers
            existing_fields = [
                d.get("field") for d in (mandate.dealbreakers or [])
                if isinstance(d, dict) and d.get("field")
            ]
            new_dealbreakers = [
                {"field": kw, "value": kw, "source": "inferred"}
                for kw in matched_keywords
                if kw not in existing_fields
            ]
            if new_dealbreakers:
                return {"add_dealbreakers": new_dealbreakers}

    return None


def apply_mandate_delta(
    db: Session,
    mandate: Mandate,
    delta: dict,
    trigger_signal_id: str,
) -> None:
    """
    Apply a computed mandate delta. Increments version. Emits mandate_refined events.
    """
    now = datetime.now(timezone.utc)

    add_dealbreakers = delta.get("add_dealbreakers", [])
    for db_item in add_dealbreakers:
        field = db_item.get("field", "unknown")
        old_value = list(mandate.dealbreakers or [])

        current = list(mandate.dealbreakers or [])
        existing_fields = [d.get("field") for d in current if isinstance(d, dict)]
        if field not in existing_fields:
            current.append(db_item)
            mandate.dealbreakers = current
            mandate.version = (mandate.version or 1) + 1
            mandate.updated_at = now

            emit_mandate_refined(
                mandate_id=str(mandate.id),
                field_changed="dealbreakers",
                trigger_signal_id=trigger_signal_id,
                old_value=old_value,
                new_value=current,
            )

    if add_dealbreakers:
        db.commit()
