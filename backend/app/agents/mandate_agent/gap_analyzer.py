"""
Rule-based gap analysis for mandate collection.

Tracks what the user WANTS for a specific transaction (intent, category,
budget, location, etc.).  Personal profile gap analysis lives in
app.services.conversation.gap_analyzer.
"""
from __future__ import annotations

from typing import Any


_MANDATE_GAP_ORDER = [
    "intent_type",
    "vertical",
    "category",
    "budget",
    "location",
    "condition",
    "timing",
    "style_preferences",
    "dealbreakers",
    "autonomy_level",
]

_MANDATE_QUESTIONS = {
    "intent_type": "What are you trying to do — buy, sell, or find a service?",
    "vertical": "Is this for goods or services?",
    "category": "What category best describes what you need?",
    "budget": "What budget range should I target?",
    "location": "Which area should I focus on?",
    "condition": "What condition is acceptable?",
    "timing": "When do you need this completed?",
    "style_preferences": "Any style or preference I should prioritise?",
    "dealbreakers": "Any dealbreakers I should always avoid?",
    "autonomy_level": "How autonomous should I be: supervised, escalate key points, or fully autonomous?",
}

_CATEGORY_DETAIL_PROMPTS = {
    "car": "Do you have a specific car in mind, or should I focus on a body style like sedan or SUV?",
    "vehicle": "Do you have a specific vehicle in mind, or should I focus on a body style like sedan, SUV, or truck?",
    "automobile": "Do you have a specific automobile in mind, or should I focus on a body style like sedan or SUV?",
}


def _normalized_text(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _needs_category_detail(state: dict[str, Any]) -> bool:
    """Return True when we should ask a category-specific clarification question.

    We ask for extra detail only after a category is present and before style
    preferences are captured, which allows us to use style preferences for
    practical subtype details (for example: sedan vs SUV).
    """
    category = _normalized_text(state.get("category"))
    if not category or _is_filled(state, "style_preferences"):
        return False
    return category in _CATEGORY_DETAIL_PROMPTS


def _category_detail_question(state: dict[str, Any]) -> str:
    category = _normalized_text(state.get("category"))
    return _CATEGORY_DETAIL_PROMPTS.get(
        category,
        "Any specific type or variant you want me to focus on?",
    )


def _is_filled(state: dict[str, Any], key: str) -> bool:
    if key not in state:
        return False
    value = state[key]
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def analyze_mandate_gaps(mandate_state: dict[str, Any]) -> dict[str, Any]:
    """Return gaps and the next question for a mandate elicitation conversation.

    mandate_state is a flat dict with keys matching _MANDATE_GAP_ORDER
    (derived from the Mandate DB record via derive_mandate_state()).
    """
    gaps_remaining = [key for key in _MANDATE_GAP_ORDER if not _is_filled(mandate_state, key)]
    if _needs_category_detail(mandate_state):
        gaps_remaining.insert(0, "category_detail")
    next_gap = gaps_remaining[0] if gaps_remaining else None
    next_question = _MANDATE_QUESTIONS.get(next_gap) if next_gap else None
    if next_gap == "category_detail":
        next_question = _category_detail_question(mandate_state)

    return {
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "next_question": next_question,
    }


def compute_mandate_completeness(mandate_state: dict[str, Any]) -> float:
    """Score 0-1 based on how complete the mandate fields are.

    Weights mirror the original onboarding completeness scorer:
      intent + vertical + category  0.35
      budget                        0.20
      location                      0.15
      condition                     0.075
      timing                        0.075
      style_preferences             0.10
      dealbreakers (key present)    0.05
    """
    has_triplet = (
        _is_filled(mandate_state, "intent_type")
        and _is_filled(mandate_state, "vertical")
        and _is_filled(mandate_state, "category")
    )
    has_budget = _is_filled(mandate_state, "budget")
    has_location = _is_filled(mandate_state, "location")
    has_condition = _is_filled(mandate_state, "condition")
    has_timing = _is_filled(mandate_state, "timing")
    has_style = _is_filled(mandate_state, "style_preferences")
    has_dealbreakers_key = "dealbreakers" in mandate_state

    has_meaningful_data = any(
        [has_triplet, has_budget, has_location, has_condition, has_timing, has_style, has_dealbreakers_key]
    )
    if not has_meaningful_data:
        return 0.0

    score = 0.0
    score += 0.35 if has_triplet else 0.0
    score += 0.20 if has_budget else 0.0
    score += 0.15 if has_location else 0.0
    score += 0.075 if has_condition else 0.0
    score += 0.075 if has_timing else 0.0
    score += 0.10 if has_style else 0.0
    score += 0.05 if has_dealbreakers_key else 0.0
    return round(min(score, 1.0), 3)


def derive_mandate_state(mandate: "Mandate") -> dict[str, Any]:  # type: ignore[name-defined]
    """Flatten a Mandate ORM record into the dict shape expected by gap analysis."""
    state: dict[str, Any] = {}

    if mandate.intent_type:
        state["intent_type"] = mandate.intent_type
    if mandate.vertical:
        state["vertical"] = mandate.vertical
    if mandate.category:
        state["category"] = mandate.category
    if mandate.autonomy_level and mandate.autonomy_level != "escalate_key_points":
        state["autonomy_level"] = mandate.autonomy_level

    if isinstance(mandate.negotiation_range, list):
        for item in mandate.negotiation_range:
            if isinstance(item, dict) and item.get("dimension") == "price":
                budget: dict[str, Any] = {}
                if "min" in item:
                    budget["min"] = item["min"]
                if "max" in item:
                    budget["max"] = item["max"]
                if budget:
                    state["budget"] = budget
                break

    if isinstance(mandate.hard_constraints, list):
        for constraint in mandate.hard_constraints:
            if isinstance(constraint, dict):
                field = constraint.get("field")
                value = constraint.get("value")
                if field in ("location", "condition", "timing") and value:
                    state[field] = value

    if isinstance(mandate.soft_preferences, list):
        styles = [
            p["value"]
            for p in mandate.soft_preferences
            if isinstance(p, dict) and p.get("field") == "style" and p.get("value")
        ]
        if styles:
            state["style_preferences"] = styles

    if isinstance(mandate.dealbreakers, list) and mandate.dealbreakers:
        state["dealbreakers"] = [d for d in mandate.dealbreakers if d]

    return state


def apply_delta_to_mandate(mandate: "Mandate", delta: dict[str, Any]) -> None:  # type: ignore[name-defined]
    """Merge a mandate delta (from extract_mandate_delta) back into the ORM record."""
    if "intent_type" in delta:
        mandate.intent_type = delta["intent_type"]
    if "vertical" in delta:
        mandate.vertical = delta["vertical"]
    if "category" in delta:
        mandate.category = delta["category"]
    if "autonomy_level" in delta:
        mandate.autonomy_level = delta["autonomy_level"]

    if "negotiation_range" in delta:
        existing = list(mandate.negotiation_range or [])
        for new_item in delta["negotiation_range"]:
            if isinstance(new_item, dict):
                existing = [i for i in existing if not (isinstance(i, dict) and i.get("dimension") == new_item.get("dimension"))]
                existing.append(new_item)
        mandate.negotiation_range = existing

    if "hard_constraints" in delta:
        existing = list(mandate.hard_constraints or [])
        for new_constraint in delta["hard_constraints"]:
            if isinstance(new_constraint, dict):
                existing = [c for c in existing if not (isinstance(c, dict) and c.get("field") == new_constraint.get("field"))]
                existing.append(new_constraint)
        mandate.hard_constraints = existing

    if "soft_preferences" in delta:
        existing = list(mandate.soft_preferences or [])
        for new_pref in delta["soft_preferences"]:
            if new_pref not in existing:
                existing.append(new_pref)
        mandate.soft_preferences = existing

    if "dealbreakers" in delta:
        existing = list(mandate.dealbreakers or [])
        for item in delta["dealbreakers"]:
            if item not in existing:
                existing.append(item)
        mandate.dealbreakers = existing
