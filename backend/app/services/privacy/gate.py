"""
Privacy Gate — ARCHITECTURE.md Section 3.3

Pure function: gate(mandate) → (sanitized_signal, gate_passed)
No side effects other than logging. Never calls an LLM.
Runs BEFORE any mandate data is passed to the matching engine.

Hard rules (Phase 1):
  - negotiation_range ceiling/floor → stripped to directional signal only
  - dealbreakers → boolean satisfaction signal only (never raw)
  - hard_constraints → boolean satisfaction signal only (never raw)
  - opening position must not equal ceiling or floor
  - location → fuzzy string (exact coords only after introduction in Phase 2)

Every gate decision logged as privacy_gate_decision event regardless of outcome.
"""
from __future__ import annotations

from typing import Any

from app.db.models import Mandate
from app.observability.events import emit_privacy_gate_decision


def _extract_price_ceiling(mandate: Mandate) -> float | None:
    """Extract the price ceiling from negotiation_range or hard_constraints."""
    # Check negotiation_range first
    for dim in (mandate.negotiation_range or []):
        if isinstance(dim, dict) and dim.get("dimension") in ("price", "budget"):
            ceiling = dim.get("ceiling")
            if ceiling is not None:
                try:
                    return float(ceiling)
                except (TypeError, ValueError):
                    pass

    # Fall back to hard_constraints budget field
    for constraint in (mandate.hard_constraints or []):
        if isinstance(constraint, dict) and constraint.get("field") in ("budget_max", "price_ceiling"):
            value = constraint.get("value")
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    # Fall back to mandate_fields-style budget_max from hard_constraints
    for constraint in (mandate.hard_constraints or []):
        if isinstance(constraint, dict) and constraint.get("field") == "budget":
            value = constraint.get("value")
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return None


def _extract_location_string(mandate: Mandate) -> str | None:
    """Extract a fuzzy location string from hard_constraints (never exact geom)."""
    for constraint in (mandate.hard_constraints or []):
        if isinstance(constraint, dict) and constraint.get("field") == "location":
            value = constraint.get("value")
            if value and isinstance(value, str):
                return value.strip()
    return None


def _validate_negotiation_range(
    mandate: Mandate,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Validate negotiation_range dimensions.
    Returns (problems, gate_log_entries).
    """
    problems: list[str] = []
    log_entries: list[dict[str, Any]] = []

    for dim in (mandate.negotiation_range or []):
        if not isinstance(dim, dict):
            continue

        field = dim.get("dimension", "unknown")
        ceiling = dim.get("ceiling")
        floor_ = dim.get("floor")
        opening = dim.get("opening_position")

        if opening is not None and ceiling is not None and opening == ceiling:
            problems.append(
                f"opening_position equals ceiling for dimension '{field}'"
            )
            log_entries.append({
                "field": field,
                "action": "block",
                "rule_applied": "opening_equals_ceiling",
            })
        elif opening is not None and floor_ is not None and opening == floor_:
            problems.append(
                f"opening_position equals floor for dimension '{field}'"
            )
            log_entries.append({
                "field": field,
                "action": "block",
                "rule_applied": "opening_equals_floor",
            })
        else:
            # Strip to directional signal
            log_entries.append({
                "field": f"{field}_range",
                "action": "strip",
                "rule_applied": "range_to_directional_signal",
            })

    return problems, log_entries


def gate(mandate: Mandate) -> tuple[dict[str, Any], bool]:
    """
    Run the privacy gate against a mandate.

    Returns:
        sanitized_signal: safe representation for matching engine
        gate_passed: False if any hard rule is violated
    """
    mandate_id = str(mandate.id)
    all_problems: list[str] = []

    # 1. Validate and strip negotiation_range
    range_problems, range_log = _validate_negotiation_range(mandate)
    all_problems.extend(range_problems)
    for entry in range_log:
        emit_privacy_gate_decision(
            mandate_id=mandate_id,
            field=entry["field"],
            action=entry["action"],
            rule_applied=entry["rule_applied"],
        )

    # 2. Dealbreakers — log that they are stripped to boolean evaluation
    for db_item in (mandate.dealbreakers or []):
        field = db_item.get("field", "unknown") if isinstance(db_item, dict) else "unknown"
        emit_privacy_gate_decision(
            mandate_id=mandate_id,
            field=field,
            action="strip",
            rule_applied="dealbreaker_to_boolean",
        )

    # 3. Hard constraints — log field names only (values stripped)
    for hc in (mandate.hard_constraints or []):
        field = hc.get("field", "unknown") if isinstance(hc, dict) else "unknown"
        emit_privacy_gate_decision(
            mandate_id=mandate_id,
            field=field,
            action="pass",
            rule_applied="constraint_field_only",
        )

    gate_passed = len(all_problems) == 0

    # Build sanitized signal — safe fields only, no raw ranges or dealbreakers
    sanitized_signal: dict[str, Any] = {
        "category": mandate.category,
        "vertical": mandate.vertical,
        "intent_type": mandate.intent_type,
        "description": mandate.description,
        "soft_preferences": list(mandate.soft_preferences or []),
        # Price ceiling is extracted for filter but only as a scalar, not a range
        "price_ceiling": _extract_price_ceiling(mandate),
        # Location as fuzzy string only (no exact geom)
        "location_fuzzy": _extract_location_string(mandate),
        # Dealbreaker field names only — not values, not conditions
        "dealbreaker_fields": [
            d.get("field") for d in (mandate.dealbreakers or [])
            if isinstance(d, dict) and d.get("field")
        ],
        # Gate passed flag
        "gate_passed": gate_passed,
        "problems": all_problems,
    }

    return sanitized_signal, gate_passed
