"""
Rule-based gap analysis for onboarding/persona collection.
"""
from __future__ import annotations

from typing import Any


_GAP_ORDER = [
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

_QUESTIONS = {
    "intent_type": "What are you trying to do right now: buy, sell, or find a service?",
    "vertical": "Is this for goods or services?",
    "category": "What category best describes what you need?",
    "budget": "What budget range should I target?",
    "location": "Which location should I focus on?",
    "condition": "What condition is acceptable?",
    "timing": "When do you need this completed?",
    "style_preferences": "Any style or preference I should prioritize?",
    "dealbreakers": "Any dealbreakers I should always avoid?",
    "autonomy_level": "How autonomous should I be: supervised, escalate key points, or fully autonomous?",
}


def _is_filled(persona: dict[str, Any], key: str) -> bool:
    if key not in persona:
        return False
    value = persona[key]
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def analyze_gaps(persona: dict[str, Any]) -> dict[str, Any]:
    gaps_remaining = [key for key in _GAP_ORDER if not _is_filled(persona, key)]
    next_gap = gaps_remaining[0] if gaps_remaining else None
    return {
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "next_question": _QUESTIONS.get(next_gap) if next_gap else None,
    }


def compute_onboarding_completeness(persona: dict[str, Any]) -> float:
    has_triplet = _is_filled(persona, "intent_type") and _is_filled(persona, "vertical") and _is_filled(
        persona, "category"
    )
    has_budget = _is_filled(persona, "budget")
    has_location = _is_filled(persona, "location")
    has_condition = _is_filled(persona, "condition")
    has_timing = _is_filled(persona, "timing")
    has_style = _is_filled(persona, "style_preferences")
    has_dealbreakers_key = "dealbreakers" in persona
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
