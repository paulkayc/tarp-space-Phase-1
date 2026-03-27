from __future__ import annotations

from typing import Any

_PERSONA_GAP_ORDER = [
    "preferred_name",
    "city_or_area",
    "communication_style",
    "style_preferences",
    "personal_constraints",
]

_PERSONA_QUESTIONS = {
    "preferred_name": "What should I call you?",
    "city_or_area": "What city or area should I remember for you?",
    "communication_style": "Do you prefer concise or detailed responses?",
    "style_preferences": "Any recurring style preferences I should remember?",
    "personal_constraints": "Any personal constraints I should always keep in mind?",
}


def _is_filled(persona: dict[str, Any], key: str) -> bool:
    value = persona.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def analyze_persona_gaps(persona: dict[str, Any]) -> dict[str, Any]:
    gaps_remaining = [key for key in _PERSONA_GAP_ORDER if not _is_filled(persona, key)]
    next_gap = gaps_remaining[0] if gaps_remaining else None
    return {
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "next_question": _PERSONA_QUESTIONS.get(next_gap) if next_gap else None,
    }


def compute_persona_completeness(persona: dict[str, Any]) -> float:
    score = 0.0
    score += 0.25 if _is_filled(persona, "preferred_name") else 0.0
    score += 0.20 if _is_filled(persona, "city_or_area") else 0.0
    score += 0.20 if _is_filled(persona, "communication_style") else 0.0
    score += 0.20 if _is_filled(persona, "style_preferences") else 0.0
    score += 0.15 if _is_filled(persona, "personal_constraints") else 0.0
    return round(min(score, 1.0), 3)
